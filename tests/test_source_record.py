import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tutorskillgraph.build import build


class SourceRecordTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "data/raw/sec/anonymized_data.csv").is_file(),
                         "Fetch the pinned dataset for the end-to-end source check")
    def test_real_record_keeps_item_answers_unknown_and_predictions_separate(self):
        with TemporaryDirectory(dir=ROOT) as temp:
            out = Path(temp)
            build(ROOT / "data/raw/sec", ROOT / "data/sec_source.json", out)
            case = json.loads((out / "p019.json").read_text(encoding="utf-8"))
            observed = case["observed"]
            self.assertEqual(observed["learner"], "p019")
            self.assertEqual(observed["log"]["record"], 55)
            self.assertEqual(observed["turns"][6]["excerpt"], "2x+2y-10=500")
            score = observed["independent_assessment"]
            self.assertAlmostEqual(float(score["raw_fraction"]) * score["max_points"], 6)
            self.assertIsNone(score["item_answer"])
            self.assertIsNone(score["item_reason"])
            self.assertIsNone(score["item_score"])
            self.assertIsNone(case["proposed"]["observed_probe_response"])
            self.assertEqual(case["proposed"]["current_decision"], "待取证")
            self.assertIn("6/9", (out / "p019.zh-CN.md").read_text(encoding="utf-8"))
