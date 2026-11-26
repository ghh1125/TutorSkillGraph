"""Prepare or execute paired final inference with the released StudentBench tutor."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.reason_trials import EXP, read_json, write_json
from tutorskillgraph.skill_graph import build_graph
from tutorskillgraph.studentbench_tutor import RUNS, csv_rows, observed_reply, prepare, run_cached, verified_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Send only requests missing from the cache")
    args = parser.parse_args()
    design, requests = prepare(build_graph())
    missing = [key for key in requests if not (RUNS / f"{key}.json").exists()]
    print(f"{len(design['trials'])} paired students, {len(requests)} distinct requests, {len(missing)} uncached.")
    if missing and not args.run:
        return
    if args.run and missing:
        lock = RUNS / "inference.running"
        with lock.open("x") as marker:
            marker.write("Native inference in progress. Check the response cache before resuming.")
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda key: run_cached(key, requests[key]), missing))
        finally:
            lock.unlink()
    manifest = read_json(EXP / "native_sources.json")
    rows = []
    for trial in design["trials"]:
        session = trial["session"]
        events = csv_rows(verified_file(f"{session}/events.csv", manifest))
        replies = {arm: read_json(RUNS / f"{key}.json") for arm, key in trial["requests"].items()}
        person = read_json(verified_file(f"{session}/student.json", manifest))
        actual = {}
        for assessment in ("pre", "post"):
            answers = csv_rows(verified_file(f"{session}/{assessment}.csv", manifest))
            score = sum(int(a["is_correct"]) for a in answers)
            if score != person[f"{assessment}test_score_points"] or len(answers) != person["assessment_max_score_points"]:
                raise ValueError(f"Official assessment totals disagree for {session}")
            actual[f"{assessment}test"] = score
        actual["out_of"] = person["assessment_max_score_points"]
        rows.append({**trial, "observed_original": observed_reply(trial, events),
                     "historical_student_scores": actual, "replay": replies, "replay_student_outcomes": None})
    write_json(RUNS / "comparison.json", rows)
    print(f"Saved {len(rows)} comparisons with the historical tutor replies.")


if __name__ == "__main__":
    main()
