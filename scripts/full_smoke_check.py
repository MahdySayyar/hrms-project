"""گردش‌های کامل هشت ماژول روی HTTP و PostgreSQL واقعی؛ داده‌ها ساختگی‌اند."""
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path
import httpx
from sqlalchemy import delete, func, select

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from app.database import Admin, Branch, Employee, Position, SessionLocal, Unit
from app.hr_models import (AssignmentHistory, Attendance, AuditLog, Candidate, CareerPlan, EmploymentContract, Evaluation,
                          HrRequest, Interview, OnboardingTask, PayrollProfile, PayrollRule, Payslip, Shift, Training, TrainingEnrollment)
from app.module_forms import MODULES

results, created = [], {}
run_id = uuid.uuid4().hex[:8]
completed = False
server = None
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
log = (artifacts / "full-smoke-server.log").open("w", encoding="utf-8")
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
base_url = f"http://127.0.0.1:{port}"


def check(name, passed):
    results.append({"check": name, "passed": bool(passed)})
    print(("PASS " if passed else "FAIL ") + name, flush=True)
    if not passed:
        raise AssertionError(name)


def remember(model, record_id):
    created.setdefault(model, []).append(record_id)
    return record_id


def start():
    global server
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=root, stdout=log, stderr=log)
    for _ in range(100):
        try:
            if httpx.get(base_url + "/health", timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if server.poll() is not None:
            raise RuntimeError("Server exited; inspect full-smoke-server.log.")
        time.sleep(0.1)
    raise RuntimeError("Server did not become ready.")


def stop():
    if server and server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def token(client):
    page = client.get("/")
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def login(username, password):
    client = httpx.Client(base_url=base_url, follow_redirects=False, timeout=15, trust_env=False)
    page = client.get("/login")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post("/login", data={"csrf_token": csrf, "username": username, "password": password})
    check("login " + username, response.status_code == 303)
    return client


def post(client, url, data):
    return client.post(url, data={"csrf_token": token(client), **data})


def create(client, module, data):
    response = post(client, f"/hr/{module}/new", data)
    if response.status_code != 303:
        (artifacts / "full-smoke-failure.html").write_text(response.text, encoding="utf-8")
    check(module + " creation", response.status_code == 303)
    record_id = int(response.headers["location"].split("/")[3].split("?")[0])
    return remember(MODULES[module]["model"], record_id)


try:
    with SessionLocal() as db:
        unit = db.scalar(select(Unit).order_by(Unit.id))
        other = db.scalar(select(Unit).where(Unit.branch_id != unit.branch_id))
        position = db.scalar(select(Position).order_by(Position.id))
        branch_id, unit_id, other_branch, other_unit, position_id = unit.branch_id, unit.id, other.branch_id, other.id, position.id
        baseline_employee_count = db.scalar(select(func.count()).select_from(Employee))
        current_admin_id = db.scalar(select(Admin.id).where(Admin.username == os.environ["ADMIN_USERNAME"]))
        existing_rule = db.scalar(select(PayrollRule).where(PayrollRule.contract_type == "آزمایشی"))
        if existing_rule:
            raise RuntimeError("This smoke scenario needs the educational 'آزمایشی' rule to be unused; use a disposable test database if already configured.")
    start()
    admin = login(os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"])
    for module in MODULES:
        check(module + " list and form render", admin.get(f"/hr/{module}").status_code == 200 and admin.get(f"/hr/{module}/new").status_code == 200)
    check("module overview shows eight functional sections", admin.get("/modules").status_code == 200 and "حقوق و فیش‌های آموزشی" in admin.get("/modules").text)
    check("new module forms reject forged CSRF", admin.post("/hr/candidates/new", data={"csrf_token": "forged"}).status_code == 403)
    own_position_title = f"سمت آزمایشی {run_id}"
    check("create disposable position for history test", post(admin, "/organization/positions/new", {"title": own_position_title, "description": "شرح شغل ساختگی"}).status_code == 303)
    with SessionLocal() as db:
        position_id = remember(Position, db.scalar(select(Position.id).where(Position.title == own_position_title)))
    candidate_data = {"first_name": "متقاضی آزمون", "last_name": run_id, "national_id": "9900020011", "phone": "09000200011", "email": "full-test@example.invalid", "branch_id": str(branch_id), "unit_id": str(unit_id), "position_id": str(position_id), "application_date": "2025-01-01", "status": "new", "notes": "دادهٔ ساختگی آزمون"}
    candidate_id = create(admin, "candidates", candidate_data)
    check("candidate requires a passed interview before acceptance", post(admin, f"/hr/candidates/{candidate_id}/edit", {**candidate_data, "status": "accepted"}).status_code == 400)
    interview_data = {"candidate_id": str(candidate_id), "scheduled_at": "2025-01-02T10:30", "interviewer": "مصاحبه‌کنندهٔ ساختگی", "result": "passed", "notes": "نتیجهٔ ساختگی"}
    interview_id = create(admin, "interviews", interview_data)
    check("passed interview permits candidate acceptance", post(admin, f"/hr/candidates/{candidate_id}/edit", {**candidate_data, "status": "accepted"}).status_code == 303)
    hire = post(admin, f"/hire/{candidate_id}", {"employee_code": f"FULL-{run_id}".upper(), "hire_date": "2025-01-01", "contract_type": "آزمایشی"})
    check("candidate hiring succeeds", hire.status_code == 303)
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        employee_id = remember(Employee, candidate.employee_id)
        tasks = db.scalars(select(OnboardingTask).where(OnboardingTask.candidate_id == candidate_id)).all()
        check("hiring creates one employee and three onboarding tasks", candidate.status == "hired" and employee_id and len(tasks) == 3)
        for task in tasks:
            remember(OnboardingTask, task.id)
        task_id = tasks[0].id
    check("repeated hiring does not duplicate employee", post(admin, f"/hire/{candidate_id}", {"employee_code": "IGNORED"}).status_code == 303)
    check("onboarding task completion succeeds", post(admin, f"/onboarding/{task_id}", {"completed": "true"}).status_code == 303)
    check("hired candidate demographics cannot be overwritten", post(admin, f"/hr/candidates/{candidate_id}/edit", candidate_data).status_code == 400)
    check("candidate detail shows employee link and checklist", admin.get(f"/hr/candidates/{candidate_id}").status_code == 200 and "چک‌لیست پذیرش" in admin.get(f"/hr/candidates/{candidate_id}").text)
    shift_id = create(admin, "shifts", {"name": f"شیفت آزمون {run_id}", "start_time": "08:00", "end_time": "16:00", "break_minutes": "0"})
    attendance_data = {"employee_id": str(employee_id), "work_date": "2025-02-03", "shift_id": str(shift_id), "clock_in": "08:00", "clock_out": "18:00", "notes": "ساختگی"}
    attendance_id = create(admin, "attendance", attendance_data)
    with SessionLocal() as db:
        attendance = db.get(Attendance, attendance_id)
        check("attendance computes 600 worked minutes and 120 overtime minutes", attendance.worked_minutes == 600 and attendance.overtime_minutes == 120)
    check("duplicate employee-day attendance rejected", post(admin, "/hr/attendance/new", attendance_data).status_code == 400)
    check("presence requires clock-in and clock-out", post(admin, "/hr/attendance/new", {**attendance_data, "work_date": "2025-02-07", "clock_in": "", "clock_out": ""}).status_code == 400)
    absence_id = create(admin, "attendance", {**attendance_data, "work_date": "2025-02-05", "presence_status": "absent", "clock_in": "", "clock_out": ""})
    with SessionLocal() as db:
        absence = db.get(Attendance, absence_id)
        check("absence persists without fabricated work or overtime", absence.presence_status == "absent" and absence.clock_in is None and absence.worked_minutes == 0 and absence.overtime_minutes == 0)
    night_id = create(admin, "shifts", {"name": f"شیفت شب آزمون {run_id}", "start_time": "22:00", "end_time": "06:00", "break_minutes": "0"})
    night_attendance = create(admin, "attendance", {**attendance_data, "work_date": "2025-02-04", "shift_id": str(night_id), "clock_in": "22:00", "clock_out": "06:00"})
    with SessionLocal() as db:
        check("night shift crosses midnight correctly", db.get(Attendance, night_attendance).worked_minutes == 480 and db.get(Attendance, night_attendance).overtime_minutes == 0)
    leave_data = {"employee_id": str(employee_id), "start_date": "2025-03-01", "end_date": "2025-03-02", "leave_type": "annual", "description": "درخواست ساختگی"}
    leave_id = create(admin, "leave", leave_data)
    check("leave approval succeeds with administrator", post(admin, f"/requests/{leave_id}/review", {"decision": "approved", "review_notes": "تأیید ساختگی"}).status_code == 303)
    with SessionLocal() as db:
        item = db.get(HrRequest, leave_id)
        check("request stores approver and review time", item.status == "approved" and item.reviewed_by and item.reviewed_at)
    check("reviewed request cannot be overwritten", post(admin, f"/hr/leave/{leave_id}/edit", leave_data).status_code == 400)
    overlap_id = create(admin, "travel", {"employee_id": str(employee_id), "start_date": "2025-03-02", "end_date": "2025-03-03", "destination": "مقصد ساختگی", "description": "مأموریت ساختگی"})
    check("overlapping approved travel and leave rejected", post(admin, f"/requests/{overlap_id}/review", {"decision": "approved", "review_notes": ""}).status_code == 400)
    check("rejection requires a reason", post(admin, f"/requests/{overlap_id}/review", {"decision": "rejected", "review_notes": ""}).status_code == 400)
    check("travel rejection with reason succeeds", post(admin, f"/requests/{overlap_id}/review", {"decision": "rejected", "review_notes": "هم‌پوشانی آزمایشی"}).status_code == 303)
    administrative_id = create(admin, "administrative", {"employee_id": str(employee_id), "start_date": "2025-03-05", "description": "درخواست گواهی ساختگی"})
    check("administrative request can be approved", post(admin, f"/requests/{administrative_id}/review", {"decision": "approved", "review_notes": ""}).status_code == 303)
    profile_data = {"employee_id": str(employee_id), "base_salary": "60000000", "hourly_rate": "300000", "benefits": "5000000", "deductions": "1000000"}
    profile_id = create(admin, "payroll-profiles", profile_data)
    rule_data = {"contract_type": "آزمایشی", "calculation_mode": "monthly", "monthly_hours": "200", "overtime_factor": "1.5", "insurance_percent": "5", "tax_percent": "10", "notes": "نرخ‌های صرفاً آزمایشی؛ مقررات قانونی نیست"}
    rule_id = create(admin, "payroll-rules", rule_data)
    calculated = post(admin, "/payroll/calculate", {"employee_id": str(employee_id), "period": "2025-02"})
    check("educational monthly payroll calculation succeeds", calculated.status_code == 303)
    payslip_id = remember(Payslip, int(calculated.headers["location"].split("/")[2]))
    with SessionLocal() as db:
        payslip = db.get(Payslip, payslip_id)
        original_snapshot = dict(payslip.rule_snapshot)
        check("monthly payroll formula produces expected 55015000 rial", payslip.overtime_amount == 900000 and payslip.net_amount == 55015000)
    check("payslip is labeled educational and displays saved input rates", "فیش حقوقی آموزشی" in admin.get(f"/payroll/{payslip_id}").text)
    check("payroll rule can be changed", post(admin, f"/hr/payroll-rules/{rule_id}/edit", {**rule_data, "calculation_mode": "hourly", "overtime_factor": "2"}).status_code == 303)
    repeated = post(admin, "/payroll/calculate", {"employee_id": str(employee_id), "period": "2025-02"})
    with SessionLocal() as db:
        check("same-period payroll preserves original payslip and rule snapshot", repeated.headers.get("location") == f"/payroll/{payslip_id}" and db.get(Payslip, payslip_id).rule_snapshot == original_snapshot)
    march_attendance = create(admin, "attendance", {**attendance_data, "work_date": "2025-03-06"})
    hourly = post(admin, "/payroll/calculate", {"employee_id": str(employee_id), "period": "2025-03"})
    hourly_id = remember(Payslip, int(hourly.headers["location"].split("/")[2]))
    with SessionLocal() as db:
        pay = db.get(Payslip, hourly_id)
        check("hourly payroll counts regular and overtime hours once", pay.base_amount == 2400000 and pay.overtime_amount == 1200000 and pay.net_amount == 6310000)
    contract_data = {"employee_id": str(employee_id), "contract_type": "آزمایشی", "start_date": "2025-01-01", "end_date": "2027-01-01", "base_salary": "61000000", "notes": "قرارداد ساختگی"}
    contract_id = create(admin, "contracts", contract_data)
    check("contract activation succeeds", post(admin, f"/contracts/{contract_id}/activate", {}).status_code == 303)
    with SessionLocal() as db:
        check("activation updates current contract and payroll base", db.get(Employee, employee_id).contract_type == "آزمایشی" and db.get(PayrollProfile, profile_id).base_salary == 61000000)
    check("active contract cannot be rewritten", post(admin, f"/hr/contracts/{contract_id}/edit", contract_data).status_code == 400)
    renew = post(admin, f"/contracts/{contract_id}/renew", {"start_date": "2026-01-01", "end_date": "2027-12-31", "contract_type": "آزمایشی", "base_salary": "62000000", "notes": "تمدید ساختگی"})
    check("contract renewal creates a preserved draft", renew.status_code == 303)
    renewed_id = remember(EmploymentContract, int(renew.headers["location"].split("/")[3].split("?")[0]))
    check("renewal activation succeeds", post(admin, f"/contracts/{renewed_id}/activate", {}).status_code == 303)
    with SessionLocal() as db:
        check("renewal retains previous contract with closed date range", db.get(EmploymentContract, contract_id).status == "renewed" and db.get(EmploymentContract, contract_id).end_date == date(2025, 12, 31) and db.get(EmploymentContract, renewed_id).status == "active")
    check("termination retains records and deactivates employee", post(admin, f"/contracts/{renewed_id}/terminate", {"end_date": "2026-02-01", "reason": "خاتمهٔ ساختگی"}).status_code == 303)
    with SessionLocal() as db:
        check("terminated contract is retained in PostgreSQL", db.get(EmploymentContract, renewed_id).status == "ended" and not db.get(Employee, employee_id).active)
    evaluation_id = create(admin, "evaluations", {"employee_id": str(employee_id), "review_date": "2025-05-01", "score": "85", "feedback": "بازخورد ساختگی", "goals": "هدف آزمایشی"})
    check("invalid performance score rejected", post(admin, "/hr/evaluations/new", {"employee_id": str(employee_id), "review_date": "2025-05-02", "score": "101", "feedback": "ساختگی", "goals": "ساختگی"}).status_code == 400)
    training_id = create(admin, "trainings", {"title": f"دورهٔ آزمون {run_id}", "training_date": "2025-06-01", "capacity": "1", "description": "دورهٔ ساختگی"})
    enrollment_id = create(admin, "enrollments", {"employee_id": str(employee_id), "training_id": str(training_id), "status": "completed", "notes": "گذراندن ساختگی"})
    with SessionLocal() as db:
        other_employee = db.scalar(select(Employee.id).where(Employee.id != employee_id))
    check("training capacity cannot be exceeded", post(admin, "/hr/enrollments/new", {"employee_id": str(other_employee), "training_id": str(training_id), "status": "planned", "notes": ""}).status_code == 400)
    career_id = create(admin, "career", {"employee_id": str(employee_id), "target_position_id": str(position_id), "target_date": "2027-01-01", "progress": "30", "actions": "برنامهٔ ساختگی توسعه"})
    employee_edit = {"employee_code": f"FULL-{run_id}".upper(), "first_name": "متقاضی آزمون", "last_name": run_id, "national_id": "9900020011", "phone": "09000200011", "email": "full-test@example.invalid", "hire_date": "2025-01-01", "branch_id": str(other_branch), "unit_id": str(other_unit), "position_id": str(position_id), "contract_type": "آزمایشی"}
    check("organizational assignment change succeeds", post(admin, f"/employees/{employee_id}/edit", employee_edit).status_code == 303)
    check("position can be renamed without rewriting historical assignment", post(admin, f"/organization/positions/{position_id}/edit", {"title": own_position_title + " جدید", "description": "شرح شغل ساختگی"}).status_code == 303)
    with SessionLocal() as db:
        histories = db.scalars(select(AssignmentHistory).where(AssignmentHistory.employee_id == employee_id).order_by(AssignmentHistory.id)).all()
        check("history retains previous assignment and exactly one current assignment", len(histories) == 2 and histories[0].branch_id == branch_id and histories[0].end_date is not None and histories[1].branch_id == other_branch and histories[1].end_date is None)
        check("history preserves position title as recorded before later renaming", all(item.position_title == own_position_title for item in histories))
    check("history and aggregate reports render", admin.get(f"/history/{employee_id}").status_code == 200 and admin.get("/reports?period=2025-02").status_code == 200)
    csv_response = admin.get("/reports/employees.csv")
    check("CSV export excludes national ID and phone", csv_response.status_code == 200 and "9900020011" not in csv_response.text and "09000200011" not in csv_response.text)
    password = "Full-Smoke-Password-123"
    hr_username, viewer_username = f"hr_{run_id}", f"view_{run_id}"
    hr_id = create(admin, "users", {"username": hr_username, "display_name": "کارشناس آزمون", "password": password, "role": "hr", "branch_scope_id": str(branch_id), "unit_scope_id": str(unit_id), "is_active": "true"})
    viewer_id = create(admin, "users", {"username": viewer_username, "display_name": "مشاهده‌گر آزمون", "password": password, "role": "viewer", "branch_scope_id": str(branch_id), "unit_scope_id": "", "is_active": "true"})
    hr = login(hr_username, password)
    check("scoped HR cannot read employee moved to another branch", hr.get(f"/employees/{employee_id}").status_code == 404 and f"FULL-{run_id}".upper() not in hr.get("/employees").text)
    check("scoped HR cannot access payroll, audit or user management", all(hr.get(path).status_code == 403 for path in ("/payroll", "/audit", "/hr/users")))
    check("HR cannot approve administrative requests", post(hr, f"/requests/{administrative_id}/review", {"decision": "approved", "review_notes": ""}).status_code == 403)
    check("HR cannot create candidates in another branch", post(hr, "/hr/candidates/new", {**candidate_data, "branch_id": str(other_branch), "unit_id": str(other_unit)}).status_code in (400, 403))
    hr_edit = {"username": hr_username, "display_name": "کارشناس آزمون", "password": "", "role": "hr", "branch_scope_id": str(branch_id), "unit_scope_id": str(unit_id), "is_active": "false"}
    check("administrator can deactivate an HR account", post(admin, f"/hr/users/{hr_id}/edit", hr_edit).status_code == 303)
    check("deactivated HR account immediately loses its session", hr.get("/").status_code == 303)
    check("administrator can reactivate the same HR account", post(admin, f"/hr/users/{hr_id}/edit", {**hr_edit, "is_active": "true"}).status_code == 303)
    check("administrator cannot disable own management access", post(admin, f"/hr/users/{current_admin_id}/edit", {"username": os.environ["ADMIN_USERNAME"], "display_name": "مدیر منابع انسانی", "password": "", "role": "viewer", "branch_scope_id": "", "unit_scope_id": "", "is_active": "false"}).status_code == 400)
    viewer = login(viewer_username, password)
    check("viewer can see aggregate dashboard and reports", viewer.get("/").status_code == 200 and viewer.get("/reports").status_code == 200)
    check("viewer cannot see employee records, CSV, recruitment or payroll", all(viewer.get(path).status_code == 403 for path in ("/employees", "/reports/employees.csv", "/hr/candidates", "/payroll")))
    check("viewer dashboard does not leak employee names", "سارا نمونه" not in viewer.get("/").text and "متقاضی آزمون" not in viewer.get("/").text)
    with SessionLocal() as db:
        audit_record = db.scalar(select(AuditLog).where(AuditLog.entity == "employment_contracts", AuditLog.record_id == renewed_id, AuditLog.action == "terminate"))
        check("contract termination creates an audit entry", audit_record is not None)
    check("audit UI renders", admin.get("/audit").status_code == 200)
    stop()
    start()
    admin.close()
    admin = login(os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"])
    check("recruitment, requests, payslips and contract history survive web restart", all(admin.get(path).status_code == 200 for path in (f"/hr/candidates/{candidate_id}", f"/hr/leave/{leave_id}", f"/payroll/{payslip_id}", f"/hr/contracts/{renewed_id}", f"/history/{employee_id}")))
    admin.close(); hr.close(); viewer.close()
    completed = True
finally:
    stop()
    log.close()
    with SessionLocal() as db:
        user_ids = created.get(Admin, [])
        if user_ids:
            db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        employee_ids = created.get(Employee, [])
        if employee_ids:
            db.execute(delete(AssignmentHistory).where(AssignmentHistory.employee_id.in_(employee_ids)))
        for model in (OnboardingTask, Interview, Candidate, Attendance, HrRequest, Payslip, PayrollProfile, Evaluation, TrainingEnrollment, CareerPlan):
            if created.get(model):
                db.execute(delete(model).where(model.id.in_(created[model])))
        for record_id in reversed(created.get(EmploymentContract, [])):
            db.execute(delete(EmploymentContract).where(EmploymentContract.id == record_id))
        for model in (Training, Shift, PayrollRule, Employee, Admin, Position):
            if created.get(model):
                db.execute(delete(model).where(model.id.in_(created[model])))
        db.commit()
    (artifacts / "full-smoke-results.json").write_text(json.dumps({"run_id": run_id, "database": "PostgreSQL", "checks": results, "all_passed": completed and all(item["passed"] for item in results)}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Completed {len(results)} full-module checks.")
