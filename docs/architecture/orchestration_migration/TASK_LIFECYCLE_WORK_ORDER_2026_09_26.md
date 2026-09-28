# Durable Task Lifecycle: Implementation and Acceptance Work Order

Prepared 2026-09-26 from the working tree at `2cdc2f98b`. This work order assumes the WORKBOOK_DELIVERY_WORK_ORDER is complete or in final integration. It is a design directive, not a certification of the current implementation.

## Objective

Make ONE durable task lifecycle work across chat, workbook retrieval, canvas editing, and a sandboxed outbound action. A conversation must update a persisted task rather than reconstruct it every turn. The lifecycle must survive restarts, honor corrections, gate completion claims, and produce consistent delivery across HTTP, streaming, history, and reload.

## Authority

This work order is the specification. `docs/architecture/orchestration_migration/04_CONTRACTS.md` defines the chain (objective → operation → evidence/result → verification → delivery). The existing components are the building blocks. No new frameworks. No incident vocabulary in production code.

## Verified foundations

| Component | Lines | What it provides | Work order uses it for |
|---|---|---|---|
| `core/goals/goal_run_service.py` | 1007 | Persisted runs, guarded transitions, waiting, replanning, human checkpoints | Task revision and state transitions |
| `core/agent_objective.py` | 112 | Explicit goals and machine-checkable completion criteria | Objective identity and completion tests |
| `core/task_outcome_contract.py` | 824 | Registered evidence verifiers, trusted provenance, separate task/tool/delivery success | Verification stage |
| `core/execution_recovery.py` | 138 | Detection of interrupted executions, RUNNING→FAILED with recovery stamps | Restart recovery |
| `docs/.../04_CONTRACTS.md` | — | The five-stage chain, domain-independence rules, component ownership map | Specification |
| `core/finalization.py` | — | Flag-gated exact-execution finalization with failure naming and no concealment | Delivery stage |
| `core/answer_presentation.py` | — | pres-v2 renderer (typed values, identity status, field-selection status) | Presentation from structured evidence |
| `core/async_turn_continuation.py` | — | Background edit continuations with idempotency, conflict detection | Operation retry and reconciliation |

## The defect being addressed

The orchestrator and planner total ~23,000 lines. Intent interpretation, pending-file recovery, canvas execution, background work, formatting, and delivery have overlapping responsibilities with no single task-state authority. A conversation reconstructs the task every turn from the transcript instead of updating a persisted task. This causes: competing early-return paths, duplicated state ownership, presentation requests ignored across turns, and delivery inconsistency.

## Design principle

A conversation updates a task. The task is the durable record. The transcript is conversational context and evidence — not the only place task facts exist.

For each active task, Atom knows:
- What the user wants and which request established it.
- Current entities, constraints, source requirements, output preferences.
- What changed in the latest turn.
- Which operations have run and what they established.
- What remains unresolved.
- What qualifies as completion.

These are different transitions, not different intents:

| User says | Task transition |
|---|---|
| "Find prices for these eight machines" | Create objective + retrieval operation |
| "Use factory prices" | Revise requested fields; reuse sufficient evidence |
| "Make it cleaner" | Change presentation; retain objective and evidence |
| "Search again and make it cleaner" | Create retrieval attempt AND change presentation |
| "Replace item three" | Revise objective; invalidate affected downstream work |
| "Send it" | Resolve referenced artifact and authorization before execution |
| "Stop" | Cancel eligible outstanding work; report completed actions |

## Step 0 — Select and declare the authoritative lifecycle

Owner: architecture owner with integration owner.

- Audit GoalRunService's transition model against 04_CONTRACTS.md's five stages. Identify gaps (operation identity, evidence revision, delivery pin).
- Declare GoalRunService (extended) as the authoritative task-state authority. No second goal engine.
- Define the task-revision schema: objective_id, revision, entities, constraints, source requirements, output preferences, outstanding operations, completion criteria. Version it.
- Define the operation schema: operation_id (one per action), objective_id, operation type, requested change, authorization state, evidence_revision, status transitions, idempotency key.
- Define the delivery schema: delivery_id, execution_id, message_id, content hash, finalization version, evidence/action references.

Exit: one schema document covering task revision, operation, and delivery — owned by one module.

## Step 1 — Wire the lifecycle into chat (single capability: workbook retrieval)

Owner: integration owner.

- Replace the orchestrator's ad-hoc session state with the task record. When a chat turn arrives, resolve the active task (or create one), apply the transition, persist the revision, execute authorized operations, verify, persist the result, and deliver.
- The existing pending_file_task, canvas_edit, and narration lanes become operations within the task lifecycle. Their state moves from session metadata to the task record.
- The presentation intent (compact/table/default) is carried on the task revision, not inferred per-turn.
- Streaming carries progress events only; the finalized message is gated by the finalizer.

Exit: the original eight-machine ask produces the correct ordered entries, and a formatting follow-up re-renders without re-retrieving, and a re-search creates a new attempt — all through the task lifecycle.

## Step 2 — Add canvas editing as a second capability

Owner: integration owner.

- The canvas-edit lane becomes an operation type within the same lifecycle. Objective revision triggers operation invalidation for affected downstream work.
- The operation's authorization state (authorized / pending_approval / applied / rejected) is tracked in the task record.
- The existing idempotency (operation_id stamping, expected_prior_audit_id) is preserved.
- Correction ("replace item three") creates an objective revision and invalidates the stale retrieval evidence.

Exit: an edit turn uses the same task record as the retrieval turn. A correction invalidates the affected evidence. A restart after the edit shows the correct outcome.

## Step 3 — Add a sandboxed outbound action as a third capability

Owner: integration owner.

- The outbound action (email draft, task creation) is an operation with authorization, execution, and reconciliation.
- The operation's idempotency key prevents duplicate sends. The reconciliation step checks whether the external action completed even if the response was lost.
- A timeout during the action records "outcome uncertain" — never "sent" without confirmation, never "failed" without checking.

Exit: the outbound action completes honestly, survives restart without duplication, and reports uncertainty when it exists.

## Step 4 — Give the UI a consistent task view

Owner: frontend owner with integration owner.

- The task view shows: what Atom understood (objective), what is running (operations), what needs input (clarifications/checkpoints), and what is verified (evidence).
- The concise answer comes from the verified result — not from concealing a confused execution.
- Detailed traces are available separately (the existing evidence panel).

Exit: the canvas page shows the task state consistently after each turn and after reload.

## Step 5 — Evaluate whole conversations

Owner: harness owner with integration owner.

- Build evaluation scenarios covering: changed requirements, ambiguous references, competing tasks, stale sources, partial failures, restart recovery.
- Measure: completed outcomes, missed constraints, false completion claims, duplicate effects, latency, cost.
- Use the acceptance runner (v4+) extended with the task-lifecycle assertions.

Exit: the evaluation suite demonstrates the lifecycle across all three capabilities with measurable outcomes.

## Mandatory acceptance matrix

| Case | Required proof |
|---|---|
| Fresh session, eight-machine ask | Objective created; retrieval operation executed; eight ordered entries; structured evidence persisted |
| Formatting follow-up | Zero retrieval; re-render from persisted evidence; presentation changed; objective unchanged |
| Compound re-search + clean | New retrieval attempt; presentation changed; both intents preserved in the task record |
| "Use factory prices" | Field revision; evidence re-selected (not re-retrieved if sufficient); labels updated |
| "Replace item three" | Objective revision; stale evidence invalidated; remaining evidence reused |
| "Send it" | Authorization resolved; operation executed; outcome reconciled; duplicate prevented |
| "Stop" | Outstanding work cancelled; completed actions reported honestly |
| Restart mid-operation | Recovery detected; outcome recorded honestly; no duplicate on resume |
| Reload | History shows the same delivered text; evidence association retained |
| Two overlapping turns | Distinct execution identities; no cross-turn state corruption |
| Token-bearing stream | Assembled text equals persisted delivery; claim holdback contract retained |

## Completion package

1. Source/runtime manifest and exact reproduction commands.
2. Corrected acceptance runner JSON with every matrix case PASS.
3. The actual answers from the public endpoint for all scenarios.
4. Turn-scoped invocation events proving retrieval, rendering, finalization, persistence, retry, and stream claims.
5. Regression suite results.
6. A UI check on the canvas page showing the task view.
7. The framework assessment: remaining engineering burden vs a LangGraph or Temporal prototype on the same scenarios.

## Framework decision criteria (post-pilot)

Compare on the same scenarios:
- How much lifecycle code would LangGraph's checkpointed control flow eliminate?
- How much operational burden would Temporal's durable execution eliminate?
- What does the existing GoalRunService + task_outcome_contract approach cost to maintain?

Decide based on measured engineering burden, not feature checklists.

## Research basis

- [Anthropic: effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — compaction alone insufficient; explicit progress artifacts and verified incremental work necessary.
- [Anthropic: building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — routing as explicit classification; use application code for identity, authorization, and state transitions.
- [LangGraph: persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — thread checkpoints vs cross-thread stores; the task-memory / general-memory distinction.
- [LangGraph: interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — persisted interruption/resumption.
- [Temporal: durable AI](https://docs.temporal.io/ai) — durable workflow execution for multi-day waits and worker recovery.
- [Temporal: error handling](https://github.com/temporalio/documentation/blob/main/docs/develop/python/best-practices/error-handling.mdx) — idempotent activities and reconciliation around external effects.
- [SQLite: online backup](https://www.sqlite.org/backup.html) — consistent snapshots of active databases.
- [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests) — keyed replay of stored responses; rejection of mismatched parameters.
