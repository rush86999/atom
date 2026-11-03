# Employee repair successor — results

Executed source: `b7ea53b31` (clean worktree at the integrated run).

## Backend

`backend-integrated.log` — **552 passed** across assignment/employee,
readiness/patch invariants, two-domain campaign, goal/approval, HITL,
structured consumers, alignment, oracle/presentation and reviewed-work
neighborhoods.

`focused-affected.log` — **204 passed** across assignment executor, routes,
readiness, proposal, outcome, patch invariants and the two-domain campaign.

`patch-invariants.log` — **8 passed**:

| Invariant | Observed |
|---|---|
| transitive uncertain descendant | upstream invalidation refused; status/result/operation/authority/budget unchanged |
| fact or teaching advance without plan revision | old patch stale; refreshed patch applies in a fresh lifecycle |
| authority transition without plan revision | old patch stale |
| same id/same material | applied once; restart replay `already_applied` |
| same id/different material | conflict |
| concurrent duplicate adoption | one `applied`, one `already_applied`, one revision |
| requirement weakening / unproven fact | refused |
| registered mutation relabelled read-only | refused |
| forced CAS retry | pure callback runs twice, zero adapter effects, one revision |

`two-domain-campaign.log` — **4 passed**: industrial quote feasible 494.75 and
infeasible 5-day twin; procurement corrected 270.00 bill and closed-period
twin.

## Probes

`evidence-contract-probes.log` — **9 passed**: six independent receipt-strength/
Sent Items probes, two G0 probes and the public blocked-readiness route.

`corrected-patch-invariant-probe.log` — **3 passed** with
`base_task_version=record.task_version`.

`original-patch-invariant-probe.log` — **2 passed, 1 failed at setup**: the
original helper uses `task_revision.revision` (the obsolete objective revision),
so its first apply is correctly refused as stale. See README.

## Frontend

`frontend-integrated.log` — **54 passed** across AssignmentPanel, goal-run
detail/index and approvals.

## Pre-existing failures

`pre-existing-task-lifecycle-at-source.log` — the same four
`test_task_lifecycle.py` failures as the parent/base. Disclosed, not counted.

## Boundaries

Deterministic level only. Served-model adaptive choice and ordinary-product
two-domain campaign remain unrun. No model inference or live provider action;
historical denominators unchanged.
