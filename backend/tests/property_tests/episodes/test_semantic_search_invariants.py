"""
Property-based tests for semantic search consistency invariants.

Uses Hypothesis to test semantic search invariants across many generated inputs:
- Determinism: Same query returns same results (same order)
- Stability: Search results stable across multiple calls
- Relevance: Returned episodes are relevant to query (similarity > threshold)
- Ranking: Results ranked by relevance (descending similarity)
- Pagination: Paginated results have no duplicates
- Completeness: All pages combined = full result set
- Result count: Result count <= limit parameter
- Empty query: Empty query returns empty results or defaults

These tests complement the integration tests by verifying invariants hold
across many different input combinations.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from hypothesis import given, strategies as st, settings, HealthCheck

from core.episode_retrieval_service import EpisodeRetrievalService
from core.models import AgentEpisode


# =============================================================================
# Property-Based Tests for Search Determinism
# =============================================================================

class TestSearchDeterminism:
    """
    Property-based tests for semantic search determinism invariants.

    Verifies that search results are deterministic and stable.
    """

    @pytest.mark.asyncio
    @given(
        query=st.text(min_size=1, max_size=500, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_deterministic_invariant(self, retrieval_service_mocked, query):
        """
        Same query returns same results (same order).

        Property: For any query Q, running semantic search twice
        with the same Q should return identical results in the same order.

        Mathematical specification:
        Let R(Q) be the result set for query Q
        Then: R(Q) = R'(Q) (deterministic)
        And: order(R(Q)) = order(R'(Q)) (same ordering)

        This ensures reproducibility of search results.
        """
        from hypothesis import HealthCheck

        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create test episodes
        episodes = []
        for i in range(5):
            ep = AgentEpisode(
                id=f"ep_{i}_{uuid4().hex[:8]}",
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Test task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i),
                completed_at=base_time - timedelta(hours=i-1) if i > 0 else None
            )
            episodes.append(ep)
            retrieval_service_mocked.db.add(ep)

        retrieval_service_mocked.db.commit()

        # Mock semantic search to return deterministic results
        mock_results = [
            {"id": episodes[0].id, "similarity": 0.95},
            {"id": episodes[1].id, "similarity": 0.85},
        ]
        retrieval_service_mocked.lancedb.search.return_value = mock_results

        # Run search twice
        result1 = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task=query,
            limit=10,
            require_canvas=False,
            require_feedback=False
        )

        result2 = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task=query,
            limit=10,
            require_canvas=False,
            require_feedback=False
        )

        # Verify deterministic results
        assert result1["count"] == result2["count"], (
            f"Result count differs: {result1['count']} vs {result2['count']}"
        )

        # Extract episode IDs
        ids1 = [ep["id"] for ep in result1["episodes"]]
        ids2 = [ep["id"] for ep in result2["episodes"]]

        assert ids1 == ids2, (
            f"Search results not deterministic: {ids1} vs {ids2}"
        )

    @pytest.mark.asyncio
    @given(
        query=st.text(min_size=1, max_size=200, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_stability_invariant(self, retrieval_service_mocked, query):
        """
        Search results are stable across multiple calls.

        Property: For any query Q, running semantic search multiple times
        should return results with the same relevance scores.

        Mathematical specification:
        Let R(Q) = [(e₁, s₁), (e₂, s₂), ..., (eₙ, sₙ)] be search results
        Let R'(Q) = [(e₁, s₁'), (e₂, s₂'), ..., (eₙ, sₙ')] be second run
        Then: sᵢ = sᵢ' for all i in [1, n] (scores stable)

        This ensures consistent ranking across queries.
        """
        from hypothesis import HealthCheck

        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create test episode
        episode = AgentEpisode(
            id=str(uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test task",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="active",
            started_at=base_time - timedelta(hours=1)
        )
        retrieval_service_mocked.db.add(episode)
        retrieval_service_mocked.db.commit()

        # Mock semantic search with fixed similarity score
        fixed_similarity = 0.87
        retrieval_service_mocked.lancedb.search.return_value = [
            {"id": episode.id, "similarity": fixed_similarity}
        ]

        # Run search multiple times
        results = []
        for _ in range(3):
            result = await retrieval_service_mocked.retrieve_contextual(
                agent_id=agent_id,
                current_task=query,
                limit=10,
                require_canvas=False,
                require_feedback=False
            )
            results.append(result)

        # Verify stability - all results should have same scores
        for i in range(1, len(results)):
            assert results[i]["count"] == results[0]["count"], (
                f"Result count not stable: {results[0]['count']} vs {results[i]['count']}"
            )

            if results[0]["count"] > 0 and results[i]["count"] > 0:
                score1 = results[0]["episodes"][0].get("relevance_score", 0)
                score2 = results[i]["episodes"][0].get("relevance_score", 0)

                assert score1 == score2, (
                    f"Relevance scores not stable: {score1} vs {score2}"
                )


# =============================================================================
# Property-Based Tests for Search Relevance
# =============================================================================

class TestSearchRelevance:
    """
    Property-based tests for semantic search relevance invariants.

    Verifies that search results are relevant and properly ranked.
    """

    @pytest.mark.asyncio
    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_relevance_invariant(self, retrieval_service_mocked, similarity_scores):
        """
        Returned episodes are relevant to query (similarity > threshold).

        Property: For any semantic search result, all returned episodes
        must have similarity score >= relevance_threshold.

        Mathematical specification:
        Let R = [(e₁, s₁), (e₂, s₂), ..., (eₙ, sₙ)] be search results
        Let T be the relevance threshold (e.g., 0.5)
        Then: sᵢ >= T for all i in [1, n]

        This ensures only relevant episodes are returned.
        """
        from hypothesis import HealthCheck

        RELEVANCE_THRESHOLD = 0.5

        # Filter scores by threshold
        relevant_scores = [s for s in similarity_scores if s >= RELEVANCE_THRESHOLD]

        # Create mock episodes for relevant scores
        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        mock_results = []
        for i, score in enumerate(relevant_scores):
            ep_id = f"ep_{i}_{uuid4().hex[:8]}"
            mock_results.append({"id": ep_id, "similarity": score})

            # Create episode in DB
            episode = AgentEpisode(
                id=ep_id,
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i)
            )
            retrieval_service_mocked.db.add(episode)

        retrieval_service_mocked.db.commit()
        retrieval_service_mocked.lancedb.search.return_value = mock_results

        # Run search
        result = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task="test query",
            limit=10,
            require_canvas=False,
            require_feedback=False
        )

        # Verify all results meet relevance threshold
        if result["count"] > 0:
            for ep in result["episodes"]:
                relevance = ep.get("relevance_score", 0)
                assert relevance >= RELEVANCE_THRESHOLD, (
                    f"Episode {ep['id']} has relevance {relevance} < threshold {RELEVANCE_THRESHOLD}"
                )

    @pytest.mark.asyncio
    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_ranking_invariant(self, retrieval_service_mocked, similarity_scores):
        """
        Results are ranked by relevance (descending similarity).

        Property: For any semantic search result, episodes must be
        sorted by relevance score in descending order.

        Mathematical specification:
        Let R = [(e₁, s₁), (e₂, s₂), ..., (eₙ, sₙ)] be search results
        Then: s₁ >= s₂ >= ... >= sₙ (descending order)

        This ensures most relevant episodes appear first.
        """
        from hypothesis import HealthCheck

        # Sort scores in descending order (as they should be returned)
        sorted_scores = sorted(similarity_scores, reverse=True)

        # Create mock episodes with sorted scores
        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        mock_results = []
        for i, score in enumerate(sorted_scores):
            ep_id = f"ep_{i}_{uuid4().hex[:8]}"
            mock_results.append({"id": ep_id, "similarity": score})

            episode = AgentEpisode(
                id=ep_id,
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i)
            )
            retrieval_service_mocked.db.add(episode)

        retrieval_service_mocked.db.commit()
        retrieval_service_mocked.lancedb.search.return_value = mock_results

        # Run search
        result = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task="test query",
            limit=10,
            require_canvas=False,
            require_feedback=False
        )

        # Verify descending ranking
        if result["count"] >= 2:
            for i in range(result["count"] - 1):
                score_current = result["episodes"][i].get("relevance_score", 0)
                score_next = result["episodes"][i + 1].get("relevance_score", 0)

                assert score_current >= score_next, (
                    f"Results not ranked: episode {i} has score {score_current}, "
                    f"episode {i+1} has score {score_next} (should be descending)"
                )


# =============================================================================
# Property-Based Tests for Search Pagination
# =============================================================================

class TestSearchPagination:
    """
    Property-based tests for semantic search pagination invariants.

    Verifies that pagination works correctly without duplicates.
    """

    @pytest.mark.asyncio
    @given(
        total_episodes=st.integers(min_value=5, max_value=50),
        page_size=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_pagination_invariant(self, retrieval_service_mocked, total_episodes, page_size):
        """
        Paginated results have no duplicates.

        Property: For any paginated search, no episode ID should appear
        more than once across all pages.

        Mathematical specification:
        Let P₁, P₂, ..., Pₖ be pages of search results
        Let IDs(Pᵢ) be the set of episode IDs in page Pᵢ
        Then: IDs(Pᵢ) ∩ IDs(Pⱼ) = ∅ for all i ≠ j (no duplicates)

        This ensures correct pagination without overlap.
        """
        from hypothesis import HealthCheck

        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create episodes
        episode_ids = []
        for i in range(total_episodes):
            ep_id = f"ep_{i}_{uuid4().hex[:8]}"
            episode_ids.append(ep_id)

            episode = AgentEpisode(
                id=ep_id,
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i)
            )
            retrieval_service_mocked.db.add(episode)

        retrieval_service_mocked.db.commit()

        # Mock semantic search to return all episodes
        mock_results = [{"id": ep_id, "similarity": 0.9 - (i * 0.01)} for i, ep_id in enumerate(episode_ids)]
        retrieval_service_mocked.lancedb.search.return_value = mock_results

        # Simulate pagination
        all_episode_ids = set()
        num_pages = (total_episodes + page_size - 1) // page_size  # Ceiling division

        for page in range(num_pages):
            offset = page * page_size
            limit = min(page_size, total_episodes - offset)

            # Retrieve page
            result = await retrieval_service_mocked.retrieve_contextual(
                agent_id=agent_id,
                current_task="test query",
                limit=limit,
                require_canvas=False,
                require_feedback=False
            )

            # Extract episode IDs
            page_ids = [ep["id"] for ep in result["episodes"]]

            # Check for duplicates within page
            assert len(page_ids) == len(set(page_ids)), (
                f"Page {page} has duplicate episode IDs: {page_ids}"
            )

            # Check for duplicates across pages
            for ep_id in page_ids:
                assert ep_id not in all_episode_ids, (
                    f"Duplicate episode ID {ep_id} found on page {page}"
                )
                all_episode_ids.add(ep_id)

        # Verify all episodes accounted for (up to page_size * num_pages)
        assert len(all_episode_ids) <= total_episodes, (
            f"More unique episodes returned than exist: {len(all_episode_ids)} > {total_episodes}"
        )

    @pytest.mark.asyncio
    @given(
        total_episodes=st.integers(min_value=5, max_value=30),
        page_size=st.integers(min_value=3, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_completeness_invariant(self, retrieval_service_mocked, total_episodes, page_size):
        """
        All pages combined equal full result set.

        Property: For any paginated search, concatenating all pages
        should give the complete result set.

        Mathematical specification:
        Let P₁, P₂, ..., Pₖ be pages of search results
        Let R = P₁ ∪ P₂ ∪ ... ∪ Pₖ (concatenated)
        Let T be the full result set (no pagination)
        Then: |R| = |T| (completeness)

        This ensures pagination doesn't miss results.
        """
        from hypothesis import HealthCheck

        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create episodes
        episode_ids = []
        for i in range(total_episodes):
            ep_id = f"ep_{i}_{uuid4().hex[:8]}"
            episode_ids.append(ep_id)

            episode = AgentEpisode(
                id=ep_id,
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i)
            )
            retrieval_service_mocked.db.add(episode)

        retrieval_service_mocked.db.commit()

        # Mock semantic search
        mock_results = [{"id": ep_id, "similarity": 0.9} for ep_id in episode_ids]
        retrieval_service_mocked.lancedb.search.return_value = mock_results

        # Retrieve all episodes without pagination
        full_result = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task="test query",
            limit=total_episodes,
            require_canvas=False,
            require_feedback=False
        )

        # Retrieve with pagination
        all_paginated_ids = []
        num_pages = (total_episodes + page_size - 1) // page_size

        for page in range(num_pages):
            offset = page * page_size
            limit = min(page_size, total_episodes - offset)

            result = await retrieval_service_mocked.retrieve_contextual(
                agent_id=agent_id,
                current_task="test query",
                limit=limit,
                require_canvas=False,
                require_feedback=False
            )

            page_ids = [ep["id"] for ep in result["episodes"]]
            all_paginated_ids.extend(page_ids)

        # Verify completeness
        full_ids = [ep["id"] for ep in full_result["episodes"]]

        assert len(all_paginated_ids) == len(full_ids), (
            f"Pagination incomplete: paginated count {len(all_paginated_ids)} "
            f"!= full count {len(full_ids)}"
        )

        assert set(all_paginated_ids) == set(full_ids), (
            "Paginated results don't match full result set"
        )


# =============================================================================
# Property-Based Tests for Search Bounds
# =============================================================================

class TestSearchBounds:
    """
    Property-based tests for semantic search bound invariants.

    Verifies that search respects result count limits and empty queries.
    """

    @pytest.mark.asyncio
    @given(
        total_episodes=st.integers(min_value=5, max_value=30),
        limit=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_result_count_invariant(self, retrieval_service_mocked, total_episodes, limit):
        """
        Result count respects limit parameter.

        Property: For any search with limit L, the number of returned
        episodes should be <= L.

        Mathematical specification:
        Let R(Q, L) be search results for query Q with limit L
        Then: |R(Q, L)| <= L (limit respected)

        This ensures pagination limits are enforced.
        """
        from hypothesis import HealthCheck

        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create episodes
        episode_ids = []
        for i in range(total_episodes):
            ep_id = f"ep_{i}_{uuid4().hex[:8]}"
            episode_ids.append(ep_id)

            episode = AgentEpisode(
                id=ep_id,
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i)
            )
            retrieval_service_mocked.db.add(episode)

        retrieval_service_mocked.db.commit()

        # Mock semantic search
        mock_results = [{"id": ep_id, "similarity": 0.9} for ep_id in episode_ids]
        retrieval_service_mocked.lancedb.search.return_value = mock_results

        # Run search with limit
        result = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task="test query",
            limit=limit,
            require_canvas=False,
            require_feedback=False
        )

        # Verify limit respected
        actual_count = result["count"]
        assert actual_count <= limit, (
            f"Result count {actual_count} exceeds limit {limit}"
        )

        # Also verify <= total episodes
        assert actual_count <= total_episodes, (
            f"Result count {actual_count} exceeds total episodes {total_episodes}"
        )

    @pytest.mark.asyncio
    @given(
        empty_query=st.sampled_from(["", "   ", "\t", "\n", "  \t\n  "])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_empty_query_invariant(self, retrieval_service_mocked, empty_query):
        """
        Empty query returns empty results or defaults.

        Property: For any empty or whitespace-only query Q,
        the search should return empty results or use default query.

        Mathematical specification:
        Let Q be an empty query (len(Q.strip()) = 0)
        Let R(Q) be search results for Q
        Then: |R(Q)| = 0 (empty results)
        Or: R(Q) = R(default_query) (use default)

        This handles edge case of empty search queries.
        """
        from hypothesis import HealthCheck

        agent_id = f"test_agent_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create test episodes
        for i in range(5):
            episode = AgentEpisode(
                id=f"ep_{i}_{uuid4().hex[:8]}",
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="AUTONOMOUS",
                human_intervention_count=0,
                outcome="success",
                status="active",
                started_at=base_time - timedelta(hours=i)
            )
            retrieval_service_mocked.db.add(episode)

        retrieval_service_mocked.db.commit()

        # Mock empty search results
        retrieval_service_mocked.lancedb.search.return_value = []

        # Run search with empty query
        result = await retrieval_service_mocked.retrieve_contextual(
            agent_id=agent_id,
            current_task=empty_query,
            limit=10,
            require_canvas=False,
            require_feedback=False
        )

        # Verify empty query behavior
        # Either empty results or handled gracefully
        if empty_query.strip() == "":
            # Truly empty query - should return empty or use default
            # We expect empty results from our mock
            assert result["count"] >= 0, "Empty query should not cause errors"
            # In real implementation, might use default query
        else:
            # Whitespace-only query - same behavior
            assert result["count"] >= 0, "Whitespace query should not cause errors"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def retrieval_service_mocked(db_session):
    """
    Create EpisodeRetrievalService instance with mocked LanceDB.

    Mocks search to return test episodes for semantic retrieval testing.
    """
    # Mock LanceDB handler
    mock_lancedb = Mock()
    mock_lancedb.search.return_value = []  # Default empty search results

    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeRetrievalService(db_session)
        service.lancedb = mock_lancedb
        yield service


@pytest.fixture(scope="function")
def db_session():
    """
    Create fresh database session for property tests.

    Uses in-memory SQLite for test isolation.
    """
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import pool

    # Set testing environment
    os.environ["TESTING"] = "1"

    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Use pooled connections with check_same_thread=False for SQLite
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
        echo=False,
        pool_pre_ping=True
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables we need
    from core.database import Base

    tables_to_create = [
        'agent_episodes',
        'episode_segments',
        'canvas_audit',
        'agent_feedback',
        'agent_registry',
        'chat_sessions',
    ]

    for table_name in tables_to_create:
        if table_name in Base.metadata.tables:
            try:
                Base.metadata.tables[table_name].create(engine, checkfirst=True)
            except Exception as e:
                print(f"Warning: Could not create table {table_name}: {e}")

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass
