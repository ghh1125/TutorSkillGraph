"""Verify the pinned SEC inputs, reading Git blobs or downloading them from the source."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "data/raw/sec")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/sec_source.json").read_text(encoding="utf-8"))
    upstream = ROOT / "data/scaffolded-error-correction"
    args.destination.mkdir(parents=True, exist_ok=True)
    for filename, expected in manifest["files"].items():
        target = args.destination / filename
        if target.exists():
            data = target.read_bytes()
        elif (upstream / ".git").exists():
            data = subprocess.check_output(
                ["git", "-C", str(upstream), "cat-file", "blob", f"{manifest['commit']}:{filename}"]
            )
        else:
            url = f"https://raw.githubusercontent.com/the-oak-lab/scaffolded-error-correction/{manifest['commit']}/{filename}"
            with urlopen(Request(url, headers={"User-Agent": "TutorSkillGraph/0.1"}), timeout=60) as response:
                data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f"Hash mismatch for {filename}; existing files are not overwritten.")
        if not target.exists():
            staging = target.with_suffix(target.suffix + ".download")
            staging.write_bytes(data)
            staging.replace(target)
        print(f"Verified {filename}")


if __name__ == "__main__":
    main()
