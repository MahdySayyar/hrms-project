"""Controlled synthetic before/after reads; separate PostgreSQL schema, no live HR workflows or exports."""
import argparse
import gc
import hashlib
import json
import platform
import re
import statistics
import sys
import tracemalloc
from collections import Counter
from contextlib import ExitStack
from datetime import date, datetime, time, timezone
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import access, database, main, modules, security
from app.database import Admin, Branch, Employee, Position, Unit
from app.hr_models import Attendance, AuditLog, Candidate, HrRequest, Payslip, Shift
from tests.support import PostgresSandbox


def seed(factory, count):
    with factory() as db:
        branch = Branch(name="Synthetic measured branch")
        position = Position(title="Synthetic measured position", description="Disposable architecture fixture")
        db.add_all([branch, position])
        db.flush()
        unit = Unit(name="Synthetic measured unit", branch_id=branch.id)
        shift = Shift(name="Synthetic measured shift", start_time=time(8), end_time=time(16), break_minutes=0)
        admin = Admin(username="synthetic_architecture_admin", display_name="کاربر ساختگی اندازه‌گیری", password_hash="unused",
                      role="admin", is_active=True)
        db.add_all([unit, shift, admin])
        db.flush()
        employee_data = [dict(employee_code=f"SYN-{i:06}", first_name="کارمند", last_name=f"ساختگی {i}",
            national_id="9900000000", phone="09000000000", email="synthetic@example.invalid", hire_date=date(2024, 1, 1),
            branch_id=branch.id, unit_id=unit.id, position_id=position.id, contract_type="دائم", active=i % 2 == 0) for i in range(count)]
        db.execute(insert(Employee), employee_data)
        ids = db.scalars(select(Employee.id).order_by(Employee.id)).all()
        db.execute(insert(HrRequest), [dict(employee_id=ident, kind="leave", start_date=date(2030, 1, 1),
            end_date=date(2030, 1, 2), status="pending", description="درخواست ساختگی") for ident in ids])
        db.execute(insert(Attendance), [dict(employee_id=ident, work_date=date(2025, 1, 2), shift_id=shift.id,
            presence_status="present", worked_minutes=480, overtime_minutes=0, required_minutes=480) for ident in ids])
        db.execute(insert(Payslip), [dict(employee_id=ident, period="2025-01", base_amount=100, overtime_amount=0,
            benefits=0, insurance=0, tax=0, deductions=0, net_amount=100, input_snapshot={"employee_name": "کارمند ساختگی"},
            rule_snapshot={}, created_by=admin.id) for ident in ids])
        db.execute(insert(Candidate), [dict(first_name="متقاضی", last_name=f"ساختگی {i}", national_id="9900000000",
            phone="09000000000", email="synthetic@example.invalid", branch_id=branch.id, unit_id=unit.id,
            position_id=position.id, application_date=date(2025, 1, 1), status="new") for i in range(150)])
        db.commit()
        return admin.id


def measured_get(client, engine, path, *, measure_memory=False):
    statements = []
    def capture(_conn, _cursor, sql, _params, _context, _many):
        statements.append(sql)  # Only synthetic statements, parameters are never collected or exported.
    event.listen(engine, "before_cursor_execute", capture)
    if measure_memory:
        gc.collect()
        tracemalloc.start()
    try:
        started = perf_counter()
        response = client.get(path, follow_redirects=False)
        elapsed = (perf_counter() - started) * 1000
        peak = tracemalloc.get_traced_memory()[1] if measure_memory else None
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        if measure_memory:
            tracemalloc.stop()
    if response.status_code != 200:
        raise AssertionError("Synthetic read did not return HTTP 200.")
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    tables = Counter()
    for sql in selects:
        match = re.search(r"\bFROM\s+(\w+)", sql)
        if match:
            tables[match[1]] += 1
    # Compare rendered bytes with the random CSRF value removed; no body or row values leave the lab.
    body = response.content
    if "text/html" in response.headers.get("content-type", ""):
        body = re.sub(rb'(name="csrf_token" value=")[^"]+("\s*>)', rb'\1CSRF\2', body)
    result = {"status": response.status_code, "elapsed_ms": elapsed, "selects": len(selects),
              "selects_by_primary_table": dict(tables), "response_bytes": len(response.content),
              "canonical_body_sha256": hashlib.sha256(body).hexdigest()}
    if peak is not None:
        result["python_tracemalloc_peak_bytes"] = peak
    return result


def explain_synthetic(engine):
    plans = {}
    queries = {
        "approved_overlap": "SELECT id FROM hr_requests WHERE employee_id = 1 AND id <> 1 AND kind IN ('leave','travel') AND status = 'approved' AND start_date <= DATE '2030-01-02' AND end_date >= DATE '2030-01-01'",
        "attendance_period": "SELECT coalesce(sum(worked_minutes),0) FROM attendance WHERE work_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-31'",
        "payslip_period": "SELECT coalesce(sum(net_amount),0) FROM payslips WHERE period = '2025-01'",
    }
    with engine.begin() as connection:
        for name in ("hr_requests", "attendance", "payslips"):
            connection.execute(text("ANALYZE " + name))
        for name, sql in queries.items():
            plans[name] = connection.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))
    return {"provenance": "Synthetic rows in a disposable schema; plans do not describe production traffic or selective historical months",
            "candidate_indexes_applied": False, "plans": plans}


def run(args):
    target = (ROOT / args.output).resolve()
    target.relative_to(ROOT)
    if target.exists():
        raise FileExistsError("Choose a new evidence filename.")
    if not 100 <= args.employees <= 10000 or not 3 <= args.repeats <= 20:
        raise ValueError("Use 100..10000 synthetic employees and 3..20 repeated sequential samples.")
    started = datetime.now(timezone.utc)
    with ExitStack() as stack:
        sandbox = stack.enter_context(PostgresSandbox())
        user_id = seed(sandbox.session_factory, args.employees)
        for module in (main, modules, access, database):
            stack.enter_context(patch.object(module, "SessionLocal", sandbox.session_factory))
        stack.enter_context(patch.object(main, "engine", sandbox.engine))
        token, _ = security.new_session(user_id)
        def remove_session():
            with security.session_lock:
                security.sessions.pop(token, None)
        stack.callback(remove_session)
        client = stack.enter_context(TestClient(main.app, raise_server_exceptions=False))
        client.cookies.set(security.COOKIE_NAME, token)
        readings = []
        for path in [f"/hr/{module}?page_size={size}" for module in ("leave", "attendance", "candidates") for size in (1, 50, 100)] + ["/reports/employees.csv"]:
            measured_get(client, sandbox.engine, path)  # One warm sample, excluded from statistics.
            samples = [measured_get(client, sandbox.engine, path) for _ in range(args.repeats)]
            timings = sorted(s["elapsed_ms"] for s in samples)
            readings.append({"path": path, "warmups": 1, "samples": samples,
                "median_ms": statistics.median(timings), "min_ms": timings[0], "max_ms": timings[-1],
                "note": "Sequential local TestClient timing, not a load-test P95 or capacity estimate"})
        csv_memory = measured_get(client, sandbox.engine, "/reports/employees.csv", measure_memory=True)
        reports = []
        for period in ("2025-01", "۲۰۲۵-۰۱", "٢٠٢٥-٠١"):
            response = client.get("/reports", params={"period": period})
            if response.status_code != 200:
                raise AssertionError("A syntactically valid synthetic report period was rejected.")
            reports.append({"input_period": period, "rendered_period": response.context["period"],
                            "payroll_total": int(response.context["payroll_total"]),
                            "expected_synthetic_payroll_total": 100 * args.employees})
        index_plans = explain_synthetic(sandbox.engine)
        with sandbox.session_factory() as db:
            export_audits = db.scalars(select(AuditLog).where(AuditLog.action == "export")).all()
            audit_summary = {"count": len(export_audits), "all_row_counts_correct": all(row.details.get("rows") == args.employees for row in export_audits)}
    # The context has now dropped this schema. Only hashes, aggregates and plans with synthetic literals are exported.
    payload = {"id": "MEASURE-READ-PATHS-20261117", "phase": args.phase, "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(), "isolation": "Disposable PostgreSQL schema, synthetic records, real SQL/HTTP rendering in TestClient; no live web process changed",
        "schema_removed": not sandbox.created, "python": platform.python_version(), "platform": platform.platform(),
        "employees": args.employees, "requests_seeded": args.employees, "attendance_seeded": args.employees,
        "payslips_seeded": args.employees, "candidates_seeded": 150, "repeats": args.repeats,
        "authentication": "One synthetic admin session issued before timing; login is excluded",
        "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                          ("app/modules.py", "app/main.py", "app/hr_models.py", "scripts/measure_read_paths_20261117.py")},
        "reads": readings, "csv_memory_sample": csv_memory, "export_audits": audit_summary,
        "report_period_probe": reports, "index_plan_probe": index_plans,
        "limitations": ["One host, one in-process HTTP app, sequential warm samples; no RPS or concurrent-user capacity claim",
                        "Tracemalloc measures Python allocations, not total native/process/PostgreSQL RSS",
                        "All attendance and payslips lie in one month; this is unsuitable for deciding a selective period index",
                        "CSV still returns a complete buffered response; the experiment measures input-row materialization cost"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"phase": args.phase, "schema_removed": payload["schema_removed"],
        "reads": [{"path": r["path"], "selects": r["samples"][0]["selects"], "median_ms": round(r["median_ms"], 2)} for r in readings],
        "csv_python_peak_bytes": csv_memory["python_tracemalloc_peak_bytes"], "periods": reports}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--employees", type=int, default=10000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
