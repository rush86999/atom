# Employee-decided requested artifact — source c7a265c37

Status: **the normal Assignments UI produced a requested DOCX from the
employee's own evidence-derived quote calculation. The compiler added the
artifact step after the verified typed receipt, rendered it from durable
results, and the run completed only with the artifact criterion verified.**
No line items, formulas, executable steps, final rows or document body were
supplied by the harness.

## Source and run

| Item | Value |
|---|---|
| Product source | `c7a265c37` (requested artifact for quote and procurement; business-ordered artifact columns) |
| Frontend build | `X8jwE6ACQOmwiGXPFjzKD` (`next build --webpack`; UI source identical to `f2aa6518d`) |
| World | `backend/data/acceptance_worlds/g5-ui-requested-final` |
| Returned run | `6e51794a-2d0b-43f2-bbfe-18a0884a1487` |
| `/from-objective` status | HTTP 200 |
| Selected authorized sources | 1 (price-book.xlsx / Prices) |
| Agent proposal source | `model`, `technical_fallback=false` |
| Model-chosen work | `quote_calculation` |
| Final status | completed / satisfied |
| Artifact SHA-256 | `a6b8fffdb6d32dc6f2680310659db375ec71d3a7bd9ef0eef1996141ecee7583` |

## What the employee did

1. Read the one authorized workbook (two rows of `Item`, `Qty`, `Price`,
   `Currency`) through the normal `dataset.read` adapter.
2. The served local model chose `quote_calculation`, mapping `Item`, `Qty`
   and `Price` and binding the user's taught commercial terms (USD, freight
   20.00, tax none). The compiler deterministically resolved optional
   columns from the accepted schema and recorded that observation; no step
   mechanics, formulas or rows came from the harness.
3. `quote.lines_from_rows` derived the line items from the read rows;
   `quote.calculate` produced the verified receipt: A 2 x 100.00 = 200.00,
   B 3 x 50.00 = 150.00, freight 20.00, total **370.00 USD**.
4. The compiler appended `requested-artifact` (`artifact.document`) depending
   on `quote-total`, with `compose_from_results` and a verified-receipt
   requirement. The document rendered from the durable `quote.calculate`
   result, not from a supplied body.
5. The `artifact_verified` completion criterion was required and met. The
   assignment completed only after the artifact was applied and hashed.

## Independent checks

- The captured `/api/assignments/from-objective` request contains
  `requested_output=document`, the source handle and teaching terms; it has
  no `line_items`, `deliverables`, steps, formulas or final total.
- Independent arithmetic from the uploaded rows:
  `2*100.00 + 3*50.00 + 20.00 = 370.00`.
- `receipt.total == 370.00`; receipt line nets are `A=200.00`, `B=150.00`.
- The artifact was downloaded through the UI `Download` control and the API;
  both byte streams are identical and match the recorded `sha256`.
- Extracted DOCX text contains `370.00 USD`, both line items with their
  `Net` values, the source label, human-facing column labels (`Item`,
  `Description`, `Qty`, `Unit price`, `Discount`, `Net`, `Currency`) and an
  `Audit` section with step/source identity.
- UI text shows the exact returned run completed with `Result: 370.00 USD`.

## Boundaries

- The guided/manual artifact path and calculation-only objectives remain
  separate supported paths and are unchanged.
- The harness supplied the user's taught commercial terms through the
  existing UI field; it did not supply line items, totals or a document body.
- The upload is a workbook-derived `dataset.read`; the same artifact path is
  covered by a procurement (`invoice.reconcile`) route test, but this
  browser run exercises the quote domain.
- A real source quantity/price version change with selective retention and
  controlled cancellation/uncertainty remain separate gates in this batch.
- No live/cloud provider, credential, consent, send, spend or deployment was
  used. Historical 111/123, planner 5/5, goal router 1/2 and alignment gap
  3.0 remain unchanged.
