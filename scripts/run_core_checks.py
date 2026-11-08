"""Run contract tests and save exact pass/fail evidence without live HR data or credentials."""
import argparse
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        self.records.append({"test": test.id(), "status": "passed"})
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.records.append({"test": test.id(), "status": "failed", "reason": str(err[1])})
        super().addFailure(test, err)

    def addError(self, test, err):
        self.records.append({"test": test.id(), "status": "error", "reason": type(err[1]).__name__})
        super().addError(test, err)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", required=True, help="A new JSON evidence path; existing results are preserved")
    parser.add_argument("--pattern", default="test_core_workflows.py")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        parser.error("Evidence already exists. Use a new output name.")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=args.pattern, top_level_dir=str(ROOT))
    start = datetime.now(timezone.utc)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    revision = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    payload = {"phase": args.phase, "started_at": start.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_parent_commit": revision, "database": "PostgreSQL", "isolation": "Disposable hrms_test_<uuid> schema; synthetic fixtures",
        "tests_run": result.testsRun, "all_passed": result.wasSuccessful(), "checks": result.records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output.relative_to(ROOT).as_posix()}")
    sys.exit(0 if result.wasSuccessful() else 1)
