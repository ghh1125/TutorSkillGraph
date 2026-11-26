"""Run a paired comparison, resume completed requests, and prepare independent review material."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.lesson_review import payload, run_one
from tutorskillgraph.reason_trials import EXP, comparison_case, digest, model_input, read_json, write_json


def summarize(cases, definitions, view, directory):
    rows, review, reveal = [], [], {}
    totals = {"input_tokens": 0, "output_tokens": 0}
    for case, ref in zip(cases, definitions):
        pair = [read_json(directory / f"{case['case']}_{arm}.json") for arm in ("answer", "reason")]
        for r in pair:
            for k in totals:
                totals[k] += r["usage"][k]
        a, b = [r["selected_action"] for r in pair]
        rows.append({"case": case["case"], "reference": ref["reference"], "answer": a, "reason": b,
                     "answer_match": a == ref["reference"], "reason_match": b == ref["reference"],
                     "invalid_event_ids": sum(len(r["unresolved_citations"]) for r in pair)})
        random.Random("blind-v1/" + case["case"]).shuffle(pair)
        reveal[case["case"]] = [r["arm"] for r in pair]
        review.append({"case": case["case"], "source": case["source"], "evidence": model_input(case, view, True),
                       "proposals": {str(i): r["decision"] for i, r in enumerate(pair, 1)},
                       "teacher_evaluation": {"preferred": None, "reason": None, "adequate_proposals": None}})
    stats = {"n": len(rows), "answer_match": sum(r["answer_match"] for r in rows),
             "reason_match": sum(r["reason_match"] for r in rows),
             "gained": sum(not r["answer_match"] and r["reason_match"] for r in rows),
             "lost": sum(r["answer_match"] and not r["reason_match"] for r in rows),
             "changed_action": sum(r["answer"] != r["reason"] for r in rows), "usage": totals}
    write_json(directory / "summary.json", {**stats, "rows": rows})
    write_json(directory / "review_key.json", reveal)
    # A reviewer may already have entered ratings. Never overwrite their copy.
    review_path = directory / "blind_review.json"
    if not review_path.exists():
        write_json(review_path, {"instructions": "对照原课与新题首答，判断动作、两种预测、撤回条件是否有依据。"
                                 "preferred 可填 1、2、两者相当、都不充分、无法判定。", "cases": review})
    print(json.dumps(stats))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--view", choices=["text", "table", "hypergraph"], default="text")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    definitions = read_json(EXP / "cases.json")
    manifest = read_json(EXP / "sources.json")
    cases = [comparison_case(d, manifest) for d in definitions]
    if len({c["case"] for c in cases}) != len(cases):
        raise ValueError("Repeated learner/session")
    directory = EXP / "runs" / args.view
    directory.mkdir(parents=True, exist_ok=True)
    jobs = [(case, arm) for case in cases for arm in (False, True)]
    random.Random(20261122).shuffle(jobs)
    frozen = {"reference_sha256": digest(EXP / "cases.json"), "protocol_sha256": digest(EXP / "protocol.zh-CN.md"),
              "order_and_requests": [{"case": c["case"], "arm": "reason" if a else "answer",
                  "sha256": sha256(json.dumps(payload(c, args.view, a), ensure_ascii=False).encode()).hexdigest()}
                 for c, a in jobs]}
    lock = directory / "design_lock.json"
    if lock.exists() and read_json(lock) != frozen:
        raise ValueError("Inputs or references differ from the frozen run. Use a new run directory.")
    if not lock.exists():
        write_json(lock, frozen)
    if args.prepare_only:
        print(f"Frozen {len(jobs)} requests for {len(cases)} learners")
        return
    if not args.summarize_only:
        with ThreadPoolExecutor(3) as pool:
            list(pool.map(lambda job: run_one(job[0], args.view, job[1], directory), jobs))
    summarize(cases, definitions, args.view, directory)


if __name__ == "__main__":
    main()
