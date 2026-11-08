"""ST-02 / BR-08 and BR-09: positive, negative and boundary cases."""
import unittest

from app.request_workflow.domain import ReviewError, Reviewer, decision_changes_state, validate_decision


class RequestRules(unittest.TestCase):
    admin = Reviewer(1, "admin")

    def test_tc_02_u01_pending_accepts_both_final_decisions(self):
        for decision in ("approved", "rejected"):
            with self.subTest(decision=decision):
                self.assertTrue(decision_changes_state("pending", decision))

    def test_tc_02_u02_final_identical_retry_does_not_change(self):
        for state in ("approved", "rejected"):
            self.assertFalse(decision_changes_state(state, state))

    def test_tc_02_u03_both_opposite_final_transitions_are_rejected(self):
        for before, after in (("approved", "rejected"), ("rejected", "approved")):
            with self.assertRaises(ReviewError) as caught:
                decision_changes_state(before, after)
            self.assertEqual(caught.exception.status_code, 409)

    def test_tc_02_u04_unknown_stored_state_is_rejected(self):
        with self.assertRaises(ReviewError) as caught:
            decision_changes_state("unknown", "approved")
        self.assertEqual(caught.exception.code, "INVALID_REQUEST_STATE")

    def test_tc_02_u05_invalid_target_is_rejected(self):
        for target in ("pending", "cancelled", None, ""):
            with self.assertRaises(ReviewError):
                decision_changes_state("pending", target)

    def test_tc_02_u06_admin_can_approve_without_notes(self):
        validate_decision("approved", "", self.admin)

    def test_tc_02_u07_rejection_requires_nonblank_reason(self):
        for notes in ("", " ", "\n\t"):
            with self.assertRaises(ReviewError) as caught:
                validate_decision("rejected", notes, self.admin)
            self.assertEqual(caught.exception.code, "REJECTION_REASON_REQUIRED")
        validate_decision("rejected", "دلیل ساختگی", self.admin)

    def test_tc_02_u08_notes_length_boundary(self):
        validate_decision("approved", "x" * 3000, self.admin)
        with self.assertRaises(ReviewError):
            validate_decision("approved", "x" * 3001, self.admin)

    def test_tc_02_u09_non_admin_cannot_decide(self):
        for role in ("hr", "viewer", "unknown"):
            with self.assertRaises(ReviewError) as caught:
                validate_decision("approved", "", Reviewer(2, role))
            self.assertEqual(caught.exception.status_code, 403)

    def test_tc_02_u10_invalid_decision_format(self):
        for decision in ("pending", "APPROVED", "", None):
            with self.assertRaises(ReviewError):
                validate_decision(decision, "reason", self.admin)
