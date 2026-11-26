"""Regression checks anchored in the publicly released development classrooms."""

import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.reason_trials import RAW, ROOT, events, windows
from tutorskillgraph.studentbench_tutor import csv_rows


@unittest.skipUnless(
    find_spec("sympy") and (RAW / "task_id_0608.csv").exists(),
    "requires grounded extra and original data",
)
class GroundedTurnTests(unittest.TestCase):
    def test_proof_changes_the_move_on_the_same_math(self):
        from tutorskillgraph.grounded_skill import example_pair, grounded_move, material_for, turn_at

        for sid, shown, learner, expected in (
            ("task_id_0402", 15, 16, "challenge_exponent_shortcut"),
            ("task_id_0608", 13, 15, "acknowledge_proof"),
        ):
            block = next(b for b in windows(events(sid)) if b[0]["pos"] == shown)
            idx = next(i for i, e in enumerate(block) if e["pos"] == learner)
            material = material_for(block[0]["content"])
            turn = turn_at(block[: idx + 1], idx, material)
            self.assertEqual(grounded_move(turn), expected)
            a, b = example_pair(material, turn)
            self.assertTrue(all(v > 0 for v in a + b))
            self.assertNotEqual(material.relation(a), material.relation(b))

    @unittest.skipUnless(
        (ROOT / "data/raw/studentbench-native/task_id_0104/events.csv").exists(),
        "requires the painter case",
    )
    def test_painter_transition_precedes_lunch(self):
        from tutorskillgraph.grounded_skill import phase

        rows = csv_rows(ROOT / "data/raw/studentbench-native/task_id_0104/events.csv")
        self.assertEqual(phase(rows[0]["content"]).boundary, "noon")
