"""Regression: matched inputs must not disclose the held-out reason or the author's reference."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.reason_trials import EXP, RAW, comparison_case, model_input, read_json
from tutorskillgraph.skill_graph import build_graph
from tutorskillgraph.studentbench_tutor import NATIVE, chat_prefix, csv_rows, requests_for


class PairedInputTests(unittest.TestCase):
    @unittest.skipUnless((RAW / "task_id_0219.csv").exists(), "requires pinned GRE trajectories")
    def test_only_the_current_items_unaided_work_differs(self):
        manifest = read_json(EXP / "sources.json")
        for spec in read_json(EXP / "cases.json"):
            case = comparison_case(spec, manifest)
            for view in ("text", "table", "hypergraph"):
                baseline = model_input(case, view, False)
                treatment = copy.deepcopy(model_input(case, view, True))
                work = treatment["later_item_before_feedback"]["first_response_work"]
                self.assertEqual(work, case["later"]["reason"])
                self.assertNotIn(work, str(baseline))
                treatment["later_item_before_feedback"]["first_response_work"] = None
                self.assertEqual(treatment, baseline)
                self.assertNotIn("reference", baseline)
            self.assertLess(max(r["event"] for r in case["record"]), case["later"]["item_event"])

    @unittest.skipUnless((NATIVE / "task_id_0104/events.csv").exists() and (RAW / "task_id_0219.csv").exists(),
                         "requires pinned native data and construction trajectories")
    def test_native_replay_has_one_edit_and_no_future_turns(self):
        graph = build_graph()
        manifest = read_json(EXP / "native_sources.json")
        for target in read_json(EXP / "native_targets.json"):
            pair, entry = requests_for(target, graph, manifest)
            old, new = pair["original_plan"], dict(pair["skill_plan"])
            self.assertTrue(entry["matched_versions"])
            self.assertTrue(all(graph.versions[v].source_session != target["session"]
                                for v in entry["matched_versions"]))
            self.assertIn(entry["plan_addition"], new["instructions"])
            new["instructions"] = new["instructions"].replace("\n" + entry["plan_addition"], "", 1)
            self.assertEqual(old, new)
            files = NATIVE / target["session"]
            plan = read_json(files / "plan.json")
            concept = next(c for c in plan["concepts"] if c["concept_id"] == entry["concept"])
            rows = csv_rows(files / "events.csv")
            prefix = [r for r in rows if int(r["trajectory_position"]) <= target["cutoff"]]
            self.assertEqual(old["input"], chat_prefix(plan, concept, prefix, target["cutoff"]))
            next_reply = next(r["content"] for r in rows if int(r["trajectory_position"]) > target["cutoff"]
                              and r["event_type"] == "ai_tutor_message")
            self.assertNotIn(next_reply, str(old["input"]))
