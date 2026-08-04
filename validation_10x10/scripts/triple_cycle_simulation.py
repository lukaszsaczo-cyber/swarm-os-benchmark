"""Run three fair paired synthetic 10x10 engineering simulations.

Scenarios:
1. relevant_memory: prior-cycle intuition can help after state 40;
2. irrelevant_noise: memory must be rejected and both conditions remain identical;
3. failure_purge: both conditions receive the same forced first-cycle failures,
   proving failed material is not retained by SWARM.

These simulations validate mechanics only. They are not Claude API evidence and
cannot confirm the preregistered 20% hypothesis.
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

# Make direct execution robust without requiring an editable installation.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swarm_validation.evaluator import Evaluation
from swarm_validation.models import ProviderResponse, Usage
from swarm_validation.protocol import ProtocolConfig
from swarm_validation.runner import BenchmarkRunner


class PairedScenarioProvider:
    def __init__(self, scenario: str, seed: int) -> None:
        self.scenario = scenario
        self.seed = seed
        self.calls: list[dict[str, object]] = []
        self.seen: dict[tuple[str, int], list[str]] = {}

    def generate(self, *, model, system, messages, max_tokens, temperature, metadata=None):
        condition = str(metadata["condition"])
        agent_id = int(metadata["agent_id"])
        task_id = str(metadata["task_id"])
        attempt = int(metadata["attempt"])

        key = (condition, agent_id)
        sequence = self.seen.setdefault(key, [])
        if task_id not in sequence:
            sequence.append(task_id)
        position = len(sequence)

        memory_used = "Prior-cycle intuition" in system
        base_probability = 0.72

        # Paired stress condition: both SWARM and baseline fail the first cycle.
        # This tests purge behavior without giving either condition an unfair task.
        forced_first_cycle_failure = self.scenario == "failure_purge" and position <= 8

        if forced_first_cycle_failure:
            probability = 0.0
        elif self.scenario == "relevant_memory" and condition == "swarm" and memory_used:
            probability = 0.84
        else:
            probability = base_probability

        if not forced_first_cycle_failure:
            probability = min(0.96, probability + 0.12 * (attempt - 1))

        # Common random number: same latent difficulty for both conditions.
        latent = random.Random(f"{self.scenario}:{self.seed}:{task_id}:{attempt}").random()
        passed = latent < probability
        expected = int(task_id.split("/")[-1])
        text = f"    return {expected if passed else expected + 1}\n"
        chars = len(system) + sum(len(item["content"]) for item in messages)
        usage = Usage(input_tokens=55 + chars // 4, output_tokens=8)

        self.calls.append({
            "condition": condition,
            "agent_id": agent_id,
            "task_id": task_id,
            "attempt": attempt,
            "memory_used": memory_used,
            "forced_failure": forced_first_cycle_failure,
            "passed_candidate": passed,
        })
        return ProviderResponse(
            text=text,
            usage=usage,
            model=model,
            stop_reason="end_turn",
            latency_ms=1.0,
            request_id=f"synthetic-{self.scenario}-{len(self.calls)}",
        )


def fast_evaluate(task, completion, config=None):
    expected = int(task.task_id.split("/")[-1])
    passed = f"return {expected}" in completion
    return Evaluation(
        passed=passed,
        status="passed" if passed else "failed",
        execution_ms=0.1,
        return_code=0 if passed else 1,
        stdout="",
        stderr="" if passed else "AssertionError",
    )


def write_tasks(path: Path, scenario: str) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index in range(160):
            if scenario == "irrelevant_noise":
                topic = f"unique_topic_{index} isolated_concept_{index} operation_{index}"
            else:
                topic = "sequence list sum aggregate values"
            record = {
                "task_id": f"t/{index}",
                "prompt": f'def value_{index}():\n    """{topic}; return integer {index}."""\n',
                "test": f"def check(candidate):\n    assert candidate() == {index}",
                "entry_point": f"value_{index}",
            }
            handle.write(json.dumps(record) + "\n")


def run_scenario(root: Path, scenario: str, seed: int) -> dict[str, object]:
    output = root / scenario
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    tasks = output / "tasks.jsonl"
    write_tasks(tasks, scenario)

    provider = PairedScenarioProvider(scenario, seed)
    config = ProtocolConfig(
        bootstrap_samples=2000,
        max_live_calls=960,
        cycle_length=8,
    )
    report = BenchmarkRunner(
        config=config,
        provider=provider,
        tasks_path=tasks,
        output_dir=output / "results",
        evaluator_fn=fast_evaluate,
    ).run()

    swarm_calls = [call for call in provider.calls if call["condition"] == "swarm"]
    result = {
        "scenario": scenario,
        "seed": seed,
        "report": report,
        "swarm_memory_calls": sum(bool(call["memory_used"]) for call in swarm_calls),
        "swarm_retry_memory_calls": sum(
            bool(call["memory_used"])
            for call in swarm_calls
            if int(call["attempt"]) > 1
        ),
        "forced_failure_calls_swarm": sum(bool(call["forced_failure"]) for call in swarm_calls),
        "forced_failure_calls_baseline": sum(
            bool(call["forced_failure"])
            for call in provider.calls
            if call["condition"] == "baseline"
        ),
    }
    (output / "simulation_summary.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    root = PROJECT_ROOT / "results" / "memory-cycle-v4-synthetic"
    root.mkdir(parents=True, exist_ok=True)
    results = [
        run_scenario(root, "relevant_memory", 101),
        run_scenario(root, "irrelevant_noise", 202),
        run_scenario(root, "failure_purge", 303),
    ]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
