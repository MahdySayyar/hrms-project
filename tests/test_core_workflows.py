"""UC-01, UC-02, UC-03: real PostgreSQL + FastAPI HTTP contracts, including failures."""
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app import main
from app.database import Admin, Branch, Employee, Position, Unit
from app.hr_models import Attendance, AuditLog, HrRequest, PayrollProfile, PayrollRule, Payslip, Shift
from app.security import COOKIE_NAME, hash_password
from tests.support import PostgresTestCase


class CoreWorkflows(PostgresTestCase):
    password = "Synthetic-Core-Test-Password-Only"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.clients = []
        self.credentials = {}
        with self.factory() as db:
            branches = [Branch(name=f"test-{suffix}-{x}") for x in ("A", "B")]
            db.add_all(branches)
            db.flush()
            units = [Unit(name="synthetic-unit", branch_id=x.id) for x in branches]
            position = Position(title=f"test-position-{suffix}", description="Synthetic test position")
            db.add_all(units + [position])
            db.flush()
            employees = [Employee(employee_code=f"TEST-{suffix}-{i}", first_name="آزمون", last_name="ساختگی",
                national_id="9900000000", phone="09000000000", email="test@example.invalid", hire_date=date(2025, 1, 1),
                branch_id=branches[i].id, unit_id=units[i].id, position_id=position.id, contract_type="آزمایشی", active=True) for i in range(2)]
            db.add_all(employees)
            for role in ("admin", "hr", "viewer"):
                user = Admin(username=f"test_{role}_{suffix}", display_name="کاربر ساختگی آزمون", password_hash=self.password_hash,
                    role=role, is_active=True, branch_scope_id=branches[0].id if role != "admin" else None,
                    unit_scope_id=units[0].id if role == "hr" else None)
                db.add(user)
                db.flush()
                self.credentials[role] = (user.username, user.id)
            db.commit()
            self.employee_id, self.outside_id = [x.id for x in employees]

    def tearDown(self):
        for client in self.clients:
            client.close()

    def client(self, role=None):
        client = TestClient(main.app, raise_server_exceptions=False)
        self.clients.append(client)
        if role:
            page = client.get("/login")
            token = self.csrf(page.text)
            response = client.post("/login", data={"username": self.credentials[role][0], "password": self.password,
                "csrf_token": token}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
        return client

    @staticmethod
    def csrf(html):
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        if not match:
            raise AssertionError("The rendered form has no CSRF token.")
        return match.group(1)

    def post(self, client, path, data):
        token = self.csrf(client.get("/").text)
        return client.post(path, data={**data, "csrf_token": token}, follow_redirects=False)

    def request(self, client, kind="leave", start="2030-01-01", end="2030-01-02", employee=None):
        payload = {"employee_id": str(employee or self.employee_id), "start_date": start, "end_date": end,
                   "leave_type": "annual", "destination": "مقصد ساختگی", "description": "درخواست ساختگی آزمون"}
        response = self.post(client, f"/hr/{kind}/new", payload)
        self.assertEqual(response.status_code, 303)
        return int(response.headers["location"].split("/")[3].split("?")[0])

    def audit_count(self, request_id):
        with self.factory() as db:
            return db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity == "hr_requests",
                AuditLog.record_id == request_id, AuditLog.action == "review"))

    def payroll_fixture(self, mode="monthly", deductions=1_000_000, hourly_rate=300_000):
        with self.factory() as db:
            rule = db.scalar(select(PayrollRule).where(PayrollRule.contract_type == "آزمایشی"))
            if not rule:
                rule = PayrollRule(contract_type="آزمایشی")
                db.add(rule)
            rule.calculation_mode, rule.monthly_hours, rule.overtime_factor = mode, Decimal("200"), Decimal("1.5")
            rule.insurance_percent, rule.tax_percent = Decimal("5"), Decimal("10")
            profile = PayrollProfile(employee_id=self.employee_id, base_salary=60_000_000, hourly_rate=hourly_rate,
                                     benefits=5_000_000, deductions=deductions)
            shift = Shift(name="test-shift-" + uuid.uuid4().hex, start_time=time(8), end_time=time(16), break_minutes=0)
            db.add_all([profile, shift])
            db.flush()
            db.add(Attendance(employee_id=self.employee_id, work_date=date(2025, 2, 6), shift_id=shift.id,
                presence_status="present", clock_in=time(8), clock_out=time(18), worked_minutes=600,
                overtime_minutes=120, required_minutes=480))
            db.commit()
            return rule.id, profile.id

    def test_tc_01_01_login_logout_csrf_and_rotation(self):
        client = self.client()
        self.assertEqual(client.get("/employees", follow_redirects=False).status_code, 303)
        page = client.get("/login")
        old_cookie = client.cookies.get(COOKIE_NAME)
        credentials = {"username": self.credentials["admin"][0], "password": self.password}
        self.assertEqual(client.post("/login", data=credentials).status_code, 403)
        token = self.csrf(page.text)
        response = client.post("/login", data={**credentials, "password": "wrong", "csrf_token": token})
        self.assertEqual(response.status_code, 401)
        response = client.post("/login", data={**credentials, "csrf_token": token}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertNotEqual(old_cookie, client.cookies.get(COOKIE_NAME))
        self.assertEqual(client.get("/employees").status_code, 200)
        response = self.post(client, "/logout", {})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(client.get("/employees", follow_redirects=False).status_code, 303)

    def test_tc_01_02_roles_and_branch_scope(self):
        hr, viewer = self.client("hr"), self.client("viewer")
        self.assertEqual(hr.get(f"/employees/{self.outside_id}").status_code, 404)
        self.assertEqual(hr.get(f"/employees/{self.employee_id}").status_code, 200)
        for path in ("/payroll", "/audit", "/hr/users"):
            self.assertEqual(hr.get(path).status_code, 403)
        self.assertEqual(viewer.get("/reports").status_code, 200)
        self.assertEqual(viewer.get("/employees").status_code, 403)
        self.assertEqual(viewer.get("/reports/employees.csv").status_code, 403)
        self.assertEqual(self.post(hr, "/requests/999999/review", {"decision": "approved"}).status_code, 403)

    def test_tc_01_03_inactive_account_is_rejected(self):
        client = self.client("hr")
        with self.factory() as db:
            db.get(Admin, self.credentials["hr"][1]).is_active = False
            db.commit()
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)

    def test_tc_02_01_creation_and_invalid_date_range(self):
        client = self.client("hr")
        response = self.post(client, "/hr/leave/new", {"employee_id": str(self.employee_id), "start_date": "2030-01-02",
            "end_date": "2030-01-01", "leave_type": "annual", "description": "ساختگی"})
        self.assertEqual(response.status_code, 400)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(HrRequest).where(HrRequest.employee_id == self.employee_id)), 0)
        request_id = self.request(client)
        with self.factory() as db:
            self.assertEqual(db.get(HrRequest, request_id).status, "pending")

    def test_tc_02_02_approval_and_atomic_audit(self):
        client = self.client("admin")
        request_id = self.request(client)
        response = self.post(client, f"/requests/{request_id}/review", {"decision": "approved", "review_notes": "تأیید ساختگی"})
        self.assertEqual(response.status_code, 303)
        with self.factory() as db:
            item = db.get(HrRequest, request_id)
            self.assertEqual(item.status, "approved")
            self.assertEqual(item.reviewed_by, self.credentials["admin"][1])
            self.assertIsNotNone(item.reviewed_at)
        self.assertEqual(self.audit_count(request_id), 1)

    def test_tc_02_03_rejection_requires_reason(self):
        client = self.client("admin")
        request_id = self.request(client)
        self.assertEqual(self.post(client, f"/requests/{request_id}/review", {"decision": "rejected", "review_notes": " "}).status_code, 400)
        self.assertEqual(self.audit_count(request_id), 0)
        self.assertEqual(self.post(client, f"/requests/{request_id}/review", {"decision": "rejected", "review_notes": "دلیل ساختگی"}).status_code, 303)

    def test_tc_02_04_same_decision_is_idempotent(self):
        client = self.client("admin")
        request_id = self.request(client)
        self.post(client, f"/requests/{request_id}/review", {"decision": "approved", "review_notes": "اول"})
        response = self.post(client, f"/requests/{request_id}/review", {"decision": "approved", "review_notes": "دوم"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.audit_count(request_id), 1)
        with self.factory() as db:
            self.assertEqual(db.get(HrRequest, request_id).review_notes, "اول")

    def test_tc_02_05_conflicting_final_decision_is_explicitly_rejected(self):
        client = self.client("admin")
        request_id = self.request(client)
        self.post(client, f"/requests/{request_id}/review", {"decision": "approved", "review_notes": "اول"})
        response = self.post(client, f"/requests/{request_id}/review", {"decision": "rejected", "review_notes": "تغییر متناقض"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.audit_count(request_id), 1)
        with self.factory() as db:
            self.assertEqual(db.get(HrRequest, request_id).status, "approved")

    def test_tc_02_06_overlap_includes_shared_boundary_day(self):
        client = self.client("admin")
        first = self.request(client)
        second = self.request(client, "travel", "2030-01-02", "2030-01-03")
        self.post(client, f"/requests/{first}/review", {"decision": "approved"})
        self.assertEqual(self.post(client, f"/requests/{second}/review", {"decision": "approved"}).status_code, 400)
        self.assertEqual(self.audit_count(second), 0)
        with self.factory() as db:
            self.assertEqual(db.get(HrRequest, second).status, "pending")

    def test_tc_02_07_parallel_overlapping_approvals_have_one_winner(self):
        client = self.client("admin")
        ids = [self.request(client), self.request(client, "travel")]
        token = self.csrf(client.get("/").text)
        def approve(request_id):
            return client.post(f"/requests/{request_id}/review", data={"decision": "approved", "csrf_token": token}, follow_redirects=False).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(approve, ids))
        self.assertEqual(sorted(statuses), [303, 400])
        self.assertEqual(sum(self.audit_count(x) for x in ids), 1)

    def test_tc_02_08_failed_audit_rolls_back_decision(self):
        client = self.client("admin")
        request_id = self.request(client)
        def fail_audit(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().lower().startswith("insert into audit_log"):
                raise RuntimeError("Simulated audit write failure in disposable test schema")
        event.listen(self.sandbox.engine, "before_cursor_execute", fail_audit)
        try:
            self.assertEqual(self.post(client, f"/requests/{request_id}/review", {"decision": "approved"}).status_code, 500)
        finally:
            event.remove(self.sandbox.engine, "before_cursor_execute", fail_audit)
        with self.factory() as db:
            self.assertEqual(db.get(HrRequest, request_id).status, "pending")
        self.assertEqual(self.audit_count(request_id), 0)

    def test_tc_02_09_missing_invalid_and_notes_boundary(self):
        client = self.client("admin")
        self.assertEqual(self.post(client, "/requests/999999/review", {"decision": "approved"}).status_code, 404)
        request_id = self.request(client)
        self.assertEqual(self.post(client, f"/requests/{request_id}/review", {"decision": "pending"}).status_code, 400)
        self.assertEqual(self.post(client, f"/requests/{request_id}/review", {"decision": "approved", "review_notes": "x" * 3001}).status_code, 400)
        self.assertEqual(self.post(client, f"/requests/{request_id}/review", {"decision": "approved", "review_notes": "x" * 3000}).status_code, 303)

    def test_tc_03_01_monthly_formula_and_immutable_retry(self):
        client = self.client("admin")
        rule_id, profile_id = self.payroll_fixture()
        payload = {"employee_id": str(self.employee_id), "period": "2025-02"}
        response = self.post(client, "/payroll/calculate", payload)
        self.assertEqual(response.status_code, 303)
        location = response.headers["location"]
        payslip_id = int(location.split("/")[2])
        with self.factory() as db:
            item = db.get(Payslip, payslip_id)
            self.assertEqual((item.overtime_amount, item.net_amount), (900_000, 55_015_000))
            before = (dict(item.input_snapshot), dict(item.rule_snapshot))
            db.get(PayrollRule, rule_id).overtime_factor = Decimal("2")
            db.get(PayrollProfile, profile_id).base_salary = 70_000_000
            db.commit()
        self.assertEqual(self.post(client, "/payroll/calculate", payload).headers["location"], location)
        with self.factory() as db:
            item = db.get(Payslip, payslip_id)
            self.assertEqual((item.input_snapshot, item.rule_snapshot), before)
            self.assertEqual(db.scalar(select(func.count()).select_from(Payslip).where(Payslip.employee_id == self.employee_id)), 1)

    def test_tc_03_02_hourly_formula_counts_overtime_once(self):
        client = self.client("admin")
        self.payroll_fixture(mode="hourly")
        response = self.post(client, "/payroll/calculate", {"employee_id": str(self.employee_id), "period": "2025-02"})
        self.assertEqual(response.status_code, 303)
        with self.factory() as db:
            item = db.get(Payslip, int(response.headers["location"].split("/")[2]))
            self.assertEqual((item.base_amount, item.overtime_amount, item.net_amount), (2_400_000, 900_000, 6_055_000))

    def test_tc_03_03_invalid_period_and_missing_profile(self):
        client = self.client("admin")
        for period in ("2025-13", "not-a-month", "2025-02"):
            self.assertEqual(self.post(client, "/payroll/calculate", {"employee_id": str(self.employee_id), "period": period}).status_code, 400)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Payslip).where(Payslip.employee_id == self.employee_id)), 0)

    def test_tc_03_04_zero_hourly_rate_is_rejected(self):
        client = self.client("admin")
        self.payroll_fixture(mode="hourly", hourly_rate=0)
        self.assertEqual(self.post(client, "/payroll/calculate", {"employee_id": str(self.employee_id), "period": "2025-02"}).status_code, 400)

    def test_tc_03_05_negative_net_has_no_payslip(self):
        client = self.client("admin")
        self.payroll_fixture(deductions=1_000_000_000)
        self.assertEqual(self.post(client, "/payroll/calculate", {"employee_id": str(self.employee_id), "period": "2025-02"}).status_code, 400)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Payslip).where(Payslip.employee_id == self.employee_id)), 0)
