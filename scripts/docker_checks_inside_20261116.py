"""Run synthetic PostgreSQL checks in a disposable Docker test container."""
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/srv/hrms")
OUTPUT = ROOT / "artifacts/docker-checks"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))

if (ROOT / ".env").exists():
    raise RuntimeError("Docker verification must never mount the native .env.")

with (OUTPUT / "verification.log").open("x", encoding="utf-8") as log:
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "coverage>=7,<8", "PyYAML>=6,<7"], stdout=log, stderr=log, check=True)
    import entrypoint
    entrypoint.configure()
    commands = [
        [sys.executable, "-m", "coverage", "run", "--data-file", str(OUTPUT / "coverage-data"),
            "--source", "app/request_workflow", "scripts/run_core_checks.py", "--phase", "after",
            "--pattern", "test_*.py", "--output", "artifacts/docker-checks/core.json"],
        [sys.executable, "-m", "coverage", "report", "--data-file", str(OUTPUT / "coverage-data"), "--fail-under", "80"],
        [sys.executable, "-m", "coverage", "json", "--data-file", str(OUTPUT / "coverage-data"), "-o", str(OUTPUT / "coverage.json")],
        [sys.executable, "-m", "pip", "check"],
    ]
    if os.getenv("HRMS_CHECK_SKIP_REGRESSION") != "1":
        commands.append([sys.executable, "scripts/run_isolated_smoke.py", "--output", "artifacts/docker-checks/regression.json"])
    outcomes = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log)
        outcomes.append({"command": command[1:], "exit_code": result.returncode})
    (OUTPUT / "verification.json").write_text(json.dumps({
        "isolation": "Disposable verification container and unique synthetic PostgreSQL schemas; no native .env mounted",
        "all_passed": all(item["exit_code"] == 0 for item in outcomes), "checks": outcomes,
        "package_versions": {name: importlib.metadata.version(name) for name in ("coverage", "PyYAML", "psycopg", "fastapi")},
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": all(item["exit_code"] == 0 for item in outcomes), "checks": len(outcomes)}))
    sys.exit(0 if all(item["exit_code"] == 0 for item in outcomes) else 1)
