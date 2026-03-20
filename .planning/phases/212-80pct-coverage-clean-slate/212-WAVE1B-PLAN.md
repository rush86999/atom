---
phase: 212-80pct-coverage-clean-slate
plan: WAVE1B
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_byok_handler.py
  - backend/tests/test_cognitive_tier_system.py
  - backend/tests/test_episode_segmentation_service.py
  - backend/tests/test_episode_retrieval_service.py
autonomous: true

must_haves:
  truths:
    - "llm/byok_handler.py achieves 80%+ line coverage (multi-provider routing tested)"
    - "llm/cognitive_tier_system.py achieves 80%+ line coverage (tier classification tested)"
    - "episode_segmentation_service.py achieves 80%+ line coverage (segmentation logic tested)"
    - "episode_retrieval_service.py achieves 80%+ line coverage (retrieval modes tested)"
    - "Backend overall coverage increases from 15% to 25%+"
    - "All new tests pass with pytest"
  artifacts:
    - path: "backend/tests/test_byok_handler.py"
      provides: "Unit tests for BYOKHandler"
      min_lines: 450
      exports: ["TestBYOKHandler", "TestProviderRouting", "TestTokenStreaming"]
    - path: "backend/tests/test_cognitive_tier_system.py"
      provides: "Unit tests for CognitiveTierSystem"
      min_lines: 400
      exports: ["TestCognitiveClassifier", "TestCacheAwareRouter", "TestEscalationManager"]
    - path: "backend/tests/test_episode_segmentation_service.py"
      provides: "Unit tests for EpisodeSegmentationService"
      min_lines: 350
      exports: ["TestEpisodeSegmentation", "TestSegmentCreation", "TestTimeGaps"]
    - path: "backend/tests/test_episode_retrieval_service.py"
      provides: "Unit tests for EpisodeRetrievalService"
      min_lines: 400
      exports: ["TestEpisodeRetrieval", "TestTemporalRetrieval", "TestSemanticRetrieval"]
  key_links:
    - from: "backend/tests/test_byok_handler.py"
      to: "backend/core/llm/byok_handler.py"
      via: "Direct imports and mock LLM providers"
      pattern: "from core.llm.byok_handler import"
    - from: "backend/tests/test_cognitive_tier_system.py"
      to: "backend/core/llm/cognitive_tier_system.py"
      via: "Direct imports and mock LLM providers"
      pattern: "from core.llm.cognitive_tier_system import"
    - from: "backend/tests/test_episode_segmentation_service.py"
      to: "backend/core/episode_segmentation_service.py"
      via: "Direct imports and mock database sessions"
      pattern: "from core.episode_segmentation_service import"
    - from: "backend/tests/test_episode_retrieval_service.py"
      to: "backend/core/episode_retrieval_service.py"
      via: "Direct imports and mock LanceDB"
      pattern: "from core.episode_retrieval_service import"
---

<objective>
Achieve 25%+ backend coverage by testing 4 LLM and episode services: byok_handler, cognitive_tier_system, episode_segmentation_service, and episode_retrieval_service.

Purpose: These modules handle multi-provider LLM routing, cognitive tier classification, and episodic memory operations. High coverage ensures reliable AI operations and memory management.

Output: Four test files with 1,600+ total lines, achieving 80%+ coverage on each target module, bringing overall backend coverage to 25%+.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/llm/byok_handler.py
@backend/core/llm/cognitive_tier_system.py
@backend/core/episode_segmentation_service.py
@backend/core/episode_retrieval_service.py

# Test Pattern Reference
From Phase 216: Use AsyncMock for async methods, patch services at import location, mock database sessions with SessionLocal fixtures.

# Target Files Analysis

## 1. llm/byok_handler.py (~400 lines)
Key methods:
- route_to_provider(): Provider selection by cognitive tier
- stream_completion(): Token streaming
- handle_provider_failure(): Fallback logic
- estimate_tokens(): Token estimation
- get_provider_status(): Provider health checks

Providers: OpenAI, Anthropic, DeepSeek, Gemini, MiniMax

## 2. llm/cognitive_tier_system.py (~300 lines)
Classes:
- CognitiveClassifier: Token/complexity classification
- CacheAwareRouter: Prompt caching awareness
- EscalationManager: Quality-based tier escalation

Tiers: Micro, Standard, Versatile, Heavy, Complex

## 3. episode_segmentation_service.py (~250 lines)
Key methods:
- create_segment(): Create episode segment
- detect_segment_boundary(): Time gap/topic change detection
- merge_segments(): Segment consolidation
- get_active_segment(): Active segment retrieval

## 4. episode_retrieval_service.py (~300 lines)
Key methods:
- retrieve_temporal(): Time-based retrieval
- retrieve_semantic(): Vector search retrieval
- retrieve_sequential(): Full episode retrieval
- retrieve_contextual(): Hybrid retrieval
- weight_by_feedback(): Feedback-weighted results

# Test Infrastructure Requirements
- Mock database sessions (SQLAlchemy)
- Mock LLM providers (OpenAI, Anthropic, etc.)
- Mock vector database (LanceDB)
- AsyncMock for async methods
- Parametrize for multiple providers/maturity levels
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for byok_handler</name>
  <files>backend/tests/test_byok_handler.py</files>
  <action>
Create backend/tests/test_byok_handler.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.llm.byok_handler import BYOKHandler

2. Fixtures:
   - mock_handler(): Returns BYOKHandler with mocked providers
   - mock_openai(): Mock OpenAI client
   - mock_anthropic(): Mock Anthropic client
   - sample_prompt(): Returns test prompt

3. Class TestProviderRouting:
   - test_route_to_openai(): Routes Micro tier to OpenAI GPT-4o-mini
   - test_route_to_anthropic(): Routes Standard tier to Claude Sonnet
   - test_route_to_deepseek(): Routes Versatile tier to DeepSeek
   - test_route_to_gemini(): Routes Heavy tier to Gemini Pro
   - test_route_to_minimax(): Routes Complex tier to MiniMax M2.5

4. Class TestTokenStreaming:
   - test_stream_openai(): Streams tokens from OpenAI
   - test_stream_anthropic(): Streams tokens from Anthropic
   - test_stream_handles_errors(): Graceful error handling
   - test_stream_timeout(): Handles timeout
   - test_stream_empty_response(): Handles empty stream

5. Class TestProviderFailure:
   - test_fallback_on_primary_failure(): Falls back to secondary provider
   - test_fallback_exhaustion(): Raises error when all fail
   - test_retry_on_transient_error(): Retries on 5xx errors
   - test_no_retry_on_auth_error(): No retry on 401/403

6. Class TestTokenEstimation:
   - test_estimate_tokens_simple(): Estimates simple prompts
   - test_estimate_tokens_with_system(): Includes system prompt
   - test_estimate_tokens_with_history(): Includes conversation history
   - test_estimate_tokens_accuracy(): Within 10% of actual

7. Class TestProviderStatus:
   - test_get_all_provider_status(): Returns status for all providers
   - test_healthy_provider(): Returns True for healthy
   - test_unhealthy_provider(): Returns False for unhealthy
   - test_provider_health_check(): Performs active health check

8. Use parametrize for all providers and tiers
  </action>
  <verify>
pytest backend/tests/test_byok_handler.py -v
pytest backend/tests/test_byok_handler.py --cov=core.llm.byok_handler --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All byok_handler tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for cognitive_tier_system</name>
  <files>backend/tests/test_cognitive_tier_system.py</files>
  <action>
Create backend/tests/test_cognitive_tier_system.py with comprehensive tests:

1. Imports: pytest, from core.llm.cognitive_tier_system import CognitiveClassifier, CacheAwareRouter, EscalationManager

2. Fixtures:
   - mock_classifier(): Returns CognitiveClassifier
   - mock_router(): Returns CacheAwareRouter
   - mock_escalation(): Returns EscalationManager

3. Class TestCognitiveClassifier:
   - test_classify_micro(): Classifies <500 token simple prompts
   - test_classify_standard(): Classifies 500-2000 token prompts
   - test_classify_versatile(): Classifies complex multi-part prompts
   - test_classify_heavy(): Classifies code generation tasks
   - test_classify_complex(): Classifies >4000 token semantic tasks
   - test_classification_consistent(): Same prompt classifies to same tier

4. Class TestCacheAwareRouter:
   - test_cache_hit(): Uses cached tier for known prompts
   - test_cache_miss(): Classifies new prompts
   - test_cache_key_generation(): Creates consistent cache keys
   - test_cache_hit_cost_reduction(): Verifies 90%+ cost reduction

5. Class TestEscalationManager:
   - test_escalate_on_quality_threshold(): Escalates on low quality
   - test_escalation_cooldown(): Respects 5-min cooldown
   - test_escalation_history_tracking(): Tracks escalation history
   - test_escalation_not_repeated(): Avoids repeated escalation

6. Class TestTierComparison:
   - test_compare_tiers_all(): Returns correct ordering
   - test_estimate_cost_accuracy(): Within 10% of actual
   - test_get_recommended_tier(): Recommends based on task type

7. Use parametrize for tier classification examples
  </action>
  <verify>
pytest backend/tests/test_cognitive_tier_system.py -v
pytest backend/tests/test_cognitive_tier_system.py --cov=core.llm.cognitive_tier_system --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All cognitive_tier_system tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests for episode_segmentation_service</name>
  <files>backend/tests/test_episode_segmentation_service.py</files>
  <action>
Create backend/tests/test_episode_segmentation_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.episode_segmentation_service import EpisodeSegmentationService

2. Fixtures:
   - mock_service(): Returns EpisodeSegmentationService
   - mock_db(): Mock database session
   - sample_segment(): Returns test EpisodeSegment

3. Class TestSegmentCreation:
   - test_create_segment(): Creates new segment
   - test_create_segment_with_context(): Includes input/output context
   - test_create_segment_links_to_episode(): Links to parent episode
   - test_create_segment_auto_detect_type(): Detects segment type

4. Class TestTimeGapDetection:
   - test_detect_gap_large_time(): Detects gap >30 minutes
   - test_detect_gap_medium_time(): Detects gap >10 minutes
   - test_no_gap_small_time(): No gap for <10 minutes
   - test_detect_gap_across_hour(): Handles hour boundaries

5. Class TestTopicChangeDetection:
   - test_detect_topic_change(): Detects topic shift
   - test_no_topic_change_same(): No change for same topic
   - test_topic_change_threshold(): Uses 0.7 similarity threshold

6. Class TestSegmentMerging:
   - test_merge_adjacent_segments(): Merges consecutive segments
   - test_merge_preserves_context(): Preserves all context
   - test_merge_updates_timestamps(): Updates timestamps correctly
   - test_no_merge_different_episodes(): Rejects cross-episode merge

7. Class TestActiveSegment:
   - test_get_active_segment(): Returns currently active segment
   - test_no_active_segment_returns_none(): Returns None when no active
   - test_close_segment(): Marks segment as closed
   - test_reopen_segment(): Reopens closed segment

8. Use parametrize for time gaps and topic changes
  </action>
  <verify>
pytest backend/tests/test_episode_segmentation_service.py -v
pytest backend/tests/test_episode_segmentation_service.py --cov=core.episode_segmentation_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All episode_segmentation_service tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 4: Create tests for episode_retrieval_service</name>
  <files>backend/tests/test_episode_retrieval_service.py</files>
  <action>
Create backend/tests/test_episode_retrieval_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.episode_retrieval_service import EpisodeRetrievalService

2. Fixtures:
   - mock_service(): Returns EpisodeRetrievalService
   - mock_lancedb(): Mock LanceDB client
   - sample_episodes(): Returns list of test episodes

3. Class TestTemporalRetrieval:
   - test_retrieve_by_date_range(): Returns episodes in date range
   - test_retrieve_recent(): Returns most recent N episodes
   - test_retrieve_by_agent(): Filters by agent_id
   - test_retrieve_empty_result(): Handles empty results
   - test_retrieve_ordering(): Returns in chronological order

4. Class TestSemanticRetrieval:
   - test_retrieve_by_embedding(): Vector similarity search
   - test_semantic_threshold(): Filters by similarity threshold
   - test_semantic_top_k(): Returns top K results
   - test_semantic_with_filters(): Combines vector search with filters

5. Class TestSequentialRetrieval:
   - test_retrieve_full_episode(): Returns complete episode
   - test_retrieve_with_segments(): Includes all segments
   - test_retrieve_ordered_segments(): Segments in order

6. Class TestContextualRetrieval:
   - test_hybrid_temporal_semantic(): Combines time + vector
   - test_hybrid_weights(): Applies temporal/semantic weights
   - test_hybrid_reranks(): Reranks combined results

7. Class TestFeedbackWeighting:
   - test_positive_feedback_boost(): +0.2 boost for positive
   - test_negative_feedback_penalty(): -0.3 penalty for negative
   - test_no_feedback_no_change(): No adjustment for no feedback
   - test_feedback_aggregation(): Aggregates multiple feedback

8. Use parametrize for retrieval modes and thresholds
  </action>
  <verify>
pytest backend/tests/test_episode_retrieval_service.py -v
pytest backend/tests/test_episode_retrieval_service.py --cov=core.episode_retrieval_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All episode_retrieval_service tests passing, 80%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all new tests:
   pytest backend/tests/test_byok_handler.py \
          backend/tests/test_cognitive_tier_system.py \
          backend/tests/test_episode_segmentation_service.py \
          backend/tests/test_episode_retrieval_service.py -v

2. Verify coverage per module (all should be 80%+):
   pytest backend/tests/ --cov=core.llm.byok_handler \
                         --cov=core.llm.cognitive_tier_system \
                         --cov=core.episode_segmentation_service \
                         --cov=core.episode_retrieval_service \
                         --cov-report=term-missing

3. Verify overall backend coverage increase:
   pytest backend/tests/ --cov=core --cov=api --cov=tools --cov-report=json
   # Backend should be 25%+ (from 15% baseline after Wave 1A)

4. Verify no regression in existing tests:
   pytest backend/tests/ -v
</verification>

<success_criteria>
1. All 4 test files pass (100% pass rate)
2. Each of 4 modules achieves 80%+ coverage
3. Backend overall coverage >= 25%
4. No regression in existing test coverage
5. All tests execute in <60 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE1B-SUMMARY.md`
</output>
