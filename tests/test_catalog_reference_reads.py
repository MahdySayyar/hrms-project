"""ADR-11: correct authorized labels with SQL work bounded by reference kinds, not page rows."""
import re
from datetime import date, datetime, time

from fastapi.testclient import TestClient
from sqlalchemy import event

from app import main, modules, security
from app.database import Admin, Branch, Employee, Position, Unit
from app.hr_models import Attendance, Candidate, CareerPlan, HrRequest, Interview, Shift, Training, TrainingEnrollment
from tests.support import PostgresTestCase


class CatalogReferenceReads(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with cls.factory() as db:
            branches = [Branch(name="synthetic-reference-" + suffix) for suffix in ("A", "B")]
            position = Position(title="سمت <ساختگی>", description="Disposable fixture")
            shift = Shift(name="شیفت <ساختگی>", start_time=time(8), end_time=time(16), break_minutes=0)
            training = Training(title="دوره ساختگی", training_date=date(2025, 1, 1), capacity=100, description="Synthetic")
            db.add_all(branches + [position, shift, training])
            db.flush()
            units = [Unit(name="synthetic-reference-unit", branch_id=b.id) for b in branches]
            db.add_all(units)
            db.flush()
            cls.user_ids = {}
            for role in ("admin", "hr", "viewer"):
                user = Admin(username="synthetic-reference-" + role, display_name="کاربر ساختگی", password_hash="unused",
                    role=role, is_active=True, branch_scope_id=branches[0].id if role != "admin" else None,
                    unit_scope_id=units[0].id if role != "admin" else None)
                db.add(user)
                db.flush()
                cls.user_ids[role] = user.id
            employees, candidates = [], []
            for i in range(123):
                idx = int(i >= 112)
                employee = Employee(employee_code=f"REF-{i:03}", first_name="کارمند", last_name=f"ساختگی {i}",
                    national_id="9900000000", phone="09000000000", email="test@example.invalid", hire_date=date(2024, 1, 1),
                    branch_id=branches[idx].id, unit_id=units[idx].id, position_id=position.id, contract_type="دائم", active=True)
                candidate = Candidate(first_name="متقاضی", last_name=f"ساختگی {i}", national_id="9900000000", phone="09000000000",
                    branch_id=branches[idx].id, unit_id=units[idx].id, position_id=position.id, application_date=date(2025, 1, 1), status="new")
                db.add_all([employee, candidate])
                employees.append(employee)
                candidates.append(candidate)
            db.flush()
            for employee in employees:
                db.add(HrRequest(employee_id=employee.id, kind="leave", start_date=date(2030, 1, 1), end_date=date(2030, 1, 2),
                                 status="pending", description="درخواست ساختگی"))
                db.add(Attendance(employee_id=employee.id, work_date=date(2025, 1, 2), shift_id=shift.id,
                    worked_minutes=480, overtime_minutes=0, required_minutes=480))
            for day in (1, 2):
                db.add(Interview(candidate_id=candidates[111].id, scheduled_at=datetime(2025, 1, day, 10), interviewer="ساختگی", result="pending"))
            db.add(CareerPlan(employee_id=employees[111].id, target_position_id=position.id,
                              target_date=date(2030, 1, 1), progress=0, actions="ساختگی"))
            db.add(TrainingEnrollment(employee_id=employees[111].id, training_id=training.id, status="planned"))
            db.commit()
            cls.inside_employee_ids = {e.id for e in employees[:112]}
            cls.last_inside_id = employees[111].id
            cls.candidate_label = "متقاضی ساختگی 111"
            cls.shift_label = shift.name

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

    def read(self, client, path, **params):
        queries = []
        def capture(_conn, _cursor, sql, values, _context, _many):
            if sql.lstrip().upper().startswith("SELECT"):
                queries.append((sql, values))
        event.listen(self.sandbox.engine, "before_cursor_execute", capture)
        try:
            response = client.get(path, params=params, follow_redirects=False)
        finally:
            event.remove(self.sandbox.engine, "before_cursor_execute", capture)
        return response, queries

    def test_tc_04_05_reference_cost_is_bounded_at_all_page_sizes(self):
        client = self.client()
        for size in (1, 50, 100):
            with self.subTest(size=size):
                response, queries = self.read(client, "/hr/attendance", page_size=size)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context["rows"]), size)
                self.assertEqual(len(queries), 5)  # auth/count/page + one employee and one shift projection
                self.assertEqual(response.context["rows"][0]["cells"][0], "کارمند ساختگی 111")
                self.assertEqual(response.context["rows"][0]["cells"][3], self.shift_label)
                references = [sql for sql, _ in queries if re.search(r"FROM (employees|shifts)\s", sql)]
                self.assertEqual(len(references), 2)
                self.assertTrue(all(" IN (" in sql for sql in references))
                self.assertTrue(all(private not in "\n".join(references) for private in ("national_id", "phone", "email", "password_hash")))

    def test_tc_04_06_only_page_references_are_read_and_next_request_is_fresh(self):
        client = self.client()
        response, queries = self.read(client, "/hr/leave", page_size=50)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(queries), 4)
        reference_queries = [(sql, values) for sql, values in queries if re.search(r"FROM employees\s", sql)]
        self.assertEqual(len(reference_queries), 1)
        sql, values = reference_queries[0]
        self.assertIn(" IN (", sql)
        # SQL concatenation also binds the separating space; only integer values are reference IDs.
        selected = {value for value in values.values() if isinstance(value, int)}
        page_ids = {row.employee_id for row in response.context["page"].rows}
        self.assertEqual(selected, page_ids)
        self.assertTrue(selected <= self.inside_employee_ids)
        with self.factory() as db:
            employee = db.get(Employee, self.last_inside_id)
            original = employee.last_name
            employee.last_name = "نام تازه ساختگی"
            db.commit()
        try:
            fresh = client.get("/hr/leave", params={"page_size": 1})
            self.assertEqual(fresh.context["rows"][0]["cells"][0], "کارمند نام تازه ساختگی")
        finally:
            with self.factory() as db:
                db.get(Employee, self.last_inside_id).last_name = original
                db.commit()

    def test_tc_04_07_other_catalogs_empty_pages_and_escaping(self):
        client = self.client()
        for path, count in (("/hr/candidates", 4), ("/hr/interviews", 4), ("/hr/career", 5), ("/hr/enrollments", 5)):
            with self.subTest(path=path):
                response, queries = self.read(client, path, page_size=100)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(queries), count)
        interviews = client.get("/hr/interviews").context["rows"]
        self.assertEqual([row["cells"][0] for row in interviews], [self.candidate_label, self.candidate_label])
        escaped = client.get("/hr/candidates").text
        self.assertIn("&lt;ساختگی&gt;", escaped)
        self.assertNotIn("سمت <ساختگی>", escaped)
        empty, queries = self.read(client, "/hr/candidates", q="no-such-synthetic-name", page=99)
        self.assertEqual((empty.status_code, empty.context["page"].total), (200, 0))
        self.assertEqual(len(queries), 3)
        invalid, queries = self.read(client, "/hr/leave", page_size=101)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(len(queries), 1)  # Authorize, then reject before any catalog query.

    def test_tc_04_08_optional_scopes_roles_and_reference_fallbacks(self):
        admin = self.client("admin")
        response = admin.get("/hr/users")
        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.context["rows"] if r["id"] == self.user_ids["admin"])
        self.assertEqual(row["cells"][3:5], ["کل سازمان", "همهٔ واحدهای محدوده"])
        for client, path in ((self.client("viewer"), "/hr/leave"), (self.client(), "/hr/users")):
            denied, queries = self.read(client, path)
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(len(queries), 1)
        with self.factory() as db:
            self.assertEqual(modules.display_value(db, "leave", "employee_id", 2147483647, references={Employee: {}}), "ثبت نشده")
            self.assertEqual(modules.display_value(db, "users", "branch_scope_id", None, references={}), "کل سازمان")
            records = [dict(employee_id=self.last_inside_id, candidate_id=112, branch_id=1, unit_id=1,
                            position_id=1, shift_id=1, training_id=1, reviewed_by=self.user_ids["admin"])]
            from types import SimpleNamespace
            labels = modules.reference_labels(db, [SimpleNamespace(**record) for record in records], records[0])
            self.assertEqual(set(labels), {Employee, Candidate, Branch, Unit, Position, Shift, Training, Admin})
            self.assertTrue(all(len(mapping) == 1 for mapping in labels.values()))
