# Phase 30: Tier 1 Coverage Push - High Impact Files

**Status:** Planning Complete
**Created:** 2026-02-19
**Priority:** High

## Phase Goal

Achieve 28% overall coverage by testing 6 highest-impact Tier 1 files (>500 lines, <20% coverage baseline) with property-based tests and integration tests.

## Success Criteria

1. **COV-01**: core/models.py (5321 lines) reaches 50% coverage
   - Current: 97.6% (2401/2439 lines)
   - Status: **ALREADY EXCEEDS TARGET** - No work needed

2. **COV-02**: core/workflow_engine.py (2260 lines) reaches 50% coverage
   - Current: 12.6% (169/1163 lines)
   - Target: 50% (+407 lines)
   - Approach: Property-based state invariants, step execution tests

3. **COV-03**: core/atom_agent_endpoints.py (2043 lines) reaches 50% coverage
   - Current: 33.6% (262/774 lines)
   - Target: 50% (+125 lines)
   - Approach: API contract tests, streaming endpoint tests

4. **COV-04**: core/workflow_analytics_engine.py (1518 lines) reaches 50% coverage
   - Current: 54.4% (338/593 lines)
   - Status: **ALREADY EXCEEDS TARGET** - No work needed

5. **COV-05**: core/llm/byok_handler.py (1180 lines) reaches 50% coverage
   - Current: 36.3% (207/549 lines)
   - Target: 50% (+68 lines)
   - Approach: Provider fallback property tests

6. **COV-06**: core/workflow_debugger.py (1396 lines) reaches 50% coverage
   - Current: 9.7% (62/527 lines)
   - Target: 50% (+202 lines)
   - Approach: Debug workflow tests, breakpoint management tests

## Overall Coverage Target

- Baseline: 12.7% (17634/116657 lines)
- Target: 28% overall
- Strategy: Focus on highest-impact files

## Plans

### Wave 1 (Parallel Execution)

- [ ] 30-01-PLAN.md — Workflow Engine State Invariants (workflow_engine.py to 50%)
- [ ] 30-02-PLAN.md — Atom Agent Endpoints API Contracts (atom_agent_endpoints.py to 50%)
- [ ] 30-03-PLAN.md — BYOK Handler Provider Fallback (byok_handler.py to 50%)
- [ ] 30-04-PLAN.md — Workflow Debugger Testing (workflow_debugger.py to 50%)

## Requirements Coverage

- **COV-01**: models.py 50% coverage (ALREADY DONE)
- **COV-02**: workflow_engine.py 50% coverage (Plan 30-01)
- **COV-03**: atom_agent_endpoints.py 50% coverage (Plan 30-02)
- **COV-04**: workflow_analytics_engine.py 50% coverage (ALREADY DONE)
- **COV-05**: byok_handler.py 50% coverage (Plan 30-03)
- **COV-06**: workflow_debugger.py 50% coverage (Plan 30-04)
- **COV-07**: Property tests verify workflow_engine stateful invariants (Plan 30-01)
- **COV-08**: Property tests verify byok_handler provider fallback (Plan 30-03)
- **COV-09**: Integration tests verify atom_agent_endpoints API contracts (Plan 30-02)
- **COV-10**: Unit tests verify models.py ORM relationships (ALREADY DONE)

## Dependencies

- None (all plans are independent)

## Related Phases

- Phase 02: Core Invariants (property-based testing patterns)
- Phase 08: 80% Coverage Push (API route testing patterns)
- Phase 29: Test Failure Fixes (baseline test quality)
