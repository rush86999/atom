# GOAL-11 email draft shared-writer repair

Source main: `0d5132c2e060a5f2ac338bca143c5e138e607658`.
Baseline audit: `84e0a6362453e865fb63aab8e251867460977338`.
Repair: `8167d919e9e247b24d9fef6507f8f653011b084e`.

This implements root-approved F1-F7 through the existing
`core.canvas_write_service.update_canvas_verified`, Canvas authority,
personal-scope and transactional claim. No new mail engine, store, CAS,
router, review lifecycle or approval engine.

## Runtime changes

- `POST /api/canvas/email/{id}/draft`
  - Resolves the authoritative active actor and exact Canvas read scope.
  - Requires `expected_prior_audit_id`; missing is a typed 409 with
    `current_audit_id`, stale is the shared 409 conflict.
  - Accepts `operation_id` and delegates the native email payload to
    `update_canvas_verified` with current tenant/workspace.
  - Preserves native draft id, thread/attachment/source fields, and returns
    the shared verified/committed_unverified/effect_unknown envelope
    truthfully. It no longer mutates Canvas/Audit directly.
- `EmailCanvasService.save_draft` is retired as a typed refusal. Caller
  inventory: no production caller remains; the public route is migrated and
  legacy service tests assert the refusal.
- `create_email_canvas` resolves the persisted active User row; missing,
  unreadable, inactive or mismatched supplied scope refuses. A guarded
  exact-row no-op `UPDATE users` claim runs in the same transaction as
  Canvas+audit insert, so peer deactivation/move before the DML produces zero
  effects. Canvas/audit use the actor scope, not hardcoded default; adoption is
  restricted to the same scope.
- `GET /api/canvas/email/{id}` uses the shared actor/scope and
  `visible_canvas_material`. Canonical top-level content wins by KEY PRESENCE:
  explicit empty to/cc/subject/body/attachments never resurrects older nested
  draft values. Thread and attachment identity are preserved; no implicit
  reattachment or send.
- Existing generic CanvasPanel `PUT /api/canvas/{id}` is unchanged.
  Attachment/review/send gates are unchanged and their tests remain green.

## Independent root projection evidence

Root's ordinary-path projection twin passed at the baseline audit commit:
`2 passed in 4.21s`, `actual_exit=0`, `same_source=true`
(`root-email-projection-independent-20261110-9nlb_0gv`). Its four
`canvas_email_routes`/`canvas_email_service`/write/authority/crud source
hashes match this repair's route/service/write/authority/crud bytes, so no
projection regression was introduced by the authority/create changes.
Sanitized controls/review are in `root_projection/`.

## Local gates

| Gate | Result | Log |
|---|---|---|
| New public shared-writer suite | 12 passed | `gates/shared_writer_12.proof` |
| Affected email/legacy/PDF/attachment/supersession group | 139 passed | `gates/affected_email_139.proof` |
| Legacy route-shape file | 10 passed, 9 pre-existing fixture failures | `gates/legacy_route_9_pre_existing.proof` |

The 9 legacy route failures are the pre-existing message/categorize fixture
path (base `0d5132c2e` had 13 failures in the same file including save; the
fixture's mock ownership chain never matched). They are disclosed, not skipped
or weakened. All attachment/review/send controls pass.

## New controls

- owner save requires prior, exact email/generic/fresh-SQL/fresh-process body
- stale prior 409 without overwriting peer; operation replay idempotent;
  same operation id with different material refuses
- inactive actor, moved actor, moved target refuse before effect
- create authority race (peer deactivate/move before claim) leaves zero
  Canvas/audit rows
- scoped create is editable through the ordinary generic PUT
- generic PUT after a native save: changed recipient and explicit empty
  cc/subject/body/attachments stay exactly empty; no resurrection
- native attachment identity preserved without duplication
- uncertain and refused writers return truthful envelopes
- ordinary created draft survives a fresh OS process

## Preservation / non-claims

- Baseline audit packet `goal11_email_draft_readback_audit_0d5132c2e` remains
  byte-identical at `84e0a6362`; original negative baseline preserved.
- Root-owned `backend/api/canvas_routes.py` and
  `backend/core/assignment_executor.py` are untouched.
- No CI YAML/goal-index/PR/merge/live DB/provider/model/browser/send/new deps.
- This is API/component scope, not browser or whole-GOAL-11 acceptance.
