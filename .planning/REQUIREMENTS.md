# Requirements: Atom BYOK Migration

**Defined:** 2026-03-22
**Core Value:** All LLM interactions flow through a single unified interface for consistency, observability, and maintainability

## v1 Requirements

Requirements for v6.0 milestone: Consolidate all BYOK LLM interactions to unified LLMService API.

### LLMService Enhancement

- [ ] **LLM-01**: LLMService exposes streaming response interface (stream_completion method)
- [ ] **LLM-02**: LLMService exposes structured output interface (generate_structured method)
- [ ] **LLM-03**: LLMService exposes cognitive tier routing (generate_with_tier method)
- [ ] **LLM-04**: LLMService exposes provider selection utilities (get_optimal_provider method)
- [ ] **LLM-05**: LLMService maintains backward compatibility during transition period

### Critical API Call Migration

- [ ] **MIG-01**: embedding_service.py migrated to LLMService (AsyncOpenAI → LLMService)
- [ ] **MIG-02**: graphrag_engine.py migrated to LLMService (OpenAI client → LLMService)
- [ ] **MIG-03**: skill_security_scanner.py migrated to LLMService (security-sensitive migration)
- [ ] **MIG-04**: atom_security/analyzers/llm.py migrated to LLMService (security module)
- [ ] **MIG-05**: lancedb_handler.py migrated to LLMService (vector database embeddings)
- [ ] **MIG-06**: social_post_generator.py migrated to LLMService (content generation)
- [ ] **MIG-07**: voice_service.py migrated to LLMService (voice processing)
- [ ] **MIG-08**: generic_agent.py standardized to use LLMService (already uses BYOKHandler)
- [ ] **MIG-09**: atom_meta_agent.py verified using LLMService (already using it)

### BYOKHandler Standardization

- [ ] **STD-01**: All 59 files importing BYOKHandler updated to use LLMService
- [ ] **STD-02**: Core service files updated (8 files: episode segmentation, workflow engine, etc.)
- [ ] **STD-03**: Agent system files updated (5 files: meta-agent, graphrag, etc.)
- [ ] **STD-04**: API routes files updated (3 files: competitor analysis, learning plans, mobile)
- [ ] **STD-05**: Tool files updated (1 file: platform management)
- [ ] **STD-06**: Deprecation warnings added to direct BYOKHandler usage
- [ ] **STD-07**: Migration documentation provided for developers

### Enhanced Observability

- [ ] **OBS-01**: LLMService tracks all LLM calls (provider, model, tokens, cost)
- [ ] **OBS-02**: Metrics aggregation by provider and model (usage, cost, latency)
- [ ] **OBS-03**: Response caching implemented for common queries
- [ ] **OBS-04**: Cache-aware routing integrated with LLMService
- [ ] **OBS-05**: Telemetry dashboard for LLM operations monitoring

### Testing & Documentation

- [ ] **TEST-01**: Unit tests for all LLMService methods (streaming, structured output, tiers)
- [ ] **TEST-02**: Integration tests for each migrated file (39 test files updated)
- [ ] **TEST-03**: Property-based tests for LLM invariants (Hypothesis)
- [ ] **TEST-04**: Performance benchmarks (before/after migration)
- [ ] **TEST-05**: API reference documentation for LLMService
- [ ] **TEST-06**: Migration guide for developers (code examples, patterns)
- [ ] **TEST-07**: Troubleshooting guide for common issues

## v2 Requirements

Deferred to future milestone. Not in v6.0 scope.

### Future Enhancements
- **FUTURE-01**: Multi-tenant LLM service isolation
- **FUTURE-02**: Custom model fine-tuning integration
- **FUTURE-03**: Edge deployment support
- **FUTURE-04**: Real-time streaming governance

## Out of Scope

| Feature | Reason |
|---------|--------|
| Breaking changes to BYOKHandler | Maintain backward compatibility during transition |
| New LLM providers | Focus on consolidation, not expansion |
| Provider-specific features | Unified interface only, use lowest common denominator |
| Database schema changes | No DB changes required for this migration |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LLM-01 through LLM-05 | Phase 222 | Pending |
| MIG-01 through MIG-09 | Phases 223-231 | Pending |
| STD-01 through STD-07 | Phases 232-240 | Pending |
| OBS-01 through OBS-05 | Phase 241 | Pending |
| TEST-01 through TEST-07 | Phases 242-243 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: TBD
- Unmapped: TBD (roadmap not created yet)

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after initial definition*
