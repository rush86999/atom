# Supported capabilities — release `40a55b283`

**Published:** 2026-10-26
**Scope:** limited launch use. This statement is the product boundary for this
release; features outside it are not claimed as complete.

## What this release supports

- **Upload and read supported spreadsheets/documents.** A named uploaded
  workbook resolves to its materialized copy; the answer cites the file, sheet
  and row/cell evidence.
- **Sourced answers and calculations.** Approved-row totals, per-currency
  subtotals and named required-input gaps. A partial result is delivered with
  its known subtotal, its gaps and no grand total.
- **Taught, evidence-bound recommendations.** A taught policy can drive a
  structured Process/Escalate recommendation. The accepted review contract must
  return a validated decision bound to workbook evidence and policy lessons;
  a raw read is never presented as a completed review.
- **Honest gaps.** Missing quantity, price, currency or approvals remain named
  obligations. The product does not invent a total or a decision.
- **Saved history and restart persistence.** Conversations, teaching, resolved
  file identity and delivered results persist. A confirmation reuses the
  accepted objective; a settled lookup is not re-run merely because a later
  turn says “go ahead”.
- **Confirmation and recovery.** An interrupted turn can recover the persisted
  read without a fresh source call. A review that could not be narrated remains
  incomplete rather than false-complete.

## Not in this release

- Mixed-source reconciliation (workbook + email/correspondence) as a completed
  journey.
- Five-order or bulk review workflows.
- General policy transfer beyond the taught policy/lesson in the conversation.
- Unknown-header mapping UX.
- New integrations or provider expansion.
- Automatic sends, approvals, edits or other mutations.

## Operating rule

If a request falls outside this boundary, the product should say what it can
do and leave the rest open. A failed live attempt returns to isolated
diagnosis; live use is not the primary test method.
