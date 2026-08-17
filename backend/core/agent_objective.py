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

    ``definition_of_done`` is either a callable taking the current loop state
    (final_answer, steps, execution_history) and returning True when the
    objective is satisfied, or None — in which case structured
    ``criteria`` (see core/goals/criterion_evaluator.py) are evaluated as
    the done-predicate. When both are None, the loop falls back to
    max_steps (current behavior).
    """

    goal: str
    definition_of_done: Optional[Callable[[Dict[str, Any]], bool]] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)
    criteria: List[Dict[str, Any]] = field(default_factory=list)
    workspace_id: str = "default"

    def is_satisfied(self, state: Dict[str, Any]) -> bool:
        """True when the objective's definition_of_done evaluates true."""
        if self.definition_of_done is not None:
            try:
                return bool(self.definition_of_done(state))
            except Exception:
                return False
        if self.criteria:
            try:
                from core.goals.criterion_evaluator import CriterionEvaluator
                evaluator = CriterionEvaluator(workspace_id=self.workspace_id)
                results = evaluator.evaluate(self.criteria, state)
                return bool(results) and all(r.satisfied for r in results)
            except Exception:
                return False
        return False


def objective_from_context(context: Dict[str, Any]) -> Optional[Objective]:
    """Build an Objective from the agent's context, if one is present.

    Callers pass an objective via ``context["objective"]`` (an Objective
    instance), ``context["objective_goal"]`` + ``context["objective_done"]``
    (a predicate), or ``context["objective_goal"]`` +
    ``context["objective_criteria"]`` (structured, machine-checkable
    criteria — the production path; see criterion_evaluator.py). A
    ``context["goal_id"]`` referencing a persisted GoalObjective builds the
    objective from the durable record. Returns None when no objective is
    supplied (loop uses max_steps).
    """
    if not objective_loop_enabled():
        return None
    obj = context.get("objective")
    if isinstance(obj, Objective):
        return obj

    # Persisted goal reference — the production injector for the loop.
    goal_id = context.get("goal_id")
    if goal_id:
        try:
            from core.goals.goal_service import GoalService
            built = GoalService(
                workspace_id=context.get("workspace_id", "default"),
                tenant_id=context.get("tenant_id", "default"),
            ).to_objective(str(goal_id))
            if built is not None:
                return built
        except Exception:
            pass  # fall through to the inline forms

    goal = context.get("objective_goal")
    done = context.get("objective_done")
    if goal and callable(done):
        return Objective(goal=goal, definition_of_done=done,
                         success_criteria=context.get("objective_criteria", []))
    criteria = context.get("objective_criteria") or []
    if goal and criteria:
        return Objective(
            goal=goal,
            criteria=list(criteria),
            success_criteria=[c.get("type", "?") for c in criteria],
            workspace_id=context.get("workspace_id", "default"),
        )
    return None
