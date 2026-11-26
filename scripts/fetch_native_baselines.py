"""Fetch only files needed for the published StudentBench tutor and native outcomes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.reason_trials import ARM, EXP, HUB, REV, ROOT, TRAJECTORY, digest, read_json, write_json

RAW = ROOT / "data/raw/studentbench-native"
PLAN = "ai_lesson_plan_data/lesson_plan_including_practice_problems.json"
MINI = ARM.replace("gemini-3.1-pro-high", "gpt-5.4-mini-none")


def fetch(entry):
    local, remote = entry
    path = RAW / local
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen(f"{HUB}/resolve/{REV}/{remote}", timeout=60) as response:
            content = response.read()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(content)
        tmp.replace(path)
    return local, {"path": remote, "sha256": digest(path)}


if __name__ == "__main__":
    sources = {"tutor.txt": "5_prompts/gre.quant.tutor.lean.v3.txt",
               "question_bank.csv": "question_bank_quant.csv"}
    for row in read_json(EXP / "cases.json"):
        s = row["session"]
        sources.update({f"{s}/plan.json": f"{ARM}/{s}/{PLAN}",
                        f"{s}/post.csv": f"{ARM}/{s}/student_data/posttest_responses.csv"})
    for s in ("task_id_0104", "task_id_0108"):
        for dest, name in (("plan.json", PLAN), ("events.csv", TRAJECTORY), ("student.json", "student_data/student.json"),
                           ("pre.csv", "student_data/pretest_responses.csv"),
                           ("post.csv", "student_data/posttest_responses.csv")):
            sources[f"{s}/{dest}"] = f"{MINI}/{s}/{name}"
    with ThreadPoolExecutor(6) as pool:
        hashes = dict(pool.map(fetch, sources.items()))
    manifest = {"revision": REV, "files": hashes}
    target = EXP / "native_sources.json"
    if target.exists() and read_json(target) != manifest:
        raise ValueError("Native baseline source files differ from the pinned manifest")
    write_json(target, manifest)
    print(f"Verified {len(hashes)} files")
