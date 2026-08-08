# AgentRadio — Lateral Asynchronous Coordination Layer

> Passive-awareness messaging between agents. Implements the AgentRadio
> protocol (Coral AI Labs — [arXiv:2607.28430](https://arxiv.org/abs/2607.28430))
> as an additive, mention-first, cost-governed lateral channel for Atom's
> multi-agent runs (meta-agent, fleet, spawned specialists).

**Last Updated**: Aug 8, 2026

> **Status: implemented (v1).** This doc began as a design spec; the layer is
> now live. What shipped:
> - **Persistence** — `agent_threads` + `lateral_messages` tables and
>   `agent_executions.thread_id` (migration `20260808_add_lateral_missing`).
> - **Service + server** — `core/agent_radio/`: `radio_service` (DB layer,
>   mention-first, per-recipient delivery, budget accounting, passive drain),
>   `radio_server` (async wakeup relay, bounded `wait_for_mention`).
> - **Governance** — `radio_guard` (attention + cost), `radio_breaker`
>   (responsibility-breakpoint gate so teams are NOT the default).
> - **Surface** — 3 `radio.*` actions via the Unified Action Registry
>   (`radio.create_thread`, `radio.send_message`, `radio.wait_for_mention`),
>   so P2 capability + P9 sandbox gates apply automatically.
> - **Hooks** — passive inbox drain at the top of both ReAct loops
>   (`generic_agent.py`, `atom_meta_agent.py`); fleet bridge in `_recruit_fleet`.
> - **Team config** — `config/lateral_teams/coding_team.yaml` (4 roles incl. a
>   Reviewer that runs a falsification pass).
> - **Tests** — 78 unit/integration tests, **90% coverage** on the package.

---

## Source findings (why this layer exists)

From the AgentRadio paper (SWE-Atlas QnA, 124 long-horizon tasks over live
production repos):

| Configuration | Resolution |
|---|---|
| Single Claude Code, Opus 4.6 | 32.3% |
| Single Claude Code, Opus 4.8 | 57.2% |
| 4-agent team, AgentRadio (Opus 4.6) | **62.1%** |
| Single DeepSeek V4 Pro | 29.0% |
| 4-agent team, AgentRadio (DeepSeek V4 Pro) | 50.8% |
| Compute-match: 6 independent Opus runs (~$17.76) | 37.9% |

The win is **structural, not scale**: cost-matched brute force loses.
Average API spend/task rose $2.96 → $19.45 (the "tax is real"), yet
compute-matched spend proves the coordination structure itself is worth it.

Key findings we design around:

1. **"An agent that is working cannot also be listening."** — Existing
   multi-agent systems fall into three flawed patterns: parallel-but-isolated,
   round-synchronized (agents stop and wait to exchange findings), and
   top-down-only asynchrony. AgentRadio's fix: **passive awareness** — a
   background watcher lets agents keep working while absorbing mentions.
2. **Timing is the win.** MinIO case: one agent discovered server-log
   evidence mid-execution; with the lateral channel the others absorbed it
   immediately and the team scored 16/16; without it, all agents agreed on
   the wrong answer. "The useful distinction is timing… one agent's discovery
   [must] reach the right peers before its operational value expired."
3. **Attention governance is the #1 unsolved bottleneck.** "Passive awareness
   makes communication available during execution. It does not decide which
   agents should exist, which discovery deserves an interruption, who should
   receive it, or when the evidence is strong enough to revise the plan."
   If every update reaches every agent → noise. Faster channels propagate
   **shared bad assumptions faster**.
4. **Negative-hypothesis blindness.** Grafana case: 4/9 rubrics required
   negative conclusions ("datasource picker did *not* auto-select") and
   neither single nor team config formed them: "Passive awareness can
   distribute an idea that somebody develops. It cannot supply a conception
   that never appears anywhere in the team." → Reviewer must run a falsification
   pass.
5. **Fixed teams must NOT be the default.** Use a multi-agent team only when
   the task contains **responsibility breakpoints** (ownership boundary
   crossing, independent hypothesis needed, risk justifying separate
   verification). Otherwise "use one agent while one context can still own
   the problem honestly."
6. **Accountability scales with duration.** Long-running coordination needs
   durable provenance — "which agent made a claim and why an action was
   accepted" — plus explicit cost limits, permissions, recovery, and human
   escalation points.

Source article: <https://venturebeat.com/orchestration/four-ai-agents-coordinating-in-real-time-outperformed-claude-opus-4-8-on-enterprise-coding-tasks>

---

## Atom grounding (re-verified Aug 8, 2026 against current `main`)

Facts established by codebase research; the implementation reuses them instead
of rebuilding. Line numbers are current as of the merge that landed this layer.

| Fact | File |
|---|---|
| **Separate `lateral_messages` + `agent_threads` tables reserved for the radio layer** — do NOT reuse `agent_messages` | `backend/core/models.py` (`AgentThread` :1856, `LateralMessage` :1905) |
| `agent_messages` (table) is **actively used** — `board_comment_service.py` stores threaded board comments on tasks (`message_type="board_comment"`, `conversation_id=task_conversation_id(task_id)`). Reusing it for radio would corrupt live board comments (wired into `minimal_app.py`) | `backend/core/board_comment_service.py:114-123` |
| Migration: `20260808_add_lateral_messaging.py` (creates both tables + `agent_executions.thread_id` FK, idempotent, SQLite-batched) | `backend/alembic/versions/20260808_add_lateral_messaging.py` |
| No mailbox/inbox/mention concept existed elsewhere; `AgentEventBus` = broadcast/feed anti-pattern (WS fan-out) | `backend/core/agent_communication.py:29` |
| Unified Action Registry route → `POST /api/rpc/{action}` + P2 capability gate + P9 sandbox gate (all gate traffic through `call_tool`) | `backend/core/action_registry.py:131` (`@register_action`), `backend/api/rpc_routes.py:63`, `backend/integrations/mcp_service.py:1103` |
| `ActionDefinition.__slots__` has no tier metadata → maturity floors enforced **in-handler** via `_require_tier` (the helper is **NOT in `action_registry.py`**; it lives in `mini_app_tool.py` and is replicated locally in `radio_actions.py`) | `backend/tools/mini_app_tool.py:623`, `backend/core/agent_radio/radio_actions.py` |
| Passive-awareness hook: first statement of each ReAct iteration, before the spend gate / `_react_step` | `backend/core/generic_agent.py:151` (`while` loop), `backend/core/atom_meta_agent.py:684` (`for` loop) |
| Fleet recruitment: `_recruit_fleet` creates the `DelegationChain`; the radio bridge attaches a breakpoint-gated thread and stamps `radio_thread_id` onto every member's `context_json` | `backend/core/atom_meta_agent.py:1517` (recruit), `:1583` (radio bridge), `backend/core/agent_radio/radio_adapter.py` |
| Redis precedent (optional cross-worker pub/sub). **Note:** there is no `get_*_redis_url()` helper — the URL chain `DRAGONFLY_URL \| UPSTASH_REDIS_URL \| REDIS_URL` is inlined in `get_fleet_state_notifier()` | `backend/core/fleet_orchestration/distributed_blackboard_service.py:104-109` |
| Cost caps already available | `backend/core/sandbox_config.py:174` (`get_sandbox_max_cost_usd()`); MICRO tier `CognitiveClassifier` at `backend/core/llm/cognitive_tier_system.py:63` |
| Provenance tagging machinery. **Note:** `memory()` is a factory on `ProvenanceTagger` (:148), **not** on `ProvenanceTag` (:68, which has no factories) | `backend/core/provenance.py` |
| Episode memory records team runs (outcome, verification tri-state) | `backend/core/models.py` `AgentEpisode` |

---

## Design decisions (from the critique)

1. **Passive awareness, not blocking waits.** Default listener = cheap
   non-blocking **inbox drain** at the top of each ReAct iteration; inbox
   content incl. full thread snapshot appended to `execution_history`
   *only when the message mentions the agent*. Blocking `wait_for_mention`
   exists but is agent-initiated, timeout-bounded (≤30 s) — never system-
   imposed. Agents working ≠ agents deaf.
2. **Mention-first, thread-scoped. No broadcast.** `send_message` requires
   ≥1 explicit mention; replies are routed to the author. The global feed
   stays the old `AgentEventBus` territory; the radio layer is a different
   (lateral, thread-addressed) channel.
3. **Teams are not the default.** Thread auto-attachment to fleet runs is
   gated on a responsibility-breakpoint classifier (feature heuristics +
   optional budget-tier LLM verdict). Single agent remains the default for
   bounded, local, reversible work.
4. **Attention governance ships in the MVP** (paper bottleneck #1): per-agent
   inbox caps (max pending mentions, backlog TTL, decay of stale threads),
   mention-only delivery, no global fan-out.
5. **Cost governance ships in the MVP**: per-thread message budget (share of
   `ATOM_SANDBOX_MAX_COST_USD`) + MICRO-tier routing for the mention
   classifier + dedicated cost field on `AgentThread.metadata_json`.
6. **Grafana fix**: the synthesized final answer passes through a
   **falsification pass** — enumerated "what we did NOT observe/verify" per
   rubric — failing-safe against shared blind spots.
7. **Provenance from day 1**: every `agent_messages` row is an audit row
   (who/from, to whom, when, thread); injected inbox content is wrapped in
   `ProvenanceTag.memory()`; deadlock/abort timestamps recorded. Leads can
   reconstruct "who claimed what, when, and why it was accepted".
8. **Registration through the Unified Action Registry** (`@register_action`)
   so RPC surface, P2 capability scoping, and P9 sandbox enforcement apply
   automatically — not a parallel `tools/registry.py` path that could bypass
   the gates.
9. **Maturity floors (in-handler `_require_tier`):** `radio.create_thread`
   INTERN+ (additive, reversible) · `radio.send_message` INTERN+
   (`memory_remember`-adjacent) · listener tools (drain-defined) STUDENT+
   (read-only). Tier floors are starting suggestions; adjust per
   governance review.
10. **Human escalation on deadlock.** Conflicting conclusions from a team
    run route through `ProposalService` (SUPERVISED+ expectation-set) —
    the paper's "clear human escalation points".

---

## Protocol

Three primitives, exposed as registry actions (`radio.*`), implemented over
a DB-backed service + in-process asyncio fast path (Redis optional):

```text
radio.create_thread(name, member_agent_ids, scope_hint="fleet|task|manual")
radio.send_message(thread_id, content, mention_agent_ids=[...],              # mention required
                   requires_response=False, metadata=None, timeout=...)
radio.wait_for_mention(thread_id, timeout<=30)                                # agent-initiated block;
                                                                              # non-blocking inbox drain
                                                                              # is the default listener
```

Injection contract (matches AgentRadio): a message mentioning `agent_id`
is delivered **with a full snapshot of the thread** (instant context), and
the receiving agent resumes its current step without interruption.

**Persistence**: new `agent_threads` + `lateral_messages` tables (`models.py:1856`/`:1905`; migration `20260808_add_lateral_messaging.py`) — deliberately separate from `agent_messages`, which is live board-comment storage (`board_comment_service.py`). `agent_messages` is NOT dead code; do not reuse it. `lateral_messages` adds `mentions` (JSON) + per-recipient `read_by` delivery tracking (in `metadata_json`); nullable `thread_id` FK on
`AgentExecution` for run attribution.

---

## Phases (TDD — red/green/refactor; each phase ends green; ≥70% cov on new code)

### P1 — Persistence + service (core, standalone)
- **Tests first** (`backend/tests/unit/agents/test_radio_service.py`):
  thread CRUD, message CRUD, mention routing, ordering, delivery/read
  transitions, TTL expiry, thread snapshot assembly, budget cap accounting.
  Plus Alembic migration test (guard-not `_table_exists`/`_column_exists`
  for SQLite hybrid).
- Migrations revive `agent_messages` (+thread_id/mentions), add
  `agent_threads`, `AgentExecution.thread_id`.
- `core/agent_radio/radio_service.py` — synchronous-safe service; async
  server wrapper in P2.

### Phase 2 — In-memory + Redis server, passive inbox
`core/agent_radio/radio_server.py` — singleton `get_radio_server()`; per-thread
`asyncio.Queue` + per-(thread,agent) wakeup `asyncio.Event` (in-memory
default); Redis pub/sub channel `radio:lateral:<thread_id>` fallback
(reuse `get_*_redis_url()` from `distributed_blackboard_service.py`,
same `DEFAULT_LISTENER_TIMEOUT_SECONDS` pattern; fail-soft when Redis off).
- Exposes: `create_thread`, `send_message`, `get_pending(root, since)`
  (the **non-blocking** drain), `wait_for_mention(timeout)`,
  `get_thread_snapshot()`.
- Tests: asyncio 2-agent ping-pong integration (proves drain + wakeup work
  across `asyncio.create_task`s), timeout enforcement, Redis paths mocked.

### Phase 3 — Registry tools + passive hook (first end-to-end checkpoint)
- `@register_action` x4 (`radio.create_thread`, `radio.send_message`,
  `radio.wait_for_mention`, `radio.read_inbox`) with `_require_tier` floors
  (canonical handlers in `core/agent_radio/radio_actions.py`); RPC surface at
  `POST /api/rpc/radio.*`; P2 capability + P9 sandbox gate tests.
- **Passive inbox drain** hooked at `generic_agent.py:148` (first statement
  of each iteration, before `_react_step`); `[INBOX @<agent>]` appended to
  `execution_history`; para-path iteration in components (`atom_meta_agent.py`
  top of its loop). Gated by `ATOM_RADIO_ENABLED` (default **true** for tool
  availability; the drain is inert without a team/thread, so solo runs are
  unaffected).
- Tests: inbox content reaches the next ReAct step (behavioral), unrelated
  messages never injected, `requires_response` honored, budget gate
  short-circuits, sandbox/capability blocks, explicit-disabled degrade is
  graceful (`success:false` + human note).

### Phase 4 — Thin adapter: fleet threads + responsibility-breakpoint gate
- `_recruit_fleet` (`atom_meta_agent.py:1498`): after `chain.id` exists,
  auto-create ONE `AgentThread` scoped to the chain, stamp `thread_id` on
  each recruiter member's context + `AgentExecution.thread_id` — **only when**
  the task crosses a responsibility breakpoint (`core/agent_radio/radio_rerouter.py`):
  heuristic features (unfamiliar legacy mentioned, cross-service/incident,
  security/migration/refactor keywords, multi-module) + optional budget-tier
  LLM verdict. Default: no thread, single-agent (paper's rule #5).
- Reviewer role = one of the 4 roles (Planner/Researcher/Implementer/
  Reviewer, config-driven `config/lateral_teams/coding_team.yaml`) and
  forever includes the **falsification pass** prompt block.
- Tests: breakpoint classifier (prec/recall on golden set), breakpoint task
  → exactly one thread + membership, bounded task → zero threads,
  `AgentExecution.thread_id` populated, reviewer prompt includes falsification
  section, cost budget attached to thread.

### Phase 5 — Attention + cost governance (operational v1)
`core/agent_radio/radio_guard.py`:
- Inbox caps (e.g. max 10 pending/agent; overflow → TTL-fifo archive with
  one digest message), backlog TTL (default 30 min), relevance decay
  (older threads with no message in 15 min → stale, dropped from next drain),
  mention-only enforcement (send without mention → error), message size cap.
- Per-thread message budget (default $0.20, env `ATOM_RADIO_TEAM_BUDGET_USD`),
  MICRO-tier classification calls; hard-stop when exhausted.
- Kill switch `ATOM_RADIO_ENABLED=false` restores pre-radio behavior for all
  paths; per-thread `overrides`.
- Tests: cap churn does not jam agent loop, budget exhaustion → team
  collapses to silent mode (no hang), stale-thread archive, mention-only
  enforcement, kill-switch parity (behavior identical to pre-feature).

### Phase 6 — Bench (the paper's own claims, measured)
`backend/tests/e2e/radio_bench.py` — run on ~12–15 synthetic long-horizon
questions over Atom's own repo (cross-module: "why does a Canvas
delivery (three) fail under X", "which provenance tag blocks a tool call
when…", cross-service incident style). Scored vs a rubric. Compares:
single agent (baseline) vs 4-agent team (old: static blackboard) vs
4-agent team (radio). Assert: radio ≥ single ≥ isolated on our task set;
record cost/wall-clock/token. If radio reproducibly does NOT beat the
isolated baseline on a category, disallow thread auto-compaction → separate
breakpoint classifier follow-up. Gate: keep `team_by_default=false` until
the bench validates.

### P7 — Docs + visibility
- `docs/agents/lateral-messaging.md` (lay user guide: protocol philosophy,
  the 3 primitives, team YAML, env flags, the $2.96→$19.45 tax trade-off);
  link from `docs/agents/overview.md`.
- `ATOM_RADIO_ENABLED` (default `true`), `ATOM_RADIO_TEMP_BUDGET_USD`,
  `ATOM_RADIO_LOOP_HOOKS` — CRUD kill switches — to ENVIRONMENT_VARIABLES.md
  and `.env.example` (defaults as above).
- Optional (follow-on): WS `radio` room broadcasts so the frontend can show
  a Team-threads panel (reuse `websocket_manager` rooms; Defender note:
  it's a *view*, not a control channel).

---

## Explicit non-goals (v1)

- No change to Conductor/Queen orchestration semantics (additive only).
- No human-in-the-loop resolution UI beyond existing ProposalService wiring.
- No shared-memory/blackboard replacement (radio is a *lateral channel*;
  the delegations chain blackboard stays the oracle for chain-level state).
- No broadcast feed (the old `AgentEventBus` is demo-only; radio never fans
  out globally).
- No hardened multi-instance session — Redis fallback is best-effort.
- No SWE-Atlas repro port (P6 bench is our own, small).

---

## Env flags (new)

| Flag | Default | Meaning |
|---|---|---|
| `ATOM_RADIO_ENABLED` | `true` | Master switch; `false` restores pre-radio behavior everywhere |
| `ATOM_RADIO_TEAM_BUDGET_USD` | `0.20` | Per-thread message cost cap |
| `ATOM_RADIO_INBOX_CAP` | `10` | Pending cap per agent per drain |
| `ATOM_RADIO_BACKLOG_TTL_MIN` | `30` | Stale message expiry |
| `ATOM_RADIO_BREAKPOINT_GATE` | `true` | Auto-attach threads only for breakpoint tasks |

Kill-switch parity is gate-checked in P5 (traffic before/after identical
behaviorally).