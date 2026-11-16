"""Verify a clean downloadable source copy in a uniquely named disposable Compose project."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_publication_20261117 import ROOT, candidates


def verify(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,45}", name):
        raise ValueError("Choose a unique lowercase verification name.")
    raw = ROOT / "artifacts" / name
    raw.mkdir(parents=True, exist_ok=False)
    source = raw / "downloaded project"
    source.mkdir()
    for name_in_repo in candidates():
        if set(Path(name_in_repo).parts) & {".runtime", ".venv", "artifacts", "node_modules"}:
            raise RuntimeError("Private directory in candidate source")
        if Path(name_in_repo).name.startswith(".env") and Path(name_in_repo).name != ".env.example":
            raise RuntimeError("Private environment in candidate source")
        target = source / name_in_repo
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name_in_repo, target)
    environment = os.environ.copy()
    environment["COMPOSE_PROJECT_NAME"] = "hrms-" + name
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        port = port_probe.getsockname()[1]
    environment["HRMS_HTTP_PORT"] = str(port)
    compose = ["docker", "compose", "-f", str(source / "deployments/compose.yaml")]
    checks = {"clean_copy_has_no_private_environment": not (source / ".env").exists(),
              "clean_copy_has_no_host_python": not (source / ".venv").exists(),
              "clean_copy_has_no_runtime": not (source / ".runtime").exists()}
    started = datetime.now(timezone.utc)
    with (raw / "verification.log").open("x", encoding="utf-8") as log:
        def run(command):
            result = subprocess.run(command, cwd=source, env=environment, stdout=log, stderr=log)
            if result.returncode:
                raise RuntimeError("Verification operation failed; see private raw log")

        def secret_hashes():
            folder = source / ".runtime/docker-hrms-secrets"
            return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}

        try:
            launcher = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(source / "scripts/start-docker.ps1")]
            run(launcher)
            before = secret_hashes()
            checks["fresh_secret_files"] = set(before) == {"db_password", "admin_password"} and all(
                len((source / ".runtime/docker-hrms-secrets" / key).read_text().strip()) >= 12 for key in before)
            run(launcher)
            checks["repeated_start_preserves_secrets"] = before == secret_hashes()
            run(["docker", "run", "--rm", "--network", "none", "--volume",
                 f"{(source / 'scripts/start-docker.sh').as_posix()}:/check.sh:ro",
                 "python:3.12-slim-bookworm", "bash", "-n", "/check.sh"])
            checks["bash_launcher_syntax"] = True
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, follow_redirects=False, timeout=10) as client:
                checks["database_health"] = client.get("/health").json().get("status") == "ok"
                page = client.get("/login")
                checks["login_form"] = page.status_code == 200 and 'id="username"' in page.text
                token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
                checks["wrong_password_401"] = client.post("/login", data={"username": "hradmin", "password": "Wrong-synthetic-password", "csrf_token": token}).status_code == 401
                password = (source / ".runtime/docker-hrms-secrets/admin_password").read_text().strip()
                checks["fresh_admin_login_303"] = client.post("/login", data={"username": "hradmin", "password": password, "csrf_token": token}).status_code == 303
                del password
                checks["dashboard_after_login"] = client.get("/").status_code == 200
                checks["csrf_required_403"] = client.post("/logout", data={}).status_code == 403
            spec = importlib.util.spec_from_file_location("download_marker", source / "scripts/verify_docker_deployment_20261116.py")
            marker_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(marker_module)
            # The marker helper owns a strictly validated synthetic schema and reads secrets only inside web.
            previous_project = os.environ.get("COMPOSE_PROJECT_NAME")
            os.environ["COMPOSE_PROJECT_NAME"] = environment["COMPOSE_PROJECT_NAME"]
            import uuid
            schema = "hrms_docker_check_" + uuid.uuid4().hex
            marker_created = False
            try:
                checks["synthetic_marker_created"] = marker_module.marker("create", schema)
                marker_created = True
                run(compose + ["stop"])
                run(compose + ["up", "-d", "--wait", "--wait-timeout", "180"])
                checks["volume_persists_after_restart"] = marker_module.marker("check", schema)
            finally:
                if marker_created:
                    checks["synthetic_marker_removed"] = marker_module.marker("drop", schema)
                if previous_project is None:
                    os.environ.pop("COMPOSE_PROJECT_NAME", None)
                else:
                    os.environ["COMPOSE_PROJECT_NAME"] = previous_project
            (source / "artifacts").mkdir(exist_ok=True)
            run([sys.executable, str(source / "scripts/run_docker_checks_20261116.py"), "--name", name])
            for path in (source / "docs/08-testing/evidence").glob("*" + name + ".json"):
                destination = ROOT / "docs/08-testing/evidence" / path.name
                with destination.open("x", encoding="utf-8") as output:
                    output.write(path.read_text(encoding="utf-8"))
            core = json.loads((ROOT / "docs/08-testing/evidence" / f"core-docker-{name}.json").read_text())
            checks["core_postgresql_passed"] = core["all_passed"]
            checks["core_tests_run"] = core["tests_run"] > 0
        finally:
            # Only this verifier's new project and synthetic volume are removed; native/existing projects are untouched.
            run(compose + ["down"])
            run(["docker", "volume", "rm", environment["COMPOSE_PROJECT_NAME"] + "_postgres_data"])
    report = {"started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
              "all_passed": all(checks.values()), "checks": checks,
              "isolation": "Clean source copy; unique disposable Compose project/volume and free loopback port; synthetic seed and schemas only",
              "human_review": "pending", "fresh_visual_test": False, "capacity_500_verified": False,
              "platform_verified": "Windows PowerShell launcher; Bash syntax locally; Linux execution covered by GitHub CI"}
    evidence = ROOT / "docs/08-testing/evidence" / (name + ".json")
    with evidence.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"all_passed": report["all_passed"], "checks": len(checks), "evidence": evidence.relative_to(ROOT).as_posix()}))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    raise SystemExit(verify(parser.parse_args().name))
