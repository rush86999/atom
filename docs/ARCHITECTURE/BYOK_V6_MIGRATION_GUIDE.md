# BYOK v6.0 Migration Guide

**Defined**: March 22, 2026
**Status**: Planning Phase
**Target**: Atom v6.0 Release

---

## Overview

The BYOK v6.0 migration consolidates all LLM interactions to a unified **LLMService API** for consistency, observability, and maintainability. This migration ensures that every LLM call flows through a single interface, providing better tracking, cost management, and performance optimization.

## Why This Migration?

### Current Challenges
- **59 files** directly import `BYOKHandler` with inconsistent usage patterns
- **9 critical API calls** bypass unified LLM service (embedding, GraphRAG, security scanning, etc.)
- **Limited observability** - difficult to track LLM usage, costs, and performance across providers
- **No unified caching strategy** - each service implements its own caching
- **Provider-specific code** scattered throughout the codebase

### v6.0 Benefits
- **Unified Interface** - Single LLMService API for all LLM interactions
- **Enhanced Observability** - Track all LLM calls (provider, model, tokens, cost)
- **Cost Optimization** - Cache-aware routing with 90% cost reduction potential
- **Better Performance** - Consistent caching and provider selection
- **Easier Maintenance** - Single point of change for LLM-related features

---

## Migration Scope

### Phase Breakdown (222-232)

| Phase | Focus | Status |
|-------|-------|--------|
| 222 | LLMService Enhancement (LLM-01 to LLM-05) | Pending |
| 223 | Critical API Migration Part 1 (MIG-01 to MIG-03) | Pending |
| 224 | Critical API Migration Part 2 (MIG-04 to MIG-06) | Pending |
| 225 | Critical API Migration Part 3 (MIG-07 to MIG-09) | Pending |
| 226 | BYOKHandler Standardization Part 1 (STD-01 to STD-02) | Pending |
| 227 | BYOKHandler Standardization Part 2 (STD-03) | Pending |
| 228 | BYOKHandler Standardization Part 3 (STD-04 to STD-05) | Pending |
| 229 | Deprecation & Documentation (STD-06 to STD-07) | Pending |
| 230 | Enhanced Observability (OBS-01 to OBS-05) | Pending |
| 231 | Testing Infrastructure Part 1 (TEST-01 to TEST-04) | Pending |
| 232 | Testing Documentation Part 2 (TEST-05 to TEST-07) | Pending |

---

## Requirements

### LLMService Enhancement (LLM-01 to LLM-05)

1. **LLM-01**: Streaming response interface (`stream_completion` method)
2. **LLM-02**: Structured output interface (`generate_structured` method)
3. **LLM-03**: Cognitive tier routing (`generate_with_tier` method)
4. **LLM-04**: Provider selection utilities (`get_optimal_provider` method)
5. **LLM-05**: Backward compatibility during transition period

### Critical API Call Migration (MIG-01 to MIG-09)

**Part 1** (Phase 223):
- MIG-01: `embedding_service.py` → LLMService (AsyncOpenAI → LLMService)
- MIG-02: `graphrag_engine.py` → LLMService (OpenAI client → LLMService)
- MIG-03: `skill_security_scanner.py` → LLMService (security-sensitive)

**Part 2** (Phase 224):
- MIG-04: `atom_security/analyzers/llm.py` → LLMService (security module)
- MIG-05: `lancedb_handler.py` → LLMService (vector database embeddings)
- MIG-06: `social_post_generator.py` → LLMService (content generation)

**Part 3** (Phase 225):
- MIG-07: `voice_service.py` → LLMService (voice processing)
- MIG-08: `generic_agent.py` → Verify using LLMService (already uses BYOKHandler)
- MIG-09: `atom_meta_agent.py` → Verify using LLMService (already using it)

### BYOKHandler Standardization (STD-01 to STD-07)

- STD-01: Update all 59 files importing BYOKHandler to use LLMService
- STD-02: Update core service files (8 files)
- STD-03: Update agent system files (5 files)
- STD-04: Update API routes files (3 files)
- STD-05: Update tool files (1 file)
- STD-06: Add deprecation warnings to direct BYOKHandler usage
- STD-07: Provide migration documentation for developers

### Enhanced Observability (OBS-01 to OBS-05)

- OBS-01: Track all LLM calls (provider, model, tokens, cost)
- OBS-02: Metrics aggregation by provider and model
- OBS-03: Response caching for common queries
- OBS-04: Cache-aware routing integration
- OBS-05: Telemetry dashboard for LLM operations monitoring

### Testing & Documentation (TEST-01 to TEST-07)

- TEST-01: Unit tests for all LLMService methods
- TEST-02: Integration tests for each migrated file (39 test files)
- TEST-03: Property-based tests for LLM invariants (Hypothesis)
- TEST-04: Performance benchmarks (before/after migration)
- TEST-05: API reference documentation for LLMService
- TEST-06: Migration guide for developers (code examples, patterns)
- TEST-07: Troubleshooting guide for common issues

---

## Migration Guidelines

### For Developers

#### Before Migration (Current Pattern)
```python
from core.llm.byok_handler import BYOKHandler

async def my_function():
    handler = BYOKHandler()
    response = await handler.generate("prompt")
    return response
```

#### After Migration (Target Pattern)
```python
from core.llm.llm_service import LLMService

async def my_function():
    service = LLMService()
    response = await service.generate("prompt")
    return response
```

### Migration Checklist

For each file that imports `BYOKHandler`:

1. ✅ Import `LLMService` instead of `BYOKHandler`
2. ✅ Update instantiation: `LLMService()` instead of `BYOKHandler()`
3. ✅ Verify method signatures match (or use adapter methods)
4. ✅ Add unit tests for migrated code
5. ✅ Run integration tests to verify behavior
6. ✅ Update documentation if needed

### Backward Compatibility

During the transition period (Phases 222-229):

- `BYOKHandler` will remain functional with deprecation warnings
- New code must use `LLMService`
- Existing code will be migrated incrementally
- No breaking changes to public APIs

---

## Performance Targets

| Metric | Before | After (Target) |
|--------|--------|----------------|
| Avg LLM call latency | ~500ms | <400ms (20% improvement) |
| Cache hit rate | ~60% | >90% (50% improvement) |
| Cost per 1M tokens | Baseline | -30% (cache-aware routing) |
| Observability coverage | ~40% | 100% (all calls tracked) |
| Code consistency | 59 files | 1 unified interface |

---

## Out of Scope

The following are explicitly **out of scope** for v6.0:

- ❌ Breaking changes to `BYOKHandler` (maintain backward compatibility)
- ❌ New LLM provider integrations (focus on consolidation, not expansion)
- ❌ Provider-specific features (unified interface only)
- ❌ Database schema changes (no DB changes required)
- ❌ Multi-tenant LLM service isolation (deferred to future milestone)
- ❌ Custom model fine-tuning integration (deferred to future milestone)
- ❌ Edge deployment support (deferred to future milestone)

---

## Progress Tracking

**Current Status**: Planning Phase
**Requirements Locked**: March 22, 2026
**Target Completion**: TBD (based on roadmap)

### Coverage Metrics
- Total requirements: 31
- Mapped to phases: 31 (100%)
- Unmapped: 0

---

## References

- **Requirements Document**: `.planning/REQUIREMENTS-v6.0-BYOK.md`
- **Phase Plans**: `.planning/phases/222-*/` through `.planning/phases/232-*/`
- **Existing BYOK Implementation**: `backend/core/llm/byok_handler.py`
- **Cognitive Tier System**: `docs/ARCHITECTURE/COGNITIVE_TIER_SYSTEM.md`

---

## Questions?

See `.planning/REQUIREMENTS-v6.0-BYOK.md` for detailed requirements and traceability matrix.

---

*Last Updated: March 24, 2026*
