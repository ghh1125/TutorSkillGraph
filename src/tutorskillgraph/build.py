"""Build the p019 decision record from the verified upstream release."""

import argparse
import json
from pathlib import Path

from .evidence import read_p019
from .report import markdown
from .revision import proposed_revision


def build(data: Path, manifest: Path, output: Path) -> None:
    case = {
        "case_id": "p019-gate-closure-v1",
        "design_commit": "80c2fbb950784aaa25b3e658bcc9910fd67b55c9",
        "observed": read_p019(data, manifest),
        "proposed": proposed_revision(),
    }
    documents = {
        "p019.zh-CN.md": markdown(case),
        "p019.json": json.dumps(case, ensure_ascii=False, indent=2) + "\n",
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, content in documents.items():
        (output / name).write_text(content, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/sec"))
    parser.add_argument("--manifest", type=Path, default=Path("data/sec_source.json"))
    parser.add_argument("--output", type=Path, default=Path("cases"))
    args = parser.parse_args()
    build(args.data, args.manifest, args.output)
    print(f"Verified sources and wrote p019.zh-CN.md and p019.json to {args.output.resolve()}")


if __name__ == "__main__":
    main()
