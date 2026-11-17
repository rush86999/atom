# Learning correction reason and revision history — November 17, 2026

The Learning review already stored every candidate state as an append-only
`ConversationEvent` snapshot, but the product never showed that history and a
correction recorded no rationale. This change adds two narrow things on the
existing surface — no new ledger, table, registry or correction engine:

1. an optional `reason` on the existing candidate revise path, stored with the
   server-derived actor and server timestamp on the existing
   `learning_candidate_revised` event;
2. one read-only `GET /api/conversation-learning/candidates/{id}/history`
   endpoint that projects the already-stored snapshots for that exact
   candidate, plus a collapsed "previous revisions" drawer in the review UI.

Source identity, the compare-and-swap revision guard, confirmation clearing,
promoted-lesson retirement and the approval digest binding are unchanged.

## What is recorded

- `changed_by` is the authenticated caller resolved server-side
  (`_reviewer(user)`); the request body's `changed_by` field is still ignored.
- `changed_at` is the server clock at the write. The event row's `created_at`
  remains the durable recorded time used by the reader.
- `reason` is optional bounded plain text (500 chars). An empty or whitespace
  reason is omitted entirely. Nothing is defaulted; older revisions and the
  creation event therefore report `reason: null` / "Reason: not recorded".

The history reader returns each stored row's own `revision`, `status` and
`digest` as recorded. Digests are never recomputed, and the reader does not run
source revalidation, so an old confirmation is not presented as proof about
current content. Decisions made after a snapshot (confirm, promote, reject,
invalidate) are separate rows that keep their own recorded state.

## Bounds, scope and honesty

- Every row must match the exact `candidate_id`, `thread_id`, `source_kind` and
  the caller's current `workspace_id`/`tenant_id` embedded in the stored
  snapshot. A snapshot bound to another scope is excluded and only counted
  (`out_of_scope_events_excluded`), so a foreign candidate or thread cannot be
  read through this route.
- The ledger has no candidate column, so the thread's learning events are
  scanned with a 2000-row bound that keeps the newest rows. Coverage reports
  `scan_truncated`, `total_events`, `returned`, `limit`, `offset` and
  `has_more`; the UI says "may be incomplete" when the bound was reached
  instead of implying full history.
- The response exposes review-shaped snapshots (lesson text, applicability,
  method status, context/format/conditions with an explicit size marker when a
  stored value is too large to include). It never returns message bodies,
  attachment bytes or a client-supplied history.
- The ledger is unsigned: `signatures.present` is `false` and the drawer says
  the entries are not signed. No hash chain, e-signature or independent-review
  claim is made, and no separation-of-duties policy is added. Recorded actors
  are shown as recorded.

Design reference, not attestation: W3C PROV-O's "revision derives from the
original entity" idea (https://www.w3.org/TR/prov-o/) and the OWASP Logging
Cheat Sheet's event-context and access-control notes
(https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).
Neither is mapped to a schema or certification here.

## User-facing behavior

- Candidate/edit/confirm/promote stays the primary path. The history drawer is
  closed by default and issues no request until explicitly opened; older pages
  load only on request.
- The optional reason is an inline field in the existing edit form. A reason
  with no content change does not save a revision.
- `rejected_reason`, `invalidated_reason` (with plain wording for source
  change/missing/reference tokens) and stale or unresolved evidence are shown
  directly. Rejected and invalidated proposals remain selectable.
- With more than one proposal for a thread, a labeled native select lists up to
  25 entries (plus the current selection) with stable candidate ids, recorded
  status and revision, instead of silently showing only the first row.

## Verification performed in this checkout

Additive tests in the existing whole-file CI selectors only; no ledger, lane or
coverage entries were changed:

- `backend/tests/test_conversation_learning.py`: reason/actor/before-after
  recording, cold-reader persistence, read-only no-revalidation, stale-write
  no-history, reason bounding and absence, foreign-scope/thread exclusion,
  pagination bounds and the scan bound keeping the newest rows.
- `backend/tests/test_conversation_learning_routes.py`: producer→revise (with
  reason)→history→confirm→promote, optional bounded page, append-only rows
  unchanged by later decisions, and unauthorized/foreign/thread/role/
  deactivated negatives through the existing guards.
- `frontend-nextjs/tests/components/ConversationLearningReview.test.tsx`:
  multiple proposals with statuses, lazy truthful history (reason present and
  absent), older-page loading, optional reason present/absent, reason-without-
  change, and invalidated/stale-evidence rendering.
- `frontend-nextjs/tests/lib/conversation-learning-api-revise.test.ts`:
  reason wire passthrough/omission and the history GET contract.

No live backend, provider/model, browser or owner database was used for this
note; independent runtime verification is a separate root step.
