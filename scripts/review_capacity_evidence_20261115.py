"""Independently assess saved synthetic capacity evidence without HR database access."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def review(evidence, output):
    evidence = (ROOT / evidence).resolve()
    output = (ROOT / output).resolve()
    evidence.relative_to(ROOT)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError("Choose a new review evidence name.")
    result = json.loads(evidence.read_text(encoding="utf-8"))
    metrics, burst = result["metrics"], result.get("burst", {})
    operations = burst.get("persistence_checks", [])
    checks = {
        "500_requested_and_authenticated": result["users_requested"] == metrics["authenticated_users_peak"] == 500,
        "10000_synthetic_employees": result["initial_employee_count"] == 10000,
        "300_seconds_completed_steady": metrics["steady_seconds"] >= 300 and metrics["finish_reason"] == "steady_completed",
        "steady_requests_present": metrics["requests"] > 0,
        "zero_steady_errors": metrics["failures"] == 0 and metrics["failure_fraction"] == 0,
        "all_four_workers_observed": result["web_workers"] == 4 and set(metrics["workers_observed_steady"]) == {"0", "1", "2", "3"},
        "500_request_burst_completed": burst.get("mode") == "requests" and burst.get("completed") == len(operations) == 500,
        "distinct_employees_in_burst": len({p["employee_id"] for p in operations}) == 500,
        "each_burst_acknowledged_and_persisted_with_one_audit": bool(operations) and all(
            p["acknowledged"] and p["persisted_once_with_audit"] for p in operations),
        "source_capture_present": (ROOT / result["source_archive"]).is_file(),
    }
    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "coding agent; independent saved-file checks, not human acceptance",
        "input": evidence.relative_to(ROOT).as_posix(), "input_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "checks": checks, "zero_error_500_user_scenario_passed": all(checks.values()),
        "latency_nfr_passed": bool(metrics["requests"] and metrics["p95_ms"] < 2000 and metrics["failure_fraction"] < .01
            and checks["500_requested_and_authenticated"] and checks["300_seconds_completed_steady"]),
        "p95_ms": metrics["p95_ms"], "requests": metrics["requests"], "steady_errors": metrics["failures"],
        "burst_dispatch_spread_ms": burst.get("dispatch_spread_ms"),
        "limitations": ["Authenticated workload after gradual login; not simultaneous login pressure",
            "Generator, proxy, webs and PostgreSQL share one host", "No HA, worker failure, TLS or real-user acceptance demonstrated",
            "Persistence was checked in a disposable synthetic fixture, not real HR records"],
        "human_review": "pending",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("zero_error_500_user_scenario_passed", "latency_nfr_passed", "requests", "steady_errors", "p95_ms")}))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    review(args.evidence, args.output)
