"""
Tests for Agent Task Cancellation
"""

import pytest
import asyncio
import uuid
from datetime import datetime

from core.agent_task_registry import (
    AgentTaskRegistry,
    register_agent_task,
    agent_task_registry
)


class TestAgentTaskRegistry:
    """Test agent task registry functionality"""

    def test_registry_singleton(self):
        """Test that registry is a singleton"""
        registry1 = AgentTaskRegistry()
        registry2 = AgentTaskRegistry()

        # Should be the same instance
        assert registry1 is registry2

    @pytest.mark.asyncio
    async def test_register_task(self):
        """Test registering a new task"""
        task_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        agent_run_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        # Create a simple async task
        async def dummy_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            task=task,
            user_id=user_id
        )

        # Verify task is registered
        assert agent_task_registry.is_agent_running(agent_id)
        assert task_id in agent_task_registry._tasks
        assert agent_task_registry.get_task(task_id) is not None

        # Cleanup
        task.cancel()
        agent_task_registry.unregister_task(task_id)

    @pytest.mark.asyncio
    async def test_get_task_by_id(self):
        """Test retrieving task by ID"""
        task_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        agent_run_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        async def dummy_task():
            await asyncio.sleep(5)

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            task=task,
            user_id=user_id
        )

        retrieved_task = agent_task_registry.get_task(task_id)

        assert retrieved_task is not None
        assert retrieved_task.task_id == task_id
        assert retrieved_task.agent_id == agent_id
        assert retrieved_task.user_id == user_id

        # Cleanup
        task.cancel()
        agent_task_registry.unregister_task(task_id)

    @pytest.mark.asyncio
    async def test_get_agent_tasks(self):
        """Test retrieving all tasks for an agent"""
        agent_id = str(uuid.uuid4())

        # Register multiple tasks for the same agent
        for i in range(3):
            task_id = str(uuid.uuid4())

            async def dummy_task():
                await asyncio.sleep(5)

            task = asyncio.create_task(dummy_task())

            agent_task_registry.register_task(
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=str(uuid.uuid4()),
                task=task,
                user_id=str(uuid.uuid4())
            )

        # Get all tasks for agent
        tasks = agent_task_registry.get_agent_tasks(agent_id)

        assert len(tasks) == 3
        assert all(t.agent_id == agent_id for t in tasks)

        # Cleanup
        for task_obj in tasks:
            task_obj.task.cancel()
            agent_task_registry.unregister_task(task_obj.task_id)

    @pytest.mark.asyncio
    async def test_is_agent_running(self):
        """Test checking if agent is running"""
        agent_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        # Initially not running
        assert not agent_task_registry.is_agent_running(agent_id)

        # Register a task
        async def dummy_task():
            await asyncio.sleep(5)

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=str(uuid.uuid4()),
            task=task,
            user_id=str(uuid.uuid4())
        )

        # Now should be running
        assert agent_task_registry.is_agent_running(agent_id)

        # Cleanup
        task.cancel()
        agent_task_registry.unregister_task(task_id)

        # No longer running
        assert not agent_task_registry.is_agent_running(agent_id)

    @pytest.mark.asyncio
    async def test_get_all_running_agents(self):
        """Test getting all running agents"""
        # Register tasks for multiple agents
        agents = [str(uuid.uuid4()) for _ in range(3)]

        for agent_id in agents:
            async def dummy_task():
                await asyncio.sleep(5)

            task = asyncio.create_task(dummy_task())

            agent_task_registry.register_task(
                task_id=str(uuid.uuid4()),
                agent_id=agent_id,
                agent_run_id=str(uuid.uuid4()),
                task=task,
                user_id=str(uuid.uuid4())
            )

        # Get all running agents
        running = agent_task_registry.get_all_running_agents()

        assert len(running) == 3
        for agent_id in agents:
            assert agent_id in running
            assert len(running[agent_id]) > 0

        # Cleanup
        for agent_id in agents:
            await agent_task_registry.cancel_agent_tasks(agent_id)

    @pytest.mark.asyncio
    async def test_task_status_tracking(self):
        """Test that task status is properly tracked"""
        task_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())

        async def dummy_task():
            await asyncio.sleep(5)

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=str(uuid.uuid4()),
            task=task,
            user_id=str(uuid.uuid4())
        )

        agent_task = agent_task_registry.get_task(task_id)

        # Initial status should be "running"
        assert agent_task.status == "running"

        # Cancel task
        agent_task.cancel()

        # Status should now be "cancelled"
        assert agent_task.status == "cancelled"

        # Cleanup
        await asyncio.sleep(0.1)
        agent_task_registry.unregister_task(task_id)


class TestTaskCancellation:
    """Test task cancellation functionality"""

    @pytest.mark.asyncio
    async def test_cancel_single_task(self):
        """Test cancelling a single task"""
        task_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())

        # Create a long-running task
        task_stopped = False

        async def long_running_task():
            nonlocal task_stopped
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                task_stopped = True
                raise

        task = asyncio.create_task(long_running_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=str(uuid.uuid4()),
            task=task,
            user_id=str(uuid.uuid4())
        )

        # Cancel the task
        success = await agent_task_registry.cancel_task(task_id)

        # Verify cancellation
        assert success is True

        # Wait a bit for cancellation to process
        await asyncio.sleep(0.2)

        # Task should be cancelled
        assert task_stopped or task.cancelled()

        # Task should be unregistered
        assert agent_task_registry.get_task(task_id) is None

    @pytest.mark.asyncio
    async def test_cancel_agent_tasks(self):
        """Test cancelling all tasks for an agent"""
        agent_id = str(uuid.uuid4())

        # Register multiple tasks
        task_count = 5

        for i in range(task_count):
            task_id = str(uuid.uuid4())

            async def dummy_task():
                try:
                    await asyncio.sleep(100)
                except asyncio.CancelledError:
                    raise

            task = asyncio.create_task(dummy_task())

            agent_task_registry.register_task(
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=str(uuid.uuid4()),
                task=task,
                user_id=str(uuid.uuid4())
            )

        # Cancel all agent tasks
        cancelled_count = await agent_task_registry.cancel_agent_tasks(agent_id)

        assert cancelled_count == task_count

        # Wait for cancellations to process
        await asyncio.sleep(0.2)

        # Agent should no longer be running
        assert not agent_task_registry.is_agent_running(agent_id)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist"""
        task_id = str(uuid.uuid4())

        success = await agent_task_registry.cancel_task(task_id)

        assert success is False

    @pytest.mark.asyncio
    async def test_cancel_agent_run(self):
        """Test cancelling a specific agent run"""
        agent_id = str(uuid.uuid4())
        agent_run_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        # Create a task
        async def dummy_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                raise

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            task=task,
            user_id=str(uuid.uuid4())
        )

        # Cancel by agent_run_id
        success = await agent_task_registry.cancel_agent_run(agent_run_id)

        assert success is True

        # Wait for cancellation
        await asyncio.sleep(0.2)

        # Verify task was cancelled
        assert not agent_task_registry.is_agent_running(agent_id)


class TestHelperFunctions:
    """Test helper functions"""

    @pytest.mark.asyncio
    async def test_register_agent_task_helper(self):
        """Test register_agent_task helper function"""
        agent_id = str(uuid.uuid4())
        agent_run_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        async def dummy_task():
            await asyncio.sleep(5)

        task = asyncio.create_task(dummy_task())

        # Use helper function
        task_id = register_agent_task(
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            task=task,
            user_id=user_id
        )

        # Verify task was registered
        assert agent_task_registry.get_task(task_id) is not None
        assert agent_task_registry.is_agent_running(agent_id)

        # Cleanup
        task.cancel()
        agent_task_registry.unregister_task(task_id)


class TestTaskCleanup:
    """Test task cleanup functionality"""

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self):
        """Test cleanup of completed tasks"""
        agent_id = str(uuid.uuid4())

        # Create tasks that complete quickly
        for i in range(3):
            task_id = str(uuid.uuid4())

            async def quick_task():
                await asyncio.sleep(0.1)

            task = asyncio.create_task(quick_task())

            agent_task_registry.register_task(
                task_id=task_id,
                agent_id=agent_id,
                agent_run_id=str(uuid.uuid4()),
                task=task,
                user_id=str(uuid.uuid4())
            )

        # Wait for tasks to complete
        await asyncio.sleep(0.3)

        # Run cleanup
        cleaned_count = await agent_task_registry.cleanup_completed_tasks()

        assert cleaned_count == 3

        # Tasks should be removed
        assert not agent_task_registry.is_agent_running(agent_id)

    @pytest.mark.asyncio
    async def test_unregister_task(self):
        """Test unregistering a task"""
        task_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())

        async def dummy_task():
            await asyncio.sleep(5)

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=agent_id,
            agent_run_id=str(uuid.uuid4()),
            task=task,
            user_id=str(uuid.uuid4())
        )

        # Verify task is registered
        assert agent_task_registry.get_task(task_id) is not None

        # Unregister
        agent_task_registry.unregister_task(task_id)

        # Allow async cleanup to complete
        await asyncio.sleep(0.1)

        # Verify task is gone
        assert agent_task_registry.get_task(task_id) is None
        assert not agent_task_registry.is_agent_running(agent_id)

        # Cleanup task
        task.cancel()

    @pytest.mark.asyncio
    async def test_get_task_id_by_run(self):
        """Test getting task_id by agent_run_id"""
        agent_run_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        async def dummy_task():
            await asyncio.sleep(5)

        task = asyncio.create_task(dummy_task())

        agent_task_registry.register_task(
            task_id=task_id,
            agent_id=str(uuid.uuid4()),
            agent_run_id=agent_run_id,
            task=task,
            user_id=str(uuid.uuid4())
        )

        # Lookup task_id by run_id
        found_task_id = agent_task_registry.get_task_id_by_run(agent_run_id)

        assert found_task_id == task_id

        # Cleanup
        task.cancel()
        agent_task_registry.unregister_task(task_id)
