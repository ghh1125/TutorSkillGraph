"""Learner-level retrospective pilot. Run with scripts/run_idea_pilot.py."""

import ast
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

TASKS = ("gate_fence", "divided_fence", "multiple_cost_fence")
TARGETS = {"weighted": (12, 4), "length_only": (2, 2), "one_of_each": (6, 2)}


def affine(node):
    """Exact (coefficient of x, coefficient of y, constant); reject nonlinear forms."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return (0, 0, Fraction(str(node.value)))
    if isinstance(node, ast.Name) and node.id in ("x", "y"):
        return (int(node.id == "x"), int(node.id == "y"), 0)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        factor = -1 if isinstance(node.op, ast.USub) else 1
        return tuple(factor * x for x in affine(node.operand))
    if isinstance(node, ast.BinOp):
        a, b = affine(node.left), affine(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            sign = 1 if isinstance(node.op, ast.Add) else -1
            return tuple(x + sign * y for x, y in zip(a, b))
        if isinstance(node.op, ast.Mult):
            if a[:2] == (0, 0):
                return tuple(a[2] * x for x in b)
            if b[:2] == (0, 0):
                return tuple(b[2] * x for x in a)
        if isinstance(node.op, ast.Div) and b[:2] == (0, 0) and b[2]:
            return tuple(Fraction(x) / b[2] for x in a)
    raise ValueError("not an affine expression")


def equation_kind(answer):
    s = answer.lower().strip().replace("×", "*").replace("−", "-").replace("$", "")
    for word, op in (("times", "*"), ("plus", "+"), ("equals", "=")):
        s = re.sub(r"\b" + word + r"\b", op, s)
    s = re.sub(r"(?<=[0-9xy)])\s+x\s+(?=[0-9(])", "*", s)
    s = re.sub(r"\s+", "", s)
    if not re.fullmatch(r"[-xy0-9.*/+=()]+", s) or re.search(r"[xy]\d", s):
        return "unclassified"
    s = re.sub(r"(?<=[0-9)])(?=[xy(])|(?<=[xy])(?=\()", "*", s)
    try:
        exprs = [affine(ast.parse(part, mode="eval").body) for part in s.split("=")]
    except (ValueError, SyntaxError, ZeroDivisionError):
        return "unclassified"
    if len(exprs) < 2:
        return "unclassified"
    normalized = set()
    for left, right in zip(exprs, exprs[1:]):
        x, y, c = (a - b for a, b in zip(left, right))
        if (x, y, c) == (0, 0, 0):
            continue
        if not c:
            return "other_equation"
        normalized.add((Fraction(-600 * x) / c, Fraction(-600 * y) / c))
    for kind, signature in TARGETS.items():
        if normalized == {signature}:
            return kind
    return "other_equation"


def read_data(root):
    manifest = json.loads((root / "data/sec_source.json").read_text(encoding="utf-8"))
    data = root / "data/raw/sec"
    for name, expected in manifest["files"].items():
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source changed: {name}")
    def rows(name):
        with (data / name).open(encoding="utf-8-sig", newline="") as src:
            return list(csv.DictReader(src))
    people = {}
    for row in rows("anonymized_data.csv"):
        if row["condition"] == "socratic":
            if row["anon_id"] in people:
                raise ValueError("Duplicate learner")
            people[row["anon_id"]] = row
    logs = defaultdict(dict)
    for record, r in enumerate(rows("anonymized_tutoring_logs.csv"), 2):
        if r["condition"] == "socratic":
            key, objective = r["anon_id"], r["learning_objective"]
            if objective in logs[key]:
                raise ValueError("Duplicate practice item")
            logs[key][objective] = {**r, "csv_record": record}
    if set(people) != set(logs) or any(set(g) != set(TASKS) for g in logs.values()):
        raise ValueError("Socratic panel incomplete")
    return people, logs, manifest["commit"]


def points(person):
    scaled = float(person["pct_practice_aligned"]) * 9
    if not 0 <= scaled <= 9 or not math.isclose(scaled, round(scaled), abs_tol=1e-8):
        raise ValueError("Unexpected aligned-item score")
    return round(scaled)


def state(row):
    if row["initial_correct"] == "TRUE":
        return "initial_correct"
    return "corrected" if row["final_correct"] == "TRUE" else "unresolved"


def gate_bounds(total):
    lo, hi = max(0, total - 6), min(3, total)
    # Farm Gates rubric: A's predicted equation earns 3, B's earns 2.
    return {"min": lo, "max": hi, "A_compatible": lo <= 3 <= hi,
            "B_compatible": lo <= 2 <= hi}


def loo_ridge(X, y):
    """Learn means, scales, coefficients and intercept from training students only."""
    X = np.asarray(X, dtype=float)
    pred = []
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        mean, std = X[mask].mean(axis=0), X[mask].std(axis=0)
        std[std == 0] = 1
        train = (X[mask] - mean) / std
        intercept = y[mask].mean()
        coef = np.linalg.solve(train.T @ train + np.eye(X.shape[1]), train.T @ (y[mask] - intercept))
        pred.append(intercept + ((X[i] - mean) / std) @ coef)
    return np.array(pred)


def run(root):
    people, logs, commit = read_data(root)
    cases, designs = [], [[], [], []]
    for learner in sorted(set(people) - {"p019"}):
        person = people[learner]
        tasks = [logs[learner][task] for task in TASKS]
        gate, divided, cost = tasks
        kind = equation_kind(cost["student_answer"])
        total = points(person)
        cases.append({"id": learner, "prior": state(divided), "gate": state(gate),
                      "divided_csv_record": divided["csv_record"], "cost_csv_record": cost["csv_record"],
                      "first_equation": cost["student_answer"], "equation_kind": kind,
                      "source_correct": cost["initial_correct"] == "TRUE",
                      "posttest_points_of_9": total, "gate_bounds": gate_bounds(total)})
        base = [float(person["pct_pretest"])] + [
            int(t[key] == "TRUE") for t in tasks for key in ("initial_correct", "final_correct")]
        help_adjusted = base + [int(t["interaction_count"]) for t in tasks]
        for design, features in zip(designs, (base, help_adjusted,
                help_adjusted + [kind == "length_only", kind == "one_of_each"])):
            design.append(features)
    y = np.asarray([r["posttest_points_of_9"] for r in cases])
    preds = [loo_ridge(X, y) for X in designs]
    for i, case in enumerate(cases):
        case["heldout_predictions"] = [float(p[i]) for p in preds]
    errors = np.abs(np.asarray(preds) - y)
    gain = errors[1] - errors[2]
    rng = np.random.default_rng(20261122)
    boot = rng.choice(gain, (10000, len(gain))).mean(axis=1)
    coverage = {}
    for group in ("corrected", "initial_correct", "unresolved"):
        subset = [r for r in cases if r["prior"] == group]
        coverage[group] = {"n": len(subset), "source_wrong": sum(not r["source_correct"] for r in subset),
                           "forms": dict(Counter(r["equation_kind"] for r in subset)),
                           "weighted_but_source_wrong": [r["id"] for r in subset if
                               r["equation_kind"] == "weighted" and not r["source_correct"]]}
    gate_corrected = [r for r in cases if r["gate"] == "corrected"]
    compatibility = Counter(
        f"A{int(r['gate_bounds']['A_compatible'])}B{int(r['gate_bounds']['B_compatible'])}"
        for r in gate_corrected)
    return {"source_commit": commit, "n": len(cases), "groups": coverage,
            "gate_corrected_n": len(gate_corrected), "gate_compatibility": dict(compatibility),
            "p019_bounds": gate_bounds(points(people["p019"])),
            "mae": errors.mean(axis=1).tolist(), "gain_M1_minus_M2": float(gain.mean()),
            "conditional_interval": np.quantile(boot, [0.025, 0.975]).tolist(),
            "improved": int((gain > 1e-10).sum()), "worsened": int((gain < -1e-10).sum()),
            "unchanged": int((np.abs(gain) <= 1e-10).sum()), "students": cases}
