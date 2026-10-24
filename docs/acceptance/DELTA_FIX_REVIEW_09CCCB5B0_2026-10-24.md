# Delta fix review — `09cccb5b0` (independent review record)

**Reviewed commit:** `09cccb5b0b977f86c0a39d59af5b922c83143e7f`
**Scope:** the bounded `[ingested]` paragraph-deletion fix only.
**Verdict from the independent reviewer:** **APPROVE WITH COMMENTS** after
three re-review rounds. The reviewer found no remaining high-severity
deletion in the `[ingested]` path.

## What changed

The attempt-8 rule deleted any first paragraph containing literal
`[ingested]` whenever a later paragraph existed. The fix now:

- requires a numbered source-list entry, a first-paragraph model preamble,
  or a `From [ingested] <source>:` lead;
- requires the same marker/source in the live tool block and a
  whitespace-normalized body excerpt;
- removes only the carrier prefix; the source label and body are kept;
- keeps prefix prose only when it contains an answer-like value;
- preserves marker mentions, explanatory prose, mismatched markers, and
  missing origins whole;
- preserves excerpt-shaped and line-numbered text on explicit quote
  requests;
- keeps the separate line-numbered path behind answer-value, decoy,
  money/percent, superstring, and short-remainder guards.

## Review rounds

1. First review found the quote guard over-triggered on business “quote”
   and the no-origin numbered fallback still deleted prose. Both were
   fixed.
2. Second review found explanatory prose naming a real source and
   answer-bearing carriers. The body-origin check and answer-value guard
   were added.
3. Third review found that any whole-paragraph deletion can still lose an
   answer. The design changed to **prefix neutralization with body
   retention**, which removes the deletion class.
4. Final review: **APPROVE WITH COMMENTS**. Comments were addressed:
   prefix answers retained, source labels retained, quote phrases
   tightened, test names aligned, acceptance pin refreshed.

## Residual, explicitly out of scope

- The line-numbered (`L1:`/`L2:`) path still removes a block when it is
  not answer-value-bearing. That is pre-existing behavior, not the
  `[ingested]` defect; its answer-value/decoy/short-remainder guards are
  tested. A fully semantic line-numbered preservation would be a separate
  change.
- Attempt-5 body retention makes internal fixture metadata (e.g.
  `Owner:`) visible. This is the deliberate safe side of “never delete an
  answer-bearing paragraph.”
- Marker mentions are preserved; the boundary does not promise zero
  `[ingested]` strings in every user-facing answer.

## Controls

The focused suite has 135 passing tests across the answer boundary, chat
history retrieval, finalization seam, chat integration, and chat
orchestrator. Permanent cases include the exact quotation, captured
carrier shapes, marker mentions, explanatory prose, marker mismatch,
missing/mismatched origin, prefix/source-label answers, answer-bearing
hybrids, long tails, two carriers, single quotes, money/percent,
superstring values, hyphenated prose, business quote wording, and explicit
quote requests.

Evidence: commit `09cccb5b0`, `backend/tests/test_attempt4_repairs.py`,
`backend/core/answer_boundary.py`.
