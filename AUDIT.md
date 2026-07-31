# Technical audit

## Verdict

This repository reproduces the reported numbers, but it is **not a HumanEval benchmark** and does not measure real LLM coding performance.

It is a deterministic simulation of two cost/quality policies over synthetic task metadata.

## Reproduced output (seed=42)

- Stateful model cost `Z`: 14217.6
- Stateless model cost `Z`: 30280.0
- Modelled cost reduction: 53.0%
- Derived token proxy reduction: 53.1%
- Stateful mean modelled quality `W`: 0.6668
- Stateless mean modelled quality `W`: 0.6000
- Stateful Q transitions: 10

## What the program actually does

1. Generates 100 metadata records containing a task name, synthetic difficulty and synthetic base line count.
2. Does not generate source-code solutions.
3. Does not execute task-specific unit tests.
4. Computes attempts, quality and cost directly from formulas in `swarm_os_core.py`.
5. Converts model cost to a token proxy with `tokens = int(Z * 4)`.

## Material limitations

- `run_tests` is imported by `benchmark.py` but never called.
- The 20 task templates are labels only. Their template difficulty value is unused.
- Stateful quality is assigned by `0.5 + memory_bonus * 0.1`; stateless quality is fixed at `0.6`.
- Stateful effective difficulty is reduced directly by accumulated memory.
- Stateful complexity falls from `2.5` to `2.0` after memory exceeds `0.2`; stateless complexity stays at `2.5`.
- Therefore the headline advantage is an output of the assumptions encoded in the simulator, not an independently observed performance gain.
- The token counts are not tokenizer measurements or API usage logs.
- The parameter `threshold`, class `Task`, field `entropy`, and helper `run_tests` do not affect the benchmark output.

## Valid claim

> Under the included deterministic simulation assumptions and seed 42, the stateful policy produces 53.0% lower modelled cost Z than the stateless policy.

## Invalid claims without additional evidence

- 53% reduction in real LLM token usage.
- +7 percentage-point improvement on HumanEval.
- Better coding quality on 100 executed programming tasks.
- Production savings for Anthropic, Moonshot AI, OpenAI or another model provider.

## Minimum path to a real benchmark

A real evaluation needs:

1. A recognized dataset such as HumanEval or MBPP, with licenses respected.
2. Identical model, temperature, context budget and stopping rules for both conditions.
3. Actual generated code saved for every attempt.
4. Sandboxed execution of official unit tests.
5. Real token counts from the provider tokenizer/API response.
6. Multiple seeds/runs, confidence intervals and paired statistical testing.
7. A leakage policy defining exactly what state may persist across tasks.
8. Full raw results sufficient for independent reproduction.
