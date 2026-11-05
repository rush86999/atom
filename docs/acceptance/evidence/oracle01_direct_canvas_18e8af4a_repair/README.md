# ORACLE-01 direct canvas repair — scope, operation identity, no-change mirror

Status: **repair submitted for independent verification.** The previous
submission (source `5eede13aa`, evidence `d8a2e019b`) is withheld. This bundle
addresses the three contracts in
`VERIFIER_ORACLE_HTTP_CANVAS_5EEDE_REPAIR_20261105.md`. Whole-app ORACLE-01
remains explicitly open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-http-canvas-20261105` |
| Base | `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1` |
| Previous withheld source | `5eede13aa7a2f765619dbd54251eaa2954d778dd` |
| Previous evidence commit | `d8a2e019b3b5e7b0ad47dd3d56f00d0d38667c95` |
| Repair source | `18e8af4a63a5f952e14a9c5f27dc81d6d313b918` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | local authenticated FastAPI `TestClient`, SQLite persistence |
| Model/provider/browser calls | none |

This is the final repair source. Its parent `21c32937a` was the first repair batch (evidence `a7f61f730`); `18e8af4a` adds two verifier refusals for a null restore target that a controlled result could otherwise bypass. Production behavior and the focused/affected counts are unchanged.

## The three withheld contracts, repaired

### 1. Foreign-scope saves/restores committed before refusal

**Before:** the writer only checked creator/audit authorship. A user with
authorship history could save or restore a canvas after it moved to another
workspace or tenant; the append and mirror replacement landed, then the oracle
refuted scope and reported `committed_unverified`. That is an unauthorized
effect, not an authorization control.

**Repair:**

- `canvas_write_scope_error()` resolves the authenticated principal's
  tenant/workspace against the authoritative `Canvas` row and, for restore,
  the target audit. It returns `403` for a foreign tenant/workspace and `404`
  for missing/foreign ownership.
- The direct service calls it **before dispatch**; the writer calls it again
  **inside the same mutation transaction** with a row lock where the database
  supports it, so an HTTP preflight alone cannot create a TOCTOU gap.
- A refusal happens before append, mirror mutation, broadcast or learning
  capture. Audit and mirror stay unchanged.
- New audit rows are stamped with the authoritative `Canvas` tenant, not a
  legacy/foreign audit tenant.
- Post-effect scope refutation remains as defense in depth for state that
  genuinely changes between commit and readback.

**Explicit scope rule:** a real canvas tenant/workspace admits only an exact
principal match. An unscoped (NULL/empty) canvas remains available to an
authorized same-tenant editor. A principal with no workspace/tenant claim is
treated as legacy `default` only when the canvas itself is unscoped or
`default`; a real foreign scope is never silently mapped into default.
Same-scope co-editing (creator or authoring audit history) is preserved.

### 2. Old identical audit certified a new deliberate save

**Before:** a manual save without an `operation_id` had no server-owned
request identity. A controlled CRUD result could return a prior update audit
with identical content, append nothing, and the public response still reported
`verified`.

**Repair:**

- Every direct update now gets a fresh server-owned
  `http-canvas-update:<uuid>` identity when the caller omits one. It is written
  into the durable audit row and returned in the response.
- A supplied `operation_id` remains an idempotent retry, but it is bound to the
  exact canonical material and an accepted review state. Reusing it for
  different material is a `409` refusal before effect, in both the service
  preflight and the writer transaction.
- Requests without an id remain distinct deliberate edits; byte-identical
  saves get distinct server-owned ids and distinct audits.
- Restores get a fresh `http-canvas-restore:<uuid>` identity written into the
  new restore audit. The verifier requires it, so `restored_from` alone (an
  old historical target) cannot certify a new restore.
- The verifier requires the returned audit to be the **current content
  revision** (skipping event-only audit stamps), so an old identical audit
  cannot certify a new save.
- A no-change restore does not invent an `audit_id` or `operation_id`; it is a
  separate zero-effect contract.

### 3. No-change restore verified a stale mirror

**Before:** the no-change verifier compared the target audit content with the
latest audit content but not with the durable `Canvas.content` mirror. A stale
mirror could be reported as `verified` with no state change.

**Repair:** the no-change branch now checks the target action/content and
tenant, the current content revision, the authoritative canvas mirror digest
and the scope. A stale mirror returns `no_change_unverified` with
`verification.status=refuted`, `effect=none`, `replay=do_not_repeat`, no audit,
and leaves the state unchanged. It never silently repairs the mirror while
claiming zero effect.

## Controls

The focused matrix is **39 direct controls + the independent verifier's 6
probe cases = 45**. Key new controls:

| Control | Assertion |
|---|---|
| `test_direct_put_foreign_workspace_refuses_before_effect` | Foreign workspace PUT: 403, no audit, mirror unchanged |
| `test_direct_put_foreign_tenant_refuses_before_effect` | Foreign tenant PUT: 403, no audit, mirror unchanged |
| `test_direct_restore_foreign_workspace_refuses_before_effect` | Foreign workspace restore: 403, no audit, mirror unchanged |
| `test_direct_restore_foreign_tenant_refuses_before_effect` | Foreign tenant restore: 403, no audit, mirror unchanged |
| `test_direct_restore_foreign_target_tenant_refuses_before_effect` | Foreign target audit tenant: 403, no audit, mirror unchanged |
| `test_writer_rechecks_scope_after_service_preflight` | Bypassing the HTTP preflight still refuses at the writer transaction |
| `test_direct_restore_no_change_stale_mirror_is_not_verified` | Stale mirror: `no_change_unverified`/`refuted`, no audit, state unchanged |
| `test_direct_put_old_identical_audit_is_not_verified` | Old identical audit result: `committed_unverified`, not `verified` |
| `test_direct_put_manual_save_gets_server_operation_identity` | Manual save gets a durable `http-canvas-update:` id; two identical saves differ |
| `test_direct_put_operation_id_different_material_is_refused` | Same operation id + different material: 409 before effect |
| `test_direct_restore_gets_server_operation_identity` | Restore audit carries the returned `http-canvas-restore:` id |
| `test_direct_put_post_commit_stale_mirror_is_committed_unverified` | Authorized commit then stale mirror: `committed_unverified`, identity retained |
| `test_direct_put_post_commit_scope_change_is_committed_unverified` | Authorized commit then moved scope: `committed_unverified`, identity retained |
| `test_same_scope_coeditor_can_save_without_creator_ownership` | Legitimate same-scope co-editing still verifies |
| `test_direct_put_null_workspace_cannot_edit_scoped_canvas` | Null principal workspace does not map into a real workspace |
| `test_direct_put_workspace_principal_can_edit_legacy_unscoped_canvas` | Explicit legacy unscoped canvas behavior preserved |
| `test_direct_put_commits_across_real_sessions` | Real separate-session factory: committed audit/mirror readback |

The independent verifier's six probes are retained in
`backend/tests/test_verifier_canvas_scope_5eede.py`: four foreign
workspace/tenant PUT/restore cases, the stale-mirror no-change case and the
old-identical-audit case.

## Results

| Scope | Python 3.14 | Python 3.11 |
|---|---|---|
| Focused repair matrix (39 direct + 6 probes) | **45 passed** | **45 passed** |
| Affected CRUD/oracle/assignment/canvas controls | **177 passed, 8 deselected** | **177 passed, 8 deselected** |
| Adjacent projection/feedback/connected canvas | **34 passed** | not run |
| Route-coverage patch seams | **3 passed** | not run |
| `tests/api/test_canvas_routes_coverage_w51.py` | **53 passed, 5 pre-existing failures** | not run |

The affected suite includes `tests/test_canvas_crud.py`,
`tests/test_oracle_connected_mutations.py`,
`tests/test_canvas_assignment_integration.py`,
`tests/test_covpush_canvasroutes.py` (WebSocket class deselected),
`tests/test_canvas_capability_service.py` and the exact-operation replay
control. The adjacent suite includes canvas projection, feedback episode and
connected binding.

## Pre-existing exclusions

These reproduce on base `81c5962bd` and are not counted as repair coverage:

- `tests/api/test_canvas_routes_coverage_w51.py`: 5 failures (fork success,
  logic not-found, 3 WebSocket cases); same 5 on the base.
- `tests/test_chat_canvas_editor.py`: 14 failures, 91 passed; same on base.
- `tests/test_covpush_regtrio.py` VFS/document-search: 2 failures; same on base.
- `tests/test_covpush_canvasroutes.py::TestCanvasWebSocket`: 4 failed, 4
  passed on base (fixture mounts `router`, not `ws_router`); the affected run
  deselects the class.

## Commands

Exact commands and extraction roots are in `TEST_RESULTS.md`.

## Boundaries

- No second oracle, mutation store or digest. The repair uses the existing
  `canvas.update` / `canvas.restore_version` verifiers and canonical material.
- No new approval prompt for ordinary authorized saves.
- No live model, provider, credential, spend, send, download or deployment
  authority.
- PostgreSQL concurrency/soak, remaining canvas routes, goals routes, provider
  writes and the whole-app ORACLE-01 inventory remain outside this slice.
- Accepted feedback/shared-CAS/wait and employee episodes remain closed.

## Artifacts

`focused-*.log`, `affected-*.log`, `adjacent-314.log`,
`routes-w51-314.log`, `patch-seams-314.log`, the four base pre-existing logs,
`README.md`, `TEST_RESULTS.md`, `verification.json`, `routes.json`.
`MANIFEST.json` records the SHA-256 of every artifact and changed source file.
