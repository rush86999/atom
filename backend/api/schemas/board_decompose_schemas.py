from __future__ import annotations

"""Decompose API schemas (Phase 4)."""

from typing import Union

from pydantic import BaseModel, Field

from core.board_decomposer import DecompositionResult, SubtaskProposal


class DecomposeRequest(BaseModel):
    spawn_workspaces: bool = False
    model_hint: Union[str, None] = Field(
        default=None,
        description="Optional BYOK model id override.",
    )


class DecomposeCommitRequest(BaseModel):
    proposals: list[SubtaskProposal]
    spawn_workspaces: bool = False


class DecomposePreview(BaseModel):
    parent_task_id: str
    rationale: str
    subtasks: list[SubtaskProposal]
    depth: int
    max_depth: int


class DecomposeCommitResult(BaseModel):
    parent_task_id: str
    created_task_ids: list[str]
    spawned_workspaces: bool
