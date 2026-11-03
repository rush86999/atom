# Employee term-contract follow-up — source c55cc9450

Status: **focused deterministic repair and both served work-request smokes
pass. Full G5 ordinary-product campaign remains open.**

This follows the role/live-validity repair at `36fd2670b` and hardens the
typed quote receipt against provenance downgrade.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `c55cc9450` |
| Prior term repair | `36fd2670b` |
| Local model | `ollama/llama3.1:8b` at `127.0.0.1:11436/v1` |
| Transport | controlled local service/DB; no cloud/live provider |

## Follow-up controls

- Added compiler-owned `term_binding_required` on the quote calculation step.
  Removing `term_receipt` from a compiled typed step now blocks; a legacy
  direct caller without the marker retains its documented contract.
- Consumption revalidation compares accepted `source_refs` and teaching
  fingerprint in addition to role, value, currency, scope, validity,
  source and revision.
- Malformed plan-revision scope is a typed refusal, not an uncaught parse
  error.
- Role comparison normalizes both sides, so `freight_amount`/`freight`/
  `shipping_amount` agree while `tax_rate` can never authorize freight.
- Executor restart controls cover expiry, stale/revoked evidence, wrong
  workspace scope and changed value. Valid rate and amount tax twins complete
  with correct totals. Missing authoritative context, tampered receipt values
  and tampered roles block without arithmetic.

## Results

| Scope | Result |
|---|---|
| Focused typed-work/adaptation/executor suite | **235 passed** |
| Independent verifier probes (`terms_20f` + `typed_work_2ce`) | **6 passed** |
| Quote smoke | model `quote_calculation`; **370.00** |
| Invoice smoke | model `invoice_reconciliation`; **270.00** |

Raw provider requests/completions are in the calls JSONL.

## Boundaries

The full held-out two-domain ordinary-product campaign (changed evidence,
independent progress, selective invalidation, cancellation, uncertain-effect
recovery, normal UI) is not yet run. G5 adaptive employee capability remains
unqualified. No new model, cloud/live provider, credential, consent, send,
spend or deployment authority. Prior deterministic acceptance at `28afe7248`
and historical `111/123`, planner 5/5, goal router 1/2 and alignment gap 3.0
remain unchanged.
