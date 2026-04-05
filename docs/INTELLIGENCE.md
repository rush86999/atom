# Intelligence & Memory Documentation

AI capabilities, knowledge management, and cognitive systems.

## Core Intelligence

### LLM & Cognition
- **[BYOK V6 Migration Guide](BYOK_V6_MIGRATION_GUIDE.md)** - LLM service migration (if exists)
- **[Cognitive Tier System](COGNITIVE_TIER_SYSTEM.md)** - 5-tier intelligent LLM routing (if exists in root, otherwise reference)

### World Model & Knowledge
- **[AI World Model](ai-world-model.md)** - Knowledge representation
- **[GraphRAG and Entity Types](GRAPHRAG_AND_ENTITY_TYPES.md)** - Graph-based intelligence
- **[GraphRAG Ported](GRAPHRAG_PORTED.md)** - GraphRAG implementation
- **[Document Processing Pipeline](DOCUMENT_PROCESSING_PIPELINE.md)** - Document ingestion

### Business Facts & Citations
- **[JIT Fact Provision System](JIT_FACT_PROVISION_SYSTEM.md)** - Just-in-time fact retrieval
- **[Citation System Guide](CITATION_SYSTEM_GUIDE.md)** - Citation management
- **[JIT Verification Quickstart](JIT_VERIFICATION_QUICKSTART.md)** - Quick setup
- **[JIT Verification Agent Compliance](JIT_VERIFICATION_AGENT_COMPLIANCE.md)** - Compliance checks
- **[JIT Verification Cache](JIT_VERIFICATION_CACHE.md)** - Caching layer

## Memory & Learning

### Episodic Memory
- **[Episodic Memory Implementation](EPISODIC_MEMORY_IMPLEMENTATION.md)** - Memory system overview
- **[Episodic Memory Quick Start](EPISODIC_MEMORY_QUICK_START.md)** - Getting started
- **[Memory Integration Guide](MEMORY_INTEGRATION_GUIDE.md)** - Integration patterns
- **[Canvas & Feedback Episodic Memory](CANVAS_FEEDBACK_EPISODIC_MEMORY.md)** - Canvas-linked memory

### Agent Learning
- **[Agent Graduation Guide](AGENT_GRADUATION_GUIDE.md)** - Agent promotion system
- **[Student Agent Training](STUDENT_AGENT_TRAINING_IMPLEMENTATION.md)** - Training workflow

## Canvas Intelligence

### Canvas Summaries
- **[LLM Canvas Summaries](LLM_CANVAS_SUMMARIES.md)** - AI-generated summaries
- **[Canvas Agent Learning Integration](CANVAS_AGENT_LEARNING_INTEGRATION.md)** - Learning from canvas

### Canvas State
- **[Canvas AI Accessibility](CANVAS_AI_ACCESSIBILITY.md)** - AI-readable canvas state
- **[Canvas State API](CANVAS_STATE_API.md)** - State API
- **[Canvas Quick Reference](CANVAS_QUICK_REFERENCE.md)** - Quick reference
- **[Canvas Recording Implementation](CANVAS_RECORDING_IMPLEMENTATION.md)** - Recording system
- **[Specialized Canvas Types](SPECIALIZED_CANVAS_TYPES_IMPLEMENTATION_COMPLETE.md)** - Custom components (archived)
- **[Recording Review Integration](RECORDING_REVIEW_INTEGRATION.md)** - Review workflow

## Error Handling & Debugging

### AI Debug System
- **[AI Debug Quick Start](AI_DEBUG_QUICK_START.md)** - Debug setup
- **[AI Debug System](AI_DEBUG_SYSTEM.md)** - Debug architecture

### Error Handling
- **[Error Handling Guidelines](ERROR_HANDLING_GUIDELINES.md)** - Error patterns
- **[Error Handling Standard](ERROR_HANDLING_STANDARD.md)** - Standards

## Supervision & Multi-Level Learning

### Supervision
- **[Multi-Level Supervision Implementation](MULTI_LEVEL_SUPERVISION_IMPLEMENTATION.md)** - Supervision levels

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
- **Memory**: [Episodic Memory](EPISODIC_MEMORY_IMPLEMENTATION.md)
- **Knowledge**: [World Model](ai-world-model.md)
- **Graph**: [GraphRAG](GRAPHRAG_AND_ENTITY_TYPES.md)
- **Facts**: [JIT Fact Provision](JIT_FACT_PROVISION_SYSTEM.md)

### By Use Case
- **Learning from Interactions**: [Memory Integration Guide](MEMORY_INTEGRATION_GUIDE.md)
- **Storing Business Knowledge**: [Citation System Guide](CITATION_SYSTEM_GUIDE.md)
- **AI Summaries**: [LLM Canvas Summaries](LLM_CANVAS_SUMMARIES.md)
- **Error Recovery**: [Error Handling Guidelines](ERROR_HANDLING_GUIDELINES.md)

## Performance

| System | Latency | Notes |
|--------|---------|-------|
| Episodic Recall | ~10-100ms | Temporal vs Semantic |
| Knowledge Graph | ~50-80ms | Local search |
| JIT Fact Verification | <500ms | With citation check |
| Canvas Summary | ~2-3s | LLM generation |

## See Also

- **[Agent System](AGENTS.md)** - Agent governance and learning
- **[Canvas Documentation](CANVAS.md)** - Canvas presentations (if exists)
- **[API Documentation](API.md)** - Intelligence API endpoints

---

*Last Updated: April 5, 2026*
