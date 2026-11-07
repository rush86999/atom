# Canvas lifecycle work order — verified delete/undelete (2026-11-07)

Status: **author-only, bounded work order. No production change, test run,
server, browser, model, provider, live DB, merge or deploy was performed.**
This is the next finite ORACLE family selected by
`ORACLE_MUTATION_QUEUE_2026_11_07.md`. Whole-app ORACLE-01 remains open.

## 1. Scope

Exactly two HTTP entrypoints and their two registered-tool equivalents:

| Context | Entrypoint | Writer |
|---|---|---|
| HTTP | `DELETE /api/canvas/{canvas_id}` (`api.canvas_routes.delete_canvas`, line 797) | `tools.canvas_crud_tool.delete_canvas` |
| HTTP | `POST /api/canvas/{canvas_id}/undelete` (`api.canvas_routes.undelete_canvas`, line 813) | `tools.canvas_crud_tool.restore_deleted_canvas` |
| Tool | `delete_canvas` (manual registration, `tools/registry.py:751`) | same `delete_canvas` |
| Tool | `restore_deleted_canvas` (public async auto-discovered by `ToolRegistry.discover_tools`) | same `restore_deleted_canvas` |

Not in scope: `PUT /api/canvas/{canvas_id}`, `POST /api/canvas/{canvas_id}/restore`,
canvas fork/capability/email/pdf/office routes, provider writes, goals, and
assignment execution. The accepted PUT/restore atomic-scope family
(`oracle01_direct_canvas_82ac9681a_atomic_scope`) is **closed** and is not
re-opened here without contrary evidence.

## 2. Current authority, exactly as read

- Router: `BaseAPIRouter(prefix="/api/canvas", dependencies=[Depends(require_pilot_user)])`.
  In `development` the pilot gate is a pass-through; in `single_user` it allows
  only `ATOM_PILOT_USER_EMAIL`. Each route also depends on `get_current_user`.
- Ownership: `_verify_canvas_owner` (`canvas_crud_tool.py:42`) returns true for
  `Canvas.created_by == user_id` **or** for any `CanvasAudit.user_id == user_id`
  whose `action_type` is not the event-only `submit`. This is the existing
  owner/co-editor policy. **Preserve it.** Do not narrow delete to creator-only
  and do not broaden it.
- Scope today: neither writer calls `canvas_write_scope_error` and neither route
  passes `current_user.tenant_id` / `workspace_id`. A new tombstone/restore row
  copies `latest.tenant_id`; it does not authorize the acting principal's scope.
- Single-tenant policy: `core/personal_scope.py` is the source of truth
  (`PERSONAL_TENANT_ID = "default"`, `PERSONAL_WORKSPACE_ID = "default"`).
  `canvas_write_scope_error` / `_scope_allows` already define the null/empty/
  `default` legacy rule. Reuse it; do not add a SaaS gate.
- Audit-only canvases: agent-created canvases may have a `CanvasAudit` trail and
  no `Canvas` row. `canvas_write_scope_error` returns 404 when the `Canvas` row
  is absent, so blindly calling it would break an existing supported delete
  path. The new lifecycle gate must handle this explicitly (see §4).

## 3. Current writer mechanics (append-only tombstone)

### Delete

`delete_canvas` opens its own `get_db_session`, checks ownership, reads the
latest row by `created_at` only, and:

- if latest is already `delete`, returns
  `{success: True, canvas_id, already_deleted: True}` with **no tombstone id**;
- otherwise appends `CanvasAudit(action_type="delete", tenant_id=latest.tenant_id,
  details_json={"deleted": True, "previous_action": latest.action_type},
  created_at=max(now, latest.created_at + 1µs))`;
- commits, then best-effort broadcasts `canvas:update` / `action="close"`;
- returns `{success, canvas_id, message}`. No `audit_id`, `operation_id`,
  `write_outcome`, verification or durable readback.

`Canvas.status` is not changed. A deleted canvas is recognized only by its
newest audit row, and `list_canvases` hides it unless `include_deleted`.

### Undelete

`restore_deleted_canvas` opens its own session and requires the latest row to be
`delete`. It finds the newest non-delete row, copies its `details_json` (removing
`operation_id`, `evidence_refs`, `postconditions`), adds
`restored_from_delete=True`, appends `action_type="restore"` with
`tenant_id=latest.tenant_id`, `canvas_type=latest.canvas_type`, strict `+1µs`
recency, commits, broadcasts `details.get("content")`/title, and returns
`{success, canvas_id, action_type}`. No source audit id, no operation id, no
content digest, no readback.

Historical rows are immutable by construction: both functions append only and
never update/delete prior `CanvasAudit` rows or rewrite `Canvas.content`.

### Parallel delete-ish paths checked

These are not alternative tombstone writers and must not be mistaken for one:

- `tools.canvas_tool.close_canvas` broadcasts `canvas:update` / `action="close"`
  for a user; it writes no `CanvasAudit` row and targets no canvas id.
- `core.email_attachment_store.delete_canvas_staged(user_id, canvas_id)` removes
  staged attachment files only.
- `core.pdf_canvas_store.delete_canvas_blobs(user_id, canvas_id)` removes PDF
  blob directories only.
- `core.office_sync_service` is a parallel canvas updater; it calls
  `deleted_canvas_ids` and skips writing an `update` row over a tombstone. That
  read-side guard is why delete must remain append-only and exact.
- `tools.canvas_crud_tool.list_canvases` and `read_canvas` derive state from the
  newest audit row, not `Canvas.status`.

## 4. Hypotheses vs evidence

These are static hypotheses to test, not runtime findings:

| # | Hypothesis | Evidence from static read | Probe |
|---|---|---|---|
| H1 | A foreign tenant/workspace co-editor can delete/undelete because scope is not checked | Both routes pass only user id; `_verify_canvas_owner` has no tenant/workspace predicate | Negative foreign tenant/workspace with an authored audit row |
| H2 | No operation identity / replay / conflict contract | Writers take no `operation_id` or `expected_prior_audit_id`; responses omit `audit_id` | Same-op replay, different-material same-op, stale-prior CAS |
| H3 | HTTP 200 is self-reported, not oracle-verified | `_VERIFIERS` has `canvas.update`/`canvas.restore_version` only; no delete/undelete verifier; routes do not call `validate` | Fresh-session verifier/readback controls |
| H4 | Undelete receipt cannot bind the exact pre-delete content row | Copies `details_json` but records no source row id or digest; strips `operation_id` | Content/type/title/source-row identity and prior-row immutability |
| H5 | Delete/undelete ordering is weaker than update/list | They order by `created_at` only; update/list use `created_at, id` | Legacy same-second tie + id tiebreak |
| H6 | Registered-tool authority can be shaped by model arguments | `mcp_service.execute_tool` forwards args; only `operator_*` strips `user_id`; `delete_canvas` takes `user_id` | Tool call with foreign `user_id` arg and trusted context user |
| H7 | Replay can duplicate a broadcast/learning side effect | No operation dedupe before append/broadcast; no correction capture is called today | Count audit rows, WS frames, `AgentFeedback`/correction rows on replay |

Non-findings: there is no evidence here that delete/undelete currently fail at
runtime, that data is corrupted, or that the accepted PUT/restore behavior
regressed. Do not state a runtime failure from this static read.

## 5. Required contract

For the ordinary self-owner or same-scope co-editor:

- **Authority now:** `get_current_user` is authoritative for HTTP; the dispatch
  context user is authoritative for the registered-tool path. A model-supplied
  `user_id` must not override it.
- **Scope:** on a `Canvas`-backed canvas, reuse
  `canvas_write_scope_error` (`tenant_id`, `workspace_id`, null/empty/default
  rule). On an audit-only canvas, authorize tenant against the latest audit
  tenant and mark workspace as legacy/unqualified rather than inventing a
  foreign-scope grant. Single-tenant null/default reuse is mandatory.
- **Atomicity:** the scope check and append share one transaction; a scope move
  before the append makes the guarded write match zero rows and refuse with zero
  effect. A move after an authorized commit may truthfully produce
  `committed_unverified`, identity retained, `replay=do_not_repeat`.
- **Operation identity:** server-owned `operation_id` for each logical
  delete/undelete. Same operation replay returns the original `audit_id`
  without a second row or broadcast. Same operation with different material or a
  target/prior row is a 409 conflict. Multiple historical rows for one key fail
  closed.
- **CAS:** `expected_prior_audit_id` (delete) and a tombstone/source audit id
  (undelete) are optional optimistic tokens; a mismatch refuses before effect.
- **Tombstone/content:** delete stores the exact prior audit id and content
  digest; undelete stores the exact tombstone id, source content-row id, content
  digest, canvas type/title provenance, and `restored_from_delete`.
- **Receipt:** include `canvas_id`, `audit_id`, `operation_id`, `write_outcome`,
  `status`, `verification`, and the prior/tombstone/source identity. Unknown
  commit outcome keeps identity and says `effect_unknown` / `do_not_repeat`.
- **Readback:** an independent fresh session reads the exact new row, checks it
  is the newest content/tombstone row, verifies action type, actor, tenant/
  workspace, operation id, source row, and content digest. The old rows remain
  present and unchanged.
- **Side effects:** one broadcast for a new effect, zero for a replay; no
  duplicate learning capture. Broadcast is not proof of commit.
- **Response codes:** 404 not found/foreign-unowned; 403 foreign tenant/workspace;
  409 stale prior/state/operation-material conflict; 200 only with a truthful
  verification status.

## 6. Minimal implementation shape (no second engine)

All changes go into existing mechanisms:

1. `backend/tools/canvas_crud_tool.py`
   - extend `delete_canvas` and `restore_deleted_canvas` with keyword-only
     `operation_id`, `expected_prior_audit_id`, `tenant_id`, `workspace_id`,
     `scope_required`; return `audit_id`, `operation_id`, `write_outcome`, and
     source/prior identity;
   - add one small internal lifecycle-scope helper that delegates to
     `canvas_write_scope_error` when a `Canvas` row exists and falls back to the
     latest audit tenant (workspace marked legacy) when it does not;
   - use `desc(created_at), desc(id)` consistently;
   - keep append-only rows and the existing `WRITE_NOT_ATTEMPTED` /
     `WRITE_COMMITTED` / `WRITE_UNKNOWN` contract.
2. `backend/core/canvas_write_service.py`
   - add `delete_canvas_verified` and `restore_deleted_canvas_verified` using the
     existing `_preflight_scope`, `_new_operation_id`, operation-material check,
     and `_envelope`; extend the frozen context with the prior/tombstone/source
     ids and content digest. Do not add a store, table, queue or approval system.
3. `backend/api/canvas_routes.py`
   - pass `current_user.tenant_id` / `workspace_id` (or `personal_scope`
     resolution) into the verified service; preserve current 404/403/409 mapping.
4. `backend/core/oracle/postcondition_verifiers.py` and
   `request_expectations.py`
   - register `canvas.delete` and `canvas.undelete` with a parameterized
     verifier next to `_canvas_write_postcondition`; freeze the same identities
     the service passes. No second oracle engine.
5. Registered-tool path
   - route both tools through the same verified service;
   - take the actor from dispatch context, not the tool's `user_id` argument;
   - refuse before effect if no trusted context user/scope exists.

Do not add `canvas.delete`/`canvas.undelete` to the action registry unless a
real assignment/generic consumer is introduced. The HTTP and tools.registry
paths can call the service and `validate(action, ctx)` directly, as the accepted
PUT/restore service does.

## 7. Probe plan (run later, only after root authorization)

The author file is
`docs/engineering/probes/canvas_lifecycle_probe_2026_11_07.py`. It is not a test
double for durability: it uses a real scratch SQLite file, mounted routes, the
real writer/service/verifier code, fresh sessions for readback, and real
`Canvas`/`CanvasAudit` rows. It does not stub expected server responses.

### Positive matrix

| ID | Setup | Expected |
|---|---|---|
| P1 | Self-owner, tenant `default`, unscoped canvas, create row + content | DELETE 200, `status=verified`, exact tombstone `audit_id`; list hides; read says deleted; prior rows unchanged |
| P2 | P1 followed by undelete | 200 `status=verified`; restore row is newest; content/type/title digest equals pre-delete; tombstone still present |
| P3 | Same-scope co-editor with an authoring audit row | Allowed under preserved `_verify_canvas_owner` policy, not creator-only |
| P4 | Null principal tenant/workspace vs `default`/null canvas | Allowed by the single-tenant null/default rule |
| P5 | Audit-only canvas (no `Canvas` row) | Allowed for the latest-audit tenant; workspace recorded as legacy, not a foreign grant |

### Negative / conflict matrix

| ID | Setup | Expected |
|---|---|---|
| N1 | Authenticated foreign user with no authorship | 404, zero new rows, no broadcast |
| N2 | Foreign tenant user with an authoring audit row | 403, zero effect, original rows intact |
| N3 | Foreign workspace user with a `Canvas`-backed canvas | 403, zero effect |
| N4 | Delete already deleted, different operation | Idempotent success with the original tombstone id and no second row |
| N5 | Undelete on a non-deleted canvas | 409 (state conflict), zero effect |
| N6 | Undelete when no pre-delete content row exists | 409, zero effect |
| N7 | `expected_prior_audit_id` mismatch | 409, zero effect |
| N8 | Same operation id, different material/target | 409, original retained |
| N9 | Scope move after the authorization read, before append | Guarded write matches zero rows; 409; winning move survives; no broadcast/learning |
| N10 | Scope move commits after an authorized commit | `committed_unverified`, identity retained, `replay=do_not_repeat` |
| N11 | Tool path with model-supplied foreign `user_id` and trusted context attacker | Must not delete the victim; context actor is authoritative |
| N12 | Tool path with no trusted context user | Refuse before effect |

### Replay / receipt / source-binding matrix

| ID | Check |
|---|---|
| R1 | Same-op delete twice: one tombstone, same `audit_id`, no second broadcast |
| R2 | Same-op undelete twice: one restore row, same `audit_id`, no duplicate broadcast/learning |
| R3 | delete → undelete → delete as distinct operations: distinct rows and identities |
| R4 | Receipt contains canvas, audit, operation, prior/tombstone/source ids, content digest, write outcome and verification status |
| R5 | Fresh-session read of the exact row proves actor/tenant/workspace/action/identity; source row is unchanged |
| R6 | Historical-row count and bytes are unchanged except the one appended row |
| R7 | Unknown commit outcome returns `effect_unknown` / `do_not_repeat`, never “nothing changed” |
| R8 | Verifier refutes missing row, wrong actor, wrong scope, wrong operation, wrong source row, wrong digest, or a later content row |

### Failure-first order

1. Run P1/P2 and the two direct negatives N1/N2 on current code. P1/P2 should
   fail because no receipt/verifier exists; N2 is the authority hypothesis.
2. Add the minimal writer/service/verifier change.
3. Run the full positive/negative/CAS/replay matrix with fresh sessions.
4. Run the registered-tool path N11/N12 through the real MCP dispatch.
5. Only then prepare an evidence packet with exact source blobs and logs.

## 8. Do-not list

- No second store, table, operation engine, oracle, approval system or SaaS gate.
- No new WebSocket/learning path; no duplicate broadcast or correction on replay.
- No creator-only narrowing and no foreign-scope broadening.
- No acceptance of `http 200` as proof; every new effect carries verification or
  honest uncertainty.
- No tests/browser/server/model/provider/live-DB run in this authoring phase.
- No merge, review comment, deploy or spend.
