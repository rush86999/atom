# Employee typed-work repair — results

Executed source: `80e3bd702`; local `ollama/llama3.1:8b`.

## Deterministic controls

`focused-tests.log` — **203 passed** across typed work requests, adaptation
contract, attempt journal, work-request bindings, assignment executor/routes
and patch invariants.

Key controls:

| Control | Observed |
|---|---|
| model carries proof switch | schema rejects |
| unverified quote/invoice evidence | compiler refuses |
| skipped evidence | compiler refuses |
| free-form freight authority | compiler refuses |
| wrong freight amount / currency | compiler refuses |
| tax none without taught support | compiler refuses |
| rate/amount tax | binds taught term and value |
| valid quote work request | compiles and executes 370.00 |
| valid invoice work request | compiles and executes 270.00 |
| preview vs full population | 20/25 preview; full 25 executed |
| stale request | refused |
| duplicate request | one revision |
| prompt shape | response-schema fields only |
| raw malformed completion | attempt journal preserves raw + validation errors |

## Served smoke

`served-work-request-smoke-report.json` and
`served-work-request-smoke-calls.jsonl`:

- initial model evidence proposal: model-backed;
- follow-up `WorkAdaptationProposal`: model-backed, valid
  `quote_calculation` with `Item/Qty/Price` column names and
  `freight`/`tax_basis` term keys;
- compiler adoption: applied;
- calculation: **370.00**;
- raw provider completions captured (`raw_available=true`).

## Boundaries

The complete held-out two-domain campaign is not yet run. G5 adaptive employee
capability remains unqualified. No cloud/live provider action or new model.
Prior deterministic acceptance at `28afe7248` remains intact; historical
`111/123`, planner 5/5, goal router 1/2 and alignment gap 3.0 unchanged.
