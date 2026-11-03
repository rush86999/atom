# Employee typed-work repair — source 80e3bd702

Status: **deterministic repair verified; short served smoke passed for the
quote work request. Full G5 two-domain campaign remains open.**

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `80e3bd702` |
| Local model | `ollama/llama3.1:8b` at `127.0.0.1:11436/v1` |
| Transport | controlled local service/DB; no cloud/live provider |

## Repairs

- Model-controlled `require_verified_source` / `require_verified_evidence`
  switches removed. Quote and invoice evidence must be applied and carry the
  full verified proof profile at compilation and dispatch.
- Taught/fact term binding: currency, freight and tax
  none/rate/amount resolve through accepted term ids, verify amount, unit,
  scope and revision, and carry provenance into compiled inputs. Free-form
  labels, missing terms, wrong values and unsupported zero-tax claims refuse.
- Follow-up prompt shape is derived from `WorkAdaptationProposal`; it declares
  only decision/reason/observation_ids/work_request/clarification and gives
  exact column-name and term-key guidance.
- Attempt journal records one attempt id across dispatch, prompt/schema,
  parsed result, raw completion, validation errors and cancellation stage.
- Served probe records raw provider responses where available.

## Short served smoke — passed

- Initial evidence proposal: model-backed; selected the price workbook.
- Follow-up: the 8B model produced a **valid `WorkAdaptationProposal`** with
  `quote_calculation`, source `read`, columns `Item/Qty/Price`, freight
  authority `freight` and tax authority `tax_basis`.
- Deterministic compiler adopted the request; the executor calculated
  **370.00** from the full durable rows.
- Exact prompt, parsed response and raw completion are in the calls JSONL.

## Deterministic results

| Scope | Result |
|---|---|
| Focused typed-work/adaptation/executor suite | **203 passed** |
| Independent typed-work probe | **4/4 passed** |
| Work-request binding/adaptation contract controls | passed |
| Quote work request | 370.00 through real executor |
| Invoice work request | 270.00 through real executor |
| Preview/full population | 20/25 preview, full 25 executed |
| Stale/duplicate/unknown/proof/term negatives | refused as required |

## Boundaries

Full G5 two-domain ordinary-product campaign (changed evidence, independent
progress, restart, cancellation, uncertain-effect recovery and final verified
quote/bill) is not yet run. No cloud provider, credential, consent, send,
spend or deployment. Prior deterministic acceptance at `28afe7248` remains
intact; historical `111/123`, planner 5/5, goal router 1/2 and alignment gap
3.0 are unchanged.
