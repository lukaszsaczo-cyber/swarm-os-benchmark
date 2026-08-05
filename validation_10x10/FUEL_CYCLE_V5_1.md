# Fuel Cycle v5.1 — causal stagnation correction

`STAGNACJA` is not a timeout. It is a persistent loss of fit with the wider system.

The controller now computes `whole_alignment` as the geometric mean of vertical direction, rhythm alignment and regulation. While the system remains in `STAGNACJA`, positive fuel gain is reduced by whole-system alignment, mismatch adds an explicit maintenance cost, tension rises, regulation weakens and `mismatch_load` accumulates. Recovery to `RYTM` is still possible when alignment, balance and fuel are restored. Otherwise the energetic consequences cause `PĘKNIĘCIE -> ROZPAD II -> 3 -> 6 -> 28 -> 40`.

This change deliberately avoids a task-count timeout. The transition is caused by mismatch and its energetic load.
