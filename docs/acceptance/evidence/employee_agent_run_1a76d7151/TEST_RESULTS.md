# Controlled agent-run admission — test results

Executed source: `1a76d7151105d8e7c845b0f7512a4bbf0e576f52`  
Stacked base: #673 evidence `46dc253a1` (delete source `e34de29d5`)  
Underlying main: `f8706fb48569e77df21801df1cc23a8d7b61ba17`

Every command ran from `backend/` with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Confirmed cross-tenant run on base main

`cross-tenant-repro-base.log`:

```
POST /api/agents/foreign-agent/run
status 200
body {"success":true,"data":{"agent_id":"foreign-agent"},"message":"Agent execution started"}
foreign_agent_status student
dispatch_calls [('foreign-agent', {})]
```

Execution was stubbed; no live model/provider call.

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_run_admission_contract.py \
  tests/unit/api/test_agent_routes.py::TestRunAgent \
  tests/test_agent_routes_coverage.py::TestAgentRunOperations \
  tests/test_agent_decision_contract.py \
  tests/test_agent_delete_scope_contract.py \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **67 passed** | `focused-314.log` |
| Python 3.11 | **67 passed** | `focused-311.log` |

The new file contributes 12 controls: member same-scope admission with
job/receipt, cross-workspace/tenant refusal, authorized admin cross-workspace,
deprecated/paused/running refusal, active-job conflict, target-change race,
authority-change race, replay/no-second-dispatch, audit rollback, readback
failure, execution failure job lifecycle and synchronous success.

## Affected selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_run_admission_contract.py \
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
| Candidate `1a76d7151` | 3.14 | **358** | 3 | 2 | `affected-314.log` |
| Candidate `1a76d7151` | 3.11 | **340** | 0 | 1 | `affected-311.log` |
| #673 base `46dc253a1` | 3.14 | 346 | 3 | 2 | `baseline-673-314.log` |
| #673 base `46dc253a1` | 3.11 | 328 | 0 | 1 | `baseline-673-311.log` |

Candidate delta: **+12 admission controls, zero new failures**.

### Shared baseline failures

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`
  (both versions)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  (3.14 only; the 3.11 environment lacks `schemathesis`)

The 3.11 selection excludes the contract file for that environment reason.

## Job lifecycle evidence

The admission commits the `AgentJob` and receipt before dispatch. The route's
job lifecycle wrapper then:

- marks the job `running` at dispatch start;
- marks it `success`/`failed` at completion;
- restores the agent's prior status only when it is still `running`.

Tests cover synchronous success, stubbed execution failure (job `failed`,
status restored) and background completion (`success`, status restored).

## Notes

- Real scratch SQLite; execution is stubbed; no live model/provider/credential/
  spend/send/download/deployment.
- Logs use `-p no:randomly` for deterministic identity comparison.
