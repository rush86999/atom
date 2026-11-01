# Brennan joint quote/knowledge handoff — 2026-11-01

Status: **agent implementation + focused integration**, not verifier acceptance
and not a live-provider qualification. The accepted 111/123 milestone is
unchanged and remains source-bound to its own tag.

## Sources

| Item | Value |
|---|---|
| Common base | `587fbc25148a6203f3785c46e56992ddcf54bd70` |
| Agent 1 branch | `codex/brennan-employee-intelligence-20261101` at `1ec6b8c37` |
| Agent 2 branch | `codex/brennan-knowledge-accounting-20261101` at `0e33928b1` |
| Joint integration | `codex/brennan-joint-integration-20261101` at `3c98b09b1` |
| Joint backend tree | see `git rev-parse 3c98b09b1:backend` |
| Configuration | local scratch SQLite/artifact stores, controlled actions, no live Zoho/Microsoft credentials |

## Implemented

### Agent 1 — employee execution and quote composition

- `execute()` no longer returns at the first waiting branch; Supplier A can
  wait while Supplier B's independent branch completes.
- Assignment-level idle ledger (schema 2): pause credit only while no branch can
  progress; overlapping waits union; open idle checkpoints across restart;
  0-40/40-80/80-90/90-100 oracle yields working 50s / paused 50s.
- Evidence requirements derived before retrieval; typed receipts select exact
  customer/agreement/line identities; obsolete, unauthorized, supplier-cost and
  embedded-instruction sources are excluded or flagged; missing/conflicting
  facts return obligations/conflicts with no plan.
- Quote plan composes typed line items through the registered `quote.calculate`
  adapter; exact Decimal arithmetic, scoped discount rules, packaging identity,
  currency/unit/pack and explicit tax/rounding.
- Quote route journey: 362.50 artifact + email draft; supplier-freight wait
  resumes the same job at 362.50 and refuses a duplicate reply.
- Public-route service proposal (hours/rates, CAD, 630.00) and non-sales
  expense-policy assessment (50.00) use the same executor/calculator.
- Explicit reassessment re-binds quote discount rules/artifact format from the
  corrected teaching; old job changes 362.50 → 355.00 with prior results kept,
  new work adopts the correction without mutating the accepted snapshot.
- Fixed retrieval evaluation: 8/8, selection/sufficiency 1.0, zero unsupported
  readiness, mean 0.045 ms.

### Agent 2 — connected contracts

- Provider contract repairs for Zoho/Microsoft; typed error envelopes instead of
  empty arrays; CRM argument shape; organization/data-center scope.
- Registered reads: WorkDrive/OneDrive page/file, CRM record/search, inventory
  item/stock, Books bill/estimate; draft/proposal actions including estimate,
  bill create/readback and Outlook draft.
- Write payload signing, exact duplicate identity, readback, uncertain outcomes;
  drive page checkpoints and coverage status.
- Agent 2 focused suite: 149 passed (its branch).

## Joint integration results

| Suite | Result |
|---|---|
| Assignment routes + executor + quote + evidence | 124 passed |
| Agent 2 connected/read/checkpoint/bookkeeping | 41 passed |
| Joint focused integration | **166 passed** |
| Retrieval evaluation | **8/8** |

### Demonstrated outcomes

- Multi-source quote route → **362.50** DOCX with 5% exception on B only.
- Supplier wait → correlated reply → same job **362.50**; duplicate reply refused.
- Service proposal route → **630.00** CAD.
- Expense-policy route/scenario → **50.00**.
- Teaching correction + explicit reassessment → **355.00** on the old job,
  prior 362.50 preserved.
- Controlled commercial update duplicate/uncertain reconciliation path passes.

## Boundaries and limitations

- **No live Zoho/Microsoft credentials** were used. Provider reads/writes are
  controlled/fixture-qualified; this is not live-provider reliability.
- **Outlook draft only.** The previous one-use send authorization is exhausted
  and was not reused; no send occurred.
- The quote route evidence test supplies typed line items directly; the
  connected-read quote test uses a controlled `action.registry` customer read.
  WorkDrive/OneDrive **content parsing into quote rows** is not yet wired into
  the public quote journey — Agent 2 ingestion/read receipts and Agent 1's
  evidence selector are integrated at the contract/adapter level, not yet in
  one browser journey.
- The quote-specific wait is route-controlled; the real browser close/backend
  restart and source-revision invalidation controls remain the accepted generic
  recovery controls, not yet repeated on this new quote path.
- Cancellation/duplicate/uncertain quote controls are route-level; no new live
  effect.
- Feature breadth remains **111/123**; these business workflows are additional
  acceptance gates, not a denominator change.

## Next executable steps

1. Consume Agent 2 WorkDrive/OneDrive read receipts (content_b64 + parsed typed
   rows) in the evidence selector, with source/version/citation.
2. Run the quote journey through the browser: RFQ → connected reads → quote →
   wait → source change → real restart → corrected response → controlled Zoho
   update → Outlook draft.
3. Repeat duplicate/cancel/uncertain controls on that journey and submit one
   source-bound joint bundle.
