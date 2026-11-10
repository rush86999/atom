# Canvas restore visible-material repair — 202f99799

**Status: submitted, withheld; not accepted.** Root independently reviews.

Executed source: `202f99799` on `codex/web-canvas-restore-ordering-20261110`,
successor to withheld `b33489fe1` / evidence `29c9771fc`. The predecessor
packet and accepted authority source `82b29cfcc` / evidence `79b47bc27` are
unchanged.

## Root negative before this repair

Root probe `/private/tmp/root-canvas-restore-visible-contract-20261110.py` at
`29c9771fc`: **2 failed, 0 passed**.

1. Target title `Reviewed title`, current title `Accidental title`, same body:
   restore returned `no_change=True`, visible title stayed `Accidental title`.
2. Older body, requested body at the same timestamp as a contentless event:
   `latest_canvas_content_audit` saw the requested body, but `read_canvas`'s
   bounded `< created_at` fallback served the older body; restore returned
   `no_change=True` while the visible body was still older.

## Repair

- `visible_canvas_material` is now the single audit-trail selection used by
  both `read_canvas` and `restore_canvas_version`.
- Latest row uses the established `created_at, id` ordering; the latest body
  row is retained as content provenance, so ordinary reads return the actual
  body `audit_id`/`created_at` instead of `None`.
- Fallback streams bounded batches over full history with no 10/50 total cap;
  same-timestamp content rows remain eligible.
- Existing `_EVENT_ONLY_ACTIONS` is the event policy; no second drifting action
  list. Submit rows never become content. Sent-email rows are normally
  contentless and are skipped by body-key presence.
- Falsy bodies (`""`, `0`, `[]`, `{}`) are preserved by key presence; email
  draft shape, office refresh and type-pin/coercion remain in the shared
  selection.
- No-change now compares canonical body, resolved type/pin policy, and a title
  when the target explicitly supplies it. Explicit empty title is restored;
  a missing title preserves the current title. A genuine current body+title
  twin still appends nothing.
- Append-only history, strict-recency append, `restored_from`, scope/authority,
  receipts and replay are unchanged. No new store, version engine or schema
  migration.

## After

- Root probe at this source: **2 passed** (2.88s-class focused run).
- New deterministic suite: **16 passed**.
- Focused reader/restore/oracle/lifecycle/crud/list/present/fork/receipt/form/
  feedback group: **420 passed in 123.03s**.
- A contentless/latest event cannot create a false no-change; a body behind 60
  event stamps is still visible; explicit empty title is preserved; repeat
  restore is no-change without a second row.

Raw logs, scratch DBs and tokens remain private under `/private/tmp`.

## Caller impact

- `read_canvas` now reports the actual body `audit_id`/`created_at` for an
  ordinary latest body; same-time body rows and full history are considered;
  submit events are not content.
- Restore no-change is stricter: title and resolved type/pin are material.
- The oracle identical-material fixture now sets the same title because title
  is part of restored material.

## Limits

- No browser, live DB, provider/model, install, deployment, PR or merge.
- No broad-suite or Python 3.14 claim.
- This packet is submitted and withheld pending root independent review.
