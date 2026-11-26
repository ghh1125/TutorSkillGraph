from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.revision import (
    Decision, ORIGINAL, PROBE, PUBLIC_TEST, ProbeResponse, Reason, assess_probe,
)


class RevisionTests(unittest.TestCase):
    def test_observational_equivalence_and_discrimination(self):
        original = ORIGINAL.predictions()
        self.assertEqual([original["all_openings"]], original["one_opening_only"])
        for task in (PROBE, PUBLIC_TEST):
            row = task.predictions()
            self.assertNotIn(row["all_openings"], row["one_opening_only"])
        self.assertEqual(PROBE.predictions()["all_openings"], "2x + 2y − 20 = 500")
        self.assertEqual(PUBLIC_TEST.predictions()["one_opening_only"],
                         ["2x + 2y − 12 = 500", "2x + 2y − 8 = 500"])

    def test_only_novel_unaided_pre_revision_work_can_trigger_withdrawal(self):
        self.assertEqual(assess_probe(None), Decision.PENDING)
        for eligible in ((False, True, True), (True, False, True), (True, True, False)):
            with self.subTest(eligible=eligible):
                response = ProbeResponse(20, Reason.ACCOUNTS_FOR_BOTH, *eligible)
                self.assertEqual(assess_probe(response), Decision.PENDING)
        good = ProbeResponse(20, Reason.ACCOUNTS_FOR_BOTH, True, True, True)
        self.assertEqual(assess_probe(good), Decision.WITHDRAW)

    def test_value_alone_or_conflict_cannot_settle_a_diagnosis(self):
        trials = [
            (10, Reason.CLAIMS_ONLY_ONE, Decision.TRY),
            (10, Reason.ACCOUNTS_FOR_BOTH, Decision.CLARIFY),
            (20, Reason.CLAIMS_ONLY_ONE, Decision.CLARIFY),
            (10, Reason.UNINFORMATIVE, Decision.CLARIFY),
            (20, Reason.UNINFORMATIVE, Decision.CLARIFY),
            (None, Reason.ACCOUNTS_FOR_BOTH, Decision.CLARIFY),
        ]
        for deduction, reason, expected in trials:
            with self.subTest(deduction=deduction, reason=reason):
                self.assertEqual(assess_probe(ProbeResponse(deduction, reason, True, True, True)),
                                 expected)
