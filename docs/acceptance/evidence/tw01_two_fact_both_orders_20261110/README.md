# TASK-WAIT-01 joined two-fact, both-order, actual-process episode (2026-11-10)

Status: **bounded controlled-mechanism PASS**. Not a general autonomy,
live-provider, ordinary-browser, actual multi-day soak or whole-app claim.

## Source and scope

- Product source: `0d5132c2e060a5f2ac338bca143c5e138e607658` (current main)
- Branch: `codex/web-tw01-two-fact-joined-20261110`
- Test-only additions:
  - `backend/tests/process_support/task_wait_two_fact_process_worker.py`
  - `backend/tests/test_task_wait_two_fact_two_order_process.py`
- Product/backend/frontend source diff: **none**
- Runtime authority: private scratch SQLite/data/LanceDB/office roots; no live
  development DB or live provider/model.

## Existing evidence reconciled before this episode

| Existing control | What it already proved | Why it did not close this slice |
|---|---|---|
| `test_task_wait_two_fact_events.py` | Two sequential facts (invoice then receiving) on one assignment, no premature artifact, final document | In-process route fixture; one order only; no real OS restart |
| `test_task_wait_source_continuation_regressions.py` | Order A restart-before-answer and Order B accept/interrupt/replay; duplicate/cancelled/irrelevant negatives | One missing fact |
| `test_task_wait_process_recovery.py` | Real OS child restart, one missing prerequisite, recovery without model poll/replay | One missing fact |
| `test_task_wait_independent_work.py` | Independent quote work while a fact is missing; final artifact stays blocked | One missing fact; not joined with both-order restart |
| `test_generic_information_multiday_contract.py::test_two_missing_facts_span_two_weeks_same_job` | Two missing facts over a controlled 7+7-day clock, same job | Generic information-wait path, not the assignment/public-route two-fact process episode; not actual soak |
| G5 `employee_g5_heldout_two_order_fresh_3ccad7a5a` | Both restart orders with a real local served model | One missing fact (receiving); served-model campaign not reusable under this no-model authorization |

The actual gap was therefore: **two distinct missing facts, in both arrival
orders, on one assignment, across real OS process restarts, with no model
call**. This episode fills exactly that gap.

## What the new episode proves

One assignment starts with only the purchase order, so both invoice and
receiving are genuinely missing. The controlled proposal transport chooses the
requested first missing role and never supplies a final plan or expected
result.

For **both orders** (`invoice -> receiving` and `receiving -> invoice`):

1. The first fact is missing; one durable question is open; no reconciliation,
   no artifact, not completed.
2. A fresh process delivers the first authorized source; the same job asks for
   the second fact; still no reconciliation/artifact/completion.
3. A fresh recovery process sees the same open second question and makes
   **zero** adaptation calls; no model poll, no advance, no result.
4. A fresh process delivers the second authorized source; the same job
   completes with one reconciliation (`140.25`), one current document artifact,
   two answer source records with source versions, and no open questions.
5. A duplicate second delivery in a fresh process is inert: one reconciliation,
   one artifact, zero adaptation calls.

The final document is read from disk, its sha256 matches the applied receipt,
and its `word/document.xml` carries the current verified total.

## Reused controls in the same focused gate

The focused 33-test gate also reuses:

- independent useful work during wait (`test_task_wait_independent_work.py`);
- sequential two-fact completion (`test_task_wait_two_fact_events.py`);
- two-job isolation (`test_task_wait_two_job_isolation.py`);
- irrelevant/duplicate/cancelled/replay negatives
  (`test_task_wait_source_continuation_regressions.py`);
- source revocation/version-after-acceptance controls;
- artifact-content guard;
- real-process one-fact recovery;
- the controlled 7+7-day two-fact clock twin.

No actual days/soak is claimed; the clock seam and durable timestamps are the
only multi-day evidence.

## Ordinary UI boundary (truthful negative)

The ordinary assignment panel sends `use_model: true`
(`frontend-nextjs/components/assignments/AssignmentPanel.tsx`), and the public
`POST /api/assignments/from-objective` route creates an LLM-backed adaptation
when `use_model` is true. This slice has **no provider/model authority**, so a
browser objective campaign was not run and no ordinary-UI pass is claimed.
The bounded episode uses the same public assignment route with the repository's
existing controlled proposal transport in real child processes. The exact
source boundary is in `ui-boundary-check.log` / `ui-boundary.json`.

## Gates

| Gate | Result |
|---|---|
| New joined two-order process test | **2 passed** (both orders) |
| Focused reused + joined controls | **33 passed** |
| Product/backend/frontend diff | **none** |
| Model/provider call | **none** (controlled transport) |
| Live DB / live account / send / spend | **none** |

## Not claimed

General adaptive judgment, live served-model quality, ordinary-browser
objective creation, actual multi-day soak, PostgreSQL/multi-worker/soak,
mobile and whole-app completion remain unqualified. The canonical 143-claim /
18-goal catalog is unchanged.
