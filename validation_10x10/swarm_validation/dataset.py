from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
from pathlib import Path
from typing import Any, Iterable, TextIO

REQUIRED_TASK_FIELDS = ("task_id", "prompt", "test", "entry_point")


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    prompt: str
    test: str
    entry_point: str
    canonical_solution: str | None = None
    metadata: dict[str, Any] | None = None


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with _open_text(path) as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Line {line_number} of {path} must contain a JSON object")
            yield line_number, value


def load_tasks(path: str | Path) -> list[BenchmarkTask]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Task dataset not found: {source}")
    tasks: list[BenchmarkTask] = []
    seen: set[str] = set()
    for line_number, item in _iter_jsonl(source):
        missing = [field for field in REQUIRED_TASK_FIELDS if field not in item]
        if missing:
            raise ValueError(f"Task on line {line_number} is missing: {', '.join(missing)}")
        task_id = str(item["task_id"])
        if task_id in seen:
            raise ValueError(f"Duplicate task_id {task_id!r}")
        seen.add(task_id)
        entry_point = str(item["entry_point"])
        if not entry_point.isidentifier():
            raise ValueError(f"Invalid entry_point {entry_point!r} for {task_id}")
        known = set(REQUIRED_TASK_FIELDS) | {"canonical_solution"}
        metadata = {key: value for key, value in item.items() if key not in known}
        tasks.append(BenchmarkTask(
            task_id=task_id,
            prompt=str(item["prompt"]),
            test=str(item["test"]),
            entry_point=entry_point,
            canonical_solution=str(item["canonical_solution"]) if item.get("canonical_solution") is not None else None,
            metadata=metadata or None,
        ))
    if not tasks:
        raise ValueError(f"Task dataset is empty: {source}")
    return tasks
