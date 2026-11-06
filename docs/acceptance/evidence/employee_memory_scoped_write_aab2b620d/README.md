# ORACLE-01 — scoped durable memory and session-context writes

Status: **submitted for independent verification.** This is the bounded
successor to the submitted tool-mutation review family and the accepted admin
repair. It covers exactly the key/value and session-context memory mutations
plus their scoped read/search consumers. The remaining Auto-Dev/memory surfaces
and whole-app ORACLE-01 remain open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-memory-write-20261105` |
| Accepted admin test successor (base) | `9d73552d249ae8ec5b05af77546faf9621bbcd47` |
| Accepted admin product (runtime) | `5fbb377a4e1eef8fdd0013275cd8b1c9b278cd41` |
| Product source | `4a32ce30b03a47163fdd790297a96108d2c5c70f` |
| Executed source (product + tests) | `aab2b620df3e740c6c255c6a869e72fcc7eb4af7` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled interleaving/fault seams |
| Model/provider/browser calls | none |

The submitted tool-mutation review branch is an independent evidence line and
is not merged here. The accepted admin product/test successor is included as
the base.

## Scope

| Method | Path | Handler | Effect |
|---|---|---|---|
| POST | `/api/memory` | `store_memory` | durable scoped store/upsert |
| POST | `/api/memory/context/{session_id}` | `update_context` | durable scoped context merge |
| DELETE | `/api/memory/{key}` | `delete_memory` | durable scoped conditional delete |
| GET | `/api/memory/{key}` | `retrieve_memory` | scoped read |
| GET | `/api/memory/search` | `search_memory` | scoped search |
| GET | `/api/memory/context/{session_id}` | `get_context` | scoped context read |

`GET /api/memory/stats` is the LanceDB statistics surface and is out of scope.
It remains read-only and unchanged.

## User outcome

An authenticated user, or an explicitly named agent in the caller's tenant, can
store, update, read, search, delete and merge context only in their own
`(tenant_id, user_id, agent_id)` scope. The effect is durable in the existing
`TenantSetting` key/value store, one safe `AuditLog` receipt commits with it,
same-operation replay is idempotent, stale/competing writes refuse with zero
effect, and another tenant/user/agent cannot enumerate or overwrite the entry.

## Authority and scope

- The routes retain the existing `get_current_user` dependency and the existing
  `require_governance` wrappers (MODERATE for store/context, HIGH for delete).
- Scope is `tenant_id = resolve_tenant_id(current_user)` (the personal tenant
  fallback is `"default"`), `user_id = current_user.id`, and the optional
  `agent_id` query parameter. No scope is inferred from request content.
- The `TenantSetting` key is a keyed digest of the exact scope plus the memory
  key/session id, and the stored JSON document carries the scope again. A
  different tenant, user or agent cannot read, search, overwrite or delete it.
- The existing unique constraint `(tenant_id, setting_key)` is the insert
  arbiter. All other `TenantSetting` consumers filter a specific setting key
  (`billing`, governance, BYOK/credential keys), so the `memory:` namespace is
  isolated.

## Exact effect contract

### Durable store

- The existing `TenantSetting` row under `memory:v1:<scope-hash>:<target-hash>`
  is created or conditionally updated. The conditional UPDATE binds the exact
  prior `setting_value`.
- A concurrent writer that changed the prior document matches zero rows and
  gets a typed 409 `STALE_TARGET` with `effect=none`; the peer value is
  preserved.
- The stored JSON contains schema, exact scope, key, value, metadata, revision
  and timestamp.

### Context merge

- The POST body is merged into the exact scoped session document; the prior
  document is the CAS material. Concurrent merges refuse rather than lose the
  peer's fields. `_updated_at` is deterministic within the operation.
- Same operation/material replay is idempotent; a later revision is
  `committed_unverified`, not `already_applied`.

### Delete

- Conditional delete binds the exact current `setting_value` and scope.
- Missing -> 404 with zero effect. Same-operation tombstone replay ->
  `already_applied`. Stale/competing delete -> 409; the peer entry is
  preserved.

## Receipt and result states

The existing `AuditLog` table is written in the same transaction as the
`TenantSetting` write/delete. The audit row id is the server-owned operation id
(`memory:store|context|delete:<supplied-or-generated>`). Metadata contains the
operation id, action, event type, exact scope, target/setting digests, request/
prior/result digests and actor id/role. No raw memory value, metadata, key,
session content, secret, SQL parameter or exception text is stored in the
receipt or returned in logs.

- `verified`: target and audit readback match; success shape plus additive
  `verification`, `operation_id`, `audit_id`.
- `already_applied`: same operation id and request material; no second effect.
- `conflict` (409): changed operation material, stale prior value, competing
  delete/store or scope/target mismatch; `effect=none`.
- `not_applied` (409): confirmed local rollback from a constraint failure with
  no original operation; `verification.effect="none"` and
  `MEMORY_TRANSACTION_ROLLED_BACK`.
- `committed_unverified` (503): post-commit audit/target readback failed or was
  refuted; `effect=committed`, original identity, `do_not_repeat`.
- `effect_unknown` (503): lost commit confirmation; `effect=unknown`, original
  identity, `do_not_repeat`, no exception text.

## Caller / consumer / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `store_memory` | verified scoped `TenantSetting` upsert |
| `update_context` | verified scoped context merge |
| `delete_memory` | verified scoped tombstone delete |
| `retrieve_memory` / `search_memory` / `get_context` | same-scope durable reads only |
| process-global `_memory_store` / `_context_store` | removed; no cross-caller bytes |
| `TenantSetting` budget/governance/BYOK consumers | filter specific keys; `memory:` namespace does not collide |
| `AuditLog` consumers | additive safe receipt |

## Controls

- **Focused memory gate: 74 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): 25 new failure-first controls plus
  the rewritten real-DB memory route controls and auth inspection.
- **Affected memory/TenantSetting/audit selection: 690 passed, 1 skipped, 7
  failed baseline on both versions** (`affected-314.log`, `affected-311.log`).
  The same selection on the accepted admin base `9d73552d2` gives 665 passed,
  1 skipped, the same 7 failures (`baseline-affected-95f7-314.log`,
  `baseline-affected-95f7-311.log`). The branch adds exactly 25 passing
  controls; the failure lists are byte-identical.

The 7 baseline failures are unrelated to this slice:

- 6 `test_covpush_w79a_api_routes.py` MiniApp/Office controls (the file is
  included as an affected consumer; the memory class itself is green).
- 1 `tests/integration/services/test_memory_consolidation_multi_tenant.py::test_memory_consolidation_tenant_isolation`
  pre-existing `AgentMemory` consolidation control.

The new matrix covers user/tenant/agent isolation, same-key independence,
store insert/update, stale prior, same-operation replay, changed material,
later revision, context merge/replay/competing merge, delete/replay/missing/
stale, confirmed rollback `effect=none`, post-commit readback
`committed_unverified`, lost confirmation `effect_unknown`, 12 audit-tamper
variants and raw-value/key/metadata non-leakage.

## Boundaries

- No live model, provider, credential, spend, send, download, deployment,
  administrator/account/budget or PostgreSQL/soak operation was used.
- No new memory table or migration; the existing `TenantSetting` and
  `AuditLog` are reused. No second memory/approval/authorization engine.
- No change to LanceDB stats, ingestion, webhooks, integration sync or live
  provider memory.
- No change to accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 or
  the submitted tool-mutation review branch.
- Whole-app ORACLE-01, PostgreSQL runtime/soak and multi-worker serialization
  remain open.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-affected-95f7-*.log`,
`source-tree.txt`, `README.md`, `TEST_RESULTS.md`, `verification.json`,
`routes.json`. `MANIFEST.json` records the SHA-256 of every artifact and source
file.
