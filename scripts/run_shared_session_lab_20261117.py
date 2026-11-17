"""Reproduce worker transfer/restart loss, then test shared-session routing in an owned Docker lab."""
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent


def enable_shared_sessions(config, source, name):
    shared = yaml.safe_load((source / "deployments/compose.shared.yaml").read_text(encoding="utf-8"))
    services = config["services"]
    init = services["init-secrets"]
    shared_init = shared["services"]["init-secrets"]
    init["volumes"].extend(shared_init["volumes"])
    init["command"] = shared_init["command"]
    services["redis"] = shared["services"]["redis"]
    config["secrets"]["redis_password"] = shared["secrets"]["redis_password"]
    web = services["web"]
    web["environment"].update(HRMS_SESSION_BACKEND="redis", HRMS_REDIS_HOST="redis",
        HRMS_REDIS_PASSWORD_FILE="/run/secrets/redis_password", HRMS_REDIS_NAMESPACE="lab:" + name)
    web["secrets"].append("redis_password")
    web["depends_on"]["redis"] = {"condition": "service_healthy"}


def run(options):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,45}", options.name):
        raise ValueError("Use a unique lowercase lab name.")
    raw = ROOT / "artifacts" / options.name
    raw.mkdir(exist_ok=False)
    source = raw / "source"
    source.mkdir()
    source_root = ROOT
    if options.source:
        source_root = (ROOT / options.source).resolve()
        source_root.relative_to(ROOT / "artifacts")
    for folder in ("app", "templates", "static", "deployments"):
        shutil.copytree(source_root / folder, source / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (source / "scripts").mkdir()
    filenames = ["init_docker_secrets.py", "container_capacity_fixture_20261117.py"]
    if options.shared:
        filenames.append("init_shared_secrets_20261117.py")
    for filename in filenames:
        shutil.copy2(source_root / "scripts" / filename, source / "scripts" / filename)
    for filename in ("requirements-lock.txt", ".dockerignore"):
        shutil.copy2(source_root / filename, source / filename)
    evidence = ROOT / "docs/08-testing/evidence" / (options.name + ".json")
    if evidence.exists():
        raise FileExistsError("Choose a new evidence name.")
    ports = []
    for _ in range(2):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            ports.append(probe.getsockname()[1])
    marker = "hrms-capacity-" + options.name
    environment = os.environ.copy()
    environment["COMPOSE_PROJECT_NAME"] = marker
    config = yaml.safe_load((source / "deployments/compose.yaml").read_text(encoding="utf-8"))
    web = config["services"]["web"]
    web.update(image="hrms-web:" + options.name, command=["python", "/lab/bootstrap.py"],
        volumes=["../scripts/container_capacity_fixture_20261117.py:/lab/bootstrap.py:ro"],
        ports=[f"127.0.0.1:{ports[0]}:8000"])
    web["environment"].update(INSTANCE_ID=marker, HRMS_CAPACITY_SCHEMA="hrms_test_" + uuid.uuid4().hex,
        HRMS_CAPACITY_USERS="1", HRMS_CAPACITY_EMPLOYEES="100")
    if options.shared:
        enable_shared_sessions(config, source, options.name)
    secondary = copy.deepcopy(web)
    secondary.pop("build")
    secondary.update(command=["python", "/lab/bootstrap.py", "--worker"],
        ports=[f"127.0.0.1:{ports[1]}:8000"], depends_on={"web": {"condition": "service_healthy"}})
    config["services"]["web2"] = secondary
    config_path = source / "deployments/session-lab.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    compose = ["docker", "compose", "-f", str(config_path)]
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "shared": options.shared,
        "source_files": [{"path": p.relative_to(source).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(source.rglob("*")) if p.is_file()],
        "synthetic_only": True, "human_review": "pending", "physical_servers_verified": False,
        "checks": {}, "raw_directory": raw.relative_to(ROOT).as_posix()}
    with (raw / "operations.log").open("x", encoding="utf-8") as log:
        def command(arguments):
            result = subprocess.run(arguments, cwd=source, env=environment, stdout=log, stderr=log)
            if result.returncode:
                raise RuntimeError("Owned session lab operation failed; see private log.")
        try:
            command(compose + ["--profile", "tools", "run", "--rm", "--no-deps", "init-secrets"])
            command(compose + ["up", "--build", "-d", "--wait", "--wait-timeout", "180"])
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=10,
                    limits=httpx.Limits(max_keepalive_connections=0)) as client:
                urls = [f"http://127.0.0.1:{port}" for port in ports]
                page = client.get(urls[0] + "/login")
                token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
                password = (source / ".runtime/docker-hrms-secrets/admin_password").read_text().strip()
                old_cookie = client.cookies.get("hrms_session")
                report["checks"]["initial_login"] = client.post(urls[0] + "/login", data={
                    "username": "capacity-0000", "password": password, "csrf_token": token}).status_code == 303
                del password
                report["checks"]["worker1_dashboard"] = client.get(urls[0] + "/").status_code == 200
                transfer = client.get(urls[1] + "/")
                report["transfer_status"] = transfer.status_code
                report["checks"]["expected_transfer_behavior"] = transfer.status_code == (200 if options.shared else 303)
                command(compose + ["restart", "web"])
                for _ in range(100):
                    try:
                        if client.get(urls[0] + "/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.2)
                restarted = client.get(urls[0] + "/")
                report["restart_status"] = restarted.status_code
                report["checks"]["expected_restart_behavior"] = restarted.status_code == (200 if options.shared else 303)
                if options.shared:
                    csrf = re.search(r'name="csrf_token" value="([^"]+)"', transfer.text).group(1)
                    report["checks"]["cross_worker_logout"] = client.post(urls[1] + "/logout", data={"csrf_token": csrf}).status_code == 303
                    report["checks"]["logout_revoked_on_worker1"] = client.get(urls[0] + "/").status_code == 303
                    client.cookies.set("hrms_session", old_cookie)
                    report["checks"]["old_anonymous_cookie_not_restored"] = client.get(urls[1] + "/").status_code == 303
            report["all_passed"] = all(report["checks"].values())
        except Exception as exc:
            report.update(all_passed=False, error_type=type(exc).__name__)
            raise
        finally:
            command(compose + ["logs", "--no-color", "--tail", "50"])
            command(compose + ["down", "--volumes"])
            report["resources_removed"] = True
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            with evidence.open("x", encoding="utf-8") as output:
                output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"all_passed": report["all_passed"], "checks": report["checks"], "evidence": evidence.relative_to(ROOT).as_posix()}))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--shared", action="store_true")
    parser.add_argument("--source", help="Prior owned source snapshot under artifacts, for the preserved baseline only")
    raise SystemExit(run(parser.parse_args()))
