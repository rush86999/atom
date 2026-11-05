# ORACLE-01 seven-route admin privilege/budget — credential/rollback results

Executed source: `9d73552d249ae8ec5b05af77546faf9621bbcd47`  
Product source: `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41`  
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

## External failure-first probes

```sh
$PY314 -B -m pytest /private/tmp/test_verifier_admin_e91e_material.py -q
$PY311 -B -m pytest /private/tmp/test_verifier_admin_e91e_material.py \
  -p no:randomly -q
```

Result: **4 passed** on both versions (`probes-314.log`, `probes-311.log`).
The three negatives are wrong stored password, replay after a changed
credential, and atomic audit rollback effect; the fourth is the valid
credential/replay twin.

## Credential/result-state matrix

```sh
$PY314 -B -m pytest tests/test_admin_credential_result_state.py -q
$PY311 -B -m pytest tests/test_admin_credential_result_state.py -q
```

Result: **11 passed** on both versions (`credential-matrix-314.log`,
`credential-matrix-311.log`).

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
  tests/test_admin_credential_result_state.py \
  -q --tb=short
```

Result: **204 passed, 2 skipped** (`focused-314.log`). The same command with
`$PY311` gives **204 passed, 2 skipped** (`focused-311.log`). This keeps the
original focused gate green and adds the expanded matrix and credential
controls.

## W79C admin CRUD controls

```sh
$PY314 -B -m pytest tests/test_covpush_w79c_api_routes.py \
  -k "AdminUsers or AdminRoles" -q --tb=short
```

Result: **23 passed, 199 deselected** (`w79c-admin-314.log`; the same command
with `$PY311` gives `w79c-admin-311.log`). The W79C create-user test now uses a
real password hash and verifies it, rather than the old non-credential
`hashed!` sentinel.

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
  tests/test_admin_credential_result_state.py \
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

Result: **1176 passed, 3 skipped** on Python 3.14 (`affected-314.log`). The
same selection on Python 3.11 gives **1175 passed, 3 skipped, 1 known timing
flake** (`affected-311.log`):

```text
tests/test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error
```

The flake passes in isolation on 3.11 (`integration-audit-311-isolated.log`);
the 3.14 affected selection is fully green.

## Counts

- External probes: 4 passed on both versions.
- Credential/result-state matrix: 11 passed on both versions.
- Focused seven-route gate: 204 passed, 2 skipped on both versions.
- W79C admin CRUD: 23 passed on both versions.
- Affected selection: 1176 passed, 3 skipped on 3.14; 1175 passed, 3 skipped,
  1 known timing flake on 3.11.
- Selections overlap; totals are not added together.

## Baseline exclusions

The exact baseline reproduction is `baseline-exclusions-52.log` on `95f7bcac1`:
31 `test_covpush_w75b_admin.py`, 9 `test_workspace_permissions.py`, 9
`test_directory_permissions.py`, 3 `test_phase21_rbac.py`. These are unrelated
to the seven admin mutation routes. The full W79C file also retains 38
pre-existing workflow-template failures (`w79c-pre-existing-314.log`); the
admin CRUD classes pass 23/23. The 2FA-lane
`test_covpush_w104_intervention.py` baseline failure remains disclosed in
`base-pre-existing.log`; the 2FA lane is closed and was not replayed.

## Coverage matrix

- Wrong hasher returns a syntactically valid hash for different credential
  material: pre-effect refusal, no user.
- Valid requested password verifies in a fresh session; replay is idempotent
  with one user and one audit.
- Changed, malformed and deleted credential after original commit: replay 503,
  no overwrite, no second user.
- Confirmed audit constraint rollback: role, user and budget targets and audit
  rows absent/unchanged, HTTP 409, `verification.effect=none`.
- Post-commit audit readback failure: 503 `committed_unverified` with
  `effect=committed` and identity.
- Lost confirmation: 503 `effect_unknown` with original operation identity,
  `do_not_repeat`, and no secret/SQL in response or captured logs.
- Duplicate target conflict: truthful 409 with no receipt.
- Retained authority, role-assignment, budget-CAS, strict-audit and
  response-compatibility controls.

## Scope

No live administrator/account/budget change, model, browser, provider,
credential, spend, send, download or deployment operation was used. PostgreSQL
runtime/soak, multi-worker serialization, live administrator/account/budget
changes and the remaining admin routes remain outside this slice. Whole-app
ORACLE-01 remains open.
