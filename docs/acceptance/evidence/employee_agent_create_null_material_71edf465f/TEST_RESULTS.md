# Exact NULL/{} material — test results

Executed source: `71edf465f`  
Base: `b36bd760b1fa060e43f9468c0f47109ec84270f0`

Every command ran from `backend/` through the bounded test gate with
`TESTING=1`, `PYTEST_CURRENT_TEST=1`, an explicit scratch SQLite
`DATABASE_URL`, and scratch `ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/
`ATOM_LANCEDB_PATH`/`LANCEDB_URI`. `PYTHONPATH` included
`/private/tmp/root-py311-plugins` and `-p pytest_freezegun` was used.

## Failure-first root probe

```sh
python3.11 -m pytest /private/tmp/root-agent-create-null-identity-probe-20261110.py \
  -q --tb=short -p no:randomly -p pytest_freezegun
```

Result on the unchanged source: **4 failed, 2 passed**
(`probe-before.log`).

- changed request NULL→{} for configuration: 201 instead of 409;
- changed request NULL→{} for schedule_config: 201 instead of 409;
- post-commit NULL→{} stored mutation for configuration: 201 instead of 503;
- post-commit NULL→{} stored mutation for schedule_config: 201 instead of 503;
- unchanged NULL and unchanged {} replays already passed.

## Focused probe after the repair

Same command: **6 passed** (`probe-after.log`).

## Create controls

```sh
python3.11 -m pytest tests/api/test_agent_create_goal14.py \
  -q --tb=short -p no:randomly -p pytest_freezegun
```

Result: **15 passed** (`create-controls-after.log`).

The added controls cover both change directions for both fields, post-commit
NULL↔{} mutations, unchanged NULL/{} replays, scheduler-once, and the existing
forged-body, concurrent-demotion, member-forbidden and changed-name controls.

## Affected selection

```sh
python3.11 -m pytest \
  tests/api/test_agent_routes.py \
  tests/api/test_agent_onboarding_routes.py \
  tests/test_agent_routes_coverage.py \
  tests/test_agent_governance_service.py \
  tests/test_agent_decision_contract.py \
  tests/test_agent_confidence_baseline.py \
  -q --tb=short -p no:randomly -p pytest_freezegun
```

Result: **216 passed, 1 failed** (`affected-after.log`).

The one failure is the pre-existing
`TestConfidenceBaseline::test_marketplace_declared_intern_gets_score_in_band`
source-literal assertion against untouched `core/agent_marketplace_service.py`.

## Boundaries

No live DB/model/provider/send/spend/deploy/deps. No new dependency, table,
migration, scope/role/maturity change, or deleted/skipped/xfailed test.
