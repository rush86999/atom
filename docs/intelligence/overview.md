# Intelligence & Memory Documentation

AI capabilities, knowledge management, and cognitive systems.

## Core Intelligence

### LLM & Cognition
- **Cognitive Tier System** — 5-tier intelligent LLM routing ([architecture/COGNITIVE_TIER_SYSTEM.md](../architecture/COGNITIVE_TIER_SYSTEM.md))
- **Learning LLM Router** — Per-model satisfaction predictors ([architecture/LEARNING_LLM_ROUTER.md](../architecture/LEARNING_LLM_ROUTER.md))

### World Model & Knowledge
- **AI World Model** — Knowledge representation
- **GraphRAG & Entity Types** — Graph-based intelligence ([intelligence/graphrag.md](graphrag.md))

### Business Facts & Citations
- **JIT Fact Provision System** — Just-in-time fact retrieval ([intelligence/jit-facts.md](jit-facts.md))
- **Citation System Guide** — Citation management

## Memory & Learning

### Episodic Memory
- **[Episodic Memory](episodic-memory.md)** — Memory system overview
- **[Episodic Memory Quick Start](episodic-quickstart.md)** — Getting started
- **[Canvas & Feedback Episodic Memory](../canvas/feedback-memory.md)** — Canvas-linked memory

### Self-Evolution ✨ NEW
- **[Self-Evolution & Reflection Pool](self-evolution.md)** — Agents learn from mistakes, generate skills, optimize capabilities
  - Reflection Pool (critique-based mistakes storage)
  - Memento-Skills (generate new skills from failures)
  - AlphaEvolver (optimize existing skills)
  - Integration with episodic memory and graduation

### Agent Learning
- **[Agent Graduation Guide](../agents/graduation.md)** — Agent promotion system
- **Student Agent Training** — Training workflow ([guides/AGENT_MATURITY_GOVERNANCE.md](../guides/AGENT_MATURITY_GOVERNANCE.md))
- **🆕 Enhanced Governance Integration** — Three-layer governance with intelligence systems

### Enhanced Governance (2026) ✨
- **[Three-Layer Governance](../agents/governance.md)** — OPERATIONAL / TACTICAL / STRATEGIC graduation decision layers (wired into the graduation exam and promotion endpoint)
- **[Policy Engine](../agents/governance.md)** — evidence-floor policies derived from readiness thresholds; STRATEGIC (AUTONOMOUS) promotions are human-in-the-loop

**Integration with Intelligence:**
- Episode data informs governance graduation decisions (readiness factors feed policy evaluation)
- Policy decisions cite per-rule evidence reasons in exam failure output

## Canvas Intelligence

### Canvas Summaries
- **[LLM Canvas Summaries](../canvas/llm-summaries.md)** — AI-generated summaries
- **Canvas Agent Learning Integration** — Learning from canvas

### Canvas State
- **[Canvas AI Accessibility](../canvas/ai-accessibility.md)** — AI-readable canvas state
- **Canvas State API** — State API
- **Canvas Quick Reference** — Quick reference
- **Canvas Recording Implementation** — Recording system

## Error Handling & Debugging

### AI Debug System
- **AI Debug Quick Start** — Debug setup
- **AI Debug System** — Debug architecture

### Error Handling
- **Error Handling Guidelines** — Error patterns
- **Error Handling Standardization** — Standards ([architecture/ERROR_HANDLING_STANDARDIZATION.md](../architecture/ERROR_HANDLING_STANDARDIZATION.md))

## Supervision & Multi-Level Learning

### Supervision
- **Agent Governance** — Maturity levels & supervision ([agents/governance.md](../agents/governance.md))

## Key Concepts

### Memory Architecture
```
User Request → World Model → Episodic Memory → Knowledge Graph → LLM Response
```

### Knowledge Types
- **Episodic Memory**: Past experiences and outcomes
- **Business Facts**: Verified truths with citations
- **Knowledge Graph**: Entities and relationships
- **Formulas**: Business logic and calculations

### Intelligence Flow
1. **Input**: User request or data event
2. **Retrieval**: Memory + Knowledge + Facts
3. **Reasoning**: LLM with retrieved context
4. **Learning**: Store experience for future
5. **Graduation**: Update agent maturity

## Quick Links

### By Feature
- **Memory**: [Episodic Memory](episodic-memory.md)
- **Knowledge**: [World Model](world-model.md)
- **Graph**: [GraphRAG](graphrag.md)
- **Facts**: [JIT Fact Provision](jit-facts.md)

### By Use Case
- **Learning from Interactions**: [Memory Integration Guide](../intelligence/memory-integration.md)
- **Self-Evolution & Mistakes**: [Self-Evolution & Reflection Pool](self-evolution.md) ✨ NEW
- **Storing Business Knowledge**: [Citation System Guide](citation-system.md)
- **AI Summaries**: [LLM Canvas Summaries](../canvas/llm-summaries.md)
- **Error Recovery**: [Error Handling Guidelines](error-handling.md)

## Performance

| System | Latency | Notes |
|--------|---------|-------|
| Episodic Recall | ~10-100ms | Temporal vs Semantic |
| Knowledge Graph | ~50-80ms | Local search |
| Reflection Pool | ~50-100ms | Vector similarity search |
| JIT Fact Verification | <500ms | With citation check |
| Canvas Summary | ~2-3s | LLM generation |
| Memento-Skill Generation | ~30-60s | LLM code generation |
| AlphaEvolver Optimization | ~2-5min | Per generation |

## See Also

- **[Agent System](../agents/)** — Agent governance and learning
- **Auto-Dev User Guide** — Self-evolving agent capabilities
- **[Canvas Documentation](../canvas/)** — Canvas presentations
- **[API Documentation](../API/)** — Intelligence API endpoints

---

*Last Updated: August 2026*
