# Fuel Cycle v5 — test results

## Automated tests

| Run | Result |
|---|---:|
| 1 | 21/21 |
| 2 | 21/21 |
| 3 | 21/21 |
| **Total** | **63/63** |

## Paired 10×10 synthetic simulations

| Scenario | SWARM tokens | Baseline tokens | Reduction | Quality delta | Mechanic |
|---|---:|---:|---:|---:|---|
| second_collapse_rebirth | 52,361 | 56,791 | **7.80%** | 0 pp | 10/10 agents completed ROZPAD II and rebirth |
| stable_rhythm | 30,070 | 30,070 | 0.00% | 0 pp | no task-count collapse |
| first_collapse_recovery | 40,383 | 40,383 | 0.00% | 0 pp | 10/10 agents returned to REGULACJA |

For the rebirth scenario the cluster-bootstrap 95% CI for token reduction was
**4.40% to 10.98%**. All scenarios remain **NOT_CONFIRMED** against the 20% gate.
These are deterministic engineering simulations, not live Claude API evidence.
