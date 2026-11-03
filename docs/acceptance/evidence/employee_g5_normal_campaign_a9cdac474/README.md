# G5 normal-product two-domain campaign — source a9cdac474

Status: **the normal-product two-domain campaign passed all 16 scripted
checks. The employee remains unqualified for general judgment; the
missing-invoice request itself was not spontaneous.**

## Source and serving

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `a9cdac47405d9f0f4872d479e1c2543a427bc490` |
| Worktree | `/private/tmp/atom-full-app` (clean at run) |
| Transport | `assignment_browser_acceptance_server.py`: real assignment routes + real `AssignmentExecutor`, scratch SQLite world, controlled local effects |
| Model | `ollama/llama3.1:8b` at `127.0.0.1:11436` |
| Context window | 16384 |
| Serving pin | `ATOM_EMPLOYEE_PROVIDER_MODEL=ollama:llama3.1:8b` |
| Raw traces | `attempts.jsonl` (dispatch prompt/schema, parsed response, raw completion) |

The run used the normal `/api/assignments/from-objective`, `/{run_id}/invalidate`,
`/cancel`, `/sources` and `/advance` routes. The harness supplied only
objective, authorized source references, teaching terms and one authorized
source after the missing-invoice gap. It did not supply rows, expected values,
step patches, final plans or evidence IDs.

## Campaign checks — 16/16 passed

| Check | Observed |
|---|---|
| Quote initial model proposal | `model` |
| Quote typed work adopted | `quote_calculation`, applied |
| Quote initial total | **370.00** |
| Quote initial completed | `completed`, outcome satisfied |
| Changed price/quantity evidence | **485.00**, recomputed |
| Changed quote completed | `completed` |
| Quote survives process restart | `completed` |
| Quote value survives restart | **485.00** |
| Cancellation | terminal `cancelled` |
| Invoice typed work adopted | `invoice_reconciliation`, applied |
| Invoice reconciled value | **270.00** |
| Invoice initial completed | `completed`, outcome satisfied |
| Missing invoice not fabricated | initial model decision `retain` |
| Missing-invoice source recovery | authorized source added; model then proposed `invoice_reconciliation`, applied |
| Missing-invoice recovered value | **270.00** |

The missing-invoice evidence was not invented: the model did not propose an
invoice reconciliation while only PO and receiving evidence existed. It also
did not spontaneously ask for the invoice; it returned `retain`. The campaign
then supplied one authorized invoice source through the product's source
recovery route, and the model chose the reconciliation. That is recovery with
model selection after an authorized source addition, not autonomous evidence
discovery.

## Mechanism controls on the same source

- Deterministic two-domain campaign: **4/4 passed** — changed quantities,
  governing price revision, infeasible/approved delivery, invoice wait and
  correction, supported bill preparation and period-close refusal.
- Uncertain-effect reconciliation: **3/3 passed** — provider-accepted then
  worker-lost reconciliation without resend, dependent blocking until
  reconciled, and model-scoped reconcile choice.
- Focused typed-work/executor/route suite: **199 passed**.

These deterministic controls are separate from the served adaptive result.

## Boundaries

No cloud/live provider, credential, consent, send, spend or deployment was
used. Only controlled local fixtures and the local 8B were contacted. Prior
deterministic acceptance `28afe7248`, historical `111/123`, planner 5/5, goal
router 1/2 and alignment gap 3.0 are unchanged.
