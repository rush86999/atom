# G5 typed-work preparation — preserved served-model negative

Status: **preparation evidence only; G5 adaptive employee capability is not
qualified.** This bundle preserves the declared local 8B configuration's
failure after the typed-work interface repair.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `2ce023cc7` (typed work requests behind deterministic compilers) |
| Local model | `ollama/llama3.1:8b` at `127.0.0.1:11436/v1` |
| Transport | controlled local service/DB; no cloud/live provider |

## Deterministic result — passed

The typed-work compiler and executor controls pass:

- quote work request compiles to `quote.lines_from_rows` + `quote.calculate`
  and executes from the full durable rows (`370.00` in the focused control);
- invoice reconciliation compiles to `invoice.reconcile` and returns `270.00`
  from full PO/invoice/receiving evidence;
- a 25-row durable population is previewed as 20 rows with
  `sampled=true,total_count=25,shown_count=20,omitted_count=5`, while execution
  resolves the full 25 rows (`25.00`);
- stale work-request adoption refuses; duplicate request adoption is
  idempotent; unknown columns/references and missing freight authority refuse.

Logs: `focused-tests.log` (22 passed), `affected-suite.log` (276 passed),
`work-request-matrix.log` (4 passed).

## Served-model result — negative at follow-up work_request

Evidence selection:

- industrial quote: model-backed; selected the price workbook and terms
  agreement (plus customer/equivalence handles);
- procurement: model-backed; selected purchase order and receiving records on
  the first turn, missing `invoice-v1` (preserved as a genuine negative).

Follow-up after evidence:

- The production consumer requested the strict `WorkAdaptationProposal`
  schema (business decision + `work_request`, no `StepPatch` plumbing).
- The 8B model did not emit a `work_request`; it attempted an unsupported
  `new_steps`/operation object. Strict validation rejected it.
- The bounded call reached the 240-second deadline; the report records
  `evidence_source=timeout`, no adoption and no calculated value.
- The deterministic fallback remains separate safety behavior, not adaptive
  success.

Raw calls/reports: `served-work-request-negative-report.json`,
`served-work-request-negative-calls.jsonl`, `evidence-selection-report.json`,
`evidence-selection-calls.jsonl`.

## Boundaries

- No G5 adaptive claim. No two-domain served campaign.
- No cloud provider, credential, consent, send, spend or deployment.
- Planner 5/5, goal router 1/2, alignment gap 3.0 and historical `111/123`
  remain unchanged.
- The prior deterministic acceptance at `28afe7248` remains intact.
