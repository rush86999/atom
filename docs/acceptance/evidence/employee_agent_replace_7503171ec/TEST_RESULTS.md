# Verified full agent replacement — test results

Executed source: `7503171eca9d27915d2911fb2fc0cc961bde9b8b`  
Base main: `33b8d6472605b7fbb4c84a9e21286c3d168b7d5c`

Every command ran from `backend/` with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Confirmed cross-tenant replacement on base main

`cross-tenant-repro-base.log`:

```
PUT /api/agents/foreign-agent
status 200
body {"success":true,"data":{"agent_id":"foreign-agent"},...,"message":"Agent Hijacked replaced successfully"}
foreign_agent_name Hijacked
foreign_agent_category hijacked
```

The caller was a workspace_admin in tenant A; the target belonged to tenant B.

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_replace_scope_contract.py \
  tests/test_agent_decision_contract.py \
  tests/test_agent_delete_scope_contract.py \
  tests/test_agent_run_admission_contract.py \
  tests/api/test_agent_routes.py::test_replace_agent_success \
  tests/api/test_agent_routes.py::test_replace_agent_missing_required_field \
  tests/api/test_agent_routes.py::test_replace_agent_invalid_name \
  tests/api/test_agent_routes.py::test_replace_agent_not_found \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **72 passed** | `focused-314.log` |
| Python 3.11 | **72 passed** | `focused-311.log` |

The new file contributes 10 controls: cross-tenant/cross-workspace refusal,
authorized admin replacement with receipt, stale target, authority change,
replay/changed material, audit rollback, readback failure, matching no-change
and missing target.

## Affected selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_replace_scope_contract.py \
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
| Candidate `7503171ec` | 3.14 | **368** | 3 | 2 | `affected-314.log` |
| Candidate `7503171ec` | 3.11 | **350** | 0 | 1 | `affected-311.log` |
| Main `33b8d6472` | 3.14 | 358 | 3 | 2 | `baseline-main-314.log` |
| Main `33b8d6472` | 3.11 | 340 | 0 | 1 | `baseline-main-311.log` |

Candidate delta: **+10 replacement controls, zero new failures**.

### Shared baseline failures

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`
  (both versions)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  (3.14 only; the 3.11 environment lacks `schemathesis`)

## Scheduler behavior

- Verified replacement with active schedule: scheduler called once.
- Replay: no second scheduler call.
- No-change: no scheduler call.
- Scheduler exception after a verified DB commit is logged; the committed
  replacement is not relabelled as rolled back.

## Notes

- Real scratch SQLite; no live model/provider/credential/spend/send/download/
  deployment.
- Logs use `-p no:randomly` for deterministic identity comparison.
