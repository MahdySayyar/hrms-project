"""Save a named source baseline without overwriting a previous stage or copying secrets."""
import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_FOLDERS = ("app", "templates", "static", "scripts", "docs", "tests", "specs", "models", "prompts", "deployments", ".github")
ROOT_FILES = ("README.md", "AGENTS.md", "requirements.txt", "requirements-lock.txt", "requirements-dev.txt", "requirements-dev-lock.txt", ".gitignore", ".gitattributes", ".env.example", "اجرای سامانه.cmd")


def save_snapshot(name, description):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", name):
        raise ValueError("Use a unique lowercase name containing letters, numbers and hyphens.")
    archive = ROOT / "artifacts" / f"{name}-source.zip"
    manifest = ROOT / "docs" / "snapshots" / f"{name}.json"
    if archive.exists() or manifest.exists():
        raise FileExistsError("This baseline already exists. Choose a new name; historical evidence is never overwritten.")
    files = []
    for folder in SOURCE_FOLDERS:
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT)
            if not path.is_file() or "__pycache__" in relative.parts or relative.parts[:2] == ("docs", "snapshots"):
                continue
            if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example") or path.suffix in (".pyc", ".log", ".secret"):
                continue
            path.resolve().relative_to(ROOT)
            files.append(path)
    files.extend(ROOT / filename for filename in ROOT_FILES if (ROOT / filename).is_file())
    files = sorted(set(files))
    entries = [{"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]
    payload = {"id": name, "captured_at": datetime.now(timezone.utc).isoformat(), "description": description,
               "origin": "Current working files captured by the coding agent; no historical student decisions inferred", "files": entries}
    archive.parent.mkdir(exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as output:
        for path in files + [manifest]:
            output.write(path, path.relative_to(ROOT).as_posix())
    print(f"Saved {len(entries)} source files to {archive.relative_to(ROOT).as_posix()}.")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Unique baseline name; existing archives cannot be overwritten")
    parser.add_argument("--description", default="Source baseline of the current working files")
    args = parser.parse_args()
    save_snapshot(args.name, args.description)
