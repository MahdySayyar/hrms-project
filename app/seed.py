"""اجرای تکرارپذیر: python -m app.seed؛ بدون پاک کردن اطلاعات موجود."""
import os
from datetime import date

from sqlalchemy import func, select

from .database import Admin, Base, Branch, Employee, Position, SessionLocal, Unit, engine
from .security import hash_password
from . import hr_models


def seed() -> None:
    username = os.getenv("ADMIN_USERNAME", "hradmin").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin = db.scalar(select(Admin).where(Admin.username == username))
        if not admin:
            if db.scalar(select(func.count()).select_from(Admin)):
                raise RuntimeError("An administrator already exists. Keep its original ADMIN_USERNAME.")
            if len(password) < 12 or password.startswith("CHANGE_ME"):
                raise RuntimeError("Set a real ADMIN_PASSWORD of at least 12 characters in .env before seeding.")
            db.add(Admin(username=username, display_name=os.getenv("ADMIN_DISPLAY_NAME", "مدیر منابع انسانی"), password_hash=hash_password(password)))

        units = {}
        # کلیدهای نمونه باعث می‌شوند ویرایش نام‌ها هم موجب ایجاد رکورد تکراری نشود.
        for branch_index, (branch_name, unit_names) in enumerate([("شعبهٔ نمونه تهران", ["اداری", "فناوری اطلاعات"]), ("شعبهٔ نمونه شیراز", ["پشتیبانی", "فروش"])], start=1):
            branch_key = f"demo-branch-{branch_index}"
            branch = db.scalar(select(Branch).where(Branch.seed_key == branch_key))
            if not branch:
                branch = db.scalar(select(Branch).where(Branch.name == branch_name))
            if not branch:
                branch = Branch(name=branch_name)
                db.add(branch)
            branch.seed_key = branch_key
            db.flush()
            for unit_index, unit_name in enumerate(unit_names, start=1):
                unit_key = f"demo-unit-{branch_index}-{unit_index}"
                unit = db.scalar(select(Unit).where(Unit.seed_key == unit_key))
                if not unit:
                    unit = db.scalar(select(Unit).where(Unit.branch_id == branch.id, Unit.name == unit_name))
                if not unit:
                    unit = Unit(name=unit_name, branch_id=branch.id)
                    db.add(unit)
                unit.seed_key = unit_key
                db.flush()
                units[(branch_name, unit_name)] = unit

        positions = []
        for position_index, (title, description) in enumerate([("کارشناس اداری", "پیگیری مکاتبات و امور اداری سازمان."), ("کارشناس فناوری اطلاعات", "پشتیبانی سامانه‌ها و تجهیزات رایانه‌ای."), ("کارشناس پشتیبانی", "پاسخ‌گویی به درخواست‌ها و پیگیری خدمات."), ("کارشناس فروش", "ارتباط با مشتریان و ثبت درخواست‌های فروش.")], start=1):
            position_key = f"demo-position-{position_index}"
            position = db.scalar(select(Position).where(Position.seed_key == position_key))
            if not position:
                position = db.scalar(select(Position).where(Position.title == title))
            if not position:
                position = Position(title=title, description=description)
                db.add(position)
            position.seed_key = position_key
            db.flush()
            positions.append(position)

        names = [("سارا", "نمونه"), ("رضا", "آزمایشی"), ("مریم", "نمونه"), ("علی", "آزمایشی"), ("نرگس", "نمونه"), ("امیر", "آزمایشی"), ("لیلا", "نمونه"), ("حامد", "آزمایشی"), ("الهام", "نمونه"), ("کیان", "آزمایشی")]
        unit_list = list(units.values())
        for index, (first_name, last_name) in enumerate(names, start=1):
            code = f"DEMO-{index:03d}"
            employee_key = f"demo-employee-{index}"
            if db.scalar(select(Employee.id).where(Employee.seed_key == employee_key)):
                continue
            existing = db.scalar(select(Employee).where(Employee.employee_code == code))
            if existing:
                existing.seed_key = employee_key
                continue
            unit = unit_list[(index - 1) % len(unit_list)]
            db.add(Employee(employee_code=code, first_name=first_name, last_name=last_name,
                            national_id=f"990000{index:04d}", phone=f"0900000{index:04d}",
                            email=f"employee{index}@example.invalid", hire_date=date(2025, 1, min(index, 28)),
                            branch_id=unit.branch_id, unit_id=unit.id,
                            position_id=positions[(index - 1) % len(positions)].id,
                            contract_type=["دائم", "مدت‌معین", "پیمانکاری"][(index - 1) % 3], active=index != 10, seed_key=employee_key))
        db.commit()
        from .hr_models import Candidate, Shift
        from datetime import time
        for index, (name, begin, end) in enumerate([("شیفت نمونه روز", time(8), time(16)), ("شیفت نمونه شب", time(22), time(6))], start=1):
            key = f"demo-shift-{index}"
            if not db.scalar(select(Shift.id).where(Shift.seed_key == key)):
                db.add(Shift(name=name, start_time=begin, end_time=end, break_minutes=0, seed_key=key))
        sample_units = list(units.values())
        for index, (first, last) in enumerate([("متقاضی", "نمونه یک"), ("متقاضی", "نمونه دو")], start=1):
            key = f"demo-candidate-{index}"
            if not db.scalar(select(Candidate.id).where(Candidate.seed_key == key)):
                unit = sample_units[index - 1]
                db.add(Candidate(first_name=first, last_name=last, national_id=f"990001{index:04d}", phone=f"0900010{index:04d}", email=f"candidate{index}@example.invalid",
                    branch_id=unit.branch_id, unit_id=unit.id, position_id=positions[index - 1].id, application_date=date.today(), status="new", notes="متقاضی ساختگی برای تمرین فرایند استخدام", seed_key=key))
        db.commit()
        counts = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in [Branch, Unit, Position, Employee, Admin]}
        print("Initialization complete:", counts)
        print("Existing records and administrator passwords were preserved.")


if __name__ == "__main__":
    seed()
