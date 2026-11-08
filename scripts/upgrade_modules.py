"""ارتقای افزایشی؛ داده‌های قبلی و رمز مدیر حفظ می‌شوند."""
import sys
from pathlib import Path
from datetime import date
from sqlalchemy import BigInteger, inspect, select, text
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import Base, Branch, Employee, Position, SessionLocal, Unit, engine
from app.hr_models import AssignmentHistory

with engine.begin() as connection:
    columns = {col["name"] for col in inspect(connection).get_columns("admins")}
    for name, definition in {"role": "VARCHAR(20) NOT NULL DEFAULT 'admin'", "is_active": "BOOLEAN NOT NULL DEFAULT TRUE", "branch_scope_id": "INTEGER REFERENCES branches(id)", "unit_scope_id": "INTEGER REFERENCES units(id)"}.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE admins ADD COLUMN {name} {definition}"))
Base.metadata.create_all(engine)
with engine.begin() as connection:
    attendance_columns = {col["name"] for col in inspect(connection).get_columns("attendance")}
    if "presence_status" not in attendance_columns:
        connection.execute(text("ALTER TABLE attendance ADD COLUMN presence_status VARCHAR(20) NOT NULL DEFAULT 'present'"))
    connection.execute(text("ALTER TABLE attendance ALTER COLUMN clock_in DROP NOT NULL, ALTER COLUMN clock_out DROP NOT NULL"))
    history_columns = {col["name"] for col in inspect(connection).get_columns("assignment_history")}
    for column in ("branch_name", "unit_name", "position_title"):
        if column not in history_columns:
            connection.execute(text(f"ALTER TABLE assignment_history ADD COLUMN {column} VARCHAR(100) NOT NULL DEFAULT ''"))
    for table in Base.metadata.sorted_tables:
        actual = {col["name"]: col["type"] for col in inspect(connection).get_columns(table.name)}
        for column in table.columns:
            if isinstance(column.type, BigInteger) and not isinstance(actual[column.name], BigInteger):
                connection.execute(text(f'ALTER TABLE "{table.name}" ALTER COLUMN "{column.name}" TYPE BIGINT'))
with SessionLocal() as db:
    for employee in db.scalars(select(Employee)).all():
        if not db.scalar(select(AssignmentHistory.id).where(AssignmentHistory.employee_id == employee.id)):
            db.add(AssignmentHistory(employee_id=employee.id, branch_id=employee.branch_id, unit_id=employee.unit_id, position_id=employee.position_id,
                                     start_date=date.today(), reason="وضعیت فعلی هنگام آغاز ثبت تاریخچه؛ گذشتهٔ نامعلوم بازسازی نشده است.",
                                     branch_name=db.get(Branch, employee.branch_id).name, unit_name=db.get(Unit, employee.unit_id).name,
                                     position_title=db.get(Position, employee.position_id).title))
    for history in db.scalars(select(AssignmentHistory)).all():
        if not history.branch_name:
            history.branch_name = db.get(Branch, history.branch_id).name
        if not history.unit_name:
            history.unit_name = db.get(Unit, history.unit_id).name
        if not history.position_title:
            history.position_title = db.get(Position, history.position_id).title
    db.commit()
print("Module tables and current-state history are ready; existing data preserved.")
