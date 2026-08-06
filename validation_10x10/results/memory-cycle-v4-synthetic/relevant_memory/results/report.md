# SWARM_OS 10 vs 10 — validation report

**Verdict: NOT_CONFIRMED**

| Metric | 10 SWARM agents | 10 baseline agents |
|---|---:|---:|
| Agent-task observations | 160 | 160 |
| Passed | 159 | 159 |
| Pass rate | 99.38% | 99.38% |
| Attempts | 207 | 218 |
| Input tokens | 41723 | 42294 |
| Output tokens | 1656 | 1744 |
| Total provider tokens | 43379 | 44038 |

## Primary result

- Token reduction: **1.50%**
- 95% agent-cluster bootstrap CI: **-0.11% to 3.41%**
- Pass-rate difference (SWARM − baseline): **0.00%**
- 95% agent-cluster bootstrap CI: **0.00% to 0.00%**

## Preregistered gates

- Complete 10×10 run: True
- Lower 95% token-reduction bound ≥ target: False
- Quality non-inferiority: True

`CONFIRMED` means the run met the preregistered statistical rule. It does not mean absolute certainty.
