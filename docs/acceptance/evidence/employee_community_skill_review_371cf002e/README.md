# ORACLE-01 — verified community-skill promote and delete

Status: **submitted for independent verification.** This is the bounded
successor to the submitted scoped-memory family and the accepted admin repair.
It covers exactly the two community-skill review mutations below. Import,
execute, package installation, sandbox execution, marketplace and the remaining
skill surfaces remain open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-community-skill-20261105` |
| Accepted admin test successor (base) | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product (runtime) | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `acfee403b` |
| Executed source (product + tests) | `371cf002e` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled interleaving/fault seams |
| Model/provider/sandbox/package calls | none |

The unaccepted memory source and the submitted tool-mutation review branch are
independent and are not merged here.

## Scope

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/skills/promote` | `promote_skill` | `core.community_skill_write_service.promote_skill` |
| DELETE | `/api/skills/{skill_id}` | `delete_skill` | `core.community_skill_write_service.delete_skill` |

The community registry stores imported skills as `SkillExecution` rows with
`skill_source="community"`, `tenant_id="system"`, `workspace_id="default"` and
`agent_id="system"`. This is a platform-global registry, not a tenant-scoped
end-user store. Import and execute are out of scope; execute can run community
code and is not exercised here.

## User outcome

A team lead or higher can promote an imported community skill from `Untrusted`
to `Active`, or delete it, with an exact binding to the skill material the
reviewer saw. A concurrent promote/delete or changed material refuses with zero
effect; a repeated operation is idempotent; every accepted effect writes one
safe `AuditLog` receipt in the same transaction; the target and receipt are read
back from a fresh session. No raw skill body, package list, code, secret or SQL
parameter is stored in the receipt or logged.

## Authority and scope

- The routes require `get_current_user` plus the existing TEAM_LEAD+ role
  hierarchy (`core.security.rbac.user_meets_role`). The role is loaded from the
  database user row, not a request field. A member/viewer is refused 403.
- The registry row is platform-global (`tenant_id="system"`,
  `workspace_id="default"`). No tenant/workspace is inferred from request
  content; a team lead from any tenant reviews the same platform registry.
- Target lookup is exact: `SkillExecution.id == skill_id` AND
  `skill_source == "community"`. Cloud/marketplace rows are never touched.
- The review material is the full community row the reviewer saw: `status`,
  `input_params` (skill name/type/metadata/body/packages),
  `security_scan_result`, `sandbox_enabled`, `agent_id`, `tenant_id`,
  `workspace_id` and `skill_id`. A keyed material digest binds the row; the raw
  body/packages/code never enter the receipt.

## Exact effect contract

### Promote

- `Untrusted` -> `Active` only when the exact prior material is unchanged. The
  conditional UPDATE binds `id`, `skill_source`, `status`, `input_params`,
  `security_scan_result` and `sandbox_enabled`.
- `Active` already -> `already_applied`, `effect=none`, no new audit row for a
  new operation id.
- Missing/non-community/cloud target -> 404 with zero effect.
- Concurrent promote or delete, or changed material -> typed 409
  `STALE_COMMUNITY_SKILL`, `effect=none`; the peer state is preserved.
- Same operation id + same skill -> `already_applied`; same id with a different
  skill -> typed 409 `OPERATION_CONFLICT`.
- A later material revision after the original operation -> 503
  `committed_unverified`, original identity, `do_not_repeat`.

### Delete

- Conditional delete binds the exact current community row material.
- Missing/non-community/cloud -> 404 with zero effect.
- Same-operation tombstone replay -> `already_applied`.
- Concurrent delete/promote or changed material -> typed 409; the peer row is
  preserved.
- A later re-import with the same id cannot be mistaken for the deleted row;
  replay remains bound to the original receipt material.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction as the
`SkillExecution` update/delete. The audit row id is the server-owned operation
id (`community-skill:promote|delete:<supplied-or-generated>`). Metadata contains
the operation id, action, event type, platform scope, target digest, skill
material digest, prior/result digests and actor id/role. The audit row itself
is platform-scoped (`tenant_id=None`, `workspace_id=None`). No raw skill body,
package name/list, code, secret or SQL parameter.

- `verified` (200-compatible success shape): target and audit readback match.
- `already_applied` (success shape): same operation id and material; no second
  effect.
- `conflict` (409): changed operation material, stale prior material,
  competing promote/delete or target mismatch; `effect=none`.
- `not_applied` (409): confirmed local rollback from a constraint failure with
  no original operation; `verification.effect="none"`.
- `committed_unverified` (503): post-commit audit/target readback failed or was
  refuted; `effect=committed`, original identity, `do_not_repeat`.
- `effect_unknown` (503): lost commit confirmation; `effect=unknown`, original
  identity, `do_not_repeat`, no exception text.

## Caller / consumer / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `POST /api/skills/promote` | verified exact-material promote |
| `DELETE /api/skills/{skill_id}` | verified exact-material tombstone delete |
| `SkillRegistryService.import_skill/execute_skill` | unchanged; no live-code surface added |
| `core.reviewed_improvement` apply path | continues to use `SkillRegistryService.promote_skill(commit=False)` inside its own accepted transaction; it is not the community review route |
| `SkillRetrievalService` / graduation | read community rows; promoted rows remain visible, deleted rows stay deleted |
| `AuditLog` consumers | additive safe receipt |

## Controls

- **Focused community-skill gate: 126 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): 21 new failure-first controls plus
  the affected route/registry tests.
- **Affected skill/registry/reviewed-improvement/audit selection: 252 passed
  on both versions** (`affected-314.log`, `affected-311.log`).
- **Unrelated marketplace/package baseline: 4 failed, 4 passed at the accepted
  admin base `9d73552d2`** (`baseline-round22-9d73552d2.log`). The same 4
  failures are present with the slice; they are package/marketplace auth
  controls, not the two reviewed routes.

The new matrix covers anonymous/member refusal, team-lead and cross-tenant
platform authority, promote/delete success, already-active no-op, same-operation
replay, changed skill conflict, later revision `committed_unverified`, stale
promote/delete, cloud-row refusal, audit rollback `effect=none`, post-commit
readback `committed_unverified`, lost confirmation `effect_unknown`, 10
audit-tamper variants and raw-body/package/name omission.

## Boundaries

- No import, execute, sandbox, Docker, package install, live-code execution or
  provider call.
- No new table, migration or second skill registry/approval engine; the existing
  `SkillExecution` and `AuditLog` are reused.
- No change to memory/admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 or
  the submitted tool-mutation review branch.
- No PostgreSQL runtime/soak, multi-worker serialization or live multi-model
  qualification.
- No model/provider/credential/spend/send/download/deployment authority.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-round22-9d73552d2.log`,
`source-tree.txt`, `README.md`, `TEST_RESULTS.md`, `verification.json`,
`routes.json`. `MANIFEST.json` records the SHA-256 of every artifact and source
file.
