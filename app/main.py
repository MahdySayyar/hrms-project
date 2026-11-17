"""مسیرها، اعتبارسنجی و عملیات مستقیم پایگاه داده برای مرحلهٔ اول."""
import os
import re
import socket
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .database import Admin, Branch, Employee, Position, ROOT, SessionLocal, Unit, engine
from .access import (audit, check_scope, current_user, protected_form, read_form, render,
                     require_admin, require_hr, scoped, scoped_employee, sync_assignment)
from .security import (COOKIE_NAME, check_csrf, current_session, discard_session,
                       hash_password, new_session, password_needs_upgrade, require_login,
                       rotate_session, set_session_cookie, verify_password)
from . import security
from .session_store import SessionStoreUnavailable
from .pagination import PageRequest, paginate
from .login_capacity import PasswordCapacity, PasswordCapacityFull

password_capacity = PasswordCapacity(workers=int(os.getenv("HRMS_PASSWORD_WORKERS", "1")),
    max_pending=int(os.getenv("HRMS_PASSWORD_PENDING", "512")))

@asynccontextmanager
async def lifespan(_app):
    import anyio.to_thread
    threads = int(os.getenv("HRMS_THREADS", "40"))
    if not 1 <= threads <= 40:
        raise RuntimeError("HRMS_THREADS must be 1..40.")
    anyio.to_thread.current_default_thread_limiter().total_tokens = threads
    yield


app = FastAPI(title="سامانه مدیریت منابع انسانی", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
CONTRACT_TYPES = ("دائم", "مدت‌معین", "پیمانکاری", "آزمایشی")
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalized(value) -> str:
    return str(value or "").strip().translate(DIGITS)


def positive_int(value) -> int | None:
    value = normalized(value)
    return int(value) if re.fullmatch(r"[0-9]{1,9}", value) and int(value) > 0 else None


def redirect(url: str):
    return RedirectResponse(url, status_code=303)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    message = exc.detail if isinstance(exc.detail, str) else "درخواست قابل پردازش نیست."
    if exc.status_code == 404:
        message = "صفحه یا رکورد موردنظر پیدا نشد."
    return render(request, "error.html", exc.status_code, title="خطا", message=message)


@app.exception_handler(SessionStoreUnavailable)
def session_error(_request, _exc):
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("سامانهٔ ورود موقتاً در دسترس نیست؛ کمی بعد دوباره تلاش کنید.",
        status_code=503, headers={"Retry-After": "2", "Cache-Control": "no-store"})


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        security.session_store.ping()
        return {"status": "ok"}
    except (SQLAlchemyError, SessionStoreUnavailable):
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "unavailable"}, status_code=503)


@app.get("/instance")
def instance():
    return {"instance": os.getenv("INSTANCE_ID", socket.gethostname())}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return guest_auth_page(request, "login.html", "ورود به سامانه",
        registration_submitted=request.query_params.get("registered") == "1")


@app.get("/register", response_class=HTMLResponse)
def registration_page(request: Request):
    return guest_auth_page(request, "register.html", "ساخت حساب")


def guest_auth_page(request, template, title, **context):
    session = current_session(request)
    if session and session.admin_id is not None:
        return redirect("/")
    if session is None:
        token, session = new_session()
        response = render(request, template, title=title, csrf_token=session.csrf_token, **context)
        set_session_cookie(response, token, authenticated=False)
        return response
    return render(request, template, title=title, **context)


def check_registration_session(request, form):
    check_csrf(request, form)
    session = current_session(request)
    if session is None or session.admin_id is not None:
        raise HTTPException(403, "برای ساخت حساب از صفحهٔ ورود اقدام کنید.")


@app.post("/register")
async def register(request: Request, form: dict = Depends(read_form)):
    await run_in_threadpool(check_registration_session, request, form)
    username = normalized(form.get("username")) if isinstance(form.get("username"), str) else ""
    display_name = normalized(form.get("display_name")) if isinstance(form.get("display_name"), str) else ""
    password = form.get("password")
    errors = []
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,50}", username):
        errors.append("نام کاربری باید ۳ تا ۵۰ نویسه و شامل حرف لاتین، عدد، نقطه، خط تیره یا زیرخط باشد.")
    if not 1 <= len(display_name) <= 100 or "\x00" in display_name:
        errors.append("نام نمایشی معتبر و حداکثر ۱۰۰ نویسه وارد کنید.")
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        errors.append("رمز عبور باید ۱۲ تا ۱۲۸ نویسه باشد.")
    elif password != form.get("password_confirmation"):
        errors.append("رمز عبور و تکرار آن یکسان نیستند.")
    if errors:
        return await run_in_threadpool(render, request, "register.html", 400, title="ساخت حساب",
            display_name=display_name[:100], username=username[:50], errors=errors)
    try:
        password_hash = await password_capacity.run(hash_password, password)
    except PasswordCapacityFull:
        raise HTTPException(503, "سامانه مشغول است. کمی بعد دوباره تلاش کنید.") from None
    created = await run_in_threadpool(create_pending_account, request, form, username, display_name, password_hash)
    if not created:
        return await run_in_threadpool(render, request, "register.html", 409, title="ساخت حساب",
            display_name=display_name, username=username, errors=["این نام کاربری قبلاً ثبت شده است."])
    return redirect("/login?registered=1")


def create_pending_account(request, form, username, display_name, password_hash):
    check_registration_session(request, form)
    with SessionLocal.begin() as db:
        account_id = db.scalar(insert(Admin).values(username=username, display_name=display_name,
            password_hash=password_hash, role="viewer", is_active=False)
            .on_conflict_do_nothing(index_elements=[Admin.username]).returning(Admin.id))
        if account_id is None:
            return False
        audit(db, request, "register", "admins", account_id)
        return True


@app.post("/login")
async def login(request: Request, form: dict = Depends(read_form)):
    await run_in_threadpool(check_csrf, request, form)
    username = normalized(form.get("username"))
    password = str(form.get("password", ""))
    account = await run_in_threadpool(login_account_snapshot, username)
    valid = False
    replacement_hash = None
    if account and account.is_active:
        try:
            valid, replacement_hash = await password_capacity.verify(verify_login_password, password, account.password_hash)
        except PasswordCapacityFull:
            response = await run_in_threadpool(render, request, "login.html", 503, title="ورود مدیر",
                errors=["سامانه در حال پردازش ورود کاربران است؛ کمی بعد دوباره تلاش کنید."], username=username)
            response.headers["Retry-After"] = "2"
            return response
    if not valid:
        return await run_in_threadpool(render, request, "login.html", 401, title="ورود مدیر", errors=["نام کاربری یا رمز عبور درست نیست."], username=username)
    token = await run_in_threadpool(commit_verified_login, request, form, account.id, account.password_hash, replacement_hash)
    if token is None:
        return await run_in_threadpool(render, request, "login.html", 401, title="ورود مدیر", errors=["نام کاربری یا رمز عبور درست نیست."], username=username)
    response = redirect("/")
    set_session_cookie(response, token)
    return response


def login_account_snapshot(username):
    with SessionLocal() as db:
        return db.execute(select(Admin.id, Admin.password_hash, Admin.is_active).where(Admin.username == username)).first()


def verify_login_password(password, stored_hash):
    valid = verify_password(password, stored_hash)
    return valid, hash_password(password) if valid and password_needs_upgrade(stored_hash) else None


def commit_verified_login(request, form, account_id, expected_hash, replacement_hash):
    with SessionLocal() as db:
        admin = db.scalar(select(Admin).where(Admin.id == account_id).with_for_update())
        if not admin or not admin.is_active or admin.password_hash != expected_hash:
            return None
        check_csrf(request, form)
        admin_id = admin.id
        if replacement_hash is not None:
            admin.password_hash = replacement_hash
        audit(db, request, "login", "admins", admin_id, actor_id=admin_id)
        token = rotate_session(request, admin_id)
        try:
            db.commit()
        except BaseException:
            security.session_store.delete(token)
            raise
        return token


@app.post("/logout")
def logout(request: Request, form: dict = Depends(protected_form)):
    with SessionLocal() as db:
        audit(db, request, "logout", "admins", current_user(request).id)
        db.commit()
    discard_session(request)
    response = redirect("/login")
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return response


@app.get("/", dependencies=[Depends(require_login)])
def dashboard(request: Request):
    user = current_user(request)
    with SessionLocal() as db:
        branches = select(func.count()).select_from(Branch)
        units = select(func.count()).select_from(Unit)
        if user.branch_scope_id:
            branches = branches.where(Branch.id == user.branch_scope_id)
        if user.unit_scope_id:
            units = units.where(Unit.id == user.unit_scope_id)
        elif user.branch_scope_id:
            units = units.where(Unit.branch_id == user.branch_scope_id)
        totals = select(func.count().label("employees"), func.count().filter(Employee.active.is_(True)).label("active"),
            branches.scalar_subquery().label("branches"), units.scalar_subquery().label("units")).select_from(Employee)
        counts = db.execute(scoped(totals, user)).mappings().one()
        recent = []
        if user.role != "viewer":
            latest = select(Employee.id, Employee.employee_code, Employee.first_name, Employee.last_name, Employee.active)
            recent = db.execute(scoped(latest, user).order_by(Employee.id.desc()).limit(5)).all()
    return render(request, "dashboard.html", title="داشبورد", counts=counts, recent=recent)


def references(db, request=None):
    user = current_user(request) if request else None
    branch_query, unit_query = select(Branch), select(Unit)
    if user and user.branch_scope_id:
        branch_query = branch_query.where(Branch.id == user.branch_scope_id)
        unit_query = unit_query.where(Unit.branch_id == user.branch_scope_id)
    if user and user.unit_scope_id:
        unit_query = unit_query.where(Unit.id == user.unit_scope_id)
    return {"branches": db.scalars(branch_query.order_by(Branch.name)).all(),
            "units": db.scalars(unit_query.order_by(Unit.name)).all(),
            "positions": db.scalars(select(Position).order_by(Position.title)).all(),
            "contract_types": CONTRACT_TYPES}


@app.get("/employees", dependencies=[Depends(require_login)])
def employee_list(request: Request, q: str = "", branch: str = "", unit: str = "", status: str = "", page: str = "1", page_size: str = "50"):
    user = require_hr(request)
    requested = PageRequest.parse(page, page_size)
    q = normalized(q)[:100]
    branch_id, unit_id = positive_int(branch), positive_int(unit)
    with SessionLocal() as db:
        query = select(Employee, Branch.name.label("branch_name"), Unit.name.label("unit_name"), Position.title.label("position_title")).join(Branch, Employee.branch_id == Branch.id).join(Unit, Employee.unit_id == Unit.id).join(Position, Employee.position_id == Position.id)
        query = scoped(query, user)
        if q:
            # % و _ واردشده از طرف کاربر هم به‌عنوان متن جست‌وجو می‌شوند.
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            query = query.where(or_(Employee.employee_code.ilike(pattern, escape="\\"), (Employee.first_name + " " + Employee.last_name).ilike(pattern, escape="\\")))
        if branch:
            query = query.where(Employee.branch_id == branch_id) if branch_id else query.where(False)
        if unit:
            query = query.where(Employee.unit_id == unit_id) if unit_id else query.where(False)
        if status in ("active", "inactive"):
            query = query.where(Employee.active.is_(status == "active"))
        catalog = paginate(db, query.order_by(Employee.id.desc()), requested)
        refs = references(db, request)
    filters = {"q": q, "branch": branch, "unit": unit, "status": status}
    return render(request, "employees.html", title="کارکنان", rows=catalog.rows, page=catalog,
                  navigation=catalog.navigation("/employees", filters), filters=filters, **refs)


def employee_form_page(request, db, values=None, errors=None, employee=None, status_code=200):
    return render(request, "employee_form.html", status_code, title="ویرایش پرونده" if employee else "افزودن کارمند",
                  values=values or {}, errors=errors or [], employee=employee, **references(db, request))


def validate_employee(db, form, current_id=None):
    fields = ("employee_code", "first_name", "last_name", "national_id", "phone", "email", "hire_date", "branch_id", "unit_id", "position_id", "contract_type")
    values = {key: normalized(form.get(key)) for key in fields}
    values["employee_code"] = values["employee_code"].upper()
    errors = []
    if not re.fullmatch(r"[\w-]{2,32}", values["employee_code"]):
        errors.append("کد پرسنلی باید ۲ تا ۳۲ نویسه و شامل حروف، عدد، خط تیره یا زیرخط باشد.")
    duplicate = select(Employee.id).where(Employee.employee_code == values["employee_code"])
    if current_id:
        duplicate = duplicate.where(Employee.id != current_id)
    if db.scalar(duplicate):
        errors.append("این کد پرسنلی قبلاً ثبت شده است؛ کد دیگری وارد کنید.")
    for field, label in (("first_name", "نام"), ("last_name", "نام خانوادگی")):
        if not 1 <= len(values[field]) <= 80:
            errors.append(f"{label} الزامی است و باید حداکثر ۸۰ نویسه باشد.")
    if not re.fullmatch(r"[0-9]{10}", values["national_id"]):
        errors.append("کد ملی باید دقیقاً ۱۰ رقم باشد.")
    if not re.fullmatch(r"09[0-9]{9}", values["phone"]):
        errors.append("شمارهٔ همراه باید ۱۱ رقم باشد و با ۰۹ شروع شود.")
    if values["email"] and (len(values["email"]) > 254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", values["email"])):
        errors.append("نشانی ایمیل معتبر وارد کنید یا این فیلد را خالی بگذارید.")
    try:
        hire_date = date.fromisoformat(values["hire_date"])
    except ValueError:
        hire_date = None
        errors.append("تاریخ استخدام را به شکل یک تاریخ میلادی معتبر وارد کنید.")
    branch_id, unit_id, position_id = (positive_int(values[key]) for key in ("branch_id", "unit_id", "position_id"))
    branch = db.get(Branch, branch_id) if branch_id else None
    unit = db.get(Unit, unit_id) if unit_id else None
    position = db.get(Position, position_id) if position_id else None
    if not branch:
        errors.append("یک شعبهٔ معتبر انتخاب کنید.")
    if not unit:
        errors.append("یک واحد معتبر انتخاب کنید.")
    elif unit.branch_id != branch_id:
        errors.append("واحد انتخاب‌شده متعلق به این شعبه نیست.")
    if not position:
        errors.append("یک سمت معتبر انتخاب کنید.")
    if values["contract_type"] not in CONTRACT_TYPES:
        errors.append("نوع قرارداد را از گزینه‌های موجود انتخاب کنید.")
    clean = {**values, "hire_date": hire_date, "branch_id": branch_id, "unit_id": unit_id, "position_id": position_id}
    return values, clean, errors


@app.get("/employees/new", dependencies=[Depends(require_login)])
def employee_new(request: Request):
    require_hr(request)
    with SessionLocal() as db:
        return employee_form_page(request, db, values={"hire_date": date.today().isoformat()})


@app.post("/employees/new")
def employee_create(request: Request, form: dict = Depends(protected_form)):
    require_hr(request)
    with SessionLocal() as db:
        values, clean, errors = validate_employee(db, form)
        if errors:
            return employee_form_page(request, db, values, errors, status_code=400)
        check_scope(request, clean["branch_id"], clean["unit_id"])
        employee = Employee(**clean, active=True)
        db.add(employee)
        try:
            db.flush()
            sync_assignment(db, employee, "ایجاد پروندهٔ کارمند")
            audit(db, request, "create", "employees", employee.id)
            db.commit()
        except IntegrityError:
            db.rollback()
            return employee_form_page(request, db, values, ["اطلاعات ذخیره نشد؛ کد پرسنلی تکراری یا اطلاعات سازمانی نامعتبر است."], status_code=400)
        return redirect(f"/employees/{employee.id}?saved=1")


@app.get("/employees/{employee_id}", dependencies=[Depends(require_login)])
def employee_detail(request: Request, employee_id: int, saved: str = "", changed: str = ""):
    with SessionLocal() as db:
        employee = scoped_employee(db, request, employee_id)
        if not employee:
            raise HTTPException(404)
        branch, unit, position = db.get(Branch, employee.branch_id), db.get(Unit, employee.unit_id), db.get(Position, employee.position_id)
    return render(request, "employee_detail.html", title="پروندهٔ کارمند", employee=employee, branch=branch, unit=unit, position=position, saved=saved == "1", changed=changed == "1")


@app.get("/employees/{employee_id}/edit", dependencies=[Depends(require_login)])
def employee_edit_page(request: Request, employee_id: int):
    with SessionLocal() as db:
        employee = scoped_employee(db, request, employee_id)
        if not employee:
            raise HTTPException(404)
        values = {column.name: str(getattr(employee, column.name)) for column in Employee.__table__.columns}
        return employee_form_page(request, db, values=values, employee=employee)


@app.post("/employees/{employee_id}/edit")
def employee_edit(request: Request, employee_id: int, form: dict = Depends(protected_form)):
    with SessionLocal() as db:
        employee = scoped_employee(db, request, employee_id, lock=True)
        if not employee:
            raise HTTPException(404)
        values, clean, errors = validate_employee(db, form, employee_id)
        if errors:
            return employee_form_page(request, db, values, errors, employee, 400)
        check_scope(request, clean["branch_id"], clean["unit_id"])
        changed_fields = [key for key, value in clean.items() if getattr(employee, key) != value]
        for key, value in clean.items():
            setattr(employee, key, value)
        try:
            sync_assignment(db, employee, "ویرایش انتساب سازمانی از پروندهٔ کارمند")
            audit(db, request, "edit", "employees", employee.id, {"fields": changed_fields})
            db.commit()
        except IntegrityError:
            db.rollback()
            return employee_form_page(request, db, values, ["اطلاعات ذخیره نشد؛ کد پرسنلی تکراری یا اطلاعات سازمانی نامعتبر است."], employee, 400)
    return redirect(f"/employees/{employee_id}?saved=1")


@app.post("/employees/{employee_id}/status")
def employee_status(request: Request, employee_id: int, form: dict = Depends(protected_form)):
    with SessionLocal() as db:
        employee = scoped_employee(db, request, employee_id, lock=True)
        if not employee:
            raise HTTPException(404)
        desired = form.get("active")
        if desired not in ("true", "false"):
            raise HTTPException(400, "وضعیت انتخاب‌شده معتبر نیست.")
        employee.active = desired == "true"
        audit(db, request, "status", "employees", employee.id, {"active": employee.active})
        db.commit()
    return redirect(f"/employees/{employee_id}?changed=1")


ORG = {"branches": {"model": Branch, "label": "شعبه‌ها", "singular": "شعبه", "name_field": "name"},
       "units": {"model": Unit, "label": "واحدها", "singular": "واحد", "name_field": "name"},
       "positions": {"model": Position, "label": "سمت‌ها", "singular": "سمت", "name_field": "title"}}


def org_config(kind):
    if kind not in ORG:
        raise HTTPException(404)
    return ORG[kind]


@app.get("/organization/{kind}", dependencies=[Depends(require_login)])
def organization_list(request: Request, kind: str, saved: str = ""):
    user = require_hr(request)
    config = org_config(kind)
    with SessionLocal() as db:
        query = select(config["model"])
        if kind == "branches" and user.branch_scope_id:
            query = query.where(Branch.id == user.branch_scope_id)
        if kind == "units":
            query = scoped(query, user, Unit)
        rows = db.scalars(query.order_by(config["model"].id)).all()
        branch_names = {branch.id: branch.name for branch in db.scalars(select(Branch)).all()}
    return render(request, "organization.html", title=config["label"], config=config, kind=kind, rows=rows, branch_names=branch_names, saved=saved == "1")


def org_form_page(request, db, kind, values=None, errors=None, record=None, status_code=200):
    config = org_config(kind)
    return render(request, "organization_form.html", status_code, title=("ویرایش " if record else "افزودن ") + config["singular"],
                  config=config, kind=kind, values=values or {}, errors=errors or [], record=record,
                  branches=db.scalars(select(Branch).order_by(Branch.name)).all())


@app.get("/organization/{kind}/new", dependencies=[Depends(require_login)])
def organization_new(request: Request, kind: str):
    require_admin(request)
    org_config(kind)
    with SessionLocal() as db:
        return org_form_page(request, db, kind)


def save_organization(request, db, kind, form, record=None):
    require_admin(request)
    config = org_config(kind)
    model, field = config["model"], config["name_field"]
    before = {key: getattr(record, key) for key in ([field, "branch_id"] if kind == "units" else [field, "description"] if kind == "positions" else [field])} if record else {}
    values = {field: normalized(form.get(field)), "branch_id": normalized(form.get("branch_id")), "description": normalized(form.get("description"))}
    errors = []
    if not 1 <= len(values[field]) <= 100:
        errors.append("نام یا عنوان الزامی است و باید حداکثر ۱۰۰ نویسه باشد.")
    duplicate = select(model.id).where(getattr(model, field) == values[field])
    branch_id = None
    if kind == "units":
        branch_id = positive_int(values["branch_id"])
        if not branch_id or not db.get(Branch, branch_id):
            errors.append("یک شعبهٔ معتبر انتخاب کنید.")
        duplicate = duplicate.where(Unit.branch_id == branch_id)
        if record and record.branch_id != branch_id and db.scalar(select(Employee.id).where(Employee.unit_id == record.id).limit(1)):
            errors.append("این واحد کارمند دارد؛ ابتدا شعبه و واحد کارکنان را در پرونده‌هایشان تغییر دهید.")
    if record:
        duplicate = duplicate.where(model.id != record.id)
    if db.scalar(duplicate):
        errors.append("این نام قبلاً ثبت شده است." if kind != "units" else "واحدی با این نام در شعبهٔ انتخاب‌شده وجود دارد.")
    if kind == "positions" and not 1 <= len(values["description"]) <= 3000:
        errors.append("شرح شغل الزامی است و باید حداکثر ۳۰۰۰ نویسه باشد.")
    if errors:
        return org_form_page(request, db, kind, values, errors, record, 400)
    target = record or model()
    setattr(target, field, values[field])
    if kind == "units":
        target.branch_id = branch_id
    if kind == "positions":
        target.description = values["description"]
    db.add(target)
    try:
        db.flush()
        after = {key: getattr(target, key) for key in ([field, "branch_id"] if kind == "units" else [field, "description"] if kind == "positions" else [field])}
        audit(db, request, "edit" if record else "create", kind, target.id, {"before": before, "after": after})
        db.commit()
    except IntegrityError:
        db.rollback()
        return org_form_page(request, db, kind, values, ["اطلاعات ذخیره نشد؛ نام تکراری یا وابستگی سازمانی نامعتبر است."], record, 400)
    return redirect(f"/organization/{kind}?saved=1")


@app.post("/organization/{kind}/new")
def organization_create(request: Request, kind: str, form: dict = Depends(protected_form)):
    org_config(kind)
    with SessionLocal() as db:
        return save_organization(request, db, kind, form)


@app.get("/organization/{kind}/{record_id}/edit", dependencies=[Depends(require_login)])
def organization_edit_page(request: Request, kind: str, record_id: int):
    require_admin(request)
    config = org_config(kind)
    with SessionLocal() as db:
        record = db.get(config["model"], record_id)
        if not record:
            raise HTTPException(404)
        values = {column.name: str(getattr(record, column.name)) for column in config["model"].__table__.columns}
        return org_form_page(request, db, kind, values=values, record=record)


@app.post("/organization/{kind}/{record_id}/edit")
def organization_edit(request: Request, kind: str, record_id: int, form: dict = Depends(protected_form)):
    config = org_config(kind)
    with SessionLocal() as db:
        record = db.get(config["model"], record_id)
        if not record:
            raise HTTPException(404)
        return save_organization(request, db, kind, form, record)


from .modules import router as modules_router
app.include_router(modules_router)
