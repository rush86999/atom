"""GoalService — persisted goals with a guarded state machine (gap B1/B8).

The legacy GoalEngine kept goals in an in-memory dict ("Mock storage for
now"); Objective was an ephemeral dataclass. GoalObjective rows are the
durable record; this service owns lifecycle and evaluation-driven status
updates. The state machine reuses the guard pattern from
core/orchestration/workflow_state_machine.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.goals.criterion_evaluator import CriterionEvaluator, CriterionResult

logger = logging.getLogger(__name__)

GOAL_STATUSES = ("active", "on_hold", "at_risk", "achieved", "failed")

# Guarded transition table: from -> {allowed next states}
GOAL_TRANSITIONS: Dict[str, set] = {
    "active":    {"on_hold", "at_risk", "achieved", "failed"},
    "on_hold":   {"active", "failed"},
    "at_risk":   {"active", "achieved", "failed"},
    "achieved":  set(),   # terminal
    "failed":    set(),   # terminal
}


class GoalTransitionError(ValueError):
    """Raised on an illegal goal status transition."""


class GoalService:
    def __init__(self, workspace_id: str = "default", tenant_id: str = "default",
                 session_factory=None):
        self.workspace_id = workspace_id or "default"
        self.tenant_id = tenant_id or "default"
        self._session_factory = session_factory

    def _sessions(self):
        if self._session_factory is not None:
            return self._session_factory
        from core.database import get_db_session
        return get_db_session

    def _evaluator(self) -> CriterionEvaluator:
        return CriterionEvaluator(workspace_id=self.workspace_id,
                                  session_factory=self._session_factory)

    # ------------------------------------------------------------------ CRUD

    def create_goal(
        self,
        title: str,
        description: str = "",
        criteria: Optional[List[Dict[str, Any]]] = None,
        key_results: Optional[List[Dict[str, Any]]] = None,
        owner_id: Optional[str] = None,
        parent_goal_id: Optional[str] = None,
        target_date: Optional[datetime] = None,
        source: str = "api",
    ) -> Dict[str, Any]:
        from core.models import GoalObjective
        if not title or not title.strip():
            raise ValueError("goal title is required")
        goal = GoalObjective(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            title=title.strip(),
            description=description or "",
            criteria=list(criteria or []),
            key_results=list(key_results or []),
            owner_id=owner_id,
            parent_goal_id=parent_goal_id,
            target_date=target_date,
            source=source,
        )
        with self._sessions()() as session:
            session.add(goal)
            session.commit()
            session.refresh(goal)
            return self._to_dict(goal)

    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        from core.models import GoalObjective
        with self._sessions()() as session:
            goal = session.query(GoalObjective).filter(GoalObjective.id == goal_id).first()
            return self._to_dict(goal) if goal else None

    def list_goals(self, status: Optional[str] = None, include_terminal: bool = True) -> List[Dict[str, Any]]:
        from core.models import GoalObjective
        with self._sessions()() as session:
            q = session.query(GoalObjective).filter(
                GoalObjective.workspace_id == self.workspace_id)
            if status:
                q = q.filter(GoalObjective.status == status)
            elif not include_terminal:
                q = q.filter(GoalObjective.status.notin_(("achieved", "failed")))
            goals = q.order_by(GoalObjective.created_at.desc()).limit(500).all()
            return [self._to_dict(g) for g in goals]

    # -------------------------------------------------------- state machine

    def transition(self, goal_id: str, new_status: str) -> Dict[str, Any]:
        from core.models import GoalObjective
        new_status = (new_status or "").strip().lower()
        if new_status not in GOAL_STATUSES:
            raise GoalTransitionError(f"unknown status '{new_status}'")
        with self._sessions()() as session:
            goal = session.query(GoalObjective).filter(GoalObjective.id == goal_id).first()
            if not goal:
                raise GoalTransitionError(f"goal {goal_id} not found")
            allowed = GOAL_TRANSITIONS.get(goal.status, set())
            if new_status not in allowed:
                raise GoalTransitionError(
                    f"illegal transition {goal.status} -> {new_status} "
                    f"(allowed: {sorted(allowed) or 'none — terminal'})")
            goal.status = new_status
            session.commit()
            session.refresh(goal)
            return self._to_dict(goal)

    # ------------------------------------------------------------ evaluation

    def evaluate(self, goal_id: str) -> Dict[str, Any]:
        """Run the goal's criteria; update progress and derived status.

        Progress = satisfied/total criteria (0 when no criteria). All
        satisfied -> achieved (guarded transition). Past target date and not
        achieved -> at_risk.
        """
        from core.models import GoalObjective
        evaluator = self._evaluator()
        with self._sessions()() as session:
            goal = session.query(GoalObjective).filter(GoalObjective.id == goal_id).first()
            if not goal:
                return {"error": f"goal {goal_id} not found"}
            results: List[CriterionResult] = evaluator.evaluate(goal.criteria or [])
            ratio = evaluator.satisfaction_ratio(results)
            goal.progress = round(ratio * 100.0, 2)

            if goal.criteria and evaluator.all_satisfied(results) and goal.status == "active":
                goal.status = "achieved"
            elif (goal.target_date is not None
                  and goal.target_date < datetime.now(timezone.utc)
                  and goal.status == "active"):
                goal.status = "at_risk"

            session.commit()
            session.refresh(goal)
            return {
                "goal_id": goal_id,
                "status": goal.status,
                "progress": goal.progress,
                "satisfied": sum(1 for r in results if r.satisfied),
                "total": len(results),
                "results": [r.to_dict() for r in results],
            }

    def add_criteria(self, goal_id: str, criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
        from core.models import GoalObjective
        with self._sessions()() as session:
            goal = session.query(GoalObjective).filter(GoalObjective.id == goal_id).first()
            if not goal:
                return {"error": f"goal {goal_id} not found"}
            merged = list(goal.criteria or []) + list(criteria or [])
            goal.criteria = merged
            session.commit()
            return {"goal_id": goal_id, "criteria_count": len(merged)}

    def update_progress_from_subtasks(self, goal_id: str,
                                      completed: int, total: int) -> Optional[Dict[str, Any]]:
        """Legacy bridge: GoalEngine-style subtask fraction, persisted."""
        from core.models import GoalObjective
        if total <= 0:
            return None
        with self._sessions()() as session:
            goal = session.query(GoalObjective).filter(GoalObjective.id == goal_id).first()
            if not goal:
                return None
            goal.progress = round(min(1.0, completed / total) * 100.0, 2)
            if goal.progress >= 100.0 and goal.status in ("active", "at_risk"):
                goal.status = "achieved"
            session.commit()
            return {"goal_id": goal_id, "progress": goal.progress, "status": goal.status}

    # ------------------------------------------------------------- objective

    def to_objective(self, goal_id: str):
        """Build a core.agent_objective.Objective from a persisted goal —
        the production injector for the (previously dormant) ReAct
        objective loop. The definition_of_done predicate runs this
        service's criterion evaluator, so agents terminate against
        machine-checkable goal state, not just a step budget."""
        from core.agent_objective import Objective
        record = self.get_goal(goal_id)
        if not record:
            return None
        evaluator = self._evaluator()

        def _done(state: Dict[str, Any]) -> bool:
            results = evaluator.evaluate(record.get("criteria") or [], state)
            return bool(results) and evaluator.all_satisfied(results)

        return Objective(
            goal=record["title"],
            definition_of_done=_done,
            constraints={"goal_id": goal_id, "workspace_id": self.workspace_id},
            success_criteria=[c.get("type", "?") for c in (record.get("criteria") or [])],
        )

    # ----------------------------------------------------------------- util

    @staticmethod
    def _to_dict(goal) -> Dict[str, Any]:
        return {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "status": goal.status,
            "progress": goal.progress,
            "criteria": goal.criteria or [],
            "key_results": goal.key_results or [],
            "owner_id": goal.owner_id,
            "parent_goal_id": goal.parent_goal_id,
            "source": goal.source,
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
            "created_at": goal.created_at.isoformat() if goal.created_at else None,
        }
