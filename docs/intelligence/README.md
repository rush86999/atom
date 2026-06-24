# Intelligence & Memory Systems

AI capabilities, knowledge management, and cognitive systems for Atom agents with 2026 Enhancement Plan integration.

## 📚 Quick Navigation

**Start Here**: [Intelligence Overview](overview.md) - Complete intelligence documentation

### Core Intelligence Systems

#### 🧠 Memory & Learning
- **[Episodic Memory](episodic-memory.md)** - Agent learning framework with POMDP (2026 enhanced) ✨
- **[Episodic Memory Quick Start](episodic-quickstart.md)** - Get started with episodic memory
- **[Memory Integration](memory-integration.md)** - Memory system integration guide
- **[Context Memory (Per-Turn Fact Extraction)](../architecture/CONTEXT_MEMORY.md)** - Hermes-style durable-fact extraction; two-tier recall; extraction-first over compression-first ✨

#### ✨ Self-Evolution (Enhanced 2026)
- **[Self-Evolution & Reflection Pool](self-evolution.md)** - Agents learn from mistakes and improve
  - Reflection Pool (critique-based storage)
  - Memento-Skills (generate skills from failures)
  - AlphaEvolver (optimize existing skills)
  - **Arbor Framework Integration** ✨ NEW: CodeHypothesisNode for skill evolution

#### 🌐 Knowledge & Reasoning (Enhanced 2026)
- **[GraphRAG & Entity Types](graphrag.md)** - Knowledge graph with multi-hop expansion ✨
- **[World Model & JIT Facts](../world-model-guide.md)** - Knowledge management
- **[JIT Fact Provision](jit-facts.md)** - Real-time fact verification with citations
- **[Vector Embeddings](vector-embeddings.md)** - Semantic search infrastructure

#### 🐛 Debugging
- **[Debug Quick Start](debug-quickstart.md)** - Debug system setup
- **[Debug System](debug-system.md)** - Debug architecture

#### 🌳 Optimization (NEW 2026)
- **[Arbor Framework](../ARBOR_FRAMEWORK.md)** - Hypothesis Tree Refinement (HTR) ✨ NEW
  - CodeHypothesisNode for code generation optimization
  - WorkflowHypothesisNode for orchestration optimization
  - RoutingHypothesisNode for LLM routing optimization
  - POMDP integration for action space exploration

## 🚀 2026 Enhancement Plan Integration

All intelligence systems have been enhanced through the 2026 Enhancement Plan:

### Phase 1: Enhanced Episodic Memory & Graduation ✅ COMPLETE
- **POMDP Memory Framework**: Write-manage-read loop for agent learning
- **Memory Consolidation**: Offline processing (inspired by human sleep)
- **Experience-Driven Graduation**: Quality-weighted episodes (20% improvement)

**See**: [episodic-memory.md](episodic-memory.md) - Complete POMDP documentation

### Phase 2: GraphRAG Enhancement ✅ COMPLETE
- **Multi-Hop Expansion**: Cue-driven activation for entity relationships
- **Dynamic Graph Construction**: Incremental updates (no full rebuild)
- **Community Detection**: Leiden algorithm for entity clustering

**See**: [graphrag.md](graphrag.md) - Complete GraphRAG documentation with 2026 enhancements

### Phase 3: Learning-Based LLM Routing ✅ COMPLETE
- **RouteLLM Training**: Preference data collection for router optimization
- **Predictive Cache Warming**: Pre-load frequently-used queries
- **15% Cost Reduction**: Additional savings on top of existing cache

**See**: [../architecture/COGNITIVE_TIER_SYSTEM.md](../architecture/COGNITIVE_TIER_SYSTEM.md) - Complete routing documentation

### Arbor Framework Integration ✨ NEW
- **POMDP Actions**: Hypothesis nodes form action space in POMDP framework
- **Observation Learning**: Validation results feed into memory quality assessment
- **GraphRAG Constraints**: Failed hypotheses become negative constraints
- **Routing Optimization**: Arbor optimizes LLM selection for hypothesis generation

**See**: [../ARBOR_FRAMEWORK.md](../ARBOR_FRAMEWORK.md) - Complete Arbor documentation

## 🎯 Key Features

### Episodic Memory (Enhanced 2026)
- **Hybrid Storage**: PostgreSQL (hot) + LanceDB (cold)
- **Retrieval Modes**: Temporal (~10ms), Semantic (~50-100ms), Sequential, Contextual
- **Graduation Integration**: Episodes track agent learning progress
- **Canvas Integration**: Canvas presentations linked to episodes
- **POMDP Framework**: Formal write-manage-read loop with observation/action spaces
- **Memory Consolidation**: Offline processing for experience-driven learning

### Self-Evolution (Enhanced 2026)
- **Reflection Pool**: Vector database of agent critiques
- **Memento-Skills**: Auto-generate skills from failure patterns
- **AlphaEvolver**: Optimize skills through mutation
- **Maturity Gated**: INTERN+ for critiques, SUPERVISED+ for optimization
- **Arbor Integration**: CodeHypothesisNode validates skill generation hypotheses

### GraphRAG (Enhanced 2026)
- **PostgreSQL-Backed**: Recursive CTE traversal (<100ms)
- **Multi-Hop Queries**: Cue-driven activation for entity relationships
- **Dynamic Construction**: Incremental updates (no full rebuild required)
- **Canonical Entities**: 6 built-in types (user, workspace, team, task, ticket, formula)
- **Custom Types**: Dynamic entity type creation with JSON Schema
- **Bidirectional Sync**: Graph ↔ Database synchronization
- **Community Detection**: Leiden algorithm for entity clustering

### Arbor Framework (NEW 2026)
- **Tree-Based Refinement**: Hypothesis Tree Refinement (HTR) for optimization
- **Multi-Domain Support**: Code, workflow, and routing hypothesis nodes
- **MCTS Selection**: UCB1 formula for exploration/exploitation balance
- **Budget Enforcement**: Tier-based limits (Free, Solo, Enterprise)
- **Cumulative Learning**: Cross-session negative constraints and insights

## 📖 Related Documentation

### 2026 Enhancements
- **[ARBOR_FRAMEWORK.md](../ARBOR_FRAMEWORK.md)** - Arbor Framework complete guide ✨ NEW
- **[ATOM_ENHANCEMENT_PLAN.md](../ATOM_ENHANCEMENT_PLAN.md)** - 2026 Enhancement Plan
- **[VALIDATION_METRICS.md](../backend/docs/VALIDATION_METRICS.md)** - Performance metrics

### Agent Integration
- **[Agent Graduation](../agents/graduation.md)** - Promotion framework
- **[Auto-Dev Guide](../guides/AUTO_DEV_USER_GUIDE.md)** - Self-evolving agents
- **[Canvas Integration](../canvas/README.md)** - Canvas presentations in memory

### System Integration
- **[Cognitive Tier System](../architecture/COGNITIVE_TIER_SYSTEM.md)** - LLM routing optimization
- **[GraphRAG & Entity Types](graphrag.md)** - Knowledge graph and entity extraction

## 🚀 Quick Start

```python
# Episodic Memory with POMDP
from core.memory.pomdp_memory_framework import POMDPMemoryFramework
pomdp = POMDPMemoryFramework()

# Arbor Framework for optimization
from core.hypothesis_tree import HypothesisTree, OptimizationNode
tree = HypothesisTree(task_type="workflow")

# GraphRAG with multi-hop
from core.graphrag.multi_hop_expansion import MultiHopExpander
expander = MultiHopExpander()

# Self-Evolution with Arbor
from core.reflection_service import ReflectionService
```

---

*Last Updated: June 18, 2026*
