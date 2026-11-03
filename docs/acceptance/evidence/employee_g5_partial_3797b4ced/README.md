# Employee G5 served-model preparation — partial, not qualified

Status: **partial G5 evidence; adaptive employee capability is not qualified.**

This bundle records the first served-local-model choice through the production
employee proposal consumer, plus the content-sensitive follow-up failure, and
keeps the accepted deterministic two-domain mechanisms separate.

## Source and model

| Item | Value |
|---|---|
| Executed source | `3797b4ced` |
| Model | `llama3.1:8b` |
| Endpoint | `http://127.0.0.1:11436/v1` |
| Pin | `ollama:llama3.1:8b` |
| Boundary | local Ollama only; no cloud/provider key, send, credential or spend |

## Served evidence selection

`model-evidence-selection-report.json` / `calls.jsonl` — 2 actual model calls:

- Industrial quote: selected `price-workbook` and `terms-agreement` (both
  required prerequisites), plus customer/equivalence candidates.
- Procurement/bookkeeping: selected `purchase-order` and
  `receiving-records`, but missed the required `invoice-v1` source.

This is a real served proposal, not a deterministic fallback. Procurement
discovery remains a recorded miss, not relabelled.

## Content-sensitive follow-up — negative preserved

`served-calculation-negative-report.json` / `calls.jsonl` — after the price
rows were read, the model proposed a mapping step through the production
adaptation consumer. The bounded repair corrected step IDs but the proposal
still supplied malformed `columns`/reference inputs; execution opened a
missing-evidence gap and a subsequent model call timed out. No calculation
was executed, adopted value is null, and the raw calls are preserved.

This negative is not adaptive success. Deterministic fallback safety and the
accepted deterministic campaign remain separate.

## Deterministic mechanisms

`focused-affected.log` — **271 passed** across assignment/employee,
readiness, proof schema, patch invariants, two-domain campaign and the
model-proposal seam.

`evidence-binding-probes.log` — **16 passed** (strict proof minima, G0,
approval, corrected patch helper).

`two-domain-campaign.log` — **4 passed**: industrial quote feasible/infeasible
and procurement corrected/period-close paths.

## Boundaries

- No held-out model campaign completion.
- No ordinary-product two-domain UI journey.
- No live provider/credential/consent/send/spend/reseed/deployment.
- Planner 5/5, goal router 1/2, alignment gap 3.0 and historical 111/123
  remain unchanged.
