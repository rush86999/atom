# Task lifecycle schema v1 (Step 0 exit)

Status: design directive for the durable task lifecycle. Implements `04_CONTRACTS.md` §2 chain using existing components. No new frameworks. No incident vocabulary in production code.

## Audit: GoalRunService vs 04_CONTRACTS

Covered today (read-only): `core/goals/goal_run_service.py:1-120,240-359`, `core/models.py:10428-10517` (`GoalObjective`, `GoalRun`), `core/agent_objective.py`, `core/task_outcome_contract.py:1-100`, `core/finalization.py:1-80`, `core/execution_recovery.py`, `core/async_turn_continuation.py:1-80`.

What GoalRunService already provides:
- Persisted runs with guarded transitions (`planning/active/waiting/paused_hitl/achieved/failed/cancelled`, `GOAL_RUN_TRANSITIONS`).
- Soft plan + cursor, `parameters` mutational state, `waiting_on`, `pending_decision`, append-only `decision_log`.
- Supervision modes, replan budget, stuck detector inputs, terminal hooks.

Gaps against 04_CONTRACTS (the Step 0 work):
1. Objective: `GoalObjective` has criteria/key_results but no `supersedes_objective_id` revision lineage, no per-entity provenance, no clarification state.
2. Operation: no per-action `operation_id` registry (only canvas-scoped stamping and soft plan steps); no authorization state machine; no idempotency key outside mutations; no `finalizer_version` at turn start.
3. Evidence: no `evidence_id` binding `operation_id` + source identity + `evidence_revision`.
4. Verification: `task_outcome_contract` verifiers exist but are not bound to `operation_id`/`evidence_id` per verdict.
5. Delivery: `finalization.py` preserves execution identity and names failure, but has no `delivery_id`/`message_id`/content-hash/evidence-ref binding; pin lives in ad-hoc session metadata.
6. Recovery: `execution_recovery` correctly marks interrupted runs FAILED without auto-resume; safe retry still needs operation idempotency + reconciliation (outbound actions).

Decision: extend `GoalRunService` as the single task-state authority. New schemas live in one owner module (`core/task_lifecycle.py`, new). No second goal engine.

## Schema v1 (JSON-compatible, versioned)

### task_revision v1
- `objective_id`, `revision` (int, monotonic), `supersedes_revision` (nullable).
- `goal_text` (user words + turn refs), `entities[]` {`id`, `label`, `aliases`, `provenance_turn`, `inferred` bool}, `requested_fields[]`, `source_requirements` {resource ids, freshness}, `output_preferences` {style default/compact/table, field}, `authorized_actions[]`.
- `completion_criteria[]` (machine-checkable, from `GoalObjective.criteria`), `clarifications[]` {question, status}, `unresolved[]`.
- Stored at `GoalRun.parameters.task_revision`; history preserved via `decision_log` entries of kind `task_revision`.

### operation v1
- `operation_id` (one per action; multi-action turns do NOT collapse), `objective_id`, `objective_revision`, `execution_id`, `type` (retrieve/edit/outbound/present/stop), `requested_change`, `capability` + `tool_contract`, `authorization` (authorized/pending_approval/applied/rejected), `idempotency_key` (required for mutations), `evidence_revision` (nullable until observed), `status` (pending/running/waiting/awaiting_approval/applied/conflict/failed/cancelled/superseded), `finalizer_version`, `parent_operation_id` (retry chains).
- New durable store (table or `GoalRun` child collection — implementation choice, one owner). Retries create new `operation_id` linked by `parent_operation_id`; never mutate a completed operation.

### delivery v1
- `delivery_id`, `execution_id`, `operation_ids[]`, `message_id` (exact assistant row), `content_sha256`, `finalization_version`, `evidence_refs[]`, `action_refs[]`, `status` (delivered/failed/persistence_failed), `transport` {request_id, replayed bool}, `streaming` {assembled_sha256, holdback honored}.
- Written once by the route final-delivery function; retries serve the stored payload by `request_id`, never by repeated text.

## Transition map (user wording → task change)
- Create objective + retrieval operation; revise fields (reuse sufficient evidence); change presentation (retain evidence); re-search = new attempt AND presentation change; replace item = objective revision + invalidate affected evidence; send = resolve artifact + authorization first; stop = cancel eligible operations, report completed actions honestly.

## Next (Steps 1-3)
Wire workbook retrieval first through this record (pending-file/canvas/narration lanes become operations; presentation intent rides the revision; streaming gated by finalizer), then canvas editing (invalidation + authorization states), then a sandboxed outbound action (idempotency + reconciliation + outcome-uncertain).
