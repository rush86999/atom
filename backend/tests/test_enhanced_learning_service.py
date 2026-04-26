"""
Test suite for Enhanced Learning Service - Unified learning platform.

Tests cover:
- RLHF (Reinforcement Learning from Human Feedback)
- Experience recording and processing
- Knowledge graph with clustering
- Learning analytics dashboard
- Parameter tuning based on feedback
- Pattern identification and reflections
- Model updates from experiences
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import numpy as np


# Import target module
from core.enhanced_learning_service import (
    EnhancedLearningService,
    LearningAnalytics
)
from core.models import AgentFeedback, AgentLearning, CognitiveExperience, AgentRegistry


class TestEnhancedLearningServiceInit:
    """Test EnhancedLearningService initialization."""

    def test_initialization_with_db(self):
        """Service initializes with database session."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)
            assert service.db is mock_db
            assert service._running is True

    def test_initialization_with_services(self):
        """Service initializes with LLM and embedding services."""
        mock_db = Mock(spec=Session)
        mock_llm = MagicMock()
        mock_embedding = MagicMock()

        with patch('core.enhanced_learning_service.LLMService', return_value=mock_llm), \
             patch('core.enhanced_learning_service.EmbeddingService', return_value=mock_embedding):
            service = EnhancedLearningService(mock_db, mock_llm, mock_embedding)
            assert service.llm_service is mock_llm
            assert service.embedding_service is mock_embedding

    def test_initialization_creates_caches(self):
        """Service initializes in-memory caches."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)
            assert hasattr(service, 'models_cache')
            assert hasattr(service, 'experiences_cache')
            assert hasattr(service, 'strategies_cache')
            assert hasattr(service, 'knowledge_graphs')


class TestRLHFRecording:
    """Test RLHF feedback recording."""

    def test_record_feedback_success(self):
        """Service records user feedback successfully."""
        mock_db = Mock(spec=Session)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback_id = service.record_feedback(
                agent_id="agent-123",
                execution_id="exec-001",
                user_id="user-123",
                feedback_type="positive",
                rating=5,
                comments="Great job!"
            )

            assert feedback_id is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_record_feedback_negative(self):
        """Service records negative feedback."""
        mock_db = Mock(spec=Session)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback_id = service.record_feedback(
                agent_id="agent-123",
                execution_id="exec-001",
                user_id="user-123",
                feedback_type="negative",
                rating=1,
                comments="Incorrect output"
            )

            assert feedback_id is not None

    def test_record_feedback_with_correction(self):
        """Service records feedback with user correction."""
        mock_db = Mock(spec=Session)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback_id = service.record_feedback(
                agent_id="agent-123",
                execution_id="exec-001",
                user_id="user-123",
                feedback_type="correction",
                corrected_output="The correct answer is 42"
            )

            assert feedback_id is not None

    def test_record_feedback_error_handling(self):
        """Service handles feedback recording errors gracefully."""
        mock_db = Mock(spec=Session)
        mock_db.add = MagicMock(side_effect=Exception("Database error"))
        mock_db.rollback = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback_id = service.record_feedback(
                agent_id="agent-123",
                execution_id="exec-001",
                user_id="user-123",
                feedback_type="positive"
            )

            assert feedback_id is None
            mock_db.rollback.assert_called_once()


class TestParameterTuning:
    """Test RLHF parameter tuning based on feedback."""

    def test_adjust_parameters_negative_feedback(self):
        """Service reduces temperature after negative feedback."""
        mock_db = Mock(spec=Session)

        # Mock existing learning record
        mock_learning = AgentLearning(
            agent_id="agent-123",
            parameters_json={"temperature": 0.7, "top_p": 0.9}
        )

        mock_db.query.return_value.filter.return_value.first.return_value = mock_learning
        mock_db.commit = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback = AgentFeedback(
                agent_id="agent-123",
                feedback_type="negative",
                rating=2
            )

            new_params = service._adjust_parameters(mock_learning, feedback)

            # Temperature should decrease
            assert new_params["temperature"] < 0.7
            assert new_params["temperature"] >= 0.3  # Minimum threshold

    def test_adjust_parameters_positive_feedback(self):
        """Service increases temperature slightly after positive feedback."""
        mock_db = Mock(spec=Session)

        mock_learning = AgentLearning(
            agent_id="agent-123",
            parameters_json={"temperature": 0.7, "top_p": 0.9}
        )

        mock_db.query.return_value.filter.return_value.first.return_value = mock_learning
        mock_db.commit = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback = AgentFeedback(
                agent_id="agent-123",
                feedback_type="positive",
                rating=5
            )

            new_params = service._adjust_parameters(mock_learning, feedback)

            # Temperature should increase slightly
            assert new_params["temperature"] > 0.7
            assert new_params["temperature"] <= 0.9  # Maximum threshold

    def test_adjust_parameters_top_p(self):
        """Service adjusts top_p based on rating."""
        mock_db = Mock(spec=Session)

        mock_learning = AgentLearning(
            agent_id="agent-123",
            parameters_json={"top_p": 0.9}
        )

        mock_db.query.return_value.filter.return_value.first.return_value = mock_learning
        mock_db.commit = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            # High rating -> increase top_p
            feedback_high = AgentFeedback(
                agent_id="agent-123",
                feedback_type="positive",
                rating=5
            )

            new_params = service._adjust_parameters(mock_learning, feedback_high)
            assert new_params["top_p"] > 0.9

            # Low rating -> decrease top_p
            feedback_low = AgentFeedback(
                agent_id="agent-123",
                feedback_type="negative",
                rating=2
            )

            mock_learning.parameters_json = {"top_p": 0.9}
            new_params = service._adjust_parameters(mock_learning, feedback_low)
            assert new_params["top_p"] < 0.9


class TestExperienceRecording:
    """Test experience recording and processing."""

    @pytest.mark.asyncio
    async def test_record_experience_success(self):
        """Service records experience successfully."""
        mock_db = Mock(spec=Session)

        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService', return_value=mock_embedding_service):
            service = EnhancedLearningService(mock_db, embedding_service=mock_embedding_service)

            # Mock _persist_experience and _process_experience
            service._persist_experience = AsyncMock()
            service._process_experience = AsyncMock()

            experience_id = await service.record_experience(
                agent_id="agent-123",
                experience_type="task_execution",
                task_description="Process data",
                inputs={"query": "test"},
                actions=[{"type": "query"}],
                outcomes={"primary": 0.9}
            )

            assert experience_id is not None
            assert experience_id.startswith("exp_")

    @pytest.mark.asyncio
    async def test_record_experience_generates_embedding(self):
        """Service generates embedding for experience."""
        mock_db = Mock(spec=Session)

        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService', return_value=mock_embedding_service):
            service = EnhancedLearningService(mock_db, embedding_service=mock_embedding_service)

            service._persist_experience = AsyncMock()
            service._process_experience = AsyncMock()

            await service.record_experience(
                agent_id="agent-123",
                experience_type="task_execution",
                task_description="Test task",
                inputs={},
                actions=[],
                outcomes={}
            )

            # Verify embedding was generated
            mock_embedding_service.generate_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_experience_caches(self):
        """Service caches experience after recording."""
        mock_db = Mock(spec=Session)

        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService', return_value=mock_embedding_service):
            service = EnhancedLearningService(mock_db, embedding_service=mock_embedding_service)

            service._persist_experience = AsyncMock()
            service._process_experience = AsyncMock()

            experience_id = await service.record_experience(
                agent_id="agent-123",
                experience_type="task_execution",
                task_description="Test",
                inputs={},
                actions=[],
                outcomes={}
            )

            # Verify experience was cached
            assert experience_id in service.experiences_cache


class TestKnowledgeGraph:
    """Test knowledge graph management."""

    @pytest.mark.asyncio
    async def test_get_knowledge_graph(self):
        """Service returns knowledge graph structure."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            # Initialize knowledge graph
            service.knowledge_graphs["default"] = {
                'nodes': {},
                'edges': {},
                'clusters': {},
                'metrics': {
                    'total_nodes': 0,
                    'total_edges': 0,
                    'density': 0,
                    'clustering_coefficient': 0,
                    'modularity': 0
                }
            }

            kg = await service.get_knowledge_graph()

            assert 'nodes' in kg
            assert 'edges' in kg
            assert 'clusters' in kg
            assert 'metrics' in kg

    @pytest.mark.asyncio
    async def test_update_knowledge_graph(self):
        """Service updates knowledge graph with experience."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            # Initialize knowledge graph
            service.knowledge_graphs["default"] = {
                'nodes': {},
                'edges': {},
                'clusters': {},
                'metrics': {
                    'total_nodes': 0,
                    'total_edges': 0,
                    'density': 0,
                    'clustering_coefficient': 0,
                    'modularity': 0
                }
            }

            experience = {
                'type': 'task_execution',
                'task_description': 'Test task',
                'vector': [0.1] * 100
            }

            await service._update_knowledge_graph(experience)

            # Verify node was added
            assert len(service.knowledge_graphs["default"]['nodes']) > 0


class TestPatternIdentification:
    """Test pattern identification in experiences."""

    @pytest.mark.asyncio
    async def test_identify_success_pattern(self):
        """Service identifies success patterns."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'outcomes': {'primary': 0.9}
            }

            patterns = await service._identify_patterns(experience)

            assert len(patterns) > 0
            assert patterns[0]['type'] == 'success'

    @pytest.mark.asyncio
    async def test_identify_failure_pattern(self):
        """Service identifies failure patterns."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'outcomes': {'primary': 0.2}
            }

            patterns = await service._identify_patterns(experience)

            assert len(patterns) > 0
            assert patterns[0]['type'] == 'failure'


class TestReflectionGeneration:
    """Test reflection generation from experiences."""

    @pytest.mark.asyncio
    async def test_generate_reflection_failure(self):
        """Service generates reflections from failures."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'type': 'failure',
                'outcomes': {'primary': 0.3}
            }

            reflections = await service._generate_reflections(experience)

            assert len(reflections) > 0
            assert 'insight' in reflections[0]


class TestLearningAnalytics:
    """Test learning analytics dashboard."""

    @pytest.mark.asyncio
    async def test_get_learning_analytics(self):
        """Service generates learning analytics."""
        mock_db = Mock(spec=Session)

        # Mock database queries
        mock_experiences = [
            Mock(experience_type='task', effectiveness_score=0.8, created_at=datetime.now(timezone.utc)),
            Mock(experience_type='task', effectiveness_score=0.9, created_at=datetime.now(timezone.utc))
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_experiences

        # Mock feedback query
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [],  # Experiences
            [Mock(feedback_type='positive', rating=5)],  # Feedback
            [Mock(id='agent-1', name='Agent 1')]  # Agents
        ]

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            analytics = await service.get_learning_analytics(days=30)

            assert isinstance(analytics, LearningAnalytics)
            assert analytics.total_experiences == 2
            assert analytics.avg_outcome_score > 0

    @pytest.mark.asyncio
    async def test_learning_analytics_includes_feedback(self):
        """Analytics includes feedback metrics."""
        mock_db = Mock(spec=Session)

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [],  # Experiences
            [
                Mock(feedback_type='positive', rating=5),
                Mock(feedback_type='negative', rating=2)
            ],  # Feedback
            []  # Agents
        ]

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            analytics = await service.get_learning_analytics(days=30)

            assert analytics.total_feedback == 2
            assert analytics.positive_feedback_ratio == 0.5


class TestModularityCalculation:
    """Test graph modularity calculation."""

    def test_calculate_modularity_no_clusters(self):
        """Modularity is 0 when no clusters exist."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            kg = {
                'clusters': {},
                'metrics': {'total_nodes': 0}
            }

            modularity = service._calculate_modularity(kg)
            assert modularity == 0.0

    def test_calculate_modularity_with_clusters(self):
        """Modularity is calculated for existing clusters."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            kg = {
                'clusters': {
                    'cluster_1': {'size': 10},
                    'cluster_2': {'size': 10}
                },
                'metrics': {'total_nodes': 20}
            }

            modularity = service._calculate_modularity(kg)
            # Balanced clusters should have high modularity
            assert 0.0 < modularity <= 1.0


class TestSimilarityCalculation:
    """Test embedding similarity calculation."""

    def test_calculate_similarity_identical(self):
        """Identical embeddings have similarity of 1.0."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            embedding = [0.5, 0.5, 0.5]
            similarity = service._calculate_similarity(embedding, embedding)

            assert similarity == 1.0

    def test_calculate_similarity_different(self):
        """Different embeddings have similarity < 1.0."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            embedding1 = [1.0, 0.0, 0.0]
            embedding2 = [0.0, 1.0, 0.0]
            similarity = service._calculate_similarity(embedding1, embedding2)

            assert 0.0 <= similarity < 1.0

    def test_calculate_similarity_zero_vector(self):
        """Zero vectors have similarity of 0.0."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            embedding1 = [0.0, 0.0, 0.0]
            embedding2 = [1.0, 1.0, 1.0]
            similarity = service._calculate_similarity(embedding1, embedding2)

            assert similarity == 0.0


class TestExperiencePersistence:
    """Test experience persistence to database."""

    @pytest.mark.asyncio
    async def test_persist_experience(self):
        """Service persists experience to database."""
        mock_db = Mock(spec=Session)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'id': 'exp-123',
                'agent_id': 'agent-123',
                'type': 'task_execution',
                'task_description': 'Test task',
                'inputs': {},
                'actions': [],
                'outcomes': {},
                'patterns': [],
                'reflections': [],
                'vector': [0.1] * 100
            }

            await service._persist_experience(experience)

            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_experience_error_handling(self):
        """Service handles persistence errors gracefully."""
        mock_db = Mock(spec=Session)
        mock_db.add = MagicMock(side_effect=Exception("Database error"))
        mock_db.rollback = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'id': 'exp-123',
                'agent_id': 'agent-123',
                'type': 'task_execution',
                'task_description': 'Test',
                'inputs': {},
                'actions': [],
                'outcomes': {},
                'patterns': [],
                'reflections': [],
                'vector': []
            }

            await service._persist_experience(experience)

            mock_db.rollback.assert_called_once()


class TestEmergentBehaviorDetection:
    """Test emergent behavior detection."""

    @pytest.mark.asyncio
    async def test_detect_emergent_behaviors(self):
        """Service detects emergent behaviors from patterns."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'patterns': [
                    {'confidence': 0.8, 'novelty': 0.7, 'name': 'New Pattern'}
                ]
            }

            # Should not raise exception
            await service._detect_emergent_behaviors(experience)


class TestModelUpdates:
    """Test model updates from experiences."""

    @pytest.mark.asyncio
    async def test_update_models_from_experience(self):
        """Service updates learning models from experience."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            experience = {
                'type': 'task_execution',
                'outcomes': {'primary': 0.8}
            }

            # Should not raise exception (simplified implementation)
            await service._update_models_from_experience(experience)


class TestShutdown:
    """Test service shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Service shuts down gracefully."""
        mock_db = Mock(spec=Session)

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            await service.shutdown()

            assert service._running is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_generate_experience_embedding_error(self):
        """Service handles embedding generation errors gracefully."""
        mock_db = Mock(spec=Session)

        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embedding.side_effect = Exception("Embedding failed")

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService', return_value=mock_embedding_service):
            service = EnhancedLearningService(mock_db, embedding_service=mock_embedding_service)

            # Use synchronous wrapper for testing
            import asyncio
            embedding = asyncio.run(service._generate_experience_embedding(
                task_description="Test",
                actions=[],
                outcomes={}
            ))

            # Should return default embedding
            assert embedding == [0.0] * 1536

    @pytest.mark.asyncio
    async def test_record_experience_empty_outcomes(self):
        """Service handles experiences with empty outcomes."""
        mock_db = Mock(spec=Session)

        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1536

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService', return_value=mock_embedding_service):
            service = EnhancedLearningService(mock_db, embedding_service=mock_embedding_service)

            service._persist_experience = AsyncMock()
            service._process_experience = AsyncMock()

            experience_id = await service.record_experience(
                agent_id="agent-123",
                experience_type="task_execution",
                task_description="Test",
                inputs={},
                actions=[],
                outcomes={}
            )

            assert experience_id is not None

    def test_feedback_update_without_existing_learning(self):
        """Service creates new learning record if none exists."""
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()

        with patch('core.enhanced_learning_service.LLMService'), \
             patch('core.enhanced_learning_service.EmbeddingService'):
            service = EnhancedLearningService(mock_db)

            feedback = AgentFeedback(
                agent_id="agent-123",
                feedback_type="positive",
                rating=5
            )

            service._update_from_feedback(feedback)

            # Should create new learning record
            mock_db.add.assert_called_once()
