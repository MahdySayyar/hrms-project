"""ADR-12/13: preserve export bytes/authorization/audit and normalize a real stored period key."""
import csv
import io
from datetime import date, time

from fastapi.testclient import TestClient
from sqlalchemy import event, func, insert, select

from app import main, security
from app.database import Admin, Branch, Employee, Position, Unit
from app.hr_models import Attendance, AuditLog, Payslip, Shift
from tests.support import PostgresTestCase


class ReportReads(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with cls.factory() as db:
            branches = [Branch(name="synthetic-export-" + suffix) for suffix in ("A", "B", "empty")]
            position = Position(title="=1+1", description="Synthetic formula-boundary fixture")
            shift = Shift(name="Synthetic export shift", start_time=time(8), end_time=time(16), break_minutes=0)
            db.add_all(branches + [position, shift])
            db.flush()
            units = [Unit(name="واحد, ساختگی", branch_id=b.id) for b in branches]
            db.add_all(units)
            db.flush()
            cls.user_ids = {}
            for role, branch_index in (("admin", None), ("hr", 0), ("viewer", 0), ("empty", 2)):
                user = Admin(username="synthetic-export-" + role, display_name="ساختگی", password_hash="unused", role=role if role != "empty" else "hr",
                    is_active=True, branch_scope_id=branches[branch_index].id if branch_index is not None else None)
                db.add(user)
                db.flush()
                cls.user_ids[role] = user.id
            names = ["=2+2", "+نمونه", "-نمونه", "@نمونه", "  =مقدار", 'نام,"ویژه"']
            data = []
            for i in range(1008):
                idx = int(i >= 1001)
                data.append(dict(employee_code=f"EXP-{i:04}", first_name=names[i] if i < len(names) else "نام ساختگی",
                    last_name="ساختگی", national_id="9900000000", phone="09000000000", email="synthetic@example.invalid",
                    hire_date=date(2024, 1, 1), branch_id=branches[idx].id, unit_id=units[idx].id, position_id=position.id,
                    contract_type="دائم", active=i % 2 == 0))
            db.execute(insert(Employee), data)
            employees = db.scalars(select(Employee.id).order_by(Employee.id)).all()
            slips = [dict(employee_id=ident, period="2025-01", base_amount=100, overtime_amount=0, benefits=0,
                          insurance=0, tax=0, deductions=0, net_amount=100, input_snapshot={}, rule_snapshot={},
                          created_by=cls.user_ids["admin"]) for ident in employees]
            db.execute(insert(Payslip), slips)
            for ident, amount in ((employees[0], 222), (employees[-1], 333)):
                db.add(Payslip(employee_id=ident, period="2024-02", base_amount=amount, overtime_amount=0,
                    benefits=0, insurance=0, tax=0, deductions=0, net_amount=amount, input_snapshot={}, rule_snapshot={}, created_by=cls.user_ids["admin"]))
                db.add(Attendance(employee_id=ident, work_date=date(2024, 2, 29), shift_id=shift.id,
                    worked_minutes=480, overtime_minutes=0, required_minutes=480))
            db.commit()

    def setUp(self):
        self.clients = []

    def tearDown(self):
        for client, token in self.clients:
            with security.session_lock:
                security.sessions.pop(token, None)
            client.close()

    def client(self, role="hr"):
        client = TestClient(main.app, raise_server_exceptions=False)
        token, _ = security.new_session(self.user_ids[role])
        client.cookies.set(security.COOKIE_NAME, token)
        self.clients.append((client, token))
        return client

    def audit_count(self):
        with self.factory() as db:
            return db.scalar(select(func.count()).select_from(AuditLog))

    def test_tc_11_01_csv_contract_and_exact_row_count_audit(self):
        before = self.audit_count()
        response = self.client().get("/reports/employees.csv")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(response.headers["content-disposition"], 'attachment; filename="employees.csv"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0], ["کد پرسنلی", "نام", "نام خانوادگی", "شعبه", "واحد", "سمت", "نوع قرارداد", "وضعیت"])
        self.assertEqual(rows[1], ["EXP-0000", "'=2+2", "ساختگی", "synthetic-export-A", "واحد, ساختگی", "'=1+1", "دائم", "فعال"])
        self.assertEqual([row[1] for row in rows[1:6]], ["'=2+2", "'+نمونه", "'-نمونه", "'@نمونه", "'  =مقدار"])
        self.assertEqual(rows[6][1], 'نام,"ویژه"')
        self.assertEqual((len(rows), rows[-1][0]), (1002, "EXP-1000"))
        self.assertNotIn("synthetic-export-B", response.text)
        self.assertEqual(self.audit_count(), before + 1)
        with self.factory() as db:
            audit = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()))
            self.assertEqual((audit.action, audit.actor_id, audit.details), ("export", self.user_ids["hr"], {"rows": 1001}))

    def test_tc_11_02_multiple_batches_projection_empty_scope_and_forbidden_role(self):
        queries = []
        def capture(_conn, _cursor, sql, _params, _context, _many):
            if "FROM employees JOIN" in sql:
                queries.append(sql)
        event.listen(self.sandbox.engine, "before_cursor_execute", capture)
        try:
            response = self.client("admin").get("/reports/employees.csv")
        finally:
            event.remove(self.sandbox.engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))), 1009)
        self.assertEqual(len(queries), 1)
        for private in ("national_id", "phone", "email", "seed_key", "hire_date"):
            self.assertNotIn(private, queries[0])
        empty = self.client("empty").get("/reports/employees.csv")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(len(list(csv.reader(io.StringIO(empty.content.decode("utf-8-sig"))))), 1)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(AuditLog).order_by(AuditLog.id.desc())).details, {"rows": 0})
        before = self.audit_count()
        self.assertEqual(self.client("viewer").get("/reports/employees.csv").status_code, 403)
        self.assertEqual(self.audit_count(), before)

    def test_tc_11_03_failed_export_audit_never_delivers_successful_csv(self):
        before = self.audit_count()
        def fail_audit(_conn, _cursor, sql, _params, _context, _many):
            if sql.startswith("INSERT INTO audit_log"):
                raise RuntimeError("Synthetic export-audit failure")
        event.listen(self.sandbox.engine, "before_cursor_execute", fail_audit)
        try:
            response = self.client().get("/reports/employees.csv")
        finally:
            event.remove(self.sandbox.engine, "before_cursor_execute", fail_audit)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("text/csv", response.headers.get("content-type", ""))
        self.assertNotIn("EXP-0000", response.text)
        self.assertEqual(self.audit_count(), before)

    def test_tc_11_04_equivalent_period_spellings_use_the_actual_snapshot_key(self):
        admin = self.client("admin")
        for period in ("2025-01", "۲۰۲۵-۰۱", "٢٠٢٥-٠١", " ۲۰۲۵-۰۱ "):
            with self.subTest(period=period):
                response = admin.get("/reports", params={"period": period})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["period"], "2025-01")
                self.assertEqual(response.context["payroll_total"], 100800)

    def test_tc_11_05_invalid_default_leap_month_and_role_scope_boundaries(self):
        admin = self.client("admin")
        before = self.audit_count()
        for period in ("2025-13", "2025-00", "0000-01", "2025-1", "2025-01-01", "abc", "   "):
            with self.subTest(period=period):
                self.assertEqual(admin.get("/reports", params={"period": period}).status_code, 400)
        default = admin.get("/reports", params={"period": ""})
        self.assertEqual(default.context["period"], date.today().strftime("%Y-%m"))
        leap = admin.get("/reports", params={"period": "۲۰۲۴-۰۲"})
        self.assertEqual((leap.status_code, leap.context["payroll_total"], leap.context["attendance"][0]), (200, 555, 960))
        for role in ("hr", "viewer"):
            response = self.client(role).get("/reports", params={"period": "۲۰۲۴-۰۲"})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context["payroll_total"])
            self.assertEqual(response.context["attendance"][0], 480)
            self.assertEqual(sum(row[2] for row in response.context["counts"]), 1001)
        self.assertEqual(self.audit_count(), before)
