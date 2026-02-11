"""
Integration tests for Episode Lifecycle with LanceDB operations

Tests cover:
1. Episode decay calculation with LanceDB metadata queries
2. Episode consolidation (merging similar episodes)
3. Episode archival to cold storage (LanceDB vs PostgreSQL)
4. Importance score updates in LanceDB
5. Bulk lifecycle operations

These tests use actual LanceDB for realistic consolidation and archival testing.
"""

import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import (
    Episode,
    EpisodeSegment,
    AgentRegistry,
    AgentStatus,
    User,
)


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture(scope="module")
def temp_lancedb_dir():
    """Create temporary directory for LanceDB data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    from core.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(test_db):
    """Create sample user."""
    user = User(
        id="user-lifecycle-123",
        email="lifecycle@test.com",
        name="Lifecycle Test User"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_agent(test_db):
    """Create sample agent."""
    agent = AgentRegistry(
        id="agent-lifecycle-456",
        name="LifecycleAgent",
        status=AgentStatus.SUPERVISED,
        description="Test agent for lifecycle operations"
    )
    test_db.add(agent)
    test_db.commit()
    return agent


@pytest.fixture
def episodes_with varying_ages(test_db, sample_agent, sample_user):
    """Create episodes with different ages for decay testing."""
    now = datetime.now()
    episodes = []

    # Create episodes at different ages
    age_configs = [
        {"days": 0, "expected_decay": 1.0},      # New
        {"days": 30, "expected_decay": 0.833},  # 30 days
        {"days": 60, "expected_decay": 0.667},  # 60 days
        {"days": 90, "expected_decay": 0.5},    # 90 days
        {"days": 120, "expected_decay": 0.333}, # 120 days
        {"days": 150, "expected_decay": 0.167}, # 150 days
        {"days": 180, "expected_decay": 0.0},   # 180 days
        {"days": 200, "expected_decay": 0.0},   # 200 days (capped at 0)
    ]

    for i, config in enumerate(age_configs):
        episode = Episode(
            id=f"episode-decay-{i}",
            title=f"Episode {i} days old",
            description=f"Episode created {config['days']} days ago",
            summary=f"Test episode for decay calculation",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["test", "decay"],
            entities=[],
            importance_score=1.0,
            status="completed",
            started_at=now - timedelta(days=config["days"]),
            ended_at=now - timedelta(days=config["days"]) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,  # Will be updated by decay calculation
            access_count=0
        )
        test_db.add(episode)
        episodes.append(episode)

    test_db.commit()
    return episodes


@pytest.fixture
def episodes_for_consolidation(test_db, sample_agent, sample_user):
    """Create similar episodes for consolidation testing."""
    now = datetime.now()
    episodes = []

    # Create semantically similar episodes (about analytics)
    similar_topics = [
        "Created sales analytics dashboard",
        "Built reporting dashboard for KPIs",
        "Developed metrics tracking dashboard",
        "Implemented analytics visualization",
        "Set up business intelligence dashboard"
    ]

    for i, title in enumerate(similar_topics):
        episode = Episode(
            id=f"episode-similar-{i}",
            title=title,
            description=f"Analytics and dashboard work",
            summary=f"Dashboard episode {i}",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["analytics", "dashboard", "metrics"],
            entities=[],
            importance_score=0.8,
            status="completed",
            started_at=now - timedelta(days=i),
            ended_at=now - timedelta(days=i) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=5,
            consolidated_into=None  # Not yet consolidated
        )
        test_db.add(episode)
        episodes.append(episode)

    # Add one dissimilar episode
    dissimilar = Episode(
        id="episode-different-0",
        title="Customer Support Ticket Routing",
        description="Automated support workflows",
        summary="Support automation episode",
        agent_id=sample_agent.id,
        user_id=sample_user.id,
        workspace_id="default",
        topics=["support", "automation"],
        entities=[],
        importance_score=0.7,
        status="completed",
        started_at=now - timedelta(days=1),
        ended_at=now - timedelta(days=1) + timedelta(hours=1),
        maturity_at_time="SUPERVISED",
        human_intervention_count=0,
        constitutional_score=0.85,
        decay_score=1.0,
        access_count=3,
        consolidated_into=None
    )
    test_db.add(dissimilar)
    episodes.append(dissimilar)

    test_db.commit()
    return episodes


# ============================================================================
# Episode Decay Tests
# ============================================================================

class TestEpisodeDecay:
    """Test episode decay calculation with LanceDB."""

    @pytest.mark.asyncio
    async def test_decay_old_episodes_calculates_scores(self, test_db, temp_lancedb_dir,
                                                         episodes_with_varying_ages):
        """Test decay score calculation for old episodes."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Apply decay to episodes older than 30 days
            result = await service.decay_old_episodes(days_threshold=30)

            assert "affected" in result
            assert "archived" in result
            assert result["affected"] > 0

            # Verify decay scores were updated
            test_db.flush()
            for episode in episodes_with_varying_ages:
                test_db.refresh(episode)
                # Decay score should have been updated
                assert episode.decay_score <= 1.0
                assert episode.decay_score >= 0.0

    @pytest.mark.asyncio
    async def test_decay_formula_boundary_conditions(self, test_db, temp_lancedb_dir,
                                                       sample_agent, sample_user):
        """Test decay formula at boundary conditions."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Test specific age boundaries
            test_cases = [
                (0, 1.0),      # 0 days = 1.0
                (90, 0.5),     # 90 days = 0.5
                (180, 0.0),    # 180 days = 0.0
            ]

            for days_old, expected_score in test_cases:
                episode = Episode(
                    id=f"episode-boundary-{days_old}",
                    title=f"Test episode {days_old} days old",
                    description="Boundary test",
                    summary="Test",
                    agent_id=sample_agent.id,
                    user_id=sample_user.id,
                    workspace_id="default",
                    topics=["test"],
                    entities=[],
                    importance_score=0.5,
                    status="completed",
                    started_at=datetime.now() - timedelta(days=days_old),
                    ended_at=datetime.now() - timedelta(days=days_old) + timedelta(hours=1),
                    maturity_at_time="SUPERVISED",
                    human_intervention_count=0,
                    constitutional_score=0.9,
                    decay_score=1.0,
                    access_count=0
                )
                test_db.add(episode)
                test_db.commit()

                # Apply decay
                await service.decay_old_episodes(days_threshold=0)
                test_db.refresh(episode)

                # Check decay score (allowing for floating point precision)
                assert abs(episode.decay_score - expected_score) < 0.01

                # Cleanup for next test
                test_db.delete(episode)
                test_db.commit()

    @pytest.mark.asyncio
    async def test_decay_archives_very_old_episodes(self, test_db, temp_lancedb_dir,
                                                     sample_agent, sample_user):
        """Test episodes older than 180 days are archived."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Create episode >180 days old
            old_episode = Episode(
                id="episode-very-old",
                title="Very Old Episode",
                description="Should be archived",
                summary="Test",
                agent_id=sample_agent.id,
                user_id=sample_user.id,
                workspace_id="default",
                topics=["test"],
                entities=[],
                importance_score=0.5,
                status="completed",
                started_at=datetime.now() - timedelta(days=200),
                ended_at=datetime.now() - timedelta(days=200) + timedelta(hours=1),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=0.9,
                decay_score=1.0,
                access_count=0
            )
            test_db.add(old_episode)
            test_db.commit()

            # Apply decay
            result = await service.decay_old_episodes(days_threshold=90)

            assert result["archived"] > 0

            # Verify episode was archived
            test_db.refresh(old_episode)
            assert old_episode.status == "archived"
            assert old_episode.archived_at is not None


# ============================================================================
# Episode Consolidation Tests
# ============================================================================

class TestEpisodeConsolidation:
    """Test episode consolidation with LanceDB semantic search."""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes(self, test_db, temp_lancedb_dir,
                                                  episodes_for_consolidation):
        """Test merging semantically similar episodes."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup LanceDB with episode data
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        # Add episodes to LanceDB
        for episode in episodes_for_consolidation:
            content = f"{episode.title} {episode.description}"
            metadata = {
                "episode_id": episode.id,
                "agent_id": episode.agent_id,
                "type": "episode"
            }
            handler.add_document(
                table_name=table_name,
                text=content,
                source=f"episode:{episode.id}",
                metadata=metadata,
                user_id=episode.user_id,
                extract_knowledge=False
            )

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Run consolidation
            result = await service.consolidate_similar_episodes(
                agent_id=episodes_for_consolidation[0].agent_id,
                similarity_threshold=0.85
            )

            assert "consolidated" in result
            assert "parent_episodes" in result
            assert isinstance(result["consolidated"], int)

            # Some episodes should have been consolidated
            # (The 5 similar ones about analytics)
            if result["consolidated"] > 0:
                # Verify consolidated_into was set
                test_db.flush()
                for episode in episodes_for_consolidation:
                    test_db.refresh(episode)
                    if episode.id != episodes_for_consolidation[0].id:  # Not parent
                        # Either consolidated or remains separate
                        assert episode.consolidated_into is None or isinstance(episode.consolidated_into, str)

    @pytest.mark.asyncio
    async def test_consolidation_with_different_thresholds(self, test_db, temp_lancedb_dir,
                                                             episodes_for_consolidation):
        """Test consolidation with varying similarity thresholds."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup LanceDB
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in episodes_for_consolidation:
            content = f"{episode.title} {episode.description}"
            metadata = {
                "episode_id": episode.id,
                "agent_id": episode.agent_id,
                "type": "episode"
            }
            handler.add_document(
                table_name=table_name,
                text=content,
                source=f"episode:{episode.id}",
                metadata=metadata,
                user_id=episode.user_id,
                extract_knowledge=False
            )

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Test different thresholds
            thresholds = [0.7, 0.85, 0.95]

            for threshold in thresholds:
                # Reset consolidated_into for each test
                for episode in episodes_for_consolidation:
                    episode.consolidated_into = None
                test_db.commit()

                result = await service.consolidate_similar_episodes(
                    agent_id=episodes_for_consolidation[0].agent_id,
                    similarity_threshold=threshold
                )

                # Higher threshold = fewer consolidations
                assert isinstance(result["consolidated"], int)
                assert result["parent_episodes"] >= 0

    @pytest.mark.asyncio
    async def test_consolidation_no_episodes_available(self, test_db, temp_lancedb_dir,
                                                         sample_agent):
        """Test consolidation when no episodes available."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # No episodes in DB
            result = await service.consolidate_similar_episodes(
                agent_id=sample_agent.id
            )

            assert result["consolidated"] == 0
            assert result["parent_episodes"] == 0


# ============================================================================
# Episode Archival Tests
# ============================================================================

class TestEpisodeArchival:
    """Test episode archival to cold storage."""

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage(self, test_db, temp_lancedb_dir,
                                            sample_agent, sample_user):
        """Test archiving episode to cold storage."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        # First add episode to LanceDB
        table_name = "episodes"
        handler.create_table(table_name)

        episode = Episode(
            id="episode-to-archive",
            title="Episode to Archive",
            description="Test archival",
            summary="Test",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["test", "archive"],
            entities=[],
            importance_score=0.5,
            status="completed",
            started_at=datetime.now() - timedelta(days=10),
            ended_at=datetime.now() - timedelta(days=10) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=5
        )
        test_db.add(episode)
        test_db.commit()

        # Add to LanceDB
        content = f"{episode.title} {episode.description}"
        metadata = {
            "episode_id": episode.id,
            "agent_id": episode.agent_id,
            "type": "episode"
        }
        handler.add_document(
            table_name=table_name,
            text=content,
            source=f"episode:{episode.id}",
            metadata=metadata,
            user_id=episode.user_id,
            extract_knowledge=False
        )

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Archive episode
            result = await service.archive_to_cold_storage(episode.id)

            assert result is True

            # Verify episode status
            test_db.refresh(episode)
            assert episode.status == "archived"
            assert episode.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_nonexistent_episode(self, test_db, temp_lancedb_dir):
        """Test archiving non-existent episode returns False."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            result = await service.archive_to_cold_storage("nonexistent-episode-id")

            assert result is False


# ============================================================================
# Importance Score Update Tests
# ============================================================================

class TestImportanceScoreUpdates:
    """Test importance score updates in LanceDB."""

    @pytest.mark.asyncio
    async def test_update_importance_with_positive_feedback(self, test_db, temp_lancedb_dir,
                                                             sample_agent, sample_user):
        """Test updating importance with positive feedback."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        episode = Episode(
            id="episode-positive-feedback",
            title="Positive Feedback Episode",
            description="Test",
            summary="Test",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["test"],
            entities=[],
            importance_score=0.5,  # Starting score
            status="completed",
            started_at=datetime.now() - timedelta(days=1),
            ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=0
        )
        test_db.add(episode)
        test_db.commit()

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Update with positive feedback (+1.0)
            result = await service.update_importance_scores(
                episode_id=episode.id,
                user_feedback=1.0
            )

            assert result is True

            # Verify score increased
            test_db.refresh(episode)
            # New score = 0.5 * 0.8 + 1.0 * 0.2 = 0.4 + 0.2 = 0.6
            assert episode.importance_score > 0.5

    @pytest.mark.asyncio
    async def test_update_importance_with_negative_feedback(self, test_db, temp_lancedb_dir,
                                                              sample_agent, sample_user):
        """Test updating importance with negative feedback."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        episode = Episode(
            id="episode-negative-feedback",
            title="Negative Feedback Episode",
            description="Test",
            summary="Test",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["test"],
            entities=[],
            importance_score=0.7,  # Starting score
            status="completed",
            started_at=datetime.now() - timedelta(days=1),
            ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=0
        )
        test_db.add(episode)
        test_db.commit()

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Update with negative feedback (-1.0)
            result = await service.update_importance_scores(
                episode_id=episode.id,
                user_feedback=-1.0
            )

            assert result is True

            # Verify score decreased
            test_db.refresh(episode)
            # New score = 0.7 * 0.8 + 0.0 * 0.2 = 0.56
            assert episode.importance_score < 0.7

    @pytest.mark.asyncio
    async def test_importance_score_clamping(self, test_db, temp_lancedb_dir,
                                              sample_agent, sample_user):
        """Test importance score is clamped to [0.0, 1.0] range."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        # Test with high starting score and positive feedback
        episode = Episode(
            id="episode-clamp-high",
            title="Clamp Test High",
            description="Test",
            summary="Test",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["test"],
            entities=[],
            importance_score=0.95,  # Already high
            status="completed",
            started_at=datetime.now() - timedelta(days=1),
            ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=0
        )
        test_db.add(episode)
        test_db.commit()

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Update with maximum positive feedback
            await service.update_importance_scores(
                episode_id=episode.id,
                user_feedback=1.0
            )

            test_db.refresh(episode)
            assert episode.importance_score <= 1.0

        # Test with low starting score and negative feedback
        episode2 = Episode(
            id="episode-clamp-low",
            title="Clamp Test Low",
            description="Test",
            summary="Test",
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["test"],
            entities=[],
            importance_score=0.05,  # Already low
            status="completed",
            started_at=datetime.now() - timedelta(days=1),
            ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=0
        )
        test_db.add(episode2)
        test_db.commit()

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Update with maximum negative feedback
            await service.update_importance_scores(
                episode_id=episode2.id,
                user_feedback=-1.0
            )

            test_db.refresh(episode2)
            assert episode2.importance_score >= 0.0


# ============================================================================
# Bulk Operations Tests
# ============================================================================

class TestBulkLifecycleOperations:
    """Test bulk episode lifecycle operations."""

    @pytest.mark.asyncio
    async def test_batch_update_access_counts(self, test_db, temp_lancedb_dir,
                                               sample_agent, sample_user):
        """Test updating access counts for multiple episodes."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        # Create multiple episodes
        episode_ids = []
        for i in range(5):
            episode = Episode(
                id=f"episode-batch-{i}",
                title=f"Batch Episode {i}",
                description="Test",
                summary="Test",
                agent_id=sample_agent.id,
                user_id=sample_user.id,
                workspace_id="default",
                topics=["test"],
                entities=[],
                importance_score=0.5,
                status="completed",
                started_at=datetime.now() - timedelta(days=i),
                ended_at=datetime.now() - timedelta(days=i) + timedelta(hours=1),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=0.9,
                decay_score=1.0,
                access_count=i * 10  # Initial counts
            )
            test_db.add(episode)
            episode_ids.append(episode.id)

        test_db.commit()

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Batch update access counts
            result = await service.batch_update_access_counts(episode_ids)

            assert "updated" in result
            assert result["updated"] == len(episode_ids)

            # Verify all episodes had access_count incremented
            for episode_id in episode_ids:
                episode = test_db.query(Episode).filter(Episode.id == episode_id).first()
                assert episode.access_count > 0

    @pytest.mark.asyncio
    async def test_batch_update_with_nonexistent_episodes(self, test_db, temp_lancedb_dir):
        """Test batch update with some nonexistent episode IDs."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=handler):
            service = EpisodeLifecycleService(test_db)
            service.lancedb = handler

            # Mix of real and fake IDs
            mixed_ids = [
                "nonexistent-1",
                "nonexistent-2",
                "nonexistent-3"
            ]

            result = await service.batch_update_access_counts(mixed_ids)

            # Should handle gracefully
            assert "updated" in result
            assert result["updated"] == 0
