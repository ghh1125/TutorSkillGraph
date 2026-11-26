"""Compare held-out learners using only information available when the gate activity ends."""

import csv
from collections import Counter

import numpy as np

from .pilot import loo_ridge, points, state


def compare(base, augmented, scores):
    predictions = np.vstack([loo_ridge(design, scores) for design in (base, augmented)])
    errors = np.abs(predictions - scores)
    gain = errors[0] - errors[1]
    boot = np.random.default_rng(20261122).choice(gain, (10000, len(gain))).mean(axis=1)
    return {
        "mae": errors.mean(axis=1).tolist(), "mae_reduction": float(gain.mean()),
        "conditional_interval": np.quantile(boot, [0.025, 0.975]).tolist(),
        "improved": int((gain > 1e-10).sum()), "worsened": int((gain < -1e-10).sum()),
        "predictions": predictions.T.tolist(),
    }


def run_gate(root, people, logs):
    with (root / "experiments/lesson_revision_pilot/gate_turns.csv").open(encoding="utf-8",
                                                                        newline="") as file:
        labels = list(csv.DictReader(file))
    ids = [r["learner"] for r in labels]
    expected = {k for k, tasks in logs.items() if k != "p019" and state(tasks["gate_fence"]) == "corrected"}
    if len(ids) != len(expected) or set(ids) != expected:
        raise ValueError("Gate annotations do not cover each eligible learner once")
    base, speaker, initial, ambiguous, scores = [], [], [], [], []
    for r in labels:
        learner, turn = r["learner"], int(r["turn"])
        gate = logs[learner]["gate_fence"]
        who, _, words = gate["conversation"].split(" || ")[turn - 1].partition(": ")
        if who != r["speaker"] or not r["anchor"] or r["anchor"] not in words:
            raise ValueError(f"Check source anchor for {learner} at turn {turn}")
        base.append([float(people[learner]["pct_pretest"]), int(gate["interaction_count"])])
        speaker.append(int(who == "user"))
        initial.append(int(turn == 1))
        ambiguous.append(bool(r["alternative_speaker"]))
        scores.append(points(people[learner]))
    x, y = np.array(base), np.array(scores)
    plus = np.column_stack((x, speaker))
    initial_baseline = np.column_stack((x, initial))
    clear = ~np.array(ambiguous)
    return {
        "order_for_predictions": ids, "scores": scores,
        "counts": dict(Counter(r["speaker"] for r in labels)),
        "first_turn_student": sum(initial), "n_excluded_in_sensitivity": sum(ambiguous),
        "help_vs_plus_speaker": compare(x, plus, y),
        "initial_content_vs_plus_speaker": compare(initial_baseline,
                                                   np.column_stack((initial_baseline, speaker)), y),
        "excluding_ambiguous": compare(x[clear], plus[clear], y[clear]),
        "order_excluding_ambiguous": [learner for learner, keep in zip(ids, clear) if keep],
    }
