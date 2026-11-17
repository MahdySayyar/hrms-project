"""Measure a native capacity baseline with synthetic records and steady-only Locust statistics."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import threading
import time
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import psutil
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.database import Admin, Base, Branch, Employee, Position, Unit
from app.hr_models import AuditLog, HrRequest
from app.security import hash_password
from tests.support import PostgresSandbox


def stop(process):
    """Stop only this runner's child process family, including Windows venv launchers."""
    if process is None:
        return
    family = processes(process.pid)
    for item in reversed(family):
        try:
            item.terminate()
        except psutil.Error:
            pass
    _, remaining = psutil.wait_procs(family, timeout=5)
    for item in remaining:
        try:
            item.kill()
        except psutil.Error:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def processes(pid):
    try:
        parent = psutil.Process(pid)
        return [parent, *parent.children(recursive=True)]
    except psutil.Error:
        return []


def sample_resources(server, generator, engine, marker, stopped, output):
    tracked = {}

    def process_totals(items):
        cpu, rss = 0, 0
        breakdown = []
        for item in items:
            try:
                used_cpu = 0
                if item.pid not in tracked:
                    tracked[item.pid] = item
                    item.cpu_percent()
                else:
                    used_cpu = tracked[item.pid].cpu_percent()
                used_rss = tracked[item.pid].memory_info().rss
                cpu += used_cpu
                rss += used_rss
                command = item.cmdline()
                role = "proxy" if "app.native_proxy:app" in command else "web" if "app.main:app" in command else "other"
                breakdown.append({"pid": item.pid, "role": role, "cpu_percent_one_core_100": used_cpu, "rss_bytes": used_rss})
            except psutil.Error:
                pass
        return cpu, rss, breakdown

    with output.open("x", encoding="utf-8") as stream:
        while not stopped.is_set():
            sample = {"time": time.time(), "host_cpu_percent": psutil.cpu_percent(),
                "host_available_ram_bytes": psutil.virtual_memory().available,
                "host_free_disk_bytes": psutil.disk_usage(str(ROOT)).free}
            for name, process in (("web", server), ("generator", generator)):
                cpu, rss, breakdown = process_totals(processes(process.pid))
                sample[name + "_cpu_percent_one_core_100"] = cpu
                sample[name + "_rss_bytes"] = rss
                sample[name + "_processes"] = breakdown
            try:
                with engine.connect() as connection:
                    rows = connection.execute(text("SELECT pid, state, wait_event_type FROM pg_stat_activity WHERE application_name = :name"), {"name": marker}).all()
                sample["lab_database_connections"] = len(rows)
                sample["lab_database_active"] = sum(row[1] == "active" for row in rows)
                sample["lab_database_waiting"] = sum(bool(row[2] and row[2] != "Client") for row in rows)
                database_processes = []
                for row in rows:
                    try:
                        database_processes.append(psutil.Process(row[0]))
                    except psutil.Error:
                        pass
                cpu, rss, _ = process_totals(database_processes)
                sample["lab_database_backend_cpu_percent_one_core_100"] = cpu
                sample["lab_database_backend_rss_bytes"] = rss
            except Exception as exc:
                sample["database_sample_error"] = type(exc).__name__
            stream.write(json.dumps(sample) + "\n")
            stream.flush()
            stopped.wait(1)


def summarize_resources(path, metrics):
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    start, end = metrics["steady_started_at"], metrics["steady_finished_at"]
    selected = [s for s in samples if start is not None and start <= s["time"] <= (end or float("inf"))]
    summaries = {}
    for key in ("host_cpu_percent", "host_available_ram_bytes", "host_free_disk_bytes", "web_cpu_percent_one_core_100", "web_rss_bytes",
                "generator_cpu_percent_one_core_100", "generator_rss_bytes", "lab_database_connections", "lab_database_active", "lab_database_waiting",
                "lab_database_backend_cpu_percent_one_core_100", "lab_database_backend_rss_bytes"):
        values = [s[key] for s in selected if key in s]
        summaries[key] = {"min": min(values), "max": max(values), "mean": sum(values) / len(values)} if values else None
    role_summaries = {}
    for role in ("proxy", "web", "other"):
        values = [sum(p["cpu_percent_one_core_100"] for p in sample.get("web_processes", []) if p["role"] == role) for sample in selected]
        role_summaries[role] = {"mean": sum(values) / len(values), "max": max(values)} if values else None
    return {"all_samples": len(samples), "steady_samples": len(selected), "steady": summaries,
        "web_cpu_by_role": role_summaries,
        "sampling_errors": sum("database_sample_error" in s for s in samples),
        "cpu_semantics": "Process CPU sum; 100% = one logical core. Host CPU is normalized across all logical cores. RSS includes the Python launcher and its child processes."}


def run(args):
    if not 1 <= args.users <= 500 or not 10 <= args.steady_seconds <= 300 or not 100 <= args.employees <= 10000:
        raise ValueError("Use 1..500 users, 10..300 steady seconds and 100..10000 employees.")
    if not 0 < args.spawn_rate <= 100 or not 30 <= args.warmup_timeout <= 600:
        raise ValueError("Invalid spawn rate or setup deadline.")
    if args.burst != "none" and (args.profile != "mixed" or args.employees <= args.users):
        raise ValueError("A burst requires mixed load and extra employees reserved from steady writes.")
    if not 1 <= args.web_workers <= 8:
        raise ValueError("Use 1..8 native web workers.")
    if not 1 <= args.web_threads <= 40 or not 1 <= args.db_pool_size <= 10:
        raise ValueError("Use 1..40 threads and 1..10 pooled DB connections per cluster web.")
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError("Choose a new evidence filename.")
    source_root = (ROOT / args.source_root).resolve()
    source_root.relative_to(ROOT)
    for required in ("app/main.py", "app/database.py", "templates", "static"):
        if not (source_root / required).exists():
            raise ValueError("The selected source root is not a complete HRMS application.")
    source_files = []
    for folder, extensions in (("app", {".py"}), ("templates", {".html"}), ("static", {".css", ".js", ".svg"})):
        for path in sorted((source_root / folder).rglob("*")):
            if path.is_file() and path.suffix in extensions:
                path.resolve().relative_to(source_root)
                if path.is_symlink():
                    raise ValueError("Source capture does not follow file symlinks.")
                source_files.append(path)
    minimum_disk_bytes = 512 * 1024 * 1024
    if psutil.disk_usage(str(ROOT)).free < minimum_disk_bytes:
        raise RuntimeError("Capacity testing requires at least 512 MiB free disk space.")
    ident = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3)
    raw = ROOT / "artifacts/evidence" / ("capacity-" + ident)
    raw.mkdir(parents=True)
    marker = "hrms-capacity-" + ident
    revision = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    captured_sources = [{"path": p.relative_to(source_root).as_posix(), "sha256_utf8_lf": hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest()} for p in source_files]
    source_hashes = [item for item in captured_sources if item["path"].startswith("app/")]
    source_archive = raw / "app-before-run.zip"
    with zipfile.ZipFile(source_archive, "x", zipfile.ZIP_DEFLATED) as archive:
        for item in captured_sources:
            archive.write(source_root / item["path"], item["path"])
    started = datetime.now(timezone.utc)
    with PostgresSandbox() as sandbox:
        username, password = "synthetic_capacity_user", secrets.token_urlsafe(32)
        with sandbox.session_factory() as db:
            branch = Branch(name="Synthetic capacity branch")
            position = Position(title="Synthetic capacity position", description="Isolated architecture laboratory")
            db.add_all([branch, position])
            db.flush()
            unit = Unit(name="Synthetic capacity unit", branch_id=branch.id)
            db.add(unit)
            db.flush()
            db.add(Admin(username=username, display_name="کاربر ساختگی آزمون ظرفیت", password_hash=hash_password(password), role="hr", is_active=True))
            employees = [Employee(employee_code=f"CAP-{i:06d}", first_name="آزمون", last_name="ساختگی",
                national_id="9900000000", phone="09000000000", email="capacity@example.invalid", hire_date=date(2025, 1, 1),
                branch_id=branch.id, unit_id=unit.id, position_id=position.id, contract_type="دائم", active=True) for i in range(args.employees)]
            db.add_all(employees)
            db.commit()
            employee_ids = [e.id for e in employees]
        ids_path = raw / "employee-ids.json"
        ids_path.write_text(json.dumps(employee_ids), encoding="utf-8")
        with sandbox.owner_engine.connect() as connection:
            max_connections = connection.scalar(text("SHOW max_connections"))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        url = make_url(sandbox.url).update_query_dict({"application_name": marker})
        environment.update({"DATABASE_URL": url.render_as_string(hide_password=False), "INSTANCE_ID": marker,
            "HRMS_LAB_INSTANCE": marker, "HRMS_LAB_USERNAME": username, "HRMS_LAB_PASSWORD": password,
            "HRMS_LAB_EMPLOYEE_IDS_PATH": str(ids_path), "HRMS_LAB_EXPECTED_USERS": str(args.users),
            "HRMS_LAB_WARMUP_TIMEOUT": str(args.warmup_timeout), "HRMS_LAB_STEADY_SECONDS": str(args.steady_seconds),
            "HRMS_LAB_PROFILE": args.profile, "HRMS_LAB_SEED": "20261108",
            "HRMS_LAB_STEADY_WRITES": args.steady_writes,
            "HRMS_LAB_BURST": args.burst,
            "HRMS_LAB_ABORT_PATH": str(raw / "abort.json"),
            "HRMS_LAB_METRICS_PATH": str(raw / "workload.json"), "HRMS_LAB_WINDOW_MARKER": str(raw / "steady.json")})
        environment["PYTHONPATH"] = str(source_root)
        server = generator = None
        stopped = threading.Event()
        sampler = None
        with (raw / "web.log").open("x", encoding="utf-8") as web_log, (raw / "locust.log").open("x", encoding="utf-8") as load_log:
            try:
                server_command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]
                server_command.extend(["--http", args.http_parser])
                if args.web_workers > 1:
                    server_command = [sys.executable, str(ROOT / "scripts/run_native_cluster.py"),
                        "--workers", str(args.web_workers), "--port", str(port),
                        "--threads", str(args.web_threads), "--pool-size", str(args.db_pool_size), "--http-parser", args.http_parser]
                server = subprocess.Popen(server_command, cwd=source_root, env=environment, stdout=web_log, stderr=web_log)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    try:
                        if httpx.get(base_url + "/health", timeout=1, trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if server.poll() is not None:
                        raise RuntimeError("The isolated server stopped.")
                    time.sleep(.2)
                else:
                    raise RuntimeError("The isolated server did not become ready.")
                command = [sys.executable, "-m", "locust", "-f", str(ROOT / "tests/performance/capacity_locustfile.py"),
                    "HrmsCapacityUser" if args.profile == "mixed" else "LoginPressureUser", "--headless", "--host", base_url,
                    "--users", str(args.users), "--spawn-rate", str(args.spawn_rate), "--run-time", str(args.warmup_timeout + args.steady_seconds + 120) + "s",
                    "--stop-timeout", "12", "--csv", str(raw / "samples"), "--csv-full-history", "--only-summary", "--exit-code-on-error", "1"]
                generator = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=load_log, stderr=load_log)
                sampler = threading.Thread(target=sample_resources, args=(server, generator, sandbox.owner_engine, marker, stopped, raw / "resources.jsonl"), daemon=True)
                sampler.start()
                last_progress = time.monotonic()
                deadline = time.monotonic() + args.warmup_timeout + args.steady_seconds + 150
                while generator.poll() is None:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Capacity runner exceeded the setup/steady/shutdown deadline.")
                    if psutil.disk_usage(str(ROOT)).free < minimum_disk_bytes and not (raw / "abort.json").exists():
                        (raw / "abort.json").write_text(json.dumps({"reason": "low_disk_space", "time": time.time(),
                            "minimum_free_bytes": minimum_disk_bytes}) + "\n", encoding="utf-8")
                        print("Lab requested a controlled stop because free disk space fell below 512 MiB.", flush=True)
                    if time.monotonic() - last_progress >= 20:
                        window = json.loads((raw / "steady.json").read_text(encoding="utf-8")) if (raw / "steady.json").exists() else None
                        print(json.dumps({"progress": "steady" if window else "ramp_and_setup", "users_requested": args.users,
                            "steady_elapsed_seconds": round(time.time() - window["started_at"], 1) if window else 0}), flush=True)
                        last_progress = time.monotonic()
                    time.sleep(.5)
            finally:
                stop(generator)
                stopped.set()
                if sampler:
                    sampler.join(timeout=8)
                stop(server)
        metrics = json.loads((raw / "workload.json").read_text(encoding="utf-8"))
        with sandbox.session_factory() as db:
            audit_writes = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "status", AuditLog.entity == "employees"))
            leave_ids = select(HrRequest.id).where(HrRequest.kind == "leave", HrRequest.description == "Synthetic mixed " + marker)
            steady_leave_rows = db.scalar(select(func.count()).select_from(leave_ids.subquery()))
            steady_leave_audits = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "create",
                AuditLog.entity == "hr_requests", AuditLog.record_id.in_(leave_ids)))
            burst = metrics.get("burst", {"mode": "none", "outcomes": []})
            checks = []
            for outcome in burst["outcomes"]:
                if burst["mode"] == "requests":
                    item = db.get(HrRequest, outcome["request_id"]) if outcome["request_id"] else None
                    audits = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity == "hr_requests",
                        AuditLog.action == "create", AuditLog.record_id == outcome["request_id"]))
                    correct = bool(item and item.employee_id == outcome["employee_id"] and item.status == "pending"
                        and item.description == "Synthetic burst " + marker and audits == 1)
                else:
                    item = db.get(Employee, outcome["employee_id"])
                    audits = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity == "employees",
                        AuditLog.action == "status", AuditLog.record_id == outcome["employee_id"]))
                    correct = bool(item and not item.active and audits == 1)
                checks.append({"employee_id": outcome["employee_id"], "acknowledged": outcome["status"] == 303, "persisted_once_with_audit": correct})
            burst["persistence_checks"] = checks
            starts = [r["started_at"] for r in burst["outcomes"]]
            burst["dispatch_spread_ms"] = round((max(starts) - min(starts)) * 1000) if starts else None
            burst["all_passed"] = bool(args.burst != "none" and len(checks) == args.users
                and len({r["employee_id"] for r in checks}) == args.users
                and all(r["acknowledged"] and r["persisted_once_with_audit"] for r in checks))
        acknowledged_writes = sum(e["count"] for e in metrics["all_window_and_setup_outcomes"] if e["name"] == "write.employee_status" and e["status"] == 303 and not e["failed"])
        acknowledged_leaves = sum(e["count"] for e in metrics["all_window_and_setup_outcomes"] if e["name"] == "write.leave" and e["status"] == 303 and not e["failed"])
        enough_load = args.profile == "mixed" and args.users == 500 and args.employees == 10000 and metrics["authenticated_users_peak"] == 500 and metrics["steady_seconds"] >= 300 and metrics["finish_reason"] == "steady_completed"
        passed_latency = bool(metrics["requests"] and metrics["p95_ms"] < 2000 and metrics["failure_fraction"] < .01)
        report = {"id": ident, "started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
            "git_parent_commit": revision, "app_sources": source_hashes, "profile": args.profile,
            "source_archive": source_archive.relative_to(ROOT).as_posix(),
            "source_root": source_root.relative_to(ROOT).as_posix(), "captured_sources": captured_sources,
            "fixture_schema_source": "Current app.database.Base.metadata; selected source has no migration applied by this runner",
            "fixture_table_count": len(Base.metadata.tables),
            "source_runtime": "Uvicorn without reload; code captured before process startup",
            "minimum_free_disk_bytes": minimum_disk_bytes,
            "topology": "One native FastAPI/Uvicorn process and local PostgreSQL; separate lab port and schema" if args.web_workers == 1
                else f"{args.web_workers} native web processes, one async affinity proxy, local PostgreSQL; separate lab port and schema",
            "web_workers": args.web_workers, "threads_per_web": int(environment.get("HRMS_THREADS", "40")) if args.web_workers == 1 else args.web_threads,
            "max_connections_per_web": int(environment.get("HRMS_DB_POOL_SIZE", "5")) + int(environment.get("HRMS_DB_MAX_OVERFLOW", "10")) if args.web_workers == 1 else args.db_pool_size,
            "http_parser_requested": args.http_parser,
            "runtime_packages": {name: importlib.metadata.version(name) for name in ("aiohttp", "httpx", "uvicorn", "psycopg")},
            "initial_employee_count": args.employees, "users_requested": args.users, "spawn_rate": args.spawn_rate,
            "steady_seconds_requested": args.steady_seconds, "warmup_timeout_seconds": args.warmup_timeout,
            "steady_writes": args.steady_writes,
            "python_version": platform.python_version(), "locust_version": importlib.metadata.version("locust"),
            "os": platform.platform(), "logical_cpus": os.cpu_count(), "host_ram_bytes": psutil.virtual_memory().total,
            "database_max_connections": int(max_connections), "metrics": metrics,
            "burst": burst,
            "steady_leave_observation": {"acknowledged": acknowledged_leaves, "persisted_rows": steady_leave_rows, "create_audits": steady_leave_audits},
            "resources": summarize_resources(raw / "resources.jsonl", metrics), "generator_exit_code": generator.returncode,
            "audit_observation": {"acknowledged_status_writes_all_windows": acknowledged_writes, "persisted_status_audits": audit_writes,
                "all_acknowledgements_have_at_least_an_audit": audit_writes >= acknowledged_writes,
                "limitation": "Aggregate count only; timed-out requests may also commit. This is not per-operation exactly-once verification."},
            "nfr_500_users_verified": bool(enough_load and passed_latency),
            "limitations": ["Generator and services share one physical host", "Only the specified latency/error NFR can be assessed; this does not certify HA, authorization completeness or all write invariants", "Local native database has no container resource isolation; compare like-for-like profiles and steady windows"],
            "raw_evidence_directory": raw.relative_to(ROOT).as_posix()}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"profile": args.profile, "users": args.users, "actual_authenticated_peak": metrics["authenticated_users_peak"],
            "steady_seconds": round(metrics["steady_seconds"], 1), "requests": metrics["requests"], "failures": metrics["failures"],
            "p95_ms": metrics["p95_ms"], "rps": round(metrics["rps"], 2) if metrics["rps"] else None,
            "finish_reason": metrics["finish_reason"], "nfr_500_users_verified": report["nfr_500_users_verified"], "report": output.relative_to(ROOT).as_posix()}, ensure_ascii=True), flush=True)
        return 0 if metrics["requests"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--spawn-rate", type=float, default=20)
    parser.add_argument("--steady-seconds", type=int, default=30)
    parser.add_argument("--warmup-timeout", type=int, default=120)
    parser.add_argument("--employees", type=int, default=10000)
    parser.add_argument("--profile", choices=("mixed", "login"), default="mixed")
    parser.add_argument("--burst", choices=("none", "status", "requests"), default="none")
    parser.add_argument("--steady-writes", choices=("status", "leave"), default="status")
    parser.add_argument("--web-workers", type=int, default=1)
    parser.add_argument("--web-threads", type=int, default=8)
    parser.add_argument("--db-pool-size", type=int, default=10)
    parser.add_argument("--http-parser", choices=("auto", "h11", "httptools"), default="auto")
    parser.add_argument("--source-root", default=".", help="Application directory inside the workspace, including preserved baseline sources")
    parser.add_argument("--output", required=True)
    sys.exit(run(parser.parse_args()))
