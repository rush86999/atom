# Test Prioritization Phased Roadmap - Phase 164
**Generated**: 2026-03-11T10:42:41.365857**Baseline Coverage**: 74.55%**Target Coverage**: 80.0%**Total Gap**: 5.45 percentage points
## Overview
This roadmap provides a phased approach to achieve 80% coverage across **1 files**with **49** uncovered lines.
## Phase Summary

| Phase | Name | Files | Est. Lines | Target Gain | Cumulative |
|-------|------|-------|------------|-------------|------------|
| 165 | Core Services Coverage (Governance & LLM) | 1 | 29 | +10.0% | 74.5% → 84.5% |
| 166 | Core Services Coverage (Episodic Memory) | 0 | 0 | +8.0% | 84.5% → 92.5% |
| 167 | API Routes Coverage | 0 | 0 | +12.0% | 92.5% → 104.5% |
| 168 | Database Layer Coverage | 0 | 0 | +10.0% | 104.5% → 114.5% |
| 169 | Tools & Integrations Coverage | 0 | 0 | +8.0% | 114.5% → 122.5% |
| 170 | Integration Testing (LanceDB, WebSocket, HTTP) | 0 | 0 | +7.0% | 122.5% → 129.6% |
| 171 | Gap Closure & Final Push | 0 | 0 | +15.0% | 129.6% → 144.6% |

## Phase Details

### Phase 165: Core Services Coverage (Governance & LLM)

**Target Coverage Gain**: +10.0%
**Focus Areas**: agent_governance, llm, byok_handler, cognitive_tier

**Files (1):**

| File | Coverage | Impact | Missing | Priority |
|------|----------|--------|---------|----------|
| `core/agent_governance_service.py` | 74.55% | Critical | 49 | 6.5 |

### Phase 166: Core Services Coverage (Episodic Memory)

**Target Coverage Gain**: +8.0%
**Focus Areas**: episode_segmentation, episode_retrieval, episode_lifecycle, agent_graduation

*No files assigned*

### Phase 167: API Routes Coverage

**Target Coverage Gain**: +12.0%
**Focus Areas**: routes, api/, endpoints

*No files assigned*

### Phase 168: Database Layer Coverage

**Target Coverage Gain**: +10.0%
**Focus Areas**: models, schema, database

*No files assigned*

### Phase 169: Tools & Integrations Coverage

**Target Coverage Gain**: +8.0%
**Focus Areas**: browser_tool, device_tool, canvas_tool

*No files assigned*

### Phase 170: Integration Testing (LanceDB, WebSocket, HTTP)

**Target Coverage Gain**: +7.0%
**Focus Areas**: lancedb, websocket, http_client, external_api

*No files assigned*

### Phase 171: Gap Closure & Final Push

**Target Coverage Gain**: +15.0%
**Focus Areas**: all_remaining

*No files assigned*

## Dependency Ordering

Files are assigned to phases respecting the following dependency rules:

1. Utilities and helpers are tested before services that use them
2. Models are tested before API routes that use them
3. Core services are tested before integrations that depend on them
4. Within each phase, files are ordered by priority score (business impact × coverage gap)

## Next Steps

1. **Phase 165**: Start with governance and LLM services (highest impact)
2. **Phase 166**: Move to episodic memory services
3. **Phase 167**: Cover API routes with TestClient integration tests
4. **Phase 168**: Ensure database models have comprehensive coverage
5. **Phase 169**: Test browser and device tools with proper mocking
6. **Phase 170**: Add integration tests for external services
7. **Phase 171**: Final gap closure to achieve 80% target

