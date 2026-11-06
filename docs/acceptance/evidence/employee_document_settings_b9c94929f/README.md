# ORACLE-01 — verified document-ingestion settings updates

Status: **submitted for independent verification.** This is the next bounded
Agent 2 mutation family from the frozen reachable map. It covers exactly the
single settings-update route below; read, sync, upload, parse, memory removal
and LanceDB document deletion remain out of scope.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-document-settings-20261105` |
| Accepted admin base | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `0aa16ce762f45af9bf47dcb45bceb6910604b2ed` |
| Executed source (product + tests) | `b9c94929fecd55eab4827bcdf201c6694ac228cf` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; no live provider/sync/upload |

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| PUT | `/api/document-ingestion/settings` | `update_ingestion_settings` | `IngestionSettings` row update/create |

Durable target: the existing workspace-scoped `ingestion_settings` row
identified by `(workspace_id, integration_id)`. The same table's hybrid
ingestion columns (`entity_types`, `sync_last_n_days`, `max_records_per_sync`,
`sync_mode`, `usage_stats_json`) are never part of the bound material and are
left untouched.

## Authority and scope

- The route retains mandatory `get_current_user`; there is no role expansion.
- `workspace_id` comes from the existing `get_workspace_id(current_user)`
  resolver. The request body has no workspace or tenant field, so a caller
  cannot select a foreign workspace.
- The service re-reads the current `User` row and requires active status,
  freezing current `status`/`is_active`/raw tenant and claiming that exact
  material in a guarded no-op `User` UPDATE in the same transaction as the
  settings write and `AuditLog` receipt.
- A deactivation or tenant/workspace reassignment after the row read matches
  zero rows, rolls back the settings/audit attempt, preserves the peer state and
  returns an `effect=none` refusal.

## Exact effect contract

- Fields: `enabled`, `auto_sync_new_files`, `file_types`, `sync_folders`,
  `exclude_folders`, `max_file_size_mb`, `sync_frequency_minutes`.
- Missing row: insert with a deterministic id
  `ingestion:<HMAC(workspace,integration)>` plus model defaults and the supplied
  fields. A concurrent insert with the same primary key loses safely through
  the replay/conflict path.
- Existing row: merge only supplied fields. The conditional `UPDATE` binds the
  exact row id, workspace, integration and all seven prior field values. A peer
  change to any bound field matches zero rows -> 409 `STALE_TARGET`; peer values
  remain.
- Only `integration_id` supplied -> 200 no-change / `effect=none`, no audit.
- A request that already matches the current row -> 200 no-change /
  `effect=none`, no audit.
- Same operation id + same request material -> `already_applied`; changed
  material -> 409 `OPERATION_CONFLICT`; a later settings revision ->
  `committed_unverified`.
- After a committed change the existing in-memory service cache is cleared and
  reloaded from the row. A cache reload failure is logged and does not change
  the committed result; the DB row is the authority.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction. Operation id:
`document-settings:<supplied-or-generated>`. Metadata contains operation id,
action, event type, target integration id, workspace id, prior/request/result
settings digests and actor id/role/tenant. No raw folder paths, file-type lists,
secrets or SQL parameters are stored in the receipt or logs.

- `verified`: success shape plus additive verification/operation_id/audit_id;
  `effect=committed`.
- `already_applied`: same operation/material; one receipt, no second effect.
- `no_change`: only-integration-id or already-matching request; 200/effect=none,
  no audit.
- `conflict` (409): stale settings, changed operation or authority change;
  `effect=none`.
- `not_applied` (409): confirmed local rollback; `effect=none` and
  `DOCUMENT_SETTINGS_TRANSACTION_ROLLED_BACK`.
- `committed_unverified` (503): post-commit audit/target readback failed or was
  refuted; `effect=committed`, original identity, `do_not_repeat`.
- `effect_unknown` (503): lost commit confirmation; `effect=unknown`, original
  identity, `do_not_repeat`, no exception text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `update_ingestion_settings` route | verified settings decision service |
| `AutoDocumentIngestionService.update_settings` / `_persist_settings` | retained for internal/test callers; the route no longer uses them |
| `get_settings` / sync / upload consumers | read the row through the service cache; cache cleared/reloaded after commit |
| `ingestion_settings` row | exact seven-field CAS |
| hybrid ingestion columns | untouched by this family |
| `AuditLog` | additive safe receipt |
| other workspaces | never touched |

## Controls

- **Focused: 111 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): 26 new failure-first decision
  controls plus the rewritten route coverage classes.
- **Affected document-ingestion/audit selection: 278 passed on both versions**
  (`affected-314.log`, `affected-311.log`).
- **Baseline at `9d73552d2` (without the new contract file): 252 passed on both
  versions** (`baseline-314.log`, `baseline-311.log`). The branch adds exactly
  26 passing controls; there are no baseline failures in this selection.

The new matrix covers create/merge isolation, only-integration-id and matching
no-op, stale peer edits, same-operation replay, changed material, later
revision, authority deactivation/tenant move, audit rollback, post-commit
readback, lost confirmation, 12 audit-tamper variants, raw folder omission and
anonymous refusal.

## Boundaries

- No read/sync/upload/parse/memory-removal/LanceDB changes.
- No live provider, credential, spend, send, download or deployment operation.
- No new table, migration or second settings/approval engine; the existing
  `ingestion_settings` and `AuditLog` are reused.
- No change to accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01
  lanes or the submitted review/memory/skill/agent/goal branches.
- PostgreSQL runtime/soak, multi-worker serialization and whole-app ORACLE-01
  remain open.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-*.log`, `source-tree.txt`,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and source file.
