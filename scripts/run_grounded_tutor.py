"""Select, prepare, run once, and anonymously assess the expanded StudentBench cohort."""

import argparse
import math
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.grounded_trials import (
    EXP,
    REVISION,
    freeze,
    preflight,
    prepare,
    rows_for,
    select_sample,
)
from tutorskillgraph.reason_trials import read_json, write_json
from tutorskillgraph.studentbench_tutor import run_cached


def blind(design, experiment=EXP):
    manifest = read_json(experiment / "sources.json")
    criteria = read_json(experiment / "criteria.json")
    runs = experiment / "runs"
    packet, key = [], {}
    for case in design["cases"]:
        sid = case["session"]
        texts = {}
        if experiment == EXP:
            events = rows_for(manifest, sid)
            hist = next(e for e in events if e["pos"] == case["following"])
            if hist["event_type"] != "ai_tutor_message":
                raise ValueError(f"Unverified native reply: {sid}")
            texts["historical"] = hist["content"]
        for arm, digest in case["requests"].items():
            texts[arm] = read_json(runs / f"{digest}.json")["reply"]
        # Identical text for two plans should receive one judgement; reveal the mapping after scoring.
        unique = sorted(set(texts.values()))
        random.Random(int(sha256(("blind/grounded/v1/" + sid).encode()).hexdigest(), 16)).shuffle(unique)
        labels = dict(zip("XYZ", unique))
        key[sid] = {
            arm: next(k for k, t in labels.items() if t == reply) for arm, reply in texts.items()
        }
        packet.append({"session": sid, "criterion": criteria[sid], "replies": labels})
    freeze(runs / "blind_packet.json", packet)
    freeze(runs / "review_key.json", key)


def summarize(experiment=EXP):
    runs = experiment / "runs"
    design = read_json(runs / "design_lock.json")
    packet = read_json(runs / "blind_packet.json")
    key = read_json(runs / "review_key.json")
    ratings = read_json(experiment / "blind_ratings.json")
    arms = list(key[packet[0]["session"]])
    results, comparisons, totals = [], [], dict.fromkeys(arms, 0)
    if set(ratings) != set(key):
        raise ValueError("Missing or extra learner ratings")
    for prompt in packet:
        sid = prompt["session"]
        score = ratings[sid]
        if set(score) != set(prompt["replies"]) or not all(
            type(v[0]) is int and v[0] in (0, 1) and v[1].strip() for v in score.values()
        ):
            raise ValueError(f"Incomplete blind assessment: {sid}")
        grade = {arm: score[key[sid][arm]][0] for arm in arms}
        for arm in arms:
            totals[arm] += grade[arm]
        results.append({"session": sid, **grade})
        comparisons.append(
            {
                "session": sid,
                "criterion": prompt["criterion"],
                "replies": {
                    arm: {
                        "met": bool(grade[arm]),
                        "assessment": score[key[sid][arm]][1],
                        "reply": prompt["replies"][key[sid][arm]],
                    }
                    for arm in arms
                },
            }
        )
    gained = sum(not r["official_plan"] and r["grounded_plan"] for r in results)
    lost = sum(r["official_plan"] and not r["grounded_plan"] for r in results)
    n = gained + lost
    p = min(1, 2 * sum(math.comb(n, k) for k in range(min(gained, lost) + 1)) / 2**n) if n else 1
    hashes = {v for c in design["cases"] for v in c["requests"].values()}
    usage = {
        token: sum(read_json(runs / f"{h}.json")["usage"][token] for h in hashes)
        for token in ("input_tokens", "output_tokens")
    }
    scores = {
        "students": len(results),
        "totals": totals,
        "gained": gained,
        "lost": lost,
        "tied": len(results) - n,
        "paired_exact_two_sided_p": p,
        "distinct_requests": len(hashes),
        "usage": usage,
        "rows": results,
    }
    by_session = {r["session"]: r for r in results}
    for field in ("family", "stratum"):
        scores[field] = {}
        for c in design["cases"]:
            counts = scores[field].setdefault(c[field], dict.fromkeys(("n", *arms), 0))
            counts["n"] += 1
            for arm in arms:
                counts[arm] += by_session[c["session"]][arm]
    write_json(runs / "summary.json", scores)
    write_json(runs / "comparisons.json", comparisons)
    print({k: v for k, v in scores.items() if k not in ("rows", "family", "stratum")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["select", "prepare", "run", "blind", "summarize"])
    parser.add_argument("--evidence-revision", action="store_true", help="Run the 24-session paired replay")
    args = parser.parse_args()
    action = args.action
    experiment = REVISION if args.evidence_revision else EXP
    runs = experiment / "runs"
    if action == "select":
        if args.evidence_revision:
            cohort = read_json(REVISION / "sample.json")
        else:
            cohort = select_sample(read_json(EXP / "sources.json"))
        preflight(experiment)
        print(f"{len(cohort['cases'])} students")
        return
    if action == "summarize":
        summarize(experiment)
        return
    design, jobs = prepare(experiment)
    missing = [k for k in jobs if not (runs / f"{k}.json").exists()]
    print(
        f"{len(design['cases'])} paired learners. {len(jobs)} distinct requests, {len(missing)} uncached.",
        flush=True,
    )
    if len(jobs) > 2 * len(design["cases"]) or len(jobs) > (48 if args.evidence_revision else 64):
        raise ValueError("Exceeded planned request budget")
    if action == "prepare":
        return
    if action == "run" and missing:
        marker = runs / "inference.running"
        with marker.open("x") as f:
            f.write("Check the response cache before resuming.")
        try:
            random.Random(20261122).shuffle(missing)
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(run_cached, k, jobs[k], runs) for k in missing]
                try:
                    for i, f in enumerate(as_completed(futures), 1):
                        f.result()
                        if i % 8 == 0:
                            print(f"Saved {i}/{len(missing)} new replies.", flush=True)
                except Exception:
                    for f in futures:
                        f.cancel()
                    raise
        finally:
            marker.unlink()
    blind(design, experiment)


if __name__ == "__main__":
    main()
