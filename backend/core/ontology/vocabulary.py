"""Shared task/goal vocabulary with adapters (gap B3).

Atom had five mutually incompatible task-ish models (Objective dataclass,
Goal/GoalSubTask, BoardTask, WorkflowStep, fleet SubTask). This module
defines ONE shared vocabulary — kinds, typed relation names, and a common
node shape — plus lossless *adapters* that project each legacy model onto
it without migrating the underlying tables. Cross-system queries (e.g.
"every task in any system that DEPENDS_ON an unfulfilled outcome") become
possible by mapping rows through these adapters.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeKind(str, Enum):
    GOAL = "Goal"
    MILESTONE = "Milestone"
    TASK = "Task"
    ACTION = "Action"
    OUTCOME = "Outcome"
    AGENT = "Agent"
    SKILL = "Skill"
    INTEGRATION = "Integration"
    DOCUMENT = "Document"


class RelationName(str, Enum):
    """Typed relations of the shared vocabulary (RDFS-style property names)."""
    DECOMPOSES_INTO = "DECOMPOSES_INTO"    # Goal → Task/Milestone (HTN refinement)
    DEPENDS_ON = "DEPENDS_ON"              # Task → Task (ordering)
    ACHIEVES = "ACHIEVES"                  # Task/Action → Goal
    PRODUCES = "PRODUCES"                  # Task/Action → Outcome
    REQUIRES = "REQUIRES"                  # Task → Skill/Integration/Document
    ASSIGNED_TO = "ASSIGNED_TO"            # Task → Agent
    MEASURED_BY = "MEASURED_BY"            # Goal → Outcome (OKR key result)
    BLOCKS = "BLOCKS"                      # Outcome → Task (obstacle, KAOS-style)


class VocabularyNode:
    """A node in the shared vocabulary — duck-typed projection of any task model."""

    __slots__ = ("id", "kind", "title", "description", "status", "depends_on",
                 "parent_id", "source_system", "source_ref", "properties", "created_at")

    def __init__(
        self,
        kind: NodeKind,
        title: str,
        id: Optional[str] = None,
        description: str = "",
        status: str = "pending",
        depends_on: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
        source_system: str = "unknown",
        source_ref: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.kind = kind
        self.title = title
        self.description = description
        self.status = status
        self.depends_on = list(depends_on or [])
        self.parent_id = parent_id
        self.source_system = source_system
        self.source_ref = source_ref
        self.properties = dict(properties or {})
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "depends_on": self.depends_on,
            "parent_id": self.parent_id,
            "source_system": self.source_system,
            "source_ref": self.source_ref,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VocabularyNode {self.kind.value}:{self.title}>"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Dict-or-attribute access for the adapters."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------------------
# Adapters — one per legacy system
# ---------------------------------------------------------------------------

def from_board_task(task: Any) -> VocabularyNode:
    """Project a BoardTask (models_board.py) row or dict."""
    return VocabularyNode(
        kind=NodeKind.TASK,
        id=str(_get(task, "id", "") or ""),
        title=_get(task, "title", "") or "untitled board task",
        description=_get(task, "description", "") or "",
        status=(_get(task, "status", "") or "pending").upper(),
        depends_on=[],
        parent_id=str(_get(task, "parent_task_id") or "") or None,
        source_system="board",
        source_ref=str(_get(task, "id", "") or ""),
        properties={
            "board_id": _get(task, "board_id"),
            "priority": _get(task, "priority"),
            "root_task_id": _get(task, "root_task_id"),
        },
    )


def from_workflow_step(step: Any, workflow_id: Optional[str] = None) -> VocabularyNode:
    """Project a WorkflowStep (advanced_workflow_system.py) model."""
    return VocabularyNode(
        kind=NodeKind.TASK,
        id=str(_get(step, "step_id", "") or _get(step, "id", "") or ""),
        title=_get(step, "name", "") or "untitled step",
        description=_get(step, "description", "") or "",
        status="pending",
        depends_on=list(_get(step, "depends_on", []) or []),
        parent_id=workflow_id,
        source_system="workflow",
        source_ref=str(_get(step, "step_id", "") or ""),
        properties={
            "step_type": _get(step, "step_type"),
            "condition": _get(step, "condition"),
            "is_parallel": _get(step, "is_parallel"),
        },
    )


def from_fleet_subtask(subtask: Any) -> VocabularyNode:
    """Project a fleet TaskDecomposition SubTask (fleet_orchestration/)."""
    return VocabularyNode(
        kind=NodeKind.TASK,
        id=str(_get(subtask, "id", "") or ""),
        title=(_get(subtask, "description", "") or "untitled subtask")[:200],
        description=_get(subtask, "description", "") or "",
        status="pending",
        depends_on=list(_get(subtask, "depends_on", []) or []),
        source_system="fleet",
        properties={
            "required_domain": _get(subtask, "required_domain"),
            "can_parallelize": _get(subtask, "can_parallelize"),
            "estimated_tokens": _get(subtask, "estimated_tokens"),
        },
    )


def from_goal_subtask(subtask: Any) -> VocabularyNode:
    """Project a GoalEngine GoalSubTask (pydantic)."""
    return VocabularyNode(
        kind=NodeKind.TASK,
        id=str(_get(subtask, "id", "") or ""),
        title=_get(subtask, "title", "") or "untitled subtask",
        description=_get(subtask, "description", "") or "",
        status=(_get(subtask, "status", "PENDING") or "PENDING").upper(),
        source_system="goal_engine",
        properties={
            "due_date": getattr(_get(subtask, "due_date"), "isoformat", lambda: None)(),
            "assigned_to": _get(subtask, "assigned_to"),
        },
    )


def from_goal_objective(goal: Any) -> VocabularyNode:
    """Project a persisted GoalObjective (models.py) row or dict."""
    return VocabularyNode(
        kind=NodeKind.GOAL,
        id=str(_get(goal, "id", "") or ""),
        title=_get(goal, "title", "") or "untitled goal",
        description=_get(goal, "description", "") or "",
        status=(_get(goal, "status", "active") or "active").lower(),
        parent_id=_get(goal, "parent_goal_id"),
        source_system="goal_objective",
        properties={
            "progress": _get(goal, "progress", 0.0),
            "criteria_count": len(_get(goal, "criteria", []) or []),
            "key_results": _get(goal, "key_results", []) or [],
        },
    )


def relation(subject: VocabularyNode, name: RelationName, obj: VocabularyNode) -> Dict[str, Any]:
    """Construct a typed vocabulary relation triple."""
    return {
        "subject": subject.to_dict(),
        "predicate": name.value,
        "object": obj.to_dict(),
    }
