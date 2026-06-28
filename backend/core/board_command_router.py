from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.schemas.board_comment_schemas import SlashReply
from api.schemas.board_schemas import TaskCreate, TaskPatch
from core.board_comment_service import BoardCommentService
from core.board_service import BoardService
from core.board_state_machine import (
    BoardStatus,
    allowed_next_statuses,
    is_transition_allowed,
)
from core.models_board import BoardColumn, BoardTask

logger = logging.getLogger(__name__)


class BoardCommandRouter:
    """Translates parsed slash commands into Board*Service calls (Single-tenant)."""

    STATUS_ALIASES: dict[str, str] = {
        "backlog": BoardStatus.BACKLOG,
        "todo": BoardStatus.TODO,
        "to-do": BoardStatus.TODO,
        "to_do": BoardStatus.TODO,
        "in_progress": BoardStatus.IN_PROGRESS,
        "in-progress": BoardStatus.IN_PROGRESS,
        "inprogress": BoardStatus.IN_PROGRESS,
        "doing": BoardStatus.IN_PROGRESS,
        "in_review": BoardStatus.IN_REVIEW,
        "in-review": BoardStatus.IN_REVIEW,
        "review": BoardStatus.IN_REVIEW,
        "blocked": BoardStatus.BLOCKED,
        "done": BoardStatus.DONE,
        "complete": BoardStatus.DONE,
        "completed": BoardStatus.DONE,
    }

    def __init__(self, db: Session):
        self.db = db
        self.board_service = BoardService(db)
        self.comment_service = BoardCommentService(db)

    def _resolve_task(
        self, board_id: Union[str, None], task_ref: str
    ) -> Union[BoardTask, None]:
        try:
            uuid.UUID(task_ref)
            q = self.db.query(BoardTask).filter(BoardTask.id == task_ref)
            if board_id:
                q = q.filter(BoardTask.board_id == board_id)
            return q.first()
        except (ValueError, AttributeError):
            pass

        if len(task_ref) >= 4:
            q = self.db.query(BoardTask)
            if board_id:
                q = q.filter(BoardTask.board_id == board_id)
            rows = q.all()
            matches = [r for r in rows if str(r.id).lower().endswith(task_ref.lower())]
            if len(matches) == 1:
                return matches[0]
        return None

    def _resolve_column_by_name(
        self, board_id: str, name: str
    ) -> Union[BoardColumn, None]:
        cols = (
            self.db.query(BoardColumn)
            .filter(BoardColumn.board_id == board_id)
            .all()
        )
        return next((c for c in cols if c.name.lower() == name.lower()), None)

    def _resolve_status(self, word: str) -> Union[str, None]:
        return self.STATUS_ALIASES.get(word.strip().lower())

    def route(
        self,
        action_type: str,
        parameters: dict[str, Any],
        user_id: str,
        board_id: Union[str, None] = None,
    ) -> SlashReply:
        try:
            handler = {
                "board_create": self._cmd_create,
                "board_move": self._cmd_move,
                "board_assign": self._cmd_assign,
                "board_comment": self._cmd_comment,
                "board_list": self._cmd_list,
                "board_decompose": self._cmd_decompose_stub,
            }.get(action_type)
            if handler is None:
                return SlashReply(
                    ok=False,
                    reply=f"Unknown board command: {action_type}",
                    action_type=action_type,
                )
            return handler(
                parameters=parameters,
                user_id=user_id,
                board_id=board_id,
            )
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            return SlashReply(
                ok=False,
                reply=f"Couldn't do that: {detail}",
                action_type=action_type,
            )
        except Exception as e:
            logger.exception("BoardCommandRouter error on %s: %s", action_type, e)
            return SlashReply(
                ok=False,
                reply="Something went wrong running that command. The team has been notified.",
                action_type=action_type,
            )

    def _cmd_create(
        self, parameters, user_id, board_id
    ) -> SlashReply:
        title = parameters.get("title")
        column_name = parameters.get("column") or "Backlog"
        if not title:
            return SlashReply(
                ok=False, reply="Title is required.", action_type="board_create"
            )
        if not board_id:
            return SlashReply(
                ok=False,
                reply="No board context. Open a board first.",
                action_type="board_create",
            )

        col = self._resolve_column_by_name(board_id, column_name)
        if col is None:
            return SlashReply(
                ok=False,
                reply=f"No column named {column_name!r} on this board.",
                action_type="board_create",
                extra={"available_columns": self._column_names(board_id)},
            )

        task = self.board_service.create_task(
            board_id=board_id,
            created_by_user_id=user_id,
            payload=TaskCreate(title=title, column_id=str(col.id)),
        )
        return SlashReply(
            ok=True,
            reply=f"Created *{task.title}* in {col.name}.",
            action_type="board_create",
            task_id=str(task.id),
        )

    def _cmd_move(
        self, parameters, user_id, board_id
    ) -> SlashReply:
        task_ref = parameters.get("task_id")
        target_word = parameters.get("target") or parameters.get("status")
        if not task_ref or not target_word:
            return SlashReply(
                ok=False,
                reply="Usage: /task move <task_id> to <status>",
                action_type="board_move",
            )

        target_status = self._resolve_status(target_word)
        if target_status is None:
            return SlashReply(
                ok=False,
                reply=f"Unknown status {target_word!r}. Try one of: {', '.join(sorted(set(self.STATUS_ALIASES)))}.",
                action_type="board_move",
            )

        task = self._resolve_task(board_id, task_ref)
        if task is None:
            return SlashReply(
                ok=False,
                reply=f"Couldn't find a task matching {task_ref!r}.",
                action_type="board_move",
            )

        if task.status == target_status:
            return SlashReply(
                ok=True,
                reply=f"Task is already {target_status}.",
                action_type="board_move",
                task_id=str(task.id),
            )

        if not is_transition_allowed(task.status, target_status):
            allowed = sorted(allowed_next_statuses(task.status))
            return SlashReply(
                ok=False,
                reply=f"Can't move a {task.status!r} task to {target_status!r}. Allowed: {', '.join(allowed) or '(none)'}.",
                action_type="board_move",
                task_id=str(task.id),
                extra={"allowed_next": allowed},
            )

        updated, _meta = self.board_service.patch_task(
            board_id=str(task.board_id),
            task_id=str(task.id),
            payload=TaskPatch(expected_version=task.version_id, status=target_status),
        )
        return SlashReply(
            ok=True,
            reply=f"Moved *{updated.title}* to {target_status}.",
            action_type="board_move",
            task_id=str(updated.id),
        )

    def _cmd_assign(
        self, parameters, user_id, board_id
    ) -> SlashReply:
        task_ref = parameters.get("task_id")
        assignee = parameters.get("assignee")
        if not task_ref or not assignee:
            return SlashReply(
                ok=False,
                reply="Usage: /task assign <task_id> to <user_or_agent>",
                action_type="board_assign",
            )

        task = self._resolve_task(board_id, task_ref)
        if task is None:
            return SlashReply(
                ok=False,
                reply=f"Couldn't find a task matching {task_ref!r}.",
                action_type="board_assign",
            )

        try:
            uuid.UUID(assignee)
            user_id_target = assignee
        except (ValueError, AttributeError):
            from core.models import User

            user = (
                self.db.query(User)
                .filter(
                    User.email.ilike(f"{assignee}@%"),
                )
                .first()
            )
            if user is None:
                return SlashReply(
                    ok=False,
                    reply=f"Couldn't find user {assignee!r}.",
                    action_type="board_assign",
                )
            user_id_target = str(user.id)

        updated, _meta = self.board_service.patch_task(
            board_id=str(task.board_id),
            task_id=str(task.id),
            payload=TaskPatch(
                expected_version=task.version_id,
                assignee_user_id=user_id_target,
            ),
        )
        return SlashReply(
            ok=True,
            reply=f"Assigned *{updated.title}*.",
            action_type="board_assign",
            task_id=str(updated.id),
        )

    def _cmd_comment(
        self, parameters, user_id, board_id
    ) -> SlashReply:
        task_ref = parameters.get("task_id")
        content = parameters.get("content")
        if not task_ref or not content:
            return SlashReply(
                ok=False,
                reply="Usage: /task comment <task_id> <text>",
                action_type="board_comment",
            )

        task = self._resolve_task(board_id, task_ref)
        if task is None:
            return SlashReply(
                ok=False,
                reply=f"Couldn't find a task matching {task_ref!r}.",
                action_type="board_comment",
            )

        msg = self.comment_service.create_comment(
            board_id=str(task.board_id),
            task_id=str(task.id),
            author_user_id=user_id,
            content=content,
        )
        return SlashReply(
            ok=True,
            reply=f"Posted comment on *{task.title}*.",
            action_type="board_comment",
            task_id=str(task.id),
            extra={"comment_id": str(msg.id)},
        )

    def _cmd_list(
        self, parameters, user_id, board_id
    ) -> SlashReply:
        status_filter = parameters.get("status")
        if not board_id:
            return SlashReply(
                ok=False,
                reply="No board context. Open a board first.",
                action_type="board_list",
            )

        tasks = self.board_service.list_tasks(board_id)
        if status_filter:
            canonical = self._resolve_status(status_filter)
            if canonical is None:
                return SlashReply(
                    ok=False,
                    reply=f"Unknown status {status_filter!r}.",
                    action_type="board_list",
                )
            tasks = [t for t in tasks if t.status == canonical]

        if not tasks:
            return SlashReply(
                ok=True,
                reply="No tasks." if not status_filter else f"No {status_filter} tasks.",
                action_type="board_list",
            )

        lines = []
        for t in tasks[:10]:
            short_id = str(t.id).split("-")[0]
            lines.append(f"• `{short_id}` {t.title} ({t.status})")
        trailer = "" if len(tasks) <= 10 else f"\n_…and {len(tasks) - 10} more_"
        return SlashReply(
            ok=True,
            reply="\n".join(lines) + trailer,
            action_type="board_list",
        )

    def _cmd_decompose_stub(
        self, parameters, user_id, board_id
    ) -> SlashReply:
        return SlashReply(
            ok=False,
            reply=(
                "/task decompose lands in Phase 4. "
                "Use the REST endpoint for now."
            ),
            action_type="board_decompose",
        )

    def _column_names(self, board_id: str) -> list[str]:
        return [
            c.name
            for c in self.board_service.list_columns(board_id)
        ]


SLASH_PATTERNS: dict[str, dict[str, Any]] = {
    r"^/task\s+create\s+(.+?)(?:\s+in\s+(\w[\w\s]*))?$": {
        "action_type": "board_create",
        "title_group": 1,
        "column_group": 2,
    },
    r"^/task\s+move\s+(\S+)\s+to\s+(\w[\w-]*)$": {
        "action_type": "board_move",
        "task_id_group": 1,
        "target_group": 2,
    },
    r"^/task\s+assign\s+(\S+)\s+to\s+(\S+)$": {
        "action_type": "board_assign",
        "task_id_group": 1,
        "assignee_group": 2,
    },
    r"^/task\s+comment\s+(\S+)\s+(.+)$": {
        "action_type": "board_comment",
        "task_id_group": 1,
        "content_group": 2,
    },
    r"^/task\s+list(?:\s+(\w[\w-]*))?$": {
        "action_type": "board_list",
        "status_group": 1,
    },
    r"^/task\s+decompose\s+(\S+)$": {
        "action_type": "board_decompose",
        "task_id_group": 1,
    },
}


def parse_slash(text: str) -> Union[tuple[str, dict[str, Any]], None]:
    text = text.strip()
    for pattern, config in SLASH_PATTERNS.items():
        m = re.match(pattern, text, re.IGNORECASE)
        if not m:
            continue
        groups = m.groups()
        action = config["action_type"]
        params: dict[str, Any] = {}
        if "title_group" in config:
            params["title"] = groups[config["title_group"] - 1]
        if "column_group" in config:
            params["column"] = groups[config["column_group"] - 1]
        if "task_id_group" in config:
            params["task_id"] = groups[config["task_id_group"] - 1]
        if "target_group" in config:
            params["target"] = groups[config["target_group"] - 1]
        if "assignee_group" in config:
            params["assignee"] = groups[config["assignee_group"] - 1]
        if "content_group" in config:
            params["content"] = groups[config["content_group"] - 1]
        if "status_group" in config:
            params["status"] = groups[config["status_group"] - 1]
        return action, params
    return None
