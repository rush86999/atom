# Atom 80% Test Coverage Initiative

## What This Is

A comprehensive testing initiative to achieve 80% code coverage across the Atom AI-powered business automation platform, with special focus on AI-related components (LLM integration, agent governance, episodic memory, social layer, community skills, local agent, IM adapters). The milestone covers all testing approaches: unit tests, integration tests, and property-based tests using Hypothesis.

## Core Value

**Critical AI system paths are thoroughly tested and validated before production deployment.**

If everything else fails, the following must have comprehensive test coverage:
- Agent governance and maturity-based routing (STUDENT → AUTONOMOUS)
- LLM integration and multi-provider routing
- Episodic memory creation, retrieval, and graduation
- Social layer communication and feed management
- Community skills parsing, sandboxing, and execution
- Local agent shell/file access with security boundaries
- IM adapter webhook handling and message routing

## Requirements

### Validated

<!-- OpenClaw Integration features delivered but need coverage -->
- ✓ IM adapters (Telegram/WhatsApp) — implemented, needs tests
- ✓ Local agent (God Mode) — implemented, needs tests
- ✓ Social layer (Moltbook) — implemented, needs tests
- ✓ Simplified installer — implemented, needs tests
- ✓ Community skills integration — implemented, needs tests
- ✓ Property-based testing framework (Hypothesis) — existing
- ✓ Integration test infrastructure — existing

### Active

<!-- 80% coverage milestone -->
- [ ] **Phase 1: Measure baseline** — Run coverage report, identify gaps in AI components
- [ ] **Phase 2: LLM integration coverage** — Test multi-provider routing, streaming, token management, error handling
- [ ] **Phase 3: Agent governance coverage** — Test maturity routing, permissions, graduation, context resolution
- [ ] **Phase 4: Episodic memory coverage** — Test segmentation, retrieval, lifecycle, graduation integration
- [ ] **Phase 5: Social layer coverage** — Test post generation, PII redaction, communication, channels
- [ ] **Phase 6: Community skills coverage** — Test parsing, adaptation, sandbox, registry, security scanning
- [ ] **Phase 7: Local agent coverage** — Test shell execution, directory permissions, command whitelist, security
- [ ] **Phase 8: IM adapters coverage** — Test webhook handling, governance routing, rate limiting, audit logging
- [ ] **Property-based tests** — Add Hypothesis tests for system invariants (database, API contracts, state machines)
- [ ] **Integration tests** — Test cross-service workflows (agent → LLM → memory → social)
- [ ] **Fuzzy tests** — Test input validation and security boundaries

### Out of Scope

<!-- Explicit boundaries -->
- **E2E UI testing** — Requires Playwright/Cypress, separate tooling, defer to v2
- **Load testing** — Performance and scalability, defer to v2
- **Chaos engineering** — Resilience testing, defer to v2
- **Visual regression** — UI snapshot testing, defer to v2
- **Frontend components** — React components tested separately (if at all)

## Context

**Current State (Post-OpenClaw Integration):**
- 5 major features delivered (IM adapters, local agent, social layer, installer, community skills)
- Test infrastructure exists (pytest, Hypothesis, pytest-cov)
- Property-based testing framework in place (~28 existing tests)
- Coverage baseline unknown (to be measured in Phase 1)

**AI Components Requiring Coverage:**

**LLM & Intelligence:**
- `core/llm/` - Multi-provider LLM routing (OpenAI, Anthropic, DeepSeek, Gemini)
- `core/llm_usage_tracker.py` - Token tracking and cost management
- `core/business_intelligence.py` - Analytics and insights
- `core/communication_intelligence.py` - Message intelligence

**Agent System:**
- `core/agent_governance_service.py` - Maturity routing (STUDENT → AUTONOMOUS)
- `core/agent_execution_service.py` - Agent execution orchestration
- `core/agent_graduation_service.py` - Graduation readiness scoring
- `core/agent_context_resolver.py` - Context resolution for agent requests
- `core/agent_communication.py` - Agent-to-agent event bus
- `core/agent_social_layer.py` - Social feed management
- 15+ additional agent modules

**Episodic Memory:**
- `core/episode_segmentation_service.py` - Automatic episode creation
- `core/episode_retrieval_service.py` - Memory retrieval (temporal, semantic, sequential)
- `core/episode_lifecycle_service.py` - Episode lifecycle management
- `core/episode_integration.py` - Integration with agent operations

**Community Skills:**
- `core/skill_parser.py` - SKILL.md parsing with lenient frontmatter
- `core/skill_adapter.py` - LangChain BaseTool wrapping
- `core/skill_sandbox.py` - Docker sandbox isolation
- `core/skill_registry_service.py` - Skill import and management
- `core/skill_security_scanner.py` - LLM-based security scanning

**Local Agent:**
- `core/local_agent_service.py` - Host process orchestration
- `core/directory_permission.py` - Maturity-based directory access
- `core/command_whitelist.py` - Command category enforcement
- `core/host_shell_service.py` - Shell execution with security

**Social Layer:**
- `core/social_post_generator.py` - GPT-4.1 mini NLG for posts
- `core/pii_redactor.py` - Microsoft Presidio for PII removal
- `core/agent_communication.py` - Redis pub/sub for horizontal scaling

**IM Adapters:**
- `core/im_governance_service.py` - Webhook verification, rate limiting
- Telegram webhook routes, signature verification
- WhatsApp webhook routes, business verification

**Testing Framework:**
- pytest 7.4+ with async support
- Hypothesis 6.92+ for property-based testing
- pytest-cov for coverage reporting
- pytest-asyncio for async test support

## Constraints

- **Quality Standard**: 80% coverage is the target (not arbitrary, but defensible quality bar)
- **Focus Area**: AI-related components (highest risk and complexity)
- **Test Types**: Unit, integration, and property-based tests (all three approaches)
- **Timeline**: Flexible - quality matters more than speed
- **Priority**: Critical paths first (governance, security, AI operations)
- **Performance**: Test suite should run in reasonable time (<30 min preferred)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|--------|
| Measure baseline first | Can't improve what you don't measure | — Pending |
| Focus on AI components | Highest complexity and risk areas | — Pending |
| All three test approaches | Unit (fast), integration (workflows), property-based (edge cases) | — Pending |
| Property-based for invariants | Catches edge cases unit tests miss | — Pending |
| Test new OpenClaw features | 5 major features just delivered, need validation | — Pending |
| Coverage over line count | 80% coverage of critical paths > 100% of trivial code | — Pending |

---
*Last updated: 2026-02-17 after OpenClaw Integration completion*
