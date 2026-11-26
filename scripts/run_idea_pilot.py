"""Reproduce the exploratory pilot; requires NumPy."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from tutorskillgraph.gate_pilot import run_gate
from tutorskillgraph.pilot import read_data, run

if __name__ == "__main__":
    result = run(root)
    output = root / "experiments/lesson_revision_pilot/results.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "students"}, indent=2))
    people, logs, _ = read_data(root)
    gate = run_gate(root, people, logs)
    output.with_name("gate_results.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print("Gate MAE reductions:", {k: v["mae_reduction"] for k, v in gate.items()
                                   if isinstance(v, dict) and "mae_reduction" in v})
