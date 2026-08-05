from __future__ import annotations

import random
from typing import Any

from .models import TaskOutcome
from .protocol import ProtocolConfig


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _cluster_rows(outcomes: list[TaskOutcome]) -> dict[int, dict[str, float]]:
    clusters: dict[int, dict[str, float]] = {}
    for outcome in outcomes:
        row = clusters.setdefault(outcome.agent_id, {
            "swarm_tokens": 0.0, "baseline_tokens": 0.0,
            "swarm_pass": 0.0, "baseline_pass": 0.0,
            "swarm_n": 0.0, "baseline_n": 0.0,
        })
        prefix = "swarm" if outcome.condition == "swarm" else "baseline"
        row[f"{prefix}_tokens"] += outcome.total_tokens
        row[f"{prefix}_pass"] += 1.0 if outcome.passed else 0.0
        row[f"{prefix}_n"] += 1.0
    return clusters


def _metrics(rows: list[dict[str, float]]) -> tuple[float, float]:
    swarm_tokens = sum(row["swarm_tokens"] for row in rows)
    baseline_tokens = sum(row["baseline_tokens"] for row in rows)
    reduction = 1.0 - swarm_tokens / baseline_tokens if baseline_tokens else 0.0
    swarm_pass = sum(row["swarm_pass"] for row in rows)
    baseline_pass = sum(row["baseline_pass"] for row in rows)
    swarm_n = sum(row["swarm_n"] for row in rows)
    baseline_n = sum(row["baseline_n"] for row in rows)
    delta = (swarm_pass / swarm_n if swarm_n else 0.0) - (baseline_pass / baseline_n if baseline_n else 0.0)
    return reduction, delta


def analyze(outcomes: list[TaskOutcome], config: ProtocolConfig) -> dict[str, Any]:
    clusters_map = _cluster_rows(outcomes)
    expected_ids = set(range(config.agents_per_condition))
    if set(clusters_map) != expected_ids:
        raise ValueError("Incomplete agent clusters")
    rows = [clusters_map[index] for index in sorted(clusters_map)]
    for index, row in enumerate(rows):
        if row["swarm_n"] != config.tasks_per_agent or row["baseline_n"] != config.tasks_per_agent:
            raise ValueError(f"Agent pair {index} has incomplete outcomes")
    reduction, quality_delta = _metrics(rows)

    rng = random.Random(20260801)
    reductions: list[float] = []
    quality_deltas: list[float] = []
    for _ in range(config.bootstrap_samples):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        value, delta = _metrics(sample)
        reductions.append(value)
        quality_deltas.append(delta)
    reduction_ci = [_percentile(reductions, 0.025), _percentile(reductions, 0.975)]
    quality_ci = [_percentile(quality_deltas, 0.025), _percentile(quality_deltas, 0.975)]

    swarm = [item for item in outcomes if item.condition == "swarm"]
    baseline = [item for item in outcomes if item.condition == "baseline"]

    def summary(items: list[TaskOutcome]) -> dict[str, Any]:
        return {
            "observations": len(items),
            "passed": sum(item.passed for item in items),
            "pass_rate": sum(item.passed for item in items) / len(items),
            "attempts": sum(item.attempts for item in items),
            "input_tokens": sum(item.input_tokens for item in items),
            "output_tokens": sum(item.output_tokens for item in items),
            "cache_creation_input_tokens": sum(item.cache_creation_input_tokens for item in items),
            "cache_read_input_tokens": sum(item.cache_read_input_tokens for item in items),
            "total_tokens": sum(item.total_tokens for item in items),
            "provider_latency_ms": round(sum(item.provider_latency_ms for item in items), 3),
        }

    token_gate = reduction_ci[0] >= config.target_token_reduction
    quality_gate = quality_ci[0] >= -config.quality_noninferiority_margin
    complete = len(outcomes) == config.agents_per_condition * config.tasks_per_agent * 2
    verdict = "CONFIRMED" if token_gate and quality_gate and complete else "NOT_CONFIRMED"
    return {
        "schema_version": "5.0",
        "protocol": config.to_dict(),
        "swarm": summary(swarm),
        "baseline": summary(baseline),
        "token_reduction": reduction,
        "token_reduction_cluster_bootstrap_ci95": reduction_ci,
        "quality_pass_rate_delta": quality_delta,
        "quality_delta_cluster_bootstrap_ci95": quality_ci,
        "gates": {
            "complete_10x10": complete,
            "token_reduction_lower_ci_at_least_target": token_gate,
            "quality_noninferiority_lower_ci": quality_gate,
        },
        "verdict": verdict,
    }


def render_markdown(report: dict[str, Any]) -> str:
    pct = lambda value: f"{value * 100:.2f}%"
    sw = report["swarm"]
    base = report["baseline"]
    token_ci = report["token_reduction_cluster_bootstrap_ci95"]
    quality_ci = report["quality_delta_cluster_bootstrap_ci95"]
    return f"""# SWARM_OS 10 vs 10 — validation report

**Verdict: {report['verdict']}**

| Metric | 10 SWARM agents | 10 baseline agents |
|---|---:|---:|
| Agent-task observations | {sw['observations']} | {base['observations']} |
| Passed | {sw['passed']} | {base['passed']} |
| Pass rate | {pct(sw['pass_rate'])} | {pct(base['pass_rate'])} |
| Attempts | {sw['attempts']} | {base['attempts']} |
| Input tokens | {sw['input_tokens']} | {base['input_tokens']} |
| Output tokens | {sw['output_tokens']} | {base['output_tokens']} |
| Total provider tokens | {sw['total_tokens']} | {base['total_tokens']} |

## Primary result

- Token reduction: **{pct(report['token_reduction'])}**
- 95% agent-cluster bootstrap CI: **{pct(token_ci[0])} to {pct(token_ci[1])}**
- Pass-rate difference (SWARM − baseline): **{pct(report['quality_pass_rate_delta'])}**
- 95% agent-cluster bootstrap CI: **{pct(quality_ci[0])} to {pct(quality_ci[1])}**

## Preregistered gates

- Complete 10×10 run: {report['gates']['complete_10x10']}
- Lower 95% token-reduction bound ≥ target: {report['gates']['token_reduction_lower_ci_at_least_target']}
- Quality non-inferiority: {report['gates']['quality_noninferiority_lower_ci']}

`CONFIRMED` means the run met the preregistered statistical rule. It does not mean absolute certainty.
"""
