"""Run the existing eight-module regression suite without touching the live HR schema."""
import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.support import PostgresSandbox


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        parser.error("Choose a new evidence path.")
    raw = ROOT / "artifacts/evidence" / ("full-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3))
    raw.mkdir(parents=True)
    with PostgresSandbox() as sandbox:
        env = os.environ.copy()
        env.update({"DATABASE_URL": sandbox.url, "ADMIN_USERNAME": "synthetic_smoke_admin",
            "ADMIN_PASSWORD": secrets.token_urlsafe(32), "HRMS_ARTIFACT_DIR": str(raw)})
        with (raw / "runner.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-m", "app.seed"], cwd=ROOT, env=env, stdout=log, stderr=log, check=True, timeout=30)
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/full_smoke_check.py")], cwd=ROOT, env=env, stdout=log, stderr=log, timeout=120)
        payload = json.loads((raw / "full-smoke-results.json").read_text(encoding="utf-8"))
        payload["isolation"] = "Disposable PostgreSQL schema; all accounts and records are synthetic"
        payload["raw_evidence_directory"] = raw.relative_to(ROOT).as_posix()
        payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(payload['checks'])} regression checks; all_passed={payload['all_passed']}; {output.relative_to(ROOT).as_posix()}")
        sys.exit(completed.returncode)
