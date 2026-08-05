import json
import tempfile
import unittest
from pathlib import Path

from swarm_validation.controller import BASE_SYSTEM, SwarmController
from swarm_validation.dataset import BenchmarkTask
from swarm_validation.evaluator import Evaluation
from swarm_validation.models import ProviderResponse, Usage
from swarm_validation.protocol import ProtocolConfig
from swarm_validation.runner import BenchmarkRunner


def task(i, topic="sequence list sum"):
    return BenchmarkTask(
        f"t/{i}",
        f'def value_{i}():\n    """{topic}; return integer {i}."""\n',
        f"def check(candidate):\n    assert candidate() == {i}",
        f"value_{i}",
    )


def fast_evaluate(task, completion, config=None):
    expected = int(task.task_id.split("/")[-1])
    passed = f"return {expected}" in completion
    return Evaluation(
        passed,
        "passed" if passed else "failed",
        0.1,
        0 if passed else 1,
        "",
        "" if passed else "AssertionError",
    )


class InspectProvider:
    def __init__(self):
        self.calls = []

    def generate(self, *, model, system, messages, max_tokens, temperature, metadata=None):
        self.calls.append((metadata.copy(), system, [dict(item) for item in messages]))
        expected = int(metadata["task_id"].split("/")[-1])
        attempt = metadata["attempt"]
        text = f"    return {expected if attempt > 1 else expected + 1}\n"
        chars = len(system) + sum(len(item["content"]) for item in messages)
        return ProviderResponse(
            text,
            Usage(60 + chars // 4, 8),
            model,
            "end_turn",
            1.0,
            "x",
        )


def drive_to_rhythm(controller: SwarmController, start: int = 1) -> int:
    index = start
    while controller.state.phase != "RYTM":
        controller.observe(task(index), True, f"    return {index}\n", "", attempts=1)
        index += 1
        if index - start > 12:
            raise AssertionError(controller.phase_history)
    return index


def drive_second_collapse(controller: SwarmController, start: int = 1) -> int:
    index = drive_to_rhythm(controller, start)
    while controller.state.phase != "40":
        controller.observe(task(index), False, "", "AssertionError", attempts=3)
        index += 1
        if index - start > 20:
            raise AssertionError(controller.phase_history)
    return index


class CycleMemoryTests(unittest.TestCase):
    def test_stable_rhythm_does_not_collapse_by_task_count(self):
        controller = SwarmController(0, cycle_length=4)
        for index in range(1, 17):
            controller.observe(task(index), True, f"    return {index}\n", "", attempts=1)
        self.assertEqual(controller.state.phase, "RYTM")
        self.assertNotIn("ROZPAD_II", controller.phase_history)
        self.assertFalse(controller.pending_intuitive)

    def test_second_collapse_requires_crystal_rhythm_stagnation_and_crack(self):
        controller = SwarmController(0)
        drive_second_collapse(controller)
        expected = [
            "KRYSTALIZACJA",
            "RYTM",
            "STAGNACJA",
            "PĘKNIĘCIE",
            "ROZPAD_II",
            "3",
            "6",
            "28",
            "40",
        ]
        positions = [controller.phase_history.index(phase) for phase in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(controller.state.collapse_two_count, 1)

    def test_40_is_threshold_and_new_cycle_starts_through_difference(self):
        controller = SwarmController(0)
        next_index = drive_second_collapse(controller)
        self.assertEqual(controller.state.phase, "40")
        self.assertTrue(controller.working_memory)
        self.assertFalse(controller.intuitive_memory)
        self.assertTrue(controller.pending_intuitive)

        prompt = controller.system_prompt(task(next_index))
        self.assertEqual(controller.state.phase, "RÓŻNICA")
        self.assertEqual(controller.state.cycle_index, 1)
        self.assertFalse(controller.working_memory)
        self.assertTrue(controller.intuitive_memory)
        self.assertIn("40→RÓŻNICA", controller.phase_history)
        self.assertIn("Prior-cycle intuition", prompt)

    def test_failures_are_destroyed_at_6(self):
        controller = SwarmController(0)
        drive_second_collapse(controller)
        self.assertFalse(controller.transient_failures)
        self.assertTrue(all(entry.passed for entry in controller.pending_intuitive))
        self.assertTrue(all("return " not in entry.lesson for entry in controller.pending_intuitive))

    def test_first_collapse_can_return_to_regulation_in_same_cycle(self):
        controller = SwarmController(0)
        controller.observe(task(1), False, "", "AssertionError", attempts=3)
        controller.observe(task(2), False, "", "AssertionError", attempts=3)
        self.assertEqual(controller.state.phase, "ROZPAD_I")
        controller.observe(task(3), True, "    return 3\n", "", attempts=1)
        controller.observe(task(4), True, "    return 4\n", "", attempts=1)
        self.assertEqual(controller.state.phase, "REGULACJA")
        self.assertEqual(controller.state.cycle_index, 0)
        self.assertFalse(controller.pending_intuitive)

    def test_unrecovered_first_collapse_reaches_40_without_intuition(self):
        controller = SwarmController(0, recovery_window=2)
        controller.observe(task(1), False, "", "AssertionError", attempts=3)
        controller.observe(task(2), False, "", "AssertionError", attempts=3)
        self.assertEqual(controller.state.phase, "ROZPAD_I")
        controller.observe(task(3), False, "", "AssertionError", attempts=3)
        controller.observe(task(4), False, "", "AssertionError", attempts=3)
        self.assertEqual(controller.state.phase, "40")
        self.assertFalse(controller.pending_intuitive)
        controller.system_prompt(task(5))
        self.assertEqual(controller.state.phase, "RÓŻNICA")
        self.assertFalse(controller.intuitive_memory)

    def test_low_fuel_blocks_intuitive_recall(self):
        controller = SwarmController(0)
        next_index = drive_second_collapse(controller)
        controller.system_prompt(task(next_index))
        self.assertTrue(controller.intuitive_memory)
        controller.state.fuel = controller.memory_recall_fuel - 0.01
        self.assertEqual(controller.system_prompt(task(next_index + 1)), BASE_SYSTEM)

    def test_irrelevant_intuitive_memory_is_rejected(self):
        controller = SwarmController(0)
        next_index = drive_second_collapse(controller)
        controller.system_prompt(task(next_index, "sequence list sum"))
        self.assertEqual(
            controller.system_prompt(task(next_index + 1, "graph vertex edge traversal")),
            BASE_SYSTEM,
        )

    def test_raw_code_never_becomes_intuitive_memory(self):
        controller = SwarmController(0)
        next_index = drive_second_collapse(controller)
        controller.system_prompt(task(next_index))
        self.assertTrue(controller.intuitive_memory)
        self.assertTrue(
            all("return 1" not in entry.lesson for entry in controller.intuitive_memory)
        )

    def test_retry_drops_memory_but_keeps_feedback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_path = root / "tasks.jsonl"
            with tasks_path.open("w", encoding="utf-8") as handle:
                for index in range(10):
                    item = task(index)
                    handle.write(
                        json.dumps(
                            {
                                "task_id": item.task_id,
                                "prompt": item.prompt,
                                "test": item.test,
                                "entry_point": item.entry_point,
                            }
                        )
                        + "\n"
                    )
            provider = InspectProvider()
            config = ProtocolConfig(
                tasks_per_agent=1,
                max_live_calls=60,
                bootstrap_samples=100,
            )
            BenchmarkRunner(
                config=config,
                provider=provider,
                tasks_path=tasks_path,
                output_dir=root / "out",
                evaluator_fn=fast_evaluate,
            ).run()
            swarm_calls = [
                call for call in provider.calls if call[0]["condition"] == "swarm"
            ]
            retry = [call for call in swarm_calls if call[0]["attempt"] == 2][0]
            self.assertEqual(retry[1], BASE_SYSTEM)
            self.assertGreater(len(retry[2]), 1)

    def test_success_increases_fuel_failure_decreases_fuel(self):
        success = SwarmController(0)
        before = success.state.fuel
        success.observe(task(1), True, "    return 1\n", "", attempts=1)
        self.assertGreater(success.state.fuel, before)

        failure = SwarmController(0)
        before = failure.state.fuel
        failure.observe(task(1), False, "", "x", attempts=3)
        self.assertLess(failure.state.fuel, before)


if __name__ == "__main__":
    unittest.main()
