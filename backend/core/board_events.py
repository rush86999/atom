from __future__ import annotations

"""
Board event emitter (Phase 2).

Thin wrapper around ``ConnectionManager.broadcast_event`` that:
    * Always uses the board channel ``board:{board_id}``.
    * Dual-broadcasts to the linked Canvas channel when a task transition
      affects its workspace.
    * Standardises the payload shape.
"""

import logging
from typing import Any, Union

from core.websockets import ConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Board event-type constants.
# --------------------------------------------------------------------------- #
BOARD_TASK_CREATED = "board:task:created"
BOARD_TASK_MOVED = "board:task:moved"
BOARD_TASK_TRANSITIONED = "board:task:transitioned"
BOARD_TASK_UPDATED = "board:task:updated"
BOARD_TASK_DELETED = "board:task:deleted"
BOARD_COMMENT_POSTED = "board:comment:posted"


def _attach_constants_to_manager() -> None:
    attrs = {
        "BOARD_TASK_CREATED": BOARD_TASK_CREATED,
        "BOARD_TASK_MOVED": BOARD_TASK_MOVED,
        "BOARD_TASK_TRANSITIONED": BOARD_TASK_TRANSITIONED,
        "BOARD_TASK_UPDATED": BOARD_TASK_UPDATED,
        "BOARD_TASK_DELETED": BOARD_TASK_DELETED,
        "BOARD_COMMENT_POSTED": BOARD_COMMENT_POSTED,
    }
    for name, value in attrs.items():
        if not hasattr(ConnectionManager, name):
            setattr(ConnectionManager, name, value)


_attach_constants_to_manager()


def board_channel(board_id: str) -> str:
    """Channel name for board-level broadcasts."""
    return f"board:{board_id}"


def canvas_channel(canvas_id: str) -> str:
    """Channel name for canvas-level broadcasts."""
    return f"canvas:{canvas_id}"


class BoardEventEmitter:
    """Stateless emitter. Constructed per-mutation; passes through to manager."""

    def __init__(self, manager: Union[ConnectionManager, None] = None):
        self.manager = manager or get_connection_manager()

    # ------------------------------------------------------------------- #
    # Helpers
    # ------------------------------------------------------------------- #
    @staticmethod
    def _task_summary(task: Any) -> dict[str, Any]:
        """Pull the fields the frontend reducer needs off the task."""
        if isinstance(task, dict):
            return {
                "id": str(task.get("id")),
                "board_id": str(task.get("board_id")),
                "column_id": str(task.get("column_id")),
                "title": task.get("title"),
                "status": task.get("status"),
                "sort_order": float(task.get("sort_order", 0.0)),
                "version_id": task.get("version_id"),
                "canvas_id": (
                    str(task.get("canvas_id")) if task.get("canvas_id") else None
                ),
            }
        # ORM instance
        return {
            "id": str(task.id),
            "board_id": str(task.board_id),
            "column_id": str(task.column_id),
            "title": task.title,
            "status": task.status,
            "sort_order": float(task.sort_order),
            "version_id": task.version_id,
            "canvas_id": str(task.canvas_id) if task.canvas_id else None,
        }

    async def _dual_broadcast(
        self,
        board_id: str,
        canvas_id: Union[str, None],
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast to the board channel + (if set) the linked Canvas channel."""
        bchan = board_channel(board_id)
        await self.manager.broadcast_event(bchan, event_type, payload)
        if canvas_id:
            await self.manager.broadcast_event(
                canvas_channel(canvas_id),
                event_type,
                payload,
            )

    # ------------------------------------------------------------------- #
    # Public emit_* helpers
    # ------------------------------------------------------------------- #
    async def emit_task_created(self, task: Any) -> None:
        summary = self._task_summary(task)
        await self._dual_broadcast(
            board_id=summary["board_id"],
            canvas_id=summary.get("canvas_id"),
            event_type=BOARD_TASK_CREATED,
            payload={"task": summary},
        )

    async def emit_task_moved(self, task: Any, from_column_id: str, to_column_id: str) -> None:
        summary = self._task_summary(task)
        await self._dual_broadcast(
            board_id=summary["board_id"],
            canvas_id=summary.get("canvas_id"),
            event_type=BOARD_TASK_MOVED,
            payload={
                "task": summary,
                "from_column_id": from_column_id,
                "to_column_id": to_column_id,
            },
        )

    async def emit_task_transitioned(
        self, task: Any, from_status: str, to_status: str
    ) -> None:
        summary = self._task_summary(task)
        await self._dual_broadcast(
            board_id=summary["board_id"],
            canvas_id=summary.get("canvas_id"),
            event_type=BOARD_TASK_TRANSITIONED,
            payload={
                "task": summary,
                "from_status": from_status,
                "to_status": to_status,
            },
        )

    async def emit_task_updated(self, task: Any) -> None:
        """Generic field-update event."""
        summary = self._task_summary(task)
        await self._dual_broadcast(
            board_id=summary["board_id"],
            canvas_id=summary.get("canvas_id"),
            event_type=BOARD_TASK_UPDATED,
            payload={"task": summary},
        )

    async def emit_task_deleted(self, task: Any) -> None:
        summary = self._task_summary(task)
        await self.manager.broadcast_event(
            board_channel(summary["board_id"]),
            BOARD_TASK_DELETED,
            {"task_id": summary["id"], "board_id": summary["board_id"]},
        )

    async def emit_comment_posted(
        self,
        task: Any,
        comment_id: str,
        comment_payload: dict[str, Any],
    ) -> None:
        summary = self._task_summary(task)
        await self._dual_broadcast(
            board_id=summary["board_id"],
            canvas_id=summary.get("canvas_id"),
            event_type=BOARD_COMMENT_POSTED,
            payload={
                "task_id": summary["id"],
                "comment_id": comment_id,
                "comment": comment_payload,
            },
        )
