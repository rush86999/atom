# Step 0 — Authoritative Lifecycle Schema (TASK_LIFECYCLE_WORK_ORDER Step 0)

Prepared 2026-09-26. This document declares GoalRunService (extended) as the
authoritative task-state authority and defines the three record types.

## Audit: GoalRunService vs 04_CONTRACTS.md's five stages

| Stage | GoalRunService provides | Gap identified |
|---|---|---|
| Objective | GoalObjective + GoalRun with guarded transitions, replan budget, stuck detector | No revision chain (a replan replaces the plan; it doesn't record WHAT changed or WHY as a linked revision) |
| Operation | Plan steps with kind, done flag, human_checkpoint | No per-action operation identity (plan steps are pre-declared, not dynamically minted per action); no idempotency key; no evidence revision |
| Evidence/Result | DONE verification against goal criteria (never trusted) | No evidence revision tracking (content-addressed source identity); no coverage ledger |
| Verification | criterion_evaluator with structured criteria | Already registered in task_outcome_contract's verifier registry — reuse, don't rebuild |
| Delivery | Terminal notification, marketplace feedback | No delivery pin (content hash + finalization version); no delivery record linked to the execution |

## Resolution

GoalRunService is the AUTHORITATIVE task-state authority. Its guarded
transition model (planning → active → waiting → paused_hitl → achieved/
failed/cancelled) and its durable decision log are the backbone. Three new
record types extend it:

1. **TaskRevision** — one revision of the active task, appended per turn
   that changes what the user wants. Carries: ordered requested items,
   requested fields, constraints, output preferences, cause
   (initial_request / objective_revision / presentation_change / compound /
   continuation), and the revision it supersedes. The revision chain IS
   the audit trail.

2. **Operation** — one action within a task. Multi-action turns get
   multiple operations. Carries: operation_id, attempt_id, objective_id,
   revision_id, operation_type, target, requested changes, status
   transitions, evidence_action (stamped from the OBSERVED retrieval
   outcome — creating the record proves nothing), evidence_revision
   (content-addressed), idempotency key.

3. **Delivery** — the finalized delivery for one execution. Carries:
   delivery_id, execution_id, message_id, revision_id, operation_ids,
   content hash, delivered_at, finalizer version, evidence revision,
   presentation version, and the delivered text itself. The pin records
   the POST-finalization text — retries serve this verbatim.

## Implementation

`core/task_lifecycle.py` defines the three dataclasses with constructors,
validation, and `build_lifecycle_record()` for persistence. All schemas
are domain-independent (no business vocabulary; entities, fields, and
sources are opaque strings supplied by the caller).

## Declared

- GoalRunService (extended with the three record types above) is the
  authoritative task-state authority for the chat path. The existing
  pending_file_task, canvas_edit, and narration lanes become operations
  within the lifecycle.
- task_outcome_contract.py remains the verification authority (its
  registered verifier registry is the verification stage).
- answer_presentation.py remains the presentation authority (its pres-v2
  renderer is the delivery stage's rendering backend).
- core/finalization.py remains the finalization authority (its
  finalize_payload is the delivery stage's claim gate).
- No second goal engine. No second finalizer. No second renderer.
