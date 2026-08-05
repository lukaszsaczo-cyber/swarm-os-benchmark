from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Callable

from .analysis import analyze, render_markdown
from .code_extract import normalize_completion
from .controller import StatelessController, SwarmController
from .dataset import BenchmarkTask, load_tasks
from .evaluator import Evaluation, SandboxConfig, evaluate
from .models import AttemptRecord, EngineState, MemoryEntry, TaskOutcome, WorkingObservation
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
        f"Status: {status}. Error tail:\n{tail[:1800]}\n"
        "Return only a corrected Python function body, with no explanation or Markdown."
    )


def _task_message(task: BenchmarkTask) -> str:
    return (
        "Complete the missing body of this Python function. Return only the body code, already indented for the function.\n\n"
        + task.prompt
    )


def _make_swarm(agent_id: int, config: ProtocolConfig) -> SwarmController:
    return SwarmController(
        agent_id=agent_id,
        cycle_length=config.cycle_length,
        max_intuitive_entries=config.max_intuitive_entries,
        max_prompt_memory_entries=config.max_prompt_memory_entries,
        min_keyword_overlap=config.memory_min_keyword_overlap,
        min_jaccard=config.memory_min_jaccard,
        memory_recall_fuel=config.memory_recall_fuel,
        vertical_threshold=config.vertical_threshold,
        crystallization_threshold=config.crystallization_threshold,
        rhythm_threshold=config.rhythm_threshold,
        stagnation_threshold=config.stagnation_threshold,
        crack_threshold=config.crack_threshold,
        first_collapse_fuel=config.first_collapse_fuel,
        first_collapse_balance=config.first_collapse_balance,
        first_collapse_persistence=config.first_collapse_persistence,
        recovery_fuel=config.recovery_fuel,
        recovery_balance=config.recovery_balance,
        recovery_window=config.recovery_window,
        stagnation_persistence=config.stagnation_persistence,
        crack_persistence=config.crack_persistence,
    )


def _restore_swarm(data: dict[str, Any], config: ProtocolConfig) -> SwarmController:
    controller = _make_swarm(int(data["agent_id"]), config)
    controller.state = EngineState(**data["state"])
    controller.intuitive_memory = [MemoryEntry(**entry) for entry in data.get("intuitive_memory", [])]
    controller.working_memory = [WorkingObservation(**entry) for entry in data.get("working_memory", [])]
    controller.transient_failures = list(data.get("transient_failures", []))
    controller.pending_intuitive = [MemoryEntry(**entry) for entry in data.get("pending_intuitive", [])]
    controller.phase_history = list(data.get("phase_history", []))
    return controller


def _controller_snapshot(controller: SwarmController) -> dict[str, Any]:
    return {
        "agent_id": controller.agent_id,
        "state": controller.state.to_dict(),
        "intuitive_memory": [asdict(entry) for entry in controller.intuitive_memory],
        "working_memory": [asdict(entry) for entry in controller.working_memory],
        "transient_failures": list(controller.transient_failures),
        "pending_intuitive": [asdict(entry) for entry in controller.pending_intuitive],
        "phase_history": list(controller.phase_history),
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
        evaluator_fn: Callable[[BenchmarkTask, str, SandboxConfig | None], Evaluation] = evaluate,
    ) -> None:
        self.config = config
        self.config.validate()
        self.provider = provider
        self.evaluator_fn = evaluator_fn
        self.tasks_path = Path(tasks_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = load_tasks(self.tasks_path)
        self.assignments = assign_tasks(self.tasks, config)
        self.attempts_path = self.output_dir / "attempts.jsonl"
        self.outcomes_path = self.output_dir / "outcomes.jsonl"
        self.checkpoint_path = self.output_dir / "checkpoint.json"
        self.swarm = {i: _make_swarm(i, config) for i in range(config.agents_per_condition)}
        self.baseline = {i: StatelessController(i) for i in range(config.agents_per_condition)}
        self.outcomes: list[TaskOutcome] = []
        self.completed: set[str] = set()
        self.api_calls: int = 0
        if resume:
            self._load_checkpoint()
        elif self.attempts_path.exists() or self.outcomes_path.exists():
            raise FileExistsError(f"Output directory is not empty: {self.output_dir}; use --resume or a new directory")

        manifest = {
            "schema_version": "5.0",
            "dataset": str(self.tasks_path),
            "dataset_sha256": dataset_sha256(self.tasks_path),
            "protocol": config.to_dict(),
            "assignment": {str(k): [task.task_id for task in v] for k, v in self.assignments.items()},
            "worst_case_api_calls": config.agents_per_condition * config.tasks_per_agent * config.max_attempts * 2,
            "prompt_caching": False,
            "memory_cycle": "KRYSTALIZACJA -> RYTM -> STAGNACJA -> PĘKNIĘCIE -> ROZPAD_II -> 3 -> 6 -> 28 -> 40 -> RÓŻNICA",
            "first_collapse": "loss of fuel/balance before crystallization -> ROZPAD_I -> REGULACJA recovery or 40 without retained intuition",
            "cycle_trigger": "dynamic metrics; task count is a working-memory safety ceiling only",
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
        self.swarm = {int(key): _restore_swarm(value, self.config) for key, value in data["swarm_controllers"].items()}

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
        first_system = controller.system_prompt(task)
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
            system = first_system if attempt == 1 else controller.retry_system_prompt(task)
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
            result = self.evaluator_fn(task, completion, SandboxConfig(self.config.timeout_seconds, self.config.memory_mb))
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

        controller.observe(
            task,
            passed,
            final_completion,
            final_error,
            attempts=len(records),
            max_attempts=self.config.max_attempts,
        )
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
