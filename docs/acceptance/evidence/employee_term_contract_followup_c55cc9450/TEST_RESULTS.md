# Employee term-contract follow-up — results

Executed source: `c55cc9450`; local `ollama/llama3.1:8b`.

## Deterministic controls

`focused-tests.log` — **235 passed** across typed work requests, bindings,
adaptation contract, attempt journal, proposal seam, assignment executor,
routes, patch invariants and proof binding.

`independent-probes.log` — **6 passed**: the verifier's two exact term probes
(tax-rate cannot authorize freight; expiry between compilation and consumption
refuses) and the four strict typed-work controls.

Key follow-up controls:

| Control | Observed |
|---|---|
| valid `freight_amount` alias | accepted and bound |
| tax-rate term as freight | refused |
| freight term as tax rate | refused |
| rate and amount tax twins | execute to 405.00 / 375.00 |
| expiry between compile and consumption | blocked through executor |
| stale/revoked fact before dispatch | blocked through executor |
| wrong workspace scope | blocked through executor |
| changed authoritative value | blocked through executor |
| restart between compile and consumption | blocked/valid twin still works |
| compiled receipt stripped | blocked |
| legacy caller without marker | documented legacy contract retained |
| tampered receipt value/role | blocked |
| missing authoritative context | blocked |

## Served smokes

`quote-report.json`, `quote-calls.jsonl`:

- model selected the price workbook;
- follow-up `WorkAdaptationProposal` produced `quote_calculation` with
  `Item/Qty/Price` column names and `freight`/`tax_basis` term keys;
- compiler adopted; executor calculated **370.00**;
- raw provider completions captured.

`invoice-report.json`, `invoice-calls.jsonl`:

- follow-up context advertised only `invoice_reconciliation` for the
  PO/invoice/receiving evidence shape;
- the model produced the invoice/PO/receiving bindings;
- compiler adopted; `invoice.reconcile` executed to **270.00**;
- raw provider completion captured.

## Boundaries

Full G5 ordinary-product campaign still open. No cloud/live provider or new
model. Prior deterministic acceptance at `28afe7248` and historical scores are
unchanged.
