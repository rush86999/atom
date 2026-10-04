# Milestone A — job-work ledger + reliable multi-source investigation (ZCode, round 34)

Date: 2026-10-04 · Guide: `docs/architecture/orchestration_migration/BUSINESS_DECISION_SYSTEM_AGENT_GUIDE_2026_10_04.md`
Serving identity: backend pid 29881, started 2026-10-04T16:34:52Z, HEAD `43e851e8e`, DB snapshot `atom-pre-restart-20261004-111025.db.gz`.

## Fixtures

- Original canvas `0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb` — untouched; final content SHA-256 prefix `f028613cf755564d`, byte-identical before and after all runs.
- Disposable fork `9d2b0f4a-4f1e-4f2b-855b-4a89f66fce6f` (created via `POST /api/canvas/{id}/fork`) — same SHA; draft never edited, never sent.
- Trained agent `9837ec71-4f1b-41db-b014-119862362d44` ("Sales Agent", 46 durable lessons).
- Acceptance prompt (guide-specified, verbatim): "Check the other machinery and verify whether pricing needs updating, following your training. Don't change the draft yet." Fresh session each run (msA…msA8), no operator reformulation, real API (`POST /api/chat/message`).

## Five defects found and fixed by the live runs (all pinned)

| # | Run | Defect | Fix | Commit |
|---|-----|--------|-----|--------|
| 1 | msA1 | `name 'shared_tool_state' is not defined` — recovery block read the turn blackboard inside `_get_qwen_response`, which never received it; template fallback shipped | Optional `shared_tool_state` param passed at the single call site; no-plan catch-all restored (research turns with no derivable sources had lost the honest "did NOT run" evidence) | `79763c376` |
| 2 | msA1 | `name '_deadline' is not defined` — replan/chain arms read `process_chat_message`'s local clock | Read the method's own `deadline` param with the standard None-guard, freshly at each arm; pinned with a REAL `TurnDeadline(95)` (existing pins passed none — that is why three NameErrors of one class shipped) | `d7a17cfa6` |
| 3 | msA2 | Singleflight ledger bypass: the canvas-edit leg's executed lookup reached the reply via reuse, but the prefetch ledger settle sat inside the named-file gate — executed lookups left NO retrieve operation | Settle follows execution (ungated); file bookkeeping only enriches; failure log DEBUG→WARNING | `3202021d5` |
| 4 | msA3 | Double-settle crash `running -> running`: the decline arm settled its operation, then the shared settle re-settled it | `_ms_dispatched` flag — shared settle only on the fresh-dispatch arm | `3202021d5` |
| 5 | msA3 | Canvas-deixis false decline: "…Don't change the draft yet" produced a CORRECT canvas-derived query (the quote's own machine names) and the relevance gate declined it — canvas subject admissible only on edit-shaped turns | `_canvas_referencing_message` (determiner + document/set noun deixis, domain-general, no purchasing vocabulary) admitted at the plan-relevance gate and planner `allow_canvas_target`; stale-plan protection intact (query must still MATCH the canvas topic) | `3202021d5` |
| 6 | msA2–msA6 | **The entire requirement-driven recovery block (replan, chain, catch-all) lived inside the planner-wait's `except` handler** — it only ran when the planner raised. The chain arm's own condition (`_planned and _tool_block`) was unsatisfiable there | Relocated to the shared continuation where success and failure paths converge; recovery-state observability line added (skip paths were DEBUG-invisible across five runs) | `43e851e8e` |
| 7 | msA6/msA7 | Chain re-ran `datasets` (already executed) because `consulted_sources` only tracks the canvas-edit leg's accounting; and a planning exhaustion recorded nothing durable (model asked the user to invent a retry) | The executed plan's own service counts as consulted; planning failure now creates a durable retrieval operation (not_dispatched/planning_failed) with an open re-run question | `43e851e8e` |

## Documented execution path (proposals → invocations → outcomes by operation identity)

1. `POST /api/chat/message` → `process_chat_message` creates the turn blackboard `_shared_tool` and ONE `TurnDeadline`; canvas-edit leg (`_try_canvas_edit`) is denied by the task-lifecycle scope validator (correct — research turn), the denial recorded as a `cancelled` edit operation with the reason.
2. Tool planner (`plan_tool_use`, structured, provider-swept) proposes e.g. `datasets.search:Roper Whitney Linmac Bead Roller Manual Flanger Slitter` — planning provenance (`source`, `recovered`) rides `plan._result_meta`.
3. Reply leg (`_get_qwen_response`): multi-source seam begins a `retrieve` lifecycle operation BEFORE dispatch (`begin_retrieval_turn` → GoalRun `parameters["task_lifecycle"]`), executes via `execute_tool_plan`, settles with `finish_retrieval_turn` + `record_read_outcome` (execution facts: invoked/outcome/served_basis/failure_stage/planning/items). Singleflight reuse settles the same way.
4. Requirement-driven recovery (both paths): derives the taught source set from the agent's lessons (`datasets` from workbook words, `outlook` from correspondence words), credits what executed, chains the missing taught source (bounded by turn deadline), or records honest exhaustion (`[planning-failed]` + durable open question). Declined lookups record `not_dispatched` with the decline justification.
5. Response carries `open_work` + `task_run_id`; `next_steps` derive from the DURABLE record when it exists.

Live-verified end-to-end in msA8: goal run `2a668b6a` holds `edit op df950e70 cancelled` + `retrieve op a444a372 applied, outcome=search_succeeded, basis=live, planning={source: structured, recovered: false}` — proposal, invocation and outcome linked by operation id, inspectable via `GET /api/goal-runs/{id}`.

## Honest milestone status

**Milestone A structural criteria: MET.** The task ledger engages on every path (executed, reused, declined, planning-failed); both taught sources are derived from teaching and chained order-independently; the complete investigation does not need operator rescue to REACH its sources; draft untouched across 8 runs; no read-permission asks were needed to run lookups.

**Milestone A acceptance criteria: PARTIALLY MET — not claimable.** All-eight evidence-backed dispositions were not produced in any single run: the fallback-model plan quality is bimodal (canvas-derived machine queries vs message-noun queries matching junk filenames like `zz-formula-e2e-check.xlsx`); the reply then honestly reports blank results and proposes the correct taught next steps (per-model value_trace, supplier schedules, mailbox sweep) instead of completing them within the same bounded turn. Run-to-run reliability of the plan's query construction from TEACHING (not message nouns) is the remaining gate. The chained-source result also currently rides the turn's block rather than a second operation record.

## Metrics (observed)

Turn latency 35–95s (budget 95s); cost: BYOK deepseek/openrouter routes; unnecessary clarification asks: 1 per run (the post-evidence "which next?" — legitimate when evidence is truly absent, unnecessary when the lesson orders the next source); unauthorized edits: 0 (scope gate denied all edit attempts; all recorded); duplicate effects: 0; template fallbacks: 0 after fix #1.

## Known pre-existing failures (not this arc's)

7 pending-file refresh tests fail at HEAD and with this tree (proven via worktree baseline, round 32 note). All other affected suites green: 257 passed (ledger, chain, pending-file, teaching, canvas-repair, zero-effect, action-program, target-set).
