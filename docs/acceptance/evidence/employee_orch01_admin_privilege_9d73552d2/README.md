# ORACLE-01 — seven-route admin privilege/budget material and rollback repair

Status: **submitted for independent verification.** This is the bounded
credential-material and confirmed-rollback repair on the seven admin routes.
The prior seven-route authority, role-assignment, budget-CAS and strict-audit
contracts are retained. Remaining admin routes and whole-app ORACLE-01 remain
open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-admin-privilege-20261105` |
| Accepted auth/2FA base | `95f7bcac1a0375b4f0465a77e15130f68fc9665d` |
| Product source (repair) | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Executed source (product + W79C real-hash test) | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled interleaving/fault seams |
| Model/provider/browser calls | none |

`9d73552d2` changes only the W79C create-user assertion to use a real password
hash; the product files are byte-identical to `5fbb377a4`.

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

## Repair A — credential material is verified and bound

- **Initial proof:** `create_admin_user` verifies the actual generated
  `password_hash` against the authorized password with the existing
  `core.auth.verify_password` primitive **before** writing. A hasher that
  returns a syntactically valid hash for different credential material is a
  safe pre-effect `CREDENTIAL_MISMATCH` refusal (422); no user, audit or
  receipt is written.
- **Private verifier material:** the verifier's postcondition uses
  id/email/name/role/status plus a keyed, non-reversible
  `credential_commitment` over the exact stored hash. The public
  `AdminUserResponse` projection intentionally omits it.
- **Creation result commitment:** the private result digest includes the
  credential commitment. After commit, a fresh-session read must still match
  that digest and `verify_password` must still accept the authorized password;
  otherwise the response is honest `committed_unverified`, never verified.
- **Replay:** replay reconciles the original audit result digest against the
  current private state. A later credential reset, malformed hash or deleted
  user makes replay `committed_unverified` 503 and never overwrites the reset,
  generates a fresh salted hash, or creates a second user. Unchanged replay is
  idempotent `already_applied` with one user and one audit.
- **Update/delete:** user update/delete CAS binds the current credential hash
  (and not an unrelated `last_login`), so a concurrent credential change
  refuses before effect or is honestly refuted after a later change. The
  delete postcondition remains absence; a credential reset before delete
  refuses and preserves the reset.
- **No leakage:** raw passwords, password hashes, tokens, secrets and SQL
  parameters are absent from public responses, audit metadata, receipts and
  captured logs. The commitment is inside a keyed digest, not stored raw.

## Repair B — confirmed rollback reports effect=none

- A commit-time `IntegrityError` after the target was flushed, with no existing
  operation, rolls back the target and audit together. The shared commit helper
  returns typed `not_applied` (HTTP 409) with `verification.effect="none"`,
  `verification.status="refused"`, and a safe `ADMIN_TRANSACTION_ROLLED_BACK`
  code. It does not say the mutation committed.
- Branch separation is preserved:
  - an existing duplicate operation still reconciles its original receipt;
  - an audit/target readback unavailable **after** a successful commit remains
    `committed_unverified` with `effect="committed"`;
  - a genuinely lost commit confirmation remains `effect_unknown` with the
    original operation identity, `do_not_repeat`, and no exception SQL or
    parameters.
- The helper is shared by all seven routes. The role, user and budget rollback
  twins verify that target and audit rows are both absent (or the prior budget
  setting is unchanged) and the response is `effect=none`.

## Retained contracts

- Actor id/role/status/active flag is frozen and claimed in the same
  transaction as the target write; concurrent demotion/disablement/deletion
  refuses with zero effect.
- Role/user material CAS; database unique arbiters for role name and email;
  role-existence predicate in admin-user insert; role delete `NOT EXISTS` plus
  FK and assigned-user readback; budget exact-value CAS with partial merge and
  unseen-field preservation.
- `AuditLog` remains the existing durable receipt/audit ledger. No new table,
  parallel credential engine or schema migration was added.
- Response compatibility: create 201, update/delete 200, refusals
  403/404/409/422, uncertainty 503, with additive
  `verification`/`operation_id`/`audit_id` metadata.

## Controls

- **Focused seven-route gate: 204 passed, 2 skipped on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`). This keeps the original focused gate
  green and adds the expanded matrix and credential/result-state controls.
- **External failure-first probes: 4 passed on both versions**
  (`probes-314.log`, `probes-311.log`; 3.11 uses `-p no:randomly` for the
  external-path pytest-randomly/thinc seed issue).
- **Credential/result-state matrix: 11 passed on both versions**
  (`credential-matrix-314.log`, `credential-matrix-311.log`).
- **W79C admin CRUD controls: 23 passed on both versions**
  (`w79c-admin-314.log`, `w79c-admin-311.log`).
- **Affected admin/auth/permissions/billing/audit selection: 1176 passed,
  3 skipped on 3.14** (`affected-314.log`); **1175 passed, 3 skipped, 1 known
  timing flake on 3.11** (`affected-311.log`), with the flake passing in
  isolation (`integration-audit-311-isolated.log`).

The narrow matrix covers: wrong stored hash cannot certify; valid credential
verifies in a fresh session; changed, malformed and deleted credential replay
cannot silently earn `already_applied`; unchanged replay is idempotent with one
user/audit; confirmed role/user/budget rollback reports effect=none; post-commit
readback failure remains committed_unverified; lost confirmation remains
effect_unknown with identity; duplicate target conflict is truthful.

## Baseline exclusions

- 52 unrelated pre-existing controls on `95f7bcac1`: 31
  `test_covpush_w75b_admin.py` cache/health/skill, 9
  `test_workspace_permissions.py`, 9 `test_directory_permissions.py`, 3
  `test_phase21_rbac.py` (`baseline-exclusions-52.log`).
- The full `test_covpush_w79c_api_routes.py` retains 38 pre-existing
  workflow-template failures (`w79c-pre-existing-314.log`); the admin CRUD
  classes are selected separately and pass 23/23.
- `test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error`
  is a millisecond-clock timing flake; it passes in isolation on 3.11 and the
  3.14 affected selection is fully green.
- The 2FA-lane `test_covpush_w104_intervention.py` baseline failure remains
  disclosed in `base-pre-existing.log`; the 2FA lane is closed and was not
  replayed.

## Boundaries

- No live administrator/account/budget change, provider, credential, spend,
  send, download or deployment operation was used.
- No second authorization, approval, audit, credential or operation engine;
  the slice uses the existing `AuditLog`, `AdminRole`, `AdminUser`,
  `TenantSetting`, `User`, `verify_password` and `require_super_admin` /
  `get_platform_admin` mechanisms.
- No new confirmation prompt for already-authorized administration.
- PostgreSQL runtime/soak, multi-worker serialization, live
  administrator/account/budget changes and the remaining admin routes are not
  qualified.
- Accepted canvas/auth-2FA/ORCH-01/feedback/wait/employee lanes and historical
  model scores remain closed and unchanged.
- Whole-app ORACLE-01 remains open.

## Artifacts

`focused-*.log`, `probes-*.log`, `credential-matrix-*.log`,
`w79c-admin-*.log`, `affected-*.log`, `baseline-exclusions-52.log`,
`w79c-pre-existing-314.log`, `base-pre-existing.log`,
`integration-audit-311-isolated.log`, `source-tree.txt`, `README.md`,
`TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
