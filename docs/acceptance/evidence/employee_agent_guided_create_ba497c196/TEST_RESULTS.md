# Guided agent creation — test results

Executed source: `ba497c196`  
Base: `fb4d7f5549169b58a1601a1083207e3f0bb44a6b`

Every command ran from `backend/` through the bounded test gate with
`TESTING=1`, `PYTEST_CURRENT_TEST=1`, an explicit scratch SQLite
`DATABASE_URL`, and scratch `ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/
`ATOM_LANCEDB_PATH`/`LANCEDB_URI`. `PYTHONPATH` included
`/private/tmp/root-py311-plugins`; `-p no:randomly -p pytest_freezegun` was
used.

The guided factory is the only model-facing component and is replaced by a
deterministic controlled double. The route, JWT auth, decision writer,
AuditLog, SQLite state and scheduler boundary are real.

## Failure-first

```sh
python3.11 -m pytest tests/api/test_agent_guided_create_goal14.py \
  -q --tb=short -p no:randomly -p pytest_freezegun
```

Result on the unchanged source: **6 failed, 1 passed**
(`failure-first.log`).

- no operation_id/audit receipt/replay;
- concurrent deactivation still created;
- NULL→{} schedule replay 201 instead of 409;
- scheduler ran twice;
- foreign acting_agent_id queued 202 instead of 404;
- same-scope acting-agent HITL params lacked exact workspace material;
- inactive-user control passed.

## Focused matrix after repair

Same command: **13 passed** (`guided-after.log`).

Exact additive CI env (no office/LanceDB overrides):

```sh
TESTING=1 PYTEST_CURRENT_TEST=1 \
DATABASE_URL=sqlite:///scratch/test.db \
ATOM_DATA_DIR=scratch/data \
SECRET_KEY=ci-test-secret-key ENVIRONMENT=development \
python3.11 -m pytest tests/api/test_agent_guided_create_goal14.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **13 passed** (`ci-guided-step.log`).

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

Result: **259 passed** (`affected-after.log`).

## CI lane contract

```sh
python3.11 -m pytest tests/test_ci_backend_lane_contract.py \
  tests/test_quickstart_matrix_contract.py -q --tb=short
```

Result: **41 passed** (`ci-lane-contract.log`). The new step is declared in
the additive manifest and the workflow; the baseline file is unchanged.

## Boundaries

No live DB/model/provider/credential/send/spend/deploy/dependency, no
budget/BYOK file, no new table/store, no deleted/skipped/xfailed test.
