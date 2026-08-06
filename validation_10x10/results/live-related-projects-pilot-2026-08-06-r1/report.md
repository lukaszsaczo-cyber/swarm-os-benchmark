# SWARM_OS 10 vs 10 — validation report

**Verdict: NOT_CONFIRMED**

| Metric | 10 SWARM agents | 10 baseline agents |
|---|---:|---:|
| Agent-task observations | 80 | 80 |
| Passed | 52 | 48 |
| Pass rate | 65.00% | 60.00% |
| Attempts | 189 | 187 |
| Input tokens | 80253 | 75344 |
| Output tokens | 31250 | 30561 |
| Total provider tokens | 111503 | 105905 |
| Tokens per passed task | 2144.29 | 2206.35 |
| Estimated provider cost (USD) | 0.7095 | 0.6844 |
| Cost per passed task (USD) | 0.013644 | 0.014259 |

## Primary result

- Token reduction: **-5.29%**
- 95% agent-cluster bootstrap CI: **-18.01% to 4.94%**
- Pass-rate difference (SWARM − baseline): **5.00%**
- Token reduction per passed task: **2.81%**
- Cost reduction per passed task: **4.31%**
- 95% agent-cluster bootstrap CI: **-7.50% to 16.25%**

## Preregistered gates

- Complete 10×10 run: True
- Lower 95% token-reduction bound ≥ target: False
- Quality non-inferiority: False

`CONFIRMED` means the run met the preregistered statistical rule. It does not mean absolute certainty.
