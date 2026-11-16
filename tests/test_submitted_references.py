"""Synthetic PostgreSQL checks for scoped, bounded source validation on submission."""
import uuid
from datetime import date, time

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app import main, modules
from app.database import Admin, Branch, Employee, Position, Unit
from app.hr_models import AuditLog, Candidate, HrRequest, Shift, Training
from app.security import COOKIE_NAME, new_session, session_lock, sessions
from tests.support import PostgresTestCase


class SubmittedReferences(PostgresTestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:10]
        with self.factory() as db:
            branches = [Branch(name=f"ref-{suffix}-{i}") for i in range(2)]
            position = Position(title=f"ref-{suffix}", description="Synthetic")
            db.add_all(branches + [position]); db.flush()
            units = [Unit(name="synthetic", branch_id=b.id) for b in branches]
            db.add_all(units); db.flush()
            employees = [Employee(employee_code=f"REF-{suffix}-{i}", first_name="ساختگی", last_name="آزمون",
                national_id="9900000000", phone="09000000000", email="ref@example.invalid", hire_date=date(2025, 1, 1),
                branch_id=branches[int(i == 64)].id, unit_id=units[int(i == 64)].id,
                position_id=position.id, contract_type="دائم", active=True) for i in range(65)]
            user = Admin(username=f"ref-{suffix}", display_name="ساختگی", password_hash="unused",
                role="hr", is_active=True, branch_scope_id=branches[0].id, unit_scope_id=units[0].id)
            candidate = Candidate(first_name="ساختگی", last_name="آزمون", national_id="9900000000", phone="09000000000",
                email="ref@example.invalid", branch_id=branches[0].id, unit_id=units[0].id, position_id=position.id,
                application_date=date(2025, 1, 1), status="new")
            shift = Shift(name=f"ref-{suffix}", start_time=time(8), end_time=time(16), break_minutes=0)
            training = Training(title=f"ref-{suffix}", training_date=date(2030, 1, 1), capacity=2, description="Synthetic")
            db.add_all(employees + [user, candidate, shift, training]); db.commit()
            self.employee_id, self.outside_id = employees[0].id, employees[64].id
            self.user = user
            self.source_ids = {"employees": employees[0].id, "candidates": candidate.id, "branches": branches[0].id,
                "branches_all": branches[1].id, "units": units[0].id, "units_all": units[1].id,
                "positions": position.id, "shifts": shift.id, "trainings": training.id}
        self.token, self.session = new_session(user.id)
        self.client = TestClient(main.app, raise_server_exceptions=False)
        self.client.cookies.set(COOKIE_NAME, self.token)

    def tearDown(self):
        self.client.close()
        with session_lock:
            sessions.pop(self.token, None)

    def post(self, employee_id, **extra):
        return self.client.post("/hr/leave/new", data={"employee_id": employee_id, "start_date": "2030-01-01",
            "end_date": "2030-01-02", "leave_type": "annual", "description": "ساختگی",
            "csrf_token": self.session.csrf_token, **extra}, follow_redirects=False)

    def test_tc_02_10_successful_post_is_bounded_and_invalid_references_have_no_writes(self):
        loaded = []
        def loaded_employee(target, _):
            loaded.append(target.id)
        event.listen(Employee, "load", loaded_employee)
        try:
            persian_id = str(self.employee_id).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
            response = self.post(persian_id)
        finally:
            event.remove(Employee, "load", loaded_employee)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(loaded)
        self.assertLessEqual(len(loaded), 2)
        self.assertEqual(set(loaded), {self.employee_id})
        request_id = int(response.headers["location"].split("/")[3].split("?")[0])
        with self.factory() as db:
            self.assertEqual(db.get(HrRequest, request_id).employee_id, self.employee_id)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditLog).where(
                AuditLog.entity == "hr_requests", AuditLog.action == "create", AuditLog.record_id == request_id)), 1)
            before = db.scalar(select(func.count()).select_from(HrRequest))
        for value in (str(self.outside_id), "2147483647", "x", "-1", "", "9" * 100):
            with self.subTest(value=value):
                self.assertEqual(self.post(value).status_code, 400)
        self.assertEqual(self.post(self.employee_id, leave_type="invalid").status_code, 400)
        self.assertEqual(self.post(self.employee_id, csrf_token="invalid").status_code, 403)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(HrRequest)), before)

    def test_tc_02_11_all_reference_sources_preserve_scope_and_optional_empty_choices(self):
        request = Request({"type": "http", "method": "POST", "path": "/synthetic", "headers": []})
        request.state.user = self.user
        with self.factory() as db:
            for source, ident in self.source_ids.items():
                with self.subTest(source=source):
                    all_options = modules.options_for(source, db, request)
                    selected = modules.options_for(source, db, request, selected=str(ident))
                    self.assertEqual(selected, [row for row in all_options if row[0] == str(ident)])
                    self.assertEqual(len(selected), 1)
                    self.assertEqual(modules.options_for(source, db, request, selected="x"), [])
            fields = modules.fields_for(modules.MODULES["users"], db, request, submitted={
                "username": "synthetic", "display_name": "ساختگی", "password": "Synthetic-only",
                "role": "hr", "is_active": "true", "branch_scope_id": "", "unit_scope_id": ""})
            values, clean, errors = modules.parse_fields(fields, {"username": "synthetic", "display_name": "ساختگی",
                "password": "Synthetic-only", "role": "hr", "is_active": "true"})
            self.assertFalse(errors)
            self.assertIsNone(clean["branch_scope_id"])
            self.assertIsNone(clean["unit_scope_id"])
