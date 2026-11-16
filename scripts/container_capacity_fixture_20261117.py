"""Synthetic capacity schema bootstrap; only inside a uniquely marked Docker lab."""
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, "/srv/hrms")
import entrypoint
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema


def configure(create=False):
    marker = os.environ.get("INSTANCE_ID", "")
    schema = os.environ.get("HRMS_CAPACITY_SCHEMA", "")
    if not marker.startswith("hrms-capacity-") or not re.fullmatch(r"hrms_test_[0-9a-f]{32}", schema):
        raise RuntimeError("Only a uniquely marked disposable capacity lab is allowed")
    entrypoint.configure()
    url = make_url(os.environ["DATABASE_URL"])
    if create:
        owner = create_engine(url)
        try:
            with owner.begin() as connection:
                connection.execute(CreateSchema(schema))
        finally:
            owner.dispose()
    os.environ["DATABASE_URL"] = url.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(hide_password=False)


def seed(worker=False):
    configure(create=not worker)
    if worker:
        os.environ.pop("ADMIN_PASSWORD", None)
        os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
    from app.database import Admin, Base, Branch, Employee, Position, SessionLocal, Unit, engine
    from app import hr_models
    from app.security import hash_password
    Base.metadata.create_all(engine)
    users = int(os.environ["HRMS_CAPACITY_USERS"])
    employees = int(os.environ["HRMS_CAPACITY_EMPLOYEES"])
    if not 1 <= users <= 500 or not users < employees <= 10000:
        raise RuntimeError("Invalid synthetic fixture bounds")
    password_hash = hash_password(os.environ["ADMIN_PASSWORD"])
    with SessionLocal.begin() as db:
        branch = Branch(name="شعبهٔ ساختگی آزمون ظرفیت")
        position = Position(title="سمت ساختگی آزمون ظرفیت", description="Synthetic lab only")
        db.add_all([branch, position])
        db.flush()
        unit = Unit(name="واحد ساختگی", branch_id=branch.id)
        db.add(unit)
        db.flush()
        db.execute(insert(Admin), [{"username": f"capacity-{i:04d}", "display_name": f"حساب آزمایش {i:04d}",
            "password_hash": password_hash, "role": "hr", "is_active": True} for i in range(users + 1)])
        db.execute(insert(Employee), [{"employee_code": f"CAP-{i:06d}", "first_name": "آزمون", "last_name": "ساختگی",
            "national_id": "9900000000", "phone": "09000000000", "email": "capacity@example.invalid",
            "hire_date": date(2025, 1, 1), "branch_id": branch.id, "unit_id": unit.id, "position_id": position.id,
            "contract_type": "دائم", "active": True} for i in range(1, employees + 1)])
    os.environ.pop("ADMIN_PASSWORD", None)
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


def inspect():
    configure()
    from app.database import Admin, SessionLocal
    from app.hr_models import AuditLog
    users = int(os.environ["HRMS_CAPACITY_USERS"])
    with SessionLocal() as db:
        counts = list(db.execute(select(Admin.username, func.count(AuditLog.id)).join(AuditLog, AuditLog.actor_id == Admin.id)
            .where(AuditLog.action == "login", Admin.username != f"capacity-{users:04d}").group_by(Admin.username)))
        print(json.dumps({"distinct_login_accounts": len(counts), "each_account_one_login_audit": len(counts) == users and all(n == 1 for _, n in counts),
            "status_audits": db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "status", AuditLog.entity == "employees"))}))


if __name__ == "__main__":
    inspect() if "--inspect" in sys.argv else seed(worker="--worker" in sys.argv)
