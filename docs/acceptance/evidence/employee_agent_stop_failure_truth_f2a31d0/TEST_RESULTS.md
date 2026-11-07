# Agent stop/cancel failure truth — test results

Executed source: `f2a31d0e66ba36d015934875130e777d69f06957`  
Base main: `248a2329623b433e68104c4d89d2965683d81013`

Every command ran from `backend/` with a fresh explicit scratch SQLite
database, `TESTING=1`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=$PWD` and
`-p no:randomly`.

## External probes

The exact Agent 3 probes and the two supplied registry-fault probes were run
unchanged (copied only for execution and included as
`agent3_stop_probes.py` and `root_registry_fault_probes.py`).

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent3_pr695_stop_probes.py \
  tests/test_verifier_stop_failure_truth.py -q --tb=short
```

| Tree | Python | Result | Log |
|---|---|---|---|
| Merged predecessor `1faccf71c` / base main `248a23296` | 3.14 | **3 failed, 2 passed** | `pre-fix-external-314.log` |
| Merged predecessor `1faccf71c` / base main `248a23296` | 3.11 | **3 failed, 2 passed** | `pre-fix-external-311.log` |
| Fixed `f2a31d0e6` | 3.14 | **5 passed** | `external-probes-314.log` |
| Fixed `f2a31d0e6` | 3.11 | **5 passed** | `external-probes-311.log` |

Pre-fix failures were exactly:

- `test_receipt_failure_response_still_reports_cancelled_count`
- `test_cancellation_failure_after_partial_progress_is_not_effect_none`
- `test_unreadable_registry_is_not_a_verified_empty_task_set`

## Focused stop / shared-route callers

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_stop_scope_contract.py \
  tests/test_agent_stop_failure_projection.py \
  tests/test_agent_decision_contract.py \
  tests/test_agent_run_admission_contract.py \
  tests/test_agent_delete_scope_contract.py \
  tests/test_agent_replace_scope_contract.py \
  tests/api/test_agent_routes.py::test_update_agent \
  tests/api/test_agent_routes.py::test_replace_agent_success \
  tests/api/test_agent_routes.py::test_delete_agent_success \
  tests/api/test_agent_routes.py::test_run_agent_success \
  tests/api/test_agent_routes.py::test_stop_running_agent \
  tests/api/test_agent_routes.py::test_stop_agent_multiple_tasks \
  tests/test_agent_routes_coverage.py::TestAgentStopEndpoint \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **101 passed** | `focused-314.log` |
| Python 3.11 | **101 passed** | `focused-311.log` |

The focused selection contains the nine submitted stop controls, the new
failure-truth controls, the safe-projection tests, and the shared decision
route callers affected by the HTTP mapper.

## Affected selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_stop_scope_contract.py \
  tests/test_agent_stop_failure_projection.py \
  tests/test_agent_run_admission_contract.py \
  tests/test_agent_delete_scope_contract.py \
  tests/test_agent_delete_cascade.py \
  tests/test_agent_decision_contract.py \
  tests/test_agent_replace_scope_contract.py \
  tests/unit/api/test_agent_routes.py \
  tests/api/test_agent_routes.py \
  tests/test_agent_routes_coverage.py \
  tests/test_agent_execution_service.py \
  tests/test_agent_governance_service.py \
  tests/test_covpush_w29_governance.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_agent_marketplace_publish_contract.py \
  tests/contract/test_agent_api_contract.py \
  -q --tb=line
```

The 3.11 command omits `tests/contract/test_agent_api_contract.py` because that
interpreter lacks `schemathesis`.

| Tree | Python | Passed | Skipped | Failed | Log |
|---|---|---|---|---|---|
| Fixed `f2a31d0e6` | 3.14 | **392** | 3 | 2 | `affected-314.log` |
| Fixed `f2a31d0e6` | 3.11 | **374** | 0 | 1 | `affected-311.log` |
| Base `248a23296` | 3.14 | 385 | 3 | 2 | `baseline-main-314.log` |
| Base `248a23296` | 3.11 | 367 | 0 | 1 | `baseline-main-311.log` |

Delta: **+7 controls on both interpreters, zero new failures**.

### Shared baseline failures

| Test | 3.14 | 3.11 | Status |
|---|---|---|---|
| `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent` | failed | failed | pre-existing on main |
| `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination` | failed | not collected | pre-existing on main; 3.11 lacks `schemathesis` |

## New failure-truth controls

- `test_unreadable_task_state_is_unavailable_before_dispatch` — typed 503,
  effect none, no cancel, tasks remain, no audit.
- `test_cancellation_exception_after_dispatch_is_effect_unknown` — 503,
  effect unknown, do not repeat, no invented count, one task remains.
- `test_receipt_failure_reports_effect_unknown_after_cancel` — asserts the
  public 503 carries `data.agent_id` and `data.cancelled_tasks == 2`.
- `test_readback_failure_reports_known_cancelled_count` — post-commit refuted
  readback carries the known count and committed effect.
- Safe-projection tests — allowlisted types only, private fields omitted,
  no-data decision does not conjure an observation.

## Notes

- `cancelled_tasks` is the in-process registry's reported result, not proof of
  physical worker termination.
- The DB rollback after a cancellation exception covers only the database
  claim; the external effect remains unknown and must not be blindly retried.
- Shared baseline failures are recorded, not repaired or waived.
