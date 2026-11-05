# ORACLE-01 — seven-route admin privilege and tenant-budget verified writes

Status: **submitted for independent verification.** This is the bounded
successor to the accepted five-route auth/2FA slice. It covers exactly the
seven admin routes below. The remaining admin routes and whole-app ORACLE-01
remain open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-admin-privilege-20261105` |
| Accepted auth/2FA base | `95f7bcac1a0375b4f0465a77e15130f68fc9665d` |
| Product source | `e91e12e82cfd13d2d748b0c29e5a51454fa2e5dc` |
| Executed source (product + expanded tests) | `e4590b26a0e0cbdacbccd032f7b77104296309df` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled interleaving/fault seams |
| Model/provider/browser calls | none |

The administrative source is `e91e12e82`; `e4590b26a` adds the expanded
regression suite only (no product-file change).

## Scope

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/admin/roles` | `create_admin_role` | `core.admin_write_service.create_admin_role` |
| PATCH | `/api/admin/roles/{role_id}` | `update_admin_role` | `core.admin_write_service.update_admin_role` |
| DELETE | `/api/admin/roles/{role_id}` | `delete_admin_role` | `core.admin_write_service.delete_admin_role` |
| POST | `/api/admin/users` | `create_admin_user` | `core.admin_write_service.create_admin_user` |
| PATCH | `/api/admin/users/{admin_id}` | `update_admin_user` | `core.admin_write_service.update_admin_user` |
| DELETE | `/api/admin/users/{admin_id}` | `delete_admin_user` | `core.admin_write_service.delete_admin_user` |
| PUT | `/api/admin/tenants/{tenant_id}/budget` | `update_tenant_budget` | `core.admin_write_service.update_tenant_budget` |

`AdminRole` and `AdminUser` remain global platform rows. Tenant billing remains
tenant-scoped through `TenantSetting(tenant_id, setting_key="billing")`.
Authorization remains the existing `require_super_admin` /
`get_platform_admin` policy; no tenant/workspace ownership is inferred from
request content.

## Caller / consumer map

- **Role/user routes** use `api.admin_routes.require_super_admin` (exact
  `super_admin`). `AdminUser.role_id` is the only role assignment FK;
  `AdminRole.permissions` is consumed by the admin role responses, not by a
  separate in-process permission cache. The existing RBAC cache is for
  `UserRole` permissions, which these routes do not mutate. A fresh-session
  role read/route GET therefore observes the committed permissions.
- **Budget route** uses `core.admin_endpoints.get_platform_admin`
  (`workspace_admin` and above). The billing setting is consumed by
  `BudgetEnforcementService._get_enforcement_mode`,
  `SpendAggregationService._budget_limit_from_setting`, and the budget GET/PUT
  routes. The same `TenantSetting['billing']` document is also written by
  `BudgetEnforcementService._set_budget_override`; the exact-value CAS prevents
  this update from overwriting an unseen override or mode.
- **Parallel writers** traced: `update_admin_last_login` (admin user
  `last_login`), role/user create/update/delete, budget override, and the
  generic `TenantSetting` writers for other keys. User update/delete material
  excludes `last_login` so a concurrent login update is preserved rather than
  lost; role deletion uses the assigned-user `NOT EXISTS` predicate plus the
  real FK. The budget CAS binds the exact current billing document.

## Contract

### Authority and target claim

- The service freezes the acting administrator's id, role, status and active
  flag. A read-only current-authority gate rejects an already demoted or
  disabled actor; a conditional no-op update on the `User` row must still match
  before any target mutation. A concurrent demotion, disablement or deletion
  matches zero rows and refuses with zero effect.
- Role/user targets use material CAS predicates: current name, permissions,
  description, email, role and status must still match. `last_login` is
  intentionally excluded from the user material so a concurrent login writer
  is preserved.
- Role/user create uses the database unique constraints as the arbiter for
  duplicate role names and admin emails. Conflicts map to typed 409 responses.
- Admin-user create embeds a role-existence `EXISTS` predicate in the INSERT,
  so a concurrent role deletion cannot leave a dangling assignment.
- Role delete performs a conditional delete with a `NOT EXISTS` assigned-user
  predicate and an in-transaction in-use count. A concurrent assignment either
  wins before the delete (delete refuses) or loses the role-existence insert
  (assignment refuses); no dangling user is produced. The readback also checks
  for assigned users.
- Budget update performs an exact `TenantSetting.setting_value` CAS. Partial
  updates merge only the supplied fields and preserve unseen keys such as
  `enforcement.override`. A concurrent limit/mode change matches zero rows and
  the loser gets a typed 409. Non-finite, negative or unsupported values are
  refused before mutation; a non-finite body is rejected without echoing the
  value in a 500 error.

### Operation receipt, replay and audit readback

- Every accepted mutation writes one `AuditLog` row in the **same transaction**
  as the target change. The row id is the server-owned operation id (a supplied
  id is prefixed deterministically; otherwise a fresh id is generated).
- The receipt metadata binds operation kind, actor id/role, platform or tenant
  scope, target type/id, request material digest and result digest. No password
  hash, token, secret or SQL parameter is stored.
- The service independently reads the audit row and target from a fresh session
  on the same engine. Receipt existence is not success: the target must still
  match the result digest (or be absent for a delete).
- Same operation id and same material: `already_applied` acknowledgement of the
  original operation, with no second effect. Same id with different material:
  typed 409 conflict. A later target revision: `committed_unverified` 503 with
  the original identity and `do_not_repeat`. Lost confirmation:
  `effect_unknown` 503 with the original identity and no raw exception text.
- Audit missing/refuted/wrong-scope/wrong-actor/wrong-material remains an
  honest uncertain outcome. The route exposes additive `verification`,
  `operation_id` and `audit_id` metadata; ordinary success/error shapes remain
  compatible.
- The seven-route response shapes preserve the existing status codes and
  fields. Create remains 201; update/delete remain 200; refusals remain
  403/404/409/422; uncertain outcomes are 503.

### Durable ledger and migration

The existing `AuditLog` (`saas_audit_logs`) table is the operation receipt and
audit ledger. No new table, parallel approval engine or schema migration was
added, so no pre-migration upgrade is required for this slice. The ledger's
primary key supplies same-operation arbitration; the metadata digests bind the
request and result.

## Controls

- **Focused core: 193 passed, 1 skipped on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`). This is the 10-test base contract,
  the 36-test failure-first matrix, and the 147 existing admin CRUD/coverage
  controls.
- **W79C admin CRUD controls: 23 passed on both versions**
  (`w79c-admin-314.log`, `w79c-admin-311.log`), now backed by a real scratch DB
  actor instead of a mock session.
- **Combined focused coverage: 216 passed, 1 skipped** (overlap removed).
- **Seven-route failure-first matrix: 36 passed on both versions**
  (`matrix-314.log`, `matrix-311.log`; a subset of the focused core).
- **Affected admin/auth/permissions/billing/audit selection: 1165 passed,
  3 skipped on both versions** (`affected-314.log`, `affected-311.log`).
- The matrix covers authorized exact twins; anonymous / non-super-admin /
  missing-target refusals; concurrent duplicate role-name and admin-email
  creates; role in-use and role-delete vs user assignment under FK
  enforcement; stale role/user updates; actor demotion and disablement; budget
  partial merge, unseen override preservation, concurrent partial update CAS
  and non-finite values; same-id replay, changed material and later target
  revision; tombstone replay; fresh-session role-permission and budget
  consumers; audit omission/type/actor/target/material/scope mismatch; lost
  confirmation; password-material non-leakage; and concurrent last-login
  preservation.

## Baseline exclusions

The following are pre-existing on the accepted auth/2FA base `95f7bcac1` and
are not caused by this slice:

- 52 unrelated model/physics controls: 31 `test_covpush_w75b_admin.py`
  cache/health/skill controls, 9 `test_workspace_permissions.py`, 9
  `test_directory_permissions.py`, and 3 `test_phase21_rbac.py`. The exact
  baseline reproduction is `baseline-exclusions-52.log`.
- The full `test_covpush_w79c_api_routes.py` file retains 38 pre-existing
  workflow-template failures on both baseline and repaired source
  (`w79c-pre-existing-314.log`). The admin CRUD classes are selected separately
  and pass (23/23).
- `test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error`
  is a millisecond-clock timing flake. It passes in isolation on both versions
  (`integration-audit-314.log`, `integration-audit-311.log`); the final
  affected selection passes on both versions.
- The 2FA-lane `test_covpush_w104_intervention.py` baseline failure remains
  disclosed in `base-pre-existing.log`; the 2FA lane is closed and was not
  replayed.

## Boundaries

- No live administrator/account/budget change, provider, credential, spend,
  send, download or deployment operation was used.
- No second authorization, approval, audit or operation engine; the slice uses
  the existing `AuditLog`, `AdminRole`, `AdminUser`, `TenantSetting`, `User` and
  `require_super_admin` / `get_platform_admin` mechanisms.
- No new confirmation prompt for already-authorized administration.
- PostgreSQL runtime/soak, multi-worker serialization, live
  administrator/account/budget changes and the remaining admin routes are not
  qualified.
- Accepted canvas/auth-2FA/ORCH-01/feedback/wait/employee lanes and historical
  model scores remain closed and unchanged.
- Whole-app ORACLE-01 remains open.

## Artifacts

`focused-*.log`, `base-contract-*.log`, `matrix-*.log`, `w79c-admin-*.log`,
`affected-*.log`, `baseline-exclusions-52.log`, `w79c-pre-existing-314.log`,
`base-pre-existing.log`, `integration-audit-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
