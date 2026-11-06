# Goal-run mode/cancel decisions — test results

Executed source: `e74115a92a6529910c24b0fe92833c1c5e48c539`  
Product source: `96d838d5cdc6001242a43402eab5a52b758ac646`  
Accepted admin base: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Runtime: real scratch SQLite with fresh sessions; no live model/agent/provider.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_goal_run_decision_contract.py \
  -q --tb=short
```

Result: **27 passed** (`focused-314.log`). The same command with `$PY311`
gives **27 passed** (`focused-311.log`).

## Affected goal-run selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_goal_run_decision_contract.py \
  tests/test_goal_run_routes.py \
  tests/test_goal_journey_gaps.py \
  tests/test_goal_run_access_control.py \
  tests/test_goal_effect_family_controls.py \
  tests/test_goal_run_service.py \
  tests/test_goal_run_events.py \
  tests/test_goal_run_bugfixes.py \
  tests/test_goal_run_fixes.py \
  tests/test_agent_marketplace_goal_runs.py \
  -q --tb=short
```

Result: **148 passed** on both Python 3.14 and 3.11
(`affected-314.log`, `affected-311.log`).

The same selection on the accepted admin base `9d73552d2` (without the new
contract file) gives **121 passed on both versions**
(`baseline-314.log`, `baseline-311.log`). The branch adds exactly 27 passing
controls; there are no baseline failures in this selection.

## Coverage matrix

- Supervisor mode success with audit and revision bump.
- Member mode refusal; cross-workspace 404.
- Invalid mode 422; already-requested mode 200 no-change/effect none.
- Stale revision race -> 409, peer mode preserved.
- Same-operation replay `already_applied`; changed material 409; later
  revision `committed_unverified`.
- Owner member cancel; supervisor cancel; non-owner member 403; cross-workspace
  404; already-cancelled 409; stale revision 409.
- Cancellation records status, clears `waiting_on`, appends the decision log
  and bumps `material_revision`; replay is idempotent.
- Audit constraint rollback -> 409 `not_applied`, `effect=none`.
- Post-commit readback -> 503 `committed_unverified`.
- Lost confirmation -> 503 `effect_unknown` with identity; no exception text.
- 15 audit-tamper variants never certify.
- Authority deactivation before the claim -> effect-none refusal.
- No raw plan/parameters/decision-log/secret in audit metadata or logs.

## Counts

- Focused: 27 passed on both versions.
- Affected: 148 passed on both versions.
- Baseline: 121 passed on both versions.
- New passing controls: 27.
- Selections overlap; totals are not added together.

## Scope

No plan/advance/resume/execute/checkpoint changes and no live agent/model
execution. No new table or migration. PostgreSQL runtime/soak and multi-worker
qualification remain open. The repaired review/memory/skill/agent branches are
independent and not merged.
