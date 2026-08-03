#!/usr/bin/env python3
"""Export the authorized OpenAI HumanEval dataset to the harness JSONL format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/HumanEval.jsonl")
    args = parser.parse_args()
    try:
        from human_eval.data import read_problems
    except ImportError as exc:
        raise SystemExit(
            "Install the official dataset package first: "
            "pip install git+https://github.com/openai/human-eval.git"
        ) from exc
    problems = read_problems()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for task_id, problem in problems.items():
            record = {
                "task_id": task_id,
                "prompt": problem["prompt"],
                "canonical_solution": problem.get("canonical_solution"),
                "test": problem["test"],
                "entry_point": problem["entry_point"],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(problems)} tasks to {target}")


if __name__ == "__main__":
    main()
