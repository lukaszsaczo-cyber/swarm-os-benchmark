#!/usr/bin/env python3
"""Full 10x16 synthetic check of orchestration, logging and statistics.

This does not call Claude and is not a performance result.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_validation.models import ProviderResponse, Usage
from swarm_validation.protocol import ProtocolConfig
import swarm_validation.runner as runner_module
from swarm_validation.evaluator import Evaluation
from swarm_validation.runner import BenchmarkRunner


class SyntheticProvider:
    def generate(self, *, model, system, messages, max_tokens, temperature, metadata=None):
        first = messages[0]["content"]
        function_name = first.split("def ", 1)[1].split("(", 1)[0]
        value = int(function_name.split("_")[-1])
        condition = metadata["condition"]
        usage = Usage(
            input_tokens=60 if condition == "swarm" else 80,
            output_tokens=15 if condition == "swarm" else 20,
        )
        return ProviderResponse(
            text=f"    return {value}\n",
            usage=usage,
            model="synthetic-provider",
            stop_reason="end_turn",
            latency_ms=1.0,
            request_id=f"synthetic-{condition}-{function_name}",
        )


def main() -> None:
    root = ROOT
    runner_module.evaluate = lambda task, completion, config: Evaluation(True, "passed", 0.1, 0, "", "")
    tasks_path = root / "results" / "offline-harness-tasks.jsonl"
    output_dir = root / "results" / "offline-harness"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    resume = False
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    with tasks_path.open("w", encoding="utf-8") as handle:
        for index in range(160):
            record = {
                "task_id": f"synthetic/{index}",
                "prompt": f'def value_{index}():\n    """Return {index}."""\n',
                "canonical_solution": f"    return {index}\n",
                "test": f"def check(candidate):\n    assert candidate() == {index}",
                "entry_point": f"value_{index}",
            }
            handle.write(json.dumps(record) + "\n")
    config = ProtocolConfig(bootstrap_samples=2000)
    report = BenchmarkRunner(
        config=config,
        provider=SyntheticProvider(),
        tasks_path=tasks_path,
        output_dir=output_dir,
        resume=resume,
    ).run()
    report["synthetic_only"] = True
    report["verdict"] = "SYNTHETIC_HARNESS_PASS"
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report_md = (output_dir / "report.md").read_text(encoding="utf-8").replace("**Verdict: CONFIRMED**", "**Verdict: SYNTHETIC_HARNESS_PASS**")
    warning = "# SYNTHETIC HARNESS CHECK — NOT A CLAUDE RESULT\n\nThis file validates orchestration only. The 25% value was injected by the fake provider and must never be cited as SWARM_OS performance.\n\n"
    (output_dir / "report.md").write_text(warning + report_md, encoding="utf-8")
    print(json.dumps({
        "synthetic_only": True,
        "verdict": report["verdict"],
        "token_reduction": report["token_reduction"],
        "swarm_observations": report["swarm"]["observations"],
        "baseline_observations": report["baseline"]["observations"],
    }, indent=2))


if __name__ == "__main__":
    main()
