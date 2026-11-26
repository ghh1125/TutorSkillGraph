"""Recompute both dataset comparisons on CPU using their pinned source files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.dataset_baselines import fence_models, gre_outcomes, rule_table_comparison
from tutorskillgraph.reason_trials import EXP, write_json


if __name__ == "__main__":
    fence = fence_models()
    gre = gre_outcomes()
    write_json(EXP / "dataset_baselines.json", {"fence": fence, "gre": gre,
                                                "rule_table_comparison": rule_table_comparison()})
    matched = [q for case in gre for q in case["linked_form_pairs"]]
    print("SEC", fence["original"], fence["paired_holdout"]["mae_points_of_9"])
    print("GRE", len(gre), "students;", len(matched), "concept-linked posttest answers;",
          sum(q["correct"] for q in matched), "correct")
