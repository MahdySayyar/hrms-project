"""مسیرهای مستقیم ماژول‌ها؛ برنامه همچنان یک مونولیت و یک PostgreSQL است."""
import calendar
import csv
import io
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from .access import (audit, check_scope, current_user, render, require_admin, require_hr, scoped, scoped_employee, sync_assignment)
from .database import Admin, Branch, Employee, Position, SessionLocal, Unit
from .hr_models import (AssignmentHistory, Attendance, AuditLog, Candidate, CareerPlan, EmploymentContract, Evaluation, HrRequest, Interview,
                        OnboardingTask, PayrollProfile, PayrollRule, Payslip, Shift, Training, TrainingEnrollment, utc_now)
from .module_forms import (CANDIDATE_STATES, CONTRACT_STATES, CONTRACT_TYPES, INTERVIEW_RESULTS, LABELS, MODULES, REQUEST_STATES, DATE, EMPLOYEE, field, money, pick)
from .security import check_csrf, hash_password, require_login

router = APIRouter()
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalized(value):
    return str(value or "").strip().translate(DIGITS)


def redirect(path):
    return RedirectResponse(path, status_code=303)


async def browser_form(request: Request):
    require_login(request)
    form = dict(await request.form())
    check_csrf(request, form)
    return form


def config_for(module, request):
    if module not in MODULES:
        raise HTTPException(404)
    config = MODULES[module]
    (require_admin if config.get("admin_only") else require_hr)(request)
    return config


def candidate_for(db, request, candidate_id, lock=False):
    query = scoped(select(Candidate).where(Candidate.id == candidate_id), require_hr(request), Candidate)
    candidate = db.scalar(query.with_for_update() if lock else query)
    if not candidate:
        raise HTTPException(404)
    return candidate


def options_for(source, db, request):
    user = current_user(request)
    if source == "employees":
        return [(str(row.id), f"{row.first_name} {row.last_name} · {row.employee_code}") for row in db.scalars(scoped(select(Employee), user).order_by(Employee.id)).all()]
    if source == "candidates":
        return [(str(row.id), f"{row.first_name} {row.last_name}") for row in db.scalars(scoped(select(Candidate), user, Candidate).where(Candidate.employee_id.is_(None)).order_by(Candidate.id)).all()]
    if source in ("branches", "branches_all"):
        query = select(Branch)
        if source == "branches" and user.branch_scope_id:
            query = query.where(Branch.id == user.branch_scope_id)
        return [(str(row.id), row.name) for row in db.scalars(query.order_by(Branch.id)).all()]
    if source in ("units", "units_all"):
        query = scoped(select(Unit), user, Unit) if source == "units" else select(Unit)
        names = {row.id: row.name for row in db.scalars(select(Branch)).all()}
        return [(str(row.id), f"{row.name} · {names[row.branch_id]}") for row in db.scalars(query.order_by(Unit.id)).all()]
    model, label = {"positions": (Position, "title"), "shifts": (Shift, "name"), "trainings": (Training, "title")}[source]
    return [(str(row.id), getattr(row, label)) for row in db.scalars(select(model).order_by(model.id)).all()]


def fields_for(config, db, request):
    fields = []
    for original in config["fields"]:
        item = original.copy()
        if item.get("source"):
            item["options"] = options_for(item["source"], db, request)
        elif item.get("choices"):
            item["options"] = list(item["choices"].items())
        fields.append(item)
    return fields


def parse_fields(fields, form):
    values, clean, errors = {}, {}, []
    for item in fields:
        name, kind = item["name"], item["kind"]
        value = str(form.get(name, "")) if kind == "password" else normalized(form.get(name, item.get("default", "")))
        values[name] = "" if kind == "password" else value
        if not value:
            if item["required"]:
                errors.append(f"{item['label']} را وارد کنید.")
            clean[name] = None if kind in ("date", "time", "select", "number", "decimal") else ""
            continue
        try:
            if kind == "number":
                if not re.fullmatch(r"[0-9]{1,16}", value):
                    raise ValueError()
                parsed = int(value)
            elif kind == "decimal":
                if not re.fullmatch(r"[0-9]{1,6}(\.[0-9]{1,2})?", value):
                    raise ValueError()
                parsed = Decimal(value)
            elif kind == "date":
                parsed = date.fromisoformat(value)
            elif kind == "time":
                parsed = time.fromisoformat(value)
            elif kind == "datetime-local":
                parsed = datetime.fromisoformat(value)
            elif kind == "select":
                if value not in {str(key) for key, _ in item["options"]}:
                    raise ValueError()
                parsed = int(value) if item.get("source") else value
            else:
                parsed = value
                if len(value) > item.get("maximum_length", 3000):
                    raise ValueError()
                if kind == "email" and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
                    raise ValueError()
            if kind in ("number", "decimal") and not item.get("minimum", 0) <= parsed <= item.get("maximum", 1_000_000_000):
                raise ValueError()
            clean[name] = parsed
        except (ValueError, InvalidOperation):
            errors.append(f"مقدار {item['label']} معتبر نیست.")
    return values, clean, errors


def form_page(request, db, module, values=None, errors=None, record=None, status_code=200, custom_fields=None, custom_title=None, action=None, description=None):
    config = MODULES[module]
    fields = custom_fields or fields_for(config, db, request)
    return render(request, "module_form.html", status_code, title=custom_title or ("ویرایش " if record else "افزودن ") + config["singular"],
                  fields=fields, values=values or {}, errors=errors or [], module=module, record=record,
                  action=action or (f"/hr/{module}/{record.id}/edit" if record else f"/hr/{module}/new"),
                  back=f"/hr/{module}/{record.id}" if record else f"/hr/{module}", description=description or config.get("description", ""))


def query_for(module, request):
    config = config_for(module, request)
    model = config["model"]
    query = select(model)
    user = current_user(request)
    if model is Candidate:
        query = scoped(query, user, Candidate)
    elif model is Interview:
        query = scoped(query.join(Candidate, Interview.candidate_id == Candidate.id), user, Candidate)
    elif hasattr(model, "employee_id"):
        query = scoped(query.join(Employee, model.employee_id == Employee.id), user)
    if model is HrRequest:
        query = query.where(HrRequest.kind == module)
    return query


def record_for(db, request, module, record_id, lock=False):
    query = query_for(module, request).where(MODULES[module]["model"].id == record_id)
    record = db.scalar(query.with_for_update(of=MODULES[module]["model"]) if lock else query)
    if not record:
        raise HTTPException(404)
    return record


def display_value(db, module, key, value):
    if value is None or value == "":
        if key == "branch_scope_id":
            return "کل سازمان"
        if key == "unit_scope_id":
            return "همهٔ واحدهای محدوده"
        return "ثبت نشده"
    models = {"employee_id": Employee, "candidate_id": Candidate, "branch_id": Branch, "unit_id": Unit, "position_id": Position,
              "target_position_id": Position, "shift_id": Shift, "training_id": Training, "branch_scope_id": Branch, "unit_scope_id": Unit, "reviewed_by": Admin}
    if key in models:
        row = db.get(models[key], value)
        if row is None:
            return "ثبت نشده"
        if isinstance(row, (Employee, Candidate)):
            return f"{row.first_name} {row.last_name}"
        return getattr(row, "title", None) or getattr(row, "name", None) or row.display_name
    if key == "status":
        return (CANDIDATE_STATES if module == "candidates" else CONTRACT_STATES if module == "contracts" else REQUEST_STATES if module in ("leave", "travel", "administrative") else {"planned": "ثبت‌نام‌شده", "completed": "تکمیل‌شده", "cancelled": "لغوشده"}).get(value, value)
    if key == "result":
        return INTERVIEW_RESULTS[value]
    for item in MODULES[module]["fields"]:
        if item["name"] == key and item.get("choices"):
            return item["choices"].get(str(value).lower(), value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return value


def validate_record(db, request, module, clean, record):
    errors = []
    if module == "candidates":
        if record and record.employee_id:
            errors.append("این متقاضی استخدام شده است؛ اطلاعات فردی را در پروندهٔ کارمند ویرایش کنید.")
        if not re.fullmatch(r"[0-9]{10}", clean["national_id"]):
            errors.append("کد ملی باید ۱۰ رقم باشد.")
        if not re.fullmatch(r"09[0-9]{9}", clean["phone"]):
            errors.append("شمارهٔ همراه باید ۱۱ رقم و با ۰۹ آغاز شود.")
        unit = db.get(Unit, clean["unit_id"])
        if not unit or unit.branch_id != clean["branch_id"]:
            errors.append("واحد انتخاب‌شده متعلق به این شعبه نیست.")
        check_scope(request, clean["branch_id"], clean["unit_id"])
        if clean["status"] == "accepted" and (not record or not db.scalar(select(Interview.id).where(Interview.candidate_id == record.id, Interview.result == "passed"))):
            errors.append("پذیرش نیاز به حداقل یک مصاحبه با نتیجهٔ قبول دارد.")
    if module == "interviews":
        candidate = candidate_for(db, request, clean["candidate_id"])
        if candidate.employee_id or candidate.status == "rejected":
            errors.append("برای متقاضی ردشده یا استخدام‌شده مصاحبهٔ جدید ثبت نمی‌شود.")
        if clean["result"] != "pending" and clean["scheduled_at"] > datetime.now():
            errors.append("نتیجهٔ مصاحبهٔ آینده را نمی‌توان از قبل ثبت کرد.")
        if record and record.candidate_id != clean["candidate_id"]:
            errors.append("متقاضی مصاحبهٔ ثبت‌شده قابل تغییر نیست.")
    if module == "shifts":
        duration = minutes_between(clean["start_time"], clean["end_time"])
        if duration <= clean["break_minutes"]:
            errors.append("مدت شیفت باید بیشتر از زمان استراحت باشد و شروع و پایان متفاوت باشند.")
    if module == "attendance":
        employee = scoped_employee(db, request, clean["employee_id"])
        if clean["work_date"] > date.today():
            errors.append("تردد مربوط به آینده قابل ثبت نیست.")
        if clean["work_date"] < employee.hire_date:
            errors.append("روز تردد نمی‌تواند قبل از تاریخ استخدام باشد.")
        shift = db.get(Shift, clean["shift_id"])
        clean["required_minutes"] = minutes_between(shift.start_time, shift.end_time) - shift.break_minutes
        total = 0
        if clean["presence_status"] == "present":
            if not clean["clock_in"] or not clean["clock_out"]:
                errors.append("برای ثبت حضور، ساعت ورود و خروج را وارد کنید.")
            else:
                total = minutes_between(clean["clock_in"], clean["clock_out"])
                if total <= shift.break_minutes:
                    errors.append("زمان خروج باید کارکردی بیشتر از استراحت ایجاد کند.")
        else:
            clean["clock_in"] = clean["clock_out"] = None
        clean["worked_minutes"] = max(0, total - shift.break_minutes) if clean["presence_status"] == "present" else 0
        clean["overtime_minutes"] = max(0, clean["worked_minutes"] - clean["required_minutes"])
    if module in ("leave", "travel", "administrative"):
        scoped_employee(db, request, clean["employee_id"])
        clean["kind"] = module
        if module == "administrative":
            clean["end_date"] = clean["start_date"]
        if clean["end_date"] < clean["start_date"]:
            errors.append("تاریخ پایان نباید قبل از تاریخ شروع باشد.")
        if record and record.status != "pending":
            errors.append("درخواست بررسی‌شده قابل ویرایش نیست؛ درخواست جدید ثبت کنید.")
    if module == "contracts":
        if record and record.status != "draft":
            errors.append("قرارداد فعال یا خاتمه‌یافته قابل بازنویسی نیست؛ از تمدید یا خاتمه استفاده کنید.")
        if clean["end_date"] and clean["end_date"] < clean["start_date"]:
            errors.append("پایان قرارداد باید پس از شروع آن باشد.")
        if clean["contract_type"] != "دائم" and not clean["end_date"]:
            errors.append("برای این نوع قرارداد، تاریخ پایان الزامی است.")
        if record and record.renewed_from_id and record.employee_id != clean["employee_id"]:
            errors.append("کارمند قرارداد تمدیدشده قابل تغییر نیست.")
    if module == "users":
        db.execute(select(func.pg_advisory_xact_lock(704811)))
        actor = db.execute(select(Admin.role, Admin.is_active).where(Admin.id == current_user(request).id)).one()
        if actor.role != "admin" or not actor.is_active:
            raise HTTPException(403, "حساب شما دیگر دسترسی مدیریت کاربران ندارد.")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,50}", clean["username"]):
            errors.append("نام کاربری باید ۳ تا ۵۰ حرف لاتین، عدد، نقطه، زیرخط یا خط تیره باشد.")
        if not record and len(clean.get("password", "")) < 12:
            errors.append("رمز اولیه باید حداقل ۱۲ نویسه باشد.")
        if record and clean.get("password"):
            errors.append("رمز در فرم ویرایش تغییر نمی‌کند؛ برای تغییر رمز به فرایند جدا نیاز است.")
        if record and record.username != clean["username"]:
            errors.append("نام کاربری حساب موجود قابل تغییر نیست.")
        clean["is_active"] = clean["is_active"] == "true"
        if clean["role"] == "admin":
            clean["branch_scope_id"] = clean["unit_scope_id"] = None
        if clean["unit_scope_id"]:
            unit = db.get(Unit, clean["unit_scope_id"])
            if not clean["branch_scope_id"] or unit.branch_id != clean["branch_scope_id"]:
                errors.append("واحد دسترسی باید متعلق به شعبهٔ انتخاب‌شده باشد.")
        if record and record.id == current_user(request).id and (clean["role"] != "admin" or not clean["is_active"]):
            errors.append("نقش یا فعالیت حساب مدیریتی خود را نمی‌توانید تغییر دهید.")
        if record and record.role == "admin" and (clean["role"] != "admin" or not clean["is_active"]):
            remaining = db.scalar(select(func.count()).select_from(Admin).where(Admin.role == "admin", Admin.is_active.is_(True), Admin.id != record.id))
            if remaining < 1:
                errors.append("حداقل یک مدیر فعال باید باقی بماند.")
        password = clean.pop("password", "")
        if not record and password:
            clean["password_hash"] = hash_password(password)
    if module == "enrollments":
        training = db.scalar(select(Training).where(Training.id == clean["training_id"]).with_for_update())
        occupied = db.scalar(select(func.count()).select_from(TrainingEnrollment).where(TrainingEnrollment.training_id == training.id, TrainingEnrollment.status != "cancelled", TrainingEnrollment.id != (record.id if record else -1)))
        if clean["status"] != "cancelled" and occupied >= training.capacity:
            errors.append("ظرفیت دوره تکمیل شده است.")
    if module == "trainings" and record:
        occupied = db.scalar(select(func.count()).select_from(TrainingEnrollment).where(TrainingEnrollment.training_id == record.id, TrainingEnrollment.status != "cancelled"))
        if clean["capacity"] < occupied:
            errors.append("ظرفیت جدید از تعداد ثبت‌نام‌های موجود کمتر است.")
    return errors


def minutes_between(start, end):
    first, last = start.hour * 60 + start.minute, end.hour * 60 + end.minute
    return (last - first) % (24 * 60)


@router.get("/modules", dependencies=[Depends(require_login)])
def module_index(request: Request):
    return render(request, "modules.html", title="بخش‌های منابع انسانی")


@router.get("/hr/{module}")
def module_list(request: Request, module: str, q: str = "", status: str = ""):
    config = config_for(module, request)
    with SessionLocal() as db:
        query = query_for(module, request)
        model = config["model"]
        if status and hasattr(model, "status"):
            query = query.where(model.status == normalized(status))
        if q and module == "candidates":
            escaped = normalized(q)[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where((Candidate.first_name + " " + Candidate.last_name).ilike(f"%{escaped}%", escape="\\"))
        records = db.scalars(query.order_by(model.id.desc())).all()
        rows = [{"id": row.id, "cells": [display_value(db, module, key, getattr(row, key)) for key in config["columns"]]} for row in records]
    return render(request, "module_list.html", title=config["title"], module=module, config=config, rows=rows,
                  headings=[LABELS.get(key, key) for key in config["columns"]], q=q, status=status, status_choices=CANDIDATE_STATES if module == "candidates" else REQUEST_STATES if module in ("leave", "travel", "administrative") else CONTRACT_STATES if module == "contracts" else {})


@router.get("/hr/{module}/new")
def module_new(request: Request, module: str):
    config_for(module, request)
    with SessionLocal() as db:
        return form_page(request, db, module)


@router.post("/hr/{module}/new")
def module_create(request: Request, module: str, form: dict = Depends(browser_form)):
    config = config_for(module, request)
    with SessionLocal() as db:
        return save_record(request, db, module, config, form)


def save_record(request, db, module, config, form, record=None):
    fields = fields_for(config, db, request)
    values, clean, errors = parse_fields(fields, form)
    if not errors:
        errors.extend(validate_record(db, request, module, clean, record))
    if errors:
        return form_page(request, db, module, values, errors, record, 400)
    target = record or config["model"]()
    for key, value in clean.items():
        setattr(target, key, value)
    db.add(target)
    try:
        db.flush()
        if module == "interviews":
            candidate = candidate_for(db, request, target.candidate_id, lock=True)
            if candidate.status in ("new", "review"):
                candidate.status = "interview"
            if candidate.status == "accepted" and not db.scalar(select(Interview.id).where(Interview.candidate_id == candidate.id, Interview.result == "passed")):
                candidate.status = "interview"
        audit(db, request, "edit" if record else "create", config["model"].__tablename__, target.id,
              {"fields": [key for key in clean if key not in ("password_hash", "national_id", "phone", "email")]})
        db.commit()
    except IntegrityError:
        db.rollback()
        return form_page(request, db, module, values, ["این مورد قبلاً ثبت شده یا با اطلاعات وابسته سازگار نیست."], record, 400)
    return redirect(f"/hr/{module}/{target.id}?saved=1")


@router.get("/hr/{module}/{record_id}/edit")
def module_edit_page(request: Request, module: str, record_id: int):
    config_for(module, request)
    with SessionLocal() as db:
        record = record_for(db, request, module, record_id)
        values = {column.name: str(getattr(record, column.name)) if getattr(record, column.name) is not None else "" for column in record.__table__.columns}
        if module == "users":
            values["is_active"] = "true" if record.is_active else "false"
        return form_page(request, db, module, values=values, record=record)


@router.post("/hr/{module}/{record_id}/edit")
def module_edit(request: Request, module: str, record_id: int, form: dict = Depends(browser_form)):
    config = config_for(module, request)
    with SessionLocal() as db:
        record = record_for(db, request, module, record_id, lock=True)
        return save_record(request, db, module, config, form, record)


@router.get("/hr/{module}/{record_id}")
def module_detail(request: Request, module: str, record_id: int, saved: str = ""):
    config = config_for(module, request)
    with SessionLocal() as db:
        record = record_for(db, request, module, record_id)
        keys = [item["name"] for item in config["fields"] if item["kind"] != "password"]
        for key in ("status", "worked_minutes", "overtime_minutes", "review_notes", "reviewed_by", "reviewed_at"):
            if hasattr(record, key) and key not in keys:
                keys.append(key)
        details = [(LABELS.get(key, key), display_value(db, module, key, getattr(record, key))) for key in keys]
        interviews, tasks = [], []
        if module == "candidates":
            interviews = db.scalars(select(Interview).where(Interview.candidate_id == record.id).order_by(Interview.scheduled_at)).all()
            tasks = db.scalars(select(OnboardingTask).where(OnboardingTask.candidate_id == record.id).order_by(OnboardingTask.id)).all()
    return render(request, "module_detail.html", title=config["singular"], module=module, config=config, record=record, details=details,
                  interviews=interviews, tasks=tasks, saved=saved == "1", interview_results=INTERVIEW_RESULTS)


def hire_fields(db, request):
    config = {"fields": [field("employee_code", "کد پرسنلی", maximum_length=32), DATE("hire_date", "تاریخ استخدام"), pick("contract_type", "نوع قرارداد فعلی", choices=CONTRACT_TYPES)]}
    return fields_for(config, db, request)


@router.get("/hire/{candidate_id}")
def hire_page(request: Request, candidate_id: int):
    with SessionLocal() as db:
        candidate = candidate_for(db, request, candidate_id)
        if candidate.status != "accepted" or candidate.employee_id:
            raise HTTPException(400, "فقط متقاضی پذیرفته‌شده و استخدام‌نشده قابل تبدیل به کارمند است.")
        return form_page(request, db, "candidates", custom_fields=hire_fields(db, request), custom_title="ثبت استخدام و آغاز پذیرش",
                         action=f"/hire/{candidate_id}", description="اطلاعات فردی و سازمانی از متقاضی منتقل می‌شود؛ پروندهٔ کارمند و چک‌لیست پذیرش با هم ثبت می‌شوند.")


@router.post("/hire/{candidate_id}")
def hire_candidate(request: Request, candidate_id: int, form: dict = Depends(browser_form)):
    with SessionLocal() as db:
        candidate = candidate_for(db, request, candidate_id, lock=True)
        if candidate.employee_id:
            return redirect(f"/employees/{candidate.employee_id}")
        if candidate.status != "accepted":
            raise HTTPException(400, "متقاضی هنوز پذیرفته نشده است.")
        fields = hire_fields(db, request)
        values, clean, errors = parse_fields(fields, form)
        code = normalized(clean.get("employee_code")).upper()
        if not re.fullmatch(r"[\w-]{2,32}", code):
            errors.append("کد پرسنلی باید ۲ تا ۳۲ حرف، عدد، خط تیره یا زیرخط باشد.")
        if db.scalar(select(Employee.id).where(Employee.employee_code == code)):
            errors.append("این کد پرسنلی قبلاً ثبت شده است.")
        if errors:
            return form_page(request, db, "candidates", values, errors, status_code=400, custom_fields=fields, custom_title="ثبت استخدام", action=f"/hire/{candidate_id}")
        employee = Employee(employee_code=code, hire_date=clean["hire_date"], contract_type=clean["contract_type"], active=True,
                            **{key: getattr(candidate, key) for key in ("first_name", "last_name", "national_id", "phone", "email", "branch_id", "unit_id", "position_id")})
        db.add(employee)
        try:
            db.flush()
            candidate.employee_id, candidate.status = employee.id, "hired"
            for title in ("تکمیل مدارک هویتی", "معرفی واحد و شرح شغل", "آماده‌سازی دسترسی و تجهیزات"):
                db.add(OnboardingTask(candidate_id=candidate.id, title=title))
            sync_assignment(db, employee, "استخدام از پروندهٔ متقاضی")
            audit(db, request, "hire", "candidates", candidate.id, {"employee_id": employee.id})
            db.commit()
        except IntegrityError:
            db.rollback()
            return form_page(request, db, "candidates", values, ["کد پرسنلی تکراری است یا استخدام هم‌زمان دیگری ثبت شده است."], status_code=400, custom_fields=fields, custom_title="ثبت استخدام", action=f"/hire/{candidate_id}")
    return redirect(f"/hr/candidates/{candidate_id}?saved=1")


@router.post("/onboarding/{task_id}")
def complete_onboarding(request: Request, task_id: int, form: dict = Depends(browser_form)):
    require_hr(request)
    with SessionLocal() as db:
        task = db.get(OnboardingTask, task_id)
        if not task:
            raise HTTPException(404)
        candidate = candidate_for(db, request, task.candidate_id, lock=True)
        if not candidate.employee_id:
            raise HTTPException(400, "پذیرش فقط پس از ثبت استخدام انجام می‌شود.")
        if form.get("completed") not in ("true", "false"):
            raise HTTPException(400, "وضعیت کار معتبر نیست.")
        task.completed = form["completed"] == "true"
        task.completed_at = utc_now() if task.completed else None
        audit(db, request, "onboarding", "onboarding_tasks", task.id, {"completed": task.completed})
        db.commit()
    return redirect(f"/hr/candidates/{candidate.id}?saved=1")


@router.post("/requests/{request_id}/review")
def review_request(request: Request, request_id: int, form: dict = Depends(browser_form)):
    reviewer = require_admin(request)
    decision, notes = form.get("decision"), normalized(form.get("review_notes"))
    if decision not in ("approved", "rejected") or len(notes) > 3000:
        raise HTTPException(400, "نتیجه یا توضیح بررسی معتبر نیست.")
    if decision == "rejected" and not notes:
        raise HTTPException(400, "علت رد درخواست را بنویسید.")
    with SessionLocal() as db:
        item = db.scalar(select(HrRequest).where(HrRequest.id == request_id).with_for_update())
        if not item:
            raise HTTPException(404)
        scoped_employee(db, request, item.employee_id, lock=True)
        if item.status != "pending":
            return redirect(f"/hr/{item.kind}/{item.id}")
        if decision == "approved" and item.kind in ("leave", "travel"):
            overlap = db.scalar(select(HrRequest.id).where(HrRequest.employee_id == item.employee_id, HrRequest.id != item.id,
                HrRequest.kind.in_(["leave", "travel"]), HrRequest.status == "approved", HrRequest.start_date <= item.end_date, HrRequest.end_date >= item.start_date))
            if overlap:
                raise HTTPException(400, "بازهٔ درخواست با مرخصی یا مأموریت تأییدشدهٔ دیگری هم‌پوشانی دارد.")
        item.status, item.review_notes, item.reviewed_by, item.reviewed_at = decision, notes, reviewer.id, utc_now()
        audit(db, request, "review", "hr_requests", item.id, {"decision": decision})
        db.commit()
    return redirect(f"/hr/{item.kind}/{item.id}?saved=1")


@router.post("/contracts/{contract_id}/activate")
def activate_contract(request: Request, contract_id: int, form: dict = Depends(browser_form)):
    require_hr(request)
    with SessionLocal() as db:
        contract = record_for(db, request, "contracts", contract_id, lock=True)
        employee = scoped_employee(db, request, contract.employee_id, lock=True)
        if contract.status == "active":
            return redirect(f"/hr/contracts/{contract.id}")
        if contract.status != "draft":
            raise HTTPException(400, "فقط پیش‌نویس قرارداد فعال می‌شود.")
        if contract.start_date > date.today() or (contract.end_date and contract.end_date < date.today()):
            raise HTTPException(400, "برای فعال‌سازی باید تاریخ امروز داخل بازهٔ قرارداد باشد.")
        active = db.scalar(select(EmploymentContract).where(EmploymentContract.employee_id == employee.id, EmploymentContract.status == "active").with_for_update())
        if active:
            if contract.renewed_from_id != active.id or contract.start_date <= active.start_date:
                raise HTTPException(400, "این کارمند قرارداد فعال دارد؛ از مسیر تمدید همان قرارداد استفاده کنید.")
            active.end_date, active.status = contract.start_date - timedelta(days=1), "renewed"
            db.flush()
        elif contract.renewed_from_id:
            previous = db.get(EmploymentContract, contract.renewed_from_id)
            if not previous or previous.employee_id != employee.id:
                raise HTTPException(400, "قرارداد قبلی تمدید متعلق به این کارمند نیست.")
        contract.status = "active"
        employee.contract_type, employee.active = contract.contract_type, True
        profile = db.scalar(select(PayrollProfile).where(PayrollProfile.employee_id == employee.id))
        if profile:
            profile.base_salary = contract.base_salary
        else:
            db.add(PayrollProfile(employee_id=employee.id, base_salary=contract.base_salary, hourly_rate=0, benefits=0, deductions=0))
        audit(db, request, "activate", "employment_contracts", contract.id)
        db.commit()
    return redirect(f"/hr/contracts/{contract_id}?saved=1")


@router.get("/contracts/{contract_id}/renew")
def renew_contract_page(request: Request, contract_id: int):
    with SessionLocal() as db:
        contract = record_for(db, request, "contracts", contract_id)
        if contract.status != "active":
            raise HTTPException(400, "تمدید از قرارداد فعال آغاز می‌شود.")
        fields = fields_for({"fields": [DATE("start_date", "شروع دورهٔ جدید"), DATE("end_date", "پایان دورهٔ جدید"), pick("contract_type", "نوع قرارداد جدید", choices=CONTRACT_TYPES), money("base_salary", "حقوق پایهٔ جدید"), field("notes", "توضیح تمدید", "textarea", False)]}, db, request)
        return form_page(request, db, "contracts", record=contract, custom_fields=fields, custom_title="تمدید قرارداد", action=f"/contracts/{contract_id}/renew",
                         description="یک پیش‌نویس جدید ساخته می‌شود و نسخهٔ قبلی حفظ می‌ماند. هنگام فعال‌سازی تمدید، قرارداد قبلی در روز قبل از شروع دورهٔ جدید بسته می‌شود.")


@router.post("/contracts/{contract_id}/renew")
def renew_contract(request: Request, contract_id: int, form: dict = Depends(browser_form)):
    with SessionLocal() as db:
        old = record_for(db, request, "contracts", contract_id, lock=True)
        if old.status != "active":
            raise HTTPException(400, "فقط قرارداد فعال تمدید می‌شود.")
        fields = fields_for({"fields": [DATE("start_date", "شروع دورهٔ جدید"), DATE("end_date", "پایان دورهٔ جدید"), pick("contract_type", "نوع قرارداد جدید", choices=CONTRACT_TYPES), money("base_salary", "حقوق پایهٔ جدید"), field("notes", "توضیح تمدید", "textarea", False)]}, db, request)
        values, clean, errors = parse_fields(fields, form)
        if not errors and (clean["start_date"] <= old.start_date or clean["end_date"] < clean["start_date"]):
            errors.append("دورهٔ جدید باید پس از شروع قرارداد قبلی آغاز شود و پایان معتبر داشته باشد.")
        if errors:
            return form_page(request, db, "contracts", values, errors, old, 400, custom_fields=fields, custom_title="تمدید قرارداد", action=f"/contracts/{contract_id}/renew")
        new = EmploymentContract(employee_id=old.employee_id, renewed_from_id=old.id, status="draft", **clean)
        db.add(new)
        db.flush()
        audit(db, request, "renew", "employment_contracts", new.id, {"previous_contract_id": old.id})
        db.commit()
    return redirect(f"/hr/contracts/{new.id}?saved=1")


@router.post("/contracts/{contract_id}/terminate")
def terminate_contract(request: Request, contract_id: int, form: dict = Depends(browser_form)):
    require_hr(request)
    reason = normalized(form.get("reason"))
    try:
        end_date = date.fromisoformat(normalized(form.get("end_date")))
    except ValueError:
        raise HTTPException(400, "تاریخ خاتمه معتبر نیست.")
    if not reason or len(reason) > 3000:
        raise HTTPException(400, "علت خاتمهٔ همکاری را وارد کنید.")
    with SessionLocal() as db:
        contract = record_for(db, request, "contracts", contract_id, lock=True)
        employee = scoped_employee(db, request, contract.employee_id, lock=True)
        if contract.status != "active" or not contract.start_date <= end_date <= date.today():
            raise HTTPException(400, "قرارداد باید فعال و تاریخ خاتمه بین شروع قرارداد و امروز باشد.")
        contract.status, contract.end_date, contract.termination_reason = "ended", end_date, reason
        employee.active = False
        audit(db, request, "terminate", "employment_contracts", contract.id, {"employee_id": employee.id})
        db.commit()
    return redirect(f"/hr/contracts/{contract_id}?saved=1")


@router.get("/payroll")
def payroll_page(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        records = db.scalars(select(Payslip).order_by(Payslip.id.desc())).all()
        rows = [{"id": row.id, "employee": row.input_snapshot["employee_name"], "period": row.period, "net": row.net_amount} for row in records]
        employees = options_for("employees", db, request)
    return render(request, "payroll.html", title="حقوق و فیش‌های آموزشی", rows=rows, employees=employees, period=date.today().strftime("%Y-%m"))


def rounded(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@router.post("/payroll/calculate")
def calculate_payroll(request: Request, form: dict = Depends(browser_form)):
    user = require_admin(request)
    period = normalized(form.get("period"))
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", period):
            raise ValueError()
        start = date.fromisoformat(period + "-01")
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        employee_id = int(normalized(form.get("employee_id")))
    except ValueError:
        raise HTTPException(400, "کارمند یا دورهٔ میلادی معتبر نیست؛ نمونهٔ دوره: 2026-11.")
    with SessionLocal() as db:
        employee = scoped_employee(db, request, employee_id, lock=True)
        existing = db.scalar(select(Payslip).where(Payslip.employee_id == employee.id, Payslip.period == period))
        if existing:
            return redirect(f"/payroll/{existing.id}")
        profile = db.scalar(select(PayrollProfile).where(PayrollProfile.employee_id == employee.id))
        rule = db.scalar(select(PayrollRule).where(PayrollRule.contract_type == employee.contract_type))
        if not profile or not rule:
            raise HTTPException(400, "ابتدا پروفایل پرداخت کارمند و قاعدهٔ آموزشی نوع قرارداد او را ثبت کنید.")
        if rule.calculation_mode == "hourly" and profile.hourly_rate <= 0:
            raise HTTPException(400, "برای محاسبهٔ ساعتی، نرخ ساعتی مثبت وارد کنید.")
        records = db.scalars(select(Attendance).where(Attendance.employee_id == employee.id, Attendance.work_date.between(start, end)).order_by(Attendance.work_date)).all()
        worked = sum(item.worked_minutes for item in records)
        overtime = sum(item.overtime_minutes for item in records)
        regular = worked - overtime
        hourly = Decimal(profile.base_salary) / rule.monthly_hours if rule.calculation_mode == "monthly" else Decimal(profile.hourly_rate)
        base = profile.base_salary if rule.calculation_mode == "monthly" else rounded(Decimal(regular) / 60 * hourly)
        overtime_amount = rounded(Decimal(overtime) / 60 * hourly * rule.overtime_factor)
        gross = base + overtime_amount + profile.benefits
        insurance = rounded(Decimal(gross) * rule.insurance_percent / 100)
        tax = rounded(Decimal(gross) * rule.tax_percent / 100)
        net = gross - insurance - tax - profile.deductions
        if net < 0:
            raise HTTPException(400, "کسورات از ناخالص بیشتر است؛ پروفایل و نرخ‌های آموزشی را بررسی کنید.")
        input_snapshot = {"employee_name": f"{employee.first_name} {employee.last_name}", "employee_code": employee.employee_code,
            "contract_type": employee.contract_type, "base_salary": profile.base_salary, "hourly_rate": profile.hourly_rate,
            "benefits": profile.benefits, "deductions": profile.deductions, "worked_minutes": worked, "regular_minutes": regular,
            "overtime_minutes": overtime, "attendance_ids": [item.id for item in records]}
        rule_snapshot = {key: str(getattr(rule, key)) for key in ("contract_type", "calculation_mode", "monthly_hours", "overtime_factor", "insurance_percent", "tax_percent")}
        payslip = Payslip(employee_id=employee.id, period=period, base_amount=base, overtime_amount=overtime_amount, benefits=profile.benefits,
            insurance=insurance, tax=tax, deductions=profile.deductions, net_amount=net, input_snapshot=input_snapshot, rule_snapshot=rule_snapshot, created_by=user.id)
        db.add(payslip)
        db.flush()
        audit(db, request, "calculate", "payslips", payslip.id, {"period": period})
        db.commit()
    return redirect(f"/payroll/{payslip.id}")


@router.get("/payroll/{payslip_id}")
def payslip_detail(request: Request, payslip_id: int):
    require_admin(request)
    with SessionLocal() as db:
        payslip = db.get(Payslip, payslip_id)
        if not payslip:
            raise HTTPException(404)
    return render(request, "payslip.html", title="فیش حقوقی آموزشی", payslip=payslip)


@router.get("/history/{employee_id}")
def employee_history(request: Request, employee_id: int):
    with SessionLocal() as db:
        employee = scoped_employee(db, request, employee_id)
        records = db.scalars(select(AssignmentHistory).where(AssignmentHistory.employee_id == employee.id).order_by(AssignmentHistory.id.desc())).all()
        rows = [{"start": row.start_date, "end": row.end_date, "branch": row.branch_name,
                 "unit": row.unit_name, "position": row.position_title, "reason": row.reason} for row in records]
    return render(request, "history.html", title="تاریخچهٔ انتساب سازمانی", employee=employee, rows=rows)


@router.get("/reports", dependencies=[Depends(require_login)])
def reports(request: Request, period: str = ""):
    user = current_user(request)
    if not period:
        period = date.today().strftime("%Y-%m")
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", normalized(period)):
            raise ValueError()
        start = date.fromisoformat(normalized(period) + "-01")
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    except ValueError:
        raise HTTPException(400, "دورهٔ گزارش باید ماه میلادی معتبر باشد.")
    with SessionLocal() as db:
        counts = db.execute(scoped(select(Branch.name, Unit.name, func.count(Employee.id), func.count(Employee.id).filter(Employee.active.is_(True)))
            .select_from(Employee).join(Branch, Branch.id == Employee.branch_id).join(Unit, Unit.id == Employee.unit_id).group_by(Branch.name, Unit.name), user)).all()
        attendance = db.execute(scoped(select(func.coalesce(func.sum(Attendance.worked_minutes), 0), func.coalesce(func.sum(Attendance.overtime_minutes), 0), func.count(Attendance.id).filter(Attendance.presence_status == "absent"))
            .select_from(Attendance).join(Employee, Employee.id == Attendance.employee_id).where(Attendance.work_date.between(start, end)), user)).one()
        requests = db.execute(scoped(select(HrRequest.kind, HrRequest.status, func.count()).join(Employee, Employee.id == HrRequest.employee_id)
            .where(HrRequest.start_date <= end, HrRequest.end_date >= start).group_by(HrRequest.kind, HrRequest.status), user)).all()
        payroll_total = db.scalar(select(func.coalesce(func.sum(Payslip.net_amount), 0)).where(Payslip.period == period)) if user.role == "admin" else None
    return render(request, "reports.html", title="گزارش‌های منابع انسانی", counts=counts, attendance=attendance, requests=requests,
                  period=period, payroll_total=payroll_total, request_states=REQUEST_STATES, request_kinds={"leave": "مرخصی", "travel": "مأموریت", "administrative": "اداری"})


def safe_csv(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@router.get("/reports/employees.csv")
def export_employees(request: Request):
    user = require_hr(request)
    with SessionLocal() as db:
        rows = db.execute(scoped(select(Employee, Branch.name, Unit.name, Position.title).join(Branch, Branch.id == Employee.branch_id)
            .join(Unit, Unit.id == Employee.unit_id).join(Position, Position.id == Employee.position_id), user).order_by(Employee.id)).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["کد پرسنلی", "نام", "نام خانوادگی", "شعبه", "واحد", "سمت", "نوع قرارداد", "وضعیت"])
        for employee, branch, unit, position in rows:
            writer.writerow([safe_csv(value) for value in [employee.employee_code, employee.first_name, employee.last_name, branch, unit, position, employee.contract_type, "فعال" if employee.active else "غیرفعال"]])
        audit(db, request, "export", "employees", details={"rows": len(rows)})
        db.commit()
    return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="employees.csv"'})


@router.get("/audit")
def audit_page(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        rows = db.execute(select(AuditLog, Admin.display_name).outerjoin(Admin, Admin.id == AuditLog.actor_id).order_by(AuditLog.id.desc()).limit(300)).all()
    labels = {"create": "ثبت", "edit": "ویرایش", "status": "تغییر وضعیت", "login": "ورود", "logout": "خروج", "hire": "استخدام", "onboarding": "پذیرش", "review": "بررسی درخواست", "activate": "فعال‌سازی قرارداد", "renew": "تمدید", "terminate": "خاتمهٔ همکاری", "calculate": "محاسبهٔ حقوق", "export": "دریافت گزارش"}
    entities = {"employees": "کارکنان", "admins": "کاربران", "branches": "شعبه‌ها", "units": "واحدها", "positions": "سمت‌ها", "candidates": "متقاضیان", "onboarding_tasks": "پذیرش", "hr_requests": "درخواست‌ها", "employment_contracts": "قراردادها", "payslips": "فیش‌ها", "assignment_history": "تاریخچه"}
    entities.update({config["model"].__tablename__: config["title"] for config in MODULES.values()})
    return render(request, "audit.html", title="سابقهٔ تغییرات", rows=rows, action_labels=labels, entity_labels=entities)
