from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    def to_dict(self) -> dict[str, int]:
        return asdict(self) | {"total_tokens": self.total_tokens}


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    usage: Usage
    model: str
    stop_reason: str | None
    latency_ms: float
    request_id: str | None = None


@dataclass
class MemoryEntry:
    task_id: str
    keywords: list[str]
    lesson: str
    passed: bool = True
    cycle_index: int = 0
    confidence: float = 1.0
    evidence_count: int = 1


@dataclass
class WorkingObservation:
    task_id: str
    keywords: list[str]
    lesson: str
    passed: bool
    status: str
    cycle_index: int


@dataclass
class EngineState:
    fuel: float = 1.0
    memory: float = 0.0
    entropy: float = 0.0
    state: str = "A"
    solved_count: int = 0
    previous_w: float = 0.5
    cycle_index: int = 0
    tasks_in_cycle: int = 0
    phase: str = "ACTIVE"
    spiral_level: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AttemptRecord:
    condition: str
    agent_id: int
    task_id: str
    attempt: int
    call_order: int
    model: str
    prompt_sha256: str
    system_prompt: str
    messages: list[dict[str, Any]]
    raw_response: str
    completion: str
    usage: dict[str, int]
    provider_latency_ms: float
    stop_reason: str | None
    request_id: str | None
    passed: bool
    status: str
    execution_ms: float
    stderr: str
    engine_before: dict[str, Any] | None = None
    engine_after: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskOutcome:
    condition: str
    agent_id: int
    task_id: str
    passed: bool
    attempts: int
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    total_tokens: int
    provider_latency_ms: float
    execution_ms: float
    final_status: str
    call_first: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
