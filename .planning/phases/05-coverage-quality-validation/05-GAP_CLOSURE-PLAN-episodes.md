---
phase: 05-coverage-quality-validation
plan: GAP_CLOSURE-03
subsystem: episodic-memory-testing
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/integration/episodes/test_lancedb_integration.py
  - backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py
  - backend/tests/integration/episodes/test_graduation_validation.py
  - backend/tests/unit/episodes/test_episode_segmentation_service.py
  - backend/tests/unit/episodes/test_episode_lifecycle_service.py
  - backend/tests/unit/episodes/test_agent_graduation_service.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Episodic memory domain achieves 80% coverage (all services >80%)"
    - "LanceDB vector search and embedding generation tests pass"
    - "Episode decay/consolidation/archival tests with actual LanceDB operations pass"
    - "Graduation exam execution and constitutional validation tests pass"
  artifacts:
    - path: "backend/tests/integration/episodes/test_lancedb_integration.py"
      provides: "LanceDB vector search and embedding tests"
      min_lines: 250
    - path: "backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py"
      provides: "LanceDB operations for decay/consolidation/archival"
      min_lines: 200
    - path: "backend/tests/integration/episodes/test_graduation_validation.py"
      provides: "Graduation exam and constitutional validation tests"
      min_lines: 200
    - path: "backend/tests/unit/episodes/test_episode_segmentation_service.py"
      provides: "Enhanced segmentation tests >80% coverage"
      min_tests: 25
    - path: "backend/tests/unit/episodes/test_episode_lifecycle_service.py"
      provides: "Enhanced lifecycle tests >80% coverage"
      min_tests: 20
  key_links:
    - from: "backend/tests/integration/episodes/test_lancedb_integration.py"
      to: "backend/core/episode_retrieval_service.py"
      via: "actual LanceDB client connection"
      pattern: "lancedb\\.connect|vector_search"
    - from: "backend/tests/integration/episodes/test_graduation_validation.py"
      to: "backend/core/agent_graduation_service.py"
      via: "SandboxExecutor integration"
      pattern: "graduation_exam|constitutional_validation"
---

<objective>
Add LanceDB integration tests and enhance unit tests to achieve 80% coverage for the episodic memory domain.

**Purpose:** Episodic memory domain currently has weighted average ~40% coverage. EpisodeSegmentationService at 27%, EpisodeRetrievalService at 65%, EpisodeLifecycleService at 53%, and AgentGraduationService at 42%. The main gaps are LanceDB integration paths (vector search, embedding generation, consolidation) and graduation exam execution with constitutional validation.

**Output:** New integration test suite for LanceDB operations, enhanced unit tests for segmentation and lifecycle, and graduation validation tests to bring all services to 80%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/phases/05-coverage-quality-validation/05-03-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-VERIFICATION.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@backend/core/episode_segmentation_service.py
@backend/core/episode_retrieval_service.py
@backend/core/episode_lifecycle_service.py
@backend/core/agent_graduation_service.py
@backend/tests/unit/episodes/
@backend/tests/property_tests/database/test_episode_invariants.py
</context>

<tasks>

<task type="auto">
  <name>Add LanceDB integration tests for vector search and embedding generation</name>
  <files>backend/tests/integration/episodes/test_lancedb_integration.py</files>
  <action>
    Create a new integration test file for testing LanceDB vector search and embedding generation.

    The file should test:
    1. LanceDB client connection and table creation
    2. Vector embedding generation for episode content
    3. Semantic search with cosine similarity
    4. Hybrid search (temporal + semantic)
    5. Batch embedding operations
    6. Query performance and result ranking

    Use the existing property test patterns from tests/property_tests/database/test_episode_invariants.py as reference for LanceDB setup.

    Mock external dependencies (OpenAI/embedding API) but use real LanceDB in-memory or test database.

    File structure:
    - Import necessary modules from core.episode_retrieval_service
    - Create a TestLanceDBIntegration class
    - Use pytest.mark.asyncio for async test methods
    - Target 250+ lines of tests covering LanceDB integration paths

    Uncovered paths in episode_retrieval_service.py to target:
    - Embedding generation (lines 80-120 approximately)
    - Vector search operations (lines 150-200)
    - Hybrid query chains (lines 250-300)
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/integration/episodes/test_lancedb_integration.py -v --cov=core/episode_retrieval_service --cov-report=term-missing

    Expected: New tests pass, EpisodeRetrievalService coverage increases from 65% to 85%+
  </verify>
  <done>
    LanceDB integration tests created. EpisodeRetrievalService coverage increases by 20+ percentage points.
  </done>
</task>

<task type="auto">
  <name>Add LanceDB integration tests for episode decay/consolidation/archival</name>
  <files>backend/tests/integration/episodes/test_episode_lifecycle_lancedb.py</files>
  <action>
    Create a new integration test file for testing LanceDB operations in episode lifecycle (decay, consolidation, archival).

    The file should test:
    1. Episode decay calculation with LanceDB metadata queries
    2. Episode consolidation (merging similar episodes)
    3. Episode archival to cold storage (LanceDB vs PostgreSQL)
    4. Importance score updates in LanceDB
    5. Bulk lifecycle operations

    Target 200+ lines of tests.

    Uncovered paths in episode_lifecycle_service.py to target:
    - Decay calculation (lines 60-100)
    - Consolidation logic (lines 120-180)
    - Archival operations (lines 200-250)
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/integration/episodes/test_episode_lifecycle_lancedb.py -v --cov=core/episode_lifecycle_service --cov-report=term-missing

    Expected: New tests pass, EpisodeLifecycleService coverage increases from 53% to 80%+
  </verify>
  <done>
    LanceDB lifecycle integration tests created. EpisodeLifecycleService coverage increases by 27+ percentage points.
  </done>
</task>

<task type="auto">
  <name>Add integration tests for graduation exam and constitutional validation</name>
  <files>backend/tests/integration/episodes/test_graduation_validation.py</files>
  <action>
    Create a new integration test file for testing graduation exam execution and constitutional validation with episodic memory.

    The file should test:
    1. Graduation exam execution with SandboxExecutor
    2. Constitutional compliance validation against Knowledge Graph rules
    3. Episode-based readiness score calculation
    4. Intervention rate calculation from episode history
    5. Graduation scenarios for each maturity level (STUDENT->INTERN, INTERN->SUPERVISED, SUPERVISED->AUTONOMOUS)

    Target 200+ lines of tests.

    Reference the graduation criteria from docs/AGENT_GRADUATION_GUIDE.md:
    - STUDENT -> INTERN: 10 episodes, 50% intervention rate, 0.70 constitutional score
    - INTERN -> SUPERVISED: 25 episodes, 20% intervention rate, 0.85 constitutional score
    - SUPERVISED -> AUTONOMOUS: 50 episodes, 0% intervention rate, 0.95 constitutional score

    Uncovered paths in agent_graduation_service.py to target:
    - Graduation exam execution (lines 253-285)
    - Constitutional validation (lines 200-250)
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/integration/episodes/test_graduation_validation.py -v --cov=core/agent_graduation_service --cov-report=term-missing

    Expected: New tests pass, AgentGraduationService coverage increases from 42% to 70%+
  </verify>
  <done>
    Graduation validation integration tests created. AgentGraduationService coverage increases by 28+ percentage points.
  </done>
</task>

<task type="auto">
  <name>Enhance episode segmentation service unit tests</name>
  <files>backend/tests/unit/episodes/test_episode_segmentation_service.py</files>
  <action>
    Add additional unit tests to increase EpisodeSegmentationService coverage from 27% to 80%+.

    Add tests for:
    1. Edge cases in time gap detection (boundary conditions, negative deltas)
    2. Topic change detection with similar but not identical topics
    3. Task completion detection with various task states
    4. Metadata extraction with missing or malformed data
    5. Cosine similarity calculation edge cases (empty vectors, identical vectors)
    6. Segmentation with multiple simultaneous triggers

    Add 5-10 new test methods (total 25-30 tests, up from 20).

    Focus on uncovered lines in episode_segmentation_service.py:
    - Error handling paths
    - Edge case validation
    - Conditional branches for different segmentation scenarios
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/unit/episodes/test_episode_segmentation_service.py -v --cov=core/episode_segmentation_service --cov-report=term-missing

    Expected: 25+ tests passing, EpisodeSegmentationService coverage increases from 27% to 80%+
  </verify>
  <done>
    EpisodeSegmentationService unit tests enhanced. Coverage increases by 53+ percentage points.
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run all episodic memory tests: pytest tests/unit/episodes/ tests/integration/episodes/ -v --cov=core --cov-report=term
2. Verify episodic memory domain coverage exceeds 80%:
   - EpisodeSegmentationService: 80%+ (from 27%)
   - EpisodeRetrievalService: 85%+ (from 65%)
   - EpisodeLifecycleService: 80%+ (from 53%)
   - AgentGraduationService: 70%+ (from 42%)
3. Verify LanceDB integration tests pass with actual database operations
4. Verify graduation exam and constitutional validation tests pass
</verification>

<success_criteria>
Episodic memory domain achieves 80% weighted average coverage:
- EpisodeSegmentationService: 80%+ coverage (from 27%)
- EpisodeRetrievalService: 85%+ coverage (from 65%)
- EpisodeLifecycleService: 80%+ coverage (from 53%)
- AgentGraduationService: 70%+ coverage (from 42%)
- LanceDB integration test suite created (250+ lines)
- Graduation validation integration test suite created (200+ lines)
- Episode lifecycle LanceDB integration tests created (200+ lines)
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-03-SUMMARY.md`
</output>
