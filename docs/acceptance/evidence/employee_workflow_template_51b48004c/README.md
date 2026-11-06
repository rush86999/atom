# ORACLE-01 — verified workflow-template create/update

Status: **submitted for independent verification.** This is the next bounded
Agent 2 mutation family from the frozen reachable map. It covers exactly the two
template mutation routes below; read/list/search/instantiate/execute/import/
delete/rate/export remain out of scope.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-workflow-template-20261105` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `5fbd5c8f51449ed3fa6323a304713c04161d3491` |
| Executed source (product + tests) | `51b48004cdacace1a077865c3ee8fd6edbff8b50` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite and temp template directory; no live workflow/model/provider |

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| POST | `/api/workflow-templates/` | `create_template` | create one template JSON file |
| PUT | `/api/workflow-templates/{template_id}` | `update_template_endpoint` | update one template JSON file |

The durable target is the existing filesystem template store under the
manager's configured `template_dir`. No database template row, table or
migration is introduced.

## Authority and scope

- Routes retain `require_permission(Permission.WORKFLOW_MANAGE)` and
  `get_current_user` (TEAM_LEAD+).
- The service re-reads the current `User` row, requires active status and
  TEAM_LEAD+, freezes current status/is_active/role/raw tenant and claims that
  exact material in the same database transaction as the `AuditLog` receipt.
- Templates are global workflow definitions, not tenant rows. The audit receipt
  is attributed to the acting user's real tenant/workspace.
- Template ids are sanitized to `[A-Za-z0-9_-]` before any path join; a loaded
  id containing separators is not found.

## Exact effect contract

### Create

- The route keeps category/complexity validation (422) and step normalization.
- One `WorkflowTemplate` is built and duration calculated. The file is written
  atomically with an exclusive link, so a pre-existing id is never overwritten.
- Same operation id + same request -> `already_applied`; changed material ->
  409 `OPERATION_CONFLICT`; a receipt whose target file is missing/different ->
  `committed_unverified`.

### Update

- The existing blocked-field list and 422 for an empty update are preserved.
- The exact canonical prior template material (every model field) is bound
  under a per-template lock. The file is re-read immediately before the write;
  a peer edit -> 409 `STALE_TARGET`, peer file preserved.
- Only name/description/steps/inputs/tags may change; steps and inputs use the
  existing `TemplateStep`/`TemplateParameter` models. Duration is recalculated
  and `updated_at` advances only when the material actually changes.
- Same operation id + same request -> `already_applied`; changed material ->
  409 `OPERATION_CONFLICT`; later revision -> `committed_unverified`.
- A request that already matches -> 200 no-change / `effect=none`, no audit.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction boundary as the
file write. Operation id:
`workflow-template:create|update:<supplied-or-generated>`. Metadata contains
operation id, action, event type, target template id, prior/request/result
digests and actor id/role/tenant. No raw template name, description, steps,
parameters, prompts, code, secret or SQL parameter is stored in the receipt or
logs.

- `verified`: success plus additive verification/operation_id/audit_id.
- `already_applied`: same operation/material; one receipt.
- `no_change`: matching update; 200/effect=none, no audit.
- `conflict` (409): existing id, stale file, changed operation or authority
  change; `effect=none`.
- `not_applied` (409): confirmed local rollback; file restored/removed and
  `effect=none`.
- `committed_unverified` (503): post-commit readback failed/refuted.
- `effect_unknown` (503): lost confirmation; original identity, no exception
  text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `create_template` / `update_template_endpoint` routes | verified decision service |
| `WorkflowTemplateManager.create_template` / `update_template` | retained for internal/test callers; the two routes no longer use them |
| template JSON file | exact canonical prior/result CAS under a per-template lock |
| list/get/search/instantiate/execute/import | read the files/manager; unchanged |
| `AuditLog` | additive safe receipt |
| other template ids | never touched |

## Controls

- **Focused: 27 new decision controls passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`).
- **Affected template/system/route/auth/audit selection: 646 passed, 14
  skipped, 40 failed baseline on both versions** (`affected-314.log`,
  `affected-311.log`).
- **Baseline at `9d73552d2` (without the new contract file): 619 passed, 14
  skipped, the same 40 failures on both versions** (`baseline-314.log`,
  `baseline-311.log`). The branch adds exactly 27 passing controls; failure
  lists are byte-identical.

The 40 baseline failures are pre-existing fixture/API drift unrelated to the
two template mutations:

- 38 `test_covpush_w79c_api_routes.py` template controls use a `MagicMock` user
  without a real role/DB row, so the existing permission dependency refuses
  them before the route body;
- `test_workflow_template_routes_coverage.py::TestImportExportTemplate::test_import_template_valid`
  passes a `MagicMock` author email into `WorkflowTemplate`;
- `test_workflow_template_routes_coverage.py::TestUpdateTemplate::test_update_template_steps`
  expects the legacy `id` step key while the model exposes `step_id`.

All reproduce exactly on the accepted admin base.

The new matrix covers TEAM_LEAD/admin create/update, member and anonymous
refusal, create collision, audit receipts with raw-content omission, replay,
changed material, later revision, stale peer edit, authority deactivation/
demotion, audit rollback with file restoration/removal, post-commit readback,
lost confirmation, audit tampering and path traversal.

## Boundaries

- No read/list/search/instantiate/execute/import/delete/rate/export changes.
- No live workflow/agent/model/provider/credential/spend/send/download/
  deployment operation.
- No new table, migration or second template/approval engine; the existing JSON
  store and `AuditLog` are reused.
- No change to accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01
  lanes or the submitted review/memory/skill/agent/goal/document branches.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
