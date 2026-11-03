# Employee two-domain served work-request smoke — results

Executed source: `20f3ffc19`; local `ollama/llama3.1:8b`.

## Quote

| Stage | Observed |
|---|---|
| evidence selection | model-backed; price workbook |
| follow-up work request | model-backed `quote_calculation` |
| columns | `Item/Qty/Price` |
| money terms | `freight` / `tax_basis` taught keys |
| compiler adoption | applied |
| executor result | **370.00** |
| raw completion | captured |

Logs: `quote-report.json`, `quote-calls.jsonl`.

## Invoice

| Stage | Observed |
|---|---|
| available operation | `invoice_reconciliation` only (evidence shape) |
| follow-up work request | model-backed invoice/PO/receiving bindings |
| compiler adoption | applied |
| reconcile result | **270.00** |
| raw completion | captured |

Logs: `invoice-report.json`, `invoice-calls.jsonl`.

## Deterministic controls

`focused-tests.log` — **218 passed**:

- proof switches rejected; unverified/skipped evidence refused;
- taught term resolution, amount/currency/scope, tax none/rate/amount;
- prompt shape only response-schema fields; raw malformed completion and
  validation errors preserved under one attempt;
- quote 370.00 and invoice 270.00 twins; one approved bill action compiles;
- preview/full population, stale/duplicate/unknown/forged requests.

## Boundaries

Full G5 ordinary-product campaign remains open. No held-out event/restart/
cancellation/uncertainty campaign, no cloud/live provider or new model. Prior
deterministic acceptance at `28afe7248` remains intact; historical `111/123`,
planner 5/5, goal router 1/2 and alignment gap 3.0 unchanged.
