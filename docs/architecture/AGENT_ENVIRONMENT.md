# Agent Environment — Goal-Driven Loop (W5)

> **Status:** Phase 5 (P5) implemented behind a feature flag. The
> `GenericAgent` ReAct loop can terminate on a goal predicate instead of
> always burning to `max_steps` (5a); the maturity success ratio is an
> in-loop optimization hint (5b), and GOAL-02 adds a persisted per-goal
> utility target that deterministically ranks completed `GoalRun`
> trajectories; agents expose a maturity-gated custom
> action surface with a stuck-detector (5c). **Flag defaults ON — kill
> switch `ATOM_OBJECTIVE_LOOP_ENABLED=false` restores the exact
> pre-P5 loop.**
>
> **Last Updated:** Nov 6, 2026
> **Related code:** `backend/core/agent_objective.py`, `backend/core/generic_agent.py`,
> `backend/core/goals/utility_target.py`, `backend/core/goals/goal_service.py`
> **Cross-references:** [`STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md`](./STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md), [`REVIEWER_LOOP.md`](./REVIEWER_LOOP.md)

## TL;DR

The Stanford thesis: *"In workflows we tell agents what to do. In environments
we provide infrastructure, incentives, and guardrails, but otherwise leave it
open."* Atom's loop was a prescribed pipeline (`while current_step < max_steps`).
P5 adds the missing first environment essential — a **goal/termination
predicate** — so agents decide when they're done against a `definition_of_done`.

## Feature flag (`core/agent_objective.py`)

| Flag | Default | Gates |
|---|---|---|
| `ATOM_OBJECTIVE_LOOP_ENABLED` | **false** | Whether `execute()` resolves an Objective from context; off → loop uses `max_steps` exactly (parity) |

## The `Objective` model

```
Objective(
    goal: str,
    definition_of_done: Callable[[state], bool],   # True → terminate early
    constraints: dict,
    success_criteria: list[str],
)
```

Injected via `context["objective"]` (an `Objective`) or
`context["objective_goal"]` + `context["objective_done"]` (a predicate).

## Loop integration (`generic_agent.py`)

At each iteration end, after appending the step record:
```
if _objective is not None and _objective.is_satisfied(state):
    final_answer = ... ; status = "objective_satisfied"; break
```
The `max_steps` bound remains as a hard ceiling; the objective is an *early
exit*, not a replacement for the budget.

## What this does NOT do

- **Automatic trajectory selection** — the utility target ranks completed
  trajectories deterministically; the model still chooses the next move. See
  the GOAL-02 section below.

## P5b — explicit utility (maturity success ratio as optimization target)

`GenericAgent._measure_success_rate()` reads the agent's 7-day verified
success ratio (`AgentGraduationService.calculate_skill_usage_metrics`,
best-effort, never raises). `execute()` samples a run baseline before the
loop; after each executed tool it re-samples and threads
`utility_delta = new_rate - baseline` into the next `_react_step`, which
renders an `OPTIMIZATION TARGET` block in the system prompt when a delta is
present:

```
OPTIMIZATION TARGET: your verified-success rate changed by +5.0% since the
run baseline. Prefer actions with historically high verified success;
document evidence so the outcome verifier can confirm it.
```

Gated on `ATOM_OBJECTIVE_LOOP_ENABLED` (default true). Flag off → the loop
never measures or injects (byte-identical prompt shape).

## P5c — agent-extensible tool surface

`GenericAgent.register_action(name, handler, description="", min_maturity=None)`
registers a per-agent action. `handler(args, context)` may be sync or async.
Discovery is maturity-gated: `min_maturity` (STUDENT < INTERN < SUPERVISED <
AUTONOMOUS) hides the action from AVAILABLE TOOLS while the agent's current
maturity is below the floor. Dispatch happens locally in `_step_act` before
any governance/MCP call — registered actions are agent-scoped and
pre-authorized by registration (additive; governance/capability/sandbox
layers are untouched).

The stuck-detector (UNU pattern) halts the loop with `status="stuck"` when a
tool is called 3× with identical tool+args (single-action path and parallel
batches), instead of burning the step budget in a loop. Gated on
`ATOM_OBJECTIVE_LOOP_ENABLED` (default true).

## GOAL-02 — persisted utility target + deterministic ranking

The maturity-success delta above is an in-loop optimization hint. GOAL-02 adds
the durable, comparable contract the README claim requires:

- The target lives on the existing `GoalObjective.metadata_json["utility_target"]`
  (no new table): `{metric, direction, source, description?}`.
  Accepted metrics are durable `GoalRun` counters (`human_interventions`,
  `steps_executed`, `replan_count`); `source` must be `goal_run`.
- `GoalService.set_utility_target` validates explicitly before writing.
  Missing/malformed/non-finite definitions are rejected; unknown metrics never
  silently become zero.
- `GoalService.utility_ranking` projects every terminal `GoalRun` row for the
  scoped goal/workspace (no hidden candidate cap) and ranks them with
  `core/goals/utility_target.py`. **Higher utility always ranks higher** (a
  `minimize` target is normalized to negative utility).
- Completion gates ranking before the metric: failed/cancelled runs are
  ineligible (`utility=None`, no rank), and only `achieved` runs are
  constraint-eligible in the durable projection. The pure ranking gate also
  honors an explicit trusted `constraints_ok=False` candidate, so a caller
  with real safety evidence can withhold it. Utility can never satisfy a goal
  criterion or rescue a failed/cancelled run.
- Metric evidence is a durable non-negative integral `GoalRun` counter.
  Negative, fractional, string, non-finite, and float-overflowing huge counts
  are unknown (`utility=None`, no rank) rather than zero or a crash.
- Consumers: `GoalService.evaluate` returns the read-only ranking (without
  changing status/progress), `GoalRunService`/`GoalRunRouter` receive it in the
  router context, `goal_runs.list` exposes it to agents, and
  `GET/PUT/DELETE /api/goals/{id}/utility` exposes set/read/clear at the API
  boundary (supervisor-gated writes).

The ranking is deterministic and evidence-bound; model trajectory choice stays
separate. Controlled consumer evidence: `tests/test_goal_utility_target.py`.

## Verification

`test_agent_objective.py` (7): Objective.is_satisfied (true/false/safe-on-error),
flag gating, context-building, passthrough, and loop integration (early
termination on a satisfied predicate).
`test_agent_environment_harness.py` (9): custom-action dispatch (async+sync),
maturity-gated discovery, AVAILABLE TOOLS advertising, stuck-detector halt /
flag-off parity / different-args-not-stuck, utility-delta threading, and the
OPTIMIZATION TARGET prompt block.

`test_goal_utility_target.py` (31): explicit-target validation/persistence,
higher/lower utility ranking, complete >100-candidate coverage, goal/workspace
scoping, failed/cancelled/constraint/missing/non-finite/negative/huge-count
twins, `GoalService.evaluate` and GoalRun router consumption, fresh-session
durability, flag-off parity, and the supervisor/member API boundary.
