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
| Executed source | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled interleaving/fault seams |
| Model/provider/browser calls | none |

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

## Contract

### Authority and target claim

- The service freezes the acting administrator's id, role, status and active
  flag. A conditional no-op update on the `User` row must still match before
  any target mutation; a concurrent demotion, disablement or deletion matches
  zero rows and refuses with zero effect.
- Role/user targets use material CAS predicates: current name, permissions,
  description, email, role, status and last-login fields must still match.
- Role/user create uses the database unique constraints as the arbiter for
  duplicate role names and admin emails. Conflicts map to typed 409 responses.
- Admin-user create also embeds a role-existence `EXISTS` predicate in the
  INSERT, so a concurrent role deletion cannot leave a dangling assignment.
- Role delete performs a conditional delete with a `NOT EXISTS` assigned-user
  predicate and an in-transaction in-use count. A concurrent assignment either
  wins before the delete (delete refuses) or loses the role-existence insert
  (assignment refuses); no dangling user is produced.
- Budget update performs an exact `TenantSetting.setting_value` CAS. Partial
  updates merge only the supplied fields; a concurrent limit/mode change
  matches zero rows and the loser gets a typed 409. Non-finite, negative or
  unsupported values are refused before mutation.

### Credential proof and rollback result states

- Admin-user creation verifies the **actual stored credential** against the
  authorized password before writing. A syntactically valid hash for different
  credential material is a safe pre-effect refusal; a committed mismatch is
  `committed_unverified`, never verified.
- The private result commitment includes a keyed, non-reversible fingerprint of
  the exact stored password hash. Replay uses the original receipt's result
  digest and never generates a fresh salted hash. A later credential reset,
  malformed credential or deleted user makes replay `committed_unverified` and
  never overwrites the reset or creates a second user. Public views omit all
  credential material.
- User update/delete material CAS binds the current credential hash (not an
  unrelated last-login timestamp), so a concurrent credential change refuses
  rather than silently applying.
- A commit-time `IntegrityError` with no original operation is a confirmed
  local rollback: typed `not_applied`, HTTP 409, `verification.effect=none`,
  target and audit absent. It is not `committed_unverified`. Existing duplicate
  operations still reconcile their original receipt; post-commit readback
  failure remains `committed_unverified`; lost confirmation remains
  `effect_unknown`.

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

### Durable ledger and migration

The existing `AuditLog` table is the operation receipt and audit ledger. No new
table, parallel approval engine or schema migration was added, so no
pre-migration upgrade is required for this slice.

## Controls

- **Focused seven-route gate: 204 passed, 2 skipped on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`).
- **External failure-first probes: 4 passed on both versions**
  (`probes-314.log`, `probes-311.log`).
- **Credential/result-state matrix: 11 passed on both versions**
  (`credential-matrix-314.log`, `credential-matrix-311.log`).
- **Affected admin/auth/permissions/billing/audit selection: 414 passed, 3
  skipped, 1 known pre-existing failure on both versions**
  (`affected-314.log`, `affected-311.log`).

The focused gate covers the existing CRUD/coverage controls plus the new
positive/negative/concurrency matrix: authorized exact twins; anonymous /
non-super-admin / missing-target refusals; duplicate role/email create races;
role in-use and role-delete vs assignment; stale role/user updates; actor
demotion/disablement; budget partial merge and stale CAS; same-id replay and
changed material; later target revision; tombstone replay; fresh-session
permission and budget consumers; audit omission/type/mismatch; non-finite
budget values; lost confirmation and sensitive-error assertions.

## Baseline exclusions

- `tests/test_covpush_w104_intervention.py::TestGetPendingInterventions::test_default_workspace_no_filter`
  fails on the accepted auth/2FA base without this repair; it is the retained
  known baseline failure (`base-pre-existing.log`).
- The unrelated W75B admin skill/cache/health modules have pre-existing 401
  fixture failures and are outside this seven-route slice; they are not in the
  affected selection.
- PostgreSQL runtime/soak, multi-worker serialization, live administrator
  accounts, live budget/spend changes and the remaining admin routes are not
  qualified.

## Boundaries

- No live administrator/account/budget change, provider, credential, spend,
  send, download or deployment operation was used.
- No second authorization, approval, audit or operation engine; the slice uses
  the existing `AuditLog`, `AdminRole`, `AdminUser`, `TenantSetting`, `User`
  and `require_super_admin` / `get_platform_admin` mechanisms.
- No new confirmation prompt for already-authorized administration.
- Accepted canvas/auth-2FA/ORCH-01/feedback/wait/employee lanes and historical
  model scores remain closed and unchanged.

## Artifacts

`focused-*.log`, `probes-*.log`, `credential-matrix-*.log`, `affected-*.log`,
`base-pre-existing.log`, `README.md`, `TEST_RESULTS.md`, `verification.json`,
`routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and changed source file.
