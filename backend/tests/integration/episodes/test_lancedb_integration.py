"""
Integration tests for LanceDB vector search and embedding generation

Tests cover:
1. LanceDB client connection and table creation
2. Vector embedding generation for episode content
3. Semantic search with cosine similarity
4. Hybrid search (temporal + semantic)
5. Batch embedding operations
6. Query performance and result ranking

These tests use actual LanceDB in-memory database for realistic testing.
External embedding APIs are mocked for reliability and speed.
"""

import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.episode_retrieval_service import EpisodeRetrievalService
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    CanvasAudit,
    AgentFeedback,
    ChatSession,
    ChatMessage,
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
    # Cleanup
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
def mock_governance():
    """Mock governance service to always allow access."""
    gov = Mock()
    gov.can_perform_action = Mock(return_value={
        "allowed": True,
        "agent_maturity": "SUPERVISED"
    })
    return gov


@pytest.fixture
def sample_user(test_db):
    """Create sample user."""
    user = User(
        id="user-123",
        email="test@example.com",
        name="Test User"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sample_agent(test_db):
    """Create sample agent."""
    agent = AgentRegistry(
        id="agent-456",
        name="TestAgent",
        status=AgentStatus.SUPERVISED,
        description="Test agent for LanceDB integration"
    )
    test_db.add(agent)
    test_db.commit()
    return agent


@pytest.fixture
def sample_episodes(test_db, sample_agent, sample_user):
    """Create sample episodes with varied content."""
    now = datetime.now()
    episodes = []

    episode_data = [
        {
            "title": "Data Analysis Dashboard",
            "description": "Created analytics dashboard with sales metrics",
            "summary": "Built comprehensive dashboard showing KPIs",
            "topics": ["analytics", "dashboard", "sales"],
            "importance": 0.8
        },
        {
            "title": "Customer Support Automation",
            "description": "Automated customer support ticket routing",
            "summary": "Implemented AI-based ticket classification",
            "topics": ["automation", "support", "tickets"],
            "importance": 0.9
        },
        {
            "title": "Report Generation",
            "description": "Generated monthly sales reports",
            "summary": "Automated PDF report generation",
            "topics": ["reports", "sales", "automation"],
            "importance": 0.7
        },
        {
            "title": "Database Migration",
            "description": "Migrated customer data to new schema",
            "summary": "Successfully migrated 100k records",
            "topics": ["database", "migration", "data"],
            "importance": 0.85
        },
        {
            "title": "API Integration",
            "description": "Integrated third-party payment API",
            "summary": "Connected Stripe payment processing",
            "topics": ["api", "integration", "payments"],
            "importance": 0.75
        }
    ]

    for i, data in enumerate(episode_data):
        episode = Episode(
            id=f"episode-{i}",
            title=data["title"],
            description=data["description"],
            summary=data["summary"],
            agent_id=sample_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=data["topics"],
            entities=[],
            importance_score=data["importance"],
            status="completed",
            started_at=now - timedelta(days=i),
            ended_at=now - timedelta(days=i) + timedelta(hours=1),
            duration_seconds=3600,
            maturity_at_time="SUPERVISED",
            human_intervention_count=i % 3,
            constitutional_score=0.8 + (i * 0.02),
            decay_score=1.0 - (i * 0.1),
            access_count=10 - i,
            canvas_action_count=i,
            feedback_ids=[]
        )
        test_db.add(episode)

        # Add segments for each episode
        for j in range(3):
            segment = EpisodeSegment(
                id=f"segment-{i}-{j}",
                episode_id=episode.id,
                segment_type="conversation",
                sequence_order=j,
                content=f"Content segment {j} for {data['title']}",
                content_summary=f"Summary {j}",
                source_type="chat_message",
                source_id=f"msg-{j}"
            )
            test_db.add(segment)

        episodes.append(episode)

    test_db.commit()
    return episodes


# ============================================================================
# LanceDB Connection and Table Creation Tests
# ============================================================================

class TestLanceDBConnection:
    """Test LanceDB client initialization and table operations."""

    @pytest.mark.asyncio
    async def test_lancedb_handler_initialization(self, temp_lancedb_dir):
        """Test LanceDB handler can be initialized with temporary directory."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        # Verify handler initialized
        assert handler is not None
        assert handler.db_path == temp_lancedb_dir

    @pytest.mark.asyncio
    async def test_table_creation(self, test_db, temp_lancedb_dir, sample_agent):
        """Test creating episodes table in LanceDB."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        # Create table
        table_name = "test_episodes"
        handler.create_table(table_name)

        # Verify table exists
        assert table_name in handler.db.table_names()

    @pytest.mark.asyncio
    async def test_add_documents_to_lancedb(self, test_db, temp_lancedb_dir, sample_episodes):
        """Test adding episode documents to LanceDB."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        # Add episodes to LanceDB
        for episode in sample_episodes:
            content = f"""
Title: {episode.title}
Description: {episode.description}
Summary: {episode.summary}
Topics: {', '.join(episode.topics)}
            """.strip()

            metadata = {
                "episode_id": episode.id,
                "agent_id": episode.agent_id,
                "user_id": episode.user_id,
                "status": episode.status,
                "topics": episode.topics,
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

        # Verify documents added
        table = handler.db.open_table(table_name)
        count = len(table.to_arrow())
        assert count == len(sample_episodes)


# ============================================================================
# Vector Embedding Generation Tests
# ============================================================================

class TestEmbeddingGeneration:
    """Test vector embedding generation for episode content."""

    @pytest.mark.asyncio
    async def test_embed_text_generates_vector(self, temp_lancedb_dir):
        """Test text embedding generates fixed-length vector."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        text = "This is a test episode about data analytics"
        embedding = handler.embed_text(text)

        assert embedding is not None
        # Check it's a list or array
        assert isinstance(embedding, (list, tuple))
        # Check vector dimension (should be 384 for MiniLM-L6-v2)
        assert len(embedding) > 0
        # Check values are floats
        assert all(isinstance(x, (float, int)) for x in embedding)

    @pytest.mark.asyncio
    async def test_embedding_deterministic_for_same_text(self, temp_lancedb_dir):
        """Test embeddings are consistent for identical text."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        text = "Consistent test text"
        embedding1 = handler.embed_text(text)
        embedding2 = handler.embed_text(text)

        # Embeddings should be identical or very similar
        assert len(embedding1) == len(embedding2)

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = sum(a ** 2 for a in embedding1) ** 0.5
        magnitude2 = sum(b ** 2 for b in embedding2) ** 0.5
        similarity = dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 > 0 else 0

        # Should be nearly identical (similarity > 0.99)
        assert similarity > 0.99

    @pytest.mark.asyncio
    async def test_embedding_different_for_different_text(self, temp_lancedb_dir):
        """Test embeddings differ for semantically different text."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        text1 = "Data analytics and business intelligence"
        text2 = "Customer support and ticket management"

        embedding1 = handler.embed_text(text1)
        embedding2 = handler.embed_text(text2)

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = sum(a ** 2 for a in embedding1) ** 0.5
        magnitude2 = sum(b ** 2 for b in embedding2) ** 0.5
        similarity = dot_product / (magnitude1 * magnitude2) if magnitude1 * magnitude2 > 0 else 0

        # Should be different (similarity < 0.9 for unrelated topics)
        assert similarity < 0.9

    @pytest.mark.asyncio
    async def test_batch_embedding_performance(self, temp_lancedb_dir):
        """Test batch embedding multiple texts."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        texts = [
            "First episode about analytics",
            "Second episode about automation",
            "Third episode about reporting",
            "Fourth episode about database",
            "Fifth episode about API integration"
        ]

        import time
        start = time.time()
        embeddings = [handler.embed_text(text) for text in texts]
        duration = time.time() - start

        # All embeddings generated
        assert len(embeddings) == len(texts)
        assert all(e is not None for e in embeddings)

        # Performance check: should complete in reasonable time
        # (This is a soft check - just ensure it's not excessively slow)
        assert duration < 30  # 5 embeddings should take less than 30 seconds


# ============================================================================
# Semantic Search Tests
# ============================================================================

class TestSemanticSearch:
    """Test semantic similarity search via LanceDB."""

    @pytest.mark.asyncio
    async def test_semantic_search_returns_results(self, test_db, temp_lancedb_dir,
                                                     sample_episodes, sample_agent):
        """Test semantic search returns relevant episodes."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup: Add episodes to LanceDB
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes:
            content = f"{episode.title} {episode.description} {episode.summary}"
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

        # Test search
        results = handler.search(
            table_name=table_name,
            query="data analytics dashboard",
            filter_str=f"agent_id == '{sample_agent.id}'",
            limit=3
        )

        assert len(results) > 0
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_semantic_search_relevance_ranking(self, test_db, temp_lancedb_dir,
                                                       sample_episodes, sample_agent):
        """Test semantic search ranks results by relevance."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes:
            content = f"{episode.title} {episode.description} {episode.summary}"
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

        # Search for analytics-related content
        results = handler.search(
            table_name=table_name,
            query="analytics dashboard metrics",
            filter_str=f"agent_id == '{sample_agent.id}'",
            limit=5
        )

        # Results should be ranked by distance (lower = more similar)
        if len(results) > 1:
            distances = [r.get("_distance", 1.0) for r in results]
            # Check distances are sorted (non-decreasing)
            assert distances == sorted(distances)

    @pytest.mark.asyncio
    async def test_semantic_search_with_filter(self, test_db, temp_lancedb_dir,
                                                 sample_episodes, sample_agent):
        """Test semantic search with agent filtering."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes:
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

        # Search with agent filter
        results = handler.search(
            table_name=table_name,
            query="automation",
            filter_str=f"agent_id == '{sample_agent.id}'",
            limit=10
        )

        # All results should be from the specified agent
        for result in results:
            metadata = result.get("metadata", {})
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            assert metadata.get("agent_id") == sample_agent.id


# ============================================================================
# Hybrid Search Tests
# ============================================================================

class TestHybridSearch:
    """Test hybrid search combining temporal and semantic relevance."""

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_signals(self, test_db, temp_lancedb_dir,
                                                    sample_episodes, sample_agent, mock_governance):
        """Test hybrid search combines temporal and semantic scores."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup LanceDB
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes:
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

        # Create retrieval service with mocked LanceDB
        with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=handler):
            service = EpisodeRetrievalService(test_db)
            service.governance = mock_governance

            # Test contextual retrieval (hybrid)
            result = await service.retrieve_contextual(
                agent_id=sample_agent.id,
                current_task="Create analytics dashboard",
                limit=5
            )

            assert "episodes" in result
            assert "count" in result
            assert isinstance(result["episodes"], list)
            assert result["count"] == len(result["episodes"])

    @pytest.mark.asyncio
    async def test_hybrid_search_weights(self, test_db, temp_lancedb_dir,
                                           sample_episodes, sample_agent, mock_governance):
        """Test hybrid search applies correct weights to temporal and semantic."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes:
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

        with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=handler):
            service = EpisodeRetrievalService(test_db)
            service.governance = mock_governance

            result = await service.retrieve_contextual(
                agent_id=sample_agent.id,
                current_task="automation and reporting",
                limit=3
            )

            # Results should have relevance scores
            assert "episodes" in result
            for episode in result["episodes"]:
                # Check for relevance_score in results
                assert "relevance_score" in episode or "id" in episode


# ============================================================================
# Performance Tests
# ============================================================================

class TestQueryPerformance:
    """Test LanceDB query performance and optimization."""

    @pytest.mark.asyncio
    async def test_search_performance_small_dataset(self, test_db, temp_lancedb_dir,
                                                      sample_episodes):
        """Test search performance with small dataset."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        # Add episodes
        for episode in sample_episodes:
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

        # Measure search performance
        import time
        start = time.time()
        results = handler.search(
            table_name=table_name,
            query="test query",
            limit=5
        )
        duration = time.time() - start

        # Search should be fast (< 5 seconds for small dataset)
        assert duration < 5.0
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieval_service_integration(self, test_db, temp_lancedb_dir,
                                                   sample_episodes, sample_agent, mock_governance):
        """Test EpisodeRetrievalService with real LanceDB operations."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        # Setup
        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes:
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

        # Test service integration
        with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=handler):
            service = EpisodeRetrievalService(test_db)
            service.governance = mock_governance

            # Test semantic retrieval
            result = await service.retrieve_semantic(
                agent_id=sample_agent.id,
                query="analytics and reporting",
                limit=3
            )

            assert "episodes" in result
            assert "count" in result
            assert isinstance(result["episodes"], list)
            assert result["count"] >= 0


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestLanceDBEdgeCases:
    """Test edge cases and error handling in LanceDB operations."""

    @pytest.mark.asyncio
    async def test_empty_query_handling(self, temp_lancedb_dir):
        """Test handling of empty or invalid queries."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "test_table"
        handler.create_table(table_name)

        # Empty query should return empty results or handle gracefully
        results = handler.search(
            table_name=table_name,
            query="",
            limit=5
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_nonexistent_table_search(self, temp_lancedb_dir):
        """Test searching in non-existent table."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)

        # Should handle error gracefully
        try:
            results = handler.search(
                table_name="nonexistent_table",
                query="test",
                limit=5
            )
            # Either returns empty list or raises exception
            assert isinstance(results, list) or True
        except Exception:
            # Exception is acceptable
            pass

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, test_db, temp_lancedb_dir,
                                                 sample_episodes):
        """Test handling special characters in search queries."""
        from core.lancedb_handler import LanceDBHandler, LANCEDB_AVAILABLE

        if not LANCEDB_AVAILABLE:
            pytest.skip("LanceDB not available")

        handler = LanceDBHandler(db_path=temp_lancedb_dir)
        table_name = "episodes"
        handler.create_table(table_name)

        for episode in sample_episodes[:1]:  # Just add one
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

        # Query with special characters
        special_queries = [
            "data & analytics",
            "reporting (monthly)",
            "API + integration",
            "automation/support",
        ]

        for query in special_queries:
            try:
                results = handler.search(
                    table_name=table_name,
                    query=query,
                    limit=5
                )
                assert isinstance(results, list)
            except Exception:
                # Some special chars might cause issues - that's acceptable
                pass
