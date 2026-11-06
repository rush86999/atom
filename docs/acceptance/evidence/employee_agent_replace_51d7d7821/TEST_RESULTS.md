# Verified agent PUT replacement — repaired test results

Executed source: `51d7d782198cb279b0d6dcd50dec554b45da135a`  
Base main: `33b8d6472605b7fbb4c84a9e21286c3d168b7d5c`

Every command ran from `backend/` with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Nullable-material probe

```sh
$PY314 -B -m pytest -p no:randomly \
  /private/tmp/test_verifier_replace681_nullable_material.py \
  -q --tb=short
```

| Tree | Result | Log |
|---|---|---|
| Candidate `51d7d7821` | **7 passed** | `nullable-probe-314.log` |
| Base `33b8d6472` | 7 passed (verifier baseline) | external verifier log |

Cases: configuration alone, schedule alone and both; each stored as JSON null
and SQL NULL; empty-object positive. All assert the PUT succeeds, the omitted
nullable material is unchanged, one receipt is written and no scheduler runs.

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
| Python 3.14 | **80 passed** | `focused-314.log` |
| Python 3.11 | **80 passed** | `focused-311.log` |

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
| Candidate `51d7d7821` | 3.14 | **376** | 3 | 2 | `affected-314.log` |
| Candidate `51d7d7821` | 3.11 | **358** | 0 | 1 | `affected-311.log` |
| Main `33b8d6472` | 3.14 | 358 | 3 | 2 | `baseline-main-314.log` |
| Main `33b8d6472` | 3.11 | 340 | 0 | 1 | `baseline-main-311.log` |

Delta: **+18 replacement controls, zero new failures**.

### Shared baseline failures

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`
  (both versions)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  (3.14 only; the 3.11 environment lacks `schemathesis`)

## Original evidence restoration

The original bundle `employee_agent_replace_7503171ec` now tracks the eight
previously ignored `.log`/`.txt` artifacts; its 12 manifest artifact hashes
match Git. The original bytes were retained, not regenerated.

## Notes

- Real scratch SQLite; no live model/provider/credential/spend/send/download/
  deployment.
- Logs use `-p no:randomly` for deterministic identity comparison.
