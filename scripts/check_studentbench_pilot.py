"""Fetch the frozen ten-session screen and reproduce the verifiable case counts."""
import argparse
import csv
import hashlib
import json
import urllib.request
from collections import Counter
from math import lcm
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/lesson_revision_pilot"
DATA = ROOT / "data/raw/studentbench-pilot"
REV = "304c8d63c726e72b60510bba3a44454fc0726721"
BASE = f"https://huggingface.co/datasets/handshake-ai-research/studentbench/resolve/{REV}/"


def read_csv(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def item_events(events, k):
    return [r for r in events if r["practice_problem_id"].endswith(":" + str(k))]


def evidence_checks(manifest):
    names = sorted(name for name in manifest["files"] if name.startswith("task_id_"))
    coverage = {}
    for name in names:
        events = read_csv(name)
        shown = {r["practice_problem_id"] for r in events if r["event_type"] == "practice_problem_shown"}
        coverage[name] = {"event_rows": len(events), "distinct_items_shown": len(shown)}
    first = read_csv("task_id_0147.csv")
    event = {int(r["trajectory_position"]): r for r in first}
    finals = {}
    for r in first:
        if int(r["trajectory_position"]) >= 36:
            break
        if r["event_type"] == "practice_answer_submitted":
            finals[r["practice_problem_id"]] = [r["submitted_answer"], r["is_correct"]]
    if len(finals) != 5 or any(pair != ["D", "True"] for pair in finals.values()):
        raise ValueError("Recheck the selection-pattern case")
    if "safe answer choice" not in event[36]["content"] or event[36]["actor"] != "student":
        raise ValueError("Student's question not found at its anchor")
    # On this new problem the statement precedes the first tutor message for it.
    current = item_events(first, 13857)
    if any(r["event_type"] == "ai_tutor_message" and int(r["trajectory_position"]) < 36 for r in current):
        raise ValueError("Unexpected prior hint")
    bank = {r["question_id"]: r for r in read_csv("question_bank_quant.csv")}
    post = []
    for r in read_csv("0147_posttest.csv"):
        q = bank[r["question_id"]]
        if q["format_code"] == "QC":
            post.append({"item": q["question_id"], "choice": r["student_answer"], "key": q["correct_answer"]})
    second = read_csv("task_id_0105.csv")
    selected = item_events(second, 12180)
    first_response = next(r for r in selected if r["event_type"] in
                          ("practice_answer_submitted", "ai_tutor_message", "student_message"))
    if first_response["trajectory_position"] != "135" or "37/150" not in first_response["content"]:
        raise ValueError("Recheck unprompted inclusion-exclusion response")
    if not any(r["trajectory_position"] == "139" and r["submitted_answer"] == "A"
               and r["is_correct"] == "True" for r in selected):
        raise ValueError("Expected a correct subsequent submission for this item")
    inclusion = {n: 150 // n for n in (6, 8, lcm(6, 8))}
    # Evaluate the algebraic sign in the proposed matched pair. For all real x,
    # A-B = x*(x-1)*(x*x+1). Under x>1 all factors are positive.
    def difference(x):
        return x**4 + x**2 - (x**3 + x)
    return {
        "revision": REV, "coverage": coverage,
        "case_0147": {
            "history_final_answers_before_message_36": finals,
            "student_statement_event": 36, "later_tutor_feedback": [38, 40],
            "later_exam_qc": post,
            "exam_choice_counts": dict(Counter(r["choice"] for r in post)),
            "exam_qc_correct": sum(r["choice"] == r["key"] for r in post),
            "original_item": 13806, "original_domain": "real x",
            "original_witness_differences": {str(x): difference(x) for x in (0.5, 2)},
            "revised_domain": "x > 1", "revised_answer": "A",
            "guess_D_prediction_in_both": "D",
            "actual_student_response_to_revised_item": None,
        },
        "case_0105": {"earlier_reason_events": [123, 129], "later_source_item": 12180,
                      "later_reason_event": 135, "next_tutor_event": 136,
                      "later_correct_submission": 139, "counts_in_1_to_150": inclusion,
                      "union_count": inclusion[6] + inclusion[8] - inclusion[24]},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Download missing files from pinned HF revision")
    args = parser.parse_args()
    manifest = json.loads((OUT / "studentbench_sources.json").read_text(encoding="utf-8"))
    DATA.mkdir(parents=True, exist_ok=True)
    for name, record in manifest["files"].items():
        path = DATA / name
        if not path.exists() and args.fetch:
            with urllib.request.urlopen(BASE + record["path"], timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise ValueError(f"Upstream hash mismatch: {name}")
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Local hash mismatch: {name}")
    result = evidence_checks(manifest)
    (OUT / "studentbench_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
    print("Checked", len(result["coverage"]), "sessions. 0147 QC choices:", result["case_0147"]["exam_choice_counts"])
