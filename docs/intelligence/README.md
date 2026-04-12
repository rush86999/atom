# Intelligence & Memory Systems

AI capabilities, knowledge management, and cognitive systems for Atom agents.

## 📚 Quick Navigation

**Start Here**: [Intelligence Overview](overview.md) - Complete intelligence documentation

### Core Intelligence Systems

#### 🧠 Memory & Learning
- **[Episodic Memory](episodic-memory.md)** - Agent learning framework with PostgreSQL + LanceDB
- **[Episodic Memory Quick Start](episodic-quickstart.md)** - Get started with episodic memory
- **[Memory Integration](memory-integration.md)** - Memory system integration guide

#### ✨ Self-Evolution (NEW)
- **[Self-Evolution & Reflection Pool](self-evolution.md)** - Agents learn from mistakes and improve
  - Reflection Pool (critique-based storage)
  - Memento-Skills (generate skills from failures)
  - AlphaEvolver (optimize existing skills)

#### 🌐 Knowledge & Reasoning
- **[GraphRAG & Entity Types](graphrag.md)** - Knowledge graph and entity extraction
- **[World Model & JIT Facts](../world-model-guide.md)** - Knowledge management
- **[JIT Fact Provision](jit-facts.md)** - Real-time fact verification with citations
- **[Vector Embeddings](vector-embeddings.md)** - Semantic search infrastructure

#### 🐛 Debugging
- **[Debug Quick Start](debug-quickstart.md)** - Debug system setup
- **[Debug System](debug-system.md)** - Debug architecture

## 🎯 Key Features

### Episodic Memory
- **Hybrid Storage**: PostgreSQL (hot) + LanceDB (cold)
- **Retrieval Modes**: Temporal (~10ms), Semantic (~50-100ms), Sequential, Contextual
- **Graduation Integration**: Episodes track agent learning progress
- **Canvas Integration**: Canvas presentations linked to episodes

### Self-Evolution
- **Reflection Pool**: Vector database of agent critiques
- **Memento-Skills**: Auto-generate skills from failure patterns
- **AlphaEvolver**: Optimize skills through mutation
- **Maturity Gated**: INTERN+ for critiques, SUPERVISED+ for optimization

### GraphRAG
- **PostgreSQL-Backed**: Recursive CTE traversal (<100ms)
- **Canonical Entities**: 6 built-in types (user, workspace, team, task, ticket, formula)
- **Custom Types**: Dynamic entity type creation with JSON Schema
- **Bidirectional Sync**: Graph ↔ Database synchronization

## 📖 Related Documentation

- **[Agent Graduation](../agents/graduation.md)** - Promotion framework
- **[Auto-Dev Guide](../GUIDES/AUTO_DEV_USER_GUIDE.md)** - Self-evolving agents
- **[Canvas Integration](../canvas/README.md)** - Canvas presentations in memory

## 🚀 Quick Start

```python
# Episodic Memory
from core.episode_segmentation_service import EpisodeSegmentationService

# Self-Evolution
from core.reflection_service import ReflectionService

# GraphRAG
from core.graphrag_engine import graphrag_engine
```

---

*Last Updated: April 12, 2026*
