# Approved guided-create HITL resume — test results

Executed source: `abad59590` (stage originally `2e48574ee`; folder retains the stage hash)  
Parent: `9d2ba566c`

Every command ran from `backend/` through the bounded test gate with
`TESTING=1`, `PYTEST_CURRENT_TEST=1`, an explicit scratch SQLite
`DATABASE_URL`, scratch `ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/
`ATOM_LANCEDB_PATH`/`LANCEDB_URI`, `PYTHONPATH` including
`/private/tmp/root-py311-plugins`, and
`-p no:randomly -p pytest_freezegun`.

The guided factory is a deterministic controlled double. The real FastAPI
approval route, HITL row, decision writer, AuditLog, SQLite state and
scheduler boundary are used.

## Focused HITL matrix

```sh
python3.11 -m pytest tests/api/test_agent_guided_create_goal14.py -k hitl \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **7 passed** (`hitl-focused.log`):

- valid approval creates one reviewed agent + receipt and schedules once;
- direct duplicate resume returns `already_applied` without a second child;
- duplicate public approval returns 400 without a second child;
- rejection creates nothing;
- expired row creates nothing;
- wrong-scope reviewer 404;
- modified approval material refused before approval;
- changed stored material refused before approval;
- fresh-session/restart approval creates the agent.

## Full guided matrix

```sh
python3.11 -m pytest tests/api/test_agent_guided_create_goal14.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **26 passed** (`guided-after.log`).

Exact additive CI env: **26 passed** (`ci-guided-step.log`).

## Root parent-commit probe

```sh
python3.11 -m pytest /private/tmp/root_guided_parent_commit_probe.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **2 passed** (`root-probe-after.log`), confirming the atomic parent
claim still holds after the design-before-trust-gate change.

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
  tests/test_hitl_resume.py \
  tests/test_hitl_approvals_journey.py \
  tests/test_workflow_public_approval_flow.py \
  tests/test_ci_backend_lane_contract.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **312 passed** (`affected-after.log`).

## Boundaries

No live model/provider/DB/credential/send/spend/deploy/dependency, no
budget/BYOK file, no new table/store, no deleted/skipped/xfailed test.
