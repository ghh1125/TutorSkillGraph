"""Compare certificates to released practice grades and measure old-index coverage on CPU."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.diagnostic_math import comparison
from tutorskillgraph.grounded_skill import Phase, observation
from tutorskillgraph.grounded_trials import EXP, RUNS, observation_at, rows_for, source
from tutorskillgraph.reason_trials import read_json, windows, write_json
from tutorskillgraph.skill_graph import build_graph


def grade_agreement(manifest, selected):
    results = []
    for sid in manifest["sessions"]:
        if sid in {"task_id_0104", "task_id_0108"}:
            continue
        plan_items = {}
        if sid in selected:
            plan = read_json(source(manifest, sid, "plan.json"))
            plan_items = {
                p["practice_problem_id"]: p["correct_answer"]
                for c in plan["concepts"]
                for p in c["practice_problems"]
                if p.get("correct_answer") in {"A", "B", "C", "D"}
            }
        seen = set()
        for block in windows(rows_for(manifest, sid)):
            shown = block[0]
            problem = shown["practice_problem_id"]
            item = comparison(shown["content"])
            if not item or problem in seen:
                continue
            attempt = next(
                (
                    e
                    for e in block[1:]
                    if e["event_type"] == "practice_answer_submitted"
                    and e["practice_problem_id"] == problem
                ),
                None,
            )
            if not attempt or attempt["submitted_answer"] not in {"A", "B", "C", "D"}:
                continue
            seen.add(problem)
            correct = attempt["is_correct"] == "True"
            results.append(
                {
                    "session": sid,
                    "shown": shown["pos"],
                    "attempt": attempt["pos"],
                    "family": item.family,
                    "submitted": attempt["submitted_answer"],
                    "native_mark": correct,
                    "math_key": item.key,
                    "agree": (attempt["submitted_answer"] == item.key) == correct,
                    "native_plan_key": plan_items.get(problem),
                    "printed_domain_poles": list(item.holes),
                }
            )
    return results


def old_adapter(turn, event):
    """Expose the previous graph only to observable tags from its published vocabulary."""
    if isinstance(turn.item, Phase):
        skill, material = "partition_work", "changing_team"
    else:
        skill = "test_admissible_cases"
        if turn.item.family == "absolute":
            material = "absolute_value_comparison"
        elif observation(turn) == "exponent_size_claim" and len(turn.item.names) == 1:
            material = "positive_base_power_comparison"
        elif turn.item.family in {"powers", "constant_powers", "exponential"}:
            material = "power_comparison"
        elif turn.item.family == "rational" and len(turn.item.names) == 2:
            material = "joint_constraints"
        else:
            return None
    if turn.state == "proof":
        state = "independent_justification"
    elif observation(turn) == "exponent_size_claim":
        state = "justifies_by_exponent_size_alone"
    elif event["event_type"] == "practice_answer_submitted" and not turn.learner:
        state = "choice_without_work"
    else:
        return None
    return {"skill": skill, "material": material, "observation": state}


def main():
    manifest = read_json(EXP / "sources.json")
    design = read_json(RUNS / "design_lock.json")
    legacy = build_graph()
    coverage, native_scores = [], []
    for case in design["cases"]:
        sid = case["session"]
        _, block, turn = observation_at(case, manifest)
        event = next(e for e in block if e["pos"] == case["cutoff"])
        query = old_adapter(turn, event)
        versions = legacy.retrieve(student=sid, **query) if query else []
        notes = {v.instruction for v in versions}
        note = notes.pop() if len(notes) == 1 else ""
        coverage.append(
            {
                "session": sid,
                "projected_old_tags": query,
                "old_version": [v.id for v in versions],
                "old_equals_official": not bool(note),
                "old_equals_grounded": note == case["plan_addition"],
                "grounded_edit": bool(case["plan_addition"]),
                "flat_equals_graph": case["same_edit_with_flat_table"],
            }
        )
        meta = read_json(source(manifest, sid, "student.json"))
        native_scores.append(
            {
                "session": sid,
                "historical_pre": meta["pretest_score_points"],
                "historical_post": meta["posttest_score_points"],
                "out_of": meta["assessment_max_score_points"],
                "replayed_post": None,
            }
        )
    grades = grade_agreement(manifest, {c["session"] for c in design["cases"]})
    linked = [g for g in grades if g["native_plan_key"]]
    memory = read_json(EXP / "memory.json")["episodes"]
    summary = {
        "construction": {
            "considered_sessions": len(read_json(EXP.parent / "reason_ablation/sources.json")["files"]),
            "represented_sessions": len({e["session"] for e in memory}),
            "episodes": len(memory),
            "source_exercises": len({(e["session"], e["shown"]) for e in memory}),
            "with_later_evidence": sum(bool(e["later"]) for e in memory),
            "distinct_later_attempts": len(
                {(e["session"], *e["later"][:2]) for e in memory if e["later"]}
            ),
            "moves": dict(Counter(e["move"] for e in memory)),
        },
        "native_grade_agreement": {
            "n": len(grades),
            "agree": sum(g["agree"] for g in grades),
            "students": len({g["session"] for g in grades}),
            "with_printed_domain_poles": sum(bool(g["printed_domain_poles"]) for g in grades),
            "linked_plan_keys": len(linked),
            "plan_key_agrees_with_mark": sum(
                (g["submitted"] == g["native_plan_key"]) == g["native_mark"] for g in linked
            ),
            "math_key_agrees_with_plan": sum(g["math_key"] == g["native_plan_key"] for g in linked),
            "rows": grades,
        },
        "legacy_lookup": coverage,
        "official_pre_post": native_scores,
    }
    write_json(EXP / "evidence_audit.json", summary)
    print(
        "Source episodes",
        len(memory),
        "practice-grade agreement",
        sum(g["agree"] for g in grades),
        "/",
        len(grades),
        "old plan equals official",
        sum(r["old_equals_official"] for r in coverage),
        "/",
        len(coverage),
    )


if __name__ == "__main__":
    main()
