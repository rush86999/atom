---
phase: 08-80-percent-coverage-push
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/test_canvas_tool.py
  - backend/tests/unit/test_formula_extractor.py
  - backend/tests/unit/test_bulk_operations_processor.py
  - backend/tests/unit/test_atom_meta_agent.py
  - backend/tests/unit/test_integration_data_mapper.py
  - backend/tests/unit/test_auto_document_ingestion.py
  - backend/tests/unit/test_workflow_marketplace.py
  - backend/tests/unit/test_proposal_service.py
  - backend/tests/unit/test_workflow_analytics_endpoints.py
  - backend/tests/unit/test_hybrid_data_ingestion.py
  - backend/tests/unit/test_atom_agent_endpoints.py
  - backend/tests/unit/test_advanced_workflow_system.py
  - backend/tests/unit/test_workflow_versioning_system.py
autonomous: true

must_haves:
  truths:
    - "Zero-coverage files have baseline unit tests covering main functions"
    - "Each test file achieves at least 50% coverage for its target module"
    - "Tests use existing factory fixtures (AgentFactory, UserFactory, CanvasFactory)"
    - "All new tests pass with pytest -v"
  artifacts:
    - path: "backend/tests/unit/test_canvas_tool.py"
      provides: "Tests for canvas presentation functions"
      min_lines: 300
    - path: "backend/tests/unit/test_formula_extractor.py"
      provides: "Tests for formula extraction from Excel"
      min_lines: 250
    - path: "backend/tests/unit/test_bulk_operations_processor.py"
      provides: "Tests for bulk CRUD operations"
      min_lines: 200
    - path: "backend/tests/unit/test_atom_meta_agent.py"
      provides: "Tests for meta-agent orchestration"
      min_lines: 250
    - path: "backend/tests/unit/test_integration_data_mapper.py"
      provides: "Tests for data transformation logic"
      min_lines: 250
  key_links:
    - from: "backend/tests/unit/test_canvas_tool.py"
      to: "backend/tools/canvas_tool.py"
      via: "import and test functions directly"
      pattern: "from tools.canvas_tool import"
    - from: "backend/tests/unit"
      to: "backend/tests/factories"
      via: "use factories for test data"
      pattern: "from tests.factories"
---

<objective>
Create baseline unit tests for 13 zero-coverage files to achieve initial coverage of ~4,783 lines. This is the first wave of the 80% coverage push, focusing on quick wins by adding tests to files with 0% coverage.

Purpose: Establish test coverage foundation for previously untested modules, enabling early detection of regressions and providing examples for subsequent test development.
Output: 13 new test files with 50%+ coverage for target modules
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
@backend/tests/factories/agent_factory.py
@backend/tests/factories/user_factory.py
@backend/tests/factories/canvas_factory.py
@backend/tests/test_browser_automation.py
@backend/tools/canvas_tool.py
@backend/core/formula_extractor.py
@backend/core/bulk_operations_processor.py
@backend/core/atom_meta_agent.py
@backend/core/integration_data_mapper.py
@backend/core/auto_document_ingestion.py
@backend/core/workflow_marketplace.py
@backend/core/proposal_service.py
@backend/core/workflow_analytics_endpoints.py
@backend/core/hybrid_data_ingestion.py
@backend/core/atom_agent_endpoints.py
@backend/core/advanced_workflow_system.py
@backend/core/workflow_versioning_system.py
</context>

<tasks>

<task type="auto">
  <name>Create test_canvas_tool.py with presentation function tests</name>
  <files>backend/tests/unit/test_canvas_tool.py</files>
  <action>
    Create backend/tests/unit/test_canvas_tool.py (if directory doesn't exist, create it):

    Test the following functions from tools/canvas_tool.py:
    1. present_chart() - test with valid/invalid chart types, governance allow/block
    2. present_markdown() - test content rendering, agent governance
    3. present_form() - test form schema presentation, field validation
    4. present_status_panel() - test status item rendering
    5. update_canvas() - test canvas update functionality
    6. close_canvas() - test canvas closing
    7. present_specialized_canvas() - test canvas type validation
    8. canvas_execute_javascript() - test AUTONOMOUS-only enforcement
    9. _create_canvas_audit() - test audit entry creation

    Use pytest.mark.asyncio for async tests.
    Mock WebSocketManager with AsyncMock for broadcast operations.
    Mock AgentContextResolver and AgentGovernanceService for governance tests.
    Use factories for user, agent creation.
    Test governance blocking: STUDENT agents blocked for canvas presentations.
    Test success paths: INTERN+ agents can present charts, forms, markdown.
    Test error handling: invalid chart types, empty content, governance denial.

    Follow the pattern from backend/tests/test_browser_automation.py for structure.
  </action>
  <verify>pytest backend/tests/unit/test_canvas_tool.py -v --tb=short</verify>
  <done>All canvas_tool tests pass (minimum 15 tests), 50%+ coverage on canvas_tool.py</done>
</task>

<task type="auto">
  <name>Create test_formula_extractor.py with formula extraction tests</name>
  <files>backend/tests/unit/test_formula_extractor.py</files>
  <action>
    Create backend/tests/unit/test_formula_extractor.py:

    Test the FormulaExtractor class from core/formula_extractor.py:
    1. test_formula_extractor_init() - workspace_id initialization
    2. test_extract_from_file_xlsx() - Excel file extraction
    3. test_extract_from_file_csv() - CSV formula detection
    4. test_extract_from_file_unsupported() - unsupported file type handling
    5. test_detect_formula_type() - SUM, AVERAGE, IF, VLOOKUP detection
    6. test_extract_cell_references() - A1, B2 pattern extraction
    7. test_column_letter_to_number() - A=1, Z=26, AA=27 conversion
    8. test_create_semantic_expression() - semantic naming
    9. test_detect_domain() - finance, sales, operations detection
    10. test_generate_use_case() - natural language descriptions
    11. test_parse_formula() - complete formula parsing
    12. test_get_xls_headers() - header extraction
    13. test_detect_implicit_formulas() - column relationship detection

    Create mock Excel file with openpyxl for xlsx tests.
    Create mock CSV with in-memory StringIO for csv tests.
    Test all formula patterns: SUM, AVERAGE, IF, VLOOKUP, COUNT, MAX, MIN.
    Test domain keyword matching for all 5 domains.
    Test edge cases: empty files, missing headers, circular references.
  </action>
  <verify>pytest backend/tests/unit/test_formula_extractor.py -v --tb=short</verify>
  <done>All formula_extractor tests pass (minimum 15 tests), 50%+ coverage on formula_extractor.py</done>
</task>

<task type="auto">
  <name>Create test_bulk_operations_processor.py with bulk CRUD tests</name>
  <files>backend/tests/unit/test_bulk_operations_processor.py</files>
  <action>
    Create backend/tests/unit/test_bulk_operations_processor.py:

    Test the BulkOperationsProcessor class from core/bulk_operations_processor.py:
    1. test_bulk_processor_init() - initialization with batch size
    2. test_bulk_create() - create multiple records
    3. test_bulk_update() - update multiple records
    4. test_bulk_delete() - delete multiple records
    5. test_bulk_upsert() - upsert operations
    6. test_process_in_batches() - batch processing logic
    7. test_handle_errors_in_batch() - continue_on_error behavior
    8. test_validate_batch_size() - batch size validation
    9. test_get_progress() - progress tracking
    10. test_rollback_on_failure() - transaction rollback

    Mock database session with Mock(spec=Session).
    Use factories to generate test data.
    Test success: all records processed successfully.
    Test failure scenarios: invalid data, constraint violations, connection errors.
    Test batch splitting: large datasets split into correct batch sizes.
    Test error handling: partial failures with continue_on_error.
  </action>
  <verify>pytest backend/tests/unit/test_bulk_operations_processor.py -v --tb=short</verify>
  <done>All bulk_operations_processor tests pass (minimum 12 tests), 50%+ coverage on bulk_operations_processor.py</done>
</task>

<task type="auto">
  <name>Create test_atom_meta_agent.py with meta-agent orchestration tests</name>
  <files>backend/tests/unit/test_atom_meta_agent.py</files>
  <action>
    Create backend/tests/unit/test_atom_meta_agent.py:

    Test the AtomMetaAgent class from core/atom_meta_agent.py:
    1. test_meta_agent_init() - initialization
    2. test_orchestrate_workflow() - workflow coordination
    3. test_delegate_to_specialist() - agent delegation
    4. test_synthesize_results() - result aggregation
    5. test_handle_ambiguity() - ambiguity resolution
    6. test_select_agent_for_task() - agent selection logic
    7. test_merge_agent_outputs() - output merging
    8. test_validate_consensus() - consensus validation
    9. test_handle_conflict() - conflict resolution
    10. test_update_world_model() - world model updates

    Mock specialist agents with AsyncMock.
    Mock workflow engine with AsyncMock.
    Test delegation: tasks routed to correct specialists.
    Test synthesis: multiple agent results combined correctly.
    Test error handling: specialist failures, timeout scenarios.
    Use factories for agent creation.
  </action>
  <verify>pytest backend/tests/unit/test_atom_meta_agent.py -v --tb=short</verify>
  <done>All atom_meta_agent tests pass (minimum 12 tests), 50%+ coverage on atom_meta_agent.py</done>
</task>

<task type="auto">
  <name>Create test_integration_data_mapper.py with data transformation tests</name>
  <files>backend/tests/unit/test_integration_data_mapper.py</files>
  <action>
    Create backend/tests/unit/test_integration_data_mapper.py:

    Test the IntegrationDataMapper from core/integration_data_mapper.py:
    1. test_mapper_init() - initialization with config
    2. test_map_field() - single field mapping
    3. test_map_record() - full record transformation
    4. test_map_batch() - batch transformation
    5. test_apply_transformations() - data type conversions
    6. test_handle_nested_mapping() - nested object mapping
    7. test_validate_mapped_data() - schema validation
    8. test_reverse_mapping() - destination to source mapping
    9. test_merge_mappings() - mapping combination
    10. test_cache_mapping_result() - result caching

    Test mapping: source fields to destination fields.
    Test transformations: date formats, currency conversions, enum mappings.
    Test validation: required fields, type checking, constraint validation.
    Test edge cases: missing fields, null values, empty arrays.
  </action>
  <verify>pytest backend/tests/unit/test_integration_data_mapper.py -v --tb=short</verify>
  <done>All integration_data_mapper tests pass (minimum 12 tests), 50%+ coverage on integration_data_mapper.py</done>
</task>

<task type="auto">
  <name>Create test_auto_document_ingestion.py with document processing tests</name>
  <files>backend/tests/unit/test_auto_document_ingestion.py</files>
  <action>
    Create backend/tests/unit/test_auto_document_ingestion.py:

    Test AutoDocumentIngestion from core/auto_document_ingestion.py:
    1. test_ingestion_init() - initialization
    2. test_ingest_pdf() - PDF text extraction
    3. test_ingest_docx() - DOCX text extraction
    4. test_ingest_txt() - TXT file handling
    5. test_extract_metadata() - metadata extraction
    6. test_detect_document_type() - type detection
    7. test_handle_encrypted_pdf() - encrypted PDF handling
    8. test_process_in_batch() - batch processing
    9. test_track_ingestion_progress() - progress tracking
    10. test_store_extracted_content() - content storage

    Mock file reading with StringIO/temporary files.
    Test extraction: text, tables, images from PDFs.
    Test metadata: author, creation date, page count.
    Test error handling: corrupted files, unsupported formats.
  </action>
  <verify>pytest backend/tests/unit/test_auto_document_ingestion.py -v --tb=short</verify>
  <done>All auto_document_ingestion tests pass (minimum 12 tests), 50%+ coverage on auto_document_ingestion.py</done>
</task>

<task type="auto">
  <name>Create remaining zero-coverage module tests (workflow_marketplace, proposal_service, etc.)</name>
  <files>
    backend/tests/unit/test_workflow_marketplace.py
    backend/tests/unit/test_proposal_service.py
    backend/tests/unit/test_workflow_analytics_endpoints.py
    backend/tests/unit/test_hybrid_data_ingestion.py
    backend/tests/unit/test_atom_agent_endpoints.py
    backend/tests/unit/test_advanced_workflow_system.py
    backend/tests/unit/test_workflow_versioning_system.py
  </files>
  <action>
    Create unit tests for the remaining zero-coverage files:

    1. test_workflow_marketplace.py - test template listing, search, installation, rating
    2. test_proposal_service.py - test proposal creation, approval, rejection, expiry
    3. test_workflow_analytics_endpoints.py - test analytics API endpoints
    4. test_hybrid_data_ingestion.py - test hybrid SQL+NoSQL ingestion
    5. test_atom_agent_endpoints.py - test agent chat/streaming endpoints
    6. test_advanced_workflow_system.py - test advanced workflow features
    7. test_workflow_versioning_system.py - test version control for workflows

    Each file should have 8-12 tests covering:
    - Initialization and configuration
    - Main functionality (CRUD or primary operations)
    - Error handling (invalid inputs, missing data)
    - Edge cases (empty results, boundary conditions)
    - Integration points (database, external services)

    Use pytest.mark.asyncio for async functions.
    Mock database sessions with Mock(spec=Session).
    Mock external API calls with AsyncMock.
    Use factories for test data generation.
  </action>
  <verify>pytest backend/tests/unit/ -v --tb=short -k "workflow_marketplace or proposal_service or analytics_endpoints or hybrid_ingestion or atom_agent or advanced_workflow or workflow_versioning"</verify>
  <done>All zero-coverage module tests pass (minimum 70 total tests), 50%+ coverage on all target files</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/unit/ -v to verify all new tests pass
2. Run pytest --cov=backend/tools/canvas_tool backend/tests/unit/test_canvas_tool.py to verify coverage
3. Run pytest --cov=backend/core/formula_extractor backend/tests/unit/test_formula_extractor.py to verify coverage
4. Check coverage.json to confirm at least 50% coverage for each targeted file
5. Verify no tests are marked as xfail or skip (baseline tests should all pass)
</verification>

<success_criteria>
- 13 new test files created in backend/tests/unit/
- Each target module has 50%+ code coverage
- All new tests pass with pytest -v
- Tests follow existing patterns (factories, AsyncMock, pytest.mark.asyncio)
- Coverage increase of at least 2,000 lines (42% of 4,783 target)
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-01-SUMMARY.md`
</output>
