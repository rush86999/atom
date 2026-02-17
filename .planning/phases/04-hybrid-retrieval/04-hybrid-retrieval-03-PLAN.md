---
phase: 04-hybrid-retrieval
plan: 03
type: execute
wave: 2
depends_on: [01, 02]
files_modified:
  - tests/unit/test_hybrid_retrieval.py
  - tests/property_tests/episodes/test_hybrid_retrieval_invariants.py
  - tests/integration/test_hybrid_retrieval_integration.py
autonomous: true

must_haves:
  truths:
    - Property tests verify retrieval quality (Recall@10 >90%, NDCG@10 >0.85)
    - Performance tests validate latency targets (<200ms total)
    - Property tests verify dimension consistency (384 vs 1024)
    - Property tests verify fallback behavior
    - Property tests verify no duplicates in results
    - Property tests verify results are ranked by score
  artifacts:
    - path: "tests/unit/test_hybrid_retrieval.py"
      provides: "Unit tests for hybrid retrieval components"
      exports: ["test_coarse_search", "test_reranking", "test_fallback"]
    - path: "tests/property_tests/episodes/test_hybrid_retrieval_invariants.py"
      provides: "Property-based tests for retrieval invariants"
      exports: ["Recall@10", "NDCG@10", "dimension_consistency"]
    - path: "tests/integration/test_hybrid_retrieval_integration.py"
      provides: "End-to-end integration tests"
      exports: ["test_hybrid_retrieval_e2e", "test_governance_integration"]
  key_links:
    - from: "tests/unit/test_hybrid_retrieval.py"
      to: "core/hybrid_retrieval_service.py"
      via: "Direct import and testing of service methods"
      pattern: "from core.hybrid_retrieval_service import"
    - from: "tests/property_tests/episodes/test_hybrid_retrieval_invariants.py"
      to: "core/hybrid_retrieval_service.py"
      via: "Property-based invariant testing with Hypothesis"
      pattern: "@given.*hybrid"
---

<objective>
Create comprehensive test suite for hybrid retrieval system covering quality, performance, consistency, and edge cases.

Purpose: Ensure the two-stage retrieval system (FastEmbed coarse + ST reranking) meets quality targets (Recall@10 >90%, NDCG@10 >0.85) and performance targets (<200ms total) while maintaining consistency with existing episodic memory patterns.

Output: Property tests for quality invariants, unit tests for components, integration tests for end-to-end flows.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

@core/hybrid_retrieval_service.py (created in Plan 02)
@core/embedding_service.py (extended in Plans 01-02)
@core/lancedb_handler.py (extended in Plan 01)
@tests/property_tests/episodes/test_episode_retrieval_invariants.py (existing patterns)
</context>

<tasks>

<task type="auto">
  <name>Create property tests for retrieval quality invariants</name>
  <files>tests/property_tests/episodes/test_hybrid_retrieval_invariants.py</files>
  <action>
    Create property-based tests using Hypothesis for critical retrieval invariants:

    1. Import Hypothesis and test utilities:
       ```python
    from hypothesis import given, strategies as st, settings, example
    import pytest
    from core.hybrid_retrieval_service import HybridRetrievalService
    ```

    2. Test class `TestHybridRetrievalQualityInvariants`:

       a) `test_recall_at_k` - Verify Recall@10 >90%:
          - Generate random queries and relevant episode sets
          - Verify at least 9 of 10 relevant episodes found in top-10
          - Use max_examples=50 for statistical significance

       b) `test_ndcg_at_k` - Verify NDCG@10 >0.85:
          - Generate ranked relevance scores for episodes
          - Calculate NDCG@10 for hybrid retrieval results
          - Assert NDCG@10 > 0.85 threshold

       c) `test_dimension_consistency` (CRITICAL - per research pitfall #1):
          - Verify FastEmbed embeddings are 384-dimensional
          - Verify ST embeddings are 1024-dimensional
          - Verify no mixing of dimensions in reranking

       d) `test_no_duplicates_in_results`:
          - Generate queries with potential duplicate matches
          - Verify returned episodes have unique IDs
          - Use `@example` for edge case: single episode matches multiple times

       e) `test_results_ranked_by_score`:
          - Generate query-result pairs with various scores
          - Verify results are in descending score order
          - Check `_rerank_score` field exists and is sorted

    3. Test class `TestHybridRetrievalPerformanceInvariants`:

       a) `test_coarse_search_latency`:
          - Measure FastEmbed coarse search time
          - Assert P95 latency < 20ms

       b) `test_reranking_latency`:
          - Measure cross-encoder reranking time
          - Assert P95 latency < 150ms for 100 candidates

       c) `test_total_latency_budget`:
          - Measure end-to-end hybrid retrieval time
          - Assert P95 latency < 200ms

    4. Test class `TestHybridRetrievalFallbackInvariants`:

       a) `test_fallback_on_rerank_failure`:
          - Simulate cross-encoder failure
          - Verify coarse results returned with warning
          - Verify reranked=False in response

       b) `test_coarse_search_required`:
          - Verify coarse search failure raises error
          - No fallback if initial search fails

    Follow existing property test patterns from test_episode_retrieval_invariants.py.
    Use @settings(max_examples=50) for standard tests, max_examples=100 for critical invariants.
  </action>
  <verify>
    pytest tests/property_tests/episodes/test_hybrid_retrieval_invariants.py -v
  </verify>
  <done>
    - Property test file created with 10+ tests
    - Recall@10 test validates >90% threshold
    - NDCG@10 test validates >0.85 threshold
    - Dimension consistency test prevents mixing 384/1024 embeddings
    - No duplicates and ranking tests exist
    - Performance tests validate latency targets
    - Fallback behavior tests exist
  </done>
</task>

<task type="auto">
  <name>Create unit tests for hybrid retrieval components</name>
  <files>tests/unit/test_hybrid_retrieval.py</files>
  <action>
    Create unit tests for individual components of the hybrid retrieval system:

    1. Test class `TestEmbeddingServiceCoarseSearch`:

       a) `test_fastembed_dimension_is_384`:
          - Generate embedding with FastEmbed
          - Assert len(embedding) == 384

       b) `test_coarse_search_returns_top_k`:
          - Mock LanceDB with 200 documents
          - Call coarse_search with top_k=50
          - Assert exactly 50 results returned

       c) `test_cache_hit_after_first_generation`:
          - Generate same embedding twice
          - Verify second call uses cache (check logs)

    2. Test class `TestEmbeddingServiceReranking`:

       a) `test_cross_encoder_reranking_top_k`:
          - Create 100 candidate documents
          - Rerank with top_k=10
          - Assert 10 results returned

       b) `test_rerank_scores_normalized`:
          - Rerank candidates
          - Assert all scores in [0, 1] range

       c) `test_reranking_fallback_to_biencoder`:
          - Mock cross-encoder to raise exception
          - Verify fallback to bi-encoder similarity

       d) `test_reranking_sorts_by_score`:
          - Create candidates with known relevance order
          - Verify reranking reverses order correctly

    3. Test class `TestHybridRetrievalService`:

       a) `test_two_stage_retrieval_flow`:
          - Mock coarse search (returns 100)
          - Mock reranking (returns 50)
          - Verify both stages called

       b) `test_stage_times_tracking`:
          - Run retrieval and measure stage_times
          - Verify coarse_ms and rerank_ms recorded

       c) `test_coarse_k_greater_than_top_k`:
          - Test with coarse_k=100, top_k=50
          - Verify 100 candidates, 50 final results

       d) `test_enable_rerank_false_skips_reranking`:
          - Call with enable_rerank=False
          - Verify only coarse search executed

    4. Test class `TestDualVectorStorage`:

       a) `test_lancedb_has_both_vector_columns`:
          - Check schema for vector and vector_fastembed
          - Assert dimensions: 1024 and 384

       b) `test_embed_dual_generates_both`:
          - Call embed_dual
          - Verify both embeddings returned

    Use AsyncMock for async methods, MagicMock for LanceDB/db.
    Follow existing unit test patterns from tests/unit/.
  </action>
  <verify>
    pytest tests/unit/test_hybrid_retrieval.py -v
  </verify>
  <done>
    - Unit test file created with 15+ tests
    - FastEmbed dimension test (384)
    - Coarse search top-k test
    - Cache hit test
    - Reranking tests (top_k, normalization, fallback, sorting)
    - HybridRetrievalService tests (two-stage, timing, parameters)
    - Dual vector storage tests
  </done>
</task>

<task type="auto">
  <name>Create integration tests for end-to-end flows</name>
  <files>tests/integration/test_hybrid_retrieval_integration.py</files>
  <action>
    Create integration tests for complete hybrid retrieval workflows:

    1. Test class `TestHybridRetrievalE2E`:

       a) `test_full_retrieval_pipeline`:
          - Create test episodes in database
          - Create LanceDB entries with both embeddings
          - Run hybrid retrieval query
          - Verify correct episodes returned

       b) `test_governance_integration`:
          - Test with STUDENT agent (should block/fallback)
          - Test with INTERN agent (should succeed)
          - Test with AUTONOMOUS agent (full access)

       c) `test_performance_with_real_data`:
          - Create 1000 test episodes
          - Run 10 hybrid queries
          - Verify average latency <200ms

       d) `test_quality_with_relevant_episodes`:
          - Create episodes with known relevance to query
          - Run hybrid retrieval
          - Verify relevant episodes ranked high

    2. Test class `TestHybridRetrievalAPI`:

       a) `test_hybrid_retrieval_endpoint`:
          - POST to /api/episodes/retrieve/hybrid
          - Verify response structure

       b) `test_hybrid_retrieval_request_validation`:
          - Test invalid top_k (negative, >500)
          - Test missing query
          - Verify 422 responses

       c) `test_hybrid_retrieval_governance_enforcement`:
          - Call endpoint with STUDENT agent
          - Verify 403 or fallback to temporal

    3. Test class `TestHybridRetrievalWithRealModels`:

       a) `test_fastembed_real_model_generation`:
          - Use actual FastEmbed model (not mocked)
          - Verify 384-dim output
          - Verify <20ms latency

       b) `test_cross_encoder_real_model_reranking`:
          - Use actual cross-encoder (not mocked)
          - Verify reranking improves ranking
          - Verify <150ms latency for 100 candidates

    Use test database (SQLite) and test LanceDB instance.
    Follow existing integration test patterns from tests/integration/.
    Clean up test data in finally blocks.
  </action>
  <verify>
    pytest tests/integration/test_hybrid_retrieval_integration.py -v
  </verify>
  <done>
    - Integration test file created with 10+ tests
    - Full pipeline test (DB + LanceDB + retrieval)
    - Governance integration test
    - Performance test with real data
    - API endpoint tests
    - Real model tests (not mocked)
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run full test suite for hybrid retrieval:
   ```bash
   pytest tests/property_tests/episodes/test_hybrid_retrieval_invariants.py -v
   pytest tests/unit/test_hybrid_retrieval.py -v
   pytest tests/integration/test_hybrid_retrieval_integration.py -v
   ```

2. Verify property test coverage:
   - Check that Recall@10 > 90% test passes
   - Check that NDCG@10 > 0.85 test passes
   - Check dimension consistency test passes

3. Verify performance tests pass:
   - Coarse search < 20ms P95
   - Reranking < 150ms P95
   - Total < 200ms P95

4. Verify all tests use proper fixtures:
   - db_session for database tests
   - Mock for external dependencies (when appropriate)
   - Real models for performance validation

5. Check test coverage:
   ```bash
   pytest --cov=core/hybrid_retrieval_service --cov=core/embedding_service --cov-report=term-missing
   ```
   Target: >80% coverage for new code
</verification>

<success_criteria>
1. Property tests validate quality invariants (Recall@10, NDCG@10)
2. Property tests prevent dimension mismatch (384 vs 1024)
3. Performance tests validate latency targets (<200ms total)
4. Unit tests cover all components with >80% coverage
5. Integration tests validate end-to-end flows
6. All tests follow existing patterns (fixtures, mocking, cleanup)
7. Zero test failures when run together
</success_criteria>

<output>
After completion, create `.planning/phases/04-hybrid-retrieval/04-hybrid-retrieval-03-SUMMARY.md`
</output>
