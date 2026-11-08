"""تنظیم اتصال و جدول‌های کوچک مرحلهٔ اول."""
import os
from pathlib import Path
from datetime import date

from dotenv import load_dotenv
from sqlalchemy import Boolean, Date, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
database_url = os.getenv("DATABASE_URL", "")
if not database_url.startswith("postgresql+psycopg://"):
    raise RuntimeError("DATABASE_URL must point to PostgreSQL using the psycopg driver; see .env.example.")

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    branch_scope_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), default=None)
    unit_scope_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), default=None)


class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    seed_key: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("branch_id", "name", name="uq_unit_branch_name"),
        UniqueConstraint("id", "branch_id", name="uq_unit_id_branch"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    seed_key: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text)
    seed_key: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)


class Employee(Base):
    __tablename__ = "employees"
    # این قید، تعلق واحد به شعبهٔ انتخاب‌شده را در خود پایگاه داده هم تضمین می‌کند.
    __table_args__ = (
        ForeignKeyConstraint(["unit_id", "branch_id"], ["units.id", "units.branch_id"], name="fk_employee_unit_branch"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(32), unique=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    national_id: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str] = mapped_column(String(11))
    email: Mapped[str] = mapped_column(String(254), default="")
    hire_date: Mapped[date] = mapped_column(Date)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    unit_id: Mapped[int] = mapped_column(Integer)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))
    contract_type: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_key: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)
