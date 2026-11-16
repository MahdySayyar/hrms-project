"""Compare the recorded synthetic read experiments; reject mismatched workloads or changed read output."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def compare(before_path, after_path, output_path):
    paths = [(ROOT / value).resolve() for value in (before_path, after_path, output_path)]
    for path in paths:
        path.relative_to(ROOT)
    before_file, after_file, target = paths
    if target.exists():
        raise FileExistsError("Use a new comparison evidence name.")
    before, after = [json.loads(path.read_text(encoding="utf-8")) for path in (before_file, after_file)]
    settings = ("python", "platform", "employees", "requests_seeded", "attendance_seeded", "payslips_seeded", "candidates_seeded", "repeats", "authentication")
    checks = [{"check": "Matching " + key, "passed": before[key] == after[key]} for key in settings]
    runner = "scripts/measure_read_paths_20261117.py"
    checks.append({"check": "Identical measurement script", "passed": before["source_hashes"][runner] == after["source_hashes"][runner]})
    checks.append({"check": "Both disposable schemas removed", "passed": before["schema_removed"] and after["schema_removed"]})
    prior = {row["path"]: row for row in before["reads"]}
    current = {row["path"]: row for row in after["reads"]}
    checks.append({"check": "Matching endpoints and page sizes", "passed": set(prior) == set(current)})
    results = []
    for path in sorted(set(prior) & set(current)):
        old, new = prior[path], current[path]
        old_hashes = {row["canonical_body_sha256"] for row in old["samples"]}
        new_hashes = {row["canonical_body_sha256"] for row in new["samples"]}
        same_body = old_hashes == new_hashes and len(old_hashes) == 1
        checks.append({"check": "Unchanged successful read bytes " + path, "passed": same_body and all(row["status"] == 200 for row in old["samples"] + new["samples"])})
        results.append({"path": path, "canonical_response_unchanged": same_body,
            "select_counts_before": sorted({row["selects"] for row in old["samples"]}),
            "select_counts_after": sorted({row["selects"] for row in new["samples"]}),
            "median_ms_before": old["median_ms"], "median_ms_after": new["median_ms"],
            "median_reduction_percent": 100 * (1 - new["median_ms"] / old["median_ms"]),
            "response_bytes_before": old["samples"][0]["response_bytes"], "response_bytes_after": new["samples"][0]["response_bytes"]})
    old_memory = before["csv_memory_sample"]["python_tracemalloc_peak_bytes"]
    new_memory = after["csv_memory_sample"]["python_tracemalloc_peak_bytes"]
    checks.append({"check": "CSV audit row counts correct in both experiments", "passed": before["export_audits"]["all_row_counts_correct"] and after["export_audits"]["all_row_counts_correct"]})
    checks.append({"check": "CSV Python allocations reduced", "passed": new_memory < old_memory})
    checks.append({"check": "All after-period spellings produce the expected snapshot total", "passed": all(row["payroll_total"] == row["expected_synthetic_payroll_total"] for row in after["report_period_probe"])})
    payload = {"id": "COMPARE-ARCHITECTURE-READS-20261117", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "before": before_file.relative_to(ROOT).as_posix(), "after": after_file.relative_to(ROOT).as_posix(),
        "input_hashes": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in (before_file, after_file)},
        "all_passed": all(check["passed"] for check in checks), "checks": checks, "reads": results,
        "csv_python_allocations": {"peak_bytes_before": old_memory, "peak_bytes_after": new_memory,
                                   "reduction_percent": 100 * (1 - new_memory / old_memory)},
        "report_period_before": before["report_period_probe"], "report_period_after": after["report_period_probe"],
        "limitations": ["Timing medians summarize five sequential local samples, not production latency, RPS, P95 or statistical confidence",
                        "HTML response hash comparison removes only random CSRF tokens; CSV hashes compare every original byte",
                        "Tracemalloc excludes native/PostgreSQL allocations and is not total-process RAM",
                        "This comparison does not test or certify 500 concurrent users"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": payload["all_passed"], "checks": len(checks), "csv_allocations": payload["csv_python_allocations"],
                      "failures": [check for check in checks if not check["passed"]]}, ensure_ascii=True))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raise SystemExit(compare(args.before, args.after, args.output))
