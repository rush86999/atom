# Employee two-domain served work-request smoke — source 20f3ffc19

Status: **preparation evidence; both domain work requests are now served-model
backed and deterministically compiled. Full G5 ordinary-product campaign
remains open.**

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `20f3ffc19` |
| Local model | `ollama/llama3.1:8b` at `127.0.0.1:11436/v1` |
| Transport | controlled local service/DB; no cloud/live provider |

## Quote smoke — passed

`quote-report.json` / `quote-calls.jsonl`:

- initial model evidence proposal: model-backed, selected the price workbook;
- follow-up `WorkAdaptationProposal`: model-backed valid
  `quote_calculation` with `Item/Qty/Price` column names and
  `freight`/`tax_basis` term keys;
- compiler adopted; executor calculated **370.00**;
- raw provider completions captured.

## Invoice smoke — passed

`invoice-report.json` / `invoice-calls.jsonl`:

- follow-up context advertised only `invoice_reconciliation` because the
  accepted evidence shape is PO/invoice/receiving;
- the 8B produced a valid `invoice_reconciliation` request binding invoice,
  purchase order and receiving handles;
- compiler adopted; `invoice.reconcile` executed to **270.00**;
- raw provider completion captured.

## Deterministic controls

`focused-tests.log` — **218 passed** across typed work requests, bindings,
adaptation contract/attempt journal, assignment executor/routes and patch
invariants.

- mandatory verified evidence (model proof switches removed);
- taught term resolution, amount/currency/scope checks, tax none/rate/amount;
- strict prompt/response schema and raw malformed-completion capture;
- quote 370.00 and invoice 270.00 deterministic twins;
- one approved bill action compiles through the registered external action;
- preview/full population, stale/duplicate/unknown/forged requests.

## Still open

The held-out two-domain ordinary-product campaign with changed evidence,
independent progress, restart, cancellation and uncertain-effect recovery is
not yet run. G5 adaptive employee capability remains unqualified. No cloud
provider, credential, consent, send, spend or deployment. Prior deterministic
acceptance at `28afe7248` remains intact; historical `111/123`, planner 5/5,
goal router 1/2 and alignment gap 3.0 unchanged.
