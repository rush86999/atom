# Atomic acting-agent authority claim — test results

Executed source: `9d2ba566c`  
Parent: `ba497c196`

Every command ran from `backend/` through the bounded test gate with
`TESTING=1`, `PYTEST_CURRENT_TEST=1`, an explicit scratch SQLite
`DATABASE_URL`, scratch `ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/
`ATOM_LANCEDB_PATH`/`LANCEDB_URI`, `PYTHONPATH` including
`/private/tmp/root-py311-plugins`, and `-p no:randomly -p pytest_freezegun`.

## Root parent-commit negative

```sh
python3.11 -m pytest /private/tmp/root_guided_parent_commit_probe.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Before the repair: **2 failed** (`root-negative/root-parent-commit-before.log`),
with 201 verified child+audit after a peer scope move or demotion.

After: **2 passed** (`root-probe-after.log`).

The root's probe, proof and failure log are preserved under `root-negative/`.

## Guided matrix

```sh
python3.11 -m pytest tests/api/test_agent_guided_create_goal14.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **19 passed** (`guided-after.log`).

Added coverage:

- supplied peer scope move and autonomous→student demotion after the route
  snapshot, both 409 with zero child/audit/scheduler;
- peer delete and peer confidence/configuration material change;
- valid current autonomous acting-agent twin (201 verified, parent receipt,
  scheduler once);
- replay after parent authority change returns 409, not stale success;
- existing forged-body/blueprint, inactive/concurrent actor, foreign acting
  agent, NULL/{} material, rollback, readback and create-only controls.

## Affected selection

```sh
python3.11 -m pytest \
  tests/api/test_agent_onboarding_routes.py \
  tests/api/test_agent_guided_create_goal14.py \
  tests/api/test_agent_create_goal14.py \
  tests/api/test_agent_routes.py \
  tests/test_agent_routes_coverage.py \
  tests/test_agent_governance_service.py \
  tests/test_agent_decision_contract.py \
  tests/test_ci_backend_lane_contract.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **265 passed** (`affected-after.log`).

## Boundaries

No live model/provider/DB/credential/send/spend/deploy/dependency, no
budget/BYOK file, no new table/store, no deleted/skipped/xfailed test.
