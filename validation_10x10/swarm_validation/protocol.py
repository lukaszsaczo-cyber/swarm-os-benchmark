from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from .dataset import BenchmarkTask


@dataclass(frozen=True)
class ProtocolConfig:
    model: str = "claude-sonnet-4-6"
    agents_per_condition: int = 10
    tasks_per_agent: int = 16
    assignment_seed: int = 20260801
    call_order_seed: int = 330016
    max_attempts: int = 3
    max_tokens: int = 2048
    temperature: float | None = None
    timeout_seconds: float = 3.0
    memory_mb: int = 512
    target_token_reduction: float = 0.20
    quality_noninferiority_margin: float = 0.02
    bootstrap_samples: int = 20000
    max_live_calls: int = 960
    pricing_input_usd_per_million: float | None = None
    pricing_output_usd_per_million: float | None = None

    # Legacy name retained for config compatibility. It is now only a safety ceiling;
    # ROZPAD II is caused by rhythm loss after crystallization, never by task count.
    cycle_length: int = 16
    max_intuitive_entries: int = 4
    max_prompt_memory_entries: int = 1
    memory_min_keyword_overlap: int = 2
    memory_min_jaccard: float = 0.08
    memory_recall_fuel: float = 0.42

    vertical_threshold: float = 0.62
    crystallization_threshold: float = 0.66
    rhythm_threshold: float = 0.62
    stagnation_threshold: float = 0.46
    crack_threshold: float = 0.34
    first_collapse_fuel: float = 0.24
    first_collapse_balance: float = 0.30
    first_collapse_persistence: int = 2
    recovery_fuel: float = 0.44
    recovery_balance: float = 0.42
    recovery_window: int = 3
    stagnation_persistence: int = 2
    crack_persistence: int = 3

    @classmethod
    def load(cls, path: str | Path) -> "ProtocolConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if self.agents_per_condition != 10:
            raise ValueError("Final protocol requires exactly 10 agents per condition")
        if self.tasks_per_agent < 1 or self.max_attempts < 1 or self.cycle_length < 1:
            raise ValueError("tasks_per_agent, max_attempts and cycle_length must be positive")
        expected = self.agents_per_condition * self.tasks_per_agent * self.max_attempts * 2
        if self.max_live_calls < expected:
            raise ValueError(
                f"max_live_calls={self.max_live_calls} is below worst-case protocol calls={expected}"
            )
        bounded = {
            "memory_recall_fuel": self.memory_recall_fuel,
            "vertical_threshold": self.vertical_threshold,
            "crystallization_threshold": self.crystallization_threshold,
            "rhythm_threshold": self.rhythm_threshold,
            "stagnation_threshold": self.stagnation_threshold,
            "crack_threshold": self.crack_threshold,
            "first_collapse_fuel": self.first_collapse_fuel,
            "first_collapse_balance": self.first_collapse_balance,
            "recovery_fuel": self.recovery_fuel,
            "recovery_balance": self.recovery_balance,
        }
        for name, value in bounded.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name, value in {
            "first_collapse_persistence": self.first_collapse_persistence,
            "recovery_window": self.recovery_window,
            "stagnation_persistence": self.stagnation_persistence,
            "crack_persistence": self.crack_persistence,
        }.items():
            if value < 1:
                raise ValueError(f"{name} must be positive")


def assign_tasks(tasks: list[BenchmarkTask], config: ProtocolConfig) -> dict[int, list[BenchmarkTask]]:
    config.validate()
    needed = config.agents_per_condition * config.tasks_per_agent
    if len(tasks) < needed:
        raise ValueError(f"Dataset has {len(tasks)} tasks; final protocol requires at least {needed}")
    selected = list(tasks)
    random.Random(config.assignment_seed).shuffle(selected)
    selected = selected[:needed]
    return {
        agent_id: selected[
            agent_id * config.tasks_per_agent : (agent_id + 1) * config.tasks_per_agent
        ]
        for agent_id in range(config.agents_per_condition)
    }


def dataset_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
