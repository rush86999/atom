# Verified agent stop/cancel — test results

Executed source: `1faccf71cf00f5a1d421ce67adca3f0f652066d2`  
Source checkpoint: `6d7b453dc8e88813c3a142b1c88dd3c185a4872a`  
Base main: `66e09c5ee9f6693ab3a6e188bd50d03fae62bf39`

Every command ran from `backend/` with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

Each run used a fresh explicit scratch SQLite database and `-p no:randomly`.

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_stop_scope_contract.py \
  tests/test_agent_run_admission_contract.py \
  tests/test_agent_delete_scope_contract.py \
  tests/test_agent_decision_contract.py \
  tests/api/test_agent_routes.py::test_stop_running_agent \
  tests/api/test_agent_routes.py::test_stop_agent_no_tasks \
  tests/api/test_agent_routes.py::test_stop_agent_not_found \
  tests/api/test_agent_routes.py::test_stop_agent_multiple_tasks \
  tests/test_agent_routes_coverage.py::TestAgentStopEndpoint \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **74 passed** | `focused-314.log` |
| Python 3.11 | **74 passed** | `focused-311.log` |

The focused selection contains all 9 stop controls plus the existing run,
delete and decision contracts and the four legacy route/coverage stop tests.

## Affected selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_agent_stop_scope_contract.py \
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

The 3.11 command is identical except that
`tests/contract/test_agent_api_contract.py` is omitted because that interpreter
lacks `schemathesis`.

| Tree | Python | Passed | Skipped | Failed | Log |
|---|---|---|---|---|---|
| Candidate `1faccf71c` | 3.14 | **367** | 3 | 2 | `affected-314.log` |
| Candidate `1faccf71c` | 3.11 | **349** | 0 | 1 | `affected-311.log` |
| Main `66e09c5ee` | 3.14 | 358 | 3 | 2 | `baseline-main-314.log` |
| Main `66e09c5ee` | 3.11 | 340 | 0 | 1 | `baseline-main-311.log` |

Delta: **+9 passed on both interpreters, zero new failures**.

### Shared baseline failures

| Test | 3.14 | 3.11 | Status |
|---|---|---|---|
| `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent` | failed | failed | pre-existing on main |
| `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination` | failed | not collected | pre-existing on main; 3.11 lacks `schemathesis` |

No failure is added by this branch. The earlier candidate run's disk-space
errors were environmental; the reruns above were made with sufficient free
space and produced no `OSError: [Errno 28]`.

## Controls exercised

- current actor/tenant/workspace and `AGENT_RUN` authority;
- exact agent material CAS with `AUTHORITY_CHANGED` and `STALE_TARGET`;
- zero-task no-change with no receipt;
- replay without a second cancellation;
- one AuditLog receipt after a successful cancellation;
- receipt failure after cancellation -> `effect_unknown`;
- missing agent -> 404;
- legacy stop route mocks supply `get_agent_tasks` so cancellation counts are
  actually exercised.

## Notes

- Real scratch SQLite; in-process task-registry fake; no live model, provider,
  credential, spend, send, download or deployment.
- Logs use `-p no:randomly` so candidate/base failure identities are directly
  comparable.
- Shared baseline failures are recorded, not repaired or waived.
