from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from .analysis import analyze, render_markdown
from .code_extract import normalize_completion
from .controller import StatelessController, SwarmController
from .dataset import BenchmarkTask, load_tasks
from .evaluator import SandboxConfig, evaluate
from .models import AttemptRecord, TaskOutcome
from .protocol import ProtocolConfig, assign_tasks, dataset_sha256
from .provider import Provider


def _json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def _prompt_hash(system: str, messages: list[dict[str, Any]]) -> str:
    payload = json.dumps({"system": system, "messages": messages}, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _error_feedback(status: str, stderr: str) -> str:
    tail = "\n".join((stderr or "").splitlines()[-12:])
    return (
        "The previous candidate failed the local unit tests. "
        f"Status: {status}. Error tail:\n{tail[:2400]}\n"
        "Return only a corrected Python function body, with no explanation or Markdown."
    )


def _task_message(task: BenchmarkTask) -> str:
    return (
        "Complete the missing body of this Python function. Return only the body code, already indented for the function.\n\n"
        + task.prompt
    )


def _restore_swarm(data: dict[str, Any]) -> SwarmController:
    from .models import EngineState, MemoryEntry
    controller = SwarmController(agent_id=int(data["agent_id"]))
    controller.state = EngineState(**data["state"])
    controller.entries = [MemoryEntry(**entry) for entry in data.get("entries", [])]
    return controller


def _controller_snapshot(controller: SwarmController) -> dict[str, Any]:
    return {
        "agent_id": controller.agent_id,
        "state": controller.state.to_dict(),
        "entries": [asdict(entry) for entry in controller.entries],
    }


class BenchmarkRunner:
    def __init__(
        self,
        *,
        config: ProtocolConfig,
        provider: Provider,
        tasks_path: str | Path,
        output_dir: str | Path,
        resume: bool = False,
    ) -> None:
        self.config = config
        self.config.validate()
        self.provider = provider
        self.tasks_path = Path(tasks_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = load_tasks(self.tasks_path)
        self.assignments = assign_tasks(self.tasks, config)
        self.attempts_path = self.output_dir / "attempts.jsonl"
        self.outcomes_path = self.output_dir / "outcomes.jsonl"
        self.checkpoint_path = self.output_dir / "checkpoint.json"
        self.swarm = {i: SwarmController(i) for i in range(config.agents_per_condition)}
        self.baseline = {i: StatelessController(i) for i in range(config.agents_per_condition)}
        self.outcomes: list[TaskOutcome] = []
        self.completed: set[str] = set()
        self.api_calls: int = 0
        if resume:
            self._load_checkpoint()
        elif self.attempts_path.exists() or self.outcomes_path.exists():
            raise FileExistsError(f"Output directory is not empty: {self.output_dir}; use --resume or a new directory")

        manifest = {
            "schema_version": "3.0",
            "dataset": str(self.tasks_path),
            "dataset_sha256": dataset_sha256(self.tasks_path),
            "protocol": config.to_dict(),
            "assignment": {str(k): [task.task_id for task in v] for k, v in self.assignments.items()},
            "worst_case_api_calls": config.agents_per_condition * config.tasks_per_agent * config.max_attempts * 2,
            "prompt_caching": False,
        }
        _json_dump(self.output_dir / "manifest.json", manifest)

    def _load_checkpoint(self) -> None:
        if not self.checkpoint_path.exists():
            raise FileNotFoundError("--resume requires checkpoint.json")
        data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        expected_protocol = hashlib.sha256(json.dumps(self.config.to_dict(), sort_keys=True).encode()).hexdigest()
        expected_dataset = dataset_sha256(self.tasks_path)
        if data.get("protocol_sha256") != expected_protocol or data.get("dataset_sha256") != expected_dataset:
            raise ValueError("Checkpoint protocol or dataset does not match the requested run")
        self.completed = set(data.get("completed", []))
        self.outcomes = [TaskOutcome(**item) for item in data.get("outcomes", [])]
        self.api_calls = int(data.get("api_calls", 0))
        self.swarm = {int(key): _restore_swarm(value) for key, value in data["swarm_controllers"].items()}

    def _save_checkpoint(self) -> None:
        data = {
            "protocol_sha256": hashlib.sha256(json.dumps(self.config.to_dict(), sort_keys=True).encode()).hexdigest(),
            "dataset_sha256": dataset_sha256(self.tasks_path),
            "api_calls": self.api_calls,
            "completed": sorted(self.completed),
            "outcomes": [item.to_dict() for item in self.outcomes],
            "swarm_controllers": {str(key): _controller_snapshot(value) for key, value in self.swarm.items()},
        }
        _json_dump(self.checkpoint_path, data)

    def _solve(
        self,
        *,
        condition: str,
        agent_id: int,
        task: BenchmarkTask,
        call_first: str,
        call_order: int,
    ) -> TaskOutcome:
        controller = self.swarm[agent_id] if condition == "swarm" else self.baseline[agent_id]
        system = controller.system_prompt(task)
        messages: list[dict[str, Any]] = [{"role": "user", "content": _task_message(task)}]
        total_input = total_output = total_cache_create = total_cache_read = 0
        total_latency = total_execution = 0.0
        passed = False
        final_status = "not_run"
        final_completion = ""
        final_error = ""
        engine_before = self.swarm[agent_id].state.to_dict() if condition == "swarm" else None
        records: list[AttemptRecord] = []

        for attempt in range(1, self.config.max_attempts + 1):
            self.api_calls += 1
            if self.api_calls > self.config.max_live_calls:
                raise RuntimeError(f"Application API-call guard exceeded: {self.config.max_live_calls}")
            response = self.provider.generate(
                model=self.config.model,
                system=system,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                metadata={"condition": condition, "agent_id": agent_id, "task_id": task.task_id, "attempt": attempt},
            )
            completion = normalize_completion(response.text, task.prompt, task.entry_point)
            result = evaluate(task, completion, SandboxConfig(self.config.timeout_seconds, self.config.memory_mb))
            usage = response.usage
            total_input += usage.input_tokens
            total_output += usage.output_tokens
            total_cache_create += usage.cache_creation_input_tokens
            total_cache_read += usage.cache_read_input_tokens
            total_latency += response.latency_ms
            total_execution += result.execution_ms
            final_status = result.status
            final_completion = completion
            final_error = result.stderr
            record = AttemptRecord(
                condition=condition, agent_id=agent_id, task_id=task.task_id, attempt=attempt,
                call_order=call_order, model=response.model, prompt_sha256=_prompt_hash(system, messages),
                system_prompt=system, messages=[dict(item) for item in messages],
                raw_response=response.text, completion=completion, usage=usage.to_dict(),
                provider_latency_ms=response.latency_ms, stop_reason=response.stop_reason,
                request_id=response.request_id, passed=result.passed, status=result.status,
                execution_ms=result.execution_ms, stderr=result.stderr, engine_before=engine_before,
            )
            records.append(record)
            if result.passed:
                passed = True
                break
            messages = messages + [
                {"role": "assistant", "content": response.text},
                {"role": "user", "content": _error_feedback(result.status, result.stderr)},
            ]

        controller.observe(task, passed, final_completion, final_error)
        engine_after = self.swarm[agent_id].state.to_dict() if condition == "swarm" else None
        if records:
            records[-1].engine_after = engine_after
        for record in records:
            _append_jsonl(self.attempts_path, record.to_dict())

        return TaskOutcome(
            condition=condition, agent_id=agent_id, task_id=task.task_id, passed=passed,
            attempts=len(records), input_tokens=total_input, output_tokens=total_output,
            cache_creation_input_tokens=total_cache_create, cache_read_input_tokens=total_cache_read,
            total_tokens=total_input + total_output + total_cache_create + total_cache_read,
            provider_latency_ms=round(total_latency, 3), execution_ms=round(total_execution, 3),
            final_status=final_status, call_first=call_first,
        )

    def run(self) -> dict[str, Any]:
        order_rng = random.Random(self.config.call_order_seed)
        call_counter = 0
        for agent_id in range(self.config.agents_per_condition):
            for task in self.assignments[agent_id]:
                first = "swarm" if order_rng.random() < 0.5 else "baseline"
                order = [first, "baseline" if first == "swarm" else "swarm"]
                for condition in order:
                    call_counter += 1
                    condition_key = f"{agent_id}:{task.task_id}:{condition}"
                    if condition_key in self.completed:
                        continue
                    outcome = self._solve(
                        condition=condition, agent_id=agent_id, task=task,
                        call_first=first, call_order=call_counter,
                    )
                    self.outcomes.append(outcome)
                    _append_jsonl(self.outcomes_path, outcome.to_dict())
                    self.completed.add(condition_key)
                    self._save_checkpoint()

        report = analyze(self.outcomes, self.config)
        _json_dump(self.output_dir / "report.json", report)
        (self.output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
        return report
