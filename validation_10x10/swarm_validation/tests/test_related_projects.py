from __future__ import annotations

import unittest

from swarm_validation.analysis import analyze, render_markdown
from swarm_validation.controller import BASE_SYSTEM, SwarmController
from swarm_validation.dataset import BenchmarkTask
from swarm_validation.models import TaskOutcome, WorkingObservation
from swarm_validation.protocol import ProtocolConfig, assign_tasks


class RelatedProjectAssignmentTests(unittest.TestCase):
    def test_project_sequence_keeps_one_ordered_project_per_agent(self) -> None:
        tasks = []
        for project_index in range(10):
            project_id = f"project_{project_index}"
            for step in range(1, 3):
                tasks.append(
                    BenchmarkTask(
                        task_id=f"{project_id}::{step:02d}",
                        prompt=f"# Project convention: stable order\ndef f_{project_index}_{step}():\n",
                        test="def check(candidate):\n    assert True\n",
                        entry_point=f"f_{project_index}_{step}",
                        metadata={"project_id": project_id, "step_index": step},
                    )
                )
        config = ProtocolConfig(
            tasks_per_agent=2,
            assignment_mode="project_sequence",
            max_live_calls=120,
        )
        assigned = assign_tasks(tasks, config)
        self.assertEqual(set(assigned), set(range(10)))
        for sequence in assigned.values():
            project_ids = {(item.metadata or {})["project_id"] for item in sequence}
            self.assertEqual(len(project_ids), 1)
            self.assertEqual([(item.metadata or {})["step_index"] for item in sequence], [1, 2])

    def test_project_sequence_rejects_missing_metadata(self) -> None:
        tasks = [
            BenchmarkTask(
                task_id=f"task_{index}",
                prompt=f"def f_{index}():\n",
                test="def check(candidate):\n    assert True\n",
                entry_point=f"f_{index}",
            )
            for index in range(20)
        ]
        config = ProtocolConfig(
            tasks_per_agent=2,
            assignment_mode="project_sequence",
            max_live_calls=120,
        )
        with self.assertRaises(ValueError):
            assign_tasks(tasks, config)


class WorkingMemoryTests(unittest.TestCase):
    def task(self) -> BenchmarkTask:
        return BenchmarkTask(
            task_id="orders::02",
            prompt=(
                "# Project: orders\n"
                "# Project convention: canonical order status mapping\n"
                "def orders_valid(values):\n"
            ),
            test="def check(candidate):\n    assert True\n",
            entry_point="orders_valid",
            metadata={"project_id": "orders", "step_index": 2},
        )

    def test_only_passed_same_project_working_evidence_is_recalled(self) -> None:
        controller = SwarmController(agent_id=0)
        controller.state.fuel = 1.0
        controller.state.phase = "REGULACJA"
        controller.state.state = "REGULACJA"
        controller.working_memory = [
            WorkingObservation(
                task_id="orders::01",
                keywords=["orders", "canonical", "status", "mapping"],
                lesson="Text processing: boundary guards. Project convention: canonical order status mapping",
                passed=True,
                status="passed",
                cycle_index=0,
                quality=1.0,
                phase="NAPIĘCIE",
            ),
            WorkingObservation(
                task_id="access::01",
                keywords=["orders", "canonical", "status", "mapping"],
                lesson="OTHER PROJECT MUST NOT APPEAR",
                passed=True,
                status="passed",
                cycle_index=0,
                quality=1.0,
                phase="NAPIĘCIE",
            ),
            WorkingObservation(
                task_id="orders::00",
                keywords=["orders", "canonical", "status", "mapping"],
                lesson="FAILED EVIDENCE MUST NOT APPEAR",
                passed=False,
                status="failed",
                cycle_index=0,
                quality=0.0,
                phase="NAPIĘCIE",
            ),
        ]
        prompt = controller.system_prompt(self.task())
        self.assertIn("Current-cycle working guidance", prompt)
        self.assertIn("canonical order status mapping", prompt)
        self.assertNotIn("OTHER PROJECT", prompt)
        self.assertNotIn("FAILED EVIDENCE", prompt)

    def test_retry_never_receives_memory(self) -> None:
        controller = SwarmController(agent_id=0)
        self.assertEqual(controller.retry_system_prompt(self.task()), BASE_SYSTEM)

    def test_humaneval_style_task_does_not_use_working_memory(self) -> None:
        controller = SwarmController(agent_id=0)
        controller.state.fuel = 1.0
        controller.working_memory = [
            WorkingObservation(
                task_id="HumanEval/0",
                keywords=["sequence", "values"],
                lesson="MUST NOT APPEAR",
                passed=True,
                status="passed",
                cycle_index=0,
                quality=1.0,
                phase="NAPIĘCIE",
            )
        ]
        task = BenchmarkTask(
            task_id="HumanEval/1",
            prompt="def solve(values):\n",
            test="def check(candidate):\n    assert True\n",
            entry_point="solve",
        )
        self.assertNotIn("MUST NOT APPEAR", controller.system_prompt(task))


class BusinessMetricsTests(unittest.TestCase):
    def test_report_contains_cost_per_passed_task(self) -> None:
        config = ProtocolConfig(
            tasks_per_agent=1,
            bootstrap_samples=100,
            pricing_input_usd_per_million=3.0,
            pricing_output_usd_per_million=15.0,
        )
        outcomes = []
        for agent_id in range(10):
            outcomes.append(
                TaskOutcome(
                    condition="swarm",
                    agent_id=agent_id,
                    task_id=f"p{agent_id}::01",
                    passed=True,
                    attempts=1,
                    input_tokens=90,
                    output_tokens=10,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                    total_tokens=100,
                    provider_latency_ms=1.0,
                    execution_ms=1.0,
                    final_status="passed",
                    call_first="swarm",
                )
            )
            outcomes.append(
                TaskOutcome(
                    condition="baseline",
                    agent_id=agent_id,
                    task_id=f"p{agent_id}::01",
                    passed=True,
                    attempts=1,
                    input_tokens=100,
                    output_tokens=10,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                    total_tokens=110,
                    provider_latency_ms=1.0,
                    execution_ms=1.0,
                    final_status="passed",
                    call_first="swarm",
                )
            )
        report = analyze(outcomes, config)
        self.assertAlmostEqual(report["swarm"]["tokens_per_passed_task"], 100.0)
        self.assertGreater(report["token_per_passed_task_reduction"], 0.0)
        self.assertGreater(report["cost_per_passed_task_reduction"], 0.0)
        markdown = render_markdown(report)
        self.assertIn("Cost per passed task", markdown)


if __name__ == "__main__":
    unittest.main()
