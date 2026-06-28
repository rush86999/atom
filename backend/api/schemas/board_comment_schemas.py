from __future__ import annotations

"""Pydantic v2 schemas for board comment APIs (Phase 3)."""

from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Task-level comments (AgentMessage rows)
# --------------------------------------------------------------------------- #
class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10_000)
    parent_message_id: Union[str, None] = None  # for threading


class CommentPatch(BaseModel):
    content: str = Field(..., min_length=1, max_length=10_000)
    expected_version: Union[int, None] = None


class AuthorInfo(BaseModel):
    user_id: Union[str, None] = None
    agent_id: Union[str, None] = None
    display_name: Union[str, None] = None


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: Union[str, None]
    conversation_id: Union[str, None]
    content: str
    author: AuthorInfo
    parent_message_id: Union[str, None]
    created_at: datetime
    replies: list[CommentRead] = Field(default_factory=list)


CommentRead.model_rebuild()


# --------------------------------------------------------------------------- #
# Artifact-level comments (read-only view over ArtifactComment)
# --------------------------------------------------------------------------- #
class ArtifactCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_id: str
    canvas_id: Union[str, None]
    content: str
    user_id: Union[str, None]
    agent_id: Union[str, None]
    created_at: datetime
    updated_at: Union[datetime, None]


# --------------------------------------------------------------------------- #
# Slash command bridge
# --------------------------------------------------------------------------- #
class SlashReply(BaseModel):
    ok: bool = True
    reply: str
    action_type: str
    task_id: Union[str, None] = None
    extra: dict[str, Any] = Field(default_factory=dict)
