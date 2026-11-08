"""Run Locust against a disposable local PostgreSQL schema and a separate web process."""
import argparse
import importlib.metadata
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.database import Admin, Branch, Employee, Position, Unit
from app.security import hash_password
from tests.support import PostgresSandbox


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_lab(args):
    if not 1 <= args.users <= 500 or not 10 <= args.seconds <= 300 or not 10 <= args.employees <= 10000 or not 0 < args.spawn_rate <= 100:
        raise ValueError("Use 1..500 users, 10..300 seconds, 10..10000 synthetic employees and a spawn rate in (0, 100].")
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError("Choose a new result path; measured evidence is never overwritten.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3)
    raw = ROOT / "artifacts" / "evidence" / ("load-" + run_id)
    raw.mkdir(parents=True)
    with PostgresSandbox() as sandbox:
        password, username = secrets.token_urlsafe(32), "synthetic_load_user"
        with sandbox.session_factory() as db:
            branch = Branch(name="Synthetic load branch")
            position = Position(title="Synthetic load position", description="Isolated load test only")
            db.add_all([branch, position])
            db.flush()
            unit = Unit(name="Synthetic load unit", branch_id=branch.id)
            db.add(unit)
            db.flush()
            db.add(Admin(username=username, display_name="کاربر ساختگی آزمایش بار", password_hash=hash_password(password), role="hr", is_active=True))
            employees = [Employee(employee_code=f"LOAD-{i:06d}", first_name="آزمون", last_name="ساختگی",
                national_id="9900000000", phone="09000000000", email="load@example.invalid", hire_date=date(2025, 1, 1),
                branch_id=branch.id, unit_id=unit.id, position_id=position.id, contract_type="دائم", active=True) for i in range(args.employees)]
            db.add_all(employees)
            db.commit()
            employee_ids = [item.id for item in employees]
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        marker = "hrms-load-lab-" + run_id
        env.update({"DATABASE_URL": sandbox.url, "INSTANCE_ID": marker, "HRMS_LAB_INSTANCE": marker,
            "HRMS_LAB_USERNAME": username, "HRMS_LAB_PASSWORD": password,
            "HRMS_LAB_EMPLOYEE_IDS": json.dumps(employee_ids), "HRMS_LAB_METRICS_PATH": str(raw / "workload.json")})
        server = None
        started = datetime.now(timezone.utc)
        with (raw / "web.log").open("w", encoding="utf-8") as web_log, (raw / "locust.log").open("w", encoding="utf-8") as load_log:
            try:
                server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=web_log, stderr=web_log)
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    try:
                        if httpx.get(base_url + "/health", timeout=1, trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if server.poll() is not None:
                        raise RuntimeError("Isolated server exited; inspect the lab web log.")
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Isolated server was not ready.")
                command = [sys.executable, "-m", "locust", "-f", str(ROOT / "tests/performance/locustfile.py"),
                    "--headless", "--host", base_url, "--users", str(args.users), "--spawn-rate", str(args.spawn_rate),
                    "--run-time", str(args.seconds) + "s", "--stop-timeout", "5", "--csv", str(raw / "samples"),
                    "--csv-full-history", "--only-summary", "--exit-code-on-error", "1"]
                completed = subprocess.run(command, cwd=ROOT, env=env, stdout=load_log, stderr=load_log, timeout=args.seconds + 60)
            finally:
                stop(server)
        metrics = json.loads((raw / "workload.json").read_text(encoding="utf-8"))
        report = {"id": run_id, "started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
            "topology": "One native FastAPI process and local PostgreSQL; no container resource isolation",
            "isolation": "Disposable PostgreSQL schema and synthetic accounts/employees; separate web port",
            "users_requested": args.users, "spawn_rate_per_second": args.spawn_rate, "duration_requested_seconds": args.seconds,
            "initial_employee_count": args.employees, "locust_version": importlib.metadata.version("locust"),
            "python_version": platform.python_version(), "os": platform.platform(), "logical_cpus": os.cpu_count(),
            "metrics": metrics, "locust_exit_code": completed.returncode,
            "nfr_500_users_verified": False,
            "limitations": ["Generator and application share the same host", "Short local experiment; not a production capacity or uptime measurement", "Task weights are 80/20; the observed HTTP ratio is reported separately", "NFR-01 requires a separate acceptance run with 500 authenticated concurrent users and five minutes of steady workload; this lab does not certify that target"],
            "raw_evidence_directory": raw.relative_to(ROOT).as_posix()}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"users": args.users, "requests": metrics["requests"], "failures": metrics["failures"],
            "p95_ms": metrics["p95_ms"], "rps": round(metrics["rps_over_wall_window"], 2), "report": output.relative_to(ROOT).as_posix()}, ensure_ascii=False))
        return completed.returncode if metrics["requests"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--spawn-rate", type=float, default=5)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--employees", type=int, default=100)
    parser.add_argument("--output", required=True)
    sys.exit(run_lab(parser.parse_args()))
