# Conversation learning — ordinary Chat / Assignments consumption evidence

Source commit: `a888f5d6c93e293fb6130adf8ecf3ffd1e5a0451`

This directory closes the normal-consumer half of the conversation-derived
learning successor. The accepted local-core tag
`local-core-2026-10-30-final` (`da9cc8b12`) is unchanged; the earlier
applicability evidence at `conversation-learning-50b53be/` is untouched.

## Contract exercised here

- A promoted conversation lesson carries its normalized `context` on the
  journal entry's top-level field and its provenance/method under
  `details.conversation_learning`.
- Ordinary Chat extracts the turn's `task_context` (or top-level `customer`,
  `qualification`, `task_scope`, `recipient`) and passes it to the same
  `get_agent_lessons(..., task_context=..., workspace_id=...)` retrieval used
  by the rest of work-time memory. `include_context_bound=True` is not used
  for prompt injection.
- Ordinary Assignments resolve the applicable method at start, compile it
  into the existing `formula.calculate` step, and expose the consumed
  `effective_lesson_ids` (id + revision) on both the start response and the
  `GET /api/assignments/{run_id}` read model.
- Matching context consumes the lesson; wrong context excludes it; missing
  required context produces a targeted clarification and replaces a reply
  that tries to improvise a substitute.

## Live isolated-world evidence

World: `/Users/rushiparikh/projects/atom-conversation-context-world/atom.db`
Dataset: `rates` (`Qty`, `Price`) materialized under
`$ATOM_DATA_DIR/sheet_datasets/rates.parquet`.
Lesson: `97543615ea294d769807c0d0165eb65c`, revision `1`, scoped to
`customer=Customer-A, qualification=licensed`, method `multiply_sum`.

The server was launched with `ATOM_TURN_DECISION_ROUTING=0` so the local
Ollama turn-interpretation wait (about 60s in this world) would not consume
the reply budget. The ordinary Chat route, memory assembler, lesson
retrieval and response composition are unchanged by that operational flag.

| Case | Public route | Result |
|---|---|---|
| Chat matching | `POST /api/chat/message` | `memory_context` carries `TRAINING LESSONS`, lesson id `97543615…`, `rev 1`, `multiply_sum`, `Customer-A`, `licensed`; reply applies `2 × 7.50 = 15` |
| Chat wrong | `POST /api/chat/message` | no `TRAINING LESSONS`, no lesson id, no clarification |
| Chat missing qualification | `POST /api/chat/message` | `memory_context` carries `TEACHING CONTEXT REQUIRED … qualification`; reply is the deterministic ask `Before I can apply the taught method, I need to confirm: qualification.` |
| Assignment matching | `POST /api/assignments` | `status=completed`, `formula.calculate=20.00`, `effective_lesson_ids=[{id, revision:1}]` |
| Assignment wrong | `POST /api/assignments` | HTTP 409 `teaching_context_mismatch` |
| Assignment missing | `POST /api/assignments` | HTTP 409 `teaching_context_unresolved`, `missing=["qualification"]`, lesson id returned |
| Assignment restart | `GET /api/assignments/{run_id}` after backend restart | still `completed`, same lesson id/revision, formula `20.00` |

Artifacts: `chat-matching.json`, `chat-wrong.json`, `chat-missing.json`,
`assignment-matching.json`, `assignment-wrong.json`,
`assignment-missing.json`, `assignment-matching-restart.json`.

## Test evidence

| Suite | Result |
|---|---|
| Targeted backend (conversation learning, routes, assignments, chat orchestrator) | **303 passed** |
| Frontend learning suites (`ConversationLearningReview`, product profile learning) | **4 passed** |

A wider run (`wider-canvas-regressions.log`, not the 303-pass set) shows 14
`test_chat_canvas_editor.py` failures (`lane refused pre-planning: the turn's own words do not
authorize a canvas mutation`). Those fail identically at the parent commit
`55dddd6d4` in a clean worktree, so they are pre-existing and unrelated to
this change; they are not counted in the 303-pass targeted set above.

## Bounds

No live mailbox, email send, credential change, deployment, source
writeback, arbitrary URL fetch or external action was performed. Only the
isolated local world and local model were used.
