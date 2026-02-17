---
phase: 03-memory-layer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/property_tests/episodes/test_episode_segmentation_invariants.py
  - tests/property_tests/episodes/test_episode_retrieval_invariants.py
  - tests/property_tests/episodes/test_agent_graduation_invariants.py
  - tests/unit/episodes/test_episode_segmentation_service.py
  - tests/unit/episodes/test_episode_retrieval_service.py
  - tests/unit/episodes/test_episode_lifecycle_service.py
autonomous: true

must_haves:
  truths:
    - "All episodic memory retrieval modes return no duplicate episodes"
    - "Temporal retrieval results are sorted by time (newest first)"
    - "Semantic retrieval results are ranked by similarity (descending)"
    - "Time-gap segmentation triggers new episodes when threshold exceeded"
    - "Topic change detection creates segments when similarity < threshold"
    - "Task completion markers create episode boundaries"
    - "Graduation readiness scores are in valid range [0, 100]"
    - "Episode decay scores decrease over time without access"
    - "Retrieval performance meets SLA (<100ms for semantic search)"
  artifacts:
    - path: "tests/property_tests/episodes/test_episode_retrieval_invariants.py"
      provides: "Property tests for retrieval invariants (temporal, semantic, sequential)"
      min_lines: 1000
    - path: "tests/property_tests/episodes/test_episode_segmentation_invariants.py"
      provides: "Property tests for segmentation invariants (time gaps, topic changes)"
      min_lines: 800
    - path: "tests/property_tests/episodes/test_agent_graduation_invariants.py"
      provides: "Property tests for graduation invariants (readiness scores, criteria)"
      min_lines: 750
    - path: "tests/unit/episodes/test_episode_lifecycle_service.py"
      provides: "Unit tests for decay, consolidation, archival"
      min_lines: 600
  key_links:
    - from: "tests/property_tests/episodes/test_episode_retrieval_invariants.py"
      to: "core/episode_retrieval_service.py"
      via: "imports EpisodeRetrievalService"
      pattern: "from core.episode_retrieval_service import"
    - from: "tests/property_tests/episodes/test_episode_segmentation_invariants.py"
      to: "core/episode_segmentation_service.py"
      via: "imports EpisodeSegmentationService"
      pattern: "from core.episode_segmentation_service import"
    - from: "tests/property_tests/episodes/test_agent_graduation_invariants.py"
      to: "core/agent_graduation_service.py"
      via: "imports AgentGraduationService"
      pattern: "from core.agent_graduation_service import"
---

<objective>
Verify episodic memory test coverage meets all critical invariants (AR-06, AR-12).

Purpose: Ensure existing property-based tests cover all episodic memory segmentation, retrieval, lifecycle, and graduation scenarios with no gaps in critical path validation.

Output: Verified test coverage report with any gaps filled.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md

# Implementation files under test
@/Users/rushiparikh/projects/atom/backend/core/episode_segmentation_service.py
@/Users/rushiparikh/projects/atom/backend/core/episode_retrieval_service.py
@/Users/rushiparikh/projects/atom/backend/core/episode_lifecycle_service.py
@/Users/rushiparikh/projects/atom/backend/core/agent_graduation_service.py

# Existing property tests
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/episodes/test_agent_graduation_invariants.py
</context>

<tasks>

<task type="auto">
  <name>Verify Segmentation Coverage</name>
  <files>tests/property_tests/episodes/test_episode_segmentation_invariants.py</files>
  <action>
    Verify segmentation property tests cover:
    1. Time-gap detection (TIME_GAP_THRESHOLD_MINUTES = 30)
    2. Topic change detection (SEMANTIC_SIMILARITY_THRESHOLD = 0.75)
    3. Task completion markers
    4. Boundary consistency (disjoint, chronological)
    5. Canvas-aware segmentation tracking
    6. Feedback-linked segmentation

    Check existing test classes:
    - TestTimeGapSegmentationInvariants
    - TestTopicChangeSegmentationInvariants
    - TestTaskCompletionSegmentationInvariants
    - TestSegmentBoundaryInvariants
    - TestCanvasAwareRetrievalInvariants (contextual)
    - TestFeedbackLinkedRetrievalInvariants (contextual)

    Run segmentation tests: pytest tests/property_tests/episodes/test_episode_segmentation_invariants.py -v
  </action>
  <verify>
    pytest tests/property_tests/episodes/test_episode_segmentation_invariants.py -v --tb=short | head -100
  </verify>
  <done>
    All segmentation invariants have property tests with max_examples >= 50 for critical invariants.
    Tests verify time-gap (>30min), topic change (<0.75 similarity), task completion boundaries.
  </done>
</task>

<task type="auto">
  <name>Verify Retrieval Coverage</name>
  <files>tests/property_tests/episodes/test_episode_retrieval_invariants.py</files>
  <action>
    Verify retrieval property tests cover AR-12 requirements:
    1. No duplicates in retrieval results
    2. Temporal queries sorted by time (newest first)
    3. Semantic results ranked by similarity (descending)
    4. Sequential retrieval includes all segments
    5. Contextual hybrid scoring (temporal + semantic)
    6. Performance validation (<100ms for semantic search)

    Check existing test classes:
    - TestTemporalRetrievalInvariants (time filtering, limits, ordering)
    - TestSemanticRetrievalInvariants (similarity bounds, ranking)
    - TestSequentialRetrievalInvariants (segments included, ordering)
    - TestContextualRetrievalInvariants (hybrid scoring, feedback boosting)
    - TestEpisodeFilteringInvariants (status, user filters)
    - TestEpisodePaginationInvariants (page counts, offsets)
    - TestEpisodeIntegrityInvariants (boundaries, time ordering)

    Run retrieval tests: pytest tests/property_tests/episodes/test_episode_retrieval_invariants.py -v
  </action>
  <verify>
    pytest tests/property_tests/episodes/test_episode_retrieval_invariants.py -v --tb=short | head -100
  </verify>
  <done>
    All retrieval invariants have property tests with max_examples >= 50.
    Tests verify no duplicates, temporal sorting, semantic ranking, pagination bounds.
  </done>
</task>

<task type="auto">
  <name>Verify Graduation Coverage</name>
  <files>tests/property_tests/episodes/test_agent_graduation_invariants.py</files>
  <action>
    Verify graduation property tests cover:
    1. Episode count requirements (INTERN: 10, SUPERVISED: 25, AUTONOMOUS: 50)
    2. Intervention rate thresholds (INTERN: 50%, SUPERVISED: 20%, AUTONOMOUS: 0%)
    3. Constitutional score thresholds (INTERN: 0.70, SUPERVISED: 0.85, AUTONOMOUS: 0.95)
    4. Readiness score bounds [0, 100]
    5. Maturity transition validation
    6. Supervision metrics integration

    Check existing test classes:
    - TestGraduationCriteriaInvariants
    - TestReadinessScoreInvariants
    - TestMaturityTransitionInvariants (if exists)

    Run graduation tests: pytest tests/property_tests/episodes/test_agent_graduation_invariants.py -v
  </action>
  <verify>
    pytest tests/property_tests/episodes/test_agent_graduation_invariants.py -v --tb=short | head -100
  </verify>
  <done>
    All graduation invariants have property tests with max_examples >= 200 for critical invariants.
    Tests verify episode counts, intervention rates, constitutional scores, readiness bounds.
  </done>
</task>

<task type="auto">
  <name>Verify Lifecycle Coverage</name>
  <files>tests/unit/episodes/test_episode_lifecycle_service.py</files>
  <action>
    Verify lifecycle tests cover:
    1. Episode decay (90-day threshold, 180-day archival)
    2. Consolidation (similarity-based merging)
    3. Archival to cold storage (LanceDB)
    4. Importance score updates based on feedback

    Check existing test functions in test_episode_lifecycle_service.py:
    - Test decay_old_episodes
    - Test consolidate_similar_episodes
    - Test archive_to_cold_storage
    - Test update_importance_scores
    - Test batch_update_access_counts

    Run lifecycle tests: pytest tests/unit/episodes/test_episode_lifecycle_service.py -v
  </action>
  <verify>
    pytest tests/unit/episodes/test_episode_lifecycle_service.py -v --tb=short | head -50
  </verify>
  <done>
    Lifecycle service tests cover decay, consolidation, archival, and importance updates.
  </done>
</task>

<task type="auto">
  <name>Verify Performance SLA Tests</name>
  <files>tests/test_episode_performance.py</files>
  <action>
    Verify performance tests exist for:
    1. Episode creation performance (<5s)
    2. Temporal retrieval (<10ms)
    3. Semantic retrieval (<100ms)
    4. Sequential retrieval (<50ms)

    Check existing test class: TestEpisodePerformance

    Run performance tests: pytest tests/test_episode_performance.py -v
  </action>
  <verify>
    pytest tests/test_episode_performance.py -v --tb=short
  </verify>
  <done>
    Performance tests verify SLA compliance: episode creation <5s, temporal <10ms, semantic <100ms.
  </done>
</task>

<task type="auto">
  <name>Run Full Episodic Memory Test Suite</name>
  <files>tests/property_tests/episodes/, tests/unit/episodes/, tests/integration/episodes/</files>
  <action>
    Run all episodic memory tests to verify coverage and identify any gaps:

    1. Property tests: pytest tests/property_tests/episodes/ -v
    2. Unit tests: pytest tests/unit/episodes/ -v
    3. Integration tests: pytest tests/integration/episodes/ -v
    4. Performance tests: pytest tests/test_episode_performance.py -v

    Check for any failing tests or coverage gaps.
  </action>
  <verify>
    pytest tests/property_tests/episodes/ tests/unit/episodes/ tests/integration/episodes/ tests/test_episode_performance.py -v --tb=line | tail -50
  </verify>
  <done>
    All episodic memory tests pass (target: 95%+ pass rate).
    Coverage report shows all critical paths tested.
  </done>
</task>

</tasks>

<verification>
## Phase Verification

1. Review all episodic memory test results
2. Confirm property tests cover AR-12 requirements (no duplicates, sorted, ranked)
3. Verify segmentation tests cover time-gap, topic change, task completion
4. Verify retrieval tests cover temporal, semantic, sequential, contextual modes
5. Verify graduation tests cover readiness scores, constitutional compliance
6. Verify lifecycle tests cover decay, consolidation, archival
7. Generate coverage report for episodic memory module
</verification>

<success_criteria>
1. All episodic memory property tests pass (max_examples >= 50 for critical invariants)
2. AR-12 requirements verified: no duplicates, temporal sorted, semantic ranked
3. Segmentation coverage: time-gap (>30min), topic change (<0.75), task completion
4. Retrieval coverage: all 4 modes (temporal, semantic, sequential, contextual)
5. Graduation coverage: episode counts, intervention rates, constitutional scores
6. Lifecycle coverage: decay, consolidation, archival
7. Performance SLAs verified: <5s creation, <10ms temporal, <100ms semantic
</success_criteria>

<output>
After completion, create `.planning/phases/03-memory-layer/03-memory-layer-01-SUMMARY.md`
</output>
