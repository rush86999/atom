# Phase 223: Critical Migration Part 1 - Context

**Gathered:** March 22, 2026
**Status:** Ready for planning

## Phase Boundary

Migrate three critical backend services from direct OpenAI/Anthropic API calls to the unified LLMService:
1. `embedding_service.py` - Currently uses AsyncOpenAI client
2. `graphrag_engine.py` - Currently uses OpenAI client
3. `skill_security_scanner.py` - LLM-based security scanning

All three services must pass existing tests with no regression in functionality.

## Implementation Decisions

### Migration Strategy
- **Parallel migration tracks**: Each service migrates independently using existing LLMService capabilities (no need to add embedding methods first)
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

None—discussion stayed within phase scope.

---

*Phase: 223-critical-migration-part-1*
*Context gathered: 2026-03-22*
