"""CR-02 catalog contracts against disposable PostgreSQL and real HTTP rendering."""
from datetime import date
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app import main
from app.database import Admin, Branch, Employee, Position, Unit
from app.hr_models import AuditLog, HrRequest, Payslip
from app.security import COOKIE_NAME, new_session
from tests.support import PostgresTestCase


class CatalogPagination(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_ids = {}
        with cls.factory() as db:
            branches = [Branch(name="synthetic-catalog-" + x) for x in ("A", "B")]
            position = Position(title="synthetic-catalog-position", description="Disposable fixture")
            db.add_all(branches + [position])
            db.flush()
            units = [Unit(name="synthetic-unit", branch_id=b.id) for b in branches]
            db.add_all(units)
            db.flush()
            for role in ("admin", "hr", "viewer"):
                user = Admin(username="synthetic-catalog-" + role, display_name="آزمون", password_hash="unused",
                    role=role, is_active=True, branch_scope_id=branches[0].id if role != "admin" else None)
                db.add(user)
                db.flush()
                cls.user_ids[role] = user.id
            employees = []
            for i in range(123):
                idx = int(i >= 112)
                employees.append(Employee(employee_code=f"CAT-{i:03}", first_name="حرف%_" if i == 0 else "کارمند",
                    last_name="ساختگی", national_id="9900000000", phone="09000000000", email="test@example.invalid",
                    hire_date=date(2025, 1, 1), branch_id=branches[idx].id, unit_id=units[idx].id,
                    position_id=position.id, contract_type="دائم", active=i % 2 == 0))
            db.add_all(employees)
            db.flush()
            for employee in employees:
                db.add(HrRequest(employee_id=employee.id, kind="leave", start_date=date(2030, 1, 1),
                    end_date=date(2030, 1, 2), status="pending", description="ساختگی"))
                db.add(Payslip(employee_id=employee.id, period="2025-01", base_amount=100, overtime_amount=0,
                    benefits=0, insurance=0, tax=0, deductions=0, net_amount=100,
                    input_snapshot={"employee_name": "ساختگی"}, rule_snapshot={}, created_by=cls.user_ids["admin"]))
            db.commit()
            cls.inside_ids = [e.id for e in employees[:112]][::-1]
            cls.branch_id, cls.unit_id = branches[0].id, units[0].id

    def setUp(self):
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            # Remove only this test's synthetic session.
            token = client.cookies.get(COOKIE_NAME)
            from app import security
            with security.session_lock:
                security.sessions.pop(token, None)
            client.close()

    def client(self, role="hr"):
        client = TestClient(main.app, raise_server_exceptions=False)
        self.clients.append(client)
        if role:
            token, _ = new_session(self.user_ids[role])
            client.cookies.set(COOKIE_NAME, token)
        return client

    def catalog(self, client, **params):
        response = client.get("/employees", params=params)
        self.assertEqual(response.status_code, 200)
        return response.context["page"]

    def test_tc_04_01_bounded_ordered_pages_and_clamping(self):
        client = self.client()
        first = self.catalog(client)
        second = self.catalog(client, page=2)
        last = self.catalog(client, page=1000000)
        self.assertEqual((first.total, first.size, first.pages), (112, 50, 3))
        self.assertEqual([r.Employee.id for r in first.rows], self.inside_ids[:50])
        self.assertEqual([r.Employee.id for r in second.rows], self.inside_ids[50:100])
        self.assertEqual([r.Employee.id for r in last.rows], self.inside_ids[100:])
        self.assertEqual((last.number, last.first, last.last), (3, 101, 112))
        self.assertEqual(len(self.catalog(client, page_size=100).rows), 100)
        self.assertEqual(len(self.catalog(client, page="۲", page_size="۱۰۰").rows), 12)
        statements = []
        def capture(_conn, _cursor, sql, _params, _context, _many):
            if "FROM employees JOIN" in sql and "count(" not in sql.lower():
                statements.append(sql)
        event.listen(self.sandbox.engine, "before_cursor_execute", capture)
        try:
            self.catalog(client, page_size=1)
        finally:
            event.remove(self.sandbox.engine, "before_cursor_execute", capture)
        self.assertTrue(statements)
        self.assertTrue(all("LIMIT" in sql and "OFFSET" in sql for sql in statements))

    def test_tc_04_02_invalid_empty_and_role_boundaries(self):
        client = self.client()
        for params in ({"page": "0"}, {"page": "-1"}, {"page": "1.5"}, {"page": "1000001"},
                       {"page": "x"}, {"page": ""}, {"page_size": "0"}, {"page_size": "101"}, {"page_size": "true"}):
            with self.subTest(params=params):
                self.assertEqual(client.get("/employees", params=params).status_code, 400)
        empty = self.catalog(client, q="no-such-synthetic-name", page=99)
        self.assertEqual((empty.total, empty.number, empty.pages, empty.first, empty.last), (0, 1, 1, 0, 0))
        self.assertEqual(empty.navigation("/employees"), {"previous": None, "next": None})
        self.assertEqual(self.client(None).get("/employees", follow_redirects=False).status_code, 303)
        self.assertEqual(self.client("viewer").get("/employees").status_code, 403)
        self.assertEqual(self.catalog(client, branch="invalid").total, 0)

    def test_tc_04_03_scope_literal_filters_and_navigation(self):
        client = self.client()
        self.assertEqual(self.catalog(client, q="%").total, 1)
        self.assertEqual(self.catalog(client, q="_").total, 1)
        response = client.get("/employees", params={"q": "کارمند", "branch": self.branch_id,
            "unit": self.unit_id, "status": "active", "page_size": 10})
        self.assertEqual(response.status_code, 200)
        page = response.context["page"]
        self.assertEqual(page.total, 55)
        self.assertTrue(all(r.Employee.active and r.Employee.branch_id == self.branch_id for r in page.rows))
        params = parse_qs(urlsplit(response.context["navigation"]["next"]).query)
        self.assertEqual(params, {"q": ["کارمند"], "branch": [str(self.branch_id)], "unit": [str(self.unit_id)],
            "status": ["active"], "page_size": ["10"], "page": ["2"]})

    def test_tc_04_04_modules_and_payslips_are_bounded_without_writes(self):
        with self.factory() as db:
            before = db.scalar(select(func.count()).select_from(AuditLog))
        hr, admin = self.client(), self.client("admin")
        module = hr.get("/hr/leave", params={"page": 3, "page_size": 50})
        self.assertEqual(module.status_code, 200)
        self.assertEqual((module.context["page"].total, len(module.context["rows"])), (112, 12))
        payroll = admin.get("/payroll", params={"page": 3})
        self.assertEqual(payroll.status_code, 200)
        self.assertEqual((payroll.context["page"].total, len(payroll.context["rows"])), (123, 23))
        self.assertEqual(hr.get("/payroll").status_code, 403)
        self.assertEqual(admin.get("/hr/leave", params={"page_size": 101}).status_code, 400)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditLog)), before)
