from __future__ import annotations

"""Pydantic v2 schemas for the Kanban Board API (Phase 1).

Conventions:
    * ``expected_version`` is REQUIRED on every PATCH so the server can enforce
      optimistic locking (mirrors DelegationChain at core/models.py:5567).
    * ``workspace: bool = False`` on TaskCreate signals "auto-create a Canvas
      of canvas_type='kanban' and link it to the task".
    * Read serializers embed a ``canvas`` summary so the frontend can render an
      "Open Workspace" affordance without a second round-trip.
"""

from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Column
# --------------------------------------------------------------------------- #
class ColumnCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    position: int = 0
    wip_limit: Union[int, None] = None


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    name: str
    position: int
    wip_limit: Union[int, None] = None
    version_id: int
    task_count: int = 0  # populated by the service layer


# --------------------------------------------------------------------------- #
# Board
# --------------------------------------------------------------------------- #
class BoardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Union[str, None] = Field(default=None, max_length=120)
    description: Union[str, None] = None
    # Optional: seed the board with the standard 6 columns on create
    seed_default_columns: bool = True


class BoardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: Union[str, None]
    description: Union[str, None]
    owner_user_id: Union[str, None]
    archived_at: Union[datetime, None]
    version_id: int
    created_at: datetime
    updated_at: datetime


class BoardDetail(BoardRead):
    columns: list[ColumnRead] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Task
# --------------------------------------------------------------------------- #
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Union[str, None] = None
    column_id: str
    status: str = "backlog"
    priority: str = "normal"
    assignee_user_id: Union[str, None] = None
    assignee_agent_id: Union[str, None] = None
    parent_task_id: Union[str, None] = None
    due_at: Union[datetime, None] = None
    labels: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    # When true, the server creates a Canvas of canvas_type="kanban" and links
    # it to the new task via task.canvas_id.
    workspace: bool = False


class TaskPatch(BaseModel):
    """PATCH body. Every field is optional; ``expected_version`` is required.

    A PATCH may carry any combination of:
        * ``column_id`` + ``sort_order`` (reorder / move column)
        * ``status`` (transition; validated against the state machine)
        * ``assignee_user_id`` / ``assignee_agent_id`` (assignment)
        * ``title`` / ``description`` / ``priority`` / ``due_at`` / ``labels``
        * ``workspace: true`` (idempotently create the Canvas if missing)
    """

    expected_version: int = Field(..., description="Client's view of version_id; mismatch -> 409")

    column_id: Union[str, None] = None
    sort_order: Union[float, None] = None
    status: Union[str, None] = None

    title: Union[str, None] = None
    description: Union[str, None] = None
    priority: Union[str, None] = None
    assignee_user_id: Union[str, None] = None
    assignee_agent_id: Union[str, None] = None
    due_at: Union[datetime, None] = None
    labels: Union[list[str], None] = None
    metadata_json: Union[dict[str, Any], None] = None

    # Idempotently create the task workspace Canvas if missing.
    workspace: Union[bool, None] = None


class CanvasSummary(BaseModel):
    """Minimal Canvas info embedded on TaskRead so the UI can link to it."""

    canvas_id: str
    name: str
    status: str
    artifact_count: int = 0
    presence_count: int = 0


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    column_id: str
    title: str
    description: Union[str, None]
    status: str
    priority: str
    assignee_user_id: Union[str, None]
    assignee_agent_id: Union[str, None]
    parent_task_id: Union[str, None]
    root_task_id: Union[str, None]
    sort_order: float
    due_at: Union[datetime, None]
    labels: list[Any] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: Union[str, None]
    canvas_id: Union[str, None]
    version_id: int
    created_at: datetime
    updated_at: datetime
    canvas: Union[CanvasSummary, None] = None


# --------------------------------------------------------------------------- #
# Rebalance
# --------------------------------------------------------------------------- #
class RebalanceRequest(BaseModel):
    """Body of POST /api/boards/{board_id}/rebalance.

    Floats accumulate rounding error over many fractional-index inserts.
    Clients SHOULD call rebalance periodically (e.g. nightly) per column.
    """

    column_id: Union[str, None] = None  # if None, rebalance every column


class RebalanceResult(BaseModel):
    rebalanced_columns: list[str]
    moved_tasks: int
