"""Fetch the pinned small-tutor arm, then just the plans and metadata needed for replay."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.reason_trials import (
    ARM,
    HUB,
    REV,
    ROOT,
    TRAJECTORY,
    digest,
    read_json,
    write_json,
)

EXP = ROOT / "experiments/grounded_tutor"
RAW = ROOT / "data/raw/studentbench-grounded"
MINI = ARM.replace("gemini-3.1-pro-high", "gpt-5.4-mini-none")
FILES = {
    "events.csv": TRAJECTORY,
    "plan.json": "ai_lesson_plan_data/lesson_plan_including_practice_problems.json",
    "student.json": "student_data/student.json",
}


def public_bytes(url):
    for attempt in range(3):
        try:
            with urlopen(
                Request(url, headers={"User-Agent": "TutorSkillGraph/0.1"}), timeout=25
            ) as response:
                return response.read()
        except (URLError, TimeoutError, ConnectionError) as error:
            if isinstance(error, HTTPError) and error.code in {401, 403, 404}:
                raise
            if attempt == 2:
                if not shutil.which("curl"):
                    raise
                return subprocess.check_output(
                    ["curl", "-fsSL", "--retry", "2", "--max-time", "30", url]
                )
            time.sleep(attempt + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans", action="store_true", help="Fetch plans for the selected sessions")
    parser.add_argument("--sample", type=Path, help="Fetch the files for a locked replay sample")
    args = parser.parse_args()
    path = (args.sample.parent if args.sample else EXP) / "sources.json"
    manifest = read_json(path) if path.exists() else {}
    if manifest:
        if manifest["revision"] != REV or manifest["arm"] != MINI:
            raise ValueError("Source revision or arm changed")
        sessions = manifest["sessions"]
    elif args.sample:
        cohort = read_json(args.sample)
        if (cohort["source_revision"], cohort["source_arm"]) != (REV, MINI):
            raise ValueError("Replay sample belongs to a different dataset release or arm")
        sessions = [c["session"] for c in cohort["cases"]]
        manifest = {"revision": REV, "arm": MINI, "sessions": sessions, "files": {}}
    else:
        tree_url = f"https://huggingface.co/api/datasets/handshake-ai-research/studentbench/tree/{REV}/{MINI}?limit=200"
        tree = json.loads(public_bytes(tree_url))
        sessions = sorted(x["path"].rsplit("/", 1)[1] for x in tree if x["type"] == "directory")
        if (
            not sessions
            or len(tree) >= 200
            or any(not re.fullmatch(r"task_id_[0-9]+", s) for s in sessions)
        ):
            raise ValueError("Unexpected session inventory")
        manifest = {"revision": REV, "arm": MINI, "sessions": sessions, "files": {}}
    jobs = [(s, "events.csv") for s in sessions if s not in {"task_id_0104", "task_id_0108"}]
    if args.plans or args.sample:
        selected = read_json(args.sample or EXP / "sample.json")["cases"]
        jobs.extend((c["session"], name) for c in selected for name in ("plan.json", "student.json"))

    def fetch(job):
        session, name = job
        relative = f"{session}/{name}"
        file = RAW / relative
        remote = f"{MINI}/{session}/{FILES[name]}"
        if not file.exists():
            file.parent.mkdir(parents=True, exist_ok=True)
            content = public_bytes(f"{HUB}/resolve/{REV}/{remote}")
            if name.endswith(".json"):
                json.loads(content)
            elif not content.startswith(b"trajectory_position,"):
                raise ValueError(f"Unexpected trajectory header: {relative}")
            temp = file.with_suffix(".part")
            temp.write_bytes(content)
            temp.replace(file)
        record = {"path": remote, "sha256": digest(file)}
        if relative in manifest["files"] and manifest["files"][relative] != record:
            raise ValueError(f"Source checksum changed: {relative}")
        return relative, record

    with ThreadPoolExecutor(8) as pool:
        results = dict(pool.map(fetch, jobs))
    manifest["files"].update(results)
    write_json(path, manifest)
    print(f"{len(sessions)} sessions, {len(results)} source files verified", flush=True)


if __name__ == "__main__":
    main()
