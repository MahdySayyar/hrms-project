"""BR-08 and BR-09: request decisions without HTTP or database dependencies."""
from dataclasses import dataclass
from enum import Enum


class RequestState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewError(Exception):
    def __init__(self, code, message, status_code):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class Reviewer:
    id: int
    role: str
    branch_scope_id: int | None = None
    unit_scope_id: int | None = None


def validate_decision(decision, notes, reviewer):
    if reviewer.role != "admin":
        raise ReviewError("REVIEW_FORBIDDEN", "این بخش فقط برای مدیر منابع انسانی در دسترس است.", 403)
    if decision not in (RequestState.APPROVED.value, RequestState.REJECTED.value) or len(notes) > 3000:
        raise ReviewError("INVALID_REVIEW", "نتیجه یا توضیح بررسی معتبر نیست.", 400)
    if decision == RequestState.REJECTED.value and not notes.strip():
        raise ReviewError("REJECTION_REASON_REQUIRED", "علت رد درخواست را بنویسید.", 400)


def decision_changes_state(current, desired):
    """Return false for an identical retry; reject any conflicting final transition."""
    if desired not in (RequestState.APPROVED.value, RequestState.REJECTED.value):
        raise ReviewError("INVALID_REVIEW", "نتیجهٔ بررسی معتبر نیست.", 400)
    try:
        state = RequestState(current)
    except ValueError:
        raise ReviewError("INVALID_REQUEST_STATE", "وضعیت درخواست معتبر نیست و نیاز به بررسی دارد.", 409) from None
    if state == RequestState.PENDING:
        return True
    if state.value == desired:
        return False
    raise ReviewError("REQUEST_ALREADY_REVIEWED", "این درخواست قبلاً بررسی شده است و نتیجهٔ آن قابل تغییر نیست؛ درخواست جدید ثبت کنید.", 409)
