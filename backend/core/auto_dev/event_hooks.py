"""
Auto-Dev Event Hooks

Lightweight event bus for triggering learning loops from lifecycle events
in the episodic memory system. Decouples the core EpisodeService and
SandboxExecutor from the Auto-Dev engines.

Usage:
    from core.auto_dev.event_hooks import event_bus

    # Register a listener
    @event_bus.on_task_fail
    async def handle_failure(event: TaskEvent):
        ...

    # Emit from EpisodeService
    await event_bus.emit_task_fail(TaskEvent(...))
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class TaskEvent:
    """Event payload for task lifecycle events."""

    episode_id: str
    agent_id: str
    tenant_id: str
    task_description: str = ""
    error_trace: str | None = None
    outcome: str = ""  # "success", "failure", "partial"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillExecutionEvent:
    """Event payload for skill execution events."""

    execution_id: str
    agent_id: str
    tenant_id: str
    skill_id: str
    skill_name: str = ""
    execution_seconds: float = 0.0
    token_usage: int = 0
    success: bool = False
    output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Type alias for event handler functions
EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """
    Simple in-process event bus for Auto-Dev lifecycle events.

    Supports three event types:
    - on_task_fail: triggered when an episode ends in failure
    - on_task_success: triggered when an episode completes successfully
    - on_skill_execution: triggered after a skill is executed in sandbox
    """

    def __init__(self):
        self._fail_handlers: list[EventHandler] = []
        self._success_handlers: list[EventHandler] = []
        self._skill_handlers: list[EventHandler] = []

    # --- Decorator registration ---

    def on_task_fail(self, handler: EventHandler) -> EventHandler:
        """Register a handler for task failure events."""
        self._fail_handlers.append(handler)
        return handler

    def on_task_success(self, handler: EventHandler) -> EventHandler:
        """Register a handler for task success events."""
        self._success_handlers.append(handler)
        return handler

    def on_skill_execution(self, handler: EventHandler) -> EventHandler:
        """Register a handler for skill execution events."""
        self._skill_handlers.append(handler)
        return handler

    # --- Emission ---

    async def emit_task_fail(self, event: TaskEvent) -> None:
        """Emit a task failure event to all registered handlers."""
        await self._dispatch(self._fail_handlers, event, "on_task_fail")

    async def emit_task_success(self, event: TaskEvent) -> None:
        """Emit a task success event to all registered handlers."""
        await self._dispatch(self._success_handlers, event, "on_task_success")

    async def emit_skill_execution(self, event: SkillExecutionEvent) -> None:
        """Emit a skill execution event to all registered handlers."""
        await self._dispatch(self._skill_handlers, event, "on_skill_execution")

    # --- Internal ---

    async def _dispatch(
        self, handlers: list[EventHandler], event: Any, event_name: str
    ) -> None:
        """Dispatch event to all handlers, catching exceptions to prevent cascade."""
        if not handlers:
            return

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Auto-Dev event handler error in {event_name} "
                    f"(handler={handler.__name__}): {e}",
                    exc_info=True,
                )

    def clear(self) -> None:
        """Remove all registered handlers. Useful for testing."""
        self._fail_handlers.clear()
        self._success_handlers.clear()
        self._skill_handlers.clear()


# Global singleton — imported by EpisodeService and SandboxExecutor
event_bus = EventBus()
