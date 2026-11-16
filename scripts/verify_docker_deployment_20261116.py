"""Verify the newly seeded Docker deployment; publish no credentials or HR rows."""
import argparse
import hashlib
import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", str(ROOT / "deployments/compose.yaml")]


def command(arguments):
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Docker operation failed; exit code " + str(result.returncode))
    return result.stdout.strip()


def marker(mode, schema):
    if not re.fullmatch(r"hrms_docker_check_[0-9a-f]{32}", schema):
        raise ValueError("Only this verifier's synthetic schema is allowed.")
    code = '''import json,sys
try:
 import entrypoint
 entrypoint.configure()
 from sqlalchemy import text
 from app.database import engine
 mode,schema=sys.argv[1:]
 with engine.begin() as connection:
  if mode == "create":
   connection.execute(text('CREATE SCHEMA "'+schema+'"'))
   connection.execute(text('CREATE TABLE "'+schema+'".sentinel (value integer NOT NULL)'))
   connection.execute(text('INSERT INTO "'+schema+'".sentinel VALUES (17)'))
   ok=True
  elif mode == "check":
   ok=connection.scalar(text('SELECT value FROM "'+schema+'".sentinel')) == 17
  else:
   connection.execute(text('DROP SCHEMA "'+schema+'" CASCADE'))
   ok=True
 print(json.dumps({"ok":ok}))
except Exception as exc:
 print(json.dumps({"ok":False,"error_type":type(exc).__name__}))
 sys.exit(1)
'''
    result = subprocess.run(COMPOSE + ["exec", "-T", "web", "python", "-", mode, schema], input=code,
        capture_output=True, text=True, cwd=ROOT)
    if result.returncode:
        raise RuntimeError("Synthetic persistence check failed")
    return json.loads(result.stdout)["ok"]


def verify(output):
    output = (ROOT / output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError("Choose a new deployment evidence filename.")
    checks = {}
    with httpx.Client(base_url="http://127.0.0.1:8001", trust_env=False, follow_redirects=False, timeout=10) as client:
        checks["health_database_connection"] = client.get("/health").json().get("status") == "ok"
        checks["docker_instance"] = client.get("/instance").json().get("instance") == "hrms-docker-1"
        page = client.get("/login")
        checks["login_form"] = page.status_code == 200 and 'id="username"' in page.text
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        old_cookie = client.cookies.get("hrms_session")
        checks["wrong_password_401"] = client.post("/login", data={"username": "hradmin", "password": "Synthetic-wrong-password", "csrf_token": token}).status_code == 401
        password = (ROOT / ".runtime/docker-hrms-secrets/admin_password").read_text(encoding="utf-8").strip()
        response = client.post("/login", data={"username": "hradmin", "password": password, "csrf_token": token})
        del password
        checks["sample_login_303"] = response.status_code == 303
        checks["rotated_httponly_cookie"] = client.cookies.get("hrms_session") != old_cookie and "httponly" in response.headers.get("set-cookie", "").lower()
        dashboard = client.get("/")
        checks["authenticated_dashboard"] = dashboard.status_code == 200
        checks["missing_csrf_403"] = client.post("/logout", data={}).status_code == 403
        token = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.text).group(1)
        checks["logout_303"] = client.post("/logout", data={"csrf_token": token}).status_code == 303
        checks["logout_invalidates_session"] = client.get("/").status_code == 303
    safe_image = command(COMPOSE + ["exec", "-T", "web", "python", "-c",
        "import json,os,pathlib; print(json.dumps({'nonroot':os.getuid()==10001,'native_env_absent':not pathlib.Path('/srv/hrms/.env').exists(),'native_runtime_absent':not pathlib.Path('/srv/hrms/.runtime').exists(),'single_uvicorn_pid1':b'app.main:app' in pathlib.Path('/proc/1/cmdline').read_bytes()}))"])
    checks.update(json.loads(safe_image))
    schema = "hrms_docker_check_" + uuid.uuid4().hex
    created = False
    try:
        checks["synthetic_marker_created"] = marker("create", schema)
        created = True
        command(COMPOSE + ["stop"])
        command(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "150"])
        checks["volume_marker_survived_stop_start"] = marker("check", schema)
        checks["synthetic_marker_removed"] = marker("drop", schema)
        created = False
    finally:
        if created:
            marker("drop", schema)
    with httpx.Client(trust_env=False, timeout=10) as client:
        checks["docker_healthy_after_restart"] = client.get("http://127.0.0.1:8001/health").json().get("status") == "ok"
        checks["native_site_preserved"] = client.get("http://127.0.0.1:8000/instance").json().get("instance") == "hrms-local-1"
    container_json = command(COMPOSE + ["ps", "--format", "json"])
    try:
        containers = json.loads(container_json)
    except json.JSONDecodeError:
        containers = [json.loads(line) for line in container_json.splitlines() if line.strip()]
    if isinstance(containers, dict):
        containers = [containers]
    payload = {"recorded_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "all_passed": all(checks.values()), "isolation": "Fresh Docker sample database and uniquely named disposable synthetic persistence schema; native HR untouched",
        "containers": [{k: row.get(k) for k in ("Name", "Service", "Image", "State", "Health")} for row in containers],
        "image_id": command(["docker", "image", "inspect", "--format", "{{.Id}}", "hrms-web:docker-baseline"]),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
            ("deployments/compose.yaml", "deployments/app/Dockerfile", "deployments/app/entrypoint.py", ".dockerignore", "requirements-lock.txt")},
        "human_review": "pending", "capacity_500_verified": False,
        "limitations": ["Single web, process-local sessions; restart logs users out", "Docker startup verification is not 500-user or HA acceptance"],
    }
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"all_passed": payload["all_passed"], "checks": len(checks), "containers": payload["containers"]}))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.output))
