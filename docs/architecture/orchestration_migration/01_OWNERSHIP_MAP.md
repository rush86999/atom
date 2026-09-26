# Orchestration Migration — Responsibility & State Ownership Map (Discovery Artifact 1)

All file:line references at baseline `39d6532d5` (see 00_BASELINE). The file
is actively edited upstream — re-locate by symbol on drift. Conditional-return
counts and other size observations are deliberately excluded; this map rests
on state ownership and call structure only.

## 1. Durable state stores

| Store (table/model) | Owning stack | Key identifiers | Main writers | Main readers |
|---|---|---|---|---|
| `workflow_executions` (`WorkflowExecution`, models.py:761) | Automation | uuid4 `execution_id`; `version` counter | `core/workflow_engine.py:160`–607 (via `ExecutionStateManager`, execution_state_manager.py:25) | `workflow_endpoints.py:738`; `execution_recovery.py:42` (also writes: RUNNING→FAILED reaper) |
| `agent_executions` (`AgentExecution`, models.py:1053) | **Chat + agent stacks SHARED** | uuid4 id; `triggered_by` (chat/continuation/websocket/…); `metadata_json` blob | Chat: `chat_orchestrator.py:3113` (`_start_chat_execution`), `:3597` (`_finish_chat_execution`, called from 15 exit paths). Agent stack: `generic_agent.py:1858`, `atom_meta_agent.py:691`, `async_turn_continuation.py:339`, `supervised_queue_service.py:437`, `proposal_service.py` (6 sites), `canvas_tool.py` (6 sites), +5 more modules | `chat_routes.py:781` (trace by `metadata_json.$.session_id`), `api/agent_routes.py:97`, canvas write-verification `chat_orchestrator.py:6499` |
| `agent_reasoning_steps` (`AgentReasoningStep`, models.py:1092) | Chat + agent shared | FK `execution_id`, step_number | `chat_orchestrator.py:3669` (`_record_chat_step`, 7 call sites), `atom_meta_agent.py:3007` | trace endpoint; verify panel context |
| `CanvasAudit` | Canvas ops | `details_json.operation_id` / `.execution_id` (stamped by writer) | `chat_canvas_editor.py:2518/2692` (canvas ops), continuations stamp `operation_id=continuation_id` (async_turn_continuation.py:996) | write-verification guard `chat_orchestrator.py:6522`–6589; preapply gate `:611–648` |
| `AsyncContinuationClaim` (models.py) | Continuation | `session_id` PK (atomic insert = one-in-flight, async_turn_continuation.py:168) | continuation claim/release; startup cleanup `:452` | `continuation_in_flight` |
| pending file task state | Chat, per conversation | `task_id`, `supersedes`, statuses pending→retrieved→delivered/served | `core/pending_file_task.py`; durable carrier = `ChatMessage.metadata_json["pending_file_task"/"pending_file_result"]` (chat_orchestrator.py:13058–13072) | next-turn resume `:3980–4037`; loader `:13188–13268` |
| `verify_panel_runs` (`VerifyPanelRun`) | Verification | run id | `verify_panel.py:72–106` (fire-and-forget) | `exchange_memory_maintenance.py:264` |
| `saas_audit_logs` (`AuditLog`) | Cross-cutting audit | row uuid; `metadata_json.agent_execution_id` (embedded, no FK; ContextVar binding agent_action_audit.py:45–135) | `agent_action_audit.py` | `count_execution_audits` (:293); `api/audit_routes.py` |

**Continuation payloads ride `AgentExecution` rows** (`triggered_by="continuation"`,
payload `metadata_json["continuation"]`, origin link `metadata_json["originating_execution_id"]`,
async_turn_continuation.py:328–367). There is no separate continuation table.

## 2. Contention and implicit-schema risks

1. **`agent_executions` — ~16 writer modules** with divergent id sources
   (fresh uuid4 vs `context.run_id`), divergent `triggered_by`, divergent
   `metadata_json` shapes, all consumed by one reader contract
   (`chat_routes.py:789` parses `$.session_id`).
2. **`metadata_json` is an implicit schema** parsed ad-hoc by three
   subsystems: chat outcome persistence (`chat_orchestrator.py:3644–3664`),
   canvas verification binding (`:6500–6521`), audit completeness needle
   (`agent_action_audit.py:283–290`). Migration must give these explicit,
   versioned keys.
3. **`workflow_executions` — two writers** (engine + recovery reaper), benign
   today but the pattern to avoid replicating.

## 3. Dead weight (retirement candidates, confirm before deleting)

- `core/enhanced_execution_state_manager.py` — `EnhancedExecutionStateManager`
  subclasses `ExecutionStateManager` (:92); **production consumers: none**
  (test-only imports; repo-wide search incl. dynamic references found nothing).
- `core/agent_execution_service.py` — writes `AgentExecution` but
  `execute_agent_chat` has **zero production callers**; orphaned duplicate of
  chat-orchestrator persistence.
- `core/agent_orchestrator.py`, `core/agent_task_registry.py` — in-memory
  only, no durable state (not dead, but not state owners).

## 4. Five responsibilities → current owners (chat path)

| Responsibility | Current owner(s) | Notes |
|---|---|---|
| Task resolution | Entry lanes of `process_chat_message` (3769–5899): pending-task matching `:3980–4037`, planner routing, objective construction inside `_build_turn_task_outcome` (3151–3595, a 444-line builder) | Objective state exists per-turn only; no cross-turn revision lineage (see 02) |
| Execution | `_start/_finish_chat_execution`; tool paths; `async_turn_continuation` runner (budgets, attempts, idempotency gates 611–648, 969–997) | Execution id doubles as operation id for canvas writes (`:4909`, `:6477`) — multi-operation turns collapse into one id |
| Evidence | `workbook_read_artifact.py` (coverage: found/ambiguous/absent/incomplete, `coverage.complete`), evidence blocks + `_enforce_evidence_budget` (1521) | Coverage semantics exist and are reusable |
| Verification | Canvas guard `_canvas_write_for_operation` (6467) + `_canvas_claim_correction` (6412); `derivation_verification` (wired 10040–10063); `verify_panel` (flag OFF); contract verifier registry (02) | Guard audited as **candidate producer** — see 02 §4 |
| Delivery | Token streaming INSIDE `_get_qwen_response` (chat_token/chat_heartbeat/chat_token_done, 8993–9497); 13 terminal outcome classes in `process_chat_message`; continuation delivery = 4 channels (session append, ChatMessage row, WS `chat_continuation`, push); pending-task delivered-marking (5834–5854) | Final text reaches user via HTTP response; streamed bubble bound by `execution_id` |

## 5. Finalization facts the spec must absorb (evidence)

- Finalization side effects are scattered across **four calls at every
  terminal site**: `_update_session`, `_emit_agent_status`,
  `_finish_chat_execution`, pending-task delivered-marking.
- `chat_token_done.content` is populated **only if** final-text validation
  passes (9480–9497); on failure it is empty and the frontend keeps the
  streamed text.
- `_canvas_claim_correction` runs **once, on the non-streaming return**
  (10466–10471): an unsupported completion claim can reach the user via
  streamed tokens and be corrected only in the HTTP final message.
- The canvas guard returns **one verdict for the whole turn** (first bound
  audit row wins, 6530–6589) — no per-operation verdicts.
- `chat_continuation` has **no confirmed non-test frontend handler** —
  background completion delivery is not closed-loop (grep frontend-nextjs).
- `notified=True` is set unconditionally in `_finish_durable_record`
  (async_turn_continuation.py:418) even when WS/push delivery is best-effort.
- The pending-file-task **redelivery path re-renders a persisted copy without
  re-verification** and bypasses execution-id binding via
  `allow_persisted_evidence=True` (chat_orchestrator.py:4059–4182, esp. 4177);
  tests at test_pending_file_task_resume.py:488/524 pin this behavior — an
  explicit decision point for the new contract.
