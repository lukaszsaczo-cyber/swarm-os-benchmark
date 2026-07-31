# SWARM_OS Stateful vs Stateless Simulation

A transparent, deterministic simulation of a stateful agent policy compared with a stateless baseline over 100 synthetic programming-task records.

> **Important:** This is not OpenAI HumanEval and does not execute generated code or official HumanEval tests. It evaluates the behavior of the included mathematical cost-and-memory model.

## Reproduced result (`seed=42`)

| Metric | Stateful | Stateless | Difference |
|---|---:|---:|---:|
| Modelled cost `Z` | 14,217.6 | 30,280.0 | −53.0% |
| Derived token proxy (`int(Z × 4)`) | 56,833 | 121,120 | −53.1% |
| Modelled mean quality `W` | 0.6668 | 0.6000 | +0.0668 |
| Modelled attempts | 327 | 495 | −33.8% |
| Q transitions | 10 | — | — |

These figures are reproducible outputs of the simulator's assumptions. They are **not measurements of real API tokens or code-test pass rates**.

## Run

```bash
python benchmark.py
```

The report is written to `results/benchmark_results.txt`.

To regenerate the architecture image:

```bash
pip install -r requirements.txt
python generate_architecture.py
```

## Repository structure

```text
benchmark.py                  simulation runner
swarm_os_core.py              stateful and stateless policies
humaneval_tasks.py            synthetic task metadata generator
verify_results.py             deterministic regression check
AUDIT.md                      technical scope and limitations
results/benchmark_results.txt reproduced aggregate output
results/benchmark_run_log.txt console log
architecture.png              architecture illustration
```

## What is modelled

The stateful policy accumulates `memory`, which directly lowers effective difficulty and changes the cost multiplier. Its quality score is also calculated from the memory bonus. The stateless baseline resets on every task and uses fixed quality and complexity assumptions.

Read [`AUDIT.md`](AUDIT.md) before citing the result.

## Reproducibility check

```bash
python verify_results.py
```

## License

MIT. See `LICENSE`.
