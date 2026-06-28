from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Union

from sqlalchemy.orm import Session

from core.board_events import BoardEventEmitter
from core.board_state_machine import BoardStatus
from core.database import SessionLocal
from core.models import AgentCanvasPresence, Canvas, Tenant
from core.models_board import BoardTask

logger = logging.getLogger(__name__)


class BoardDispatcher:
    """Periodic loop that advances ready board tasks (Single-tenant)."""

    LOCK_KEY = "board:dispatcher:lock"
    LOCK_TTL_SECONDS = 30
    TICK_INTERVAL_SECONDS = 5
    STALE_PRESENCE_TIMEOUT = timedelta(minutes=10)

    def __init__(
        self,
        session_factory=SessionLocal,
        emitter: Union[BoardEventEmitter, None] = None,
        tick_interval_seconds: int = TICK_INTERVAL_SECONDS,
        machine_id: Union[str, None] = None,
    ):
        self._session_factory = session_factory
        self._emitter = emitter or BoardEventEmitter()
        self._tick_interval = tick_interval_seconds
        self._machine_id = machine_id or f"machine-{uuid.uuid4().hex[:8]}"
        self._task: Union[asyncio.Task, None] = None
        self._stopping = False

    # ------------------------------------------------------------------- #
    # Lifecycle
    # ------------------------------------------------------------------- #
    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop(), name="board-dispatcher")
        logger.info("BoardDispatcher started (machine_id=%s)", self._machine_id)

    async def stop(self) -> None:
        self._stopping = True
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("BoardDispatcher stopped")

    # ------------------------------------------------------------------- #
    # Loop
    # ------------------------------------------------------------------- #
    async def _run_loop(self) -> None:
        while not self._stopping:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("BoardDispatcher tick failed: %s", e)
            await asyncio.sleep(self._tick_interval)

    async def _tick(self) -> None:
        if not await self._acquire_lock():
            return

        session = self._session_factory()
        try:
            claimed = self._claim_ready_tasks(session)
            for task in claimed:
                try:
                    self._dispatch_one(session, task)
                except Exception as e:
                    logger.exception(
                        "Failed to dispatch task %s: %s", task.id, e
                    )
            self._reap_stale(session)
            session.commit()
        finally:
            session.close()
            await self._release_lock()

    # ------------------------------------------------------------------- #
    # Distributed lock
    # ------------------------------------------------------------------- #
    async def _acquire_lock(self) -> bool:
        try:
            from core.sync_job_queue import job_queue
            client = await job_queue.async_client
            if client is None:
                return True
            acquired = await client.set(
                self.LOCK_KEY, self._machine_id, nx=True, ex=self.LOCK_TTL_SECONDS
            )
            return bool(acquired)
        except Exception as e:
            logger.warning("Dispatcher lock acquire failed (%s); assuming leader", e)
            return True

    async def _release_lock(self) -> None:
        try:
            from core.sync_job_queue import job_queue
            client = await job_queue.async_client
            if client is None:
                return
            value = await client.get(self.LOCK_KEY)
            if value == self._machine_id:
                await client.delete(self.LOCK_KEY)
        except Exception:
            pass

    # ------------------------------------------------------------------- #
    # Claim + dispatch
    # ------------------------------------------------------------------- #
    def _claim_ready_tasks(self, session: Session) -> list[BoardTask]:
        MAX_BATCH = 50
        try:
            rows = (
                session.query(BoardTask)
                .filter(
                    BoardTask.status == BoardStatus.TODO,
                    BoardTask.assignee_agent_id.isnot(None),
                )
                .order_by(BoardTask.due_at.is_(None), BoardTask.due_at.asc())
                .limit(MAX_BATCH)
                .with_for_update(skip_locked=True)
                .all()
            )
        except Exception as e:
            if "for_update" in str(e).lower() or "skip_locked" in str(e).lower() or "near" in str(e).lower():
                rows = (
                    session.query(BoardTask)
                    .filter(
                        BoardTask.status == BoardStatus.TODO,
                        BoardTask.assignee_agent_id.isnot(None),
                    )
                    .order_by(BoardTask.due_at.is_(None), BoardTask.due_at.asc())
                    .limit(MAX_BATCH)
                    .all()
                )
            else:
                raise
        return rows

    def _dispatch_one(self, session: Session, task: BoardTask) -> None:
        if not self._governance_allows(session, task):
            logger.info(
                "Governance denied board_task_execute for agent %s on task %s",
                task.assignee_agent_id,
                task.id,
            )
            return

        previous_status = task.status
        try:
            from core.board_state_machine import assert_transition
            assert_transition(previous_status, BoardStatus.IN_PROGRESS)
        except Exception:
            return

        task.status = BoardStatus.IN_PROGRESS
        try:
            session.flush()
        except Exception:
            session.rollback()
            return

        if task.canvas_id is not None:
            self._join_canvas(session, task)

        logger.info(
            "Dispatched task %s -> in_progress (agent=%s, board=%s)",
            task.id, task.assignee_agent_id, task.board_id,
        )

    def _governance_allows(self, session: Session, task: BoardTask) -> bool:
        try:
            from core.agent_governance_service import AgentGovernanceService
            from core.models import AgentRegistry
            agent = session.query(AgentRegistry).filter(AgentRegistry.id == str(task.assignee_agent_id)).first()
            workspace_id = agent.workspace_id if agent else "default"

            svc = AgentGovernanceService(db=session, workspace_id=workspace_id)
            result = svc.can_perform_action(
                agent_id=str(task.assignee_agent_id),
                action_type="board_task_execute",
            )
            return bool(result.get("allowed"))
        except Exception as e:
            logger.warning(
                "Governance check failed for task %s (allowing): %s", task.id, e
            )
            return True

    def _join_canvas(self, session: Session, task: BoardTask) -> None:
        existing = (
            session.query(AgentCanvasPresence)
            .filter(
                AgentCanvasPresence.agent_id == str(task.assignee_agent_id),
                AgentCanvasPresence.canvas_id == str(task.canvas_id),
                AgentCanvasPresence.status == "active",
            )
            .first()
        )
        if existing is not None:
            existing.current_action = f"Working on: {task.title}"
            existing.joined_at = datetime.now(timezone.utc)
            return

        canvas = session.query(Canvas).filter(Canvas.id == str(task.canvas_id)).first()
        tenant_id = canvas.tenant_id if canvas else None
        if not tenant_id:
            tenant = session.query(Tenant).first()
            tenant_id = tenant.id if tenant else "default"

        session.add(
            AgentCanvasPresence(
                agent_id=str(task.assignee_agent_id),
                canvas_id=str(task.canvas_id),
                tenant_id=str(tenant_id),
                role="contributor",
                status="active",
                current_action=f"Working on: {task.title}",
            )
        )

    def _reap_stale(self, session: Session) -> None:
        threshold = datetime.now(timezone.utc) - self.STALE_PRESENCE_TIMEOUT
        stale = (
            session.query(AgentCanvasPresence)
            .filter(
                AgentCanvasPresence.status == "active",
                AgentCanvasPresence.joined_at < threshold,
            )
            .all()
        )
        for p in stale:
            p.status = "left"
            p.left_at = datetime.now(timezone.utc)


dispatcher = BoardDispatcher()
