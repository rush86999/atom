"""
Agent Objective — goal/termination predicate for the ReAct loop (W5, P5).

Converts ``GenericAgent``'s ``while current_step < max_steps`` from a
step-counter into a goal-driven loop: agents decide when they're done
against a ``definition_of_done`` predicate, not just by exhausting a budget.

Behind ``ATOM_OBJECTIVE_LOOP_ENABLED`` (default true). Kill-switch:
set ``false`` → the loop uses the original ``max_steps`` bound exactly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def objective_loop_enabled() -> bool:
    """Master switch for the goal-driven loop. Default True."""
    return _env_bool("ATOM_OBJECTIVE_LOOP_ENABLED", True)


@dataclass
class Objective:
    """A goal + termination predicate injected at loop start.

    ``definition_of_done`` is a callable taking the current loop state
    (final_answer, steps, execution_history) and returning True when the
    objective is satisfied. When None, the loop falls back to max_steps
    (current behavior).
    """

    goal: str
    definition_of_done: Optional[Callable[[Dict[str, Any]], bool]] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)

    def is_satisfied(self, state: Dict[str, Any]) -> bool:
        """True when the objective's definition_of_done evaluates true."""
        if self.definition_of_done is None:
            return False
        try:
            return bool(self.definition_of_done(state))
        except Exception:
            return False


def objective_from_context(context: Dict[str, Any]) -> Optional[Objective]:
    """Build an Objective from the agent's context, if one is present.

    Callers pass an objective via ``context["objective"]`` (an Objective
    instance) or ``context["objective_goal"]`` + ``context["objective_done"]``
    (a predicate). Returns None when no objective is supplied (loop uses
    max_steps).
    """
    if not objective_loop_enabled():
        return None
    obj = context.get("objective")
    if isinstance(obj, Objective):
        return obj
    goal = context.get("objective_goal")
    done = context.get("objective_done")
    if goal and callable(done):
        return Objective(goal=goal, definition_of_done=done,
                         success_criteria=context.get("objective_criteria", []))
    return None
