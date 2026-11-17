"""Audit publishable files and Git history without printing runtime secret values."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent


def git(*arguments):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *arguments], cwd=ROOT)


def candidates():
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    return sorted({name for name in names if name and (ROOT / name).is_file()})


def audit():
    secret_values = []
    env = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}
    if env.get("ADMIN_PASSWORD"):
        secret_values.append(env["ADMIN_PASSWORD"])
    if env.get("DATABASE_URL"):
        password = make_url(env["DATABASE_URL"]).password
        if password:
            secret_values.append(password)
    folder = ROOT / ".runtime/docker-hrms-secrets"
    for name in ("db_password", "admin_password", "redis_password"):
        if (folder / name).exists():
            secret_values.append((folder / name).read_text(encoding="utf-8").strip())
    secrets = [value.encode("utf-8") for value in secret_values if len(value) >= 12 and not value.startswith("CHANGE_ME")]
    patterns = {
        "github_token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
        "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "aws_access_key": rb"AKIA[0-9A-Z]{16}",
    }
    findings = []

    def forbidden(name):
        parts = Path(name).parts
        leaf = Path(name).name
        return bool(set(parts) & {".runtime", ".venv", "artifacts", "node_modules"}) or (
            leaf == ".env" or leaf.startswith(".env.") and leaf != ".env.example"
        ) or Path(name).suffix.lower() in {".dump", ".backup", ".sqlite", ".sqlite3", ".zip", ".tar", ".gz"}

    def inspect(name, data, scope):
        for rule, pattern in patterns.items():
            if re.search(pattern, data):
                findings.append({"scope": scope, "path": name, "rule": rule})
        if any(value in data for value in secrets):
            findings.append({"scope": scope, "path": name, "rule": "known_runtime_secret"})

    names = candidates()
    for name in names:
        if forbidden(name):
            findings.append({"scope": "working_tree", "path": name, "rule": "private_or_archive_path"})
        inspect(name, (ROOT / name).read_bytes(), "working_tree")
    blobs = 0
    for entry in git("rev-list", "--objects", "--all").decode("utf-8").splitlines():
        object_id, _, name = entry.partition(" ")
        if git("cat-file", "-t", object_id).strip() != b"blob":
            continue
        blobs += 1
        if forbidden(name):
            findings.append({"scope": "history", "path": name, "rule": "private_or_archive_path"})
        inspect(name, git("cat-file", "blob", object_id), "history")
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(), "all_passed": not findings,
        "publishable_files": len(names), "history_blobs_checked": blobs, "findings": findings,
        "scope": "Ignored runtime excluded; known local runtime secret bytes and selected credential patterns checked in publishable files and all Git blobs; no database rows read/exported",
        "human_review": "pending",
        "source_files": [{"path": name, "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
                         for name in names if name.startswith(("app/", "deployments/"))],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = (ROOT / args.output).resolve()
    target.relative_to(ROOT)
    if target.exists():
        parser.error("Choose a new evidence filename.")
    result = audit()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("all_passed", "publishable_files", "history_blobs_checked", "findings")}))
    raise SystemExit(0 if result["all_passed"] else 1)
