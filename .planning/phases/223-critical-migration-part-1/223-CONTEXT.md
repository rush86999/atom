# Phase 223: Critical Migration Part 1 - Context

**Gathered:** March 22, 2026
**Status:** Ready for planning

## Guiding Vision

**Unify ALL LLM calls under LLMService API** — including embeddings, voice, and any other LLM interactions. This achieves:
- **Centralized BYOK** — Single point for all provider Bring Your Own Key configuration
- **Unified cost tracking** — All token usage and costs tracked through one service
- **Easier maintenance** — One interface to update, monitor, and optimize

Phase 223 is the first step toward this vision, migrating three critical services.

## Phase Boundary

Migrate three critical backend services from direct OpenAI/Anthropic API calls to the unified LLMService:
1. `embedding_service.py` - Currently uses AsyncOpenAI client
2. `graphrag_engine.py` - Currently uses OpenAI client
3. `skill_security_scanner.py` - LLM-based security scanning

All three services must pass existing tests with no regression in functionality.

## Implementation Decisions

### Migration Strategy
- **Comprehensive unification**: LLMService becomes the single source of truth for ALL LLM interactions (embeddings, chat, streaming, structured output, future voice)
- **Parallel migration tracks**: Each service migrates independently using existing LLMService capabilities (add embedding methods to LLMService if needed)
- **Sequential dependency**: Plans execute in order (223-01 → 223-02 → 223-03 → 223-04) with 223-01 completing before subsequent migrations start
- **Verify after each plan**: Run all existing tests after each plan completion. If tests fail, stop and fix before proceeding to next plan
- **Maintain existing interfaces**: Keep all original service methods and signatures unchanged—only swap internal implementation to use LLMService

### Claude's Discretion
- Determine whether 223-01 (add embedding support to LLMService) is actually needed based on what embedding_service.py currently requires
- Choose specific test execution strategy (full test suite vs. targeted tests) based on test suite speed
- Handle any edge cases where LLMService doesn't perfectly match existing functionality

## Specific Ideas

No specific requirements—use standard migration patterns.

## Deferred Ideas

- **Voice/audio LLM support** — Add to LLMService API as part of the unified vision (future phase)
- **Cost tracking dashboard** — Leverage unified LLMService cost data for observability (future milestone)

---

*Phase: 223-critical-migration-part-1*
*Context gathered: 2026-03-22*
