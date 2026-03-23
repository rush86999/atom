# Phase 226: LLM Provider Registry & LUX Integration - Context

**Gathered:** March 22, 2026
**Status:** Needs research before planning

## Phase Boundary

Create an extensible LLM provider registry system with auto-discovery, LUX model integration, and improved API key management.

**Goals:**
1. **Provider Registry System** — Auto-discover models from pricing APIs (LiteLLM, OpenRouter)
2. **LUX Integration** — Add LUX model to BPC (Bits Per Character) routing system
3. **Extensibility** — Make it trivial to add new frontier models as they're released
4. **API Key UI/UX** — Improve user experience for managing API keys

## Implementation Decisions

### Research Needed (Before Planning)
This phase requires significant research before planning:
1. **LiteLLM API** — Understand model pricing API, auto-discovery capabilities
2. **OpenRouter API** — Model catalog, pricing, integration patterns
3. **BPC System** — Current architecture, how routing works, where LUX fits
4. **LUX Model** — What is LUX? Capabilities, pricing, integration requirements
5. **Frontend API Key Management** — Current UI/UX, pain points, improvement opportunities

### Claude's Discretion
- Phase numbering (226 vs new milestone)
- Whether to split into multiple phases (research → provider registry → LUX integration → UI/UX)
- Technology choices for API integrations
- Scope of UI/UX improvements

## Specific Ideas

- **Auto-discovery**: Poll pricing APIs periodically to discover new models
- **Provider Registry**: Central registry of available models with pricing, capabilities, metadata
- **BPC Integration**: LUX model added to routing decisions based on cost/performance
- **Extensibility**: Plugin architecture or config-driven model additions
- **UI/UX**: Dashboard for API keys, provider management, model selection

## Deferred Ideas

None — all ideas are in scope for this phase.

---

*Phase: 226-llm-provider-registry*
*Context gathered: 2026-03-22*

**Next Step:** Run `/gsd:plan-phase 226 --research` to conduct research before planning.
