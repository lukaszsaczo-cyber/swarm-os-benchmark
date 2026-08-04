# SWARM_OS memory cycle v4

## Corrected sequence

`ACTIVE CYCLE → ROZPAD II → 3 → 6 → 28 → 40 → NEW CYCLE`

- **Working/informational memory** exists only inside the active cycle.
- **Local feedback** from a failure remains available only for retries of the same task.
- **ROZPAD II** freezes the completed-cycle material.
- **3** extracts successful residue for analysis.
- **6** deletes all failures, raw errors, raw code and unrelated noise.
- **28** consolidates only a short generalized rule into a pending intuitive record.
- **40** is the transition threshold. No reset occurs inside state 40.
- On crossing **40 → NEW CYCLE**, pending intuitive memory is promoted, working memory and failure buffers are cleared, and the operational cycle resets.

## Retrieval rules

- Only memory from a completed earlier cycle may enter a prompt.
- At least two meaningful keywords and a minimum Jaccard similarity are required.
- At most one compact intuitive rule is injected.
- Raw code is never retained as intuitive memory.
- A failed task never becomes long-term memory.
- After the first failed attempt, intuitive memory is removed; the retry uses only concrete local test feedback.

## Corrected feedback direction

- Success raises fuel and records a generalized successful observation.
- Failure lowers fuel, raises entropy and enters only a transient failure buffer.
- Failure data is destroyed during state 6.

## Verified engineering checks

- Target suite: 19 tests, executed three times — 57/57 passed.
- Relevant-memory simulation: 1.50% point token reduction, equal 159/160 pass count.
- Irrelevant-noise simulation: memory rejected, exact equality between conditions.
- Paired failure-purge simulation: equal forced failures, no retained failure memory, exact equality afterward.
- All synthetic verdicts: `NOT_CONFIRMED`; these checks do not establish the 20% live hypothesis.
