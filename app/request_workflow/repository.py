"""PostgreSQL reads, row locks and writes for the request decision module."""
from sqlalchemy import select

from ..database import Employee
from ..hr_models import AuditLog, HrRequest


class RequestReviewRepository:
    def __init__(self, session):
        self.session = session

    def transaction(self):
        return self.session.begin()

    def locked_request(self, request_id):
        return self.session.scalar(select(HrRequest).where(HrRequest.id == request_id).with_for_update())

    def locked_employee(self, employee_id, reviewer):
        query = select(Employee).where(Employee.id == employee_id)
        if reviewer.branch_scope_id:
            query = query.where(Employee.branch_id == reviewer.branch_scope_id)
        if reviewer.unit_scope_id:
            query = query.where(Employee.unit_id == reviewer.unit_scope_id)
        return self.session.scalar(query.with_for_update())

    def has_approved_overlap(self, item):
        # BR-10: inclusive intervals; the employee lock serializes concurrent approvals.
        return self.session.scalar(select(HrRequest.id).where(HrRequest.employee_id == item.employee_id,
            HrRequest.id != item.id, HrRequest.kind.in_(("leave", "travel")), HrRequest.status == "approved",
            HrRequest.start_date <= item.end_date, HrRequest.end_date >= item.start_date)) is not None

    def save_decision(self, item, decision, notes, reviewer_id, reviewed_at):
        previous = item.status
        item.status, item.review_notes, item.reviewed_by, item.reviewed_at = decision, notes, reviewer_id, reviewed_at
        self.session.add(AuditLog(actor_id=reviewer_id, action="review", entity="hr_requests", record_id=item.id,
            details={"decision": decision, "previous_status": previous, "kind": item.kind}))
