from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .dataset import BenchmarkTask
from .models import EngineState, MemoryEntry, WorkingObservation

BASE_SYSTEM = """You are solving a Python function-completion benchmark. Return only executable Python code for the missing function body. Do not use Markdown fences, explanations, tests, imports unrelated to the task, files, network access, subprocesses, or external packages. Keep the solution concise and deterministic."""

STOP = {
    "def", "return", "the", "and", "for", "with", "from", "that", "this",
    "function", "python", "given", "should", "into", "using", "write",
    "which", "where", "when", "then",
}

PRE_CRYSTAL_PHASES = {"RÓŻNICA", "NAPIĘCIE", "REGULACJA", "DOPASOWANIE", "PION"}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    return sorted(
        {
            word
            for word in words
            if word not in STOP
            and not any(ch.isdigit() for ch in word)
            and word not in {"value", "integer"}
        }
    )[:48]


def _features(completion: str, entry_point: str) -> list[str]:
    wrapper = f"def {entry_point}(*args, **kwargs):\n" + (completion or "    pass\n")
    try:
        tree = ast.parse(wrapper)
    except SyntaxError:
        return ["direct construction"]

    features: list[str] = []
    if any(isinstance(node, (ast.For, ast.While, ast.comprehension)) for node in ast.walk(tree)):
        features.append("bounded iteration")
    if any(
        isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
        for node in ast.walk(tree)
    ):
        features.append("comprehension")
    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    if entry_point in calls:
        features.append("recursion with an explicit base case")
    if any(name in calls for name in ("sorted", "min", "max", "sum", "any", "all")):
        features.append("a standard deterministic reduction")
    if any(isinstance(node, (ast.Set, ast.Dict)) for node in ast.walk(tree)):
        features.append("set or mapping membership")
    if any(isinstance(node, ast.If) for node in ast.walk(tree)):
        features.append("early boundary checks")
    if any(isinstance(node, ast.Subscript) for node in ast.walk(tree)):
        features.append("guarded indexing")
    if not features:
        features.append("a direct minimal transformation")
    return features[:3]


def _generalize(task: BenchmarkTask, completion: str) -> tuple[str, list[str]]:
    keys = _keywords(task.prompt)
    keyset = set(keys)
    if keyset & {"sequence", "list", "array", "sum", "aggregate", "values"}:
        domain = "Sequence processing"
    elif keyset & {"graph", "vertex", "edge", "path", "tree"}:
        domain = "Graph processing"
    elif keyset & {"string", "text", "word", "character"}:
        domain = "Text processing"
    elif keyset & {"number", "numeric", "digit", "prime", "factor"}:
        domain = "Numeric processing"
    else:
        domain = "Matching task structure"
    technique = _features(completion, task.entry_point)[0]
    return f"{domain}: {technique}; boundary guards."[:120], keys


@dataclass
class SwarmController:
    agent_id: int

    # cycle_length remains a memory/safety ceiling only; it never triggers ROZPAD II.
    cycle_length: int = 16
    max_intuitive_entries: int = 4
    max_prompt_memory_entries: int = 1
    min_keyword_overlap: int = 2
    min_jaccard: float = 0.08
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

    state: EngineState = field(default_factory=EngineState)
    intuitive_memory: list[MemoryEntry] = field(default_factory=list)
    working_memory: list[WorkingObservation] = field(default_factory=list)
    transient_failures: list[str] = field(default_factory=list)
    pending_intuitive: list[MemoryEntry] = field(default_factory=list)
    phase_history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.phase_history:
            self.phase_history.append(self.state.phase)

    def _set_phase(self, phase: str) -> None:
        if self.state.phase == phase:
            self.state.phase_age += 1
            return
        self.state.phase = phase
        self.state.state = phase
        self.state.phase_age = 0
        self.phase_history.append(phase)

    def _cross_threshold_40(self) -> None:
        if self.state.phase != "40":
            return

        merged = self.intuitive_memory + self.pending_intuitive
        deduplicated: dict[str, MemoryEntry] = {}
        for entry in merged:
            previous = deduplicated.get(entry.lesson)
            if previous is None or (entry.confidence, entry.cycle_index) > (
                previous.confidence,
                previous.cycle_index,
            ):
                deduplicated[entry.lesson] = entry

        self.intuitive_memory = sorted(
            deduplicated.values(),
            key=lambda entry: (entry.confidence, entry.cycle_index, entry.evidence_count),
            reverse=True,
        )[: self.max_intuitive_entries]

        intuition_strength = sum(entry.confidence for entry in self.intuitive_memory) / max(
            1, len(self.intuitive_memory)
        )
        self.pending_intuitive.clear()
        self.working_memory.clear()
        self.transient_failures.clear()

        self.state.cycle_index += 1
        self.state.tasks_in_cycle = 0
        refreshed_floor = 0.62 if self.intuitive_memory else 0.50
        self.state.fuel = _clamp(
            max(refreshed_floor, self.state.fuel + 0.08 * intuition_strength),
            0.0,
            1.25,
        )
        self.state.memory = min(2.0, intuition_strength)
        self.state.entropy = _clamp(self.state.entropy * 0.55, 0.0, 2.0)

        # A new cycle is not a copy. It starts through RÓŻNICA with retained intuition.
        self.state.vertical_alignment = 0.5
        self.state.balance = 0.5
        self.state.tension = 0.25
        self.state.regulation = 0.5
        self.state.rhythm_alignment = 0.5
        self.state.crystallization = 0.0
        self.state.last_quality = 0.5
        self.state.previous_w = 0.5
        self.state.success_streak = 0
        self.state.failure_streak = 0
        self.state.low_balance_streak = 0
        self.state.stagnation_streak = 0
        self.state.collapse_one_age = 0
        self._set_phase("RÓŻNICA")
        self.phase_history.append("40→RÓŻNICA")

    def _select(self, task: BenchmarkTask) -> list[MemoryEntry]:
        if self.state.fuel < self.memory_recall_fuel:
            return []
        if self.state.phase in {"ROZPAD_I", "STAGNACJA", "PĘKNIĘCIE", "ROZPAD_II"}:
            return []

        task_words = set(_keywords(task.prompt + " " + task.entry_point))
        scored: list[tuple[int, float, float, int, MemoryEntry]] = []
        for entry in self.intuitive_memory:
            words = set(entry.keywords)
            overlap = len(task_words & words)
            union = len(task_words | words) or 1
            jaccard = overlap / union
            if overlap < self.min_keyword_overlap or jaccard < self.min_jaccard:
                continue
            scored.append((overlap, jaccard, entry.confidence, entry.cycle_index, entry))
        scored.sort(reverse=True, key=lambda item: item[:4])
        return [item[-1] for item in scored[: self.max_prompt_memory_entries]]

    def system_prompt(self, task: BenchmarkTask) -> str:
        self._cross_threshold_40()
        selected = self._select(task)
        if not selected:
            return BASE_SYSTEM
        memory = "\n".join(f"- {entry.lesson}" for entry in selected)
        return BASE_SYSTEM + "\n\nPrior-cycle intuition:\n" + memory

    def retry_system_prompt(self, task: BenchmarkTask) -> str:
        # Retry uses local test feedback only. Intuition is removed after a miss.
        return BASE_SYSTEM

    def _update_metrics(self, quality: float, attempts: int, max_attempts: int) -> None:
        state = self.state
        retry_ratio = (attempts - 1) / max(1, max_attempts - 1)
        stress = _clamp(retry_ratio * 0.55 + (0.65 if quality == 0.0 else 0.0))

        state.vertical_alignment = _clamp(
            0.65 * state.vertical_alignment + 0.35 * quality
        )
        rhythm_instant = _clamp(
            0.75 * quality
            + 0.25 * (1.0 - abs(quality - state.last_quality))
            - 0.30 * stress
        )
        state.rhythm_alignment = _clamp(
            0.65 * state.rhythm_alignment + 0.35 * rhythm_instant
        )
        state.tension = _clamp(
            0.70 * state.tension
            + 0.45 * (1.0 - quality)
            + 0.35 * stress
            - 0.25 * quality
        )
        deviation = 1.0 - state.vertical_alignment
        state.regulation = _clamp(
            state.regulation
            + 0.14 * quality
            - 0.18 * stress
            - 0.08 * deviation
        )

        provisional_balance = _clamp(
            0.38 * state.vertical_alignment
            + 0.24 * state.rhythm_alignment
            + 0.20 * state.regulation
            + 0.18 * _clamp(state.fuel)
            - 0.15 * state.tension
        )
        fuel_delta = (
            0.18 * quality
            + 0.06 * state.regulation
            - 0.045
            - 0.18 * deviation
            - 0.14 * state.tension
            - 0.12 * stress
        )
        state.fuel = _clamp(state.fuel + fuel_delta, 0.0, 1.25)
        state.balance = _clamp(
            0.38 * state.vertical_alignment
            + 0.24 * state.rhythm_alignment
            + 0.20 * state.regulation
            + 0.18 * _clamp(state.fuel)
            - 0.15 * state.tension
        )

        if quality >= 0.70:
            state.crystallization = _clamp(
                0.65 * state.crystallization + 0.35 * max(state.balance, provisional_balance)
            )
            state.success_streak += 1
            state.failure_streak = 0
        else:
            state.crystallization = _clamp(0.90 * state.crystallization)
            state.failure_streak += 1
            state.success_streak = 0

        if state.balance <= self.first_collapse_balance or state.fuel <= self.first_collapse_fuel:
            state.low_balance_streak += 1
        else:
            state.low_balance_streak = 0

        state.last_quality = quality
        state.previous_w = quality
        state.entropy = _clamp(
            0.75 * state.entropy + 0.35 * (1.0 - quality) + 0.20 * stress,
            0.0,
            2.0,
        )

    def _enter_first_collapse(self) -> None:
        self.state.collapse_one_count += 1
        self.state.collapse_one_age = 0
        self.pending_intuitive.clear()
        self._set_phase("ROZPAD_I")

    def _abandon_incomplete_cycle(self) -> None:
        # No retained code: the organization never reached crystallized form and rhythm.
        self.pending_intuitive.clear()
        self.transient_failures.clear()
        self.working_memory.clear()
        self._set_phase("40")

    def _process_second_collapse(self) -> None:
        self.state.collapse_two_count += 1
        self._set_phase("PĘKNIĘCIE")
        self._set_phase("ROZPAD_II")
        self._set_phase("3")

        # 3 separates residue from chaos; only proven, high-quality observations remain candidates.
        residue = [
            observation
            for observation in self.working_memory
            if observation.passed and observation.quality >= 0.70
        ]

        self._set_phase("6")
        # 6 removes failures, raw code and one-off noise.
        grouped: dict[str, list[WorkingObservation]] = {}
        for observation in residue:
            lesson_lower = observation.lesson.lower()
            if not observation.lesson or "return " in lesson_lower or "traceback" in lesson_lower:
                continue
            grouped.setdefault(observation.lesson, []).append(observation)

        cleaned: list[MemoryEntry] = []
        for lesson, items in grouped.items():
            keywords = sorted(
                set().union(*(set(item.keywords) for item in items))
            )[:48]
            mean_quality = sum(item.quality for item in items) / len(items)
            confidence = _clamp(0.50 + 0.28 * mean_quality + 0.06 * (len(items) - 1))
            cleaned.append(
                MemoryEntry(
                    task_id=items[-1].task_id,
                    keywords=keywords,
                    lesson=lesson,
                    passed=True,
                    cycle_index=self.state.cycle_index,
                    confidence=confidence,
                    evidence_count=len(items),
                )
            )
        cleaned.sort(
            key=lambda entry: (entry.confidence, entry.evidence_count),
            reverse=True,
        )
        self.transient_failures.clear()

        self._set_phase("28")
        # 28 consolidates the good information as a refreshed intuition candidate.
        self.pending_intuitive = cleaned[: self.max_intuitive_entries]
        self.state.spiral_level += sum(
            entry.confidence for entry in self.pending_intuitive
        )

        # 40 is only the threshold. Crossing occurs when the next task arrives.
        self._set_phase("40")

    def _advance_phase(self, quality: float) -> None:
        state = self.state
        phase = state.phase

        if phase == "ROZPAD_I":
            state.collapse_one_age += 1
            if quality >= 0.70:
                # Feeding/regulation during the repair window can restore the same cycle.
                state.fuel = _clamp(state.fuel + 0.22, 0.0, 1.25)
                state.regulation = _clamp(state.regulation + 0.16)
                state.balance = _clamp(state.balance + 0.14)
            if state.fuel >= self.recovery_fuel and state.balance >= self.recovery_balance:
                state.low_balance_streak = 0
                state.collapse_one_age = 0
                self._set_phase("REGULACJA")
            elif state.collapse_one_age >= self.recovery_window:
                self._abandon_incomplete_cycle()
            return

        if phase in PRE_CRYSTAL_PHASES and (
            state.low_balance_streak >= self.first_collapse_persistence
        ):
            self._enter_first_collapse()
            return

        if phase == "RÓŻNICA":
            self._set_phase("NAPIĘCIE")
        elif phase == "NAPIĘCIE":
            if state.balance >= 0.45:
                self._set_phase("REGULACJA")
        elif phase == "REGULACJA":
            if state.regulation >= 0.54 and state.balance >= 0.50:
                self._set_phase("DOPASOWANIE")
        elif phase == "DOPASOWANIE":
            if (
                state.vertical_alignment >= self.vertical_threshold
                and state.balance >= 0.55
                and state.fuel >= self.recovery_fuel
            ):
                self._set_phase("PION")
        elif phase == "PION":
            if (
                state.crystallization >= self.crystallization_threshold
                and state.success_streak >= 2
            ):
                self._set_phase("KRYSTALIZACJA")
        elif phase == "KRYSTALIZACJA":
            if (
                state.rhythm_alignment >= self.rhythm_threshold
                and state.balance >= 0.58
            ):
                self._set_phase("RYTM")
        elif phase == "RYTM":
            mismatch = (
                state.rhythm_alignment < self.stagnation_threshold
                or state.balance < 0.44
            )
            state.stagnation_streak = state.stagnation_streak + 1 if mismatch else 0
            if state.stagnation_streak >= self.stagnation_persistence:
                self._set_phase("STAGNACJA")
        elif phase == "STAGNACJA":
            recovered = (
                quality >= 0.70
                and state.rhythm_alignment >= self.rhythm_threshold
                and state.balance >= 0.52
                and state.fuel >= self.recovery_fuel
            )
            if recovered:
                state.stagnation_streak = 0
                self._set_phase("RYTM")
                return

            state.stagnation_streak += 1
            crack_ready = (
                state.stagnation_streak >= self.crack_persistence
                and (
                    state.balance <= self.crack_threshold
                    or state.fuel <= self.crack_threshold
                    or state.tension >= 0.72
                )
            )
            if crack_ready:
                self._process_second_collapse()

    def observe(
        self,
        task: BenchmarkTask,
        passed: bool,
        completion: str,
        final_error: str,
        *,
        attempts: int = 1,
        max_attempts: int = 3,
    ) -> None:
        quality = 0.0
        if passed:
            quality = max(0.55, 1.0 - 0.225 * (attempts - 1))
            self.state.solved_count += 1
            lesson, keywords = _generalize(task, completion)
            self.working_memory.append(
                WorkingObservation(
                    task_id=task.task_id,
                    keywords=keywords,
                    lesson=lesson,
                    passed=True,
                    status="passed",
                    cycle_index=self.state.cycle_index,
                    quality=quality,
                    phase=self.state.phase,
                )
            )
        else:
            self.transient_failures.append(task.task_id)
            self.working_memory.append(
                WorkingObservation(
                    task_id=task.task_id,
                    keywords=_keywords(task.prompt),
                    lesson="",
                    passed=False,
                    status="failed",
                    cycle_index=self.state.cycle_index,
                    quality=0.0,
                    phase=self.state.phase,
                )
            )

        # Keep bounded working evidence without closing the cycle by count.
        maximum_working = max(8, self.cycle_length * 2)
        if len(self.working_memory) > maximum_working:
            self.working_memory = self.working_memory[-maximum_working:]

        self._update_metrics(quality, attempts, max_attempts)
        self.state.tasks_in_cycle += 1
        self._advance_phase(quality)


@dataclass
class StatelessController:
    agent_id: int

    def system_prompt(self, task: BenchmarkTask) -> str:
        return BASE_SYSTEM

    def retry_system_prompt(self, task: BenchmarkTask) -> str:
        return BASE_SYSTEM

    def observe(
        self,
        task: BenchmarkTask,
        passed: bool,
        completion: str,
        final_error: str,
        *,
        attempts: int = 1,
        max_attempts: int = 3,
    ) -> None:
        return None
