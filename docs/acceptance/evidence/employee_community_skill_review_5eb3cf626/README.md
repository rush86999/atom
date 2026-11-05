# ORACLE-01 — verified TEAM_LEAD+ community-skill decisions

Status: **submitted for independent verification.** This is the bounded
community-skill promote/delete family selected after the scoped-memory and
tool-mutation repair submissions. It covers exactly the two community-skill
mutation routes; import, execute, list, get and the rest of the skill surface
remain out of scope.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-skill-review-20261105` |
| Accepted admin test successor (base) | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product (runtime) | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `f8477493c80b198ec236bafa600b9bee230840fd` |
| Executed source (product + tests) | `5eb3cf62644e0350e0f487a58dfddc4b00dabbc0` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; no live code sandbox, model or provider |
| Model/provider/browser calls | none |

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| POST | `/api/skills/promote` | `promote_skill` | `Untrusted` community skill -> `Active` |
| DELETE | `/api/skills/{skill_id}` | `delete_skill` | delete the community `SkillExecution` row |

Community skills are `SkillExecution` rows with `skill_source="community"`,
`tenant_id="system"`, `agent_id="system"`, `workspace_id="default"`, the
reviewed material in `input_params`/`security_scan_result`, and a status of
`Untrusted` or `Active`. Cloud execution rows are never visible to these
decisions.

## Authority

- Both routes retain mandatory `get_current_user` and add
  `require_role(UserRole.TEAM_LEAD)`. The service independently re-reads the
  actor and checks active status and TEAM_LEAD+ role before any effect.
- Community rows are global/system review targets, not tenant-scoped candidate
  rows. A TEAM_LEAD+ reviewer from any tenant may review the global community
  registry; the audit receipt is attributed to the acting reviewer's real
  tenant/user. The target's `system` scope is recorded as metadata.
- Cloud rows (`skill_source != "community"`) resolve as not found.

## Exact transitions

### Promote

- Allowed prior status: `Untrusted` -> `Active`.
- Already `Active`:
  - same operation id + same material -> `already_applied`;
  - a new operation id -> no-change success (`status="Active"`,
    `previous_status="Active"`, `effect="none"`, no new audit), preserving the
    old API.
- Any other prior status -> 409 `UNSUPPORTED_STATUS`, zero effect.

### Delete

- Allowed for any community status (`Untrusted`/`Active`).
- Missing -> 404; same-operation tombstone replay -> `already_applied`;
  stale/competing delete -> 409 with the peer row preserved.

### Material binding

Promote uses a guarded `UPDATE` and delete a guarded `DELETE`. Both bind the
exact id, prior status, `skill_source`, target `skill_id`, row
tenant/agent/workspace, `input_params`, `security_scan_result` and
`sandbox_enabled`. A peer edit before the claim matches zero rows and returns
409 `STALE_TARGET`; the peer row is preserved.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction as the
`SkillExecution` change. The audit row id is the server-owned operation id
(`skill:promote|delete:<supplied-or-generated>`). Metadata contains the
operation id, action, event type, target id/system scope, skill name,
prior/result status, request/prior/result material digests and actor id/role.
No raw skill body, generated code, package list, scan payload, secret or SQL
parameter is stored in the receipt or logs.

- `verified`: success shape plus additive `verification`, `operation_id`,
  `audit_id`; `effect=committed`.
- `already_applied`: same operation id and request material; one receipt, no
  second effect.
- `conflict` (409): changed material, stale prior state, competing decision,
  unsupported status or non-community target; `effect=none`.
- `not_applied` (409): confirmed local rollback; `effect=none` and
  `SKILL_TRANSACTION_ROLLED_BACK`; target/audit unchanged or absent.
- `committed_unverified` (503): post-commit audit/target readback failed or was
  refuted; `effect=committed`, original identity, `do_not_repeat`.
- `effect_unknown` (503): lost commit confirmation; `effect=unknown`, original
  identity, `do_not_repeat`, no exception text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `promote_skill` / `delete_skill` routes | verified TEAM_LEAD+ decision service |
| `SkillRegistryService.promote_skill` / `delete_skill` | retained for internal/test callers; routes no longer use them |
| community `SkillExecution` rows | exact material CAS |
| cloud `SkillExecution` rows | invisible to these decisions |
| `AuditLog` | additive safe receipt |
| import/execute/list/get/episodes | unchanged and included in affected regression |

## Controls

- **Focused community-skill gate: 42 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): 34 new failure-first controls plus
  the rewritten route coverage class.
- **Affected skill/marketplace/registry/review/audit selection: 268 passed, 4
  failed baseline on both versions** (`affected-314.log`,
  `affected-311.log`). The same selection on the accepted admin base
  `9d73552d2` gives 234 passed and the same 4 failures
  (`baseline-affected-95f7-314.log`, `baseline-affected-95f7-311.log`). The
  branch adds exactly 34 passing controls; the failure lists are identical.

The 4 baseline failures are pre-existing import errors for absent
`api.package_routes` / `api.marketplace_routes` modules in
`tests/test_round22_marketplace_security.py`; they are unrelated to the two
skill decision routes.

The new matrix covers TEAM_LEAD/admin twins; member/viewer/guest/anonymous
refusal; missing/cloud 404; promote `Untrusted`/`Active`/unsupported; delete
`Untrusted`/`Active`/replay/missing/stale; same-operation replay; changed
material; later status/code/scan/lineage revision; competing/stale peer edits;
rollback `effect=none`; post-commit readback `committed_unverified`; lost
confirmation `effect_unknown`; 15 audit-tamper variants; and raw skill
material omission.

## Boundaries

- No import, execute, list, get, episodes or learning-progress changes.
- No live skill/code execution, provider, credential, spend, send, download or
  deployment operation.
- No new table, migration or second review/approval engine; `SkillExecution`
  and `AuditLog` are reused.
- No change to the repaired memory/tool-mutation branches or accepted
  admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 lanes.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-affected-95f7-*.log`,
`source-tree.txt`, `README.md`, `TEST_RESULTS.md`, `verification.json`,
`routes.json`. `MANIFEST.json` records the SHA-256 of every artifact and source
file.
