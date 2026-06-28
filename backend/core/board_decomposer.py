from __future__ import annotations

import logging
from typing import Any, Union

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from core.board_events import BoardEventEmitter
from core.board_service import BoardService
from core.models import Tenant, User
from core.models_board import BoardTask

logger = logging.getLogger(__name__)

MAX_ROOT_DEPTH = 3


class SubtaskProposal(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Union[str, None] = None
    column_name: str = Field(
        default="Backlog",
        description="Name of the destination column (matched case-insensitively on commit).",
    )
    priority: str = Field(default="normal")
    estimated_hours: Union[float, None] = None


class DecompositionResult(BaseModel):
    rationale: str = Field(default="")
    subtasks: list[SubtaskProposal]


class BoardDecomposer:
    """LLM-driven decomposition (Single-tenant)."""

    def __init__(
        self,
        db: Session,
        emitter: Union[BoardEventEmitter, None] = None,
    ):
        self.db = db
        self.board_service = BoardService(db)
        self.emitter = emitter or BoardEventEmitter()

    @staticmethod
    def _root_depth(task: BoardTask) -> int:
        if task.parent_task_id is None:
            return 1
        depth = 1
        current = task
        seen = {current.id}
        while current.parent_task_id is not None and depth <= MAX_ROOT_DEPTH + 1:
            parent = (
                current.parent_task
                if current.parent_task is not None
                else None
            )
            if parent is None or parent.id in seen:
                break
            seen.add(parent.id)
            depth += 1
            current = parent
        return depth

    @classmethod
    def _check_depth(cls, task: BoardTask) -> None:
        depth = cls._root_depth(task)
        if depth >= MAX_ROOT_DEPTH:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "depth_cap_exceeded",
                    "message": (
                        f"Refusing to decompose: task is already at depth {depth} "
                        f"(max {MAX_ROOT_DEPTH})."
                    ),
                    "current_depth": depth,
                    "max_depth": MAX_ROOT_DEPTH,
                },
            )

    @staticmethod
    def _check_byok(handler) -> None:
        clients = getattr(handler, "clients", {}) or {}
        if not clients:
            raise HTTPException(
                status_code=424,
                detail={
                    "error": "no_byok_key",
                    "message": (
                        "Task decomposition requires a tenant BYOK key. "
                        "Add one in Settings → API Keys."
                    ),
                },
                headers={"X-Setup-Hint": "byok-required"},
            )

    @staticmethod
    def _build_prompt(task: BoardTask, canvas_summary: str) -> str:
        return (
            f"Decompose the following Kanban task into 3-8 actionable subtasks.\n\n"
            f"TASK TITLE: {task.title}\n"
            f"TASK DESCRIPTION: {task.description or '(none)'}\n"
            f"PRIORITY: {task.priority}\n"
            f"{canvas_summary}\n\n"
            f"Return JSON matching this schema:\n"
            f'{{"rationale": "<short explanation>", '
            f'"subtasks": [{{"title": "...", "description": "...", '
            f'"column_name": "Backlog"|"To Do"|"In Progress", '
            f'"priority": "low"|"normal"|"high"|"urgent", '
            f'"estimated_hours": <float>}}]}}\n\n'
            f"Rules:\n"
            f"- Each subtask title must be a concrete action (verb + object).\n"
            f"- Order subtasks by suggested execution order.\n"
            f"- Prefer fewer, well-scoped subtasks over many trivial ones.\n"
            f"- Return ONLY the JSON object; no commentary."
        )

    def _canvas_artifact_summary(self, task: BoardTask) -> str:
        if task.canvas_id is None:
            return "CANVAS: (none)"
        from core.models import Artifact

        rows = (
            self.db.query(Artifact)
            .filter(Artifact.canvas_id == str(task.canvas_id))
            .order_by(Artifact.created_at.desc())
            .limit(20)
            .all()
        )
        if not rows:
            return "CANVAS: present, no artifacts yet"
        bullets = "\n".join(f"  - [{a.type}] {a.name}" for a in rows)
        return f"CANVAS ARTIFACTS:\n{bullets}"

    async def propose(
        self,
        board_id: str,
        task_id: str,
        handler,
    ) -> DecompositionResult:
        task = self.board_service._get_task_scoped(task_id, board_id)
        self._check_depth(task)
        self._check_byok(handler)

        prompt = self._build_prompt(task, self._canvas_artifact_summary(task))

        try:
            structured = await handler.generate_structured_response(
                prompt=prompt,
                system_instruction=(
                    "You are a senior engineering manager decomposing a task. "
                    "Be precise. Always return a valid JSON object matching the schema."
                ),
                response_model=DecompositionResult,
                temperature=0.3,
                task_type="board_decompose",
            )
        except Exception as e:
            logger.warning("Decompose LLM call failed (task=%s): %s", task_id, e)
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "decompose_llm_failed",
                    "message": "The LLM call failed. Please retry.",
                },
            ) from e

        if structured is None:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "decompose_llm_no_response",
                    "message": "The LLM returned no response. Check BYOK key and quota.",
                },
            )

        if isinstance(structured, dict):
            try:
                structured = DecompositionResult.model_validate(structured)
            except ValidationError as e:
                logger.warning("Decompose LLM returned malformed JSON: %s", e)
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "decompose_llm_malformed",
                        "message": "The LLM returned malformed JSON.",
                    },
                ) from e

        if not structured.subtasks:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "decompose_empty",
                    "message": "The LLM proposed zero subtasks.",
                },
            )
        if len(structured.subtasks) > 8:
            structured.subtasks = structured.subtasks[:8]

        return structured

    def commit(
        self,
        board_id: str,
        parent_task_id: str,
        proposals: list[SubtaskProposal],
        created_by_user_id: Union[str, None],
        spawn_workspaces: bool = False,
    ) -> list[BoardTask]:
        parent = self.board_service._get_task_scoped(parent_task_id, board_id)
        self._check_depth(parent)

        columns_by_name = {
            c.name.lower(): c for c in self.board_service.list_columns(board_id)
        }
        default_column = columns_by_name.get("backlog") or next(iter(columns_by_name.values()))

        tenant_id: str = "default"
        if created_by_user_id:
            user = self.db.query(User).filter(User.id == created_by_user_id).first()
            if user and user.tenant_id:
                tenant_id = str(user.tenant_id)

        if tenant_id == "default":
            tenant = self.db.query(Tenant).first()
            if tenant and tenant.id:
                tenant_id = str(tenant.id)

        created: list[BoardTask] = []
        try:
            for i, p in enumerate(proposals):
                col = columns_by_name.get(p.column_name.strip().lower(), default_column)

                child = BoardTask(
                    board_id=board_id,
                    column_id=col.id,
                    title=p.title,
                    description=p.description,
                    status="backlog",
                    priority=p.priority or "normal",
                    parent_task_id=parent.id,
                    root_task_id=parent.root_task_id or parent.id,
                    sort_order=float(i),
                    created_by_user_id=created_by_user_id,
                )
                self.db.add(child)
                self.db.flush()
                if spawn_workspaces:
                    self.board_service.create_task_workspace(child, tenant_id=tenant_id)
                created.append(child)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        for c in created:
            self.db.refresh(c)
        return created
