"""Capture current source and test 500 simultaneous logins in a disposable Docker/schema lab."""
import argparse
import copy
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psutil
import yaml

from run_shared_session_lab_20261117 import enable_shared_sessions

ROOT = Path(__file__).resolve().parent.parent


def run(args):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,45}", args.name) or not 1 <= args.users <= 500:
        raise ValueError("Use a unique lowercase name and 1..500 synthetic users")
    raw = ROOT / "artifacts" / args.name
    raw.mkdir(parents=True, exist_ok=False)
    evidence = ROOT / "docs/08-testing/evidence" / (args.name + ".json")
    if evidence.exists():
        raise FileExistsError("Use a new evidence name")
    source = raw / "source"
    source.mkdir()
    shutil.copy2(ROOT / "tests/performance/login_storm_20261117.py", raw / "login_storm.py")
    for folder in ("app", "templates", "static", "deployments"):
        shutil.copytree(ROOT / folder, source / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (source / "scripts").mkdir()
    scripts = ["init_docker_secrets.py", "container_capacity_fixture_20261117.py"]
    if args.shared:
        scripts.append("init_shared_secrets_20261117.py")
    for name in scripts:
        shutil.copy2(ROOT / "scripts" / name, source / "scripts" / name)
    for name in ("requirements-lock.txt", ".dockerignore"):
        shutil.copy2(ROOT / name, source / name)
    captured = [{"path": p.relative_to(source).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(source.rglob("*")) if p.is_file()]
    marker = "hrms-capacity-" + args.name
    environment = os.environ.copy()
    environment["COMPOSE_PROJECT_NAME"] = marker
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment["HRMS_HTTP_PORT"] = str(port)
    override = source / "deployments/lab.json"
    config = yaml.safe_load((source / "deployments/compose.yaml").read_text(encoding="utf-8"))
    web = config["services"]["web"]
    web.update(image="hrms-web:" + args.name, command=["python", "/lab/bootstrap.py"],
        volumes=["../scripts/container_capacity_fixture_20261117.py:/lab/bootstrap.py:ro"])
    web["environment"].update(INSTANCE_ID=marker, HRMS_CAPACITY_SCHEMA="hrms_test_" + uuid.uuid4().hex,
        HRMS_CAPACITY_USERS=str(args.users), HRMS_CAPACITY_EMPLOYEES="10000",
        HRMS_PASSWORD_WORKERS=str(args.password_workers))
    if args.shared:
        enable_shared_sessions(config, source, args.name)
    if args.web_workers == 4:
        ports = web.pop("ports")
        web["environment"].update(HRMS_THREADS="8", HRMS_DB_POOL_SIZE="5", HRMS_DB_MAX_OVERFLOW="5")
        for index in range(2, 5):
            additional = copy.deepcopy(web)
            additional.pop("build")
            additional["command"] = ["python", "/lab/bootstrap.py", "--worker"]
            additional["depends_on"] = {"web": {"condition": "service_healthy"}}
            config["services"][f"web{index}"] = additional
        config["services"]["proxy"] = {"image": web["image"], "command": ["python", "-m", "uvicorn", "app.native_proxy:app", "--host", "0.0.0.0", "--port", "8000"],
            "environment": {"HRMS_PROXY_MODE": "shared" if args.shared else "compose", "HRMS_PROXY_TIMEOUT": "180", "INSTANCE_ID": marker,
                "HRMS_NATIVE_BACKENDS": json.dumps(["http://web:8000", "http://web2:8000", "http://web3:8000", "http://web4:8000"])},
            "networks": ["backend"], "ports": ports, "healthcheck": copy.deepcopy(web["healthcheck"]),
            "depends_on": {name: {"condition": "service_healthy"} for name in ("web", "web2", "web3", "web4")}}
    override.write_text(json.dumps(config, indent=2), encoding="utf-8")
    compose = ["docker", "compose", "-f", str(override)]
    started = datetime.now(timezone.utc)
    report = {"started_at": started.isoformat(), "source_parent_commit": subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "captured_source_files": captured,
        "topology": f"{args.web_workers} Docker Uvicorn processes, PostgreSQL and {'Redis shared sessions' if args.shared else 'memory sessions'}; fresh disposable schema, synthetic accounts only",
        "shared_sessions": args.shared, "password_workers_per_web": args.password_workers,
        "users_requested": args.users, "employees": 10000, "human_review": "pending", "nfr_500_mixed_workload_verified": False,
        "load_generator_source_sha256": hashlib.sha256((raw / "login_storm.py").read_bytes()).hexdigest(),
        "limitations": ["Generator and Docker share this physical host", "Simultaneous login workload only; no 300-second mixed-load/HA certification"],
        "raw_evidence_directory": raw.relative_to(ROOT).as_posix()}
    with (raw / "operations.log").open("x", encoding="utf-8") as log:
        def command(arguments, capture=False):
            result = subprocess.run(arguments, cwd=source, env=environment, text=True,
                stdout=subprocess.PIPE if capture else log, stderr=log)
            if result.returncode:
                raise RuntimeError("Owned lab operation failed; see raw log")
            return result.stdout

        async def measure():
            module_path = raw / "login_storm.py"
            spec = importlib.util.spec_from_file_location("login_storm", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            password = (source / ".runtime/docker-hrms-secrets/admin_password").read_text().strip()
            stopped = asyncio.Event()
            resources = []
            process = psutil.Process()
            process.cpu_percent()
            async def sample():
                while not stopped.is_set():
                    resources.append({"time": time.time(), "host_cpu_percent": psutil.cpu_percent(),
                        "host_available_ram_bytes": psutil.virtual_memory().available,
                        "generator_cpu_one_core_100": process.cpu_percent(), "generator_rss": process.memory_info().rss})
                    await asyncio.sleep(1)
            sampler = asyncio.create_task(sample())
            try:
                result = await module.measure(f"http://127.0.0.1:{port}", args.users, password, marker)
                (raw / "workload.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                report["metrics"] = {key: value for key, value in result.items() if not key.startswith("raw_")}
            finally:
                del password
                stopped.set()
                await sampler
                (raw / "resources.json").write_text(json.dumps(resources, indent=2), encoding="utf-8")
                report["resources"] = {"samples": len(resources), "peak_host_cpu_percent": max((r["host_cpu_percent"] for r in resources), default=0),
                    "minimum_available_ram_bytes": min((r["host_available_ram_bytes"] for r in resources), default=0),
                    "peak_generator_cpu_one_core_100": max((r["generator_cpu_one_core_100"] for r in resources), default=0)}
        try:
            command(compose + ["--profile", "tools", "run", "--rm", "--no-deps", "init-secrets"])
            command(compose + ["build", "web"])
            command(compose + ["up", "-d", "--wait", "--wait-timeout", "180"])
            print(json.dumps({"progress": "500_forms_then_simultaneous_login" if args.users == 500 else "login_burst", "users": args.users}), flush=True)
            asyncio.run(measure())
            report["database_checks"] = json.loads(command(compose + ["exec", "-T", "web", "python", "/lab/bootstrap.py", "--inspect"], capture=True))
            container = marker + "-web-1"
            report["container_state"] = json.loads(command(["docker", "inspect", container, "--format", "{{json .State}}"], capture=True))
            report["restart_count"] = int(command(["docker", "inspect", container, "--format", "{{.RestartCount}}"], capture=True))
            extra_services = [f"web{i}" for i in range(2, args.web_workers + 1)]
            if args.web_workers > 1:
                extra_services.append("proxy")
            report["secondary_restart_counts"] = {service: int(command(["docker", "inspect",
                f"{marker}-{service}-1", "--format", "{{.RestartCount}}"], capture=True))
                for service in extra_services}
            metrics = report["metrics"]
            report["all_passed"] = bool(metrics["login"]["failures"] == 0 and metrics["probes"]["failures"] == 0
                and metrics["unique_authenticated_cookies"] == args.users
                and metrics["session_checks"]["failures"] == 0 and report["database_checks"]["each_account_one_login_audit"]
                and report["restart_count"] == 0 and not any(report["secondary_restart_counts"].values()))
        except Exception as exc:
            report.update(all_passed=False, failure_type=type(exc).__name__)
            raise
        finally:
            command(compose + ["logs", "--no-color", "--tail", "100"])
            command(compose + ["down", "--volumes"])
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            report["test_resources_removed"] = True
            with evidence.open("x", encoding="utf-8") as output:
                output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"all_passed": report["all_passed"], "metrics": report.get("metrics"), "evidence": evidence.relative_to(ROOT).as_posix()}), flush=True)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--users", type=int, default=500)
    parser.add_argument("--web-workers", type=int, choices=(1, 4), default=1)
    parser.add_argument("--password-workers", type=int, choices=(1, 2), default=1)
    parser.add_argument("--shared", action="store_true")
    raise SystemExit(run(parser.parse_args()))
