# ORACLE-01 bounded slice — verified direct HTTP canvas save/restore

Status: **submitted for independent verification; whole-app ORACLE-01 remains
open.** This bundle covers exactly two mounted routes. It does not claim the
whole-application ORACLE-01 inventory, and it does not relabel the historical
route-discovery counts as current verified coverage.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-http-canvas-20261105` |
| Base | `81c5962bd17b3ffa90cd5107d5b3134821c0ffa1` |
| Initial slice source | `326534847041be79f4cf078861bd6dc223be8cc4` |
| Duplicate-after-later-edit fix | `852aaf0398e38c8b1897b4a5f1fed745d7c8ac66` |
| Executed source | `5eede13aa7a2f765619dbd54251eaa2954d778dd` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | local authenticated FastAPI `TestClient`, SQLite persistence |
| Model/provider/browser calls | none |

While preparing this bundle, a new negative control — a duplicate operation
retried **after a later edit** — exposed a false pass. The retry found the old
audit row, refreshed the canvas mirror with the old content, and the direct
route reported `verified` against that old audit while the later edit was
still the current audit version. `852aaf039` fixes that. `5eede13aa` adds the
two remaining explicit outcome controls (`effect_unknown` and
`no_change_unverified`); its production code is identical to `852aaf039`. All
logs in this directory are from `5eede13aa`; the superseded `326534847` and
`852aaf039` logs are not submitted.

## Route family

| Method | Path | Handler | Writer | Verifier |
|---|---|---|---|---|
| `PUT` | `/api/canvas/{canvas_id}` | `api.canvas_routes.update_canvas_content` | `tools.canvas_crud_tool.update_canvas_content` | `canvas.update` |
| `POST` | `/api/canvas/{canvas_id}/restore` | `api.canvas_routes.restore_canvas_version` | `tools.canvas_crud_tool.restore_canvas_version` | `canvas.restore_version` |

Mounted prefix is confirmed in `backend/main_api_app.py`, which includes both
`api.canvas_routes.router` and `api.canvas_routes.ws_router` under
`/api/canvas`. The focused tests mount the HTTP `router` at the same prefix and
override only authentication/DB dependencies; the real CRUD tool, audit table,
canvas mirror and SQLite persistence run normally.

## What changed

1. **Verified-write service.** `core/canvas_write_service.py` freezes the
   canonical request content, actor, tenant, workspace, target canvas and
   operation before dispatch; it calls the existing CRUD tool and then the
   existing postcondition verifier. It does not add a second store, digest or
   oracle engine.
2. **Canonical content, shared by writer and verifier.**
   `canonical_update_content` and `canonical_restore_content` in
   `tools/canvas_crud_tool.py` are the single representation used by both the
   writer and `core/oracle/postcondition_verifiers.py`, so email normalization
   cannot make the verifier compare against different material.
3. **Scope and identity checks.** The canvas verifier now checks the frozen
   actor, tenant, workspace, target canvas, operation id and restore target.
   It reads its own session; the request session is never passed.
4. **Direct PUT request identity.** The route now accepts optional
   `operation_id` and `expected_prior_audit_id` query parameters. Without an
   operation id, byte-identical edits remain deliberate distinct edits. A
   duplicate operation retry reuses its audit row and adds no second audit.
5. **Honest post-commit outcomes.** A committed write that the oracle cannot
   verify keeps its `audit_id`/`operation_id` (and `restored_from` where
   applicable), is not described as unapplied, and carries
   `replay: do_not_repeat`.
6. **Duplicate-after-later-edit hardening.** A duplicate operation retry only
   refreshes the mirror when its audit row is still the latest version. The
   verifier refutes an `already_applied` result when a later audit is current,
   so the retry cannot claim the later content as its own verified save and
   cannot revert the later edit.

## Outcome contract

`PUT`/`restore` return HTTP 200 for every outcome except a before-write
refusal. A refusal is `400` (bad request), `404` (missing/foreign canvas or
audit) or `409` (stale `expected_prior_audit_id`). A 200 always includes an
explicit `verification` object.

| Top-level `status` | `verification.status` | Meaning |
|---|---|---|
| `verified` | `verified` | Committed effect, exact audit/material/mirror/scope/operation match |
| `no_change` | `verified` | Truthful zero effect; restore target already current; no audit appended |
| `committed_unverified` | `disabled`, `unavailable` or `refuted` | Effect committed (or already applied) but not verified; identity retained; `replay: do_not_repeat` |
| `no_change_unverified` | `disabled`, `unavailable` or `refuted` | No-change outcome not independently verified; identity retained |
| `effect_unknown` | `unavailable` | Append may have committed; identity retained; `replay: do_not_repeat` |
| `refused` | `not_attempted` | Refused before the append; effect `none`; no audit added |

The oracle kill switch (`ATOM_ORACLE_VERIFIER_ENABLED=false`) reports
`committed_unverified` with `verification.status: disabled`. It cannot
fabricate `verified`.

## Failure-first controls (24)

All controls run through the mounted HTTP routes unless marked verifier-level.

| # | Control | Assertion |
|---|---|---|
| 1 | `test_direct_put_is_verified_against_durable_material` | Normal PUT returns 200, `status=verified`, `write_outcome=committed`, exact `audit_id`; fresh readback has +1 audit, exact content and mirror |
| 2 | `test_direct_put_same_title_and_length_still_checks_exact_content` | Same title and same-length content are not sufficient; exact content is compared |
| 3 | `test_direct_put_duplicate_operation_is_idempotent` | Same `operation_id` twice: second is `already_applied`, same `audit_id`, verified, no second audit |
| 4 | `test_direct_put_byte_identical_without_operation_is_a_distinct_edit` | Byte-identical edits without an operation id append two distinct audits and both verify |
| 5 | `test_direct_restore_is_verified_and_append_only` | Restore verifies, `restored_from` is the target, +1 audit, provenance and restored content are durable |
| 6 | `test_direct_restore_no_change_is_truthful_and_adds_no_audit` | Restoring the current version reports `no_change` and appends nothing |
| 7 | `test_direct_put_duplicate_operation_after_later_edit_is_not_verified` | Duplicate retry after a later edit keeps the original `audit_id`, reports `committed_unverified`/`refuted`, adds no audit, and leaves the later audit and mirror intact |
| 8 | `test_direct_put_workspace_mismatch_is_committed_but_unverified` | Workspace mismatch: committed effect retained, `committed_unverified`, `refuted`, `replay=do_not_repeat` |
| 9 | `test_direct_put_stale_prior_audit_is_refused_without_effect` | Stale `expected_prior_audit_id`: HTTP 409, no audit appended |
| 10 | `test_direct_restore_foreign_canvas_is_refused_without_effect` | Foreign user's canvas: HTTP 404, no audit appended |
| 11 | `test_direct_put_oracle_unavailable_preserves_committed_identity` | Oracle returns `None`: committed audit retained, `unavailable`, `replay=do_not_repeat` |
| 12 | `test_direct_put_oracle_refuted_preserves_committed_identity` | Forced refutation: committed audit retained, `refuted`, `replay=do_not_repeat` |
| 13 | `test_direct_put_kill_switch_never_fabricates_verified` | Kill switch: `committed_unverified`/`disabled`, never `verified` |
| 14 | `test_direct_put_verifier_gets_no_request_session` | Captured verifier context has no request `db`; actor/canvas expectations are frozen |
| 15 | `test_direct_put_tenant_mismatch_is_committed_but_unverified` | Tenant mismatch: committed audit retained, `committed_unverified`/`refuted` |
| 16 | `test_direct_put_oracle_exception_preserves_committed_identity` | Oracle exception: committed audit retained, `unavailable` |
| 17 | `test_direct_restore_wrong_canvas_audit_is_refused_without_effect` | Audit from another canvas: HTTP 404, no audit appended |
| 18 | `test_direct_restore_old_identical_material_is_no_change` | An old audit with identical material is a truthful `no_change`, not a new version |
| 19 | `test_verifier_refuses_operation_mismatch` | Verifier refutes an audit whose `operation_id` differs from the frozen operation |
| 20 | `test_verifier_refuses_absent_audit` | Verifier refutes a missing audit id |
| 21 | `test_verifier_refuses_stale_mirror` | Verifier refutes an accepted audit whose canvas mirror is stale |
| 22 | `test_verifier_refuses_restore_target_mismatch` | Verifier refutes a restore whose `restored_from` differs from the frozen target |
| 23 | `test_direct_put_effect_unknown_keeps_identity` | A storage result that may have committed reports `effect_unknown`/`unavailable`, retains `audit_id`/`operation_id`, and says `replay=do_not_repeat` |
| 24 | `test_direct_restore_no_change_kill_switch_is_unverified_no_effect` | A no-change restore under the kill switch reports `no_change_unverified`/`disabled`, effect `none`, and appends no audit |

## Commands and results

Full command lines are in `TEST_RESULTS.md`. Summary:

| Scope | Python 3.14 | Python 3.11 | Log |
|---|---|---|---|
| Direct route family | **24 passed** | **24 passed** | `direct-314.log`, `direct-311.log` |
| Canvas/oracle neighborhood (direct family + canvas routes/CRUD/assignment/oracle/projection/capability/feedback) | **207 passed, 8 deselected** | **181 passed, 8 deselected** | `canvas-neighborhood-314.log`, `canvas-neighborhood-311.log` |
| Canvas action/async controls | **11 passed, 131 deselected** | **11 passed, 131 deselected** | `canvas-actions-314.log`, `canvas-actions-311.log` |
| Accepted feedback/wait regression | **263 passed** | **263 passed** | `feedback-regression-314.log`, `feedback-regression-311.log` |

The 3.14 neighborhood includes 26 `tests/contract/test_canvas_api_contract.py`
tests. Python 3.11 lacks `schemathesis`, so that contract file is excluded
there; the difference is exactly those 26 tests (`207 - 181 = 26`).

## Pre-existing exclusions

These failures reproduce on the base source `81c5962bd`; they are not caused
by this slice and are not counted as coverage.

- `tests/test_covpush_canvasroutes.py::TestCanvasWebSocket`: the fixture mounts
  `router` but not `ws_router`, so all 8 WebSocket tests fail or error
  (`4 failed, 4 passed` on the base). The neighborhood runs deselect the whole
  class.
- 18 unrelated editor/action-registry/async failures in
  `tests/test_chat_canvas_editor.py`,
  `tests/test_canvas_conversation_root_causes.py`,
  `tests/core/test_action_registry_coverage.py` and
  `tests/test_async_turn_continuation.py` reproduce on the base
  (`18 failed, 319 passed`). They are outside the claimed family.
- Python 3.11 has no `schemathesis`; the canvas API contract module is not
  importable there. The 3.14 run covers it.

## Boundaries and remaining open

- **Whole-app ORACLE-01 remains explicitly open.** The historical discovery
  map records 821 mounted mutation-shaped routes / 693 bypass candidates;
  those are discovery counts, not current verified coverage. This submission
  covers only the two routes above.
- Other canvas routes (context/state, logic, WebSocket state updates),
  goals routes, provider writes, multi-worker/soak and PostgreSQL remain
  outside this slice.
- No new approval flow for ordinary saves; no tenant inferred from model
  content; no cross-workspace restore.
- No live model, provider, credential, spend, send, download or deployment
  authority was added.
- Accepted CAS/feedback/wait/episode evidence and closed lanes are unchanged.

## Artifacts

`direct-*.log`, `canvas-neighborhood-*.log`, `canvas-actions-*.log`,
`feedback-regression-*.log`, `base-ws-pre-existing.log`,
`base-editor-pre-existing.log`, `README.md`, `TEST_RESULTS.md`,
`verification.json`, `routes.json`. `MANIFEST.json` records the SHA-256 of
every artifact and the changed source files.
