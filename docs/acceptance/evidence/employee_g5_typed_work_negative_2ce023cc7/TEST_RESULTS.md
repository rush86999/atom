# G5 typed-work preparation — results

Executed source: `2ce023cc7`; local `ollama/llama3.1:8b`.

## Deterministic compiler

| Control | Observed |
|---|---|
| quote work request | compiles map+calculate; executes from full rows; `370.00` |
| invoice work request | compiles `invoice.reconcile`; executes `270.00` |
| preview/full population | preview 20/25; execution uses all 25; `25.00` |
| stale adoption | refused after task_version advance |
| duplicate request | second adoption `already_applied`; one revision |
| unknown column/reference | refused before adoption |
| missing freight authority | refused before adoption |

Logs: `focused-tests.log` (22 passed), `affected-suite.log` (276 passed),
`work-request-matrix.log` (4 passed).

## Served evidence selection

- Quote: model-backed; selected `price-workbook` and `terms-agreement`.
- Procurement: model-backed; selected `purchase-order` and
  `receiving-records`; `invoice-v1` was not selected on the first turn.
  Preserved as a genuine negative.

## Served follow-up — failure

- Strict `WorkAdaptationProposal` exposes only decision/reason/observation_ids/
  `work_request`/clarification.
- The 8B model emitted an unsupported `new_steps`/operation object instead of
  `work_request`; validation rejected it.
- The call reached the 240-second deadline. No work request was adopted and no
  calculated value was produced. Deterministic fallback is not counted as
  adaptive success.

Exact traces: `served-work-request-negative-report.json` and
`served-work-request-negative-calls.jsonl`.

## Boundaries

Preparation evidence only. G5 remains unqualified; no served two-domain
campaign, cloud provider, live effect, credential/consent/spend or deployment.
Historical `111/123`, planner 5/5, goal router 1/2 and alignment gap 3.0
unchanged. Prior deterministic acceptance at `28afe7248` remains intact.
