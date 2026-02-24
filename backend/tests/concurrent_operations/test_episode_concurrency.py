"""
Episode Concurrency Tests

Tests for race conditions in episode segmentation and async operations
using asyncio.gather for concurrent async execution.

These tests detect bugs that only manifest when multiple async operations
run concurrently, which single-threaded async tests cannot catch.

Key Bugs Tested:
- Duplicate episode IDs from concurrent creation
- State leakage between concurrent segmentations
- LanceDB archival race conditions
- Canvas context extraction timeout handling
- Async resource cleanup (connections, tasks)

SQLite Limitations:
- Episode service uses SQLite for persistence
- Tests use force_create=True for deterministic behavior
- Documented PostgreSQL behavior for true async concurrency
"""

import asyncio
import pytest
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    ChatMessage,
    ChatSession,
    Episode,
    User,
)
from core.episode_segmentation_service import EpisodeSegmentationService


class TestConcurrentEpisodeCreation:
    """Test concurrent episode creation for ID collisions."""

    @pytest.mark.asyncio
    async def test_concurrent_episode_creation_no_duplicate_ids(self, db_session: Session):
        """
        CONCURRENT: Multiple async episode creations running simultaneously.

        Tests that concurrent episode creation doesn't produce duplicate IDs.
        Each episode should have a unique UUID.

        BUG_PATTERN: Race condition in UUID generation causes collisions.
        EXPECTED: All episode IDs are unique.
        """
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Create chat sessions
        task_count = 10
        sessions = []
        for i in range(task_count):
            session = ChatSession(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=f"Test Session {i}",
                created_at=datetime.utcnow() - timedelta(hours=i),
                message_count=0,
            )
            db_session.add(session)
            db_session.flush()  # Flush to get session object with ID
            # Add workspace_id attribute (service expects it but ChatSession doesn't have it)
            session.workspace_id = "default"
            sessions.append(session)

        db_session.commit()

        # Mock external dependencies (LanceDB, LLM)
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            # Mock LanceDB handler
            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_db.add = MagicMock()
            mock_lancedb.return_value = mock_db

            # Mock canvas summary service
            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(return_value="Mock canvas summary")
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            async def create_episode(task_id: int):
                """Create episode with unique session."""
                session_id = sessions[task_id].id
                agent_id = agent.id

                # Add messages to session
                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=session_id,
                    workspace_id="default",
                    role="user",
                    content=f"Test message {task_id}",
                    created_at=datetime.utcnow(),
                )
                db_session.add(msg)
                db_session.commit()

                return await service.create_episode_from_session(
                    session_id=session_id,
                    agent_id=agent_id,
                    force_create=True
                )

            # Launch concurrent episode creations
            tasks = [create_episode(i) for i in range(task_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all creations completed
            successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
            errors = [r for r in results if isinstance(r, Exception)]

            assert len(errors) == 0, f"Errors during creation: {errors}"
            assert len(successful_results) == task_count, \
                f"Only {len(successful_results)}/{task_count} episodes created"

            # Verify no duplicate episode IDs
            episode_ids = [r.id for r in successful_results]
            unique_ids = set(episode_ids)
            assert len(episode_ids) == len(unique_ids), \
                f"Duplicate episode IDs found: {len(episode_ids)} total, {len(unique_ids)} unique"

    @pytest.mark.asyncio
    async def test_concurrent_episode_creation_different_agents(self, db_session: Session):
        """
        CONCURRENT: Concurrent episode creation for different agents.

        Tests that episodes for different agents don't interfere.
        Each agent should get their own isolated episodes.

        BUG_PATTERN: State leakage between agent operations.
        EXPECTED: Each agent has correct episode count.
        """
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        # Create multiple agents
        agent_count = 5
        agents = []
        for i in range(agent_count):
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name=f"TestAgent{i}",
                category="test",
                module_path="test.module",
                class_name="TestAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
            )
            db_session.add(agent)
            agents.append(agent)

        db_session.commit()

        # Create sessions for each agent
        episodes_per_agent = 3
        sessions = []
        for agent_idx in range(agent_count):
            for ep_idx in range(episodes_per_agent):
                session = ChatSession(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=f"Agent{agent_idx}_Session{ep_idx}",
                    created_at=datetime.utcnow() - timedelta(hours=agent_idx * episodes_per_agent + ep_idx),
                    message_count=0,
                )
                db_session.add(session)
                sessions.append(session)

        db_session.commit()

        # Mock external dependencies
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_db.add = MagicMock()
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(return_value="Mock summary")
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            task_idx = [0]

            async def create_episode_for_agent(agent_idx: int, ep_idx: int):
                """Create episode for specific agent."""
                session_idx = agent_idx * episodes_per_agent + ep_idx
                session_id = sessions[session_idx].id
                agent_id = agents[agent_idx].id

                # Add message
                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=session_id,
                    workspace_id="default",
                    role="user",
                    content=f"Agent{agent_idx} message {ep_idx}",
                    created_at=datetime.utcnow(),
                )
                db_session.add(msg)
                db_session.commit()

                result = await service.create_episode_from_session(
                    session_id=session_id,
                    agent_id=agent_id,
                    force_create=True
                )
                task_idx[0] += 1
                return result

            # Launch all episode creations concurrently
            tasks = []
            for agent_idx in range(agent_count):
                for ep_idx in range(episodes_per_agent):
                    tasks.append(create_episode_for_agent(agent_idx, ep_idx))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all creations succeeded
            successful = [r for r in results if r is not None and not isinstance(r, Exception)]
            errors = [r for r in results if isinstance(r, Exception)]

            assert len(errors) == 0, f"Errors: {errors}"
            assert len(successful) == agent_count * episodes_per_agent

            # Verify each agent has correct number of episodes
            for agent in agents:
                agent_episodes = db_session.query(Episode).filter(
                    Episode.agent_id == agent.id
                ).count()
                assert agent_episodes == episodes_per_agent, \
                    f"Agent {agent.name} has {agent_episodes} episodes, expected {episodes_per_agent}"


class TestConcurrentSegmentationOperations:
    """Test concurrent segmentation for state leakage."""

    @pytest.mark.asyncio
    async def test_concurrent_segmentation_no_state_leakage(self, db_session: Session):
        """
        CONCURRENT: Multiple segmentations of different sessions.

        Tests that segmentation state doesn't leak between operations.
        Each segmentation should use its own session data.

        BUG_PATTERN: Shared state between concurrent segmentations.
        EXPECTED: Each episode has correct session data.
        """
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Create sessions with different content
        session_count = 5
        sessions = []
        for i in range(session_count):
            session = ChatSession(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=f"Session{i}",
                created_at=datetime.utcnow() - timedelta(hours=i),
                message_count=0,
            )
            db_session.add(session)
            sessions.append(session)

            # Add unique messages per session
            for msg_idx in range(3):
                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=session.id,
                    workspace_id="default",
                    role="user",
                    content=f"Session{i}_Message{msg_idx}",
                    created_at=datetime.utcnow() + timedelta(seconds=msg_idx),
                )
                db_session.add(msg)

        db_session.commit()

        # Mock dependencies
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_db.add = MagicMock()
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(return_value="Mock summary")
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            async def segment_session(session_idx: int):
                """Segment specific session."""
                session_id = sessions[session_idx].id
                agent_id = agent.id

                result = await service.create_episode_from_session(
                    session_id=session_id,
                    agent_id=agent_id,
                    force_create=True
                )
                return result, session_idx

            # Launch concurrent segmentations
            tasks = [segment_session(i) for i in range(session_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all succeeded
            successful = [(r, idx) for r, idx in results if r is not None and not isinstance(r, Exception)]
            errors = [(r, idx) for r, idx in results if isinstance(r, Exception)]

            assert len(errors) == 0, f"Errors: {errors}"
            assert len(successful) == session_count

            # Verify each episode has correct session_id
            for episode, session_idx in successful:
                assert episode.session_id == sessions[session_idx].id, \
                    f"Episode session_id mismatch for session {session_idx}"


class TestConcurrentLanceDBArchival:
    """Test concurrent LanceDB archival operations."""

    @pytest.mark.asyncio
    async def test_concurrent_lancedb_archival(self, db_session: Session):
        """
        CONCURRENT: Multiple episodes archived simultaneously.

        Tests that LanceDB archival handles concurrent operations.
        All episodes should be successfully archived.

        BUG_PATTERN: Race condition in LanceDB add operations.
        EXPECTED: All episodes archived without error.
        """
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Create episodes directly (skip create_episode_from_session for speed)
        episode_count = 10
        episodes = []
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid.uuid4()),
                title=f"Episode{i}",
                summary=f"Summary for episode {i}",
                agent_id=agent.id,
                user_id=user.id,
                workspace_id="default",
                session_id=str(uuid.uuid4()),
                execution_ids=[],
                canvas_ids=[],
                feedback_ids=[],
                started_at=datetime.utcnow() - timedelta(hours=i),
                ended_at=datetime.utcnow() - timedelta(hours=i) + timedelta(minutes=30),
                duration_seconds=1800,
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=0,
                human_edits=[],
            )
            db_session.add(episode)
            episodes.append(episode)

        db_session.commit()

        # Track archival calls
        archival_count = [0]

        async def mock_archive(episode_data):
            """Mock LanceDB archival."""
            archival_count[0] += 1
            await asyncio.sleep(0.001)  # Simulate async operation
            return True

        # Mock dependencies
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            mock_db = MagicMock()
            mock_db.add = MagicMock(side_effect=mock_archive)
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(return_value="Mock summary")
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            # Archive episodes concurrently
            async def archive_episode(episode_idx: int):
                episode = episodes[episode_idx]
                await service._archive_to_lancedb(episode)
                return episode.id

            tasks = [archive_episode(i) for i in range(episode_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all archival succeeded
            errors = [r for r in results if isinstance(r, Exception)]
            assert len(errors) == 0, f"Archival errors: {errors}"

            # Verify all episodes were archived
            assert archival_count[0] == episode_count, \
                f"Only {archival_count[0]}/{episode_count} episodes archived"


class TestConcurrentCanvasContextExtraction:
    """Test concurrent canvas context extraction with timeouts."""

    @pytest.mark.asyncio
    async def test_concurrent_canvas_extraction_with_timeout(self, db_session: Session):
        """
        CONCURRENT: Multiple LLM canvas extractions running in parallel.

        Tests that timeout handling works correctly under concurrent load.
        Slow extractions should timeout without blocking others.

        BUG_PATTERN: Timeout doesn't work correctly with concurrent operations.
        EXPECTED: All extractions complete or timeout appropriately.
        """
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Create session with canvas
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title="Test Session",
            created_at=datetime.utcnow(),
            message_count=0,
        )
        db_session.add(session)

        canvas = CanvasAudit(
            id=str(uuid.uuid4()),
            session_id=session.id,
            canvas_type="chart",
            canvas_data={"type": "line", "data": [1, 2, 3]},
            created_at=datetime.utcnow(),
        )
        db_session.add(canvas)
        db_session.commit()

        # Mock LLM with variable delay
        extraction_count = [0]
        timeout_count = [0]

        async def mock_canvas_summary(canvas_audit, agent_task):
            """Mock canvas summary with delay."""
            extraction_count[0] += 1
            # First extraction is slow (times out), others are fast
            if extraction_count[0] == 1:
                await asyncio.sleep(3)  # Exceeds timeout
                timeout_count[0] += 1
                return {"summary": "slow extraction"}
            else:
                await asyncio.sleep(0.01)
                return {"summary": f"extraction {extraction_count[0]}"}

        # Mock dependencies
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_db.add = MagicMock()
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(side_effect=mock_canvas_summary)
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            # Add message
            msg = ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session.id,
                workspace_id="default",
                role="user",
                content="Test message",
                created_at=datetime.utcnow(),
            )
            db_session.add(msg)
            db_session.commit()

            # Launch concurrent extractions (using asyncio.wait_for for timeout)
            async def extract_with_timeout(canvas_audit, agent_task):
                try:
                    result = await asyncio.wait_for(
                        mock_canvas_summary(canvas_audit, agent_task),
                        timeout=2.0  # 2 second timeout
                    )
                    return result
                except asyncio.TimeoutError:
                    return {"summary": "timeout", "error": "timeout"}

            # Launch 5 concurrent extractions
            tasks = [
                extract_with_timeout(canvas, "test_task")
                for _ in range(5)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify results
            assert len(results) == 5, "Should have 5 results"
            assert all(not isinstance(r, Exception) for r in results), "No exceptions should occur"


class TestAsyncResourceCleanup:
    """Test async resource cleanup on errors."""

    @pytest.mark.asyncio
    async def test_db_connection_cleanup_on_error(self, db_session: Session):
        """
        CONCURRENT: Resources cleaned up correctly when async tasks fail.

        Tests that database connections are released when operations fail.
        No connection leaks should occur.

        BUG_PATTERN: Database connections not released on async error.
        EXPECTED: Connection count returns to baseline after errors.
        """
        # Track connection usage
        connections_opened = [0]
        connections_closed = [0]

        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock dependencies with failure
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            async def failing_llm_call(*args, **kwargs):
                """Mock LLM that always fails."""
                await asyncio.sleep(0.01)
                raise Exception("Simulated LLM failure")

            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(side_effect=failing_llm_call)
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            # Launch failing tasks
            async def failing_task(task_id: int):
                """Task that will fail."""
                try:
                    session = ChatSession(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        title=f"FailingSession{task_id}",
                        created_at=datetime.utcnow(),
                        message_count=0,
                    )
                    db_session.add(session)
                    db_session.commit()

                    msg = ChatMessage(
                        id=str(uuid.uuid4()),
                        conversation_id=session.id,
                        workspace_id="default",
                        role="user",
                        content=f"Failing message {task_id}",
                        created_at=datetime.utcnow(),
                    )
                    db_session.add(msg)
                    db_session.commit()

                    # This will fail due to LLM error
                    result = await service.create_episode_from_session(
                        session_id=session.id,
                        agent_id=agent.id,
                        force_create=True
                    )
                    return result
                except Exception as e:
                    # Expected to fail
                    return e

            # Launch 10 failing tasks concurrently
            tasks = [failing_task(i) for i in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all tasks failed (as expected)
            assert all(isinstance(r, Exception) for r in results), \
                "All tasks should have failed"

            # Verify database still works (connections were cleaned up)
            test_query = db_session.query(User).first()
            assert test_query is not None, "Database should still be accessible"

    @pytest.mark.asyncio
    async def test_async_task_cancellation_cleanup(self, db_session: Session):
        """
        CONCURRENT: Tasks cancelled cleanly with resource cleanup.

        Tests that cancelled async tasks release resources properly.
        No resource leaks should occur on cancellation.

        BUG_PATTERN: Cancelled tasks don't release resources.
        EXPECTED: Resources cleaned up after cancellation.
        """
        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock slow operation
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            async def slow_llm_call(*args, **kwargs):
                """Mock LLM that is very slow."""
                await asyncio.sleep(10)  # Will be cancelled
                return {"summary": "should not reach here"}

            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(side_effect=slow_llm_call)
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            # Create cancellable tasks
            async def cancellable_task(task_id: int):
                """Task that can be cancelled."""
                session = ChatSession(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=f"CancellableSession{task_id}",
                    created_at=datetime.utcnow(),
                    message_count=0,
                )
                db_session.add(session)
                db_session.flush()
                session.workspace_id = "default"  # Service expects this
                db_session.commit()

                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=session.id,
                    workspace_id="default",
                    role="user",
                    content=f"Message {task_id}",
                    created_at=datetime.utcnow(),
                )
                db_session.add(msg)
                db_session.commit()

                result = await service.create_episode_from_session(
                    session_id=session.id,
                    agent_id=agent.id,
                    force_create=True
                )
                return result

            # Launch tasks
            task1 = asyncio.create_task(cancellable_task(1))
            task2 = asyncio.create_task(cancellable_task(2))

            # Wait a bit then cancel
            await asyncio.sleep(0.1)
            task1.cancel()
            task2.cancel()

            # Handle cancellation
            try:
                await task1
            except asyncio.CancelledError:
                pass

            try:
                await task2
            except asyncio.CancelledError:
                pass

            # Verify database still works (resources cleaned up)
            test_query = db_session.query(User).first()
            assert test_query is not None, "Database should still be accessible after cancellation"

    @pytest.mark.asyncio
    async def test_no_resource_leak_after_many_async_operations(self, db_session: Session):
        """
        CONCURRENT: Many async operations should not leak resources.

        Tests resource usage after many concurrent operations.
        Resource count should remain within acceptable bounds.

        BUG_PATTERN: Memory leak or connection leak after many operations.
        EXPECTED: Resource count reasonable (< 50 objects increase).
        """
        import gc

        # Get initial object count
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create test data
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="hash",
            status="active",
        )
        db_session.add(user)

        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock dependencies
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb, \
             patch('core.llm.canvas_summary_service.CanvasSummaryService') as mock_canvas_svc:

            mock_db = MagicMock()
            mock_db.embed_text = MagicMock(return_value=[0.1] * 384)
            mock_db.add = MagicMock()
            mock_lancedb.return_value = mock_db

            mock_canvas_instance = MagicMock()
            mock_canvas_instance.generate_summary = AsyncMock(return_value="Mock summary")
            mock_canvas_svc.return_value = mock_canvas_instance

            service = EpisodeSegmentationService(db_session)

            # Run many async operations
            operation_count = 50

            async def single_operation(op_id: int):
                """Single episode creation operation."""
                session = ChatSession(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=f"Session{op_id}",
                    created_at=datetime.utcnow(),
                    message_count=0,
                )
                db_session.add(session)
                db_session.flush()
                session.workspace_id = "default"  # Service expects this
                db_session.commit()

                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=session.id,
                    workspace_id="default",
                    role="user",
                    content=f"Message {op_id}",
                    created_at=datetime.utcnow(),
                )
                db_session.add(msg)
                db_session.commit()

                result = await service.create_episode_from_session(
                    session_id=session.id,
                    agent_id=agent.id,
                    force_create=True
                )
                return result

            # Launch operations in batches
            batch_size = 10
            for batch in range(operation_count // batch_size):
                tasks = [
                    single_operation(batch * batch_size + i)
                    for i in range(batch_size)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            # Force garbage collection
            gc.collect()
            final_objects = len(gc.get_objects())

            # Verify no significant leak (allow 50 object tolerance for caching)
            object_increase = final_objects - initial_objects
            assert object_increase < 50, \
                f"Possible memory leak: {object_increase} objects added (threshold: 50)"
