# Public custom agent creation — test results

Executed source: `9dc1e84a9`  
Base main: `01b554c55045334fa562cd2858c278f5bb3e1545`

Every command ran from `backend/` through the bounded test gate with
`TESTING=1`, `PYTEST_CURRENT_TEST=1`, an explicit scratch SQLite
`DATABASE_URL`, and scratch `ATOM_DATA_DIR`/`ATOM_LANCEDB_PATH`/`LANCEDB_URI`.
No live DB, provider, model, credential, send, spend, download or deployment
was used.

## Failure-first on the unmodified route

```sh
TESTING=1 PYTEST_CURRENT_TEST=1 DATABASE_URL="sqlite:///$SCRATCH/test.db" \
  ... python3 run_bounded_test_gate.py --cwd backend --profile bounded -- \
  python3.11 -m pytest tests/api/test_agent_create_goal14.py -q --tb=short -p no:randomly
```

Result: **2 failed, 1 passed** (`failure-first.log`).

```
FAILED test_custom_create_forged_body_is_ignored_and_receipt_replays
  KeyError: 'operation_id'
FAILED test_custom_create_refuses_concurrent_actor_demotion
  assert 201 == 409
PASSED test_custom_create_member_is_forbidden
```

## Focused gate after the repair

Same command against the rebased executed source.

Result: **4 passed** (`focused-311.log`). The added fourth control is
same-operation/changed-material conflict (`409 OPERATION_CONFLICT`).

## Affected selection

```sh
python3.11 -m pytest \
  tests/api/test_agent_routes.py \
  tests/api/test_agent_onboarding_routes.py \
  tests/test_agent_routes_coverage.py \
  tests/test_agent_governance_service.py \
  tests/test_agent_decision_contract.py \
  tests/test_agent_confidence_baseline.py \
  -q --tb=short -p no:randomly
```

Result: **216 passed, 1 failed** (`affected-311.log`).

The one failure is pre-existing and unrelated:

```
tests/test_agent_confidence_baseline.py::TestConfidenceBaseline::test_marketplace_declared_intern_gets_score_in_band
assert "confidence_score=0.55" in src
```

`core/agent_marketplace_service.py` is not in this diff; the assertion reads
the source text and fails identically on pristine `origin/main`
(`baseline-main-confidence.log`, 1 failed).

## Controls exercised

| Control | Result |
|---|---|
| Forged body tenant/workspace/user/status/maturity/confidence ignored | pass |
| Created row uses current actor tenant/workspace | pass |
| Created row forced STUDENT and confidence below 0.5 | pass |
| One durable `AuditLog` `agent_created` receipt | pass |
| Same operation/material replay does not duplicate row or receipt | pass |
| Changed material on same operation id conflicts | pass |
| Concurrent actor demotion at claim boundary refuses create | pass |
| Member without `AGENT_MANAGE` forbidden | pass |

No test was deleted, skipped or xfailed.
