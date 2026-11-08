"""UC-02 transaction and workflow orchestration; no HTTP or direct SQL."""
from dataclasses import dataclass

from ..hr_models import utc_now
from .domain import ReviewError, decision_changes_state, validate_decision


@dataclass(frozen=True)
class ReviewResult:
    id: int
    kind: str
    changed: bool


class RequestReviewService:
    def __init__(self, repository, clock=utc_now):
        self.repository = repository
        self.clock = clock

    def review(self, request_id, decision, notes, reviewer):
        validate_decision(decision, notes, reviewer)
        with self.repository.transaction():
            item = self.repository.locked_request(request_id)
            if item is None or self.repository.locked_employee(item.employee_id, reviewer) is None:
                raise ReviewError("REQUEST_NOT_FOUND", "درخواست موردنظر پیدا نشد.", 404)
            if item.kind not in ("leave", "travel", "administrative"):
                raise ReviewError("INVALID_REQUEST_KIND", "نوع درخواست معتبر نیست و نیاز به بررسی دارد.", 409)
            changed = decision_changes_state(item.status, decision)
            if changed:
                if decision == "approved" and item.kind in ("leave", "travel") and self.repository.has_approved_overlap(item):
                    raise ReviewError("REQUEST_OVERLAP", "بازهٔ درخواست با مرخصی یا مأموریت تأییدشدهٔ دیگری هم‌پوشانی دارد.", 400)
                self.repository.save_decision(item, decision, notes, reviewer.id, self.clock())
            result = ReviewResult(item.id, item.kind, changed)
        return result
