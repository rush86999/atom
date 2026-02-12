# Phase 8: 80% Coverage Push - State

**Phase**: 08 - 80% Coverage Push
**Status**: In Progress
**Started**: 2026-02-12

## Objective

Systematically add unit tests to uncovered code paths across core, api, and tools modules to achieve 80% overall code coverage.

## Current Coverage

- **Overall**: 16.06% (10,817 / 55,115 lines covered)
- **Target**: 80% (44,092 / 55,115 lines)
- **Gap**: 44,298 lines to cover

### Module Breakdown

| Module | Current Coverage | Target | Missing Lines |
|--------|-----------------|--------|---------------|
| core | 16.6% (6,785 / 40,801) | 80%+ | 27,231 |
| api | 30.3% (3,930 / 12,977) | 80%+ | 6,373 |
| tools | 7.6% (102 / 1,337) | 80%+ | 906 |

## Success Criteria

1. Overall coverage reaches 80%
2. Core module coverage reaches 80%+
3. API module coverage reaches 80%+
4. Tools module coverage reaches 80%+
5. All zero-coverage files receive baseline unit tests
6. High-impact files receive comprehensive tests
7. Coverage quality gates prevent regression

## Plans (7 Total)

### Pending Plans
- [ ] 08-80-percent-coverage-01-PLAN.md — Zero-coverage files baseline (15 files, 4,783 lines)
- [ ] 08-80-percent-coverage-02-PLAN.md — Workflow engine comprehensive tests (1,089 lines)
- [ ] 08-80-percent-coverage-03-PLAN.md — LLM & BYOK handler tests (794 lines)
- [ ] 08-80-percent-coverage-04-PLAN.md — Episodic memory service tests (650+ lines)
- [ ] 08-80-percent-coverage-05-PLAN.md — Analytics & debugging tests (930 lines)
- [ ] 08-80-percent-coverage-06-PLAN.md — API module coverage completion (6,000+ lines)
- [ ] 08-80-percent-coverage-07-PLAN.md — Tools module coverage completion (1,000+ lines)

## Priority Files

### Zero-Coverage Files (Quick Wins)
1. tools/canvas_tool.py (379 lines, 0.0%)
2. core/formula_extractor.py (313 lines, 0.0%)
3. core/bulk_operations_processor.py (292 lines, 0.0%)
4. core/atom_meta_agent.py (331 lines, 0.0%)
5. core/integration_data_mapper.py (338 lines, 0.0%)

### High-Impact Files
1. core/workflow_engine.py (1,089 missing, 6.4% covered)
2. core/atom_agent_endpoints.py (736 missing, 0.0% covered)
3. core/auto_document_ingestion.py (479 missing, 0.0% covered)
4. core/workflow_versioning_system.py (476 missing, 0.0% covered)
5. core/advanced_workflow_system.py (473 missing, 0.0% covered)

## Current Blockers

None identified

## Risks

- Large amount of code to cover (44,298 lines)
- Time-intensive effort (estimated 360-465 hours)
- Some modules may require complex test setup (LLM mocking, database integration)
- Property test collection errors may interfere with coverage measurement

## Notes

- See `backend/tests/coverage_reports/COVERAGE_PRIORITY_ANALYSIS.md` for detailed analysis
- Focus on unit tests first, then integration tests
- Use existing test infrastructure from Phases 1-7
- Leverage factory-boy factories for test data
- Use FastAPI TestClient for API tests
- Mock external dependencies (LLM providers, databases)
