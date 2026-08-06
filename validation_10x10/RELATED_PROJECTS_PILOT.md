# SWARM_OS Related Projects Pilot

## Purpose

This is an **exploratory live API pilot** designed to test the setting in which SWARM memory is supposed to help: one agent works through a sequence of related tasks inside one project.

It is separate from the completed HumanEval run. HumanEval uses independent problems and remains the regression benchmark.

## Frozen pilot design

- 10 SWARM agents vs 10 stateless baseline agents.
- One distinct project per paired agent cluster.
- 8 ordered steps per project, 80 paired observations per condition.
- Same Claude model, call order randomization, retry limit, evaluator and token accounting for both conditions.
- Maximum 480 API calls.
- No prompt caching.
- Every task repeats the full project convention, so the baseline is not denied necessary information.
- SWARM may add at most one compact, relevant, passed working-memory lesson from the same project.
- Failed evidence, other-project evidence and all memory on retry are excluded.

## Assignment rule

`assignment_mode = project_sequence` groups tasks by `project_id` and orders them by `step_index`. Project groups may be shuffled by the frozen assignment seed, but steps inside a project may not be shuffled.

## Measures

Primary preregistered exploratory gates:

1. Lower 95% cluster-bootstrap bound for total token reduction is at least 10%.
2. Lower 95% cluster-bootstrap bound for pass-rate difference is at least -2 percentage points.
3. The run is complete.

Business measures reported in addition:

- tokens per passed task,
- estimated provider cost,
- cost per passed task,
- attempts per passed task.

## Interpretation boundary

A positive result is evidence for this frozen related-project dataset, not universal proof. Because the mechanism and dataset were designed after observing HumanEval, the pilot is exploratory. A company-facing confirmatory claim requires freezing this mechanism and running a new blind holdout project set without further tuning.
