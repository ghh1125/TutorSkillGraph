"""Read only observations from the pinned Scaffolded Error Correction release."""

import csv
import hashlib
import json
from pathlib import Path


def locate(csv_path: Path, **key: str) -> tuple[dict, dict]:
    """Keep logical and physical positions even when a CSV cell spans lines."""
    matches = []
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(key).issubset(reader.fieldnames or []):
            raise ValueError(f"Missing join columns in {csv_path.name}")
        start = reader.line_num + 1
        for record, row in enumerate(reader, 2):
            if all(row[k] == v for k, v in key.items()):
                matches.append((row, {"file": csv_path.name, "record": record,
                                      "first_line": start, "last_line": reader.line_num}))
            start = reader.line_num + 1
    if len(matches) != 1:
        raise ValueError(f"Expected one record for {key}, found {len(matches)}")
    return matches[0]


# These paraphrases describe utterances. Each anchor is an exact, short substring.
TURN_NOTES = (
    (1, "user", "x+2y=500", "学生提交初答。"),
    (2, "assistant", "no gate at all", "导师先问没有门洞时，矩形的完整周长是多少。"),
    (3, "user", "2x+2y=500", "学生写出没有门洞时的方程。"),
    (4, "assistant", "10-foot gate", "导师确认周长表达式，问十英尺门洞怎样影响用料。"),
    (5, "user", "I removed one x", "学生解释，有门的那一边不用围，因此删去了一个 x。"),
    (6, "assistant", "only subtract the 10-foot opening", "导师对照整条边和十英尺门洞，已明确提示只减门洞。"),
    (7, "user", "2x+2y-10=500", "学生写出单门题的完整方程，这条回复只有算式和简短应答。"),
    (8, "assistant", "absolutely correct", "导师确认并解释单门方程，该题的对话到此结束。"),
)


def read_p019(source: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source hash mismatch: {name}")
    log, log_loc = locate(source / "anonymized_tutoring_logs.csv",
                          anon_id="p019", learning_objective="gate_fence")
    score, score_loc = locate(source / "anonymized_data.csv", anon_id="p019")
    if log["condition"] != "socratic" or log["condition"] != score["condition"]:
        raise ValueError("The episode and learner must belong to the Socratic group")
    messages = log["conversation"].split(" || ")
    if len(messages) != len(TURN_NOTES):
        raise ValueError("Recheck the turn annotations against the release")
    turns = []
    for number, role, fragment, note in TURN_NOTES:
        speaker, _, message = messages[number - 1].partition(": ")
        if role != speaker or message.count(fragment) != 1:
            raise ValueError(f"Unresolved source anchor at turn {number}")
        start = message.index(fragment)
        turns.append(dict(turn=number, role=role, excerpt=fragment, start=start,
                          end=start + len(fragment), paraphrase=note))
    base = f"{manifest['repository']}/blob/{manifest['commit']}/"
    for location in (log_loc, score_loc):
        location["link"] = f"{base}{location['file']}#L{location['first_line']}-L{location['last_line']}"
    # Keep the file value as published. The codebook defines the denominator.
    outcome_raw = score["pct_practice_aligned"]
    return {
        "learner": "p019", "objective": "gate_fence", "condition": log["condition"],
        "source_commit": manifest["commit"], "log": log_loc, "turns": turns,
        "initial_correct_label": log["initial_correct"], "final_correct_label": log["final_correct"],
        "independent_assessment": {
            "score_source": score_loc, "field": "pct_practice_aligned",
            "raw_fraction": outcome_raw, "max_points": manifest["outcome_contract"]["max_points"],
            "scope": "three_transfer_items_combined",
            "related_public_item": "补充材料第 4 题 Farm Gates，两个门洞分别为 12 和 8 英尺，围栏 500 英尺。",
            "paper": "https://arxiv.org/pdf/2611.20061v1#page=49",
            "codebook": base + "codebooks.xlsx",
            "item_answer": None, "item_score": None, "item_reason": None,
            "missing_reason": "公开版本仅提供三道变式题合计成绩，缺少该生在 Farm Gates 上的逐题记录。",
        },
    }
