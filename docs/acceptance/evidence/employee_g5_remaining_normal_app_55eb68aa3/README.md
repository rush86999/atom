# Employee G5 remaining normal-app behaviors — 55eb68aa3

Runtime candidate: `55eb68aa30be5f698f11a6b2da19628a4f902d97`
(branch `codex/brennan-full-app-20261102`). The worktree was clean at run
time. The serving identity reported `source_id=55eb68aa30be`, `dirty=false`
before the controlled restart and again after it.

This bundle records one normal-application backend/world for the remaining
employee G5 behaviors. It is API-level normal-app evidence, not a browser UI
journey. The browser artifact/final user journey remains with Agent 1.

## What passed

1. **Requested document artifact**
   - Objective: "Prepare the customer quote document".
   - Authorized source: uploaded `price-book.xlsx` (workbook index text).
   - Document deliverable: `customer-quote.docx`.
   - Exact arithmetic: `2*100.00 + 3*50.00 + 20.00 freight = 370.00 USD`.
   - The assignment completed only with the `artifact_verified` criterion
     met, artifact status `applied`, and a recorded sha256 equal to the
     tracked `customer-quote.docx` bytes.
   - The document text contains the source file name, both line items and
     `370.00`.

2. **Independent branch while waiting, and selective retention**
   - A real durable wait (carrier rate confirmation) kept the assignment in
     `waiting`.
   - A deterministic plan patch added two independent calculation branches.
     Both applied while the wait remained open, with distinct operation ids.
   - `branch-a` was invalidated as changed evidence. It re-ran under a new
     operation id with `prior_result_count=1`; `branch-b` kept the exact same
     operation id, value and summary; the waiting operation id was unchanged.
   - The branch patch is a deterministic control, not a model choice.

3. **Cancellation plus late response**
   - The still-waiting assignment was cancelled.
   - A late response for its correlation id returned HTTP 409 and did not
     resume work.
   - Completed branch receipts and operation ids survived cancellation.

4. **Controlled provider acceptance / lost confirmation / restart /
   reconciliation / no resend**
   - A controlled outbound effect awaited explicit approval.
   - After approval the provider accepted and the confirmation was lost:
     the step was `uncertain`, the assignment `blocked`, and the controlled
     outbox contained exactly one effect.
   - The real process restarted. The same run and original operation id
     remained uncertain; the outbox hash and one-effect count were unchanged.
   - Reconciliation `applied` bound the outbox evidence and the original
     operation. The assignment completed, the operation id stayed the same,
     and the outbox still contained exactly one effect (same sha256).

## Exact identities

| Item | Value |
| --- | --- |
| Artifact run | `d95de400-2c28-421d-81fa-95abb94e239d` |
| Artifact sha256 | `09a43610ee6c7a6989dc04d44c34a278662b8f061056040e3cb0db83a156f986` |
| Branch/wait run | `e2721197-19bc-4600-b3a8-a5a237e65095` |
| Branch A before/after | `3f2d9ef1-caf0-437a-8e77-1693992cc603` / `b9eca3eb-c393-4072-b6d5-efd80953424e` |
| Branch B retained | `d40c8b37-0feb-42fa-a426-ea101a8a0ce5` |
| Waiting operation | `17432523-a1b2-409e-992c-9d52841fdd95` |
| Uncertain run | `162f64f5-cd17-4438-9597-b48325cfc1a5` |
| Uncertain original operation | `8fb20294-a401-4912-ae8c-e3e6fe235b1e` |
| Outbox sha256 before/after | `860aaa53b286fcc0784dc03288528a489b054b9c5569bd7035a6ee972f5e8cbf` |

## Tests

`focused-tests.log`: **305 passed** in 66.05 seconds across assignment
routes/executor, employee proposal/adaptation/work requests, retained source
scope, prerequisite eligibility, patch invariants, proof binding, campaign
guard, document freshness, and the prior verifier probes.

`harness-run.log`: **18/18** campaign checks passed on the clean source.

## Boundaries

- No live provider, credential, consent, send, spend or deployment authority.
- The artifact was requested through the existing explicit deliverable route;
  this bundle does not claim that a served model selected the artifact itself.
- The independent branch was added by a deterministic, versioned plan patch;
  it is not model-selected branch discovery.
- The browser artifact/final user journey and served-model artifact choice
  remain open for Agent 1.
- Historical 111/123, previous tags/sources, planner 5/5, goal router 1/2 and
  alignment gap 3.0 are unchanged.
