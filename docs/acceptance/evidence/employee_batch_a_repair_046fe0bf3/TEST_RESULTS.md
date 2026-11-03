# Employee Batch A evidence-strength repair — results

Executed source: `046fe0bf3` (clean worktree at the integrated run).

## Independent evidence probe

`independent-evidence-contract-probe.py` is the independent verifier's six-case
probe, copied verbatim. `independent-evidence-contract-probe.log` shows
**6 passed**. It exercises:

| Case | Observed |
|---|---|
| empty verified receipt | dependent not eligible |
| verification conflict | dependent not eligible |
| verification refuted | dependent not eligible |
| verified with missing fields | dependent not eligible |
| truncated coverage | dependent not eligible |
| provider acceptance only | `sent_record_confirmed` not satisfied |

## Repo controls

`evidence-strength-controls.log` — **38 passed**. The added matrix covers:

- complete explicit verified proof (positive twin);
- absent, malformed, unverified and incomplete proof;
- conflict/refuted proof;
- non-empty missing fields and mismatches;
- unknown, incomplete and truncated coverage;
- mismatched operation/resource/subject/version bindings and missing receipt
  identity;
- skipped/result-less prerequisites;
- unknown receipt requirement names refusing normalization;
- provider acceptance alone leaving Sent Items and recipient delivery
  unresolved;
- matching explicit Sent Items readback satisfying confirmation;
- mismatched readback binding remaining unsatisfied;
- explicit readback without a provider-state field still standing on its own.

## Affected assignment suite

`assignment-affected-suite.log` — **288 passed** across employee proposal,
employee outcome, readiness, executor, routes, resource boundary, quote, step
inputs, send policy and deterministic plan suites.

## Integrated and probe runs

| Log | Result |
|---|---|
| `backend-integrated.log` | **536 passed** |
| `frontend-integrated.log` | **54 passed** |
| `g0-and-blocked-route-probes.log` | **3 passed** |
| `independent-evidence-contract-probe.log` | **6 passed** |

The integrated selection includes the G0 material/projection controls, the
blocked-readiness public route, Batch B atomic adaptation tests, goal
service/routes/loop/validation/projection, HITL and the prior Batch A
neighborhood.

## Pre-existing failures

`pre-existing-task-lifecycle-at-base.log` and
`pre-existing-task-lifecycle-at-repair.log` record the same four
`test_task_lifecycle.py` failures at base `93650be55` and at this source. They
are disclosed, not counted as passing evidence, and are outside the affected
repair selection.

## Boundaries

Batch A only; G3–G5 remain unqualified. No live provider action or model
inference; historical denominators and accepted tags unchanged.
