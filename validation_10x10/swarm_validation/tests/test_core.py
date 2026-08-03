from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from swarm_validation.analysis import analyze
from swarm_validation.code_extract import normalize_completion
from swarm_validation.controller import SwarmController
from swarm_validation.dataset import BenchmarkTask, load_tasks
from swarm_validation.evaluator import evaluate
from swarm_validation.models import ProviderResponse, TaskOutcome, Usage
from swarm_validation.protocol import ProtocolConfig, assign_tasks
from swarm_validation.runner import BenchmarkRunner


class FakeProvider:
    def generate(self, *, model, system, messages, max_tokens, temperature, metadata=None):
        first = messages[0]["content"]
        name = first.split("def ", 1)[1].split("(", 1)[0]
        completion = f"    return {int(name.split('_')[-1])}\n"
        condition = metadata["condition"]
        usage = Usage(input_tokens=60 if condition == "swarm" else 80, output_tokens=15 if condition == "swarm" else 20)
        return ProviderResponse(completion, usage, model, "end_turn", 1.0, f"fake-{condition}-{name}")


def write_tasks(path: Path, count: int) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index in range(count):
            record = {
                "task_id": f"task/{index}",
                "prompt": f"def value_{index}():\n    \"\"\"Return {index}.\"\"\"\n",
                "canonical_solution": f"    return {index}\n",
                "test": f"def check(candidate):\n    assert candidate() == {index}",
                "entry_point": f"value_{index}",
            }
            handle.write(json.dumps(record) + "\n")


class CoreTests(unittest.TestCase):
    def test_normalize_full_function(self):
        raw = "```python\ndef add(a, b):\n    return a + b\n```"
        self.assertEqual(normalize_completion(raw, "def add(a, b):\n", "add"), "    return a + b\n")

    def test_evaluator_pass_and_fail(self):
        task = BenchmarkTask("x", "def f():\n", "def check(candidate):\n    assert candidate() == 2", "f")
        self.assertTrue(evaluate(task, "    return 2\n").passed)
        self.assertFalse(evaluate(task, "    return 3\n").passed)

    def test_assignment_is_disjoint_and_paired(self):
        tasks = [BenchmarkTask(str(i), f"def f{i}():\n", "def check(candidate): pass", f"f{i}") for i in range(20)]
        config = ProtocolConfig(tasks_per_agent=2, max_live_calls=120)
        assignment = assign_tasks(tasks, config)
        ids = [task.task_id for group in assignment.values() for task in group]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)
        self.assertEqual(len(assignment), 10)

    def test_swarm_memory_is_created(self):
        task = BenchmarkTask("x", "def add(a,b):\n", "def check(candidate): pass", "add")
        controller = SwarmController(0)
        self.assertNotIn("retained memory", controller.system_prompt(task))
        controller.observe(task, True, "    return a+b\n", "")
        self.assertIn("retained memory", controller.system_prompt(task))

    def test_analysis_confirmed_at_25_percent(self):
        config = ProtocolConfig(tasks_per_agent=1, max_live_calls=60, bootstrap_samples=1000)
        outcomes = []
        for agent in range(10):
            outcomes.append(TaskOutcome("swarm", agent, f"t{agent}", True, 1, 60, 15, 0, 0, 75, 1, 1, "passed", "swarm"))
            outcomes.append(TaskOutcome("baseline", agent, f"t{agent}", True, 1, 80, 20, 0, 0, 100, 1, 1, "passed", "swarm"))
        report = analyze(outcomes, config)
        self.assertEqual(report["verdict"], "CONFIRMED")
        self.assertAlmostEqual(report["token_reduction"], 0.25)

    def test_analysis_rejects_ten_percent(self):
        config = ProtocolConfig(tasks_per_agent=1, max_live_calls=60, bootstrap_samples=1000)
        outcomes = []
        for agent in range(10):
            outcomes.append(TaskOutcome("swarm", agent, f"t{agent}", True, 1, 80, 10, 0, 0, 90, 1, 1, "passed", "baseline"))
            outcomes.append(TaskOutcome("baseline", agent, f"t{agent}", True, 1, 90, 10, 0, 0, 100, 1, 1, "passed", "baseline"))
        self.assertEqual(analyze(outcomes, config)["verdict"], "NOT_CONFIRMED")

    def test_end_to_end_10x10_fake_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_path = root / "tasks.jsonl"
            write_tasks(tasks_path, 10)
            config = ProtocolConfig(tasks_per_agent=1, max_live_calls=60, bootstrap_samples=1000)
            runner = BenchmarkRunner(config=config, provider=FakeProvider(), tasks_path=tasks_path, output_dir=root / "results")
            report = runner.run()
            self.assertEqual(report["verdict"], "CONFIRMED")
            self.assertEqual(report["swarm"]["observations"], 10)
            self.assertEqual(report["baseline"]["observations"], 10)
            self.assertTrue((root / "results" / "attempts.jsonl").is_file())

    def test_resume_after_interruption_between_conditions(self):
        class InterruptOnce(FakeProvider):
            def __init__(self):
                self.calls = 0
            def generate(self, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("synthetic interruption")
                return super().generate(**kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_path = root / "tasks.jsonl"
            write_tasks(tasks_path, 10)
            config = ProtocolConfig(tasks_per_agent=1, max_live_calls=60, bootstrap_samples=200)
            output = root / "results"
            with self.assertRaises(RuntimeError):
                BenchmarkRunner(config=config, provider=InterruptOnce(), tasks_path=tasks_path, output_dir=output).run()
            checkpoint = json.loads((output / "checkpoint.json").read_text())
            self.assertEqual(len(checkpoint["outcomes"]), 1)
            report = BenchmarkRunner(config=config, provider=FakeProvider(), tasks_path=tasks_path, output_dir=output, resume=True).run()
            self.assertEqual(report["swarm"]["observations"], 10)
            self.assertEqual(report["baseline"]["observations"], 10)
            with (output / "outcomes.jsonl").open(encoding="utf-8") as handle:
                self.assertEqual(sum(1 for _ in handle), 20)

    def test_sonnet5_uses_default_sampling(self):
        config_path = Path(__file__).parents[2] / "examples" / "final_protocol.json"
        config = ProtocolConfig.load(config_path)
        self.assertEqual(config.model, "claude-sonnet-4-6")
        self.assertIsNone(config.temperature)

    def test_final_protocol_has_160_pairs_and_960_max_calls(self):
        config_path = Path(__file__).parents[2] / "examples" / "final_protocol.json"
        config = ProtocolConfig.load(config_path)
        config.validate()
        self.assertEqual(config.agents_per_condition * config.tasks_per_agent, 160)
        self.assertEqual(config.agents_per_condition * config.tasks_per_agent * config.max_attempts * 2, 960)


if __name__ == "__main__":
    unittest.main()
