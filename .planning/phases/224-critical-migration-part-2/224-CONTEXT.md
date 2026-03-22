# Phase 224: Critical Migration Part 2 - Context

**Gathered:** March 22, 2026
**Status:** Ready for planning

## Guiding Vision

**Unify ALL LLM calls under LLMService API** — including embeddings, voice, and any other LLM interactions. This achieves:
- **Centralized BYOK** — Single point for all provider Bring Your Own Key configuration
- **Unified cost tracking** — All token usage and costs tracked through one service
- **Easier maintenance** — One interface to update, monitor, and optimize

Phase 224 continues the migration work started in Phase 223, applying proven patterns to 3 more critical files.

## Phase Boundary

Migrate three more files from direct API calls to the unified LLMService:
1. `atom_security/analyzers/llm.py` - LLM-based security analysis
2. `lancedb_handler.py` - Vector database embeddings
3. `social_post_generator.py` - Social content generation

All three services must pass existing tests with integration tests verifying LLMService compatibility.

## Implementation Decisions

### Migration Pattern Consistency
- **Copy Phase 223 patterns exactly** — Use the exact same proven migration patterns:
  1. Import LLMService at top of file
  2. Initialize LLMService in `__init__` with workspace_id parameter
  3. Replace direct client calls with `llm_service.generate_completion` or `generate_embedding`
  4. Update response extraction to `response.get("content")`
  5. Make methods async if calling LLMService async methods
  6. Update test mocks from OpenAI to LLMService with AsyncMock
  7. Add `@pytest.mark.asyncio` decorators to async test methods
- **Create migration checklist** — Document Phase 223 patterns as a reusable checklist for Phase 224 and future phases (225-232)

### Cross-Phase Dependencies
- **Add LanceDB integration test** — Verify LLMService embedding methods work correctly with LanceDB vector operations:
  - Create test that generates embeddings via `llm_service.generate_embeddings_batch`
  - Insert vectors into LanceDB
  - Perform vector search to verify results
  - Confirms 223-01 embedding methods integrate correctly with vector database
- **Add integration tests for all 3 files** — Each migrated file gets an integration test:
  - atom_security/analyzers/llm.py: Test security analysis with LLMService
  - lancedb_handler.py: Test vector embeddings with LLMService
  - social_post_generator.py: Test content generation with LLMService
- **Add meta-verification task** — After Phase 224 completion, verify cross-cutting concerns:
  - Embeddings work with all consumers (LanceDB, episodic memory, etc.)
  - Cost tracking aggregates correctly across all services
  - No unintended side effects from LLMService changes

### Test Migration Strategy
- **Copy Phase 223 test pattern exactly** — Use the exact same test migration approach:
  - Update `@patch` decorators to mock LLMService instead of OpenAI
  - Use `AsyncMock` for async LLMService method calls
  - Add `@pytest.mark.asyncio` decorators to async test methods
  - Make test methods async if they call async production methods
  - Verify mock returns match LLMService response format (`response.get("content")`)
- **Run full test suite** — After each plan, run full test suite (not just file-specific tests):
  - Catches cross-file issues that file-specific tests miss
  - Ensures no unintended side effects from LLMService migration
  - May take longer but provides higher confidence
- **Verify test coverage maintained** — Compare coverage reports before/after migration:
  - Run coverage report for each migrated file
  - Compare to baseline (pre-migration coverage)
  - Ensure coverage hasn't decreased

### Claude's Discretion
- Wave grouping for plans 224-01, 224-02, 224-03 (user specified: 224-01 + 224-02 in Wave 1, 224-03 in Wave 2)
- Integration test design and implementation details
- Meta-verification task scope and success criteria

## Specific Ideas

- Apply Phase 223 patterns as a checklist — this reduces decision fatigue during planning
- Integration tests should be realistic but not overly complex — use test fixtures, not real external services
- Full test suite execution may take 5-10 minutes — acceptable tradeoff for catching cross-file issues

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 224-critical-migration-part-2*
*Context gathered: 2026-03-22*
