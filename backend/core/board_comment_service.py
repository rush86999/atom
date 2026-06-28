from __future__ import annotations

import logging
from typing import Any, Union

from fastapi import HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.models import AgentMessage, Artifact, ArtifactComment, Tenant, User
from core.models_board import Board, BoardTask

logger = logging.getLogger(__name__)

TASK_COMMENT_CONVERSATION_PREFIX = "board_task:"


def task_conversation_id(task_id: str) -> str:
    return f"{TASK_COMMENT_CONVERSATION_PREFIX}{task_id}"


class BoardCommentService:
    """Reads + writes task-level comments; reads artifact-level comments (Single-tenant)."""

    def __init__(self, db: Session):
        self.db = db

    def _get_task_scoped(
        self, board_id: str, task_id: str
    ) -> BoardTask:
        task = (
            self.db.query(BoardTask)
            .filter(
                BoardTask.id == task_id,
                BoardTask.board_id == board_id,
            )
            .first()
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def _resolve_author_display(
        self, msg: AgentMessage
    ) -> tuple[Union[str, None], Union[str, None], Union[str, None]]:
        if msg.from_user_id:
            user = (
                self.db.query(User)
                .filter(User.id == msg.from_user_id)
                .first()
            )
            name = None
            if user:
                name = (f"{user.first_name or ''} {user.last_name or ''}".strip()) or user.email
            return str(msg.from_user_id), None, name
        return None, str(msg.from_agent_id) if msg.from_agent_id else None, "Agent"

    def _serialize(self, msg: AgentMessage) -> dict[str, Any]:
        user_id, agent_id, display = self._resolve_author_display(msg)
        return {
            "id": str(msg.id),
            "task_id": str(msg.task_id) if msg.task_id else None,
            "conversation_id": msg.conversation_id,
            "content": msg.content,
            "author": {
                "user_id": user_id,
                "agent_id": agent_id,
                "display_name": display,
            },
            "parent_message_id": str(msg.parent_message_id) if msg.parent_message_id else None,
            "created_at": msg.created_at,
        }

    def create_comment(
        self,
        board_id: str,
        task_id: str,
        author_user_id: Union[str, None],
        content: str,
        parent_message_id: Union[str, None] = None,
        author_agent_id: Union[str, None] = None,
    ) -> AgentMessage:
        if bool(author_user_id) == bool(author_agent_id):
            raise HTTPException(
                status_code=422,
                detail="Exactly one of author_user_id / author_agent_id is required.",
            )

        task = self._get_task_scoped(board_id, task_id)

        if parent_message_id is not None:
            parent = (
                self.db.query(AgentMessage)
                .filter(
                    AgentMessage.id == parent_message_id,
                    AgentMessage.conversation_id == task_conversation_id(task_id),
                )
                .first()
            )
            if parent is None:
                raise HTTPException(
                    status_code=404, detail="Parent comment not found in this thread"
                )

        tenant_id = None
        if author_user_id:
            user = self.db.query(User).filter(User.id == author_user_id).first()
            tenant_id = user.tenant_id if user else None

        if not tenant_id:
            tenant = self.db.query(Tenant).first()
            tenant_id = tenant.id if tenant else "default"

        msg = AgentMessage(
            tenant_id=tenant_id,
            from_agent_id=author_agent_id,
            from_user_id=author_user_id,
            to_agent_id=None,
            message_type="board_comment",
            content=content,
            task_id=str(task.id),
            parent_message_id=parent_message_id,
            conversation_id=task_conversation_id(task_id),
            status="delivered",
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def list_comments(
        self,
        board_id: str,
        task_id: str,
        limit: int = 100,
        before_id: Union[str, None] = None,
    ) -> list[AgentMessage]:
        self._get_task_scoped(board_id, task_id)

        q = (
            self.db.query(AgentMessage)
            .filter(
                AgentMessage.conversation_id == task_conversation_id(task_id),
                AgentMessage.message_type == "board_comment",
            )
            .order_by(AgentMessage.created_at.asc())
            .limit(min(limit, 500))
        )
        if before_id is not None:
            cursor = self.db.query(AgentMessage).filter(AgentMessage.id == before_id).first()
            if cursor is not None:
                q = q.filter(AgentMessage.created_at < cursor.created_at)
        return q.all()

    def build_thread_tree(self, messages: list[AgentMessage]) -> list[dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {}
        for m in messages:
            nodes[str(m.id)] = {**self._serialize(m), "replies": []}

        roots: list[dict[str, Any]] = []
        for m in messages:
            node = nodes[str(m.id)]
            if m.parent_message_id and str(m.parent_message_id) in nodes:
                nodes[str(m.parent_message_id)]["replies"].append(node)
            else:
                roots.append(node)
        return roots

    def patch_comment(
        self,
        comment_id: str,
        author_user_id: str,
        new_content: str,
    ) -> AgentMessage:
        msg = (
            self.db.query(AgentMessage)
            .filter(
                AgentMessage.id == comment_id,
                AgentMessage.message_type == "board_comment",
            )
            .first()
        )
        if msg is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        if msg.from_user_id is None or str(msg.from_user_id) != str(author_user_id):
            raise HTTPException(status_code=403, detail="Only the comment author can edit")
        msg.content = new_content
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def delete_comment(
        self,
        comment_id: str,
        author_user_id: str,
    ) -> None:
        msg = (
            self.db.query(AgentMessage)
            .filter(
                AgentMessage.id == comment_id,
                AgentMessage.message_type == "board_comment",
            )
            .first()
        )
        if msg is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        if msg.from_user_id is None or str(msg.from_user_id) != str(author_user_id):
            raise HTTPException(status_code=403, detail="Only the comment author can delete")
        self.db.delete(msg)
        self.db.commit()

    def list_artifact_comments_for_task(
        self,
        board_id: str,
        task_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        task = self._get_task_scoped(board_id, task_id)
        if task.canvas_id is None:
            return []

        rows = (
            self.db.query(ArtifactComment, Artifact)
            .join(Artifact, ArtifactComment.artifact_id == Artifact.id)
            .filter(
                Artifact.canvas_id == str(task.canvas_id),
            )
            .order_by(desc(ArtifactComment.created_at))
            .limit(min(limit, 500))
            .all()
        )
        out = []
        for ac, _artifact in rows:
            out.append(
                {
                    "id": str(ac.id),
                    "artifact_id": str(ac.artifact_id),
                    "canvas_id": str(task.canvas_id),
                    "content": ac.content,
                    "user_id": str(ac.user_id) if ac.user_id else None,
                    "agent_id": str(ac.agent_id) if ac.agent_id else None,
                    "created_at": ac.created_at,
                    "updated_at": getattr(ac, "updated_at", None),
                }
            )
        return out
