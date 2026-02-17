---
phase: 04-hybrid-retrieval
plan: 03
type: execute
wave: 2
depends_on: ["04-hybrid-retrieval-01", "04-hybrid-retrieval-02"]
files_modified:
  - tests/unit/test_hybrid_retrieval.py
  - tests/property_tests/episodes/test_hybrid_retrieval_invariants.py
  - tests/integration/test_hybrid_retrieval_integration.py
autonomous: true

must_haves:
  truths:
    - "Recall@10 >90% (top-10 results include 90% of relevant episodes)"
    - "NDCG@10 >0.85 (ranking quality measured by normalized discounted cumulative gain)"
    - "Relevance score improvement >15% vs. FastEmbed baseline"
    - "Total retrieval latency <200ms (coarse <20ms + rerank <150ms + overhead <30ms)"
    - "Top-k candidates always include best matches (no false negatives from reranking)"
    - "Reranking never decreases relevance scores (monotonic improvement)"
    - "Fallback to FastEmbed baseline maintains quality"
    - "Embedding consistency (same input → same embedding)"
  artifacts:
    - path: "tests/unit/test_hybrid_retrieval.py"
      provides: "Unit tests for HybridRetrievalService and components"
      min_lines: 300
    - path: "tests/property_tests/episodes/test_hybrid_retrieval_invariants.py"
      provides: "Property tests for retrieval quality invariants"
      min_lines: 500
    - path: "tests/integration/test_hybrid_retrieval_integration.py"
      provides: "End-to-end integration tests for hybrid retrieval"
      min_lines: 250
  key_links:
    - from: "tests/unit/test_hybrid_retrieval.py"
      to: "core/hybrid_retrieval_service.py"
      via: "tests all service methods"
      pattern: "test_retrieve_semantic_hybrid|test_rerank_cross_encoder"
    - from: "tests/property_tests/episodes/test_hybrid_retrieval_invariants.py"
      to: "core/hybrid_retrieval_service.py"
      via: "property tests for quality invariants"
      pattern: "test_recall_at_10|test_ndcg_at_10|test_monotonic_improvement"
    - from: "tests/integration/test_hybrid_retrieval_integration.py"
      to: "core/atom_agent_endpoints.py"
      via: "tests API endpoints end-to-end"
      pattern: "test_retrieve_hybrid_endpoint|test_retrieve_baseline_endpoint"
---

## Objective

Create comprehensive test suite for hybrid retrieval system including unit tests, property-based tests for quality invariants, and end-to-end integration tests.

**Purpose:** Ensure hybrid retrieval system meets performance targets (<200ms latency) and quality targets (Recall@10 >90%, NDCG@10 >0.85, >15% relevance improvement). Property tests validate invariants like monotonic improvement and fallback behavior.

**Output:** Unit tests for components, property tests for retrieval invariants, integration tests for API endpoints, performance benchmarks.

## Execution Context

@core/hybrid_retrieval_service.py (from Plan 02)
@core/embedding_service.py (from Plans 01-02)
@core/lancedb_handler.py (from Plan 01)
@.planning/phases/04-hybrid-retrieval/04-hybrid-retrieval-01-PLAN.md
@.planning/phases/04-hybrid-retrieval/04-hybrid-retrieval-02-PLAN.md
@tests/property_tests/episodes/test_episode_retrieval_invariants.py (existing patterns)

## Context

@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md

# Plans 01-02 Complete
- FastEmbed coarse search operational (<20ms)
- HybridRetrievalService with cross-encoder reranking
- Dual vector storage (384-dim + 1024-dim) in LanceDB
- API endpoints for hybrid and baseline retrieval

# Research Findings (04-RESEARCH.md)
- Property testing patterns exist in test_episode_retrieval_invariants.py
- Hypothesis for property-based testing (hypothesis>=6.92.0)
- Performance targets from literature: <200ms total, >90% recall, >0.85 NDCG
- Quality metrics: Recall@10, NDCG@10, relevance improvement

## Tasks

### Task 1: Create Unit Tests for Hybrid Retrieval

**Files:** `tests/unit/test_hybrid_retrieval.py` (NEW)

**Action:**
Create comprehensive unit tests for HybridRetrievalService and components:

```python
"""
Unit Tests for Hybrid Retrieval System

Tests cover:
- HybridRetrievalService methods
- Cross-encoder reranking
- FastEmbed coarse search
- Fallback behavior
- Embedding consistency
"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from core.hybrid_retrieval_service import HybridRetrievalService
from core.embedding_service import EmbeddingService
from core.models import Episode, Agent
from tests.factories import AgentFactory, EpisodeFactory


class TestHybridRetrievalService:
    """Test HybridRetrievalService orchestration."""

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService instance."""
        return HybridRetrievalService(db_session)

    @pytest.fixture
    def agent_with_episodes(self, db_session):
        """Create agent with test episodes."""
        agent = AgentFactory(maturity_level="AUTONOMOUS")

        # Create 100 episodes with varied content
        episodes = []
        for i in range(100):
            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=f"Test episode {i} about topic {i % 10}",
                content=f"Detailed content for episode {i}" * 10
            )
            episodes.append(episode)

        db_session.commit()
        return agent, episodes

    @pytest.mark.asyncio
    async def test_retrieve_semantic_hybrid_with_reranking(
        self, service, agent_with_episodes
    ):
        """Test hybrid retrieval with reranking enabled."""
        agent, episodes = agent_with_episodes

        # Search for specific topic
        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query="episodes about topic 5",
            coarse_top_k=100,
            rerank_top_k=50,
            use_reranking=True
        )

        # Assertions
        assert len(results) > 0, "Should return results"
        assert len(results) <= 50, "Should return at most rerank_top_k results"

        # Check result structure
        for ep_id, score, stage in results:
            assert isinstance(ep_id, str)
            assert 0.0 <= score <= 1.0, f"Score should be in [0, 1], got {score}"
            assert stage in ["reranked", "coarse_fallback", "coarse_only"]

    @pytest.mark.asyncio
    async def test_retrieve_semantic_hybrid_without_reranking(
        self, service, agent_with_episodes
    ):
        """Test hybrid retrieval with reranking disabled (coarse only)."""
        agent, episodes = agent_with_episodes

        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query="episodes about topic 3",
            coarse_top_k=50,
            rerank_top_k=20,
            use_reranking=False
        )

        # Assertions
        assert len(results) > 0
        assert len(results) <= 20

        # All results should be coarse_only
        for ep_id, score, stage in results:
            assert stage == "coarse_only"

    @pytest.mark.asyncio
    async def test_retrieve_semantic_baseline(
        self, service, agent_with_episodes
    ):
        """Test baseline retrieval (FastEmbed only)."""
        agent, episodes = agent_with_episodes

        results = await service.retrieve_semantic_baseline(
            agent_id=agent.id,
            query="episodes about topic 7",
            top_k=20
        )

        # Assertions
        assert len(results) > 0
        assert len(results) <= 20

        # Check result structure (no stage tag in baseline)
        for ep_id, score in results:
            assert isinstance(ep_id, str)
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_fallback_on_reranking_failure(
        self, service, agent_with_episodes, mocker
    ):
        """Test fallback to coarse results when reranking fails."""
        agent, episodes = agent_with_episodes

        # Mock cross-encoder to raise exception
        mocker.patch.object(
            service,
            '_get_reranker_model',
            side_effect=Exception("Reranking failed")
        )

        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query="test query",
            coarse_top_k=50,
            rerank_top_k=20,
            use_reranking=True
        )

        # Assertions
        assert len(results) > 0, "Should fallback to coarse results"

        # All results should be tagged as coarse_fallback
        for ep_id, score, stage in results:
            assert stage == "coarse_fallback"


class TestEmbeddingServiceExtensions:
    """Test EmbeddingService extensions for hybrid retrieval."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService instance."""
        return EmbeddingService(provider="fastembed")

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding(self, embedding_service):
        """Test FastEmbed embedding creation."""
        text = "This is a test episode about machine learning"

        embedding = await embedding_service.create_fastembed_embedding(text)

        # Assertions
        assert embedding is not None
        assert embedding.shape == (384,), f"Expected 384-dim, got {embedding.shape}"
        assert embedding.dtype == np.float32

    @pytest.mark.asyncio
    async def test_fastembed_embedding_consistency(self, embedding_service):
        """Test that same input produces same embedding."""
        text = "Consistent test input"

        embedding1 = await embedding_service.create_fastembed_embedding(text)
        embedding2 = await embedding_service.create_fastembed_embedding(text)

        # Should be identical
        np.testing.assert_array_almost_equal(
            embedding1, embedding2,
            decimal=5,
            err_msg="Same input should produce identical embeddings"
        )

    @pytest.mark.asyncio
    async def test_coarse_search_performance(self, embedding_service, db_session):
        """Test FastEmbed coarse search performance (<20ms)."""
        # Create test data
        agent = AgentFactory()
        episodes = [EpisodeFactory(agent_id=agent.id) for _ in range(1000)]
        db_session.commit()

        # Measure search time
        start = datetime.utcnow()
        results = await embedding_service.coarse_search_fastembed(
            agent_id=agent.id,
            query="test query",
            top_k=100,
            db=db_session
        )
        duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

        # Assertions
        assert duration_ms < 20, f"Coarse search should be <20ms, got {duration_ms}ms"
        assert len(results) <= 100


class TestCrossEncoderReranking:
    """Test cross-encoder reranking."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService with cross-encoder."""
        return EmbeddingService(provider="hybrid")

    @pytest.mark.asyncio
    async def test_rerank_cross_encoder(self, embedding_service, db_session):
        """Test cross-encoder reranking."""
        # Create test data
        agent = AgentFactory()
        episodes = [
            EpisodeFactory(
                agent_id=agent.id,
                summary=f"Episode {i} about specific topic",
                content=f"Content {i}" * 20
            )
            for i in range(50)
        ]
        db_session.commit()

        episode_ids = [ep.id for ep in episodes]

        # Rerank
        results = await embedding_service.rerank_cross_encoder(
            query="specific topic",
            episode_ids=episode_ids,
            agent_id=agent.id,
            db=db_session
        )

        # Assertions
        assert len(results) > 0
        assert len(results) <= 50

        # Scores should be in [0, 1]
        for ep_id, score in results:
            assert 0.0 <= score <= 1.0, f"Score should be in [0, 1], got {score}"

        # Results should be sorted by score (descending)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score"

    @pytest.mark.asyncio
    async def test_reranking_performance(self, embedding_service, db_session):
        """Test reranking performance (<150ms for 50 candidates)."""
        # Create test data
        agent = AgentFactory()
        episodes = [EpisodeFactory(agent_id=agent.id) for _ in range(50)]
        db_session.commit()

        episode_ids = [ep.id for ep in episodes]

        # Measure reranking time
        start = datetime.utcnow()
        results = await embedding_service.rerank_cross_encoder(
            query="test query",
            episode_ids=episode_ids,
            agent_id=agent.id,
            db=db_session
        )
        duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

        # Assertions
        assert duration_ms < 150, f"Reranking should be <150ms, got {duration_ms}ms"
```

**Tests:**
- HybridRetrievalService methods (with/without reranking, fallback)
- FastEmbed embedding creation and consistency
- Coarse search performance (<20ms)
- Cross-encoder reranking performance (<150ms)

**Acceptance:**
- [ ] All unit tests pass
- [ ] Coarse search <20ms verified
- [ ] Reranking <150ms verified
- [ ] Fallback behavior tested

---

### Task 2: Create Property Tests for Retrieval Invariants

**Files:** `tests/property_tests/episodes/test_hybrid_retrieval_invariants.py` (NEW)

**Action:**
Create property-based tests for retrieval quality invariants:

```python
"""
Property-Based Tests for Hybrid Retrieval Invariants

Tests CRITICAL invariants:
- Recall@10 >90% (top-10 includes 90% of relevant episodes)
- NDCG@10 >0.85 (ranking quality)
- Top-k always includes best matches (no false negatives)
- Reranking never decreases relevance (monotonic improvement)
- Fallback maintains baseline quality
- Embedding consistency (same input → same embedding)
"""
import pytest
import numpy as np
from hypothesis import strategies as st, given, settings
from sqlalchemy.orm import Session

from core.hybrid_retrieval_service import HybridRetrievalService
from core.embedding_service import EmbeddingService
from core.models import Episode
from tests.factories import AgentFactory, EpisodeFactory


class TestRecallAtK:
    """
    Recall@K invariants.

    Recall@K = (relevant episodes in top-K) / (total relevant episodes)

    Target: Recall@10 >90%
    """

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        return HybridRetrievalService(db_session)

    @given(
        query=st.text(min_size=5, max_size=100).filter(lambda x: x.strip()),
        num_episodes=st.integers(min_value=50, max_value=200)
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_recall_at_10_gt_90_percent(
        self, service, db_session, query, num_episodes
    ):
        """
        Recall@10 >90% invariant.

        Property: Top-10 results should include at least 90% of relevant episodes.
        """
        # Create agent and episodes
        agent = AgentFactory()
        episodes = []

        # Create episodes with query-related content (30% relevant)
        num_relevant = max(1, num_episodes // 3)
        for i in range(num_episodes):
            if i < num_relevant:
                # Relevant: contains query terms
                summary = f"Episode about {query[:20]}"
            else:
                # Irrelevant: different topic
                summary = f"Episode about unrelated topic {i}"

            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=summary,
                content=f"Content {i}"
            )
            episodes.append(episode)

        db_session.commit()

        # Retrieve top-10
        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query=query,
            coarse_top_k=100,
            rerank_top_k=10,
            use_reranking=True
        )

        top_k_ids = [ep_id for ep_id, _, _ in results]
        relevant_in_top_k = sum(
            1 for ep_id in top_k_ids
            if any(ep.id == ep_id for ep in episodes[:num_relevant])
        )

        recall = relevant_in_top_k / num_relevant

        # Assertion
        assert recall > 0.90, f"Recall@10 should be >90%, got {recall:.2%}"


class TestNDCGAtK:
    """
    NDCG@K invariants.

    NDCG@K measures ranking quality (positions of relevant items).

    Target: NDCG@10 >0.85
    """

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        return HybridRetrievalService(db_session)

    @given(
        query=st.text(min_size=5, max_size=50).filter(lambda x: x.strip()),
        num_episodes=st.integers(min_value=50, max_value=150)
    )
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_ndcg_at_10_gt_085(
        self, service, db_session, query, num_episodes
    ):
        """
        NDCG@10 >0.85 invariant.

        Property: Normalized discounted cumulative gain should exceed 0.85.
        """
        # Create agent and episodes with graded relevance
        agent = AgentFactory()
        episodes = []

        # Create episodes with known relevance grades (0-3)
        for i in range(num_episodes):
            relevance_grade = i % 4  # 0 (irrelevant) to 3 (highly relevant)
            if relevance_grade == 3:
                summary = f"{query} - highly relevant"
            elif relevance_grade == 2:
                summary = f"{query} - somewhat relevant"
            elif relevance_grade == 1:
                summary = f"{query} - marginally relevant"
            else:
                summary = f"unrelated topic {i}"

            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=summary,
                content=f"Content {i}"
            )
            episode.relevance_grade = relevance_grade  # Custom attribute
            episodes.append(episode)

        db_session.commit()

        # Retrieve top-10
        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query=query,
            coarse_top_k=100,
            rerank_top_k=10,
            use_reranking=True
        )

        # Calculate NDCG@10
        dcg = 0.0
        for position, (ep_id, _, _) in enumerate(results[:10], start=1):
            episode = next((ep for ep in episodes if ep.id == ep_id), None)
            if episode:
                # DCG: relevance_grade / log2(position + 1)
                dcg += episode.relevance_grade / np.log2(position + 1)

        # Ideal DCG (perfect ranking)
        ideal_grades = sorted([ep.relevance_grade for ep in episodes], reverse=True)[:10]
        idcg = sum(grade / np.log2(i + 2) for i, grade in enumerate(ideal_grades))

        ndcg = dcg / idcg if idcg > 0 else 0.0

        # Assertion
        assert ndcg > 0.85, f"NDCG@10 should be >0.85, got {ndcg:.3f}"


class TestMonotonicImprovement:
    """
    Reranking improvement invariants.

    Property: Reranking should never decrease relevance scores (monotonic).
    """

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        return HybridRetrievalService(db_session)

    @given(
        query=st.text(min_size=5, max_size=50).filter(lambda x: x.strip()),
        num_episodes=st.integers(min_value=20, max_value=50)
    )
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_reranking_monotonic_improvement(
        self, service, db_session, query, num_episodes
    ):
        """
        Reranking monotonic improvement invariant.

        Property: For any episode, reranked score >= coarse score.
        """
        # Create agent and episodes
        agent = AgentFactory()
        episodes = [EpisodeFactory(agent_id=agent.id) for _ in range(num_episodes)]
        db_session.commit()

        # Get coarse results
        coarse_results = await service.retrieve_semantic_baseline(
            agent_id=agent.id,
            query=query,
            top_k=50
        )
        coarse_scores = {ep_id: score for ep_id, score in coarse_results}

        # Get reranked results
        reranked_results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query=query,
            coarse_top_k=50,
            rerank_top_k=50,
            use_reranking=True
        )

        # Check monotonic improvement
        for ep_id, reranked_score, stage in reranked_results:
            if stage == "reranked" and ep_id in coarse_scores:
                coarse_score = coarse_scores[ep_id]
                # Reranked score should be >= coarse score (with small tolerance for numerical errors)
                assert reranked_score >= coarse_score - 0.01, \
                    f"Reranked score {reranked_score:.3f} should be >= coarse score {coarse_score:.3f}"


class TestTopKCompleteness:
    """
    Top-K completeness invariants.

    Property: Top-k results should always include best matches (no false negatives).
    """

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        return HybridRetrievalService(db_session)

    @given(
        query=st.text(min_size=5, max_size=50).filter(lambda x: x.strip()),
        num_episodes=st.integers(min_value=50, max_value=200)
    )
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_top_k_includes_best_matches(
        self, service, db_session, query, num_episodes
    ):
        """
        Top-K completeness invariant.

        Property: Top-k results should include all episodes with perfect relevance.
        """
        # Create agent and episodes
        agent = AgentFactory()
        episodes = []

        # Create 5 perfect matches (exact query in summary)
        for _ in range(5):
            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=query,  # Exact match
                content=f"Content"
            )
            episodes.append(episode)

        # Create other episodes
        for i in range(num_episodes - 5):
            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=f"Other episode {i}",
                content=f"Content {i}"
            )
            episodes.append(episode)

        db_session.commit()

        # Retrieve top-20
        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query=query,
            coarse_top_k=100,
            rerank_top_k=20,
            use_reranking=True
        )

        top_k_ids = [ep_id for ep_id, _, _ in results]

        # All 5 perfect matches should be in top-20
        perfect_match_ids = [ep.id for ep in episodes[:5]]
        perfect_matches_in_top_k = sum(
            1 for ep_id in perfect_match_ids
            if ep_id in top_k_ids
        )

        assert perfect_matches_in_top_k == 5, \
            f"All 5 perfect matches should be in top-20, found {perfect_matches_in_top_k}"


class TestEmbeddingConsistency:
    """
    Embedding consistency invariants.

    Property: Same input should produce identical embeddings.
    """

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService."""
        return EmbeddingService(provider="fastembed")

    @given(text=st.text(min_size=10, max_size=200))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_fastembed_embedding_deterministic(self, embedding_service, text):
        """
        FastEmbed embedding consistency invariant.

        Property: Same input produces identical embedding.
        """
        embedding1 = await embedding_service.create_fastembed_embedding(text)
        embedding2 = await embedding_service.create_fastembed_embedding(text)

        np.testing.assert_array_almost_equal(
            embedding1, embedding2,
            decimal=5,
            err_msg="Same input should produce identical FastEmbed embeddings"
        )

    @given(
        text=st.text(min_size=10, max_size=200),
        num_iterations=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_fastembed_embedding_stable(
        self, embedding_service, text, num_iterations
    ):
        """
        FastEmbed embedding stability across multiple calls.

        Property: Multiple calls produce identical embeddings.
        """
        embeddings = [
            await embedding_service.create_fastembed_embedding(text)
            for _ in range(num_iterations)
        ]

        # All embeddings should be identical
        for i in range(1, len(embeddings)):
            np.testing.assert_array_almost_equal(
                embeddings[0], embeddings[i],
                decimal=5,
                err_msg=f"Embedding {i} should match first embedding"
            )
```

**Tests:**
- Recall@10 >90% (top-10 includes 90% of relevant episodes)
- NDCG@10 >0.85 (ranking quality)
- Reranking monotonic improvement (never decreases scores)
- Top-K completeness (includes best matches)
- Embedding consistency (deterministic)

**Acceptance:**
- [ ] All property tests pass
- [ ] Recall@10 >90% verified (50+ examples)
- [ ] NDCG@10 >0.85 verified (30+ examples)
- [ ] Monotonic improvement verified (30+ examples)
- [ ] Embedding consistency verified (100+ examples)

---

### Task 3: Create Integration Tests

**Files:** `tests/integration/test_hybrid_retrieval_integration.py` (NEW)

**Action:**
Create end-to-end integration tests:

```python
"""
Integration Tests for Hybrid Retrieval System

Tests cover:
- API endpoints (POST /agents/{id}/retrieve-hybrid, /retrieve-baseline)
- End-to-end retrieval flows
- Performance benchmarks
- A/B testing (hybrid vs. baseline)
"""
import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.models import Agent, Episode
from tests.factories import AgentFactory, EpisodeFactory


class TestHybridRetrievalAPI:
    """Test hybrid retrieval API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent_with_data(self, db_session):
        """Create agent with test episodes."""
        agent = AgentFactory(maturity_level="AUTONOMOUS")

        # Create 200 episodes
        episodes = []
        for i in range(200):
            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=f"Episode {i} about topic {i % 20}",
                content=f"Detailed content for episode {i}" * 15
            )
            episodes.append(episode)

        db_session.commit()
        return agent, episodes

    def test_retrieve_hybrid_endpoint_success(self, client, agent_with_data):
        """Test POST /agents/{id}/retrieve-hybrid returns results."""
        agent, episodes = agent_with_data

        response = client.post(
            f"/agents/{agent.id}/retrieve-hybrid",
            json={
                "query": "episodes about topic 5",
                "coarse_top_k": 100,
                "rerank_top_k": 20,
                "use_reranking": True
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert len(data["results"]) <= 20

        # Check result structure
        for result in data["results"]:
            assert "episode_id" in result
            assert "relevance_score" in result
            assert "stage" in result
            assert 0.0 <= result["relevance_score"] <= 1.0

    def test_retrieve_baseline_endpoint_success(self, client, agent_with_data):
        """Test POST /agents/{id}/retrieve-baseline returns results."""
        agent, episodes = agent_with_data

        response = client.post(
            f"/agents/{agent.id}/retrieve-baseline",
            json={
                "query": "episodes about topic 10",
                "top_k": 20
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert len(data["results"]) <= 20

        # Baseline results should NOT have stage tag
        for result in data["results"]:
            assert "episode_id" in result
            assert "relevance_score" in result
            assert "stage" not in result

    def test_retrieve_hybrid_performance(self, client, agent_with_data):
        """Test hybrid retrieval performance (<200ms)."""
        agent, episodes = agent_with_data

        # Measure response time
        start = time.time()
        response = client.post(
            f"/agents/{agent.id}/retrieve-hybrid",
            json={
                "query": "test query for performance",
                "coarse_top_k": 100,
                "rerank_top_k": 50,
                "use_reranking": True
            }
        )
        duration_ms = (time.time() - start) * 1000

        # Assertions
        assert response.status_code == 200
        assert duration_ms < 200, f"Response should be <200ms, got {duration_ms:.1f}ms"


class TestEndToEndFlows:
    """Test end-to-end retrieval flows."""

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        from core.hybrid_retrieval_service import HybridRetrievalService
        return HybridRetrievalService(db_session)

    def test_full_retrieval_flow(self, service, db_session):
        """Test complete flow: query → retrieve → fetch episodes."""
        # Create agent and episodes
        agent = AgentFactory()
        episodes = [
            EpisodeFactory(
                agent_id=agent.id,
                summary=f"Episode {i} about specific topic",
                content=f"Content {i}"
            )
            for i in range(100)
        ]
        db_session.commit()

        # Retrieve
        results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query="specific topic",
            coarse_top_k=50,
            rerank_top_k=20,
            use_reranking=True
        )

        # Fetch full episode data
        episode_ids = [ep_id for ep_id, _, _ in results]
        fetched_episodes = db_session.query(Episode).filter(
            Episode.id.in_(episode_ids)
        ).all()

        # Assertions
        assert len(fetched_episodes) > 0
        assert len(fetched_episodes) == len(episode_ids)

        # Verify all episodes belong to agent
        for ep in fetched_episodes:
            assert ep.agent_id == agent.id


class TestABTesting:
    """Test A/B comparison: hybrid vs. baseline."""

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        from core.hybrid_retrieval_service import HybridRetrievalService
        return HybridRetrievalService(db_session)

    @pytest.mark.asyncio
    async def test_hybrid_outperforms_baseline(
        self, service, db_session
    ):
        """
        A/B test: hybrid should improve relevance by >15%.

        Measures: Average relevance score for top-10 results.
        """
        # Create agent and episodes
        agent = AgentFactory()
        episodes = []
        for i in range(200):
            # Create episodes with varying relevance to test query
            if i < 50:
                # High relevance
                summary = f"machine learning and neural networks"
            elif i < 100:
                # Medium relevance
                summary = f"machine learning algorithms"
            else:
                # Low relevance
                summary = f"unrelated topic {i}"

            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=summary,
                content=f"Content {i}"
            )
            episodes.append(episode)

        db_session.commit()

        query = "neural networks"

        # Baseline retrieval
        baseline_results = await service.retrieve_semantic_baseline(
            agent_id=agent.id,
            query=query,
            top_k=10
        )
        baseline_scores = [score for _, score in baseline_results[:10]]
        baseline_avg = np.mean(baseline_scores) if baseline_scores else 0.0

        # Hybrid retrieval
        hybrid_results = await service.retrieve_semantic_hybrid(
            agent_id=agent.id,
            query=query,
            coarse_top_k=100,
            rerank_top_k=10,
            use_reranking=True
        )
        hybrid_scores = [score for _, score, _ in hybrid_results[:10]]
        hybrid_avg = np.mean(hybrid_scores) if hybrid_scores else 0.0

        # Calculate improvement
        improvement = (hybrid_avg - baseline_avg) / (baseline_avg + 1e-8)

        # Assertion
        assert improvement > 0.15, \
            f"Hybrid should improve relevance by >15%, got {improvement:.1%} improvement"
```

**Tests:**
- API endpoint success cases
- Performance benchmarks (<200ms)
- End-to-end retrieval flows
- A/B testing (hybrid vs. baseline >15% improvement)

**Acceptance:**
- [ ] All integration tests pass
- [ ] API endpoints return results in <200ms
- [ ] End-to-end flows tested
- [ ] A/B test shows >15% improvement

---

## Deviations

**Rule 1 (Auto-fix bugs):** If tests fail due to missing dependencies, add to requirements.txt.

**Rule 2 (Performance):** If performance tests exceed targets, document and investigate.

**Rule 3 (Property tests):** If property tests flaky, adjust Hypothesis settings or add preconditions.

## Success Criteria

- [ ] Unit tests: All components tested
- [ ] Property tests: Recall@10 >90%, NDCG@10 >0.85 verified
- [ ] Integration tests: API endpoints and end-to-end flows tested
- [ ] Performance: <200ms hybrid retrieval verified
- [ ] Quality: >15% improvement vs. baseline verified

## Dependencies

- Plan 04-01 (FastEmbed Integration) must be complete
- Plan 04-02 (Sentence Transformers Reranking) must be complete

## Estimated Duration

4-5 hours (unit tests + property tests + integration tests + performance validation)
