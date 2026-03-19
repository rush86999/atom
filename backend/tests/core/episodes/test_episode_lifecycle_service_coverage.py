"""
Coverage-driven tests for EpisodeLifecycleService (currently 0% -> target 70%+)

Target file: core/episode_lifecycle_service.py (422 lines, 351 statements)

Focus areas from coverage gap analysis:
- Service initialization (lines 1-50)
- Decay operations (lines 50-120)
- Consolidation methods (lines 120-240)
- Archival process (lines 240-351)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import Episode, EpisodeSegment


class TestEpisodeLifecycleServiceCoverage:
    """Coverage-driven tests for episode_lifecycle_service.py"""

    def _create_episode(self, **kwargs):
        """Helper to create Episode with required fields"""
        defaults = {
            "agent_id": "test-agent",
            "tenant_id": "test-tenant",
            "maturity_at_time": "autonomous",
            "outcome": "success"
        }
        defaults.update(kwargs)
        return Episode(**defaults)

    def test_service_initialization(self, db_session):
        """Cover lines 25-27: Service initialization"""
        service = EpisodeLifecycleService(db_session)
        assert service.db is db_session
        assert service.lancedb is not None

    @pytest.mark.asyncio
    async def test_decay_old_episodes_basic(self, db_session):
        """Cover decay operation basic flow (lines 29-69)"""
        # Create test episode older than threshold
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        ep = self._create_episode(
            id="ep-old",
            agent_id="agent-1",
            tenant_id="tenant-1",
            task_description="Old task",
            started_at=old_date,
            status="completed",
            decay_score=1.0,
            access_count=5
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = await service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 1
        assert result["archived"] == 0  # Not old enough for auto-archive

        db_session.refresh(ep)
        # Decay score should be reduced (100 days old -> 1 - 100/180 = 0.444)
        assert ep.decay_score < 1.0
        assert ep.access_count == 6  # Incremented

    @pytest.mark.asyncio
    async def test_decay_old_episodes_auto_archive(self, db_session):
        """Cover auto-archive logic (lines 60-64)"""
        # Create very old episode (>180 days)
        very_old_date = datetime.now(timezone.utc) - timedelta(days=200)
        ep = self._create_episode(
            id="ep-very-old",
            task_description="Very old task",
            started_at=very_old_date,
            status="completed",
            decay_score=0.5,
            access_count=10
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = await service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 1
        assert result["archived"] == 1  # Should be auto-archived

        db_session.refresh(ep)
        assert ep.status == "archived"
        assert ep.archived_at is not None

    @pytest.mark.asyncio
    async def test_decay_old_episodes_skip_archived(self, db_session):
        """Cover skip already archived episodes (line 46)"""
        # Create already archived episode
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        ep = self._create_episode(
            id="ep-archived",
            task_description="Archived task",
            started_at=old_date,
            status="archived",
            decay_score=0.5
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = await service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 0  # Should skip archived
        assert result["archived"] == 0

    @pytest.mark.asyncio
    async def test_decay_old_episodes_no_episodes(self, db_session):
        """Cover empty result set (lines 44-47)"""
        service = EpisodeLifecycleService(db_session)
        result = await service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 0
        assert result["archived"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_basic(self, db_session):
        """Cover consolidation basic flow (lines 71-163)"""
        # Create completed episodes for same agent
        ep1 = self._create_episode(
            id="ep-consol-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
            task_description="Task about data analysis",
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(days=5)
        )
        ep2 = self._create_episode(
            id="ep-consol-2",
            agent_id="agent-1",
            tenant_id="tenant-1",
            task_description="Task about analytics work",
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(days=4)
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search to return similar episode
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "_distance": 0.1,  # 90% similar (1.0 - 0.1)
                "metadata": '{"episode_id": "ep-consol-2"}'
            }
        ]
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        # Should consolidate ep2 into ep1
        assert result["consolidated"] == 1
        assert result["parent_episodes"] == 1

        db_session.refresh(ep2)
        assert ep2.consolidated_into == "ep-consol-1"

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_no_episodes(self, db_session):
        """Cover empty episodes list (lines 96-97)"""
        service = EpisodeLifecycleService(db_session)

        result = await service.consolidate_similar_episodes(
            agent_id="nonexistent-agent",
            similarity_threshold=0.85
        )

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_skip_already_consolidated(self, db_session):
        """Cover skip already consolidated episodes (line 106-107, 142)"""
        # Create episodes where one is already consolidated
        ep1 = self._create_episode(
            id="ep-parent",
            agent_id="agent-2",
            tenant_id="tenant-1",
            task_description="Parent episode",
            status="completed"
        )
        ep2 = self._create_episode(
            id="ep-child",
            agent_id="agent-2",
            tenant_id="tenant-1",
            task_description="Child episode",
            status="completed",
            consolidated_into="some-other-parent"  # Already consolidated
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "_distance": 0.05,
                "metadata": '{"episode_id": "ep-child"}'
            }
        ]
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes(
            agent_id="agent-2",
            similarity_threshold=0.85
        )

        # Should not consolidate already consolidated episode
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_lancedb_error(self, db_session):
        """Cover LanceDB error handling (lines 159-162)"""
        ep = self._create_episode(
            id="ep-error",
            agent_id="agent-3",
            tenant_id="tenant-1",
            task_description="Error test",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB to raise error
        mock_lancedb = Mock()
        mock_lancedb.search.side_effect = Exception("LanceDB connection failed")
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes(
            agent_id="agent-3",
            similarity_threshold=0.85
        )

        # Should return zeros on error
        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_success(self, db_session):
        """Cover successful archival (lines 165-191)"""
        ep = self._create_episode(
            id="ep-archive-1",
            task_description="Archive me",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = await service.archive_to_cold_storage("ep-archive-1")

        assert result is True

        db_session.refresh(ep)
        assert ep.status == "archived"
        assert ep.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_not_found(self, db_session):
        """Cover episode not found (lines 178-183)"""
        service = EpisodeLifecycleService(db_session)
        result = await service.archive_to_cold_storage("nonexistent-ep")

        assert result is False

    def test_archive_episode_success(self, db_session):
        """Cover synchronous archive (lines 193-217)"""
        ep = self._create_episode(
            id="ep-sync-archive",
            task_description="Sync archive",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = service.archive_episode(ep)

        assert result is True

        db_session.refresh(ep)
        assert ep.status == "archived"
        assert ep.archived_at is not None

    def test_archive_episode_error_handling(self, db_session):
        """Cover archive error handling (lines 214-217)"""
        ep = self._create_episode(
            id="ep-archive-error",
            task_description="Archive error",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock db.commit to raise error
        with patch.object(service.db, 'commit', side_effect=Exception("DB error")):
            result = service.archive_episode(ep)

            assert result is False

    @pytest.mark.asyncio
    async def test_update_importance_scores_success(self, db_session):
        """Cover importance update (lines 219-248)"""
        ep = self._create_episode(
            id="ep-importance",
            task_description="Importance test",
            status="completed",
            importance_score=0.5
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = await service.update_importance_scores("ep-importance", 0.5)

        assert result is True

        db_session.refresh(ep)
        # New importance = 0.5 * 0.8 + (0.5 + 1.0) / 2.0 * 0.2 = 0.4 + 0.15 = 0.55
        assert ep.importance_score > 0.5

    @pytest.mark.asyncio
    async def test_update_importance_scores_not_found(self, db_session):
        """Cover episode not found (lines 234-239)"""
        service = EpisodeLifecycleService(db_session)
        result = await service.update_importance_scores("nonexistent-ep", 0.5)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_importance_scores_clamping(self, db_session):
        """Cover importance score clamping (line 243)"""
        # Test positive feedback (should clamp to 1.0)
        ep1 = self._create_episode(
            id="ep-pos",
            task_description="Positive feedback",
            status="completed",
            importance_score=0.9
        )
        # Test negative feedback (should clamp to 0.0)
        ep2 = self._create_episode(
            id="ep-neg",
            task_description="Negative feedback",
            status="completed",
            importance_score=0.1
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Maximum positive feedback
        await service.update_importance_scores("ep-pos", 1.0)
        db_session.refresh(ep1)
        assert ep1.importance_score <= 1.0

        # Maximum negative feedback
        await service.update_importance_scores("ep-neg", -1.0)
        db_session.refresh(ep2)
        assert ep2.importance_score >= 0.0

    @pytest.mark.asyncio
    async def test_batch_update_access_counts(self, db_session):
        """Cover batch access count update (lines 250-277)"""
        ep1 = self._create_episode(id="ep-access-1", task_description="Access 1", access_count=5)
        ep2 = self._create_episode(id="ep-access-2", task_description="Access 2", access_count=10)
        db_session.add_all([ep1, ep2])
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = await service.batch_update_access_counts(["ep-access-1", "ep-access-2", "nonexistent"])

        assert result["updated"] == 2

        db_session.refresh(ep1)
        db_session.refresh(ep2)
        assert ep1.access_count == 6
        assert ep2.access_count == 11

    def test_update_lifecycle_success(self, db_session):
        """Cover lifecycle update success (lines 279-330)"""
        old_date = datetime.now(timezone.utc) - timedelta(days=45)
        ep = self._create_episode(
            id="ep-lifecycle",
            task_description="Lifecycle test",
            started_at=old_date,
            decay_score=1.0
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = service.update_lifecycle(ep)

        assert result is True

        db_session.refresh(ep)
        # 45 days old -> decay = 45/90 = 0.5
        assert ep.decay_score == pytest.approx(0.5, rel=0.01)

    def test_update_lifecycle_no_started_at(self, db_session):
        """Cover missing started_at (lines 293-295)"""
        # Create an episode object without adding to DB (to avoid server_default)
        ep = Episode(
            id="ep-no-start",
            agent_id="test-agent",
            tenant_id="test-tenant",
            maturity_at_time="autonomous",
            outcome="success",
            task_description="No start time",
            started_at=None
        )

        service = EpisodeLifecycleService(db_session)
        result = service.update_lifecycle(ep)

        # Should return False and log warning when started_at is None
        assert result is False

    def test_update_lifecycle_auto_archive_old(self, db_session):
        """Cover auto-archive in lifecycle (lines 318-320)"""
        very_old_date = datetime.now(timezone.utc) - timedelta(days=200)
        ep = self._create_episode(
            id="ep-auto-arch",
            task_description="Auto archive",
            started_at=very_old_date,
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        service.update_lifecycle(ep)

        db_session.refresh(ep)
        assert ep.status == "archived"
        assert ep.archived_at is not None

    def test_update_lifecycle_error_handling(self, db_session):
        """Cover lifecycle error handling (lines 327-330)"""
        ep = self._create_episode(
            id="ep-lifecycle-error",
            task_description="Lifecycle error",
            started_at=datetime.now(timezone.utc)
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock db.commit to raise error
        with patch.object(service.db, 'commit', side_effect=Exception("DB error")):
            result = service.update_lifecycle(ep)

            assert result is False

    def test_apply_decay_single_episode(self, db_session):
        """Cover apply_decay single episode (lines 332-353)"""
        old_date = datetime.now(timezone.utc) - timedelta(days=30)
        ep = self._create_episode(
            id="ep-decay-single",
            task_description="Decay single",
            started_at=old_date,
            decay_score=1.0
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = service.apply_decay(ep)

        assert result is True

        db_session.refresh(ep)
        # 30 days old -> decay = 30/90 = 0.333
        assert ep.decay_score == pytest.approx(0.333, rel=0.01)

    def test_apply_decay_list_of_episodes(self, db_session):
        """Cover apply_decay list of episodes (lines 344-350)"""
        old_date1 = datetime.now(timezone.utc) - timedelta(days=20)
        old_date2 = datetime.now(timezone.utc) - timedelta(days=40)
        ep1 = self._create_episode(id="ep-decay-1", task_description="Decay 1", started_at=old_date1, decay_score=1.0)
        ep2 = self._create_episode(id="ep-decay-2", task_description="Decay 2", started_at=old_date2, decay_score=1.0)
        db_session.add_all([ep1, ep2])
        db_session.commit()

        service = EpisodeLifecycleService(db_session)
        result = service.apply_decay([ep1, ep2])

        assert result is True

        db_session.refresh(ep1)
        db_session.refresh(ep2)
        # 20 days -> 0.222, 40 days -> 0.444
        assert ep1.decay_score == pytest.approx(0.222, rel=0.01)
        assert ep2.decay_score == pytest.approx(0.444, rel=0.01)

    def test_consolidate_episodes_with_agent_object(self, db_session):
        """Cover consolidate_episodes with Agent object (lines 368-372)"""
        # Create mock agent object
        mock_agent = Mock()
        mock_agent.id = "agent-consol-obj"

        ep = self._create_episode(
            id="ep-consol-obj",
            agent_id="agent-consol-obj",
            task_description="Consolidate object test",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search to return empty
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = []
        service.lancedb = mock_lancedb

        # Patch asyncio at module level
        with patch('asyncio.run') as mock_run:
            mock_run.return_value = {"consolidated": 0, "parent_episodes": 0}

            result = service.consolidate_episodes(mock_agent)

            assert result["consolidated"] == 0

    def test_consolidate_episodes_with_agent_id_string(self, db_session):
        """Cover consolidate_episodes with agent_id string (line 372)"""
        service = EpisodeLifecycleService(db_session)

        # Patch asyncio at module level
        with patch('asyncio.run') as mock_run:
            mock_run.return_value = {"consolidated": 0, "parent_episodes": 0}

            result = service.consolidate_episodes("agent-string-id")

            assert result["consolidated"] == 0

    def test_consolidate_episodes_error_handling(self, db_session):
        """Cover consolidate_episodes error handling (lines 419-421)"""
        service = EpisodeLifecycleService(db_session)

        # Patch asyncio at module level
        with patch('asyncio.run', side_effect=Exception("Consolidation failed")):
            result = service.consolidate_episodes("agent-error")

            # Should return zeros on error
            assert result["consolidated"] == 0
            assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_metadata_parsing(self, db_session):
        """Cover metadata JSON parsing (lines 124-126)"""
        ep = self._create_episode(
            id="ep-metadata",
            agent_id="agent-metadata",
            tenant_id="tenant-1",
            task_description="Metadata parsing test",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search with string metadata (requires JSON parsing)
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "_distance": 0.2,  # 80% similar (below threshold)
                "metadata": '{"episode_id": "other-ep"}'  # String metadata
            }
        ]
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes(
            agent_id="agent-metadata",
            similarity_threshold=0.85
        )

        # Should not consolidate (below threshold)
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_empty_task_description(self, db_session):
        """Cover empty task_description handling (line 110)"""
        ep = self._create_episode(
            id="ep-empty-desc",
            agent_id="agent-empty",
            tenant_id="tenant-1",
            task_description=None,  # Empty description
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search with empty query
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = []
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes(
            agent_id="agent-empty",
            similarity_threshold=0.85
        )

        # Should handle empty description gracefully
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_no_metadata(self, db_session):
        """Cover missing metadata handling (lines 123-127)"""
        ep = self._create_episode(
            id="ep-no-meta",
            agent_id="agent-no-meta",
            tenant_id="tenant-1",
            task_description="No metadata test",
            status="completed"
        )
        db_session.add(ep)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search with no metadata
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "_distance": 0.1,
                "metadata": None  # No metadata
            }
        ]
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes(
            agent_id="agent-no-meta",
            similarity_threshold=0.85
        )

        # Should skip episode with no metadata
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_mixed_similarity(self, db_session):
        """Cover similarity threshold filtering (lines 129-135)"""
        ep1 = self._create_episode(
            id="ep-parent-mixed",
            agent_id="agent-mixed",
            tenant_id="tenant-1",
            task_description="Parent for mixed test",
            status="completed"
        )
        db_session.add(ep1)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Mock LanceDB search with mixed similarity results
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "_distance": 0.05,  # 95% similar (above threshold)
                "metadata": '{"episode_id": "ep-similar-1"}'
            },
            {
                "_distance": 0.2,   # 80% similar (below threshold)
                "metadata": '{"episode_id": "ep-not-similar"}'
            },
            {
                "_distance": 0.1,   # 90% similar (above threshold)
                "metadata": '{"episode_id": "ep-similar-2"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Create similar episodes
        ep_similar_1 = self._create_episode(id="ep-similar-1", agent_id="agent-mixed", tenant_id="tenant-1", task_description="Similar 1", status="completed")
        ep_not_similar = self._create_episode(id="ep-not-similar", agent_id="agent-mixed", tenant_id="tenant-1", task_description="Not similar", status="completed")
        ep_similar_2 = self._create_episode(id="ep-similar-2", agent_id="agent-mixed", tenant_id="tenant-1", task_description="Similar 2", status="completed")
        db_session.add_all([ep_similar_1, ep_not_similar, ep_similar_2])
        db_session.commit()

        result = await service.consolidate_similar_episodes(
            agent_id="agent-mixed",
            similarity_threshold=0.85
        )

        # Should consolidate episodes above threshold
        # Note: The parent episode (ep-parent-mixed) also gets processed as a potential parent
        # and can consolidate other episodes into it
        assert result["consolidated"] >= 2  # At least the 2 above threshold
        assert result["parent_episodes"] >= 1  # At least 1 parent episode
