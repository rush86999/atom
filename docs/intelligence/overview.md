# Intelligence & Memory Documentation

AI capabilities, knowledge management, and cognitive systems.

## Core Intelligence

### LLM & Cognition
- **BYOK V6 Migration Guide** - LLM service migration (if exists)
- **Cognitive Tier System** - 5-tier intelligent LLM routing (if exists in root, otherwise reference)

### World Model & Knowledge
- **AI World Model** - Knowledge representation
- **GraphRAG and Entity Types** - Graph-based intelligence
- **[GraphRAG Ported](../archive/legacy/GRAPHRAG_PORTED.md)** - GraphRAG implementation

### Business Facts & Citations
- **JIT Fact Provision System** - Just-in-time fact retrieval
- **Citation System Guide** - Citation management
- **[JIT Verification Quickstart](../archive/legacy/JIT_VERIFICATION_QUICKSTART.md)** - Quick setup
- **[JIT Verification Agent Compliance](../archive/legacy/JIT_VERIFICATION_AGENT_COMPLIANCE.md)** - Compliance checks
- **[JIT Verification Cache](../archive/legacy/JIT_VERIFICATION_CACHE.md)** - Caching layer

## Memory & Learning

### Episodic Memory
- **[Episodic Memory Implementation](episodic-memory.md)** - Memory system overview
- **[Episodic Memory Quick Start](episodic-quickstart.md)** - Getting started
- **[Canvas & Feedback Episodic Memory](../canvas/feedback-memory.md)** - Canvas-linked memory

### Self-Evolution ✨ NEW
- **[Self-Evolution & Reflection Pool](self-evolution.md)** - Agents learn from mistakes, generate skills, optimize capabilities
  - Reflection Pool (critique-based mistakes storage)
  - Memento-Skills (generate new skills from failures)
  - AlphaEvolver (optimize existing skills)
  - Integration with episodic memory and graduation

### Agent Learning
- **[Agent Graduation Guide](../agents/graduation.md)** - Agent promotion system
- **Student Agent Training** - Training workflow
- **🆕 Enhanced Governance Integration** - Three-layer governance with intelligence systems

### Enhanced Governance (2026) ✨
- **[Three-Layer Governance](../governance/)** - OPERATIONAL, TACTICAL, STRATEGIC decision layers
- **[Policy Engine](../governance/)** - Context-aware policy evaluation with intelligence data
- **[Governance-as-a-Service](../governance/)** - Multi-tenant governance API

**Integration with Intelligence:**
- Episode data informs governance graduation decisions
- Policy engine uses memory retrieval for context-aware decisions
- Knowledge graph data validates strategic governance choices
- See [VALIDATION_METRICS.md](../../backend/docs/VALIDATION_METRICS.md) for performance metrics

## Canvas Intelligence

### Canvas Summaries
- **[LLM Canvas Summaries](../canvas/llm-summaries.md)** - AI-generated summaries
- **Canvas Agent Learning Integration** - Learning from canvas

### Canvas State
- **[Canvas AI Accessibility](../canvas/ai-accessibility.md)** - AI-readable canvas state
- **Canvas State API** - State API
- **Canvas Quick Reference** - Quick reference
- **Canvas Recording Implementation** - Recording system
- **[Specialized Canvas Types](../archive/SPECIALIZED_CANVAS_TYPES_IMPLEMENTATION_COMPLETE.md)** - Custom components (archived)
- **Recording Review Integration** - Review workflow

## Error Handling & Debugging

### AI Debug System
- **AI Debug Quick Start** - Debug setup
- **AI Debug System** - Debug architecture

### Error Handling
- **Error Handling Guidelines** - Error patterns
- **[Error Handling Standard](../archive/legacy/ERROR_HANDLING_STANDARD.md)** - Standards

## Supervision & Multi-Level Learning

### Supervision
- **[Supervision Implementation](../agents/supervision-implementation.md)** - Supervision levels and real-time monitoring

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
- **Memory**: Episodic Memory
- **Knowledge**: World Model
- **Graph**: GraphRAG
- **Facts**: JIT Fact Provision

### By Use Case
- **Learning from Interactions**: Memory Integration Guide
- **Self-Evolution & Mistakes**: [Self-Evolution & Reflection Pool](self-evolution.md) ✨ NEW
- **Storing Business Knowledge**: Citation System Guide
- **AI Summaries**: [LLM Canvas Summaries](../canvas/llm-summaries.md)
- **Error Recovery**: Error Handling Guidelines

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

- **[Agent System](../agents/)** - Agent governance and learning
- **Auto-Dev User Guide** - Self-evolving agent capabilities
- **[Canvas Documentation](../canvas/)** - Canvas presentations
- **[API Documentation](../API/)** - Intelligence API endpoints

---

*Last Updated: April 12, 2026*
