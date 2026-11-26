"""Read StudentBench events and assemble comparison inputs from source anchors."""

import csv
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments/reason_ablation"
RAW = ROOT / "data/raw/studentbench-reasons"
REV = "304c8d63c726e72b60510bba3a44454fc0726721"
ARM = "1_main_leaderboard_data/gre_quant/ai_arm_gemini-3.1-pro-high"
HUB = "https://huggingface.co/datasets/handshake-ai-research/studentbench"
TRAJECTORY = "ai_tutoring_data/student_ai_tutor_interaction_trajectory.csv"


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def events(session):
    with (RAW / f"{session}.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    for r in rows:
        r["pos"] = int(r["trajectory_position"])
    if any(a["pos"] >= b["pos"] for a, b in zip(rows, rows[1:])):
        raise ValueError(f"Unordered trajectory: {session}")
    return rows


def windows(rows):
    """Split on what the student actually saw, never on future item creation."""
    blocks = []
    for r in rows:
        if r["event_type"] == "practice_problem_shown":
            blocks.append([r])
        elif blocks:
            blocks[-1].append(r)
    return blocks


def candidates(rows):
    """Recall only. Temporal and topic alignment still require content review."""
    history = []
    for block in windows(rows):
        shown = block[0]
        item = shown["practice_problem_id"]
        prefix = []
        for r in block[1:]:
            if r["event_type"] in ("practice_answer_submitted", "ai_tutor_message"):
                break
            if r["event_type"] == "student_message" and r["practice_problem_id"] == item:
                prefix.append(r)
        prior = [b for b in history if b[0]["concept_id"] == shown["concept_id"]
                 and b[0]["practice_problem_id"] != item]
        if prior and prefix:
            yield shown, prefix, prior
        actual = [r for r in block if r["practice_problem_id"] == item]
        attempts = [r for r in actual if r["event_type"] == "practice_answer_submitted"]
        if (attempts and attempts[-1]["is_correct"] == "True"
                and any(r["event_type"] == "ai_tutor_message" for r in actual)):
            history.append(block)


def comparison_case(case, manifest):
    """Keep the observed original lesson, later feedback, and investigator reference separate."""
    session = case["session"]
    if digest(RAW / f"{session}.csv") != manifest["files"][session]:
        raise ValueError(f"Source hash mismatch for {session}")
    rows = events(session)
    by_position = {r["pos"]: r for r in rows}
    probe, prefix, priors = next(c for c in candidates(rows) if c[0]["pos"] == case["probe"])
    old = next(b for b in priors if b[0]["pos"] == case["old"])
    original_id = old[0]["practice_problem_id"]
    reason = next(r for r in prefix if r["pos"] == case["statement"])
    allowed = {r["pos"] for r in old if r["practice_problem_id"] == original_id}
    turns = case["turns"]
    if turns != sorted(set(turns)) or not set(turns) <= allowed:
        raise ValueError(f"Invalid original lesson anchors: {session}")
    if not any(by_position[t]["is_correct"] == "True" for t in turns):
        raise ValueError(f"Missing original correct submission: {session}")
    transcript = []
    for pos in [case["old"], *turns]:
        r = by_position[pos]
        content = r["content"] or f"Submitted {r['submitted_answer']} (correct: {r['is_correct']})."
        transcript.append({"event": pos, "role": r["actor"], "text": content})
    # Each account of the lesson references the same ordered evidence. Its
    # student statements can be located in the full text in any representation.
    student = [r["event"] for r in transcript if r["role"] == "student"]
    teacher = [r["event"] for r in transcript if r["role"] == "ai_tutor"]
    if not teacher or not student:
        raise ValueError(f"Missing speaker roles in {session}")
    when = case["review_turn"]
    if when not in teacher:
        raise ValueError(f"Review point must be a real tutor event in {session}")
    options = {
        "retain": "Keep this lesson step for similar circumstances without targeted reteaching.",
        "change1": case["change1"], "change2": case["change2"],
        "probe": "First elicit one unaided explanation on a fresh example; defer a targeted edit.",
    }
    keys = sorted(options)
    random.Random(session).shuffle(keys)
    option_map = dict(zip("ABCD", keys))
    return {
        "case": session, "version": f"{session}/lesson/{case['old']}/v1",
        "source": f"{HUB}/blob/{REV}/{ARM}/{session}/{TRAJECTORY}",
        "record": transcript,
        "design": {"original_material_event": case["old"], "learner_events": student,
                   "tutor_events": teacher, "ordered_events": turns, "teaching_step": case["skill"],
                   "review_turn": when, "prior_visible_events": [r["event"] for r in transcript if r["event"] < when],
                   "intended_learner_step": case["learner_step"]},
        "later": {"item_event": case["probe"], "item": probe["content"], "answer": case["answer"],
                  "math_key": case["correct_answer"], "response_event": reason["pos"], "reason": reason["content"]},
        "options": {letter: options[key] for letter, key in option_map.items()},
        "option_map": option_map,
    }


def represent(case, view):
    d = case["design"]
    slots = [("material", d["original_material_event"]), ("learner actions", d["learner_events"]),
             ("tutor actions", d["tutor_events"]), ("execution order", d["ordered_events"]),
             ("teaching step", d["teaching_step"]), ("reviewed tutor turn", d["review_turn"]),
             ("events visible before that turn", d["prior_visible_events"]),
             ("step intended for the learner", d["intended_learner_step"])]
    if view == "table":
        return [{"role": k, "value": v} for k, v in slots]
    if view == "hypergraph":
        return {"nodes": [{"id": i, "value": v} for i, (_, v) in enumerate(slots)],
                "hyperedge": {"version": case["version"],
                              "incidences": [{"role": k, "node": i} for i, (k, _) in enumerate(slots)]}}
    if view != "text":
        raise ValueError(f"Unsupported view: {view}")
    return (f"The lesson uses the material at event {slots[0][1]}. The learner's actions are at "
            f"{slots[1][1]}. The tutor's actions are at {slots[2][1]}. Their order is {slots[3][1]}. "
            f"The teaching step being reviewed is: {slots[4][1]} At turn {slots[5][1]}, only "
            f"{slots[6][1]} in these excerpts preceded the tutor's move. The learner was to do this: {slots[7][1]}")


def model_input(case, view, with_reason):
    later = {k: v for k, v in case["later"].items() if k != "reason"}
    later["first_response_work"] = case["later"]["reason"] if with_reason else None
    return {"lesson_version": case["version"], "observed_earlier_events": case["record"],
            "researcher_description_of_lesson": represent(case, view),
            "later_item_before_feedback": later, "candidate_actions": case["options"]}
