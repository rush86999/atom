# Goal-run WAIT validation — November 16, 2026

This candidate repairs malformed wait specifications at the native goal-run
model and plan boundaries. It does not qualify real-model judgment, the
48-hour retained wait, or whole-app readiness.

## Problem and resulting behavior

A router could accept a list or a null/object event as a WAIT specification,
raise while consuming it, or invent a timer with no deadline from an empty
specification. Such output could leave a job without a usable continuation.

The existing plan validator now validates wait material too. The router uses
its existing `ASK_HUMAN` fallback for unusable output. Native decision execution
also checks persisted or injected WAIT material and creates an answerable
held decision on refusal. Approving that hold does not replay the invalid
WAIT or a supplied concrete `original_decision`.

Valid custom integration events, `human_input`, existing stringified match
values and timer deadlines remain supported. Positive finite `timer_seconds`
values become a concrete deadline once. Unrepresentable durations are
rejected, never clamped. The internal `set_wait` API retains its historical
leniency for missing or malformed deadlines; this is not a claim that every
internal caller is strictly validated. Workspace-wide event ingestion keeps
its existing authority requirements. No new reply endpoint was introduced.

## Independent verification

Product commits `172845127` and `9ff6a22bc` were checked in joined source
`2bff100d5`, which also includes the test-only fixture repair `768b1a943`.
A fresh scratch SQLite run with external network access denied passed **208
checks in 50.46 seconds**; 106 unrelated assignment cases were deselected.
The selection includes native goal-run loops, routes, matching, access,
watchdog, decision contracts, effects, plans and assignment human-input
compatibility. Model responses and API principals were controlled.

Six additional independent counterexamples verified both oversized durations
(`1e300`, `10**400`) refuse without raising, list and null-event refusal,
a valid relative timer, and an exact-match custom integration event. The
initial candidate's two overflow failures remain retained; they were not
counted as passes.

The new permanent 55-case module includes actual router `decide`, public
`advance`/`resume`, no-effect refusal, replay-link rejection, custom matching
and sweepable timer controls. CI selects it explicitly in `backend-core-extra`
with an isolated test database; prior selectors and environments remain.

## Reproduction

Use a supported Python environment and a new absolute scratch database.
Set `TESTING=1`, `PYTEST_VERSION=wait-validation`, and `DATABASE_URL` before
imports. From `backend`, run:

```sh
python -m pytest tests/test_goal_run_wait_spec_validation.py -q
```

No provider credential or real model call is needed. A passing controlled
router test does not establish whether a real served model chooses the right
decision for a user's unfamiliar task.
