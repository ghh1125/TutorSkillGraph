"""Cohort selection and replay with the published StudentBench tutor."""

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import asdict

from .evidence_revision import TransferHistory
from .grounded_skill import (
    Phase,
    build_memory,
    learner_turns,
    lesson_addition,
    material_for,
    turn_at,
)
from .openai_client import MODEL
from .reason_trials import EXP as OLD
from .reason_trials import ROOT, digest, read_json, windows, write_json
from .studentbench_tutor import STRATEGY, chat_prefix, csv_rows, encode, verified_file

EXP = ROOT / "experiments/grounded_tutor"
REVISION = EXP.parent / "evidence_revision"
RAW = ROOT / "data/raw/studentbench-grounded"
RUNS = EXP / "runs"
STRATA = ("justification", "phase", "written", "submission")


def source(manifest, session, name):
    key = f"{session}/{name}"
    path = RAW / key
    if digest(path) != manifest["files"][key]["sha256"]:
        raise ValueError(f"Source checksum mismatch for {key}")
    return path


def rows_for(manifest, session):
    rows = csv_rows(source(manifest, session, "events.csv"))
    seq = [int(r["trajectory_position"]) for r in rows]
    if seq != sorted(set(seq)):
        raise ValueError(f"Unordered trajectory: {session}")
    for e, pos in zip(rows, seq):
        e["pos"] = pos
    return rows


def stratum(turn, event):
    text = turn.learner.lower()
    if event["event_type"] == "student_message" and (
        len(text.split()) < 3
        or re.search(
            r"\b(?:previous (?:question|problem)|switch topics?|last question instead|never ?mind|different topic)\b",
            text,
        )
        or not re.search(
            r"[=<>^|\d]|\b(?:sign|absolute|stage|rate|area|time|quantity|base|exponent|"
            r"greater|equal|less|hours?|negative|positive|both|example|power|fraction|compare|answer|step)\b",
            text,
        )
    ):
        return None
    if turn.state == "proof" or (
        text
        and re.search(r"because|since|therefore|therefor|so |if ", text)
        and re.search(r"equal|greater|smaller|bigger|less than|cancel|factor", text)
        and re.search(r"\d|sign|simplif|exponent", text)
    ):
        return "justification"
    if isinstance(turn.item, Phase):
        return "phase"
    return "submission" if event["event_type"] == "practice_answer_submitted" else "written"


def select_sample(manifest):
    candidates, coverage = defaultdict(list), {}
    for session in manifest["sessions"]:
        if session in {"task_id_0104", "task_id_0108"}:
            coverage[session] = {"development": True}
            continue
        counts = Counter()
        for b in windows(rows_for(manifest, session)):
            item = material_for(b[0]["content"])
            if not item:
                continue
            for event, following, turn in learner_turns(b, item):
                group = stratum(turn, event)
                if group:
                    counts[group] += 1
                    candidates[group].append(
                        {
                            "session": session,
                            "shown": b[0]["pos"],
                            "cutoff": event["pos"],
                            "following": following["pos"],
                            "concept": b[0]["concept_id"],
                            "stratum": group,
                            "family": item.family,
                        }
                    )
        coverage[session] = dict(counts)
    selected, used = [], set()

    def append(group, limit):
        added = 0
        for row in candidates[group]:
            if row["session"] not in used:
                selected.append(row)
                used.add(row["session"])
                added += 1
                if added >= limit:
                    break

    for group in STRATA:
        append(group, 8)
    for group in STRATA:
        if len(selected) < 32:
            append(group, 32 - len(selected))
    result = {
        "source_revision": manifest["revision"],
        "all_arm_sessions": len(coverage),
        "screening": coverage,
        "cases": selected,
    }
    freeze(EXP / "sample.json", result)
    return result


def freeze(path, data):
    if path.exists():
        if read_json(path) != data:
            raise ValueError(f"The locked design differs: {path.name}")
    else:
        write_json(path, data)


def observation_at(c, manifest):
    rows = rows_for(manifest, c["session"])
    b = next(b for b in windows(rows) if b[0]["pos"] == c["shown"])
    i = next(i for i, r in enumerate(b) if r["pos"] == c["cutoff"])
    item = material_for(b[0]["content"])
    return rows, b, turn_at(b, i, item)


def preflight(experiment=EXP):
    manifest = read_json(experiment / "sources.json")
    cases = read_json(experiment / "sample.json")["cases"]
    packet = []
    for c in cases:
        _, b, t = observation_at(c, manifest)
        item = t.item
        packet.append(
            {
                **c,
                "stem": t.stem,
                "mathematical_key": item.key,
                "visible": [
                    {
                        "pos": e["pos"],
                        "role": e["actor"],
                        "text": e["content"],
                        "submitted": e["submitted_answer"],
                        "correct": e["is_correct"],
                    }
                    for e in b[1:]
                    if e["pos"] <= c["cutoff"]
                    and e["event_type"]
                    in {"ai_tutor_message", "student_message", "practice_answer_submitted"}
                ],
            }
        )
    write_json(experiment / "review_prefixes.json", packet)


def prepare(experiment=EXP):
    manifest = read_json(experiment / "sources.json")
    cases = read_json(experiment / "sample.json")["cases"]
    criteria = read_json(experiment / "criteria.json")
    if set(criteria) != {c["session"] for c in cases}:
        raise ValueError("Every selected learner needs a prospective criterion")
    official = read_json(OLD / "native_sources.json")
    template = verified_file("tutor.txt", official).read_text(encoding="utf-8")
    if template.count("{concept_name}") != 1 or template.count("{why_it_matters}") != 1:
        raise ValueError("Published tutor template changed")
    memory = build_memory()
    runs = experiment / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    memory_path = EXP / "memory.json"
    freeze(
        memory_path,
        {
            "source_revision": manifest["revision"],
            "construction_manifest": "../reason_ablation/sources.json",
            "episodes": [asdict(e) | {"later": list(e.later)} for e in memory.episodes],
        },
    )
    history = None
    if experiment == REVISION:
        history = TransferHistory.from_graph(memory)
        freeze(experiment / "history.json", [asdict(row) for row in history.transfers])
    # Both requests use the same visible student context.
    jobs, records = {}, []
    for c in cases:
        sid = c["session"]
        rows, _, turn = observation_at(c, manifest)
        meta = read_json(source(manifest, sid, "student.json"))
        if (meta["tutor_prompt_version_id"], meta["ai_model_preset_id"]) != (
            STRATEGY,
            "gpt-5.4-mini-none",
        ):
            raise ValueError(f"Unexpected original model/strategy: {sid}")
        plan = read_json(source(manifest, sid, "plan.json"))
        concept = next(con for con in plan["concepts"] if con["concept_id"] == c["concept"])
        messages = chat_prefix(plan, concept, rows, c["cutoff"])
        edit, evidence, move = lesson_addition(memory, turn, sid)
        if history is None:
            flat = lesson_addition(memory, turn, sid, flat=True)
            detail = {"same_edit_with_flat_table": flat[0] == edit}
        else:
            event = next(row for row in rows if row["pos"] == c["cutoff"])
            revision = history.revise(turn, event["submitted_answer"], sid)
            detail = {"transfer_evidence": None}
            if revision:
                edit, detail["transfer_evidence"] = revision
                move = "probe_fixed_relation"
        requests = {}
        for arm, note in (("official_plan", ""), ("grounded_plan", edit)):
            why = concept["why_it_matters"] + ("\n" + note if note else "")
            prompt = template.replace("{concept_name}", concept["name"]).replace("{why_it_matters}", why)
            body = {
                "model": MODEL,
                "instructions": prompt,
                "input": messages,
                "reasoning": {"effort": "low"},
                "max_output_tokens": 1100,
                "store": False,
            }
            key = hashlib.sha256(encode(body)).hexdigest()
            jobs[key] = body
            requests[arm] = key
        records.append(
            {
                **c,
                "requests": requests,
                "selected_move": move,
                "source_episodes": evidence,
                **detail,
                "plan_addition": edit,
                "visible_state": turn.state,
                "prior_assistance": turn.supplied,
            }
        )
    design = {
        "model": MODEL,
        "strategy": STRATEGY,
        "source_revision": manifest["revision"],
        "protocol_sha256": digest(experiment / "protocol.zh-CN.md"),
        "sample_sha256": digest(experiment / "sample.json"),
        "criteria_sha256": digest(experiment / "criteria.json"),
        "memory_sha256": digest(memory_path),
        "template_sha256": official["files"]["tutor.txt"]["sha256"],
        "cases": records,
    }
    if history is not None:
        design["transfer_history_sha256"] = digest(experiment / "history.json")
    freeze(runs / "design_lock.json", design)
    return design, jobs
