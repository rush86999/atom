# ORACLE-01 seven-route admin privilege/budget — test results

Executed source: `e4590b26a0e0cbdacbccd032f7b77104296309df`  
Product source: `e91e12e82cfd13d2d748b0c29e5a51454fa2e5dc`  
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

## Focused core

```sh
$PY314 -B -m pytest \
  tests/test_admin_write_contract.py \
  tests/test_admin_write_contract_matrix.py \
  tests/test_admin_budget_routes.py \
  tests/api/test_admin_routes_user_role_crud.py \
  tests/api/test_admin_routes_part1.py \
  tests/api/test_admin_routes_coverage.py \
  -q --tb=short
```

Result: **193 passed, 1 skipped** (`focused-314.log`). The same command with
`$PY311` gives **193 passed, 1 skipped** (`focused-311.log`).

This is the 10-test base contract, the 36-test failure-first matrix, and the
147 existing admin CRUD/coverage controls.

## W79C admin CRUD controls

```sh
$PY314 -B -m pytest tests/test_covpush_w79c_api_routes.py \
  -k "AdminUsers or AdminRoles" -q --tb=short
```

Result: **23 passed, 199 deselected** (`w79c-admin-314.log`). The same command
with `$PY311` gives **23 passed, 199 deselected** (`w79c-admin-311.log`).

The W79C admin classes now use a real scratch DB actor and exercise the shared
verified-write service; the rest of the W79C file is outside this slice.

## Failure-first matrix

```sh
$PY314 -B -m pytest tests/test_admin_write_contract_matrix.py -q
```

Result: **36 passed** (`matrix-314.log`; `matrix-311.log` on Python 3.11).
This is a subset of the focused core and is not added to the total.

## Base contract

```sh
$PY314 -B -m pytest tests/test_admin_write_contract.py -q
```

Result: **10 passed** (`base-contract-314.log`; `base-contract-311.log` on
Python 3.11).

## Affected admin/auth/permissions/billing/audit selection

```sh
$PY314 -B -m pytest \
  tests/api/test_admin_routes.py \
  tests/api/test_admin_routes_coverage.py \
  tests/api/test_admin_routes_coverage_extend.py \
  tests/api/test_admin_routes_part1.py \
  tests/api/test_admin_routes_part2.py \
  tests/api/test_admin_routes_user_role_crud.py \
  tests/test_admin_write_contract.py \
  tests/test_admin_write_contract_matrix.py \
  tests/test_admin_budget_routes.py \
  tests/test_decision_admin_routes.py \
  tests/test_sync_admin_routes.py \
  tests/core/test_rbac_service.py \
  tests/security/test_authorization.py \
  tests/security/test_authorization_maturity.py \
  tests/test_covpush_w103_rbac.py \
  tests/test_role_journey_rbac_gaps.py \
  tests/test_workflow_rbac_matrix.py \
  tests/test_budget_enforcement_service.py \
  tests/test_covpush_w47_budget_service.py \
  tests/test_budget_control.py \
  tests/test_covpush_w104_spend_aggregation.py \
  tests/test_personal_budget.py \
  tests/test_r80_budget_guardrail.py \
  tests/test_prompt_budget_accounting.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_audit_routes_api.py \
  tests/test_agent_action_audit.py \
  tests/test_execution_insert_path_audit.py \
  tests/test_integration_audit.py \
  tests/test_auth_fixes.py \
  tests/test_auth_bypass_bugs.py \
  tests/test_auth_bypass_fixes.py \
  tests/test_bughunt_auth.py \
  tests/test_auth_helpers.py \
  tests/test_auth_routes_coverage.py \
  -q --tb=short
```

Result: **1165 passed, 3 skipped** on Python 3.14 (`affected-314.log`). The
same selection on Python 3.11 gives **1165 passed, 3 skipped**
(`affected-311.log`).

## Counts

- Focused core: 193 passed, 1 skipped on both versions.
- W79C admin CRUD: 23 passed on both versions.
- Combined focused coverage: 216 passed, 1 skipped (overlap removed).
- Matrix: 36 passed on both versions (subset of focused).
- Affected selection: 1165 passed, 3 skipped on both versions.
- Selections overlap; totals are not added together.

## Baseline exclusions

The exact baseline reproduction is `baseline-exclusions-52.log` on the accepted
auth/2FA base `95f7bcac1`:

- `tests/test_covpush_w75b_admin.py` — 31 cache/health/skill controls.
- `tests/test_workspace_permissions.py` — 9 controls.
- `tests/test_directory_permissions.py` — 9 controls.
- `tests/test_phase21_rbac.py` — 3 controls.

These are unrelated to the seven admin mutation routes and reproduce without
this slice. The full W79C file also retains 38 pre-existing workflow-template
failures (`w79c-pre-existing-314.log`); the admin CRUD classes are selected
separately and pass.

`test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error`
is a millisecond-clock timing flake; it passes in isolation on both versions
(`integration-audit-314.log`, `integration-audit-311.log`) and the final
affected selection passes. The 2FA-lane `test_covpush_w104_intervention.py`
baseline failure remains disclosed in `base-pre-existing.log`; the 2FA lane is
closed and was not replayed.

## Coverage matrix

The focused real controls cover:

- authorized exact role/user/budget create, update and delete twins;
- anonymous, non-super-admin, member-budget and missing-target refusals with
  zero effect;
- concurrent duplicate role-name and admin-email creates (one winner);
- role in-use deletion and role delete vs user assignment under FK enforcement
  (no dangling assignment);
- stale role/user update and role-delete versus competing target change;
- actor demotion and disable/suspend before the claim;
- concurrent budget limit/mode partial updates and unseen override preservation;
- same operation id/same material acknowledgement, changed material conflict,
  distinct operation, later target revision refusal and tombstone replay;
- fresh-session role-permission and budget consumers;
- audit missing/wrong operation/actor/target/material/scope/type/security and
  lost confirmation;
- non-finite/negative/unsupported budget values rejected without a 500;
- user update/delete versus concurrent last-login writer;
- no password hash, token, secret or SQL parameter in audit/receipts/responses/
  captured logs.

## Scope

No live administrator/account/budget change, model, browser, provider,
credential, spend, send, download or deployment operation was used. PostgreSQL
runtime/soak, multi-worker serialization, live administrator/account/budget
changes and the remaining admin routes remain outside this slice. Whole-app
ORACLE-01 remains open.
