---
phase: 08-80-percent-coverage-push
plan: 09
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_auto_document_ingestion.py
  - backend/tests/unit/test_hybrid_data_ingestion.py
  - backend/tests/unit/test_proposal_service.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "auto_document_ingestion.py has baseline unit tests with 30%+ coverage"
    - "hybrid_data_ingestion.py has baseline unit tests with 30%+ coverage"
    - "proposal_service.py has baseline unit tests with 30%+ coverage"
    - "All new tests pass with pytest"
  artifacts:
    - path: "backend/tests/unit/test_auto_document_ingestion.py"
      provides: "Baseline unit tests for AutoDocumentIngestion"
      min_lines: 300
    - path: "backend/tests/unit/test_hybrid_data_ingestion.py"
      provides: "Baseline unit tests for HybridDataIngestion"
      min_lines: 300
    - path: "backend/tests/unit/test_proposal_service.py"
      provides: "Baseline unit tests for ProposalService"
      min_lines: 350
  key_links:
    - from: "test_auto_document_ingestion.py"
      to: "core/auto_document_ingestion.py"
      via: "import"
      pattern: "from core.auto_document_ingestion import"
    - from: "test_hybrid_data_ingestion.py"
      to: "core/hybrid_data_ingestion.py"
      via: "import"
      pattern: "from core.hybrid_data_ingestion import"
    - from: "test_proposal_service.py"
      to: "core/proposal_service.py"
      via: "import"
      pattern: "from core.proposal_service import"
---

<objective>
Create baseline unit tests for 3 zero-coverage core modules: auto_document_ingestion, hybrid_data_ingestion, and proposal_service. These are ingestion and proposal components critical for the agent training workflow.

Purpose: Establish test coverage for document ingestion and agent proposal systems. Baseline 30%+ coverage ensures main code paths are tested.

Output: 3 new test files with 300+ lines each, achieving 30%+ coverage on target modules.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-01-SUMMARY.md
@backend/core/auto_document_ingestion.py
@backend/core/hybrid_data_ingestion.py
@backend/core/proposal_service.py

Gap context from VERIFICATION.md:
- "test_auto_document_ingestion.py - not created"
- "test_proposal_service.py - not created"
- "test_hybrid_data_ingestion.py - not created"
- 10 zero-coverage files remain untested

Test patterns from prior plans:
- AsyncMock for async service dependencies
- FeatureFlags mock for governance bypass
- Patch decorators for isolating dependencies
- Simple test data without complex external dependencies
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create baseline unit tests for auto_document_ingestion.py</name>
  <files>backend/tests/unit/test_auto_document_ingestion.py</files>
  <action>
    Create test_auto_document_ingestion.py with baseline unit tests for AutoDocumentIngestion:

    1. Read core/auto_document_ingestion.py to understand the class structure
    2. Create test class TestDocumentIngestionInit with 3-4 tests for initialization
    3. Create test class TestDocumentParsing with 4-5 tests for document parsing logic
    4. Create test class TestContentExtraction with 4-5 tests for content extraction
    5. Create test class TestIngestionErrors with 3-4 tests for error handling

    Mock file system operations (mock_open, AsyncMock for async file reads)
    Mock document parsers (PDF, DOCX, etc.)
    Test parsing logic in isolation

    Target: 300+ lines, 15-20 tests, 30%+ coverage

    Focus on testable code paths:
    - Constructor and configuration
    - File type detection logic
    - Parser selection logic
    - Error handling for unsupported formats
  </action>
  <verify>pytest backend/tests/unit/test_auto_document_ingestion.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 30%+ coverage on auto_document_ingestion.py</done>
</task>

<task type="auto">
  <name>Task 2: Create baseline unit tests for hybrid_data_ingestion.py</name>
  <files>backend/tests/unit/test_hybrid_data_ingestion.py</files>
  <action>
    Create test_hybrid_data_ingestion.py with baseline unit tests for HybridDataIngestion:

    1. Read core/hybrid_data_ingestion.py to understand the class structure
    2. Create test class TestHybridIngestionInit with 3-4 tests for initialization
    3. Create test class TestDataSourceRouting with 4-5 tests for source selection
    4. Create test class TestDataTransformation with 4-5 tests for transformation logic
    5. Create test class TestHybridErrors with 3-4 tests for error handling

    Mock multiple data sources (API, database, file system)
    Test routing logic for different source types
    Test data transformation pipelines

    Target: 300+ lines, 15-20 tests, 30%+ coverage

    Focus on routing logic and transformation rules that can be unit tested
  </action>
  <verify>pytest backend/tests/unit/test_hybrid_data_ingestion.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 30%+ coverage on hybrid_data_ingestion.py</done>
</task>

<task type="auto">
  <name>Task 3: Create baseline unit tests for proposal_service.py</name>
  <files>backend/tests/unit/test_proposal_service.py</files>
  <action>
    Create test_proposal_service.py with baseline unit tests for ProposalService:

    1. Read core/proposal_service.py to understand the class structure
    2. Create test class TestProposalServiceInit with 3-4 tests for initialization
    3. Create test class TestProposalCreation with 4-5 tests for proposal generation
    4. Create test class TestProposalApproval with 3-4 tests for approval workflow
    5. Create test class TestProposalErrors with 3-4 tests for error scenarios

    Use AsyncMock for database operations
    Mock governance checks
    Test proposal state transitions

    Target: 350+ lines, 15-20 tests, 30%+ coverage

    Focus on:
    - Proposal creation logic
    - State management (pending, approved, rejected)
    - Validation rules
    - Error handling for invalid proposals
  </action>
  <verify>pytest backend/tests/unit/test_proposal_service.py -v | tee test_output.txt && grep -E "(PASSED|FAILED|ERROR)" test_output.txt | wc -l</verify>
  <done>15+ tests created, all passing, 30%+ coverage on proposal_service.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run pytest on all three new test files:
   ```bash
   pytest backend/tests/unit/test_auto_document_ingestion.py backend/tests/unit/test_hybrid_data_ingestion.py backend/tests/unit/test_proposal_service.py -v
   ```

2. Verify all tests pass (45-60 tests total expected)

3. Run coverage report:
   ```bash
   pytest backend/tests/unit/test_auto_document_ingestion.py backend/tests/unit/test_hybrid_data_ingestion.py backend/tests/unit/test_proposal_service.py --cov=backend.core.auto_document_ingestion --cov=backend.core.hybrid_data_ingestion --cov=backend.core.proposal_service --cov-report=term-missing
   ```

4. Verify 30%+ coverage on each target file

5. Update coverage_reports/metrics/coverage.json with new metrics
</verification>

<success_criteria>
- 3 new test files created (test_auto_document_ingestion.py, test_hybrid_data_ingestion.py, test_proposal_service.py)
- 45-60 total tests created across the three files
- 100% test pass rate
- 30%+ coverage achieved on each of the three target modules
- All tests execute in under 30 seconds
- coverage.json updated with new metrics
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-09-SUMMARY.md`
</output>
