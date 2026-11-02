# Joint repair batch — 2026-11-01

Single review candidate: `codex/brennan-joint-review-20261101` in
`/private/tmp/atom-brennan-review`.

This batch closes the reproduced blocking defects:

1. a missing discount qualification selected the general discount;
2. sparse/wrong estimate and bill readbacks returned zero conflicts;
3. returned `uncertain` action envelopes were not proven through a real
   assignment using the actual connected handler;
4. capped/fixed/unsupported pricing rules silently applied only the rate.

No live Zoho/Microsoft call, write, refresh or send was performed.

## Candidate composition

- Agent 1: `0aebf372e` (discount three-valued resolution, completion oracle,
  durable line-scoped obligations, executor outcome hardening).
- Agent 2: `7a006c147` (complete commercial readback verification, sparse vs
  mismatch, bounded retry, estimate/bill normalization).
- Joint integration on the review branch: `quote.lines_from_rows` and
  `quote.estimate_lines`, one-assignment byte→quote→estimate→draft flow, and
  real-handler uncertainty control.

## Discount resolution

- Every candidate rule is true, false or unknown.
- The highest-specificity established rule is selected, then unknown rules
  that could supersede or tie it are considered.
- A clarification is raised only when the remaining possibilities change
  material pricing (Decimal-normalized rate/cap/basis).
- Unknown conditions are never treated as false.
- Obligations bind assignment, line identity, missing field, candidate rules
  and revisions, accepted context and source versions.
- Answers resume the same work; duplicate answers do not reopen it; restart
  preserves the question; changed teaching/source refuses stale answers.
- Completion-based test oracle enumerates fully specified completions.

## Unsupported pricing semantics

The calculator now validates every discount rule before selection or
arithmetic. A simple fractional rate is implemented. Caps, fixed amounts,
tiers, formulas, unsupported bases/types and unknown material fields are
refused with a typed `QuoteInputError`; `_quote_calculate` maps that to a
`quote_input` gap and the public assignment route rejects the plan before any
commercial effect. Tests cover caps, cap amounts, max discounts, fixed
amounts, formulas, tiers, unsupported basis/type and unknown fields, plus a
public-route proof that no action is called.

## Commercial readback

- Effect observation and desired-state verification are separate.
- A remote id plus total is incomplete, not verified.
- Customer/vendor, currency, dates, reference/terms, lines, quantity, rate,
  account, discount, tax and totals are compared.
- Lines are a canonical multiset keyed by stable identity; order is ignored,
  duplicates preserved, equivalent Decimals accepted.
- Missing expected field -> incomplete; present but different -> mismatch;
  complete and equal -> verified.
- A sparse first readback is re-read once from the same remote object; the
  create is never repeated.
- Conflict/incomplete preserve remote id, payload digest and operation
  identity; dependent work stays blocked.
- `verification.status=verified|incomplete|mismatch` and
  `action_result=applied|proven_not_applied|uncertain|conflict|unavailable`
  are returned together.

## Executor consumption

The real `connected.books.create_estimate` handler is used with a controlled
provider that records acceptance then loses the response:

1. assignment starts; estimate awaits approval;
2. approve; handler returns `action_result=uncertain`;
3. assignment becomes `uncertain`, not completed;
4. dependent Outlook draft stays blocked;
5. new executor over the same lifecycle resumes with no second create;
6. reconciliation settles the original operation;
7. draft approval then creates the draft once; no send.

## One-assignment business loop

`tests/integration/test_brennan_joint_document_flow.py` runs one assignment:

1. `connected.workdrive.read_file` returns controlled CSV bytes;
2. `quote.lines_from_rows` maps runtime rows to quote lines;
3. `quote.calculate` pauses on a missing qualification;
4. the durable obligation is answered with `unlicensed`;
5. the same assignment resumes and computes **362.50**;
6. `quote.estimate_lines` prepares provider lines;
7. authorized `connected.books.create_estimate` runs once;
8. the complete readback is verified;
9. approved `connected.outlook.create_draft` uses the verified total;
10. no send occurs.

`tests/unit/test_quote_rows.py` covers percentage/amount discount mapping, missing identity/currency gaps, empty rows and provider-line flattening.

A second control changes the returned file price from 50.00 to 55.00 and
asserts the quote changes to **376.75**, proving the calculation consumed the
returned bytes rather than pre-seeded lines. An unexpected customer in a
connected receipt prevents `plan_quote_assignment` from producing a plan even
when line items are supplied.

## Test evidence

| Suite | Result |
|---|---|
| Joint core (assignment + quote + evidence + routes + joint integration + readback + connected + row mapping) | **241 passed** |
| Agent 2 focused provider/accounting/readback | **273 passed** |
| Agent 1 required assignment suite | **164 passed** |
| Public route quote/source-change/teaching-reassessment journey | **4 passed** |
| Extended assignment/action-registry suite | **334 passed, 4 pre-existing baseline failures** |

The 4 failures are turn-count/LLM-orchestration tests in
`tests/test_task_lifecycle.py`; they reproduce at baseline `acd86a2aa` without
this batch.

## Browser journey

Installed the documented frontend dependencies (`npm install
--legacy-peer-deps`) and Playwright Chromium in the review worktree. The
browser gate `scripts/acceptance/brennan_connected_browser.cjs` runs the real
Assignments page against the standalone acceptance server (real routes and
executor, controlled connected providers):

1. connected CSV bytes are read and parsed;
2. the discount qualification clarification is shown;
3. the page is left and the backend process is restarted;
4. the connected source bytes change from 50.00 to 55.00 and the read branch is
   invalidated;
5. the qualification is answered in the browser;
6. the corrected quote reaches estimate approval;
7. the estimate readback is **376.75**;
8. the Outlook draft body is **376.75**;
9. reloading shows the completed assignment.

Result: **9/9 checks passed**. Evidence:
`docs/acceptance/evidence/brennan_connected_browser_20261101/`
(`checks.json`, screenshots, backend logs). No live provider or send was
used; the controlled Outlook fake refuses `send_email`.
