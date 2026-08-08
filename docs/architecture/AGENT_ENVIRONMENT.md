# Agent Environment — Goal-Driven Loop (W5)

> **Status:** Phase 5 (P5) implemented behind a feature flag. The
> `GenericAgent` ReAct loop can terminate on a goal predicate instead of
> always burning to `max_steps`. **Flag defaults OFF — kill-switch parity
> with the pre-P5 step-counter loop.**
>
> **Last Updated:** Aug 8, 2026
> **Related code:** `backend/core/agent_objective.py`, `backend/core/generic_agent.py`
> **Cross-references:** [`STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md`](./STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md)

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

## What this does NOT do (deferred — H10)

- **Explicit utility/reward to optimize** — the `confidence` float is recorded
  but not yet fed back into action selection (future: promote maturity ratios
  from permission-gate to optimization target).
- **Agent-extensible tool surface** — both registries are still static at
  import; `agent.register_action(...)` + maturity-gated discovery is a future
  phase.
- **Stuck-detector** — same tool+args 3× → halt (UNU pattern) is a future add.

## Verification

`test_agent_objective.py` (7): Objective.is_satisfied (true/false/safe-on-error),
flag gating, context-building, passthrough, and loop integration (early
termination on a satisfied predicate).
