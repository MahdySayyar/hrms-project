"""Launch a uniquely named disposable Docker verifier; copy only synthetic evidence."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(name, skip_regression=False):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,60}", name):
        raise ValueError("Choose a unique lowercase verification name.")
    raw = ROOT / "artifacts" / ("docker-checks-" + name)
    if raw.exists():
        raise FileExistsError("Verification directory already exists; choose a new name.")
    raw.mkdir()
    command = ["docker", "compose", "-f", str(ROOT / "deployments/compose.yaml"), "run", "--rm", "--no-deps",
        "-T", "--user", "0", "--entrypoint", "python"]
    if skip_regression:
        command += ["--env", "HRMS_CHECK_SKIP_REGRESSION=1"]
    for folder in ("tests", "scripts", "deployments"):
        command += ["--volume", f"{(ROOT / folder).as_posix()}:/srv/hrms/{folder}:ro"]
    command += ["--volume", f"{raw.as_posix()}:/srv/hrms/artifacts/docker-checks",
        "web", "/srv/hrms/scripts/docker_checks_inside_20261116.py"]
    result = subprocess.run(command, cwd=ROOT)
    copies = {"core.json": "core-docker", "coverage.json": "coverage-docker", "regression.json": "regression-docker", "verification.json": "docker-verification"}
    for filename, prefix in copies.items():
        source = raw / filename
        if source.exists():
            target = ROOT / "docs/08-testing/evidence" / (prefix + "-" + name + ".json")
            with target.open("x", encoding="utf-8") as output:
                payload = json.loads(source.read_text(encoding="utf-8"))
                payload["docker_raw_evidence_directory"] = raw.relative_to(ROOT).as_posix()
                output.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--skip-regression", action="store_true", help="Use only when the current source already has a fresh passing regression record")
    args = parser.parse_args()
    raise SystemExit(run(args.name, args.skip_regression))
