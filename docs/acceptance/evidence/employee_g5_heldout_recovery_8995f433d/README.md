# Held-out recovery — original PO-7302 / INV-4491 job at 8995f433d

2026-11-04, America/Toronto.

**Status: same-job recovery of the original held-out timeout job — SUPPORTED.
This is not a fresh held-out content/event-order qualification.** The values
and identifiers became known during the failed run
(`employee_g5_heldout_timeout_6bc97759284`); this bundle preserves that
negative and demonstrates that the same frozen job can finish after the compact
schema-echo repair, with the dependent result and requested artifact verified.

A later concurrent commit `fd6b929f3` adds a separate quote-while-waiting
compact path. It landed after the executed source and is not part of this
recovery's measured result; the 422-test run and 19/19 checks remain tied to
`8995f433d`.

## Frozen job and independent arithmetic

| Item | Value |
|---|---|
| Executed source for this recovery | `8995f433d6fbf2f76a637f7fdce2c2cbf96550e7` |
| Run | `367efddf-c4b3-4e02-9ab2-23c737fd162e` |
| Wait | `await-ca15973cbdcbe5ff480c` (receiving, purchase order PO-7302) |
| Quote | **96.30 USD**, operation `69ffdd84-8ba3-4d90-83de-43551313d432` |
| Reconciliation | **140.25 USD**, operation `69ad7a27-cfb6-4a48-8baa-bf51f9d6616c` |
| Requested document | `review.docx`, sha256 `609281eb3bdc5dd4a42ea14cc389fb60775271bb5225f017a4a2b2fe88474e2b` |
| Recovery checks | **19/19** |
| Focused regression | **422 passed** |

Independent arithmetic (never sent to the model):

```
quote:          4 * 17.25 + 2 * 9.90 + freight 7.50 = 96.30 USD
reconciliation: 3 * 42.50 + freight 12.75          = 140.25 USD
```

The original negative batch selected the wait and the independent quote, kept
96.30 through a real restart and a same-job receiving answer, but the
all-purpose adaptation call timed out (180 s, then 300 s) and the job stayed
blocked with no reconciliation and no artifact.

## What happened in this continuation

1. **Schema-echo failure preserved.** At `3b3f9ef92`, the compact continuation
   reached the served local route in 32.06 s with a 5,669-character prompt, but
   the model returned instructor's injected JSON schema itself
   (`$defs`, `properties`, `required`, `title`, `type`) instead of a proposal.
   The backend log records 7 validation errors and the stage produced no
   proposal. Raw trace: `attempts-schema-echo.jsonl`.
2. **Prompt repair.** `e95d06bc9` names the compact instance shape and adds
   "Return concrete VALUES, not the JSON schema. Never output $defs,
   properties, required, title or type." A local probe of the captured prompt
   returned a valid invoice proposal in 11.8 s. `8995f433d` also exposes the
   requirement's exact `subject_identity` in reasoning views.
3. **One bounded recovery call.** One `/advance` dispatched a single compact
   call (5,997 prompt characters) to the pinned local route
   `ollama/llama3.1:8b` under the declared
   `employee_adaptive_planning_compact` v2026-11-04.1 profile. The model
   returned `decision=replan` with the accepted role step IDs
   (`source-3` invoice, `source-2` purchase order, `source-4` receiving),
   currency USD, and the compact call's own observation ID. The call took
   **57.67 s**, below the 240 s bound; there was no repair, fallback or
   provider substitution.
4. **Adoption and pre-dispatch budget boundary.** The compiler adopted the
   typed request and added `invoice-reconcile` at plan revision 6. The executor
   then refused the step **before dispatch** with
   `assignment_budget_exhausted`: the 900 s wall budget had elapsed while the
   job was blocked during the offline diagnostic gap. The failed step recorded
   `attempts=0`; `advance.json` preserves this boundary.
5. **Supported owner recovery, no database edit.** The owner raised
   `max_wall_seconds` from 900 to 3600 through
   `POST /api/assignments/{run_id}/budget` (increase-only, audited on the
   assignment) and retried the never-dispatched step through
   `POST /api/assignments/{run_id}/retry/invoice-reconcile`. The retry/resume
   applied `invoice.reconcile` with value **140.25 USD**, then applied the
   requested `artifact.document` step and the deliverable.

## Final verified state

| Check | Result |
|---|---|
| Same run and assignment identity | pass |
| Same wait correlation and subject retained | pass (`await-ca15973…`, PO-7302) |
| Quote 96.30 retained | pass (same operation `69ffdd84…`) |
| Dependent reconciliation 140.25 | pass (receipt verified) |
| Assignment completed, revision 6 | pass |
| Business-result criterion declared | pass |
| All required business requirements satisfied | pass (1/1) |
| Overall business outcome satisfied | pass |
| Requested document applied | pass |
| Document contains 96.30 | pass |
| Document contains 140.25 | pass |
| Document sha256 matches | pass |
| No applied external effect | pass (read-only/local steps only) |
| Served route local only | pass (`ollama/llama3.1:8b`) |
| Single compact dispatch, no repair/fallback | pass |
| Compact call within the 240 s bound | pass (57.67 s) |
| Owner budget extension recorded | pass (900 → 3600 s) |
| Pre-dispatch budget refusal preserved | pass (failed step, attempts 0) |

The full check object is `verification.json` (**19/19**). The durable
assignment, final employee-job projection, advance/retry/budget responses and
raw compact attempts are included alongside this README.

## Why this is still not a fresh held-out qualification

- The held-out values and identifiers are now known; the final claim needs a
  new unseen fixture set with new identifiers and values.
- The dependent step was admitted only after an owner budget extension and
  retry of a pre-dispatch refusal caused by the offline diagnostic gap. The
  compact model call itself succeeded inside its bound; the budget action is
  a harness/owner recovery, not a model result.
- The served event order is still wait → independent quote → receiving source
  authorized → restart → exact reply → reconciliation → artifact. The
  alternate order (restart while waiting, source authorized after restart)
  remains undemonstrated.
- The separate HX-1/HX-2/PO-HX-7001 recovery at
  `employee_g5_heldout_continuation_60d464a5f` is a different known-value
  recovery; neither bundle is a fresh unseen qualification.
- Procurement evidence selection and broad adaptive judgment remain open.

## Boundaries

- No live/cloud provider, credential, consent, spend, send, download or
  deployment authority was used.
- The accepted episode at `70a74cd02b5` / `4fd8951cc` is not replayed or
  re-attributed.
- Historical counts (111/123, planner 5/5, goal router 1/2, alignment gap 3.0)
  are unchanged.
- Full G5 remains open.
