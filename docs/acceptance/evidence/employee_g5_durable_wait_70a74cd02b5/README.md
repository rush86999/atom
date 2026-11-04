# Durable employee wait with independent progress — 70a74cd02b5

Status: **one ordinary employee objective persisted a model-chosen external
wait, continued a model-chosen independent quote, survived a real application
restart, accepted the warehouse's authorized receiving record and reply on the
same job, completed the dependent invoice reconciliation, and delivered the
requested review document.** The wait, step and correlation identities were
server-generated; the model supplied none.

## Run

| Item | Value |
|---|---|
| Product source | `70a74cd02b5` |
| Frontend build | `ZKXAbjqCRYz-5ML5pGUtJ` |
| World | `backend/data/acceptance_worlds/g5-wait-episode` |
| Run | `279a603f-fcb4-47a4-b092-c0a5227b8dbc` |
| Wait | `await-c44df7cdb608245de632` · receiving evidence for purchase order PO-8841 from the authorized receiving source |
| Independent quote | **370.00 USD**, operation `524e759f-6548-4cf6-ae74-3fdd6118be3f` |
| Restart | same wait correlation, status waiting |
| Reply | received 2 units, source-bound to the expected channel |
| Reconciliation | **270.00 USD** |
| Artifact | `8d0d48773c7e1bca5ee587872f818e0738035d868fb95e7e9245a53f5f6b063e` (quote 370.00 + reconciliation 270.00) |

## What happened

1. The normal Assignments UI uploaded the price list, purchase order and
   invoice, selected the authorized scope, enabled employee-decided work and
   requested a Document. No wait, step, correlation id, formula, line item or
   plan was supplied.
2. The served local model chose `await_evidence` for the warehouse's
   `receiving` fact on purchase order PO-8841 after the objective named that
   missing record. The compiler bound the correlation, subject, expected
   channel and typed answer.
3. While the wait stayed open, the model chose the ready quote calculation;
   the compiler produced the verified 370.00 USD receipt. The requested
   artifact was deferred until the blocking fact resolved, so no partial
   document was published.
4. The application process was stopped and restarted on the same world. The
   exact run reopened with the same wait correlation and status.
5. The warehouse receiving record was authorized and the reply was delivered
   through the waiting UI. The model then chose `invoice_reconciliation`; the
   compiler produced 270.00 USD and rendered the requested review document
   from that durable result.
6. The independent quote receipt and its operation id remained unchanged; the
   requested review document composes both current verified results (quote
   370.00 and reconciliation 270.00), with the source and audit provenance.
   The document was deferred while the wait was open, so no partial quote-only
   document was published as the objective's deliverable.

## Checks

- 16/16 checks pass
  (`state.json` -> `finish_result.checks`).
- Raw model requests/responses and routing identity: `attempts-start.jsonl` and `attempts-restart.jsonl`.
- Restart and wait evidence: `after-restart.png`, `detail-waiting.txt`.
- Final UI and artifact: `completed.png`, `review.docx`, `state.json`.

## Execution notes

- Both phases ran the same product source `70a74cd02b5` (backend and frontend
  identities recorded at launch). The application processes were stopped and
  relaunched on the same world between phases.
- The initial start capture was interrupted by an operator signal after the
  durable run, wait and independent quote already existed. The same run
  (`279a603f-...`) was resumed, not recreated or upgraded.
- The delivered reply was applied to that same run. The product's asynchronous
  continuation then adopted the model's valid `invoice_reconciliation`
  request; the final state and artifact were read from the authoritative task
  record after the UI poll closed on the intermediate "still required" view.

## Boundaries

- The local model is a configured candidate for the employee profiles; its
  decisions are model-selected, while execution mechanics remain compiler and
  executor owned.
- No live provider, credential, consent, send, spend or deployment was used.
- Cancellation/late-response and original-operation uncertainty recovery are
  preserved at their separately accepted scopes (regression bundles).
- Full G5 and general model judgment remain unqualified; historical counts
  unchanged.
