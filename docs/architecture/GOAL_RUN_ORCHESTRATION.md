# Goal Run Orchestration — role-scoped, multi-canvas, self-steering processes

Design record + implementation plan for **GoalRuns**: long-lived, event-resumable
executions in which a role-bound agent pursues a goal through multiple steps and
multiple canvases, deciding its own next direction after every step from the
canvas data and evolving run parameters — like a salesperson working an
informal process ("prepare a quote for a lead") across touch points spread over
days, rather than a rigid pipeline.

- **Status:** implemented 2026-09-09 — all six slices PLUS guidance &
  notifications (§6 "nothing silent": every state change notifies the
  run's creator via the canonical NotificationService with the guidance
  embedded; run pages carry a per-state guidance banner) and the loop-
  semantics fixes (re-wait, stale-hold wake guard, REVISE reuses the
  step's canvas, checkpoint-rejection rewind, tier WAIT ceilings — §8.6).
  All six §8 open questions are RESOLVED (see §8). Tests: 7 scope suites
  under `backend/tests/test_goal_run_*.py` (71 goal-run tests); frontend
  `lib/goal-run-api.ts` + `/goal-runs` pages. Verified live:
  `scripts/restart_backend.sh` clean, routes loaded and auth-gated (401
  boundary), schema present on the dev DB. Build order in §7 kept as the
  record of what landed per slice.
- **Status addendum 2026-09-10 — journey start/finish gap closure.** Tracing
  "start → work → finish a long-running goal for an agent" end to end found
  the START severed in three places and two finish-line dead ends:
  (A) `GoalObjective` had no user-facing surface at all — creatable only by
  the agent action `goals.create`, listable nowhere, so a supervisor could
  not name the goal `POST /api/goal-runs` requires (unknown id → 404);
  (B) `lib/goal-run-api.ts` had no create call and `/goal-runs` had no start
  affordance — the only way to start a run was hand-rolled HTTP;
  (C) `POST /api/goal-runs` activated the row but ran **no loop turn**, so a
  freshly started run sat `active` with a cursor and produced nothing until a
  human found the Advance button. Finish-line: (D) `/goal-runs/[id]` loaded
  once and never refreshed (a run that finishes on its own is invisible until
  a manual reload), and (E) terminal runs still rendered Advance/Cancel,
  whose backend no-ops the UI reported as success. Fixed: `GET/POST
  /api/goals` (`api/goal_routes.py`; list any-signed-in, create at member
  level — the person doing the work — with criteria/target-date
  supervisor-gated), a `start` kickoff on `POST /api/goal-runs` (default on;
  `start:false` stages a dormant run), `StartGoalRunDialog` on `/goal-runs`,
  goal TITLES on the run surfaces (a UUID is not a goal), quiet polling of
  non-terminal runs, terminal action gating, and an `advance` 409 on terminal
  runs. Also fixed workspace resolution in `_service`
  (`resolve_workspace_id` was handed a **string**, whose `getattr` misses and
  silently falls back to `"default"` — goals and runs could land in different
  workspaces).
- **Status addendum 2026-09-10 (b) — role-based access, generalized.** The
  first cut gated starting/working a run at `team_lead+`, which contradicted
  the requirement: the people who communicate outside the org must be able to
  run their own everyday process in ANY business, not just sales. Access is
  now the ladder in §3.8 — members start/work their OWN role-based runs
  (role derived from the bound agent's `specialty`/`category`, plan seeded
  from approved playbooks, no `autonomous`, governance knobs stripped,
  owner-or-supervisor on acts), `team_lead+` keeps the org-shaping acts, and
  viewers read. No industry is hardcoded anywhere.
- **Status addendum 2026-09-12 — agents can start long-running runs.** The
  start journey had one severed link left: a human could start a run
  (`POST /api/goal-runs`) and an agent could create the goal
  (`goals.create`), but the agent could not start the RUN — every
  "work this goal over the next few days" ask dead-ended in "please click
  Start for me". The agent surface now exists as action-registry actions
  (`core/action_registry.py`, dispatched through the standard
  GenericAgent → MCP → governance path, discoverable via `mcp_tool_search`):
  - **`goal_runs.start`** (governance complexity 3 / SUPERVISED+, same tier
    as `create_task`): creates the run, activates it, appends a
    `started_by_agent` provenance entry to the decision log, and kicks off
    the first loop turn (fault-isolated, `start:false` stages a dormant
    run). The agent gets exactly the **member ladder** from §3.8 — role
    from the bound agent's own `specialty`/`category`, playbook-seeded plan
    (never hand-authored), `training`/`shadow` only, governance knobs
    stripped — plus two guards the human API doesn't need: an agent may
    start a run **only for itself** (directing other agents stays
    supervisor-grade), and a **duplicate-run guard** (one non-terminal run
    per goal per agent — a retried tool call must not stack runs).
    `created_by` stays the owning human, so §6 notifications route to them.
  - **`goal_runs.list`** (complexity 1 / STUDENT+): compact run summaries —
    status, current step, what a run waits for, recent decisions, the
    `/goal-runs/{id}` URL — so the agent can report progress and finish
    lines without dumping raw run rows into its context.
  The run itself is unchanged and stays durable: after the kickoff turn it
  advances on canvas done-signals, inbound events (§3.4) and timer wakes
  (the maintenance cycle), across restarts. Verified: 15 new tests in
  `backend/tests/test_goal_run_agent_start.py` + the 113-test goal-run /
  action-registry neighborhood and the governance suites, all green.
- **Research grounding (per AGENTS.md §3):** this is the established
  *plan-and-execute with replanning* pattern ([LangChain planning
  agents](https://www.langchain.com/blog/planning-agents), [multi-agent
  plan/execute/re-plan](https://medium.com/@nayan.j.paul/building-a-multi-agent-based-auto-recursive-plan-execute-re-plan-process-4f17a270078c))
  with an agent-controlled router at each step boundary — the analog of
  LangGraph's `Command` (node returns "where to go next" + state updates at
  runtime) as opposed to pre-authored conditional edges
  ([graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
  [Command tutorial](https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-dynamic-routing-in-langgraph-with-command-2c8c0f3ef451)).
- **Repo constraint stated explicitly:** in-memory graphs (native LangGraph
  style) are rejected — this repo's non-negotiables are durable state, audit
  trails, and HITL gates, so the plan, every decision, and every parameter
  mutation are persisted rows.

---

## 1. Requirement (as framed across the design conversation)

1. Playbooks involve multiple steps and **multiple canvases related to the same
   goal**.
2. The decision tree is **dynamic**: after each canvas, the agent evaluates that
   canvas's data and decides where to go next — treated like a person who
   changes direction based on the overall goal and **mutational parameters**
   (evolving deal/project state).
3. Goals are **role-based** (e.g. the sales agent's "prepare a quote for a
   lead"): multiple touch points before the final email is sent, following an
   **informal process** — long-lived, externally interrupted/resumed, not a
   pre-authored DAG.

## 2. Current state (grounding — what exists, what's missing)

| Mechanism | What exists | Code | Gap vs. requirement |
|---|---|---|---|
| Playbooks | Advisory procedural memory; `steps` = flat JSON strings; matched per turn by `trigger_canvas_type` + keywords (cap 2); injected as prompt leg | `backend/core/models.py:12614`, `core/playbook_service.py:410-478`, `core/chat_canvas_editor.py:318-345`, `integrations/chat_orchestrator.py:2505-2517` | Not executable; no goal/canvas linkage; role-agnostic |
| Canvases | Full create/edit/dispatch lifecycle; done-signals already emitted (`no_change`, `wants_action`, `canvas_close` audit) | `models.py:3977`, `chat_canvas_editor.py:1345`, `:1652`, `models.py:4054` | No back-link to any goal/run/step; cannot group "canvases for this goal" |
| Goals | `GoalObjective` (criteria JSONB, key_results, guarded status machine), `CriterionEvaluator`, `HTNPlanner` decomposition, DoD loop wired into `GenericAgent` via `context.goal_id` | `models.py:10325`, `core/goals/goal_service.py:23-29,128-161,192-213`, `core/goals/criterion_evaluator.py:54`, `core/goals/htn_planner.py:69-172`, `core/generic_agent.py:337-339,646-658` | Zero canvas awareness; plan never persisted/advanced; nothing re-evaluates after results automatically |
| Workflow engine | Graph engine with conditional edges (static `safe_eval` on runtime state), persisted execution state, HITL governance interlock, pause/resume | `core/workflow_engine.py:148,315-319,751-827,1054-1118`, `models.py:761,1442-1483` | Conditions are authored expressions, **no LLM routing**, no canvas step type, integration-builder-shaped UX/RBAC surface |
| Frontend routing affordance | Builder offers `conditionType: 'llm'` — **no backend handler exists** | `components/Automations/CustomNodes.tsx:267` | Demand pre-scoped in UI, engine absent (separate fix, see §5) |
| Learning | Corrections → lessons; reflection pool; role-scoped experience recall; correction→rule playbook distillation | `services/canvas_context_service.py:319,418`, `core/student_learning_service.py:134,716`, `core/agent_world_model.py:1322,2405` | No goal-scoped memory; runs don't feed back into playbooks |
| Long-lived patterns | Training-session canvas reuse; background agent start/stop; `PAUSED`/resume executions | `core/student_training_service.py:994-1005`, `advanced_workflow_orchestrator.py:40-91`, `workflow_engine.py:595-620` | Nothing composes waits + events + goals |

## 3. Design

### 3.1 The GoalRun object

New persisted entity (service patterned on `student_training_service` /
`GoalService`), table `goal_runs`:

| Field | Purpose |
|---|---|
| `goal_id` (FK), `agent_id` (FK), `role` | **Role binding** — "the sales agent's goal". The role scopes recall (playbooks, experiences, lessons) and the router's persona/judgment. |
| `status` | `planning → active → waiting → active … ; active ↔ paused_hitl ; terminal: achieved / failed / cancelled`. Guarded transition table mirrors `GOAL_TRANSITIONS` (`goal_service.py:23-29`). |
| `plan` (JSON) | Soft graph of steps: `{id, kind, canvas_type?, parameters, note}`. A *familiar path*, not a schedule — the router rewrites it freely. |
| `cursor` | Current step id. |
| `parameters` (JSON) | **Mutational state** — the deal/project context (budget revealed, objections, timeline, findings). Mutated by step outputs and events; read by every router call. |
| `waiting_on` (JSON, nullable) | Active wait spec: `{event, match, deadline}` — email reply / integration event / timer / human input. Consumed on wake. |
| `decision_log` (JSON, append-only) | Every router decision: `{ts, step_id, canvas_id?, event?, decision, rationale, parameter_diff, model}`. The informal process made visible + auditable; raw material for §3.6 distillation. |
| `replan_count`, `steps_executed` | Guardrail counters. |
| `supervision_mode` | `training` / `shadow` (default) / `autonomous` — §3.7. |

Canvas gains nullable back-links `goal_run_id` + `goal_run_step_id`
(additive; all existing canvas creation sites unaffected unless they opt in).
This is the goal-scoped memory the repo currently lacks — `TurnFacts`
(`models.py:1124`) provenance is session/execution-scoped only.

### 3.2 The router (the "person changing direction")

One structured LLM call at every step boundary and every wake:

- **Input:** goal text + live criteria state (`GoalService.evaluate`), role,
  current `parameters`, digest of the just-finished step (canvas data summary /
  action result / event payload), remaining plan, last K decision-log entries,
  role playbook steps (**advisory**), relevant lessons
  (`student_learning_service.get_agent_lessons`), and the agent's **maturity
  tier** — `ASK_HUMAN` propensity scales inversely with it (§3.7): a junior
  salesperson checks with their manager more often.
- **Output (strict schema, validated; full request/response payloads logged):**

| Decision | Meaning |
|---|---|
| `ADVANCE` | Proceed to next planned step |
| `REVISE_CURRENT` | Re-work the current canvas/step |
| `BRANCH_NEW_CANVAS` | Open a new canvas (specifies type + purpose) — the multi-canvas requirement |
| `SKIP` | Drop next planned step |
| `REPLAN` | Rewrite remaining plan (subject to §3.5 guardrails) |
| `WAIT` | Suspend with `{event, match, deadline}` — e.g. reply-from-lead, 3-day follow-up timer |
| `ASK_HUMAN` | Create a HITL checkpoint (process-intrinsic, not just a guardrail) |
| `DONE` | Claim goal satisfaction (verified against criteria, never trusted blindly) |

  plus mandatory `rationale` (surfaced in the UI), optional `parameter_updates`
  (JSON patch to `parameters`), optional `target_step` spec, `confidence`.
- **Fallback:** invalid/low-confidence output → `ASK_HUMAN`; the loop never
  crashes on model output. Router model selection routes through the existing
  cost/BPC router (open question §8).

### 3.3 The loop

```
start_run(goal, agent, role):
    plan ← seed (§3.6) ; status ← active
on step completion (canvas done-signal / action result)
or wake (event fired / timer breached / HITL resume):
    1. update parameters from step output / event payload
    2. GoalService.evaluate(goal)  (+ new criterion types §3.4)
         achieved → run achieved ; at_risk (target date) → escalate via HITL
    3. router(parameters, step digest, remaining plan, role context) → decision
    4. append decision + rationale to decision_log ; apply parameter patch
    5. execute decision:
         canvas_work      → GenericAgent objective loop (context.goal_id —
                            the DoD loop already exists), canvas created with
                            back-links; done-signals drive the next boundary
         integration_action → existing action_registry + per-step governance
                            interlock (pattern from workflow_engine.py:751-827)
         wait_for         → status waiting; wake consumed-once
         human_checkpoint → HITLAction + resume (mirror workflow resume :595-620)
         done             → verify criteria, then terminal
```

Touch points are therefore **mixed-kind**: canvas work, CRM/integration
actions, waits, and human checkpoints — a salesperson's actual process. The
final send is the **existing** `CanvasActionPlan.wants_action` dispatch path
with its maturity/autonomy gates (`chat_orchestrator.py:2800-2835`) — GoalRun
never bypasses send gates.

### 3.4 Termination & criteria

New `CriterionEvaluator` types: `canvas_state` (a canvas satisfies an expected
property — reuses the IncidentEval property-check idea) and `action_dispatched`
(a canvas's action executed). `manual` (never auto-satisfied) already covers
human sign-off. `GoalService` guarded transitions drive achieved / escalate.

### 3.5 Guardrails (direction-changing is also drift risk)

- Replan budget (default 5/run, configurable) and step budget (mirror
  `max_steps` patterns).
- Replan magnitude: discarding > ~half the remaining plan requires HITL
  approval before taking effect.
- Stuck detector: 3 consecutive identical decisions → pause (analog of
  `generic_agent.py:452-467`).
- Governance interlock on every integration step; HITL approval flow for
  checkpoints; every decision carries persisted rationale.

### 3.6 Playbooks stay advisory — and get a learning loop

- **Seeding:** initial plan comes from *this role's* approved playbooks +
  role-scoped experience recall (`agent_world_model.recall_experiences`,
  canvas-filtered variant) — a familiar path prior, not control flow. The
  per-turn advisory injection in `chat_canvas_editor` is untouched.
- **Distillation:** completed runs' decision logs summarize into proposed
  playbook drafts (source=`learned`, fingerprint-deduped) through the existing
  approval queue (`playbook_service` + `student_learning_service.py:716`
  machinery). Informal process → observed runs → refined playbook → better
   seed. Compounding, and consistent with this repo's approval/eval-gate
   philosophy.

### 3.7 Integration: maturity, training, learning (the employee lifecycle)

GoalRun is where the agent *works*; maturity/training/learning is how it
*grows*. The loop **consumes** their state and **emits** events into the
existing systems — no new parallel growth machinery (AGENTS.md: use the
general layer, not special cases).

**A. Maturity gates run autonomy.** Decision types carry autonomy
requirements served by the SAME gates that already guard canvas edit/send
(`chat_orchestrator.py:2800-2835`: maturity tier + earned autonomy, reset by
corrections via `canvas_context_service.py:384`):

- Terminal send: the existing `wants_action` gates, never bypassed
  (restated from §3.3).
- `REPLAN` magnitude tolerance, `WAIT` deadline length, `BRANCH_NEW_CANVAS`,
  and continuing autonomously between touch points: approval thresholds
  scale with the agent's tier.
- One decision→gate mapping table in config; no per-decision special cases.

**B. The run is a training surface.** `supervision_mode` (§3.1) defines how
the loop behaves — generalizing `student_training_service`'s per-canvas
coaching to whole processes (training session ↔ run linked; its single
reused canvas becomes the multi-canvas run):

| Mode | Behavior | Analog |
|---|---|---|
| `training` | EVERY router decision becomes an automatic HITL checkpoint before it executes; supervisor guidance attaches to the run; teach-during-run attaches lessons to the step/decision context | new hire shadowed through their first deals |
| `shadow` (default) | decisions execute and are logged with rationale; guardrails still fire (mirrors `ATOM_PLAYBOOKS=shadow` and the draft/approval philosophy) | rep whose manager spot-checks |
| `autonomous` | guardrails only (replan budget, magnitude gate, stuck detector) | senior rep |

Mode promotion is **earned, not toggled**: driven by the graduation service
over the agent's training/shadow run record (evals + outcome metrics), in
keeping with the eval-gated promotion philosophy throughout this repo.

**C. The run feeds learning.**

- A human override of a router decision mid-run IS a correction → routed
  through the existing correction machinery (`record_user_correction`
  pattern): a decision-context snapshot (goal, parameters, step digest,
  decision + rationale) files a replayable `IncidentEval`, adjusts autonomy,
  and distills a lesson.
- Failed runs → reflection-pool critiques (`reflection_service.py:24`), same
  as the GenericAgent failure path today.
- Completed runs → world-model experiences (`agent_world_model.py:141`
  `record_experience`) carrying role + goal-shape + outcome + decision-trace
  metadata, so future run seeding recalls whole-run precedent.
- Run outcome metrics (achieved/failed, replans, human interventions) →
  graduation evidence (`agent_graduation_service`).
- Run distillation → eval-gated playbook drafts (§3.6).

One loop results: **train on supervised runs → graduate via evals → run
autonomously → decisions and outcomes keep teaching (corrections,
experiences, distilled playbooks) → better seeds and judgment.**

### 3.8 Who can run what — role-based access, any business type

The sales/quoting persona in §6 is ONE instance of a general rule. Every
business has people who communicate outside the org — support reps, claims
handlers, recruiters, buyers, account managers — and **they must be able to
start and work their own role-based run** for everyday work. Access is a
ladder, not a binary supervisor gate:

| Actor | May start a run | May work a run | Org-shaping acts |
|---|---|---|---|
| **member** (and up) | yes — **role-based only**: role is required (or derived from the bound agent's `specialty`/`category`), the plan is seeded from that role's **approved playbooks** (never hand-authored), no `autonomous`, governance knobs stripped | yes, on runs **they started** (advance, resume/override, checkpoint, cancel) | no |
| **team_lead+** | anything: explicit `plan`, any goal, any mode (incl. `autonomous`), governance params | any run, regardless of owner | change `supervision_mode`, view promotion evidence, distill to a playbook draft, inject workspace events, act on runs they do not own |
| **the agent itself** (`goal_runs.start`, 2026-09-12) | yes — the member ladder verbatim (role from its own `specialty`/`category`, playbook-seeded plan, `training`/`shadow` only, knobs stripped), **only for itself**, one non-terminal run per goal | yes — by working the run's steps; the router/executor loop is the agent working | no — and no custom plans, no mode changes, no directing other agents |
| **viewer / guest** | no (403) | no (read-only) | no |

Key properties:

- **Role is business data, never a hardcoded industry list.** `GoalRun.role`
  is a free business-function label; the start surface *suggests* roles from
  the workspace's own agents (their `category`) and the API derives the role
  from the bound agent's `specialty`/`category` when one is not passed. The
  plan comes from that role's approved playbooks, so "role-based" is enforced
  by what the run can execute, not by trusting a string.
- **Owner-or-supervisor, not everyone.** A member cannot drive, approve or
  cancel someone else's run — the HITL checkpoints of a run belong to its
  owner and the supervisor chain. The owner may approve their own run's
  decisions/checkpoints (the rep signs off their own quote); supervisors can
  act on any run.
- **The org-shaping acts stay supervisor-grade** even for an owner: mode
  promotion, distillation into role playbooks, and the workspace-wide event
  inbox. These change what *other* agents/roles do, not just this run.
- **The agent's own maturity gates are unchanged.** Role-based access decides
  who may drive the process; the existing maturity/autonomy gates still decide
  what the agent is allowed to execute (terminal sends remain on
  `wants_action`).

## 4. Explicitly rejected alternatives

1. **Building inside `WorkflowEngine`.** It is integration-connector-oriented
   with its own builder UX and RBAC surface, the repo already carries three
   workflow-engine generations, and its conditions are statically authored —
   the opposite of an informal process. We *borrow* its primitives (persisted
   execution state, pause/resume, governance interlock, wait concepts).
   The `conditionType: 'llm'` builder gap is real but is a separate fix.
2. **In-memory graph runtime (native LangGraph style).** Violates durable
   state / audit / HITL constraints.
3. **Fixed DAG per playbook.** Contradicts requirement §1.2 (agent decides).
4. **One canvas per run / per goal.** Contradicts requirement §1.1.

Non-goals: objective loop for the meta-agent; replacing per-turn playbook
injection; WorkflowEngine changes; multi-agent negotiation.

## 5. Surfaces

- **API:** `backend/api/goal_run_routes.py` — list/get/run/decision-log/
  resume/cancel, RBAC-gated to the repo's current standard (role-journey
  batches; analogous to `workflow:view/run/manage`).
- **API (goals):** `backend/api/goal_routes.py` — `GET /api/goals`,
  `GET /api/goals/{id}` (any signed-in), `POST /api/goals` (supervisor). The
  WHAT the run pursues; without it the start journey had no first link.
- **UI:** `pages/goal-runs/index.tsx` lists runs and hosts the
  **Start a goal run** dialog (`components/goals/StartGoalRunDialog.tsx`:
  pick an existing goal or create one inline, bind role agent + supervision
  mode); `/goal-runs/[id]` shows the goal title, plan, canvases per step,
  and every decision with its rationale chip (pattern: the existing
  `matched_playbooks` chips); waiting-on badge for sleeping runs; both
  surfaces poll quietly while a run is non-terminal. Canvas gallery groups
  canvases by goal (`pages/canvas/index.tsx`).

## 6. User journey — training a new role agent (sales persona)

Works for any role agent; sales is the reference persona. Surfaces: the
canvas **Training tab** (`TrainingPanel.tsx`, already supervisor-aware via
`viewer_is_supervisor`) gains a **Runs** section; the run timeline (slice 5)
shows the plan, canvases per step, decision rationale chips, and waiting
badges.

### Personas

- **Supervisor (sales lead)** — creates the agent, coaches it, approves,
  promotes. Existing review-queue visibility applies unchanged.
- **Trainee agent** — the new hire: lowest maturity tier, starts in
  `training` supervision mode by default.

### Journey A — Hire and onboard

*The "new rep starts Monday" moment.*

1. Supervisor creates a sales agent from the existing guided-agent flow
   (`AgentAttachModal` already takes a goal — "prepare quotes for inbound
   leads"). Role binding + goal create the first run-able objective; new
   role agents default to `training` mode.
2. Supervisor seeds the role's process memory: authors (or approves from
   the queue) the "quote process" playbook — the informal process in
   writing, exactly today's playbook flow.
3. First lesson taught on any canvas (existing Teach form) — a work-time
   lesson that rides the very first router prompt.

### Journey B — First coached deal (training mode)

*The "shadow your first deal" moment.* (This is the §3 mechanics sanity
check, told as the supervisor experiences it.)

1. A lead arrives — the run starts; the agent drafts its plan (seeded from
   the role playbook) and **every router decision becomes a checkpoint**.
2. Supervisor opens the checkpoint: the decision, its rationale, the
   current parameters (what the agent believes about the deal), and the
   canvas just finished. Approve → it executes; **override → it's a
   correction**: instant lesson on the next decision, IncidentEval filed,
   autonomy adjusted. Coaching, not gatekeeping.
3. Touch points span days: research canvas → quote canvas → human quote
   approval (process-intrinsic checkpoint) → send (existing dispatch
   gates) → **WAIT: reply or 3-day timer** (the waiting badge shows what
   and until when) → lead objects to price → agent revises with mutated
   parameters → resend → **achieved**.
4. The run's decision log is the debrief artifact: "walk me through why
   you revised here."

### Journey C — Shadow runs (spot-check era)

*The "I trust you; loop me in on the weird stuff" moment.*

1. After a strong training-run record + graduation evals, the agent
   promotes to `shadow` — runs execute uninterrupted; only guardrails
   (replan magnitude, stuck detector, send gates) pause.
2. Supervisor reviews decision logs asynchronously on the run timeline;
   spot-check overrides still teach (same correction path).
3. Completed runs distill: the actual paths taken propose playbook drafts
   ("when a lead cites budget, revise before resend") into the existing
   approval queue — the informal process crystallizes per role.

### Journey D — Senior rep (the flywheel)

1. Graduation to `autonomous`: guardrails only; send autonomy earned
   through the existing maturity gates.
2. Its completed runs are recallable experiences seeding the NEXT hire's
   plans; its distilled playbooks train them. Training cost per agent
   drops with each one trained — the compounding loop closes.

### UX properties (must-respect — inherited from PLAYBOOK_USER_JOURNEY)

- An override teaches the corrected agent **instantly**; approval queues
  only gate install-wide promotion (rules, playbooks, modes).
- Every checkpoint shows rationale — the supervisor coaches judgment, not
  keystrokes.
- Manager attention is budgeted: `training` interrupts on every decision
  by design, and is exited via visible promotion criteria — never a
  silent permanent default.
- Nothing silent: waits display their event and deadline; promotions and
  guardrail pauses notify through the existing HITL fan-out.

### Journey → mechanism map

| Journey moment | Mechanism |
|---|---|
| Create role agent + goal | guided-agent flow + role/goal binding (§3.1) |
| Default supervised start | `supervision_mode=training` (§3.7B) |
| Decision checkpoint w/ rationale | router `rationale` (§3.2) + HITL checkpoint |
| Override teaches instantly | correction machinery + work-time lessons (§3.7C) |
| Quote approval before send | `human_checkpoint` step; `wants_action` gates unchanged |
| Reply-or-3-days | `WAIT` spec + event wakes (§3.3) |
| Promotion shadow → autonomous | graduation service over run record (§3.7B) |
| Runs → playbook drafts | distillation (§3.6, slice 6) |
| Next hire learns from runs | experience-recall seeding (§3.6) |

## 7. Implementation plan (slices — each independently shippable)

Per AGENTS.md: `TESTING=1` scratch DB for all tests; no ad-hoc scripts near the
live DB; `scripts/restart_backend.sh` before manual verification (no
`--reload`); coordination-doc entry per slice; behavior changes flagged in
commit messages.

### Slice 1 — Schema + service skeleton (no LLM)
- `backend/core/models.py`: `GoalRun` (incl. `supervision_mode`, §3.7);
  `Canvas.goal_run_id`/`goal_run_step_id` (additive, nullable). Alembic
  migration in `backend/alembic/versions/`.
- `backend/core/goals/goal_run_service.py`: `create_run(goal, agent, role)`,
  guarded `GOAL_RUN_TRANSITIONS`, wait bookkeeping (`set_wait`/`consume_wake`,
  consumed-once), `decision_log` append, parameter patching, plan CRUD.
- Tests: `backend/tests/test_goal_run_service.py` — transitions, persistence
  across a fresh session (restart simulation), wait consume-once.
- **Accept:** run created from goal+agent+role survives restart; illegal
  transitions rejected.

### Slice 2 — Router + core decision loop
- `backend/core/goals/goal_run_router.py`: prompt assembly (§3.2 inputs),
  strict output schema + validation, `ASK_HUMAN` fallback, full payload
  logging (evidence standard).
- `goal_run_service.advance()`: wire canvas done-signals (`no_change`,
  `canvas_close`; non-terminal `wants_action`) → router → persist decision →
  execute choice; `WAIT` + timer wake via existing scheduler pattern.
  `training` mode inserts an automatic HITL checkpoint before execution of
  every decision (§3.7B).
- Tests: stubbed-LLM router tests (valid/invalid/fallback); loop e2e with a
  fake canvas done-signal driving ≥3 decisions; training-mode checkpoint
  e2e (decision held for approval until resumed).
- **Accept:** every decision persisted with rationale; invalid model output
  degrades to `ASK_HUMAN`, never crashes.

### Slice 3 — Step executors + termination
- `canvas_work` executor: GenericAgent run with `context.goal_id` + step
  context; canvas creation sites (`api/canvas_routes.py` blank-create,
  `integrations/chat_routes.py:1586` draft-to-canvas) accept optional goal-run
  back-links — additive, flagged for other callers.
- `integration_action` via `action_registry` + governance interlock;
  `human_checkpoint` via `HITLAction` + resume.
- §3.7A: decision→autonomy gate mapping (single config table) reusing the
  maturity/autonomy gate helpers; terminal send stays on the existing
  `wants_action` gates.
- §3.7C (emission side): human override of a decision routes into the
  correction machinery with a decision-context snapshot (IncidentEval +
  autonomy adjustment).
- `criterion_evaluator.py`: `+canvas_state`, `+action_dispatched`; terminal
  send stays on the existing `wants_action` gates.
- Tests: executors, criteria, HITL pause/resume e2e, restart persistence.
- **Accept:** scripted §6 sales scenario end-to-end (stub router): research →
  quote → approval → send → achieved.

### Slice 4 — Event ingestion
- Wake matcher for inbound email replies (sender/thread vs `waiting_on.match`),
  integration webhooks, timers; consumed-once semantics, ordering notes.
- Tests with synthetic events.
- **Accept:** waiting run wakes on a simulated lead reply; 3-day timer fires
  the router.

### Slice 5 — Surfaces + RBAC
- `backend/api/goal_run_routes.py` (RBAC per §5); frontend
  `lib/goal-run-api.ts`; goal-grouped gallery; run timeline + rationale chips;
  waiting badge. TrainingPanel gains a run-decision-log coaching view
  (§3.7B): supervisor reviews each pivot's rationale on training/shadow
  runs.
- Tests: route tests (incl. RBAC denials); component tests.
- **Accept:** a user can see a run's full path, every pivot's rationale, and
  all canvases grouped under the goal.

### Slice 6 — Learning loop + lifecycle
- Role-scoped plan seeding (playbooks + experience recall); post-run
  distillation → playbook drafts through the existing approval queue.
- §3.7C (consumption side): completed runs recorded as world-model
  experiences (role + goal-shape + outcome + decision trace); failed runs →
  reflection critiques; run outcome metrics → graduation evidence.
- §3.7B: supervision-mode promotion wired to the graduation service.
- Measurement (AGENTS.md §2): fixed scenario set; decision-quality/replan
  metrics with vs. without seeding — numbers in the commit message.
- **Accept:** a completed run proposes a deduped playbook draft AND appears
  as recallable experience; a strong training/shadow record unlocks
  `autonomous` mode via graduation; approval flows unchanged.

## 8. Open questions — RESOLVED 2026-09-09 (research-grounded)

1. **Router model → cheapest capable structured-output model via the
   platform cost router; optional env pin.** Routing/judgment is
   classification work: the established pattern is small/cheap models with
   forced-schema outputs for routing, escalating to frontier models only
   for actual reasoning (40–85% spend reduction reported for tiered
   routing; small models can beat generalists on narrow classification —
   [LLM model routing guide](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide),
   [structured outputs for routing](https://www.linkedin.com/pulse/using-llm-structured-outputs-routing-john-damask-bbdve),
   [4-tier agent routing](https://www.reddit.com/r/AI_Agents/comments/1ub1vl0/routing_agent_work_across_4_llm_tiers/)).
   Implemented: the router runs unpinned (platform cost router decides) and
   honors `ATOM_GOAL_RUN_ROUTER_PROVIDER_MODEL="provider:model"` for
   operators who benchmark and pin a small model. The invalid/low-confidence
   → ASK_HUMAN fallback bounds the cost of a weaker router model.
2. **Role binding → stays on the run, not `GoalObjective`.** Goals are the
   workspace's shared WHAT; the run binds WHO is pursuing it and HOW (role
   scopes recall + router judgment). One goal may legitimately be worked by
   different role agents; a role column on the goal would force one-role
   goals. Revisit only if goal-level UI needs role display.
3. **Event source priority → email replies first, generic `/events`
   webhook second (shipped), integration-specific dispatchers as needed.**
   Email is the sales persona's dominant touch point and the wait spec's
   match fields (from/thread_id) already model replies; the generic
   endpoint covers everything else without per-integration work.
4. **Timeline placement → `/goal-runs/[id]` (shipped); canvas gallery
   links in via the goal-run strip + per-card Goal badge.** A goal-detail
   page doesn't exist yet; when one does, embed the timeline there rather
   than duplicating.
5. **Mode-promotion criteria → advisory evidence, supervisor-applied,
   aligned with the repo's eval-gate philosophy.** Evidence (shipped in
   `evaluate_mode_promotion`): ≥3 runs in the current mode, ≥60% achieved,
   ≤1 human intervention/run. This mirrors standard graduated-autonomy
   practice — tiered levels, approval gates, audit trails, risk-proportional
   permission ladders
   ([Cloud Security Alliance autonomy levels](https://cloudsecurityalliance.org/blog/2026/01/28/levels-of-autonomy),
   [Anthropic: measuring agent autonomy](https://www.anthropic.com/research/measuring-agent-autonomy),
   [permission ladder](https://www.mindstudio.ai/blog/ai-agent-permission-ladder-autonomy-levels),
   [human-oversight controls](https://www.sweet.security/agent-security/human-oversight-for-ai-agents)) —
   and matches the repo's own graduation/eval-gate standards (IncidentEval
   replays gate playbook promotion). Next iteration: fold run evidence into
   `agent_graduation_service`'s readiness score instead of a parallel
   recommendation.
6. **WAIT ceilings → in the gate table, NOT the BPE genome (implemented).**
   `DEFAULT_WAIT_CEILING_DAYS = {training: 3, shadow: 14, autonomous: 30}`,
   per-run override via `parameters["wait_ceiling_days"]`. A WAIT deadline
   beyond the ceiling downgrades to ASK_HUMAN — a long silence is a
   commitment a human signs off on. Self-evolving (genome) wait limits
   would be unsupervised drift; the ceiling table is deterministic and
   auditable.
