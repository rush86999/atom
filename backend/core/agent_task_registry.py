"""
Agent Task Registry

Manages asyncio tasks for agent execution with proper cancellation support.
Enables tracking and cancellation of running agents.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """Represents a running agent task"""
    task_id: str
    agent_id: str
    agent_run_id: str
    task: asyncio.Task
    user_id: str
    started_at: datetime = field(default_factory=datetime.now)
    status: str = "running"  # running, cancelled, completed, failed

    def cancel(self) -> bool:
        """Cancel the underlying asyncio task"""
        if not self.task.done():
            self.task.cancel()
            self.status = "cancelled"
            return True
        return False


class AgentTaskRegistry:
    """
    Global registry for managing agent tasks.

    Provides:
    - Task registration for running agents
    - Task cancellation by agent_id or task_id
    - Task status tracking
    - Cleanup of completed tasks
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._tasks: Dict[str, AgentTask] = {}  # task_id -> AgentTask
        self._agent_tasks: Dict[str, Set[str]] = {}  # agent_id -> set of task_ids
        self._run_tasks: Dict[str, str] = {}  # agent_run_id -> task_id
        self._initialized = True
        logger.info("AgentTaskRegistry initialized")

    def register_task(
        self,
        task_id: str,
        agent_id: str,
        agent_run_id: str,
        task: asyncio.Task,
        user_id: str
    ) -> None:
        """Register a new agent task"""
        agent_task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            task=task,
            user_id=user_id
        )

        self._tasks[task_id] = agent_task

        # Track by agent_id
        if agent_id not in self._agent_tasks:
            self._agent_tasks[agent_id] = set()
        self._agent_tasks[agent_id].add(task_id)

        # Track by agent_run_id
        self._run_tasks[agent_run_id] = task_id

        logger.info(f"Registered task {task_id} for agent {agent_id}, run {agent_run_id}")

    def unregister_task(self, task_id: str) -> None:
        """Unregister a completed task"""
        if task_id not in self._tasks:
            return

        agent_task = self._tasks[task_id]

        # Remove from agent_tasks
        if agent_task.agent_id in self._agent_tasks:
            self._agent_tasks[agent_task.agent_id].discard(task_id)
            if not self._agent_tasks[agent_task.agent_id]:
                del self._agent_tasks[agent_task.agent_id]

        # Remove from run_tasks
        if agent_task.agent_run_id in self._run_tasks:
            del self._run_tasks[agent_task.agent_run_id]

        # Remove from tasks
        del self._tasks[task_id]

        logger.info(f"Unregistered task {task_id}")

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task by task_id"""
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found in registry")
            return False

        agent_task = self._tasks[task_id]
        success = agent_task.cancel()

        if success:
            logger.info(f"Cancelled task {task_id}")
            # Unregister after a brief delay to allow cancellation to complete
            await asyncio.sleep(0.1)
            self.unregister_task(task_id)

        return success

    async def cancel_agent_tasks(self, agent_id: str) -> int:
        """Cancel all running tasks for an agent"""
        if agent_id not in self._agent_tasks:
            logger.warning(f"No tasks found for agent {agent_id}")
            return 0

        task_ids = list(self._agent_tasks[agent_id])
        cancelled_count = 0

        for task_id in task_ids:
            if await self.cancel_task(task_id):
                cancelled_count += 1

        logger.info(f"Cancelled {cancelled_count} tasks for agent {agent_id}")
        return cancelled_count

    async def cancel_agent_run(self, agent_run_id: str) -> bool:
        """Cancel a specific agent run"""
        if agent_run_id not in self._run_tasks:
            logger.warning(f"Agent run {agent_run_id} not found in registry")
            return False

        task_id = self._run_tasks[agent_run_id]
        return await self.cancel_task(task_id)

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get task by task_id"""
        return self._tasks.get(task_id)

    def get_agent_tasks(self, agent_id: str) -> list[AgentTask]:
        """Get all tasks for an agent"""
        if agent_id not in self._agent_tasks:
            return []

        return [
            self._tasks[task_id]
            for task_id in self._agent_tasks[agent_id]
        ]

    def is_agent_running(self, agent_id: str) -> bool:
        """Check if an agent has any running tasks"""
        return agent_id in self._agent_tasks and len(self._agent_tasks[agent_id]) > 0

    def get_task_id_by_run(self, agent_run_id: str) -> Optional[str]:
        """Get task_id by agent_run_id"""
        return self._run_tasks.get(agent_run_id)

    async def cleanup_completed_tasks(self) -> int:
        """Clean up completed/failed tasks"""
        to_remove = []

        for task_id, agent_task in self._tasks.items():
            if agent_task.task.done():
                to_remove.append(task_id)

        for task_id in to_remove:
            self.unregister_task(task_id)

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} completed tasks")

        return len(to_remove)

    def get_all_running_agents(self) -> Dict[str, list[str]]:
        """Get all agents with running tasks"""
        return {
            agent_id: list(task_ids)
            for agent_id, task_ids in self._agent_tasks.items()
        }


# Global registry instance
agent_task_registry = AgentTaskRegistry()


def register_agent_task(
    agent_id: str,
    agent_run_id: str,
    task: asyncio.Task,
    user_id: str
) -> str:
    """Helper function to register an agent task and return task_id"""
    import uuid
    task_id = str(uuid.uuid4())
    agent_task_registry.register_task(
        task_id=task_id,
        agent_id=agent_id,
        agent_run_id=agent_run_id,
        task=task,
        user_id=user_id
    )
    return task_id
