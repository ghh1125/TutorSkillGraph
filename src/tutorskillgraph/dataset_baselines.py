"""Reproduce the published fence regression and link the released GRE tutor outcomes."""

import numpy as np

from .pilot import TASKS, equation_kind, points, read_data, state
from .reason_trials import EXP, ROOT, events, read_json
from .skill_graph import build_graph
from .studentbench_tutor import csv_rows, verified_file


def leave_one_out_ols(features, y):
    x = np.column_stack((np.ones(len(y)), np.asarray(features, dtype=float)))
    predictions = []
    for i in range(len(y)):
        train = np.arange(len(y)) != i
        beta = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
        predictions.append(float(x[i] @ beta))
    return predictions


def fence_models():
    people, logs, commit = read_data(ROOT)
    full = csv_rows(ROOT / "data/raw/sec/anonymized_data.csv")
    outcome = "pct_practice_aligned"
    all_scores = np.array([float(p[outcome]) for p in full])
    groups = np.array([p["condition"] for p in full])
    centered = np.array([v - all_scores[groups == g].mean() for v, g in zip(all_scores, groups)])
    sd = np.sqrt(centered @ centered / (len(full) - len(set(groups))))
    mean_correct = np.mean([float(p["n_practice_correct"]) for p in full])
    original = [[1, int(p["n_practice_fixed"]), int(p["n_practice_correct"]) - mean_correct]
                for p in people.values()]
    z = (np.array([float(p[outcome]) for p in people.values()]) - all_scores.mean()) / sd
    standardized = np.linalg.lstsq(original, z, rcond=None)[0]

    labels = csv_rows(ROOT / "experiments/lesson_revision_pilot/gate_turns.csv")
    source_role = {r["learner"]: r for r in labels}
    ids = sorted(set(people) - {"p019"})
    if set(source_role) != {i for i in ids if state(logs[i]["gate_fence"]) == "corrected"}:
        raise ValueError("Gate role labels do not match corrected items")
    designs = {"authors_ols": [], "plus_help_and_gate_eligibility": [], "plus_equation_form_and_role": []}
    for learner in ids:
        p, lesson = people[learner], logs[learner]
        base = [int(p["n_practice_fixed"]), int(p["n_practice_correct"])]
        label = source_role.get(learner)
        assisted = base + [int(lesson[t]["interaction_count"]) for t in TASKS] + [int(label is not None)]
        role = False
        if label:
            turns = lesson["gate_fence"]["conversation"].split(" || ")
            speaker, _, utterance = turns[int(label["turn"]) - 1].partition(": ")
            if speaker != label["speaker"] or label["anchor"] not in utterance:
                raise ValueError(f"Invalid gate turn for {learner}")
            role = speaker == "user"
        form = equation_kind(lesson["multiple_cost_fence"]["student_answer"])
        designs["authors_ols"].append(base)
        designs["plus_help_and_gate_eligibility"].append(assisted)
        designs["plus_equation_form_and_role"].append(assisted + [form == "length_only", form == "one_of_each", role])
    y = np.array([points(people[i]) for i in ids])
    pred = {k: leave_one_out_ols(v, y) for k, v in designs.items()}
    return {"source_commit": commit, "original": {"all_n": len(full), "socratic_n": len(people),
                "standardized_fixed": float(standardized[1]), "standardized_initial_correct": float(standardized[2])},
            "paired_holdout": {"n": len(ids), "mae_points_of_9": {
                k: float(np.abs(v - y).mean()) for k, v in pred.items()},
                "students": [{"id": learner, "actual": int(y[i]),
                              "predicted": {k: v[i] for k, v in pred.items()}} for i, learner in enumerate(ids)]}}


def gre_outcomes():
    manifest = read_json(EXP / "native_sources.json")
    bank = csv_rows(verified_file("question_bank.csv", manifest))
    by_id = {identifier: q for q in bank for identifier in (q["question_id"], q["source_question_id"])}
    results = []
    for case in read_json(EXP / "cases.json"):
        session = case["session"]
        trajectory = events(session)
        at = next(e for e in trajectory if e["pos"] == case["statement"])
        plan = read_json(verified_file(f"{session}/plan.json", manifest))
        concept = next(c for c in plan["concepts"] if c["concept_id"] == at["concept_id"])
        post = csv_rows(verified_file(f"{session}/post.csv", manifest))
        post_by_pair = {by_id[r["question_id"]]["pair"]: r for r in post}
        if len(post_by_pair) != len(post):
            raise ValueError(f"Repeated posttest pair for {session}")
        matched, unmapped = [], []
        for ref in dict.fromkeys(concept["pretest_evidence"]):
            pre = by_id.get(ref)
            answer = post_by_pair.get(pre["pair"]) if pre else None
            if not answer or by_id[answer["question_id"]]["form"] == pre["form"]:
                unmapped.append(ref)
                continue
            matched.append({"cited_pretest": ref, "pretest_item": pre["question_id"], "pair": pre["pair"],
                            "posttest_item": answer["question_id"], "chosen": answer["student_answer"],
                            "correct": bool(int(answer["is_correct"])), "skipped": answer["skipped"] == "True"})
        reply = None
        intervening = []
        for e in trajectory:
            if e["pos"] <= at["pos"]:
                continue
            if e["event_type"] == "practice_problem_shown":
                break
            if e["event_type"] == "ai_tutor_message":
                if e["practice_problem_id"] == at["practice_problem_id"]:
                    reply = {"event": e["pos"], "text": e["content"], "intervening_events": intervening}
                break
            intervening.append(e["pos"])
        results.append({"session": session, "concept": concept["name"], "student_reason_event": at["pos"],
                        "original_tutor_reply": reply, "linked_form_pairs": matched,
                        "unresolved_pretest_evidence": unmapped})
    return results


def rule_table_comparison():
    """Check whether a flat table with the same evidence selects the same versions."""
    graph = build_graph()
    rows = graph.as_record()["lesson_versions"]
    results = []
    for target in read_json(EXP / "native_targets.json"):
        roles = {k: target[k] for k in ("skill", "material", "observation")}
        matched = graph.retrieve(student=target["session"], **roles)
        flat = sorted(row["id"] for row in rows if row["parent"] and row["source_session"] != target["session"]
                      and all(row[k] == value for k, value in roles.items()))
        results.append({"session": target["session"], "rule_table": flat, "hypergraph": [v.id for v in matched]})
    return results
