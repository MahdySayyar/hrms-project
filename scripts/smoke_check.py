"""آزمون واقعی HTTP و PostgreSQL؛ فقط داده‌های ایجادشدهٔ همین آزمون پاک می‌شوند."""
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from app.database import Admin, Branch, Employee, Position, SessionLocal, Unit
from app.security import hash_password, verify_password
from app.hr_models import AssignmentHistory

artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
results = []
created = {Employee: [], Unit: [], Branch: [], Position: []}
run_id = uuid.uuid4().hex[:8]
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
base_url = f"http://127.0.0.1:{port}"
server = None
completed = False
server_log = (artifacts / "smoke-server.log").open("w", encoding="utf-8")


def check(name, condition):
    results.append({"check": name, "passed": bool(condition)})
    print(("PASS " if condition else "FAIL ") + name, flush=True)
    if not condition:
        raise AssertionError(name)


def start_server():
    global server
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=root, stdout=server_log, stderr=server_log)
    for _ in range(100):
        if server.poll() is not None:
            raise RuntimeError("Web process exited; inspect artifacts/smoke-server.log.")
        try:
            if httpx.get(base_url + "/health", timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Web process did not become ready.")


def stop_server():
    global server
    if server and server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
    server = None


def csrf(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    if not match:
        raise AssertionError("CSRF field missing")
    return match.group(1)


def login(client):
    page = client.get("/login")
    return client.post("/login", data={"csrf_token": csrf(page), "username": os.environ["ADMIN_USERNAME"], "password": os.environ["ADMIN_PASSWORD"]})


def counts_and_hash():
    with SessionLocal() as db:
        return [db.scalar(select(func.count()).select_from(model)) for model in [Branch, Unit, Position, Employee, Admin]] + [db.scalar(select(Admin.password_hash))]


def verify_edited_seed():
    # تغییرات آزمایشی روی داده‌های ساختگی، در finally به مقدار اولیه برمی‌گردند.
    snapshots = []
    try:
        with SessionLocal() as db:
            for model, key, field in [(Branch, "demo-branch-1", "name"), (Unit, "demo-unit-1-1", "name"), (Position, "demo-position-1", "title"), (Employee, "demo-employee-1", "employee_code")]:
                record = db.scalar(select(model).where(model.seed_key == key))
                original = getattr(record, field)
                changed = f"EDIT-{run_id}".upper() if model is Employee else original + f" {run_id}"
                snapshots.append((model, record.id, field, original, changed))
                setattr(record, field, changed)
            db.commit()
        before = counts_and_hash()
        subprocess.run([sys.executable, "-m", "app.seed"], cwd=root, check=True, env={**os.environ, "ADMIN_PASSWORD": "different-seed-password"})
        with SessionLocal() as db:
            preserved = all(getattr(db.get(model, record_id), field) == changed for model, record_id, field, _, changed in snapshots)
        check("seed preserves edited sample names and employee codes without duplicates", preserved and counts_and_hash() == before)
        check("seed never silently resets an existing administrator password", counts_and_hash()[-1] == before[-1])
    finally:
        with SessionLocal() as db:
            for model, record_id, field, original, changed in snapshots:
                record = db.get(model, record_id)
                if record and getattr(record, field) == changed:
                    setattr(record, field, original)
            db.commit()


try:
    before = counts_and_hash()
    subprocess.run([sys.executable, "-m", "app.seed"], cwd=root, check=True)
    subprocess.run([sys.executable, "-m", "app.seed"], cwd=root, check=True)
    check("seed is repeatable and preserves administrator hash", before == counts_and_hash())
    verify_edited_seed()
    password_hash = hash_password("smoke-password")
    check("password hash accepts correct password and rejects wrong password", verify_password("smoke-password", password_hash) and not verify_password("wrong", password_hash) and password_hash != "smoke-password")
    with SessionLocal() as db:
        unit = db.scalar(select(Unit).order_by(Unit.id))
        other_unit = db.scalar(select(Unit).where(Unit.branch_id != unit.branch_id))
        position = db.scalar(select(Position).order_by(Position.id))
        unit_id, branch_id, position_id = unit.id, unit.branch_id, position.id
        other_unit_id, other_branch_id = other_unit.id, other_unit.branch_id
    start_server()
    client = httpx.Client(base_url=base_url, follow_redirects=False, timeout=15, trust_env=False)
    check("health and instance expose only basic status and identity", client.get("/health").json() == {"status": "ok"} and set(client.get("/instance").json()) == {"instance"})
    protected_paths = ["/", "/employees", "/employees/new", "/employees/1", "/employees/1/edit", "/organization/branches", "/organization/units", "/organization/positions", "/organization/units/new", "/organization/units/1/edit"]
    check("all dashboard, employee and organization pages require login", all(client.get(path).status_code == 303 and client.get(path).headers.get("location") == "/login" for path in protected_paths))
    check("state-changing employee routes require login", client.post("/employees/new", data={}).status_code == 303)
    page = client.get("/login")
    check("login form is Persian and right-to-left", 'lang="fa" dir="rtl"' in page.text and "ورود به سامانه" in page.text)
    check("login rejects missing CSRF", client.post("/login", data={"username": os.environ["ADMIN_USERNAME"], "password": os.environ["ADMIN_PASSWORD"]}).status_code == 403)
    bad_login = client.post("/login", data={"csrf_token": csrf(page), "username": os.environ["ADMIN_USERNAME"], "password": "incorrect"})
    check("incorrect password shows Persian validation", bad_login.status_code == 401 and "نام کاربری یا رمز عبور درست نیست" in bad_login.text)
    old_cookie = client.cookies.get("hrms_session")
    response = login(client)
    check("administrator login rotates session and sets HttpOnly SameSite cookie", response.status_code == 303 and client.cookies.get("hrms_session") != old_cookie and "HttpOnly" in response.headers["set-cookie"] and "SameSite=lax" in response.headers["set-cookie"])
    dashboard = client.get("/")
    check("dashboard and all reference lists render", dashboard.status_code == 200 and all(client.get(f"/organization/{kind}").status_code == 200 for kind in ["branches", "units", "positions"]))
    token = csrf(dashboard)
    check("employee creation rejects forged CSRF", client.post("/employees/new", data={"csrf_token": "forged"}).status_code == 403)
    payload = {"csrf_token": token, "employee_code": f"CHECK-{run_id}".upper(), "first_name": "آزمون", "last_name": "ذخیره", "national_id": "۹۹۰۰۰۰۰۰۹۹", "phone": "۰۹۰۰۰۰۰۰۰۹۹", "email": "smoke@example.invalid", "hire_date": "2025-02-03", "branch_id": str(branch_id), "unit_id": str(unit_id), "position_id": str(position_id), "contract_type": "مدت‌معین"}
    mismatched = client.post("/employees/new", data={**payload, "unit_id": str(other_unit_id)})
    check("mismatched branch and unit rejected in Persian", mismatched.status_code == 400 and "واحد انتخاب‌شده متعلق به این شعبه نیست" in mismatched.text)
    invalid = client.post("/employees/new", data={**payload, "national_id": "123", "phone": "bad", "email": "wrong", "hire_date": "2025-99-99"})
    check("national ID, phone, email and date validation reject malformed data", invalid.status_code == 400 and all(text in invalid.text for text in ["کد ملی", "شمارهٔ همراه", "نشانی ایمیل", "تاریخ استخدام"]))
    response = client.post("/employees/new", data=payload)
    check("employee create persists and redirects to stable primary key", response.status_code == 303 and re.fullmatch(r"/employees/[0-9]+\?saved=1", response.headers.get("location", "")) is not None)
    employee_id = int(response.headers["location"].split("/")[2].split("?")[0])
    created[Employee].append(employee_id)
    with SessionLocal() as db:
        employee = db.get(Employee, employee_id)
        check("PostgreSQL contains normalized Persian digits and employee values", employee is not None and employee.national_id == "9900000099" and employee.phone == "09000000099" and employee.active)
    check("detail and edit pages show saved employee", payload["employee_code"] in client.get(f"/employees/{employee_id}").text and client.get(f"/employees/{employee_id}/edit").status_code == 200)
    duplicate = client.post("/employees/new", data=payload)
    check("duplicate employee code rejected with Persian message", duplicate.status_code == 400 and "این کد پرسنلی قبلاً ثبت شده است" in duplicate.text)
    changed_payload = {**payload, "first_name": "ویرایش‌شده", "last_name": "<script>alert(1)</script>", "email": "edited@example.invalid"}
    check("employee editing succeeds", client.post(f"/employees/{employee_id}/edit", data=changed_payload).status_code == 303)
    detail = client.get(f"/employees/{employee_id}")
    check("stored text is escaped against HTML injection", "&lt;script&gt;alert(1)&lt;/script&gt;" in detail.text and "<script>alert(1)</script>" not in detail.text)
    check("search works by employee code and Persian full name", payload["employee_code"] in client.get("/employees", params={"q": payload["employee_code"]}).text and payload["employee_code"] in client.get("/employees", params={"q": "ویرایش‌شده"}).text)
    check("search escapes SQL wildcard characters", payload["employee_code"] not in client.get("/employees", params={"q": "%"}).text)
    check("branch and unit filters include matches and exclude other branches", payload["employee_code"] in client.get("/employees", params={"branch": branch_id, "unit": unit_id}).text and payload["employee_code"] not in client.get("/employees", params={"branch": other_branch_id}).text)
    check("deactivation succeeds", client.post(f"/employees/{employee_id}/status", data={"csrf_token": token, "active": "false"}).status_code == 303)
    with SessionLocal() as db:
        employee = db.get(Employee, employee_id)
        check("deactivation retains PostgreSQL record", employee is not None and not employee.active)
    check("active and inactive filters reflect deactivation", payload["employee_code"] in client.get("/employees", params={"status": "inactive"}).text and payload["employee_code"] not in client.get("/employees", params={"status": "active"}).text)
    check("reactivation succeeds", client.post(f"/employees/{employee_id}/status", data={"csrf_token": token, "active": "true"}).status_code == 303)

    for kind, model, field in [("branches", Branch, "name"), ("units", Unit, "name"), ("positions", Position, "title")]:
        name = f"بررسی {kind} {run_id}"
        data = {"csrf_token": token, field: name, "branch_id": str(branch_id), "description": "شرح شغل ساختگی برای آزمون"}
        check(f"organization {kind} create succeeds", client.post(f"/organization/{kind}/new", data=data).status_code == 303)
        with SessionLocal() as db:
            record_id = db.scalar(select(model.id).where(getattr(model, field) == name))
        created[model].append(record_id)
        check(f"organization {kind} edit succeeds", client.post(f"/organization/{kind}/{record_id}/edit", data={**data, field: name + " ویرایش"}).status_code == 303)
        check(f"organization {kind} duplicates rejected", client.post(f"/organization/{kind}/new", data={**data, field: name + " ویرایش"}).status_code == 400)
    with SessionLocal() as db:
        unit_name = db.get(Unit, unit_id).name
    check("moving an occupied unit to another branch is rejected", client.post(f"/organization/units/{unit_id}/edit", data={"csrf_token": token, "name": unit_name, "branch_id": str(other_branch_id)}).status_code == 400)
    with SessionLocal() as db:
        invalid_employee = Employee(**{key: value for key, value in changed_payload.items() if key != "csrf_token"})
        from datetime import date
        invalid_employee.employee_code = f"DB-{run_id}".upper()
        invalid_employee.national_id = "9900000088"
        invalid_employee.phone = "09000000088"
        invalid_employee.hire_date = date(2025, 1, 1)
        invalid_employee.branch_id = branch_id
        invalid_employee.unit_id = other_unit_id
        invalid_employee.position_id = position_id
        db.add(invalid_employee)
        rejected = False
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            rejected = True
        check("PostgreSQL composite foreign key rejects inconsistent assignments", rejected)
    stop_server()
    start_server()
    check("process-local session is invalid after web restart", client.get("/").status_code == 303)
    check("login succeeds again after restart", login(client).status_code == 303)
    detail = client.get(f"/employees/{employee_id}")
    check("created and edited employee survives web-process restart", detail.status_code == 200 and "ویرایش‌شده" in detail.text and "edited@example.invalid" in detail.text)
    with SessionLocal() as db:
        employee = db.get(Employee, employee_id)
        check("reactivated employee state survives restart in PostgreSQL", employee.id == employee_id and employee.active and employee.email == "edited@example.invalid")
    token = csrf(client.get("/"))
    check("logout rejects missing CSRF", client.post("/logout", data={}).status_code == 403)
    check("logout revokes authenticated session", client.post("/logout", data={"csrf_token": token}).status_code == 303 and client.get("/").status_code == 303)
    client.close()
    completed = True
finally:
    stop_server()
    server_log.close()
    with SessionLocal() as db:
        for model, ids in created.items():
            if model is Employee:
                for history in db.scalars(select(AssignmentHistory).where(AssignmentHistory.employee_id.in_(ids))).all():
                    db.delete(history)
                db.flush()
            for record_id in ids:
                record = db.get(model, record_id)
                if record:
                    db.delete(record)
            db.flush()
        db.commit()
    (artifacts / "smoke-results.json").write_text(json.dumps({"run_id": run_id, "database": "PostgreSQL", "web_port": port, "checks": results, "all_passed": completed and all(item["passed"] for item in results)}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Completed {len(results)} checks. Evidence: artifacts/smoke-results.json")
