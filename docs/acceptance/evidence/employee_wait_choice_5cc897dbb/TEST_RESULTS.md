# Wait-choice diagnosis and replay — test results

Executed source: `5cc897dbb` (merged base `44178e2a8` + Agent 2 feedback
`ba81f0423`).

## Diagnosis

| Signal | Result |
|---|---|
| Original prompt | 27,513 chars |
| Original latency | 104.93 s |
| Original profile | `employee_wait_choice` v2026-11-04.1 |
| Original failure | no parsed proposal; `AdaptationProposal` validation |
| Original invalid fields | `work_request.await_evidence.blocks` min length 1; `new_steps` missing `step_id`/`title` |
| Transport | not the failure: HTTP response and raw completion were captured |

## Consumer matrix

`tests/test_employee_wait_choice.py`:

- valid wait → typed `AwaitEvidenceRequest`
- ready independent work preserved
- clarify with a specific question
- retain as safe no-progress
- captured empty-blocks object rejected by the existing contract
- true no-result deterministic, receipts/requirements retained
- model wait source accepted by the public advance route

Focused affected suite at the merged source: **342 passed** in 83.54 s.
Log: `focused-tests.log`.

## Replay

| Metric | Value |
|---|---:|
| Compact prompt | 6,361 chars |
| Model latency | 13.15 s |
| Prompt / completion tokens | 2,568 / 106 |
| Served route | `ollama/llama3.1:8b` |
| Profile | `employee_wait_choice` v2026-11-04.1 |
| Source label | `model_wait_choice` |
| Decision | `replan` → `await_evidence` |
| Business decision | current supplier invoice for `PO-SEL-520`, from the authorized procurement pool |
| Blocks | invoice reconciliation |
| Model-authored steps | none |

The raw completion, parsed compact instance, expanded proposal, usage and
routing are in `replay.json`; the captured original prompt/schema and attempt
lines are included separately. The journal prompt capture is truncated at 24k
characters; `prompt_chars` records 27,513. The original negative remains at
`employee_byok_auto_selection_0e04286b2`.

The direct consumer replay used no application DB, so it verifies the
wait-choice consumer rather than Agent 2's feedback persistence.

## Scope

This resolves the captured no-result at the consumer boundary. It does not
qualify broad adaptive judgment, served multi-model quality, live connector
breadth, Linux/KVM or multi-worker/soak.
