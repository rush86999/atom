"""
Incremental tests for Episode Retrieval Service

Phase 207-09: Coverage Quality Push
Target: Improve coverage from 53% to 65% (already at 75%, adding edge case tests)

Focus: Test error paths and edge cases that don't require complex database setup
Missing lines: Governance errors, semantic search failures, canvas context errors
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
)
from core.models import AgentRegistry, AgentStatus


class TestTemporalRetrievalErrors:
    """Test error paths in temporal retrieval"""

    @pytest.mark.asyncio
    async def test_temporal_retrieval_governance_denied(self, db_session):
        """Test temporal retrieval when governance is denied"""
        agent = AgentRegistry(
            id="agent-gov-denied",
            name="Governance Denied Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity for memory access",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_temporal(
                agent_id="agent-gov-denied",
                time_range="7d"
            )

            assert result["episodes"] == []
            assert "error" in result
            assert result["governance_check"]["allowed"] is False


class TestSequentialRetrievalErrors:
    """Test error paths in sequential retrieval"""

    @pytest.mark.asyncio
    async def test_sequential_retrieval_episode_not_found(self, db_session):
        """Test sequential retrieval when episode doesn't exist"""
        service = EpisodeRetrievalService(db_session)

        result = await service.retrieve_sequential(
            episode_id="nonexistent-episode",
            agent_id="some-agent"
        )

        assert "error" in result
        assert "Episode not found" in result["error"]


class TestSemanticRetrievalErrors:
    """Test error paths in semantic retrieval"""

    @pytest.mark.asyncio
    async def test_semantic_retrieval_governance_denied(self, db_session):
        """Test semantic retrieval when governance is denied"""
        agent = AgentRegistry(
            id="agent-semantic-gov",
            name="Semantic Gov Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity for semantic search",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_semantic(
                agent_id="agent-semantic-gov",
                query="test query"
            )

            assert result["episodes"] == []
            assert "error" in result
            assert result["governance_check"]["allowed"] is False

    @pytest.mark.asyncio
    async def test_semantic_retrieval_lancedb_error(self, db_session):
        """Test semantic retrieval when LanceDB fails"""
        agent = AgentRegistry(
            id="agent-semantic-error",
            name="Semantic Error Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock LanceDB to raise error
        with patch.object(service.lancedb, 'search') as mock_search:
            mock_search.side_effect = Exception("LanceDB connection failed")

            result = await service.retrieve_semantic(
                agent_id="agent-semantic-error",
                query="test query"
            )

            assert result["episodes"] == []
            assert "error" in result


class TestContextualRetrievalErrors:
    """Test error paths in contextual retrieval"""

    @pytest.mark.asyncio
    async def test_contextual_retrieval_governance_denied(self, db_session):
        """Test contextual retrieval when governance denies temporal access"""
        agent = AgentRegistry(
            id="agent-contextual-gov",
            name="Contextual Gov Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_contextual(
                agent_id="agent-contextual-gov",
                current_task="test task"
            )

            # Should return empty episodes when governance denied
            assert "episodes" in result
            assert result["episodes"] == []


class TestCanvasAwareRetrievalErrors:
    """Test error paths in canvas-aware retrieval"""

    @pytest.mark.asyncio
    async def test_canvas_aware_governance_denied(self, db_session):
        """Test canvas-aware retrieval when governance is denied"""
        agent = AgentRegistry(
            id="agent-canvas-gov",
            name="Canvas Gov Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_canvas_aware(
                agent_id="agent-canvas-gov",
                query="test query"
            )

            assert result["episodes"] == []
            assert "error" in result

    @pytest.mark.asyncio
    async def test_canvas_aware_lancedb_error(self, db_session):
        """Test canvas-aware retrieval when LanceDB fails"""
        agent = AgentRegistry(
            id="agent-canvas-error",
            name="Canvas Error Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock LanceDB to raise error
        with patch.object(service.lancedb, 'search') as mock_search:
            mock_search.side_effect = Exception("Canvas search failed")

            result = await service.retrieve_canvas_aware(
                agent_id="agent-canvas-error",
                query="test query"
            )

            assert result["episodes"] == []
            assert "error" in result


class TestBusinessDataRetrievalErrors:
    """Test error paths in business data retrieval"""

    @pytest.mark.asyncio
    async def test_business_data_governance_denied(self, db_session):
        """Test business data retrieval when governance is denied"""
        agent = AgentRegistry(
            id="agent-business-gov",
            name="Business Gov Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_by_business_data(
                agent_id="agent-business-gov",
                business_filters={"status": "approved"}
            )

            assert result["episodes"] == []
            assert "error" in result



class TestCanvasTypeRetrievalErrors:
    """Test error paths in canvas type retrieval"""

    @pytest.mark.asyncio
    async def test_canvas_type_governance_denied(self, db_session):
        """Test canvas type retrieval when governance is denied"""
        agent = AgentRegistry(
            id="agent-canvas-type-gov",
            name="Canvas Type Gov Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_by_canvas_type(
                agent_id="agent-canvas-type-gov",
                canvas_type="sheets"
            )

            assert result["episodes"] == []
            assert "error" in result


class TestSupervisionContextErrors:
    """Test error paths in supervision context retrieval"""

    @pytest.mark.asyncio
    async def test_supervision_context_governance_denied(self, db_session):
        """Test supervision context retrieval when governance is denied"""
        agent = AgentRegistry(
            id="agent-supervision-gov",
            name="Supervision Gov Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT,
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)

        # Mock governance to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Insufficient maturity",
                "agent_maturity": "STUDENT"
            }

            result = await service.retrieve_with_supervision_context(
                agent_id="agent-supervision-gov",
                retrieval_mode=RetrievalMode.TEMPORAL
            )

            assert result["episodes"] == []
            assert "error" in result


class TestTrendCalculation:
    """Test trend calculation edge cases"""

    def test_filter_improvement_fewer_than_five_episodes(self):
        """Test improvement trend filter with fewer than 5 episodes"""
        service = EpisodeRetrievalService(Mock())

        episodes = []
        for i in range(3):
            episode = Mock()
            episode.started_at = datetime.now() - timedelta(days=i)
            episode.supervisor_rating = 4 + i
            episodes.append(episode)

        result = service._filter_improvement_trend(episodes)

        # Should return episodes as-is when < 5
        assert len(result) == 3

    def test_filter_improvement_no_ratings(self):
        """Test improvement trend filter when no ratings available"""
        service = EpisodeRetrievalService(Mock())

        episodes = []
        for i in range(10):
            episode = Mock()
            episode.started_at = datetime.now() - timedelta(days=i)
            episode.supervisor_rating = None
            episodes.append(episode)

        result = service._filter_improvement_trend(episodes)

        # Should return episodes when can't determine trend
        assert len(result) == 10
