---
phase: 08-80-percent-coverage-push
plan: 04
type: execute
wave: 2
depends_on:
  - 08-80-percent-coverage-01
files_modified:
  - backend/tests/unit/test_episode_segmentation_service.py
  - backend/tests/unit/test_episode_retrieval_service.py
  - backend/tests/unit/test_episode_lifecycle_service.py
autonomous: true

must_haves:
  truths:
    - "Episode creation and segmentation logic is tested"
    - "Vector search and retrieval accuracy are verified"
    - "Episode lifecycle management (decay, consolidation) is covered"
    - "LanceDB and PostgreSQL integration points are tested"
  artifacts:
    - path: "backend/tests/unit/test_episode_segmentation_service.py"
      provides: "Tests for episode segmentation algorithms"
      min_lines: 300
    - path: "backend/tests/unit/test_episode_retrieval_service.py"
      provides: "Tests for episode retrieval and vector search"
      min_lines: 350
    - path: "backend/tests/unit/test_episode_lifecycle_service.py"
      provides: "Tests for episode lifecycle management"
      min_lines: 250
  key_links:
    - from: "backend/tests/unit/test_episode_segmentation_service.py"
      to: "backend/core/episode_segmentation_service.py"
      via: "import segmentation service classes"
      pattern: "from core.episode_segmentation_service import"
    - from: "backend/tests/unit/test_episode_retrieval_service.py"
      to: "backend/core/episode_retrieval_service.py"
      via: "import retrieval service classes"
      pattern: "from core.episode_retrieval_service import"
    - from: "backend/tests/unit"
      to: "backend/tests/factories/episode_factory.py"
      via: "use episode factories for test data"
      pattern: "from tests.factories.episode_factory import"
---

<objective>
Create comprehensive tests for the episodic memory system services, covering episode creation and segmentation, vector-based retrieval with LanceDB, lifecycle management (decay, consolidation, archival), and PostgreSQL operations.

Purpose: Ensure reliable episodic memory functionality which enables agents to learn from past experiences and recall relevant context for improved decision-making.
Output: Test suites for three episodic memory services achieving 80%+ coverage
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@backend/tests/coverage_reports/COVERAGE_PRIORITY_ANALYSIS.md
@backend/tests/conftest.py
@backend/tests/factories/episode_factory.py
@backend/core/episode_segmentation_service.py
@backend/core/episode_retrieval_service.py
@backend/core/episode_lifecycle_service.py
@backend/core/models.py
@backend/tests/property_tests/test_episode_integration.py
</context>

<tasks>

<task type="auto">
  <name>Create episode segmentation service tests</name>
  <files>backend/tests/unit/test_episode_segmentation_service.py</files>
  <action>
    Create backend/tests/unit/test_episode_segmentation_service.py:

    Test EpisodeSegmentationService:
    1. test_segmentation_service_init() - service initialization
    2. test_create_episode() - new episode creation
    3. test_detect_segment_boundary_time_gap() - time gap triggers segmentation
    4. test_detect_segment_boundary_topic_change() - topic change triggers segmentation
    5. test_detect_segment_boundary_task_completion() - task completion triggers segmentation
    6. test_add_segment_to_episode() - segment addition
    7. test_finalize_episode() - episode finalization
    8. test_merge_short_episodes() - merge episodes below threshold
    9. test_split_long_episodes() - split episodes above threshold
    10. test_extract_episode_summary() - summary generation

    Mock database session and LanceDB client:
    ```python
    @pytest.fixture
    def mock_lancedb():
        with patch('core.episode_segmentation_service.lancedb') as mock:
            yield mock

    @pytest.fixture
    def mock_db():
        db = Mock(spec=Session)
        return db
    ```

    Test segmentation algorithms:
    - Time gap: detect pauses > N minutes
    - Topic change: detect semantic shifts using embeddings
    - Task completion: detect when agent completes a goal

    Use EpisodeFactory from factories for test data.
  </action>
  <verify>pytest backend/tests/unit/test_episode_segmentation_service.py -v</verify>
  <done>All segmentation tests pass (10+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create episode retrieval service tests</name>
  <files>backend/tests/unit/test_episode_retrieval_service.py</files>
  <action>
    Create backend/tests/unit/test_episode_retrieval_service.py:

    Test EpisodeRetrievalService:
    1. test_retrieval_service_init() - service initialization
    2. test_temporal_retrieval() - time-based retrieval
    3. test_semantic_retrieval() - vector similarity search
    4. test_sequential_retrieval() - full episode retrieval
    5. test_contextual_retrieval() - hybrid retrieval
    6. test_retrieve_by_canvas_type() - canvas-filtered retrieval
    7. test_retrieve_by_feedback_score() - feedback-weighted retrieval
    8. test_retrieve_with_limit() - result limiting
    9. test_retrieve_with_filters() - metadata filtering
    10. test_boost_positive_feedback() - +0.2 boost for positive feedback
    11. test_penalty_negative_feedback() - -0.3 penalty for negative feedback
    12. test_include_canvas_context() - canvas context in results

    Mock LanceDB vector search:
    ```python
    @pytest.fixture
    def mock_vector_search():
        with patch('core.episode_retrieval_service.lancedb') as mock:
            mock.connect().table().search().return_value = [
                {"episode_id": "ep1", "score": 0.95},
                {"episode_id": "ep2", "score": 0.87}
            ]
            yield mock
    ```

    Test retrieval modes:
    - Temporal: episodes within time range
    - Semantic: vector similarity with cosine distance
    - Sequential: complete episodes in order
    - Contextual: combined semantic + temporal

    Test canvas/feedback integration:
    - Canvas type filtering (docs, sheets, forms, etc.)
    - Feedback score weighting
    - Context enrichment
  </action>
  <verify>pytest backend/tests/unit/test_episode_retrieval_service.py -v</verify>
  <done>All retrieval tests pass (12+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create episode lifecycle service tests</name>
  <files>backend/tests/unit/test_episode_lifecycle_service.py</files>
  <action>
    Create backend/tests/unit/test_episode_lifecycle_service.py:

    Test EpisodeLifecycleService:
    1. test_lifecycle_service_init() - service initialization
    2. test_mark_episode_for_decay() - mark for decay
    3. test_decay_episode() - reduce episode weight
    4. test_consolidate_episodes() - merge related episodes
    5. test_archive_episode() - move to cold storage
    6. test_unarchive_episode() - restore from cold storage
    7. test_get_decay_status() - check decay state
    8. test_calculate_access_frequency() - frequency calculation
    9. test_promote_hot_episode() - move to hot storage
    10. test_cleanup_archived_episodes() - delete old archives

    Mock storage operations:
    - PostgreSQL for hot storage
    - LanceDB for cold storage
    - File system for archival

    Test lifecycle transitions:
    - Active -> Decaying -> Archived
    - Archived -> Active (on access)
    - Consolidation of multiple episodes

    Test retention policies:
    - Age-based archival
    - Access-frequency tracking
    - Storage limits
  </action>
  <verify>pytest backend/tests/unit/test_episode_lifecycle_service.py -v</verify>
  <done>All lifecycle tests pass (10+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create LanceDB integration tests for episodic memory</name>
  <files>backend/tests/unit/test_episode_segmentation_service.py backend/tests/unit/test_episode_retrieval_service.py</files>
  <action>
    Add LanceDB integration tests to both service test files:

    Test LanceDB operations:
    1. test_lancedb_connection() - database connection
    2. test_create_episode_table() - table creation
    3. test_insert_episode_vector() - vector insertion
    4. test_vector_search() - similarity search
    5. test_batch_insert() - bulk insertion
    6. test_update_vector() - vector update
    7. test_delete_vector() - vector deletion
    8. test_table_indexes() - index management

    Mock LanceDB client appropriately:
    ```python
    @pytest.fixture
    def mock_lancedb_client():
        client = Mock()
        table = Mock()
        client.open_table.return_value = table
        client.create_table.return_value = table
        table.add.return_value = None
        table.search.return_value = Mock()
        return client
    ```

    Test vector operations:
    - Embedding generation for semantic search
    - Cosine similarity calculations
    - Batch operations for performance
    - Error handling for connection issues
  </action>
  <verify>pytest backend/tests/unit/test_episode_*_service.py -v -k "lancedb"</verify>
  <done>All LanceDB integration tests pass (8+ tests)</done>
</task>

<task type="auto">
  <name>Create episode access log and audit tests</name>
  <files>backend/tests/unit/test_episode_lifecycle_service.py</files>
  <action>
    Add audit logging tests to test_episode_lifecycle_service.py:

    Test EpisodeAccessLog:
    1. test_log_access() - record episode access
    2. test_get_access_history() - retrieve access log
    3. test_access_count_tracking() - count accesses
    4. test_last_access_tracking() - track last access time
    5. test_audit_trail_integrity() - verify audit completeness

    Test access logging for:
    - Retrieval operations
    - Update operations
    - Lifecycle transitions (archive/restore)
    - Consolidation operations

    Verify audit entries include:
    - episode_id
    - user_id
    - action_type
    - timestamp
    - metadata

    Use EpisodeFactory and EpisodeAccessLog from models.
  </action>
  <verify>pytest backend/tests/unit/test_episode_lifecycle_service.py -v -k "access"</verify>
  <done>All access log tests pass (5+ tests)</done>
</task>

<task type="auto">
  <name>Create canvas-aware episode tests</name>
  <files>backend/tests/unit/test_episode_segmentation_service.py backend/tests/unit/test_episode_retrieval_service.py</files>
  <action>
    Add canvas integration tests to both service files:

    Test canvas-aware episodes:
    1. test_track_canvas_presentation() - track canvas in episode
    2. test_track_canvas_action() - track user action on canvas
    3. test_filter_by_canvas_type() - filter retrieval by type
    4. test_filter_by_canvas_action() - filter by action (present/submit/close)
    5. test_canvas_context_inclusion() - include canvas in episode context
    6. test_multiple_canvas_tracking() - track multiple canvases in episode

    Test canvas types:
    - generic
    - docs
    - email
    - sheets
    - orchestration
    - terminal
    - coding

    Test canvas actions:
    - present
    - submit
    - close
    - update
    - execute

    Verify CanvasAudit linkage:
    - Lightweight references (canvas_audit_id)
    - No duplicate data storage
    - Efficient join queries
  </action>
  <verify>pytest backend/tests/unit/test_episode_*_service.py -v -k "canvas"</verify>
  <done>All canvas-aware tests pass (6+ tests)</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/unit/test_episode_segmentation_service.py -v to verify segmentation tests pass
2. Run pytest backend/tests/unit/test_episode_retrieval_service.py -v to verify retrieval tests pass
3. Run pytest backend/tests/unit/test_episode_lifecycle_service.py -v to verify lifecycle tests pass
4. Run pytest --cov=backend/core/episode_segmentation_service backend/tests/unit/test_episode_segmentation_service.py to verify coverage
5. Check coverage.json shows 50%+ coverage for all three episode services
6. Verify LanceDB mocking is comprehensive (no actual database operations)
</verification>

<success_criteria>
- test_episode_segmentation_service.py created with 15+ tests
- test_episode_retrieval_service.py created with 15+ tests
- test_episode_lifecycle_service.py created with 15+ tests
- 50%+ coverage on all three episode service files
- Canvas-aware episode testing included
- Feedback-linked episode testing included
- LanceDB integration points tested
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-04-SUMMARY.md`
</output>
