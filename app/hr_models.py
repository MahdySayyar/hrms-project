"""جدول‌های ماژول‌های کاربردی؛ همه در همان PostgreSQL و برنامهٔ یکپارچه."""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (ForeignKeyConstraint(["unit_id", "branch_id"], ["units.id", "units.branch_id"]),)
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    national_id: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str] = mapped_column(String(11))
    email: Mapped[str] = mapped_column(String(254), default="")
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    unit_id: Mapped[int] = mapped_column(Integer)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))
    application_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), unique=True, default=None)
    seed_key: Mapped[str | None] = mapped_column(String(40), unique=True, default=None)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    interviewer: Mapped[str] = mapped_column(String(100))
    result: Mapped[str] = mapped_column(String(20), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    __table_args__ = (UniqueConstraint("candidate_id", "title"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    title: Mapped[str] = mapped_column(String(150))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    seed_key: Mapped[str | None] = mapped_column(String(40), unique=True, default=None)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "work_date"), CheckConstraint("worked_minutes >= 0 AND overtime_minutes >= 0"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    work_date: Mapped[date] = mapped_column(Date)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"))
    presence_status: Mapped[str] = mapped_column(String(20), default="present")
    clock_in: Mapped[time | None] = mapped_column(Time, default=None)
    clock_out: Mapped[time | None] = mapped_column(Time, default=None)
    worked_minutes: Mapped[int] = mapped_column(Integer)
    overtime_minutes: Mapped[int] = mapped_column(Integer)
    required_minutes: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")


class HrRequest(Base):
    __tablename__ = "hr_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    kind: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    leave_type: Mapped[str] = mapped_column(String(20), default="annual")
    destination: Mapped[str] = mapped_column(String(150), default="")
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PayrollRule(Base):
    __tablename__ = "payroll_rules"
    __table_args__ = (CheckConstraint("monthly_hours > 0 AND overtime_factor >= 1 AND insurance_percent BETWEEN 0 AND 100 AND tax_percent BETWEEN 0 AND 100"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_type: Mapped[str] = mapped_column(String(30), unique=True)
    calculation_mode: Mapped[str] = mapped_column(String(20))
    monthly_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    overtime_factor: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    insurance_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    notes: Mapped[str] = mapped_column(Text, default="")


class PayrollProfile(Base):
    __tablename__ = "payroll_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), unique=True)
    base_salary: Mapped[int] = mapped_column(BigInteger)
    hourly_rate: Mapped[int] = mapped_column(BigInteger, default=0)
    benefits: Mapped[int] = mapped_column(BigInteger, default=0)
    deductions: Mapped[int] = mapped_column(BigInteger, default=0)


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("employee_id", "period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    period: Mapped[str] = mapped_column(String(7))
    base_amount: Mapped[int] = mapped_column(BigInteger)
    overtime_amount: Mapped[int] = mapped_column(BigInteger)
    benefits: Mapped[int] = mapped_column(BigInteger)
    insurance: Mapped[int] = mapped_column(BigInteger)
    tax: Mapped[int] = mapped_column(BigInteger)
    deductions: Mapped[int] = mapped_column(BigInteger)
    net_amount: Mapped[int] = mapped_column(BigInteger)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    rule_snapshot: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("admins.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EmploymentContract(Base):
    __tablename__ = "employment_contracts"
    __table_args__ = (Index("uq_employee_active_contract", "employee_id", unique=True, postgresql_where=text("status = 'active'")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    contract_type: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    base_salary: Mapped[int] = mapped_column(BigInteger)
    notes: Mapped[str] = mapped_column(Text, default="")
    renewed_from_id: Mapped[int | None] = mapped_column(ForeignKey("employment_contracts.id"), default=None)
    termination_reason: Mapped[str] = mapped_column(Text, default="")


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    review_date: Mapped[date] = mapped_column(Date)
    score: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str] = mapped_column(Text)
    goals: Mapped[str] = mapped_column(Text)


class Training(Base):
    __tablename__ = "trainings"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    training_date: Mapped[date] = mapped_column(Date)
    capacity: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)


class TrainingEnrollment(Base):
    __tablename__ = "training_enrollments"
    __table_args__ = (UniqueConstraint("employee_id", "training_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    training_id: Mapped[int] = mapped_column(ForeignKey("trainings.id"))
    status: Mapped[str] = mapped_column(String(20), default="planned")
    notes: Mapped[str] = mapped_column(Text, default="")


class CareerPlan(Base):
    __tablename__ = "career_plans"
    __table_args__ = (CheckConstraint("progress BETWEEN 0 AND 100"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    target_position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))
    target_date: Mapped[date] = mapped_column(Date)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    actions: Mapped[str] = mapped_column(Text)


class AssignmentHistory(Base):
    __tablename__ = "assignment_history"
    __table_args__ = (Index("uq_employee_current_assignment", "employee_id", unique=True, postgresql_where=text("end_date IS NULL")), ForeignKeyConstraint(["unit_id", "branch_id"], ["units.id", "units.branch_id"]),)
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    unit_id: Mapped[int] = mapped_column(Integer)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    reason: Mapped[str] = mapped_column(Text)
    branch_name: Mapped[str] = mapped_column(String(100), default="")
    unit_name: Mapped[str] = mapped_column(String(100), default="")
    position_title: Mapped[str] = mapped_column(String(100), default="")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), default=None)
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(60))
    record_id: Mapped[int | None] = mapped_column(Integer, default=None)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
