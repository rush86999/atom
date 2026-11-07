# TASK-WAIT-01 E2/E3 — two-job isolation and local-grant revocation

Source `7099473aaea41d0478fbe8b8276d0c7f9f5d3a33`. The controlled gate reports
**249 passed**, actual exit 0 (187.68s) on project Python 3.14.7 with
`TESTING=1`, fresh scratch SQLite/data/Lance/office paths and an owned pytest
basetemp.

Both rows are test-only proofs. No product code changed: the existing per-run
assignment lifecycle and the existing source-grant recheck already satisfy
these contracts. Negatives are asserted inside the committed tests, not
inferred from a successful positive run.

## E2 — same-workspace two-job isolation

Two assignments in one workspace start on different opaque purchase-order
subjects (`PO-E2-K7X2`, `PO-E2-Q9M4`) with independent invoice questions.

- `POST /sources` for A's authorized invoice resolves **only** A's question,
  keeps the invoice read, and opens A's distinct receiving question.
- B's open-question object, B's adaptation/model-call count and B's applied
  receipts are byte-identical across that operation.
- The symmetric valid twin answers B's invoice without changing A's next
  question.
- Each job later completes with its own reconciliation (`35.00` for A,
  `80.00` for B); no cross-job receipt or settlement is reused.

Boundary: same workspace only; this does not claim cross-workspace sharing
semantics or served-model decision quality.

## E3 — public source-route local-grant revocation

A waiting quote task answers with a real local connected-catalog parquet
backed by the existing `IntegrationToken` grant. Resolution is DB-only; no
external provider is contacted.

- The owner revokes the local grant while the task waits. `POST /sources`
  returns **403** at resolution, before any dataset read or quote effect; the
  same question stays open and no dependent receipt appears.
- The valid unchanged twin re-activates the same grant and submits the same
  answer. It resolves only that question and the same task completes one
  verified quote of `37.50`.

Boundary: this proves the public source-answer revocation recheck with a local
grant and connected-catalog materialization. It does not claim provider token
refresh, remote OAuth behavior, cross-workspace grants or app-wide
TASK-WAIT-01 acceptance. No live model, provider, credential, send, spend,
guest or deployment action occurred. Root owns CI, PR metadata and final
acceptance.
