"""Run three paired 10x10 engineering simulations for the fuel-directed cycle.

Scenarios:
1. second_collapse_rebirth: stable organization reaches KRYSTALIZACJA and RYTM,
   loses the main rhythm, enters STAGNACJA, PĘKNIĘCIE and ROZPAD II, then starts
   a new cycle through RÓŻNICA with refreshed intuition;
2. stable_rhythm: the form remains synchronized, so task count alone must never
   force ROZPAD II;
3. first_collapse_recovery: early fuel/balance loss causes ROZPAD I, followed by
   a return to REGULACJA in the same cycle, without long-term intuition.

These are deterministic engineering simulations, not Claude API evidence.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from swarm_validation.evaluator import Evaluation
from swarm_validation.models import ProviderResponse, Usage
from swarm_validation.protocol import ProtocolConfig
from swarm_validation.runner import BenchmarkRunner


class FuelCycleProvider:
    def __init__(self, scenario: str, seed: int) -> None:
        self.scenario = scenario
        self.seed = seed
        self.calls: list[dict[str, object]] = []
        self.seen: dict[tuple[str, int], list[str]] = {}

    def _position(self, condition: str, agent_id: int, task_id: str) -> int:
        key = (condition, agent_id)
        sequence = self.seen.setdefault(key, [])
        if task_id not in sequence:
            sequence.append(task_id)
        return len(sequence)

    def generate(self, *, model, system, messages, max_tokens, temperature, metadata=None):
        condition = str(metadata["condition"])
        agent_id = int(metadata["agent_id"])
        task_id = str(metadata["task_id"])
        attempt = int(metadata["attempt"])
        position = self._position(condition, agent_id, task_id)
        memory_used = "Prior-cycle intuition" in system

        forced_failure = False
        if self.scenario == "second_collapse_rebirth":
            # Seven stable observations reach RYTM; four failed tasks break synchrony.
            forced_failure = 8 <= position <= 11
            if position <= 7:
                probability = 1.0
            elif forced_failure:
                probability = 0.0
            else:
                probability = 0.92 if (condition == "swarm" and memory_used) else 0.62
        elif self.scenario == "stable_rhythm":
            probability = 1.0
        elif self.scenario == "first_collapse_recovery":
            forced_failure = position <= 2
            probability = 0.0 if forced_failure else 1.0
        else:
            raise ValueError(self.scenario)

        if not forced_failure and probability < 1.0:
            probability = min(0.98, probability + 0.18 * (attempt - 1))

        latent = random.Random(
            f"{self.scenario}:{self.seed}:{agent_id}:{task_id}:{attempt}"
        ).random()
        passed = latent < probability
        expected = int(task_id.split("/")[-1])
        text = f"    return {expected if passed else expected + 1}\n"
        prompt_chars = len(system) + sum(len(item["content"]) for item in messages)
        usage = Usage(input_tokens=55 + prompt_chars // 4, output_tokens=8)

        self.calls.append(
            {
                "condition": condition,
                "agent_id": agent_id,
                "task_id": task_id,
                "position": position,
                "attempt": attempt,
                "memory_used": memory_used,
                "forced_failure": forced_failure,
                "passed_candidate": passed,
            }
        )
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


def write_tasks(path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index in range(160):
            record = {
                "task_id": f"t/{index}",
                "prompt": (
                    f'def value_{index}():\n'
                    f'    """sequence list sum aggregate values; return integer {index}."""\n'
                ),
                "test": f"def check(candidate):\n    assert candidate() == {index}",
                "entry_point": f"value_{index}",
            }
            handle.write(json.dumps(record) + "\n")


def run_scenario(root: Path, scenario: str, seed: int) -> dict[str, object]:
    output = root / scenario
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    tasks = output / "tasks.jsonl"
    write_tasks(tasks)

    provider = FuelCycleProvider(scenario, seed)
    config = ProtocolConfig(
        bootstrap_samples=4000,
        max_live_calls=960,
        cycle_length=16,
    )
    runner = BenchmarkRunner(
        config=config,
        provider=provider,
        tasks_path=tasks,
        output_dir=output / "results",
        evaluator_fn=fast_evaluate,
    )
    report = runner.run()

    swarm_calls = [call for call in provider.calls if call["condition"] == "swarm"]
    controllers = list(runner.swarm.values())
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
        "forced_failure_calls_swarm": sum(
            bool(call["forced_failure"]) for call in swarm_calls
        ),
        "forced_failure_calls_baseline": sum(
            bool(call["forced_failure"])
            for call in provider.calls
            if call["condition"] == "baseline"
        ),
        "phase_histories": {
            str(controller.agent_id): controller.phase_history for controller in controllers
        },
        "final_states": {
            str(controller.agent_id): controller.state.to_dict() for controller in controllers
        },
        "second_collapse_agents": sum(
            controller.state.collapse_two_count > 0 for controller in controllers
        ),
        "first_collapse_agents": sum(
            controller.state.collapse_one_count > 0 for controller in controllers
        ),
        "agents_with_intuition": sum(
            bool(controller.intuitive_memory) for controller in controllers
        ),
    }
    (output / "simulation_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    configured_root = os.environ.get("SWARM_SIM_ROOT")
    root = (
        Path(configured_root).resolve()
        if configured_root
        else PROJECT_ROOT / "results" / "fuel-cycle-v5-synthetic"
    )
    root.mkdir(parents=True, exist_ok=True)
    results = [
        run_scenario(root, "second_collapse_rebirth", 101),
        run_scenario(root, "stable_rhythm", 202),
        run_scenario(root, "first_collapse_recovery", 303),
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
