# Conversation-derived learning evidence — 554b462

Source commit: `554b46272143749c3fde78ad0a0f95b88c2d8dec`  
Source tree: `862cd064da37d2daf886a861707480fdab653c04`

This is a **separate successor phase**. It does not move or relabel the
accepted local-core tag `local-core-2026-10-30-final` (`da9cc8b12`) or its
historical browser/live evidence.

## Implemented boundaries

- Candidate/review ledger: existing append-only `ConversationEvent`.
- Resource identity/version/access: existing `DatasetEntry` catalog and
  assignment resource-binding contract.
- Accepted teaching: existing `journal_standing_lesson_entry`.
- No new graph database, vector index or parallel knowledge store.

## Verifier-facing behavior

- Explicit provider attachment identity resolves.
- Same-name attachments with two catalog rows stay ambiguous.
- “Previous workbook” resolves only when exactly one prior resource exists.
- Punctuation is identity: `rates-2026.xlsx` does not bind to
  `rates 2026.xlsx`.
- “Usual method” remains unresolved until an explicit method is confirmed.
- Conflicting examples produce a blocking conflict, not a fabricated rule.
- Missing units block arithmetic.
- Source version changes invalidate reuse while preserving the old lesson.
- Cross-workspace resources are `access_denied`.
- Quoted text is not authority; permission-expanding lessons require the
  authored authority excerpt itself to state the expansion.
- Restart reloads unresolved dependencies and confirmations from the ledger.
- Changed candidate content clears the old confirmation/digest.
- Rejection writes no lesson.
- Correcting one lesson leaves unrelated lessons intact.
- A promoted lesson carries its structured method and applies it to new rows
  in two domains (sales pricing `20.00`, payroll-style `16.50`).

## Results

| Suite | Result |
|---|---|
| Conversation-learning service/routes | **22 passed** |
| Assignment regressions | **126 passed** |
| Teaching/renderer regressions | **137 passed** |
| Frontend review panel | **3 passed** |
| Frontend targeted (4 suites) | **34 passed** |
| TypeScript `--noEmit` | clean |

Logs: `conversation-learning-tests.log`, `assignment-regressions.log`,
`teaching-regressions.log`, `frontend-learning-tests.log`,
`frontend-targeted-tests.log`, `typescript-check.log`.

Direct reproduction: `conversation-learning-repro.json` (explicit attachment
resolved; same-name attachments ambiguous; sales/payroll method values;
quoted authority rejected; candidate review-ready).

## UI

`/learning` lists persisted local email threads and presents the evidence
chain, unresolved questions, and confirm/promote/reject actions. It does not
require raw filesystem paths or JSON.

## Bounds

Only persisted local email-canvas audits are read. No live mailbox access,
token refresh, real send, credential change, source writeback, arbitrary URL
fetching or recursive resource traversal was performed. Reference detection
is deterministic, not an LLM extractor; candidate creation is explicit.
Hosted deployment, publication, source shutdown and additional real sends
remain deferred and unauthorized.
