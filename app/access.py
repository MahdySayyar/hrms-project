"""ابزارهای کوچک مشترک برای نمایش فارسی، محدودهٔ دسترسی و ثبت تغییرات."""
from datetime import date
from zoneinfo import ZoneInfo
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from .database import Admin, Branch, Employee, Position, ROOT, SessionLocal, Unit
from .hr_models import AssignmentHistory, AuditLog
from .security import current_session, require_login

ROLE_LABELS = {"admin": "مدیر منابع انسانی", "hr": "کارشناس منابع انسانی", "viewer": "مشاهده‌گر گزارش‌های کلی"}
templates = Jinja2Templates(directory=ROOT / "templates")
templates.env.filters["fa"] = lambda value: str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
templates.env.filters["money"] = lambda value: f"{int(value):,}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
templates.env.filters["localtime"] = lambda value: value.astimezone(ZoneInfo("Asia/Tehran")).strftime("%Y-%m-%d %H:%M")


def current_user(request):
    if hasattr(request.state, "user"):
        return request.state.user
    session = current_session(request)
    with SessionLocal() as db:
        user = db.get(Admin, session.admin_id) if session and session.admin_id else None
    request.state.user = user if user and user.is_active else None
    return request.state.user


def require_hr(request: Request):
    require_login(request)
    user = current_user(request)
    if not user or user.role not in ("admin", "hr"):
        raise HTTPException(403, "برای مشاهده یا تغییر اطلاعات پرسنلی دسترسی ندارید.")
    return user


def require_admin(request: Request):
    user = require_hr(request)
    if user.role != "admin":
        raise HTTPException(403, "این بخش فقط برای مدیر منابع انسانی در دسترس است.")
    return user


def scoped(statement, user, model=Employee):
    if user.branch_scope_id:
        statement = statement.where(model.branch_id == user.branch_scope_id)
    if user.unit_scope_id:
        statement = statement.where((model.id if model is Unit else model.unit_id) == user.unit_scope_id)
    return statement


def scoped_employee(db, request, employee_id, lock=False):
    user = require_hr(request)
    statement = scoped(select(Employee).where(Employee.id == employee_id), user)
    if lock:
        statement = statement.with_for_update()
    employee = db.scalar(statement)
    if not employee:
        raise HTTPException(404)
    return employee


def check_scope(request, branch_id, unit_id):
    user = require_hr(request)
    if (user.branch_scope_id and user.branch_scope_id != branch_id) or (user.unit_scope_id and user.unit_scope_id != unit_id):
        raise HTTPException(403, "شعبه یا واحد انتخاب‌شده خارج از محدودهٔ دسترسی شماست.")


def render(request: Request, name: str, status_code=200, **context):
    session = current_session(request)
    user = current_user(request)
    return templates.TemplateResponse(request=request, name=name, status_code=status_code,
        context={"csrf_token": session.csrf_token if session else "", "admin_name": user.display_name if user else "",
                 "user": user, "role_labels": ROLE_LABELS, "errors": [], **context})


def audit(db, request, action, entity, record_id=None, details=None, actor_id=None):
    user = current_user(request)
    db.add(AuditLog(actor_id=actor_id or (user.id if user else None), action=action, entity=entity, record_id=record_id, details=details or {}))


def sync_assignment(db, employee, reason):
    current = db.scalar(select(AssignmentHistory).where(AssignmentHistory.employee_id == employee.id, AssignmentHistory.end_date.is_(None)).with_for_update())
    if current and (current.branch_id, current.unit_id, current.position_id) == (employee.branch_id, employee.unit_id, employee.position_id):
        return
    if current:
        current.end_date = date.today()
        db.flush()
    db.add(AssignmentHistory(employee_id=employee.id, branch_id=employee.branch_id, unit_id=employee.unit_id,
                             position_id=employee.position_id, start_date=date.today(), reason=reason,
                             branch_name=db.get(Branch, employee.branch_id).name, unit_name=db.get(Unit, employee.unit_id).name,
                             position_title=db.get(Position, employee.position_id).title))
