# Employee G5 — durable wait completion episode

Product source: `70a74cd02b5` (branch `codex/brennan-full-app-20261102`).
Frontend build: `ZKXAbjqCRYz-5ML5pGUtJ`.

## Completed goal

One ordinary Assignments UI episode now demonstrates:

**objective → model-chosen wait → useful independent work → process restart →
same-job authorized answer → verified dependent reconciliation → usable
requested document**

| Item | Value |
|---|---|
| Run | `279a603f-fcb4-47a4-b092-c0a5227b8dbc` |
| Wait | `await-c44df7cdb608245de632` (receiving evidence for PO-8841) |
| Independent quote | **370.00 USD**, operation `524e759f-6548-4cf6-ae74-3fdd6118be3f` |
| Restart | same run, same wait identity, status waiting |
| Reply | accepted on the same job; the warehouse receiving record was authorized |
| Reconciliation | **270.00 USD**, operation recorded on `invoice-reconcile` |
| Requested document | `8d0d48773c7e1bca5ee587872f818e0738035d868fb95e7e9245a53f5f6b063e` — composes quote 370.00 and reconciliation 270.00 with source/audit provenance |
| Evidence checks | **24/24** Git artifacts/sources; **16/16** episode checks |

## What is model-chosen vs deterministic

- The served model selected the material external wait (`await_evidence`), its
  fact, subject, expected channel and blocked operation.
- The served model selected the independent quote calculation from the
  authorized price rows while the wait stayed open.
- After the authorized reply, the served model selected
  `invoice_reconciliation`; the compiler inferred the unambiguous invoice /
  purchase-order / receiving roles from accepted evidence.
- Deterministic code supplied step ids, the correlation id, readiness,
  dependency closure, receipt verification, business-result criteria, artifact
  rendering and the consumer routes. No harness plan, formula, line item,
  expected total or wait identifier was supplied.

## Evidence

- `docs/acceptance/evidence/employee_g5_durable_wait_70a74cd02b5/` — the
  two-phase UI episode, raw model requests/responses, routing identity,
  restart, reply, artifact and durable lineage.
- `docs/acceptance/evidence/employee_g5_integrated_change_62fa207647/` — the
  real price-version change with model-chosen reassessment and retention.
- `docs/acceptance/evidence/employee_g5_ui_requested_artifact_c7a265c37/` —
  the first employee-decided requested artifact.
- `docs/acceptance/evidence/employee_g5_regression_b4c29e2b6d9e/` and
  `employee_g5_final_regressions_b4c29e2b6/` — cancellation/late-response and
  controlled uncertainty regression support at their recorded scopes.
- Focused backend verification at this source: **252 passed** across
  business requirements, durable wait, work requests, adaptation, proposal,
  assignment routes/executor, patch/proof/prerequisite and two-domain controls.
  Preflight at the preceding source: **27 passed** (independent completion
  categories, restart, conflicts, cancellation, requirement weakening).

## What the user can now do

The user can start an ordinary objective from the Assignments UI, see what
fact the employee is waiting for, see the useful work already completed and
which result remains unresolved, restart the application without losing the
wait, answer with the authorized record/reply, and receive the requested
document containing both current verified results. The UI explains the
dependency in business language and never asks the user to author a workflow,
wait id, dependency graph or result JSON.

## Remaining limits

- Full G5 remains open. General model judgment, cross-domain autonomy and
  broader served-model quality are not qualified by this episode. Local
  `llama3.1:8b` needed one bounded retry after the reply; the valid model
  choice was then adopted. A model that cannot choose the remaining work
  leaves the business result unresolved and the job unfinished.
- No live/cloud provider, credential, consent, send, spend, download or
  deployment was used.
- Cancellation/late-response and original-operation uncertainty recovery are
  preserved at their accepted scopes, not re-qualified here.
- Historical `111/123`, planner `5/5`, goal router `1/2` and alignment gap
  `3.0` are unchanged.
