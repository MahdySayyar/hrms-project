"""تعریف فرم‌ها و برچسب‌های فارسی ماژول‌ها؛ بدون لایهٔ سرویس یا مخزن."""
from .hr_models import (Attendance, Candidate, CareerPlan, EmploymentContract, Evaluation, HrRequest, Interview,
                        PayrollProfile, PayrollRule, Shift, Training, TrainingEnrollment)
from .database import Admin

CONTRACT_TYPES = {value: value for value in ("دائم", "مدت‌معین", "پیمانکاری", "آزمایشی")}
CANDIDATE_STATES = {"new": "ثبت اولیه", "review": "بررسی رزومه", "interview": "مصاحبه", "accepted": "پذیرفته‌شده", "rejected": "ردشده", "hired": "استخدام‌شده"}
REQUEST_STATES = {"pending": "در انتظار تأیید", "approved": "تأییدشده", "rejected": "ردشده"}
CONTRACT_STATES = {"draft": "پیش‌نویس", "active": "فعال", "renewed": "تمدیدشده", "ended": "خاتمه‌یافته"}
INTERVIEW_RESULTS = {"pending": "در انتظار مصاحبه", "passed": "قبول", "failed": "رد"}


def field(name, label, kind="text", required=True, **options):
    return {"name": name, "label": label, "kind": kind, "required": required, **options}


def pick(name, label, source=None, choices=None, required=True):
    return field(name, label, "select", required, source=source, choices=choices)


def money(name, label, required=True):
    return field(name, label + " (ریال)", "number", required, minimum=0, maximum=1_000_000_000)


EMPLOYEE = pick("employee_id", "کارمند", source="employees")
DATE = lambda name, label: field(name, label + " (میلادی)", "date")
NOTES = field("notes", "یادداشت", "textarea", False, maximum_length=3000)

MODULES = {
    "candidates": {"model": Candidate, "title": "استخدام و متقاضیان", "singular": "متقاضی", "columns": ["first_name", "last_name", "position_id", "application_date", "status"], "fields": [
        field("first_name", "نام", maximum_length=80), field("last_name", "نام خانوادگی", maximum_length=80),
        field("national_id", "کد ملی", maximum_length=10), field("phone", "شمارهٔ همراه", maximum_length=11), field("email", "ایمیل", "email", False, maximum_length=254),
        pick("branch_id", "شعبه", "branches"), pick("unit_id", "واحد", "units"), pick("position_id", "سمت مورد تقاضا", "positions"),
        DATE("application_date", "تاریخ درخواست"), pick("status", "وضعیت بررسی", choices={key: value for key, value in CANDIDATE_STATES.items() if key != "hired"}), NOTES]},
    "interviews": {"model": Interview, "title": "مصاحبه‌ها", "singular": "مصاحبه", "columns": ["candidate_id", "scheduled_at", "interviewer", "result"], "fields": [
        pick("candidate_id", "متقاضی", "candidates"), field("scheduled_at", "زمان مصاحبه (میلادی، ساعت محلی)", "datetime-local"), field("interviewer", "نام مصاحبه‌کننده", maximum_length=100),
        pick("result", "نتیجه", choices=INTERVIEW_RESULTS), NOTES]},
    "shifts": {"model": Shift, "title": "شیفت‌های کاری", "singular": "شیفت", "columns": ["name", "start_time", "end_time", "break_minutes"], "fields": [
        field("name", "نام شیفت", maximum_length=100), field("start_time", "ساعت شروع", "time"), field("end_time", "ساعت پایان", "time"),
        field("break_minutes", "استراحت بدون کار (دقیقه)", "number", minimum=0, maximum=240)]},
    "attendance": {"model": Attendance, "title": "حضور، غیاب و اضافه‌کاری", "singular": "تردد", "columns": ["employee_id", "work_date", "presence_status", "shift_id", "worked_minutes", "overtime_minutes"], "fields": [
        EMPLOYEE, DATE("work_date", "روز شروع کار"), pick("shift_id", "شیفت", "shifts"), field("presence_status", "وضعیت حضور", "select", choices={"present": "حاضر", "absent": "غایب"}, default="present"), field("clock_in", "ساعت ورود؛ برای حضور الزامی", "time", False), field("clock_out", "ساعت خروج؛ برای حضور الزامی", "time", False), NOTES],
        "description": "کارکرد و اضافه‌کاری از ساعت ورود، خروج و استراحت شیفت محاسبه می‌شود. شیفت شب نیز پشتیبانی می‌شود."},
    "leave": {"model": HrRequest, "title": "مرخصی‌ها", "singular": "درخواست مرخصی", "columns": ["employee_id", "start_date", "end_date", "leave_type", "status"], "fields": [
        EMPLOYEE, DATE("start_date", "شروع مرخصی"), DATE("end_date", "پایان مرخصی"), pick("leave_type", "نوع مرخصی", choices={"annual": "استحقاقی", "sick": "استعلاجی", "unpaid": "بدون حقوق"}), field("description", "علت درخواست", "textarea", maximum_length=3000)],
        "description": "درخواست را ثبت کنید؛ تأیید یا رد با مدیر منابع انسانی و در یک مرحله انجام می‌شود."},
    "administrative": {"model": HrRequest, "title": "درخواست‌های اداری", "singular": "درخواست اداری", "columns": ["employee_id", "start_date", "description", "status"], "fields": [
        EMPLOYEE, DATE("start_date", "تاریخ درخواست"), field("description", "موضوع و شرح درخواست", "textarea", maximum_length=3000)]},
    "travel": {"model": HrRequest, "title": "مأموریت‌ها", "singular": "درخواست مأموریت", "columns": ["employee_id", "start_date", "end_date", "destination", "status"], "fields": [
        EMPLOYEE, DATE("start_date", "شروع مأموریت"), DATE("end_date", "پایان مأموریت"), field("destination", "مقصد", maximum_length=150), field("description", "هدف مأموریت", "textarea", maximum_length=3000)]},
    "payroll-rules": {"model": PayrollRule, "title": "قواعد آموزشی حقوق", "singular": "قاعدهٔ محاسبه", "admin_only": True, "columns": ["contract_type", "calculation_mode", "overtime_factor", "insurance_percent", "tax_percent"], "fields": [
        pick("contract_type", "نوع قرارداد", choices=CONTRACT_TYPES), pick("calculation_mode", "مبنای محاسبه", choices={"monthly": "حقوق ثابت ماهانه", "hourly": "کارکرد ساعتی"}),
        field("monthly_hours", "ساعت مبنای ماهانه", "decimal", minimum=1, maximum=744), field("overtime_factor", "ضریب اضافه‌کاری", "decimal", minimum=1, maximum=10),
        field("insurance_percent", "درصد کسر بیمه از ناخالص", "decimal", minimum=0, maximum=100), field("tax_percent", "درصد کسر مالیات از ناخالص", "decimal", minimum=0, maximum=100), NOTES],
        "description": "این قواعد صرفاً آموزشی‌اند. نرخ‌ها را خودتان وارد کنید؛ هیچ نرخ قانونی پیش‌فرضی اعمال نمی‌شود."},
    "payroll-profiles": {"model": PayrollProfile, "title": "اطلاعات پرداخت کارکنان", "singular": "پروفایل پرداخت", "admin_only": True, "columns": ["employee_id", "base_salary", "hourly_rate", "benefits", "deductions"], "fields": [
        EMPLOYEE, money("base_salary", "حقوق پایهٔ ماهانه"), money("hourly_rate", "نرخ کارکرد ساعتی"), money("benefits", "مزایای ثابت دوره"), money("deductions", "سایر کسورات دوره")],
        "description": "مبالغ به ریال و آموزشی‌اند. کسر مرخصی، جریمه و تعدیلات توافقی را در سایر کسورات وارد کنید؛ قواعد قانونی فرض نمی‌شوند."},
    "contracts": {"model": EmploymentContract, "title": "قراردادها و تمدید", "singular": "قرارداد", "columns": ["employee_id", "contract_type", "start_date", "end_date", "status"], "fields": [
        EMPLOYEE, pick("contract_type", "نوع قرارداد", choices=CONTRACT_TYPES), DATE("start_date", "شروع قرارداد"), field("end_date", "پایان قرارداد (میلادی، اختیاری برای دائم)", "date", False), money("base_salary", "حقوق پایهٔ توافقی"), NOTES],
        "description": "قرارداد ابتدا پیش‌نویس است. با فعال‌سازی، نوع قرارداد فعلی کارمند و حقوق پایهٔ پروفایل پرداخت به‌روز می‌شود. قرارداد آینده را پس از رسیدن تاریخ شروع فعال کنید."},
    "evaluations": {"model": Evaluation, "title": "ارزیابی عملکرد", "singular": "ارزیابی", "columns": ["employee_id", "review_date", "score", "goals"], "fields": [
        EMPLOYEE, DATE("review_date", "تاریخ ارزیابی"), field("score", "امتیاز از ۱۰۰", "number", minimum=0, maximum=100), field("feedback", "بازخورد ارزیابی", "textarea", maximum_length=3000), field("goals", "هدف‌های دورهٔ بعد", "textarea", maximum_length=3000)]},
    "trainings": {"model": Training, "title": "دوره‌های آموزشی", "singular": "دوره", "columns": ["title", "training_date", "capacity", "description"], "fields": [
        field("title", "عنوان دوره", maximum_length=150), DATE("training_date", "تاریخ دوره"), field("capacity", "ظرفیت دوره", "number", minimum=1, maximum=10000), field("description", "شرح دوره", "textarea", maximum_length=3000)]},
    "enrollments": {"model": TrainingEnrollment, "title": "ثبت‌نام و سوابق آموزش", "singular": "ثبت‌نام", "columns": ["employee_id", "training_id", "status"], "fields": [
        EMPLOYEE, pick("training_id", "دوره", "trainings"), pick("status", "وضعیت شرکت", choices={"planned": "ثبت‌نام‌شده", "completed": "تکمیل‌شده", "cancelled": "لغوشده"}), NOTES]},
    "career": {"model": CareerPlan, "title": "برنامهٔ توسعهٔ شغلی", "singular": "برنامهٔ توسعه", "columns": ["employee_id", "target_position_id", "target_date", "progress"], "fields": [
        EMPLOYEE, pick("target_position_id", "سمت هدف", "positions"), DATE("target_date", "تاریخ هدف"), field("progress", "پیشرفت (درصد)", "number", minimum=0, maximum=100), field("actions", "اقدام‌های لازم برای توسعه", "textarea", maximum_length=3000)]},
    "users": {"model": Admin, "title": "کاربران و دسترسی‌ها", "singular": "کاربر", "admin_only": True, "columns": ["username", "display_name", "role", "branch_scope_id", "unit_scope_id", "is_active"], "fields": [
        field("username", "نام کاربری", maximum_length=50), field("display_name", "نام نمایشی", maximum_length=100), field("password", "رمز اولیه؛ در ویرایش خالی بگذارید", "password", False),
        pick("role", "نقش", choices={"admin": "مدیر منابع انسانی", "hr": "کارشناس منابع انسانی", "viewer": "مشاهده‌گر گزارش‌های کلی", "member": "کاربر عادی"}),
        pick("branch_scope_id", "محدودهٔ شعبه؛ خالی یعنی کل سازمان", "branches_all", required=False), pick("unit_scope_id", "محدودهٔ واحد؛ اختیاری", "units_all", required=False),
        pick("is_active", "وضعیت حساب", choices={"true": "فعال", "false": "غیرفعال"})],
        "description": "مدیر به همهٔ بخش‌ها دسترسی دارد. کارشناس فقط اطلاعات پرسنلی محدودهٔ خود را مدیریت می‌کند و حقوق، تأیید درخواست، کاربران و سابقهٔ تغییرات را نمی‌بیند. مشاهده‌گر فقط گزارش‌های کلی را می‌بیند."},
}

LABELS = {field["name"]: field["label"] for config in MODULES.values() for field in config["fields"]}
LABELS.update({"status": "وضعیت", "worked_minutes": "کارکرد (دقیقه)", "overtime_minutes": "اضافه‌کاری (دقیقه)", "required_minutes": "کارکرد مورد انتظار (دقیقه)", "review_notes": "توضیح بررسی", "reviewed_at": "زمان بررسی", "reviewed_by": "بررسی‌کننده", "completed": "انجام شده", "period": "دورهٔ میلادی", "net_amount": "خالص پرداخت (ریال)"})
