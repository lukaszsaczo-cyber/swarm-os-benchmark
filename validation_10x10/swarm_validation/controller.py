from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .dataset import BenchmarkTask
from .models import EngineState, MemoryEntry

BASE_SYSTEM = """You are solving a Python function-completion benchmark. Return only executable Python code for the missing function body. Do not use Markdown fences, explanations, tests, imports unrelated to the task, files, network access, subprocesses, or external packages. Keep the solution concise and deterministic."""


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    stop = {"def", "return", "the", "and", "for", "with", "from", "that", "this", "function", "python"}
    return sorted({word for word in words if word not in stop})[:40]


def _compact(text: str, limit: int = 260) -> str:
    value = " ".join(text.replace("\n", " ").split())
    return value if len(value) <= limit else value[: limit - 3] + "..."


@dataclass
class SwarmController:
    agent_id: int
    E: float = 0.9
    kappa: float = 1.4
    rho: float = 0.6
    rate: float = 0.25
    alpha: float = 0.1
    erosion: float = 0.05
    max_memory_entries: int = 4
    state: EngineState = field(default_factory=EngineState)
    entries: list[MemoryEntry] = field(default_factory=list)

    def system_prompt(self, task: BenchmarkTask) -> str:
        selected = self._select(task)
        if not selected:
            return BASE_SYSTEM
        memory = "\n".join(f"- {entry.lesson}" for entry in selected)
        return BASE_SYSTEM + "\n\nSWARM_OS retained memory (use only when relevant; never copy blindly):\n" + memory

    def _select(self, task: BenchmarkTask) -> list[MemoryEntry]:
        if not self.entries or self.state.memory <= 0:
            return []
        slots = min(self.max_memory_entries, max(1, math.ceil(self.state.memory * 4)))
        task_words = set(_keywords(task.prompt + " " + task.entry_point))
        scored = []
        for index, entry in enumerate(self.entries):
            overlap = len(task_words.intersection(entry.keywords))
            scored.append((overlap, index, entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[:slots]]

    def observe(self, task: BenchmarkTask, passed: bool, completion: str, final_error: str) -> None:
        w = 1.0 if passed else 0.0
        d_w = abs(w - 0.5)
        self.state.fuel += (self.E - self.kappa * w - self.rho * d_w) * self.rate
        if self.state.fuel > 0:
            self.state.memory += self.alpha * self.state.fuel
        else:
            self.state.memory *= 1 - self.erosion
        self.state.memory = max(0.0, min(2.0, self.state.memory))
        if self.state.fuel < self.kappa * w * self.rate or w < 0.3:
            self.state.state = "Q"
            self.state.fuel = 0.5
            self.state.memory *= 0.5
        else:
            self.state.state = "A"
            self.state.solved_count += 1
        self.state.previous_w = w

        if passed:
            lesson = f"{task.entry_point}: successful pattern: {_compact(completion)}"
        else:
            lesson = f"{task.entry_point}: avoid final failure: {_compact(final_error or 'unknown failure')}"
        self.entries.append(MemoryEntry(task.task_id, _keywords(task.prompt + " " + completion), lesson, passed))
        if len(self.entries) > 24:
            self.entries = self.entries[-24:]


@dataclass
class StatelessController:
    agent_id: int

    def system_prompt(self, task: BenchmarkTask) -> str:
        return BASE_SYSTEM

    def observe(self, task: BenchmarkTask, passed: bool, completion: str, final_error: str) -> None:
        return None
