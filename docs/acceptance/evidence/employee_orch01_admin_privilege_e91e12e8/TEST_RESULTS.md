# ORACLE-01 seven-route admin privilege/budget — test results

Executed source: `e91e12e82cfd13d2d748b0c29e5a51454fa2e5dc`
Accepted auth/2FA base: `95f7bcac1a0375b4f0465a77e15130f68fc9665d`
Runtime: real scratch SQLite with fresh sessions; controlled interleaving/fault
seams. No model/provider/browser operation.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused seven-route gate

```sh
$PY314 -B -m pytest \
  tests/api/test_admin_routes_user_role_crud.py \
  tests/api/test_admin_routes_coverage.py \
  tests/api/test_admin_routes_part1.py \
  tests/test_admin_write_contract.py \
  tests/test_admin_write_contract_matrix.py \
  tests/test_admin_budget_routes.py \
  tests/test_sync_admin_routes.py \
  -q --tb=short
```

Result: **190 passed, 2 skipped** (`focused-314.log`). The same command with
`$PY311` gives **190 passed, 2 skipped** (`focused-311.log`).

## Seven-route failure-first matrix

```sh
$PY314 -B -m pytest tests/test_admin_write_contract_matrix.py -q
```

Result: **33 passed** (`matrix-314.log`; `matrix-311.log` on Python 3.11).

The matrix covers:

- authorized exact create/update/delete/budget twins;
- anonymous / non-super-admin / missing-target refusals with zero effect;
- concurrent duplicate role-name and admin-email creates (one winner, one typed
  conflict);
- role in-use deletion and role delete vs user assignment (no dangling user);
- stale role/user update and actor demotion/disablement before claim;
- budget partial merge, concurrent partial update CAS, non-finite values;
- same-id/same-material replay, changed material, distinct operation and later
  target revision;
- tombstone replay after deletion;
- fresh-session role-permission and budget consumers;
- audit missing/wrong actor/target/material/scope/type and lost confirmation;
- no password hash, token, secret or SQL parameter in receipts/audit/errors.

## Affected admin/auth/permissions/billing/audit selection

```sh
$PY314 -B -m pytest \
  tests/test_budget_control.py \
  tests/test_budget_enforcement_service.py \
  tests/test_personal_budget.py \
  tests/test_round70_budget_alert_notification.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_audit_routes_api.py \
  tests/test_agent_action_audit.py \
  tests/test_integration_audit.py \
  tests/test_execution_insert_path_audit.py \
  tests/test_hitl_approvals_journey.py \
  tests/test_hitl_resume.py \
  tests/test_covpush_w105_workflow_approval_routes.py \
  tests/test_covpush_w104_intervention.py \
  tests/test_covpush_w82_intervention.py \
  tests/api/test_admin_routes_user_role_crud.py \
  tests/api/test_admin_routes_coverage.py \
  tests/api/test_admin_routes_part1.py \
  tests/test_admin_write_contract.py \
  tests/test_admin_write_contract_matrix.py \
  tests/test_admin_budget_routes.py \
  tests/test_sync_admin_routes.py \
  -q --tb=short
```

Result: **400 passed, 3 skipped, 1 failed** (`affected-314.log`). The same
selection on Python 3.11 gives **400 passed, 3 skipped, 1 failed**
(`affected-311.log`).

The retained failure is the known pre-existing:

```text
tests/test_covpush_w104_intervention.py::TestGetPendingInterventions::test_default_workspace_no_filter
```

`base-pre-existing.log` records it on the accepted base without this repair.

## Counts

- Focused seven-route gate: 190 passed, 2 skipped on both versions.
- Seven-route matrix: 33 passed on both versions.
- Affected selection: 400 passed, 3 skipped, 1 known baseline failure on both
  versions.
- Selections overlap; totals are not added together.

## Scope

No model, browser, provider, credential, spend, send, download or deployment
operation was used. PostgreSQL concurrency/soak, multi-worker serialization,
live administrator/account/budget changes and the remaining admin routes remain
outside this slice. Whole-app ORACLE-01 remains open.
