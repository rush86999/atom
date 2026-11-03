# G5 evidence selection at current source — procurement negative

Status: **the typed work-request path now passes both served domains when the
accepted evidence is supplied; the upstream procurement evidence-selection
step still fails on the declared local 8B. Full G5 remains unqualified.**

## Source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `20f3ffc19` (served quote + invoice work requests, bill compilation) |
| Evidence tip at run | `ce0b69626` |
| Local model | `ollama/llama3.1:8b` at `127.0.0.1:11436/v1` |
| Policy | `ATOM_LLM_PROVIDER_POLICY` pinned to `ollama` for the scratch run |

## Result

`evidence-selection-report.json` / `evidence-selection-calls.jsonl` preserve the
two held-out evidence-selection contexts.

| Domain | Observed |
|---|---|
| Industrial quote | model source; selected `price-workbook`, `terms-agreement`, `customer-record`, `equivalence-record` |
| Procurement / bookkeeping | **model parsed but invalid**; read 1 set `source_id=receiving-records` and `action=calculate`, and `invoice-v1` was omitted; production validation rejected the proposal and the deterministic floor selected only `purchase-order` |

The procurement call returned a parsed `EmployeeWorkProposal` in 11.84 seconds,
so this is a semantic selection failure, not a transport or timeout failure.
No retry, model switch or larger-model action was taken.

## Relationship to the typed-work smokes

`employee_two_domain_work_smoke_20f3ffc19` shows the quote and invoice typed
work requests both compile and execute (370.00 and 270.00) when the accepted
evidence handles are supplied. This bundle isolates the remaining gap:
procurement's model does not reliably choose the invoice source before typed
work can begin.

## Boundary

The full held-out two-domain ordinary-product campaign is not established.
No cloud provider, credential, consent, send, spend or deployment was used.
Prior deterministic acceptance at `28afe7248` remains intact; historical
`111/123`, planner 5/5, goal router 1/2 and alignment gap 3.0 unchanged.
