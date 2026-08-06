#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

BRANCH = "agent/rhythm-token-value-v6"


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    env = os.environ.copy()
    package_root = str(cwd / "validation_10x10")
    env["PYTHONPATH"] = package_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(cmd, cwd=cwd, text=True, check=check, env=env)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "validation_10x10/swarm_validation/controller.py").exists():
            return candidate
    raise SystemExit(
        "Run this script from the swarm-os-benchmark repository root "
        "or pass --repo /workspaces/swarm-os-benchmark"
    )


def patch_models(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from dataclasses import asdict, dataclass\n",
        "from dataclasses import asdict, dataclass, field\n",
        "models import field",
    )
    old = '''    rhythm_alignment: float = 0.5
    crystallization: float = 0.0
    last_quality: float = 0.5

    # Alignment with the wider system and the accumulated energetic cost of mismatch.
'''
    new = '''    rhythm_alignment: float = 0.5
    crystallization: float = 0.0
    last_quality: float = 0.5

    # RYTM is the stable value of the whole token flow, not raw quality alone.
    # token_value is quality created per weighted token cost, compressed to [0, 1].
    # The equilibrium is learned slowly from aligned successful work; trend and
    # volatility reveal whether the system is returning to balance or leaving it.
    token_value: float = 0.0
    token_value_equilibrium: float = 0.5
    token_value_trend: float = 0.0
    token_value_volatility: float = 0.0
    token_value_history: list[float] = field(default_factory=list)
    rhythm_direction: str = "stable"

    # Alignment with the wider system and the accumulated energetic cost of mismatch.
'''
    text = replace_once(text, old, new, "models token rhythm state")
    path.write_text(text, encoding="utf-8")


def patch_protocol(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = '''    max_intuitive_entries: int = 4
    max_prompt_memory_entries: int = 1
    max_working_prompt_entries: int = 1
    working_memory_min_quality: float = 0.70
    memory_min_keyword_overlap: int = 2
    memory_min_jaccard: float = 0.08
    memory_recall_fuel: float = 0.42

    vertical_threshold: float = 0.62
'''
    new = '''    max_intuitive_entries: int = 4
    max_prompt_memory_entries: int = 1
    # Retained only for backward-compatible configs. Working evidence is never
    # exposed to the model before 3 -> 6 -> 28 -> 40 purification.
    max_working_prompt_entries: int = 0
    working_memory_min_quality: float = 0.70
    memory_min_keyword_overlap: int = 2
    memory_min_jaccard: float = 0.08
    # Retained for old manifests. Prior-cycle intuition is part of the updated
    # system and is not switched off by a local fuel threshold.
    memory_recall_fuel: float = 0.42

    # RYTM: stable value of the complete token flow.
    rhythm_window: int = 6
    token_reference_weighted_tokens: float = 1000.0
    output_token_weight: float = 5.0
    token_equilibrium_alpha: float = 0.08

    vertical_threshold: float = 0.62
'''
    text = replace_once(text, old, new, "protocol rhythm fields")
    old = '''            "memory_recall_fuel": self.memory_recall_fuel,
            "working_memory_min_quality": self.working_memory_min_quality,
            "vertical_threshold": self.vertical_threshold,
'''
    new = '''            "memory_recall_fuel": self.memory_recall_fuel,
            "working_memory_min_quality": self.working_memory_min_quality,
            "token_equilibrium_alpha": self.token_equilibrium_alpha,
            "vertical_threshold": self.vertical_threshold,
'''
    text = replace_once(text, old, new, "protocol bounded alpha")
    old = '''        if self.crack_load <= 0.0:
            raise ValueError("crack_load must be positive")
        for name, value in {
'''
    new = '''        if self.crack_load <= 0.0:
            raise ValueError("crack_load must be positive")
        if self.rhythm_window < 3:
            raise ValueError("rhythm_window must be at least 3")
        if self.token_reference_weighted_tokens <= 0.0:
            raise ValueError("token_reference_weighted_tokens must be positive")
        if self.output_token_weight <= 0.0:
            raise ValueError("output_token_weight must be positive")
        for name, value in {
'''
    text = replace_once(text, old, new, "protocol rhythm validation")
    path.write_text(text, encoding="utf-8")


def patch_controller(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import ast\nimport re\n",
        "import ast\nimport math\nimport re\nfrom statistics import fmean, pstdev\n",
        "controller imports",
    )

    old = '''def _project_convention(task: BenchmarkTask) -> str:
    match = re.search(r"^#?\\s*Project convention:\\s*(.+)$", task.prompt, re.MULTILINE)
    return " ".join(match.group(1).split())[:120] if match else ""


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
    convention = _project_convention(task)
    lesson = f"{domain}: {technique}; boundary guards."
    if convention:
        lesson += f" Project convention: {convention}"
    return lesson[:220], keys
'''
    new = '''def _semantic_difference(prompt: str, completion: str, entry_point: str) -> str:
    """Extract the difference that survived the task, not a copy of its input."""
    lowered = " ".join(prompt.lower().split())
    rules: list[str] = []
    candidates = [
        (("original input", "original index"), "preserve original positions before filtering"),
        (("preserve input order", "stable"), "preserve first-seen order"),
        (("preserve duplicates",), "do not deduplicate repeated valid values"),
        (("stable unique", "first occurrence"), "deduplicate only after normalization and keep the first occurrence"),
        (("canonical target", "normalize target"), "normalize both the target and candidate values before comparison"),
        (("invalid", "discard invalid"), "separate invalid evidence before aggregation"),
        (("first", "last"), "handle empty valid results without indexing"),
        (("counts", "counting", "frequency"), "aggregate only canonical valid keys"),
        (("partition",), "return canonical valid values but retain original invalid values"),
    ]
    for needles, rule in candidates:
        if any(needle in lowered for needle in needles) and rule not in rules:
            rules.append(rule)
    technique = _features(completion, entry_point)[0]
    if not rules:
        rules.append(f"use {technique} with explicit boundary handling")
    elif technique not in {"a direct minimal transformation", "direct construction"}:
        rules.append(f"implement with {technique}")
    return "; ".join(rules[:3])


def _generalize(task: BenchmarkTask, completion: str) -> tuple[str, list[str]]:
    # The intuition candidate stores only the newly established difference.
    # The project convention is already present in every task and must not be
    # duplicated as pseudo-memory.
    lesson = "Confirmed difference: " + _semantic_difference(
        task.prompt, completion, task.entry_point
    )
    return lesson[:220], _keywords(task.prompt)
'''
    text = replace_once(text, old, new, "controller generalization")

    old = '''    max_prompt_memory_entries: int = 1
    max_working_prompt_entries: int = 1
    working_memory_min_quality: float = 0.70
    min_keyword_overlap: int = 2
    min_jaccard: float = 0.08
    memory_recall_fuel: float = 0.42

    vertical_threshold: float = 0.62
'''
    new = '''    max_prompt_memory_entries: int = 1
    # Backward-compatible field only. Working memory remains internal evidence.
    max_working_prompt_entries: int = 0
    working_memory_min_quality: float = 0.70
    min_keyword_overlap: int = 2
    min_jaccard: float = 0.08
    memory_recall_fuel: float = 0.42

    rhythm_window: int = 6
    token_reference_weighted_tokens: float = 1000.0
    output_token_weight: float = 5.0
    token_equilibrium_alpha: float = 0.08

    vertical_threshold: float = 0.62
'''
    text = replace_once(text, old, new, "controller rhythm fields")

    old = '''        self.state.rhythm_alignment = 0.5
        self.state.crystallization = 0.0
        self.state.last_quality = 0.5
        self.state.whole_alignment = 0.5
'''
    new = '''        self.state.rhythm_alignment = 0.5
        self.state.crystallization = 0.0
        self.state.last_quality = 0.5
        # The learned proper token-value level survives as part of the updated
        # system, while short-term oscillation is cleared for the new cycle.
        self.state.token_value = self.state.token_value_equilibrium
        self.state.token_value_trend = 0.0
        self.state.token_value_volatility = 0.0
        self.state.token_value_history.clear()
        self.state.rhythm_direction = "new_cycle"
        self.state.whole_alignment = 0.5
'''
    text = replace_once(text, old, new, "controller cycle rhythm reset")

    old = '''    def _select(self, task: BenchmarkTask) -> list[MemoryEntry]:
        if self.state.fuel < self.memory_recall_fuel:
            return []
        if self.state.phase in {"ROZPAD_I", "STAGNACJA", "PĘKNIĘCIE", "ROZPAD_II"}:
            return []

        task_words = set(_keywords(task.prompt + " " + task.entry_point))
'''
    new = '''    def _select(self, task: BenchmarkTask) -> list[MemoryEntry]:
        # Intuition is the retained update of an earlier completed cycle. It is
        # not an optional note gated by current fuel and it cannot come from the
        # cycle that is still being processed.
        task_words = set(_keywords(task.prompt + " " + task.entry_point))
'''
    text = replace_once(text, old, new, "controller intuition select gate")
    old = '''        for entry in self.intuitive_memory:
            words = set(entry.keywords)
'''
    new = '''        for entry in self.intuitive_memory:
            if entry.cycle_index >= self.state.cycle_index:
                continue
            words = set(entry.keywords)
'''
    text = replace_once(text, old, new, "controller prior cycle guard")

    start = text.index("    def _select_working(self, task: BenchmarkTask)")
    end = text.index("    def retry_system_prompt", start)
    replacement = '''    def _prompt_with_intuition(self, task: BenchmarkTask) -> str:
        intuitive = self._select(task)
        if not intuitive:
            return BASE_SYSTEM
        return BASE_SYSTEM + "\\n\\nPrior-cycle intuition:\\n" + "\\n".join(
            f"- {entry.lesson}" for entry in intuitive
        )

    def system_prompt(self, task: BenchmarkTask) -> str:
        self._cross_threshold_40()
        return self._prompt_with_intuition(task)

'''
    text = text[:start] + replacement + text[end:]
    old = '''    def retry_system_prompt(self, task: BenchmarkTask) -> str:
        # Retry uses local test feedback only. Intuition is removed after a miss.
        return BASE_SYSTEM
'''
    new = '''    def retry_system_prompt(self, task: BenchmarkTask) -> str:
        # Local test feedback changes the attempted solution, not the system's
        # already consolidated prior-cycle intuition.
        return self._prompt_with_intuition(task)
'''
    text = replace_once(text, old, new, "controller retry intuition")

    marker = '''    def _whole_alignment(self) -> float:
'''
    rhythm_methods = '''    def _instant_token_value(
        self,
        quality: float,
        input_tokens: int,
        output_tokens: int,
        cache_creation_input_tokens: int,
        cache_read_input_tokens: int,
    ) -> float:
        weighted_tokens = (
            max(0, input_tokens)
            + self.output_token_weight * max(0, output_tokens)
            + max(0, cache_creation_input_tokens)
            + max(0, cache_read_input_tokens)
        )
        cost_units = max(
            weighted_tokens / self.token_reference_weighted_tokens,
            1e-9,
        )
        raw_value = max(0.0, quality) / cost_units
        return _clamp(raw_value / (1.0 + raw_value))

    @staticmethod
    def _window_slope(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        x_mean = (len(values) - 1) / 2.0
        y_mean = fmean(values)
        denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
        if denominator <= 0.0:
            return 0.0
        return sum(
            (index - x_mean) * (value - y_mean)
            for index, value in enumerate(values)
        ) / denominator

    def _update_token_rhythm(
        self,
        quality: float,
        input_tokens: int,
        output_tokens: int,
        cache_creation_input_tokens: int,
        cache_read_input_tokens: int,
    ) -> None:
        state = self.state
        value = self._instant_token_value(
            quality,
            input_tokens,
            output_tokens,
            cache_creation_input_tokens,
            cache_read_input_tokens,
        )
        state.token_value = value
        history = list(state.token_value_history)
        history.append(value)
        history = history[-self.rhythm_window :]
        state.token_value_history = history

        equilibrium = max(state.token_value_equilibrium, 1e-6)
        mean_value = fmean(history)
        volatility = 0.0
        if len(history) >= 2:
            volatility = _clamp(pstdev(history) / max(mean_value, 0.05))
        slope = self._window_slope(history)
        normalized_trend = slope / max(state.token_value_equilibrium, 0.05)
        state.token_value_volatility = volatility
        state.token_value_trend = normalized_trend

        level_fit = math.exp(
            -2.0 * abs(math.log((mean_value + 1e-6) / (equilibrium + 1e-6)))
        )
        stability = 1.0 - volatility
        direction_fit = math.exp(-3.0 * abs(normalized_trend))
        rhythm_instant = _clamp(
            max(0.0, level_fit * stability * direction_fit) ** (1.0 / 3.0)
        )
        state.rhythm_alignment = _clamp(
            0.65 * state.rhythm_alignment + 0.35 * rhythm_instant
        )

        # The proper level can refine itself only from already aligned, stable
        # work. A persistent wasteful regime is not allowed to redefine itself
        # as the new equilibrium merely because it is repeatable.
        if (
            quality >= 0.70
            and state.vertical_alignment >= 0.55
            and len(history) >= 3
            and volatility <= 0.12
            and abs(normalized_trend) <= 0.05
            and level_fit >= 0.65
            and state.phase not in {"STAGNACJA", "PĘKNIĘCIE", "ROZPAD_II"}
        ):
            alpha = self.token_equilibrium_alpha
            state.token_value_equilibrium = (
                (1.0 - alpha) * state.token_value_equilibrium
                + alpha * mean_value
            )

        if volatility >= 0.30:
            state.rhythm_direction = "oscillating"
        elif normalized_trend <= -0.05:
            state.rhythm_direction = "falling"
        elif normalized_trend >= 0.05:
            state.rhythm_direction = "rising"
        elif mean_value < 0.85 * equilibrium:
            state.rhythm_direction = "below_equilibrium"
        elif mean_value > 1.15 * equilibrium:
            state.rhythm_direction = "above_equilibrium"
        else:
            state.rhythm_direction = "stable"

'''
    text = replace_once(text, marker, rhythm_methods + marker, "controller rhythm methods")

    old = '''    def _update_metrics(self, quality: float, attempts: int, max_attempts: int) -> None:
        state = self.state
'''
    new = '''    def _update_metrics(
        self,
        quality: float,
        attempts: int,
        max_attempts: int,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ) -> None:
        state = self.state
'''
    text = replace_once(text, old, new, "controller update signature")

    old = '''        state.vertical_alignment = _clamp(
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
'''
    new = '''        state.vertical_alignment = _clamp(
            0.65 * state.vertical_alignment + 0.35 * quality
        )
        if (
            input_tokens
            + output_tokens
            + cache_creation_input_tokens
            + cache_read_input_tokens
            <= 0
        ):
            # Direct unit/simulation observations have no provider usage record.
            # Treat them as one reference-cost action, never as free infinite value.
            input_tokens = int(self.token_reference_weighted_tokens)
        self._update_token_rhythm(
            quality,
            input_tokens,
            output_tokens,
            cache_creation_input_tokens,
            cache_read_input_tokens,
        )
        state.tension = _clamp(
'''
    text = replace_once(text, old, new, "controller replace old rhythm")

    old = '''        energy_gain = 0.18 * quality + 0.06 * state.regulation
        energy_cost = (
            0.045
            + 0.18 * deviation
            + 0.14 * state.tension
            + 0.12 * stress
        )
'''
    new = '''        rhythm_deviation = 1.0 - state.rhythm_alignment
        energy_gain = (
            0.12 * quality + 0.06 * state.regulation
        ) * state.rhythm_alignment
        energy_cost = (
            0.040
            + 0.16 * deviation
            + 0.22 * rhythm_deviation
            + 0.12 * state.tension
            + 0.10 * stress
        )
'''
    text = replace_once(text, old, new, "controller energy rhythm")

    old = '''        grouped: dict[str, list[WorkingObservation]] = {}
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
'''
    new = '''        grouped: dict[str, list[WorkingObservation]] = {}
        for observation in residue:
            lesson_lower = observation.lesson.lower()
            if not observation.lesson or "return " in lesson_lower or "traceback" in lesson_lower:
                continue
            # Related tasks form one coherent project residue. Independent tasks
            # must repeat the same difference before it can survive purification.
            group_key = _project_key(observation.task_id) or observation.lesson
            grouped.setdefault(group_key, []).append(observation)

        cleaned: list[MemoryEntry] = []
        for _, items in grouped.items():
            if _project_key(items[0].task_id) is None and len(items) < 2:
                continue
            keywords = sorted(
                set().union(*(set(item.keywords) for item in items))
            )[:48]
            mean_quality = sum(item.quality for item in items) / len(items)
            clauses: list[str] = []
            for item in items:
                content = item.lesson.removeprefix("Confirmed difference: ")
                for clause in content.split("; "):
                    clause = clause.strip()
                    if clause and clause not in clauses:
                        clauses.append(clause)
            lesson = "Cycle update: " + "; ".join(clauses[:5])
            confidence = _clamp(
                0.50 + 0.28 * mean_quality + 0.04 * min(len(items) - 1, 4)
            )
            cleaned.append(
                MemoryEntry(
                    task_id=items[-1].task_id,
                    keywords=keywords,
                    lesson=lesson[:220],
                    passed=True,
                    cycle_index=self.state.cycle_index,
                    confidence=confidence,
                    evidence_count=len(items),
                )
            )
'''
    text = replace_once(text, old, new, "controller purification consolidation")

    old = '''        attempts: int = 1,
        max_attempts: int = 3,
    ) -> None:
'''
    new = '''        attempts: int = 1,
        max_attempts: int = 3,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ) -> None:
'''
    # Appears twice (Swarm and Stateless). Replace both deliberately.
    if text.count(old) != 2:
        raise RuntimeError(f"controller observe signatures: expected 2 matches, found {text.count(old)}")
    text = text.replace(old, new)

    old = '''        self._update_metrics(quality, attempts, max_attempts)
        self.state.tasks_in_cycle += 1
'''
    new = '''        self._update_metrics(
            quality,
            attempts,
            max_attempts,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
        )
        self.state.tasks_in_cycle += 1
'''
    text = replace_once(text, old, new, "controller observe token metrics")
    path.write_text(text, encoding="utf-8")


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = '''        memory_recall_fuel=config.memory_recall_fuel,
        vertical_threshold=config.vertical_threshold,
'''
    new = '''        memory_recall_fuel=config.memory_recall_fuel,
        rhythm_window=config.rhythm_window,
        token_reference_weighted_tokens=config.token_reference_weighted_tokens,
        output_token_weight=config.output_token_weight,
        token_equilibrium_alpha=config.token_equilibrium_alpha,
        vertical_threshold=config.vertical_threshold,
'''
    text = replace_once(text, old, new, "runner rhythm config")
    old = '''            "project_sequence_memory": "passed same-project working evidence only; retries never receive memory",
'''
    new = '''            "project_sequence_memory": "working evidence remains internal; only intuition purified through 3 -> 6 -> 28 -> 40 enters the next cycle and remains present on retries",
            "rhythm_measure": "stable quality created per weighted total token flow; reports equilibrium, volatility and signed trend",
'''
    text = replace_once(text, old, new, "runner manifest")
    old = '''            attempts=len(records),
            max_attempts=self.config.max_attempts,
        )
'''
    new = '''            attempts=len(records),
            max_attempts=self.config.max_attempts,
            input_tokens=total_input,
            output_tokens=total_output,
            cache_creation_input_tokens=total_cache_create,
            cache_read_input_tokens=total_cache_read,
        )
'''
    text = replace_once(text, old, new, "runner observe usage")
    path.write_text(text, encoding="utf-8")


def patch_existing_tests(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from swarm_validation.models import TaskOutcome, WorkingObservation\n",
        "from swarm_validation.models import MemoryEntry, TaskOutcome, WorkingObservation\n",
        "test imports",
    )
    start = text.index("class WorkingMemoryTests")
    end = text.index("class BusinessMetricsTests", start)
    replacement = '''class CycleMemoryBoundaryTests(unittest.TestCase):
    def task(self, step: int = 9) -> BenchmarkTask:
        return BenchmarkTask(
            task_id=f"orders::{step:02d}",
            prompt=(
                "# Project: orders\\n"
                "# Project convention: canonical order status mapping\\n"
                f"def orders_step_{step}(values):\\n"
            ),
            test="def check(candidate):\\n    assert True\\n",
            entry_point=f"orders_step_{step}",
            metadata={"project_id": "orders", "step_index": step},
        )

    def observation(self, step: int, lesson: str) -> WorkingObservation:
        return WorkingObservation(
            task_id=f"orders::{step:02d}",
            keywords=["orders", "canonical", "status", "mapping", "values"],
            lesson=lesson,
            passed=True,
            status="passed",
            cycle_index=0,
            quality=1.0,
            phase="RYTM",
        )

    def test_current_cycle_working_evidence_is_never_prompted(self) -> None:
        controller = SwarmController(agent_id=0)
        controller.working_memory = [
            self.observation(1, "CURRENT CYCLE MUST NOT APPEAR")
        ]
        prompt = controller.system_prompt(self.task(2))
        self.assertEqual(prompt, BASE_SYSTEM)
        self.assertNotIn("Current-cycle working guidance", prompt)
        self.assertNotIn("CURRENT CYCLE", prompt)

    def test_intuition_appears_only_after_3_6_28_40_crossing(self) -> None:
        controller = SwarmController(agent_id=0)
        controller.state.phase = "STAGNACJA"
        controller.state.state = "STAGNACJA"
        controller.working_memory = [
            self.observation(1, "Confirmed difference: preserve first-seen order"),
            self.observation(2, "Confirmed difference: aggregate only canonical valid keys"),
        ]
        controller._process_second_collapse()
        self.assertEqual(controller.state.phase, "40")
        self.assertEqual(controller.intuitive_memory, [])
        self.assertTrue(controller.pending_intuitive)

        prompt = controller.system_prompt(self.task(9))
        self.assertEqual(controller.state.phase, "RÓŻNICA")
        self.assertEqual(controller.state.cycle_index, 1)
        self.assertIn("Prior-cycle intuition", prompt)
        self.assertIn("Cycle update", prompt)
        self.assertNotIn("Current-cycle working guidance", prompt)

    def test_retry_retains_prior_cycle_intuition(self) -> None:
        controller = SwarmController(agent_id=0)
        controller.state.cycle_index = 1
        controller.intuitive_memory = [
            MemoryEntry(
                task_id="orders::08",
                keywords=["orders", "canonical", "status", "mapping", "values"],
                lesson="Cycle update: normalize both sides before comparison",
                cycle_index=0,
                confidence=0.9,
                evidence_count=3,
            )
        ]
        first = controller.system_prompt(self.task(9))
        retry = controller.retry_system_prompt(self.task(9))
        self.assertIn("Prior-cycle intuition", first)
        self.assertEqual(retry, first)

    def test_humaneval_style_task_does_not_use_unrelated_intuition(self) -> None:
        controller = SwarmController(agent_id=0)
        controller.state.cycle_index = 1
        controller.intuitive_memory = [
            MemoryEntry(
                task_id="orders::08",
                keywords=["orders", "canonical", "status", "mapping"],
                lesson="MUST NOT APPEAR",
                cycle_index=0,
            )
        ]
        task = BenchmarkTask(
            task_id="HumanEval/1",
            prompt="def solve(numbers):\\n",
            test="def check(candidate):\\n    assert True\\n",
            entry_point="solve",
        )
        self.assertNotIn("MUST NOT APPEAR", controller.system_prompt(task))


'''
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_memory_tests(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = '''    def test_low_fuel_blocks_intuitive_recall(self):
        controller = SwarmController(0)
        next_index = drive_second_collapse(controller)
        controller.system_prompt(task(next_index))
        self.assertTrue(controller.intuitive_memory)
        controller.state.fuel = controller.memory_recall_fuel - 0.01
        self.assertEqual(controller.system_prompt(task(next_index + 1)), BASE_SYSTEM)
'''
    new = '''    def test_low_fuel_does_not_erase_prior_cycle_intuition(self):
        controller = SwarmController(0)
        next_index = drive_second_collapse(controller)
        controller.system_prompt(task(next_index))
        self.assertTrue(controller.intuitive_memory)
        controller.state.fuel = controller.memory_recall_fuel - 0.01
        self.assertIn("Prior-cycle intuition", controller.system_prompt(task(next_index + 1)))
'''
    text = replace_once(text, old, new, "memory test low fuel intuition")
    old = '''    def test_success_increases_fuel_failure_decreases_fuel(self):
        success = SwarmController(0)
        before = success.state.fuel
        success.observe(task(1), True, "    return 1\n", "", attempts=1)
        self.assertGreater(success.state.fuel, before)

        failure = SwarmController(0)
        before = failure.state.fuel
        failure.observe(task(1), False, "", "x", attempts=3)
        self.assertLess(failure.state.fuel, before)
'''
    new = '''    def test_approaching_vertical_uses_bounded_fuel_and_failure_drains_more(self):
        success = SwarmController(0)
        success_before = success.state.fuel
        success.observe(task(1), True, "    return 1\n", "", attempts=1)

        failure = SwarmController(0)
        failure_before = failure.state.fuel
        failure.observe(task(1), False, "", "x", attempts=3)

        self.assertLessEqual(success.state.fuel, success_before)
        self.assertLess(failure.state.fuel, failure_before)
        self.assertGreater(success.state.fuel, failure.state.fuel)
'''
    text = replace_once(text, old, new, "memory test fuel semantics")
    path.write_text(text, encoding="utf-8")


RHYTHM_TEST = r'''from __future__ import annotations

import unittest

from swarm_validation.controller import SwarmController


class TokenValueRhythmTests(unittest.TestCase):
    def update(self, controller: SwarmController, input_tokens: int, output_tokens: int, quality: float = 1.0) -> None:
        controller._update_metrics(
            quality,
            1,
            3,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def test_stable_proper_flow_converges_to_high_rhythm(self) -> None:
        controller = SwarmController(agent_id=0)
        for _ in range(10):
            self.update(controller, 400, 80)
        self.assertGreater(controller.state.rhythm_alignment, 0.80)
        self.assertLess(controller.state.token_value_volatility, 0.05)
        self.assertAlmostEqual(controller.state.token_value_trend, 0.0, delta=0.02)
        self.assertEqual(controller.state.rhythm_direction, "stable")

    def test_rising_cost_with_same_quality_is_detected_as_falling_value(self) -> None:
        controller = SwarmController(agent_id=0)
        for _ in range(6):
            self.update(controller, 400, 80)
        stable_rhythm = controller.state.rhythm_alignment
        for input_tokens, output_tokens in [(700, 120), (1000, 180), (1500, 250), (2200, 350)]:
            self.update(controller, input_tokens, output_tokens)
        self.assertLess(controller.state.rhythm_alignment, stable_rhythm)
        self.assertLess(controller.state.token_value_trend, 0.0)
        self.assertIn(controller.state.rhythm_direction, {"falling", "oscillating"})

    def test_oscillation_is_not_mistaken_for_equilibrium(self) -> None:
        stable = SwarmController(agent_id=0)
        oscillating = SwarmController(agent_id=1)
        for _ in range(10):
            self.update(stable, 400, 80)
        for input_tokens, output_tokens in [(100, 20), (2400, 420)] * 5:
            self.update(oscillating, input_tokens, output_tokens)
        self.assertGreater(
            oscillating.state.token_value_volatility,
            stable.state.token_value_volatility,
        )
        self.assertLess(
            oscillating.state.rhythm_alignment,
            stable.state.rhythm_alignment,
        )
        self.assertEqual(oscillating.state.rhythm_direction, "oscillating")

    def test_token_value_affects_fuel_even_when_quality_is_equal(self) -> None:
        stable = SwarmController(agent_id=0)
        wasteful = SwarmController(agent_id=1)
        for _ in range(8):
            self.update(stable, 400, 80)
            self.update(wasteful, 2200, 400)
        self.assertGreater(stable.state.rhythm_alignment, wasteful.state.rhythm_alignment)
        self.assertGreater(stable.state.fuel, wasteful.state.fuel)


if __name__ == "__main__":
    unittest.main()
'''


GENERATOR = r"""#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_IDS = [
    "claims", "support", "devices", "contracts", "vendors", "catalog", "warehouse", "routing", "incidents", "alerts",
    "users", "teams", "regions", "assets", "payments", "refunds", "tickets", "campaigns", "documents", "policies",
    "services", "batches", "queues", "approvals", "subscriptions", "entitlements", "exports", "imports", "sessions", "notifications",
]

PREFIXES = ["CLM", "SUP", "DEV", "CTR", "VND", "CAT", "WH", "RTE", "INC", "ALT", "USR", "TEAM", "REG", "AST", "PAY", "RFD", "TKT", "CMP", "DOC", "POL", "SVC", "BAT", "QUE", "APR", "SUB", "ENT", "EXP", "IMP", "SES", "NTF"]


def project(index: int) -> dict:
    pid = PROJECT_IDS[index]
    prefix = PREFIXES[index]
    family = index % 6

    if family == 0:
        min_len = 3 + index % 3
        separator = "_" if index % 2 == 0 else "-"
        convention = (
            f"Accept strings only; strip and uppercase; replace spaces, underscores and hyphens with '{separator}'; "
            f"collapse repeated separators; prefix all-digit values with {prefix}{separator}; "
            f"keep only values whose compact alphanumeric payload has at least {min_len} characters."
        )
        helper = f'''def norm(value):
    if not isinstance(value, str):
        return ""
    sep = {separator!r}
    key = value.strip().upper().replace(" ", sep).replace("_", sep).replace("-", sep)
    while sep + sep in key:
        key = key.replace(sep + sep, sep)
    key = key.strip(sep)
    if key.isdigit():
        key = {prefix!r} + sep + key
    payload = "".join(ch for ch in key if ch.isalnum())
    return key if len(payload) >= {min_len} and all(ch.isalnum() or ch == sep for ch in key) else ""'''
        samples = [f" {prefix.lower()} 12 ", "77", f"{prefix}-A9", "x", "bad!code", None, f"{prefix}__12", f"{prefix} 12"]
        target = f"{prefix}{separator}12"

    elif family == 1:
        labels = [
            ("NEW", ["n", "new", "created"]),
            ("ACTIVE", ["a", "active", "open"]),
            ("CLOSED", ["c", "closed", "done"]),
        ]
        aliases = {alias: canonical for canonical, names in labels for alias in names}
        convention = "Accept strings only; strip and casefold; map n/new/created to NEW, a/active/open to ACTIVE, and c/closed/done to CLOSED; reject every other value."
        helper = f'''def norm(value):
    if not isinstance(value, str):
        return ""
    aliases = {aliases!r}
    return aliases.get(value.strip().casefold(), "")'''
        samples = [" new ", "A", "done", "unknown", None, "created", "OPEN", "new"]
        target = "NEW"

    elif family == 2:
        separator = "-" if index % 2 == 0 else "_"
        marker = "#" if index % 3 == 0 else "@"
        convention = (
            f"Accept strings only; strip, remove leading '{marker}' markers, casefold, convert whitespace/underscores/hyphens to '{separator}', "
            "collapse repeated separators, and keep only nonempty letters, digits and separators."
        )
        helper = f'''def norm(value):
    if not isinstance(value, str):
        return ""
    sep = {separator!r}
    key = value.strip().lstrip({marker!r}).casefold()
    key = key.replace(" ", sep).replace("_", sep).replace("-", sep)
    while sep + sep in key:
        key = key.replace(sep + sep, sep)
    key = key.strip(sep)
    return key if key and all(ch.isalnum() or ch == sep for ch in key) else ""'''
        samples = [f" {marker}Alpha Beta ", "ALPHA__BETA", "bad!slug", "", None, "alpha-beta", f"{marker}{marker}Gamma", "alpha beta"]
        target = f"alpha{separator}beta"

    elif family == 3:
        convention = "Accept strings only; strip and casefold; require exactly one @, no whitespace, nonempty local/domain parts, and at least one dot in the domain; return the canonical email or empty string."
        helper = '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().casefold()
    if any(ch.isspace() for ch in key) or key.count("@") != 1:
        return ""
    local, domain = key.split("@")
    return key if local and domain and "." in domain and not domain.startswith(".") and not domain.endswith(".") else ""'''
        samples = [" User@Example.COM ", "user@example.com", "bad address@example.com", "x@host", None, "@example.com", "other@test.org", "USER@example.com"]
        target = "user@example.com"

    elif family == 4:
        width = 4 + index % 3
        convention = (
            f"Accept strings only; strip, remove spaces and hyphens, uppercase, accept either digits or {prefix} followed by digits, "
            f"left-pad the numeric part to width {width}, reject longer/non-numeric payloads, and return {prefix} plus the padded digits."
        )
        helper = f'''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().replace(" ", "").replace("-", "").upper()
    digits = key[len({prefix!r}):] if key.startswith({prefix!r}) else key
    if not digits.isdigit() or len(digits) > {width}:
        return ""
    return {prefix!r} + digits.zfill({width})'''
        samples = [" 12 ", f"{prefix}-12", "00012", "abc", None, "7", f"{prefix}7", "12"]
        target = f"{prefix}" + "12".zfill(width)

    else:
        convention = "Accept strings only; strip and casefold; normalize dots, backslashes and repeated slashes to '/', remove empty segments, reject '.' or '..' segments and non-alphanumeric/underscore segment characters."
        helper = '''def norm(value):
    if not isinstance(value, str):
        return ""
    raw = value.strip().casefold().replace("\\\\", "/")
    if any(part in {".", ".."} for part in raw.split("/")):
        return ""
    key = raw.replace(".", "/")
    while "//" in key:
        key = key.replace("//", "/")
    parts = [part for part in key.strip("/").split("/") if part]
    if not parts or any(not all(ch.isalnum() or ch == "_" for ch in part) for part in parts):
        return ""
    return "/".join(parts)'''
        samples = [" Root\\Child ", "root.child", "root//child", "../secret", None, "root/child", "bad!/path", "ROOT/CHILD"]
        target = "root/child"

    return {"id": pid, "label": f"{pid.title()} workflow", "convention": convention, "helper": helper, "samples": samples, "target": target}


def prompt(p: dict, step: int, signature: str, instruction: str) -> str:
    return (
        f"# Project: {p['label']}\n"
        f"# Step: {step} of 16\n"
        f"# Project convention: {p['convention']}\n\n"
        f"def {signature}:\n"
        f"    \"\"\"{instruction}\"\"\"\n"
    )


def tests(helper: str, assertions: list[str]) -> str:
    return helper + "\n\ndef check(candidate):\n" + "\n".join("    " + line for line in assertions) + "\n"


def records_for(p: dict) -> list[dict]:
    pid = p["id"]
    values = repr(p["samples"])
    target = repr(p["target"])
    right = repr(list(reversed(p["samples"][:5])) + p["samples"][:2])
    specs = [
        (f"{pid}_normalize(value)", "Return the canonical value, or an empty string for an invalid value.", [f"assert candidate({p['samples'][0]!r}) == norm({p['samples'][0]!r})", "assert candidate(None) == ''"]),
        (f"{pid}_valid(values)", "Normalize valid values in input order and preserve duplicates.", [f"values = {values}", "assert candidate(values) == [norm(v) for v in values if norm(v)]"]),
        (f"{pid}_unique(values)", "Return stable unique canonical values, keeping the first occurrence.", [f"values = {values}", "expected = []", "for v in values:", "    k = norm(v)", "    if k and k not in expected:", "        expected.append(k)", "assert candidate(values) == expected"]),
        (f"{pid}_counts(values)", "Count canonical valid values; invalid values do not appear.", [f"values = {values}", "expected = {}", "for v in values:", "    k = norm(v)", "    if k:", "        expected[k] = expected.get(k, 0) + 1", "assert candidate(values) == expected"]),
        (f"{pid}_first_index(values, target)", "Return the original index of the first canonical target match, or -1.", [f"values = {values}", f"assert candidate(values, {target}) == next((i for i, v in enumerate(values) if norm(v) and norm(v) == norm({target})), -1)", "assert candidate(values, 'invalid!') == -1"]),
        (f"{pid}_common(left, right)", "Return stable unique canonical values from left that also occur in right.", [f"left = {values}", f"right = {right}", "right_set = {norm(v) for v in right if norm(v)}", "expected = []", "for v in left:", "    k = norm(v)", "    if k and k in right_set and k not in expected:", "        expected.append(k)", "assert candidate(left, right) == expected"]),
        (f"{pid}_partition(values)", "Return (valid, invalid): canonical valid values and original invalid values.", [f"values = {values}", "assert candidate(values) == ([norm(v) for v in values if norm(v)], [v for v in values if not norm(v)])"]),
        (f"{pid}_summary(values)", "Return exactly valid_count, unique_count, first and last after normalization.", [f"values = {values}", "valid = [norm(v) for v in values if norm(v)]", "expected = {'valid_count': len(valid), 'unique_count': len(set(valid)), 'first': valid[0] if valid else '', 'last': valid[-1] if valid else ''}", "assert candidate(values) == expected"]),
        (f"{pid}_last_index(values, target)", "Return the original index of the last canonical target match, or -1.", [f"values = {values}", f"expected = next((i for i in range(len(values)-1, -1, -1) if norm(values[i]) and norm(values[i]) == norm({target})), -1)", f"assert candidate(values, {target}) == expected"]),
        (f"{pid}_positions(values)", "Map each canonical valid value to all original input positions in ascending order.", [f"values = {values}", "expected = {}", "for i, v in enumerate(values):", "    k = norm(v)", "    if k:", "        expected.setdefault(k, []).append(i)", "assert candidate(values) == expected"]),
        (f"{pid}_ranked(values)", "Return (canonical, count) pairs sorted by descending count, then canonical name.", [f"values = {values}", "counts = {}", "for v in values:", "    k = norm(v)", "    if k:", "        counts[k] = counts.get(k, 0) + 1", "assert candidate(values) == sorted(counts.items(), key=lambda item: (-item[1], item[0]))"]),
        (f"{pid}_replace_invalid(values, replacement)", "Return canonical valid values and use replacement unchanged for every invalid input.", [f"values = {values}", "assert candidate(values, '?') == [norm(v) if norm(v) else '?' for v in values]"]),
        (f"{pid}_merge_counts(left, right)", "Merge canonical counts from both inputs into one dictionary.", [f"left = {values}", f"right = {right}", "expected = {}", "for v in left + right:", "    k = norm(v)", "    if k:", "        expected[k] = expected.get(k, 0) + 1", "assert candidate(left, right) == expected"]),
        (f"{pid}_transitions(values)", "Count adjacent transitions between consecutive canonical valid values after invalid values are removed.", [f"values = {values}", "valid = [norm(v) for v in values if norm(v)]", "expected = {}", "for a, b in zip(valid, valid[1:]):", "    expected[(a, b)] = expected.get((a, b), 0) + 1", "assert candidate(values) == expected"]),
        (f"{pid}_runs(values)", "Return canonical runs as (value, run_length) after invalid values are removed.", [f"values = {values}", "valid = [norm(v) for v in values if norm(v)]", "expected = []", "for k in valid:", "    if expected and expected[-1][0] == k:", "        expected[-1] = (k, expected[-1][1] + 1)", "    else:", "        expected.append((k, 1))", "assert candidate(values) == expected"]),
        (f"{pid}_cycle_report(values, target)", "Return exactly normalized_target, first_index, last_index, occurrences, and stable_unique; invalid target gives empty target and -1 indexes.", [f"values = {values}", f"t = norm({target})", "matches = [i for i, v in enumerate(values) if t and norm(v) == t]", "unique = []", "for v in values:", "    k = norm(v)", "    if k and k not in unique:", "        unique.append(k)", "expected = {'normalized_target': t, 'first_index': matches[0] if matches else -1, 'last_index': matches[-1] if matches else -1, 'occurrences': len(matches), 'stable_unique': unique}", f"assert candidate(values, {target}) == expected"]),
    ]
    result = []
    for step, (signature, instruction, assertions) in enumerate(specs, 1):
        entry = signature.split("(", 1)[0]
        result.append({
            "task_id": f"{pid}::{step:02d}",
            "prompt": prompt(p, step, signature, instruction),
            "test": tests(p["helper"], assertions),
            "entry_point": entry,
            "project_id": pid,
            "step_index": step,
            "project_label": p["label"],
            "benchmark_type": "rhythm_v6_project_sequence",
        })
    return result


def write_batch(output: Path, indexes: range) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [record for index in indexes for record in records_for(project(index))]
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    assert len(records) == 160
    print(f"Wrote {len(records)} tasks / 10 projects to {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="validation_10x10/data/rhythm_v6_30")
    args = parser.parse_args()
    out = Path(args.output_dir)
    for batch in range(3):
        write_batch(out / f"batch_{batch + 1}.jsonl", range(batch * 10, (batch + 1) * 10))


if __name__ == "__main__":
    main()
"""


ANALYZER = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def totals(rows: list[dict], condition: str) -> dict:
    selected = [r for r in rows if r["condition"] == condition]
    passed = sum(bool(r["passed"]) for r in selected)
    total_tokens = sum(int(r["total_tokens"]) for r in selected)
    cost = sum((3.0 * int(r["input_tokens"]) + 15.0 * int(r["output_tokens"])) / 1_000_000 for r in selected)
    return {
        "observations": len(selected),
        "passed": passed,
        "pass_rate": passed / len(selected),
        "attempts": sum(int(r["attempts"]) for r in selected),
        "total_tokens": total_tokens,
        "tokens_per_pass": total_tokens / passed if passed else None,
        "cost_usd": cost,
        "cost_per_pass_usd": cost / passed if passed else None,
    }


def metric(rows: list[dict], clusters: list[int]) -> tuple[float, float, float]:
    sample = [r for r in rows if int(r["global_agent_id"]) in clusters]
    s = totals(sample, "swarm")
    b = totals(sample, "baseline")
    token_reduction = 1.0 - s["total_tokens"] / b["total_tokens"]
    quality_delta = s["pass_rate"] - b["pass_rate"]
    cost_pass_reduction = 1.0 - s["cost_per_pass_usd"] / b["cost_per_pass_usd"]
    return token_reduction, quality_delta, cost_pass_reduction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs=3, required=True)
    parser.add_argument("--output", default="validation_10x10/results/rhythm-v6-30/report.json")
    parser.add_argument("--bootstrap", type=int, default=20000)
    args = parser.parse_args()

    rows = []
    for batch, run_dir in enumerate(args.runs):
        for row in read_jsonl(Path(run_dir) / "outcomes.jsonl"):
            row["global_agent_id"] = batch * 10 + int(row["agent_id"])
            rows.append(row)
    clusters = list(range(30))
    expected = 30 * 16
    s = totals(rows, "swarm")
    b = totals(rows, "baseline")
    point = metric(rows, clusters)

    rng = random.Random(20260806)
    boot = [[], [], []]
    for _ in range(args.bootstrap):
        sample = [rng.choice(clusters) for _ in clusters]
        # Preserve multiplicity by remapping sampled cluster rows to synthetic ids.
        expanded = []
        for synthetic_id, cluster in enumerate(sample):
            for row in rows:
                if int(row["global_agent_id"]) == cluster:
                    copy = dict(row)
                    copy["global_agent_id"] = synthetic_id
                    expanded.append(copy)
        values = metric(expanded, list(range(30)))
        for i, value in enumerate(values):
            boot[i].append(value)

    report = {
        "schema_version": "6.0",
        "design": "30 new projects x 16 ordered tasks; three frozen 10x10 batches",
        "swarm": s,
        "baseline": b,
        "token_reduction": point[0],
        "quality_delta": point[1],
        "cost_per_pass_reduction": point[2],
        "ci95": {
            "token_reduction": [percentile(boot[0], 0.025), percentile(boot[0], 0.975)],
            "quality_delta": [percentile(boot[1], 0.025), percentile(boot[1], 0.975)],
            "cost_per_pass_reduction": [percentile(boot[2], 0.025), percentile(boot[2], 0.975)],
        },
    }
    report["gates"] = {
        "complete_30x16": s["observations"] == expected and b["observations"] == expected,
        "quality_noninferiority_lower_ci_at_least_minus_2pp": report["ci95"]["quality_delta"][0] >= -0.02,
        "cost_per_pass_lower_ci_above_zero": report["ci95"]["cost_per_pass_reduction"][0] > 0.0,
    }
    report["verdict"] = "CONFIRMED" if all(report["gates"].values()) else "NOT_CONFIRMED"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
'''


RUNNER_SH = r'''#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

python validation_10x10/scripts/generate_rhythm_v6_projects.py
python -m compileall -q validation_10x10/swarm_validation
python -m unittest discover -s validation_10x10/swarm_validation/tests -v

for batch in 1 2 3; do
  config="validation_10x10/examples/rhythm_v6_30/batch_${batch}.json"
  tasks="validation_10x10/data/rhythm_v6_30/batch_${batch}.jsonl"
  output="validation_10x10/results/live-rhythm-v6-30/batch_${batch}"
  PYTHONPATH=validation_10x10 python -m swarm_validation.cli plan --config "$config" --tasks "$tasks" --output-dir "$output"
done

echo "Unit and plan tests passed."
if [[ "${1:-}" != "--live" ]]; then
  echo "Live API run not started. Re-run: bash validation_10x10/RUN_RHYTHM_V6_30.sh --live"
  exit 0
fi

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is required for --live}"
for batch in 1 2 3; do
  config="validation_10x10/examples/rhythm_v6_30/batch_${batch}.json"
  tasks="validation_10x10/data/rhythm_v6_30/batch_${batch}.jsonl"
  output="validation_10x10/results/live-rhythm-v6-30/batch_${batch}"
  PYTHONPATH=validation_10x10 python -m swarm_validation.cli run \
    --config "$config" \
    --tasks "$tasks" \
    --output-dir "$output" \
    --confirm-live-run RUN_10X10_CLAUDE_VALIDATION
done

python validation_10x10/scripts/analyze_rhythm_v6_30.py \
  --runs \
  validation_10x10/results/live-rhythm-v6-30/batch_1 \
  validation_10x10/results/live-rhythm-v6-30/batch_2 \
  validation_10x10/results/live-rhythm-v6-30/batch_3 \
  --output validation_10x10/results/live-rhythm-v6-30/report_30_projects.json
'''


DOC = r'''# SWARM_OS v6 — RYTM wartości tokenów i pamięć po pełnym cyklu

## Korekta rdzenia

- `PION` nadal mierzy właściwy kierunek.
- `fuel` pozostaje rezerwą energetyczną i spada, gdy układ oddala się od PIONU lub traci RYTM.
- `RYTM` mierzy jeden spójny proces: stabilną wartość jakości utworzonej przez cały ważony przepływ tokenów.
- RYTM zapisuje poziom równowagi, zmienność oraz podpisany trend (`falling`, `rising`, `oscillating`, `stable`).
- `working_memory` jest wyłącznie materiałem bieżącego cyklu i nie trafia do promptu.
- Dopiero `ROZPAD II -> 3 -> 6 -> 28 -> 40` oczyszcza, scala i zapisuje intuicję.
- Po przekroczeniu `40` intuicja staje się częścią nowszego systemu w kolejnym cyklu; nie jest wyłączana zwykłym progiem paliwa i pozostaje na retry.

## Test

30 nowych projektów, każdy po 16 kolejnych zadań. Zestaw jest podzielony na trzy zamrożone partie 10x10 zgodne z obecnym runnerem. Główne kryterium biznesowe to koszt na poprawne rozwiązanie przy zachowaniu jakości. Raport dodatkowo pokazuje wszystkie tokeny i ich przedziały ufności.
'''


def write_support_files(root: Path) -> None:
    tests = root / "validation_10x10/swarm_validation/tests/test_rhythm_token_value_v6.py"
    tests.write_text(RHYTHM_TEST, encoding="utf-8")

    generator = root / "validation_10x10/scripts/generate_rhythm_v6_projects.py"
    generator.write_text(GENERATOR, encoding="utf-8")
    generator.chmod(0o755)

    analyzer = root / "validation_10x10/scripts/analyze_rhythm_v6_30.py"
    analyzer.write_text(ANALYZER, encoding="utf-8")
    analyzer.chmod(0o755)

    runner = root / "validation_10x10/RUN_RHYTHM_V6_30.sh"
    runner.write_text(RUNNER_SH, encoding="utf-8")
    runner.chmod(0o755)

    docs = root / "validation_10x10/RHYTHM_TOKEN_VALUE_V6.md"
    docs.write_text(DOC, encoding="utf-8")

    config_dir = root / "validation_10x10/examples/rhythm_v6_30"
    config_dir.mkdir(parents=True, exist_ok=True)
    for batch in range(1, 4):
        config = {
            "model": "claude-sonnet-4-6",
            "agents_per_condition": 10,
            "tasks_per_agent": 16,
            "assignment_seed": 20260806 + batch,
            "call_order_seed": 330600 + batch,
            "assignment_mode": "project_sequence",
            "max_attempts": 3,
            "max_tokens": 1536,
            "temperature": None,
            "timeout_seconds": 3.0,
            "memory_mb": 512,
            "target_token_reduction": 0.0,
            "quality_noninferiority_margin": 0.02,
            "bootstrap_samples": 20000,
            "max_live_calls": 960,
            "pricing_input_usd_per_million": 3.0,
            "pricing_output_usd_per_million": 15.0,
            "cycle_length": 16,
            "max_intuitive_entries": 4,
            "max_prompt_memory_entries": 1,
            "max_working_prompt_entries": 0,
            "working_memory_min_quality": 0.70,
            "memory_min_keyword_overlap": 2,
            "memory_min_jaccard": 0.08,
            "memory_recall_fuel": 0.42,
            "rhythm_window": 6,
            "token_reference_weighted_tokens": 1000.0,
            "output_token_weight": 5.0,
            "token_equilibrium_alpha": 0.08,
            "vertical_threshold": 0.62,
            "crystallization_threshold": 0.66,
            "rhythm_threshold": 0.62,
            "stagnation_threshold": 0.46,
            "crack_threshold": 0.34,
            "first_collapse_fuel": 0.24,
            "first_collapse_balance": 0.30,
            "first_collapse_persistence": 2,
            "recovery_fuel": 0.44,
            "recovery_balance": 0.42,
            "recovery_window": 3,
            "stagnation_persistence": 2,
            "crack_persistence": 3,
            "crack_load": 1.10,
            "stagnation_drain": 0.18,
            "stagnation_tension_gain": 0.16,
            "stagnation_regulation_loss": 0.10,
        }
        (config_dir / f"batch_{batch}.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def self_test() -> None:
    # Validate support code syntax before touching a repository.
    compile(RHYTHM_TEST, "test_rhythm_token_value_v6.py", "exec")
    compile(GENERATOR, "generate_rhythm_v6_projects.py", "exec")
    compile(ANALYZER, "analyze_rhythm_v6_30.py", "exec")
    print("Installer embedded-code self-test: PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--live", action="store_true", help="start the three live API batches after unit tests")
    parser.add_argument("--no-git", action="store_true", help="do not create branch/commit/push")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    root = repo_root(args.repo)
    self_test()

    if not args.no_git:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=True).stdout
        if status.strip():
            raise SystemExit("Repository has uncommitted changes. Commit or stash them before applying v6.")
        current = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
        if current != BRANCH:
            existing = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/{BRANCH}"], cwd=root, text=True).returncode == 0
            run(["git", "checkout", BRANCH if existing else "-b", *( [] if existing else [BRANCH])], root)

    files = [
        root / "validation_10x10/swarm_validation/models.py",
        root / "validation_10x10/swarm_validation/protocol.py",
        root / "validation_10x10/swarm_validation/controller.py",
        root / "validation_10x10/swarm_validation/runner.py",
        root / "validation_10x10/swarm_validation/tests/test_related_projects.py",
        root / "validation_10x10/swarm_validation/tests/test_memory_cycle_v4.py",
    ]
    for path in files:
        if not path.exists():
            raise SystemExit(f"Missing expected file: {path}")

    patch_models(files[0])
    patch_protocol(files[1])
    patch_controller(files[2])
    patch_runner(files[3])
    patch_existing_tests(files[4])
    patch_memory_tests(files[5])
    write_support_files(root)

    run([sys.executable, "validation_10x10/scripts/generate_rhythm_v6_projects.py"], root)
    run([sys.executable, "-m", "compileall", "-q", "validation_10x10/swarm_validation"], root)
    run([sys.executable, "-m", "unittest", "discover", "-s", "validation_10x10/swarm_validation/tests", "-v"], root)

    for batch in range(1, 4):
        run([
            sys.executable, "-m", "swarm_validation.cli", "plan",
            "--config", f"validation_10x10/examples/rhythm_v6_30/batch_{batch}.json",
            "--tasks", f"validation_10x10/data/rhythm_v6_30/batch_{batch}.jsonl",
            "--output-dir", f"validation_10x10/results/live-rhythm-v6-30/batch_{batch}",
        ], root)

    if not args.no_git:
        run(["git", "add", "validation_10x10"], root)
        run(["git", "commit", "-m", "Align rhythm with stable token value and gate intuition at cycle 40"], root)
        push = run(["git", "push", "-u", "origin", BRANCH], root, check=False)
        if push.returncode == 0 and shutil.which("gh"):
            run([
                "gh", "pr", "create", "--base", "main", "--head", BRANCH,
                "--title", "SWARM v6: token-value rhythm and cycle-bound intuition",
                "--body", "Implements RYTM as stable value of the full weighted token flow; keeps working evidence internal; exposes intuition only after ROZPAD II -> 3 -> 6 -> 28 -> 40; adds 30-project x 16-step validation in three frozen batches.",
            ], root, check=False)

    if args.live:
        run(["bash", "validation_10x10/RUN_RHYTHM_V6_30.sh", "--live"], root)
    else:
        print("\nPATCHED AND UNIT-TESTED. Live test command:")
        print("bash validation_10x10/RUN_RHYTHM_V6_30.sh --live")


if __name__ == "__main__":
    main()
