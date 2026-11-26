"""Download pinned public sessions; print candidate first responses for evidence review."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tutorskillgraph.reason_trials import (ARM, EXP, HUB, RAW, REV, TRAJECTORY, candidates,
                                          digest, events, read_json, write_json)


def download(session):
    file = RAW / f"{session}.csv"
    if not file.exists():
        url = f"{HUB}/resolve/{REV}/{ARM}/{session}/{TRAJECTORY}"
        with urlopen(url, timeout=45) as response:
            data = response.read()
        part = file.with_suffix(".part")
        part.write_bytes(data)
        part.replace(file)
    return session, digest(file)


if __name__ == "__main__":
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    manifest_path = EXP / "sources.json"
    existing = read_json(manifest_path)["files"] if manifest_path.exists() else {}
    if args.fetch:
        RAW.mkdir(parents=True, exist_ok=True)
        api = f"https://huggingface.co/api/datasets/handshake-ai-research/studentbench/tree/{REV}/{ARM}?limit=200"
        with urlopen(api, timeout=45) as response:
            names = sorted(e["path"].split("/")[-1] for e in json.load(response)
                           if e["type"] == "directory" and "/task_id_" in e["path"])
        cohort = names[10:10 + args.limit]
        with ThreadPoolExecutor(6) as pool:
            hashes = dict(pool.map(download, cohort))
        if any(hashes[k] != existing[k] for k in hashes.keys() & existing.keys()):
            raise ValueError("Local source differs from the existing manifest")
        write_json(manifest_path, {"revision": REV, "directory": ARM, "trajectory": TRAJECTORY,
                                   "design_sessions_excluded": names[:10], "files": {**existing, **hashes}})
    manifest = read_json(manifest_path)
    total = 0
    for s in sorted(manifest["files"])[:args.limit]:
        if digest(RAW / f"{s}.csv") != manifest["files"][s]:
            raise ValueError(f"Recheck the source hash for {s}")
        items = list(candidates(events(s)))
        total += len(items)
        if args.show:
            for q, prefix, prior in items:
                texts = " / ".join(" ".join(r["content"].split()) for r in prefix)
                print(f"{s[-4:]} {q['pos']:3} prior={prior[-1][0]['pos']}  {texts[:270]}")
    print(f"{min(args.limit, len(manifest['files']))} sessions; {total} candidate windows.")
