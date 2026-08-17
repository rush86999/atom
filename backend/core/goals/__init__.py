"""
Goal layer for Atom (gap analysis remediation B1/B2/B6/B9).

- criterion_evaluator: machine-checkable success criteria (graph predicates,
  board-state predicates, state assertions, metrics, combinators).
- goal_service: persisted GoalObjective CRUD with a guarded state machine
  and evaluation-driven progress/status updates.
- htn_planner: reusable decomposition methods (workflow templates) producing
  dependency-validated subtask plans.
"""

from core.goals.criterion_evaluator import CriterionEvaluator, CriterionResult
from core.goals.goal_service import GoalService, GoalTransitionError, GOAL_TRANSITIONS
from core.goals.htn_planner import HTNPlanner

__all__ = [
    "CriterionEvaluator",
    "CriterionResult",
    "GoalService",
    "GoalTransitionError",
    "GOAL_TRANSITIONS",
    "HTNPlanner",
]
