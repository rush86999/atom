# Scoped agent deletion — test results

Executed source: `e34de29d53636a5232e126bcba8e5f5aa7af9734`  
Base main: `f8706fb48569e77df21801df1cc23a8d7b61ba17`

Every command ran from `backend/` with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Confirmed cross-tenant reproduction on base main

`cross-tenant-repro-base.log`:

```
DELETE /api/agents/foreign-agent
status 200
body {"success":true,"data":{"agent_id":"foreign-agent","rows_cleaned":{}},...}
foreign_agent_remaining 0
```

The caller was a workspace_admin in tenant A; the target belonged to tenant B.

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_delete_scope_contract.py \
  tests/test_agent_delete_cascade.py \
  tests/test_agent_decision_contract.py \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **53 passed** | `focused-314.log` |
| Python 3.11 | **53 passed** | `focused-311.log` |

The new contract file contributes 12 controls: cross-tenant/cross-workspace
refusal, authorized owner/admin delete, dependent-row cleanup and receipt,
stale target, authority change, replay/changed target, audit rollback,
post-commit readback, lost confirmation, main-agent/running-task guards, demo
tombstone durability and tampered receipt.

## Clean affected selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_delete_scope_contract.py \
  tests/test_agent_delete_cascade.py \
  tests/test_agent_decision_contract.py \
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

| Tree | Python | Passed | Skipped | Failed | Log |
|---|---|---|---|---|---|
| Candidate `e34de29d5` | 3.14 | **346** | 3 | 2 | `affected-314.log` |
| Candidate `e34de29d5` | 3.11 | **328** | 0 | 1 | `affected-311.log` |
| Main `f8706fb48` | 3.14 | 332 | 3 | 4 | `baseline-main-314.log` |
| Main `f8706fb48` | 3.11 | 314 | 0 | 3 | `baseline-main-311.log` |

The baseline selection excludes only the new contract file. Candidate delta:
**+12 new controls, +2 repaired route fixtures, zero new failures**.

### Shared baseline failures

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`
  (both versions)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  (3.14 only; the 3.11 environment lacks `schemathesis` for that conftest)

Main additionally fails the two delete-route fixtures the candidate repairs:

- `tests/api/test_agent_routes.py::test_delete_agent_success`
- `tests/unit/api/test_agent_routes.py::TestDeleteAgent::test_delete_agent_success`

The broad selection also has 53 pre-existing `test_agent_control_routes.py`
daemon-control failures in both trees. They are unrelated to the delete route
and are not claimed as repaired.

## Changed test fixtures

- `tests/test_agent_delete_cascade.py`: uses a committed file-backed SQLite
  world so the fresh-session dependent-row readback can observe the delete,
  instead of a shared uncommitted outer transaction.
- `tests/api/test_agent_routes.py`: captures the agent id before the request,
  refreshes the test session for the post-delete query, and uses the real
  `get_agent_tasks` running-task method.

Both preserve the original assertions; no test was deleted, skipped or
xfailed.

## Notes

- Logs use `-p no:randomly` for deterministic identity comparison.
- Candidate and baseline ran on the same host with the declared environment.
- No live model/provider/credential/spend/send/download/deployment operation.
