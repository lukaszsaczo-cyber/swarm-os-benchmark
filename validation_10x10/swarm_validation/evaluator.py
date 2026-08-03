from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Callable

from .dataset import BenchmarkTask

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SandboxConfig:
    timeout_seconds: float = 3.0
    memory_mb: int = 512
    max_output_chars: int = 8000


@dataclass(frozen=True)
class Evaluation:
    passed: bool
    status: str
    execution_ms: float
    return_code: int | None
    stdout: str
    stderr: str


def _limit_process(config: SandboxConfig) -> Callable[[], None] | None:
    if resource is None:
        return None
    def apply_limits() -> None:
        cpu_seconds = max(1, math.ceil(config.timeout_seconds))
        memory_bytes = max(128, config.memory_mb) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1_000_000, 1_000_000))
        if hasattr(resource, "RLIMIT_NPROC"):
            resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    return apply_limits


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def evaluate(task: BenchmarkTask, completion: str, config: SandboxConfig | None = None) -> Evaluation:
    config = config or SandboxConfig()
    program = (
        "# SWARM_OS 10x10 candidate\n"
        + task.prompt
        + completion
        + "\n\n"
        + task.test
        + f"\n\ncheck({task.entry_point})\n"
    )
    with tempfile.TemporaryDirectory(prefix="swarm-10x10-") as temp_dir:
        path = Path(temp_dir) / "candidate.py"
        path.write_text(program, encoding="utf-8")
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(path)],
                cwd=temp_dir,
                env={"PYTHONIOENCODING": "utf-8"},
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                check=False,
                preexec_fn=_limit_process(config) if os.name == "posix" else None,
            )
            elapsed = (time.perf_counter() - started) * 1000
            return Evaluation(
                passed=proc.returncode == 0,
                status="passed" if proc.returncode == 0 else "failed",
                execution_ms=round(elapsed, 3),
                return_code=proc.returncode,
                stdout=_truncate(proc.stdout, config.max_output_chars),
                stderr=_truncate(proc.stderr, config.max_output_chars),
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = (time.perf_counter() - started) * 1000
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return Evaluation(False, "timeout", round(elapsed, 3), None, _truncate(stdout, config.max_output_chars), _truncate(stderr, config.max_output_chars))
