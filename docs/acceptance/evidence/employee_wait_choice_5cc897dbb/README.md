# Employee wait-choice — bounded typed consumer and captured no-result recovery

2026-11-04, America/Toronto.

**Status: the captured wait-choice no-result is resolved at the proposal
consumer boundary by a focused typed context/schema. The model now chooses a
valid next decision within 13.15 s on the existing local route; the original
negative remains preserved.** This is a bounded recovery/regression result, not
a general adaptive-judgment claim.

| Item | Value |
|---|---|
| Executed source | `5cc897dbb` (merge of Agent 1 slice with Agent 2 feedback `ba81f0423`) |
| Original negative | `employee_byok_auto_selection_0e04286b2`, attempt `9daf25a…` |
| Served route | `ollama/llama3.1:8b`, profile `employee_wait_choice` v2026-11-04.1 |
| Compact replay | prompt 6,361 chars; **13.15 s**; 2,568 prompt / 106 completion tokens |
| Decision | model-selected `replan` → typed `await_evidence` |
| Focused affected suite | **342 passed** at the merged source |

## Exact original failure

The captured request was not a transport or empty-output failure. The original
full prompt was **27,513 chars** and took **104.9 s**; the model returned a
near-valid `AdaptationProposal` containing an `await_evidence` work request but
with `blocks=""` and an untyped `new_steps` entry. The existing contract
rejected it with:

- `work_request.await_evidence.blocks: String should have at least 1 character`
- `new_steps.0.step_id` / `new_steps.0.title`: required fields missing

The stage therefore produced no parsed proposal and the job fell back to a
deterministic retain. The captured prompt/schema and original attempt lines are
included here; the original accepted bundle remains unchanged. `captured-prompt.txt` is the journal's 24k-character truncated capture; its `prompt_chars` and parsed context carry the exact request identity.

## Smallest consumer improvement

A focused `CompactWaitChoiceProposal` is selected before the full prompt only
when the context has a supported missing prerequisite and **no ready
operation**:

- objective, missing roles/operation/status, known identities;
- bounded candidate evidence already accepted for the missing operation;
- accepted source handles, read/unread state, versions and teaching terms;
- future choices `replan` / `clarify` / `retain`, with a flat typed wait shape.

The model owns the wait/clarify/retain choice, fact, subject and expected source.
The compiler owns the blocked-operation label, durable wait ids, known subject
binding, arithmetic, receipts and authority. No model output can supply
execution ids, rows, totals or an effect. A ready independent operation keeps
the existing single-ready compact path; the wait path returns nothing in that
case. A true no-result remains deterministic and retains applied receipts and
unresolved business requirements.

## Replay decision

The one official replay used the captured context and the already-running local
route, with no new provider, key or model download:

```
decision: replan
operation: await_evidence
fact: current supplier invoice for purchase order PO-SEL-520
subject: purchase order PO-SEL-520        (compiler-bound from known identity)
expected_from: authorized procurement pool
blocks: invoice reconciliation
blocks_operation: invoice_reconciliation
```

The raw model subject was the blocked-operation label; the compiler replaced it
with the known purchase-order identity. The model did not author the durable
wait mechanics or any executable step.

## Consumer matrix

The added tests cover:

- a valid wait instance expands to the existing typed `AwaitEvidenceRequest`;
- ready independent work is preserved rather than captured by the wait path;
- a targeted clarification and a safe retain both remain valid;
- the captured empty-`blocks`/untyped-`new_steps` shape is rejected by the
  existing contract;
- a true no-result remains deterministic and retains applied receipts and
  unresolved requirements;
- the public advance route accepts `model_wait_choice` as a model source.

The merged affected suite (wait/readiness/outcome/compact/route plus Agent 2's
feedback controls) is **342 passed**; log `focused-tests.log`.

## Limits

- The model chose a wait for the current supplier invoice even though the
  accepted pool already contained an invoice candidate. This is a bounded model
  decision on an ambiguous captured context, not one-shot relevance ranking.
- The replay was reviewed from its captured raw/validation/usage/route trace;
  no independent multi-model comparison follows.
- Broader adaptive judgment, served multi-model quality, live connectors,
  Linux/KVM and multi-worker/soak remain separate unqualified rows.
- The direct consumer replay did not persist routing feedback (the isolated
  LLMService had no application DB); Agent 2's feedback DB suite is merged and
  tested separately. This slice verifies the wait-choice consumer, not the
  feedback persistence boundary.
- No new provider, credential, spend, send, download or deployment authority was
  used.
