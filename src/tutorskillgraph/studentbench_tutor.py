"""Replay the released StudentBench GRE tutor with two versions of its lesson input."""

import csv
import hashlib
import json

from .openai_client import MODEL, complete
from .reason_trials import EXP, ROOT, digest, read_json, write_json

NATIVE = ROOT / "data/raw/studentbench-native"
RUNS = EXP / "native_runs"
STRATEGY = "gre.quant.tutor.lean.v3"


def verified_file(relative, manifest):
    path = NATIVE / relative
    if digest(path) != manifest["files"][relative]["sha256"]:
        raise ValueError(f"Source hash mismatch for {relative}")
    return path


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def chat_prefix(plan, concept, rows, cutoff):
    messages = [{"role": "user", "content": "Pretest-based lesson profile: " + plan["student_summary"]}]
    for event in rows:
        if int(event["trajectory_position"]) > cutoff:
            break
        if event["concept_id"] != concept["concept_id"]:
            continue
        kind = event["event_type"]
        if kind == "practice_problem_shown":
            role, text = "user", "Practice panel displayed:\n" + event["content"]
        elif kind == "practice_answer_submitted":
            role = "user"
            text = ("Practice panel submission: " + event["submitted_answer"]
                    + ". Marked " + {"True": "correct.", "False": "incorrect."}[event["is_correct"]])
        elif kind in {"student_message", "ai_tutor_message"}:
            role = "assistant" if kind == "ai_tutor_message" else "user"
            text = event["content"]
        else:
            continue
        messages.append({"role": role, "content": text})
    return messages


def requests_for(target, graph, manifest):
    session = target["session"]
    meta = read_json(verified_file(f"{session}/student.json", manifest))
    if (meta["tutor_prompt_version_id"], meta["ai_model_preset_id"]) != (STRATEGY, "gpt-5.4-mini-none"):
        raise ValueError(f"Unexpected original tutoring condition for {session}")
    rows = csv_rows(verified_file(f"{session}/events.csv", manifest))
    by_pos = {int(e["trajectory_position"]): e for e in rows}
    if list(by_pos) != sorted(by_pos) or len(by_pos) != len(rows):
        raise ValueError(f"Unordered trajectory for {session}")
    shown, last = by_pos[target["shown"]], by_pos[target["cutoff"]]
    if (shown["event_type"] != "practice_problem_shown" or target["shown"] >= target["cutoff"]
            or last["practice_problem_id"] != shown["practice_problem_id"]
            or last["event_type"] not in {"practice_answer_submitted", "student_message"}):
        raise ValueError(f"Invalid learner decision point for {session}")
    plan = read_json(verified_file(f"{session}/plan.json", manifest))
    concept = next(c for c in plan["concepts"] if c["concept_id"] == shown["concept_id"])
    messages = chat_prefix(plan, concept, rows, target["cutoff"])
    candidates = graph.retrieve(student=session, skill=target["skill"], material=target["material"],
                                observation=target["observation"])
    instructions = {v.instruction for v in candidates}
    # Incompatible edits or missing evidence preserve the original lesson.
    edit = instructions.pop() if len(instructions) == 1 else ""
    template = verified_file("tutor.txt", manifest).read_text(encoding="utf-8")
    if template.count("{why_it_matters}") != 1 or template.count("{concept_name}") != 1:
        raise ValueError("Published prompt slots changed")
    requests = {}
    for arm, extra in (("original_plan", ""), ("skill_plan", edit)):
        why = concept["why_it_matters"] + ("\n" + extra if extra else "")
        prompt = template.replace("{concept_name}", concept["name"]).replace("{why_it_matters}", why)
        requests[arm] = {"model": MODEL, "instructions": prompt, "input": messages,
                         "reasoning": {"effort": "low"}, "max_output_tokens": 1100, "store": False}
    return requests, {"session": session, "shown": target["shown"], "cutoff": target["cutoff"],
                      "concept": concept["concept_id"], "historical_model": meta["ai_model_endpoint_id"],
                      "matched_versions": [v.id for v in candidates], "plan_addition": edit,
                      "criterion": target["criterion"]}


def encode(body):
    return json.dumps(body, ensure_ascii=False).encode()


def prepare(graph):
    manifest = read_json(EXP / "native_sources.json")
    targets = read_json(EXP / "native_targets.json")
    payloads, trials = {}, []
    for target in targets:
        pair, entry = requests_for(target, graph, manifest)
        entry["requests"] = {}
        for arm, body in pair.items():
            signature = hashlib.sha256(encode(body)).hexdigest()
            payloads[signature] = body
            entry["requests"][arm] = signature
        trials.append(entry)
    lock = {"model": MODEL, "strategy": STRATEGY, "source_revision": manifest["revision"],
            "prompt_sha256": manifest["files"]["tutor.txt"]["sha256"],
            "target_annotation_sha256": digest(EXP / "native_targets.json"), "trials": trials}
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / "design_lock.json"
    if path.exists() and read_json(path) != lock:
        raise ValueError("The registered final-inference design has changed")
    write_json(path, lock)
    write_json(RUNS / "skill_graph.json", graph.as_record())
    return lock, payloads


def run_cached(signature, body, directory=RUNS):
    path = directory / f"{signature}.json"
    if path.exists():
        record = read_json(path)
        if record["request_sha256"] != signature or record["model"] != body["model"]:
            raise ValueError(f"Cache does not match {path.name}")
        return record
    raw, reply = complete(encode(body), path.name)
    record = {"request_sha256": signature, "response_id": raw["id"], "model": raw["model"],
              "usage": raw["usage"], "reply": reply}
    tmp = path.with_suffix(".part")
    write_json(tmp, record)
    tmp.replace(path)
    return record


def observed_reply(target, rows):
    after = (e for e in rows if int(e["trajectory_position"]) > target["cutoff"])
    for e in after:
        if e["event_type"] == "ai_tutor_message":
            if e["concept_id"] != target["concept"]:
                break
            return {"event": int(e["trajectory_position"]), "text": e["content"]}
        if e["event_type"] in {"practice_problem_shown", "student_message", "practice_answer_submitted"}:
            break
    raise ValueError(f"No immediately following tutor reply for {target['session']}")
