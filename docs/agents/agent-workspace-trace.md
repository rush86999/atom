# Agent Workspace — Live Task Trace, Feedback & Auto-Show

> **Last Updated**: August 2026
> **Audience**: Developers, AI Engineers, Power Users
> **Status**: Implemented (frontend `components/chat/AgentWorkspace.tsx`, backend `integrations/chat_orchestrator.py`)

The Agent Workspace is the right-hand panel in agent chat (`/chat`). It shows the
agent's real task work as it happens — execution steps, reasoning trace, tool
observations — so users can understand what the agent did, give per-step
feedback, and grow the training signal set. This doc describes the data
pipeline, the contracts, and the auto-show/auto-hide UX policy.

---

## 1. Data Pipeline (chat → panel)

```
User message
  └─ POST /api/chat/message
      └─ ChatOrchestrator._handle_agent_request
          ├─ _emit_agent_status("running")                 ── WS ─┐
          ├─ atom.execute(..., step_callback=step_callback)        │
          │    └─ per ReAct step: persists AgentReasoningStep      │
          │       AND invokes step_callback                 ── WS ─┤→ workspace:default
          └─ _emit_agent_status("success" | "failed")       ── WS ─┘   (+ workspace:{tenant})
```

- **`_emit_agent_step(session_id, agent_id, execution_id, step_record)`**
  (`chat_orchestrator.py`): broadcasts one normalized step envelope per ReAct
  step. Never raises — a dead WebSocket must never break the chat reply.
- **`_emit_agent_status(...)`**: broadcasts `running` before the run and
  `success`/`failed` after it. The panel uses these to bracket a run
  (auto-show / auto-hide triggers).
- Channels: `workspace:default` (what the chat UI subscribes to) plus
  `workspace:{tenant_id}` for workspace-scoped listeners.

### Step payload contract (normalized)

Emitters historically disagreed on keys (`AtomMetaAgent`/`GenericAgent` emit
`output`; the UI reads `observation`). The orchestrator normalizes every step
to (superset — original keys preserved):

```json
{
  "type": "agent_step_update",
  "data": {
    "agent_id": "atom_main",
    "execution_id": "…",
    "session_id": "…",
    "step": {
      "step": 2, "thought": "…", "action": "web_search",
      "action_input": "…", "observation": "…", "output": "…",
      "step_type": "action", "confidence": 0.92,
      "verified": "verified", "duration_ms": 810,
      "execution_id": "…", "session_id": "…", "timestamp": "…"
    }
  }
}
```

Status envelope: `{"type": "agent_status_change", "data": {"status":
"running|success|failed", "agent_id", "execution_id", "session_id"}}`.

**Rule for new emitters**: route through `_emit_agent_step` / `_emit_agent_status`
rather than broadcasting raw shapes, and prefer `observation` in new code.

---

## 2. Session Linkage & Trace Replay

- `AtomMetaAgent.execute()` stamps the run's chat session on the execution row:
  `AgentExecution.metadata_json = {"session_id": …, "channel": "chat"}` and
  includes `execution_id` in its result payload.
- `GET /api/chat/trace/{session_id}?limit=10` (`integrations/chat_routes.py`)
  returns the session's persisted runs newest-first, joined to their
  `AgentReasoningStep` rows:

```json
{"runs": [{
  "execution_id": "…", "agent_id": "atom_main", "status": "completed",
  "input_summary": "…", "started_at": "…", "steps": [{
    "step_number": 1, "step_type": "action", "thought": "…",
    "action": "web_search", "action_input": "…", "observation": "…",
    "confidence": 0.92, "verified": "verified", "duration_ms": 810,
    "resolved_model": "qwen-max", "feedback_score": null, "timestamp": "…"
  }]}]}
```

  Ownership is enforced the same way as `GET /api/chat/history/{session_id}`.
  The panel calls this on mount / session change to restore history; live
  events merge into the same run keyed by `execution_id`.

Scope note: history replay covers meta-agent (`atom_main`) chat runs, which
persist `AgentReasoningStep` rows. Standalone `GenericAgent` task runs stream
live but do not persist steps yet.

---

## 3. Feedback → Training Loop

Per-step and per-run thumbs (plus optional correction note) in the panel post
to the existing `POST /api/reasoning/feedback` (`api/reasoning_routes.py`),
which now accepts optional `execution_id` + `step_number`. When present, the
endpoint **also** stamps the polarity onto the trace row:

- `AgentReasoningStep.feedback_score = 1 | -1`
- `AgentReasoningStep.feedback_text = <comment>` (when given)

This write-through makes step feedback directly queryable by training
consumers — `core/harness_evolution_service.py` already mines
`feedback_score` for failure patterns — in addition to the governance
`AgentFeedback` adjudication flow that always runs. The frontend client is
`lib/agent-trace-api.ts` (`fetchSessionTrace`, `submitStepFeedback`), which
uses the authenticated `apiClient` (unlike the older bare-`fetch` pattern).

---

## 4. Auto-Show / Auto-Hide UX

Implemented across `pages/chat/index.tsx` (policy owner) and the panel
(defaults in `components/chat/AgentWorkspace.tsx`):

- **Slim activity rail**: when "closed" on desktop the panel stays mounted and
  renders a ~44px rail (brain icon, pulsing dot while running, unread-step
  badge, expand button). Staying mounted keeps the WebSocket live.
- **Auto-show**: the first `run_start`/step of a run opens the panel — unless
  the user manually closed it during the current run (that suppresses
  auto-open until the next run starts).
- **Auto-hide**: ~8s after a run settles (success/failed) an auto-opened panel
  collapses again. Any click inside the panel or manual toggle cancels the
  pending timer.
- **Preference**: the header eye toggle turns auto-hide off; persisted in
  `localStorage["atom_workspace_autohide"]`. The panel header also has a
  manual collapse button. The mobile drawer remains manual open/close.
- Canvas events keep auto-switching the panel to the Artifacts tab
  (pre-existing behavior).

---

## 5. Key Files

| Layer | File |
|---|---|
| Panel UI (runs, trace cards, feedback, rail) | `frontend-nextjs/components/chat/AgentWorkspace.tsx` |
| Auto-show/hide policy | `frontend-nextjs/pages/chat/index.tsx` |
| Trace/feedback client | `frontend-nextjs/lib/agent-trace-api.ts` |
| Live emitters + chat run wiring | `backend/integrations/chat_orchestrator.py` (`_emit_agent_step`, `_emit_agent_status`, `_handle_agent_request`) |
| Session stamping on runs | `backend/core/atom_meta_agent.py` (`execute()`) |
| Trace read API | `backend/integrations/chat_routes.py` (`GET /api/chat/trace/{session_id}`) |
| Feedback write-through | `backend/api/reasoning_routes.py` (`submit_step_feedback`) |
| Trace persistence | `backend/core/models.py` (`AgentExecution`, `AgentReasoningStep`) |
