# Conversation learning — ordinary Chat consumption closure

Source commit: `54543b4938a4e88cfc1ce6de4a479d0058ff7991`

This directory closes ordinary Chat consumption of conversation-derived
teaching. It builds on the applicability evidence at
`conversation-learning-50b53be/` and the earlier consumer wiring at
`conversation-learning-a888f5d6c/`. The accepted local-core tag
`local-core-2026-10-30-final` (`da9cc8b12`) is unchanged; the assignment
evidence remains separately valid.

## What changed

- `student_learning_service.resolve_teaching_contract` now returns a typed
  decision: `applicable_lessons`, `required_context`, `conflicts`,
  `excluded_lessons`, `consumed_lesson_refs`, `source_bindings`,
  `method_status`, `method_lessons`, and `all_context_values`.
- Applicable guidance and unresolved requirements are resolved
  independently. A general lesson no longer returns early and hides a
  relevant scoped requirement; an unrelated scoped lesson is excluded by the
  same bounded relevance vocabulary instead of blocking the task.
- `memory_context_assembler._lessons_leg` renders applicable lessons and a
  separate clarification prompt from that structured result. Prompt text is
  no longer the control signal.
- Chat resolves teaching BEFORE intent analysis / reply generation. A missing
  context clarification is created before the model budget is spent; the
  model cannot generate a speculative answer that is later replaced.
- The pending clarification is persisted in session metadata (and in the
  existing task ledger when the conversation already has an active task).
  It stores the original objective, session/user/employee/workspace, lesson
  IDs/revisions, requested fields, allowed values, source bindings, request
  identity and state. No second task engine or new GoalRun is created.
- A bounded natural-language interpretation of the original request infers
  only an unambiguous allowed value (e.g. “Customer-A” establishes
  `customer`). The answer turn resolves the pending request; “Probably
  licensed” preserves uncertainty, multiple values are ambiguous, and a
  value for an established key is a scope update. A self-reported
  qualification is recorded as `user_confirmation`, never as independently
  verified certification.
- Approved executable methods run through the existing
  `conversation_learning.apply_lesson_method` allowlist. The reply is rendered
  from the typed result; the model does not redo the arithmetic. Wrong
  context is an explicit exclusion (no calculation), missing context is a
  clarification, and competing equally specific methods are a conflict (no
  calculation).
- Duplicate confirmation replays the stored result idempotently. A
  clarification from a foreign session/user/workspace/employee cannot mutate
  the obligation.
- `/learning` now has a “Draft another lesson” control so a fresh candidate
  can be promoted from the same thread without deleting prior evidence.

## Live browser journey

Isolated world `/Users/rushiparikh/projects/atom-conversation-context-world`,
backend `127.0.0.1:8071`, frontend `127.0.0.1:3130`.

1. `/learning` promoted a fresh scoped method through the UI:
   lesson `77fcb41c777f45b1bf50e4a6f5644267`, revision `1`, context
   `customer=Customer-A, qualification=licensed`, method `multiply_sum`
   over `Qty`/`Price`.
2. Chat `/teach Always cite the source workbook.` added a general lesson.
3. Chat asked: “Use the pricing method for the Customer-A order with Qty 2
   and Price 7.50.” The visible reply asked only for `qualification
   (one of: licensed)`. `memory_context` retained the general lesson and
   named both lesson refs.
4. Chat answered “licensed”. The original objective resumed and the
   deterministic result was:
   `multiply_sum(quantity=2 units, unit_price=7.50 USD) = 15 USD`,
   lesson `77fcb41c…` rev `1`, outcome `completed`, no “1.75” multiplier and
   no extra “Is this correct?” confirmation.
5. Refresh kept the result visible; history’s last assistant outcome was
   `completed` with the same lesson revision.

Artifacts: `chat-context-journey-full.json`, the journey script, four
screenshots, and `chat-context-promoted.png`.

## Restart while waiting

A separate browser session asked the same task without qualification, then
the backend was restarted against the same world. After restart the same
session answered “licensed”; the pending clarification survived and the
original objective resumed with lesson `77fcb41c…` rev `1`, operands
`2`/`7.50`, result `15 USD`, outcome `completed`. Refresh/history agreed.

Artifacts: `chat-context-restart-part1.json`, `chat-context-restart-part2.json`,
their scripts/logs, and the pending/result screenshots.

## Wrong context and controls

- Wrong context (`Customer-B/unlicensed`) produced outcome `partial` and a
  `teaching_exclusion` (`teaching_context_mismatch`) naming the conflicts;
  no `teaching_execution` was produced.
- Repeating “licensed” after a completed answer replayed the stored result
  (`completed`) instead of recalculating or re-asking.
- “Probably licensed” did not confirm; the reply asked for a plain value.
  A subsequent “licensed” completed the task.
- Unit tests cover foreign-session refusal and restart persistence.

Artifacts: `chat-wrong-final.json`, plus the unit cases in
`test_conversation_learning.py`.

## Tests

| Suite | Result |
|---|---|
| Targeted backend (conversation learning, routes, assignments, memory assembler, teaching, chat orchestrator) | **413 passed** |
| Frontend learning suites | **4 passed** |
| TypeScript `--noEmit` | clean |

The known 14 `test_chat_canvas_editor.py` failures remain the pre-existing
canvas pre-planning authorization refusal documented in the earlier
successor evidence; they are not part of the 413-pass targeted set.

## Configuration and isolation

- `ATOM_TURN_DECISION_ROUTING=0` (declared supported local configuration for
  this run) and local Ollama. This result is not transferred to a different
  routing configuration.
- `ATOM_TASK_LIFECYCLE_ENABLED=1`; the task ledger is used only when the
  conversation already has an active task. Otherwise the existing
  session/assistant-metadata carrier is the durable obligation.
- `ATOM_LOCAL_ONLY=true`, scheduler and ingestion sync off.
- The isolated world uses `agent-browser-final` (workspace `default`) for the
  journey. `agent-learn` was moved to `agent-learn-ws` in this world so its
  older scoped lesson would not appear as a sibling method and create a
  competing-method conflict. This is world isolation, not a product change.

## Bounds

No live mailbox, real email send, credential change, deployment, source
writeback, arbitrary URL fetch or external research was performed. Only the
isolated local world and local model were used.
