# SWARM_OS 10 vs 10 — validation report

**Verdict: NOT_CONFIRMED**

| Metric | 10 SWARM agents | 10 baseline agents |
|---|---:|---:|
| Agent-task observations | 160 | 160 |
| Passed | 160 | 160 |
| Pass rate | 100.00% | 100.00% |
| Attempts | 209 | 220 |
| Input tokens | 42179 | 42794 |
| Output tokens | 1672 | 1760 |
| Total provider tokens | 43851 | 44554 |

## Primary result

- Token reduction: **1.58%**
- 95% agent-cluster bootstrap CI: **-1.82% to 4.75%**
- Pass-rate difference (SWARM − baseline): **0.00%**
- 95% agent-cluster bootstrap CI: **0.00% to 0.00%**

## Preregistered gates

- Complete 10×10 run: True
- Lower 95% token-reduction bound ≥ target: False
- Quality non-inferiority: True

`CONFIRMED` means the run met the preregistered statistical rule. It does not mean absolute certainty.
