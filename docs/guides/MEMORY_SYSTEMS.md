# Memory Systems — Concept Guide

> **Purpose**: Understand how Atom agents remember, learn, and retrieve knowledge.
> **Audience**: AI engineers, architects, power users
> **Read time**: ~15 minutes

---

## The Big Picture: Three Memory Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTEXT WINDOW (LLM)                     │
│  Current conversation + retrieved facts + tool results      │
└─────────────────────────────────────────────────────────────┘
                              ↑
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  TIER 1: SQL  │    │  TIER 2:      │    │  TIER 3:      │
│  (PostgreSQL) │    │  LanceDB      │    │  GraphRAG     │
│  Sub-ms       │    │  (Vector)     │    │  (Knowledge   │
│  FTS5 + exact │    │  Semantic     │    │   Graph)      │
│  fact lookup  │    │  similarity   │    │  Multi-hop    │
└───────────────┘    └───────────────┘    └───────────────┘
```

### Turn-time unification (2026-08): the Memory Context Assembler

All three tiers — plus communication memory (emails/Slack/WhatsApp/Teams)
and learning episodes — are now fused into one bounded `RELEVANT MEMORY`
block at the moment a user talks to an agent, on every chat/IM surface
(`core/memory_context_assembler.py`, injected by the ChatOrchestrator).
Legs run in parallel with per-leg fault isolation and timeouts; a startup
warm-up preloads embedding models so first turns are fast. Conversational
records from ANY integration reach the same store via shape-based routing
(`IngestionPipelineService._is_communication_record`). Toggle with
`MEMORY_CONTEXT_ASSEMBLY` (default on). Design and gap inventory:
[`architecture/AGENT_MEMORY_UNIFICATION_PLAN.md`](../architecture/AGENT_MEMORY_UNIFICATION_PLAN.md).

---

## Tier 1: Durable Facts (SQL + FTS5)

**What**: Extracted facts per conversation turn — the "source of truth"  
**Latency**: < 1ms  
**Query**: Exact match, keyword (FTS5), or `WHERE` clauses

### How It Works

```
User: "Our Q3 budget is $2.5M"
     ↓
Per-turn extractor (fast model, 1 call/turn)
     ↓
Fact: {category: "budget", value: "$2.5M", period: "Q3", confidence: 0.95}
     ↓
INSERT INTO turn_facts (session_id, turn_id, category, value, ...)
```

### Categories (Mem0's 5 Durable Types)

| Category | Examples | Use Case |
|----------|----------|----------|
| **User** | Preferences, role, constraints | Personalization |
| **Session** | Current goals, context, temp facts | Continuity |
| **World** | Business facts, policies, metrics | Grounding |
| **Procedural** | Workflows, SOPs, how-to | Task execution |
| **Semantic** | Concepts, relationships, definitions | Reasoning |

### Key Features

- **`sync_turn` hook** — Fire-and-forget extraction after each turn
- **`on_pre_compress` hook** — Queue extraction before context truncation (free, additive)
- **Truncation boundary protection** — Facts never lost to context window limits
- **Maturity-gated** — STUDENT agents don't write facts
- **Circuit breaker** — 5 failures → 120s cooldown (never raises)

---

## Tier 2: Semantic Recall (LanceDB)

**What**: Vector embeddings of facts + episodes for similarity search  
**Latency**: 10–20ms (FastEmbed)  
**Query**: "What did we discuss about budget last month?"

### When It's Used

1. **Fallback** when SQL exact match returns nothing
2. **Semantic queries** — "similar to X", "related to Y"
3. **Episode retrieval** — "Show me past runs like this one"

### Configuration

```bash
TURN_FACT_VECTOR_RECALL_ENABLED=true    # Default ON (R72)
TURN_FACT_EXTRACTION_ENABLED=true       # Default ON (R72)
TURN_FACT_MAX_PER_TURN=5                # Cap per turn
TURN_FACT_QUEUE_MAXSIZE=100             # Backpressure buffer
```

---

## Tier 3: GraphRAG (Knowledge Graph)

**What**: Entities + relationships extracted from documents + episodes  
**Latency**: 50–80ms  
**Query**: Multi-hop — "How does Project Alpha relate to Q3 budget?"

### Canonical Entity Types (6)

| Type | Examples |
|------|----------|
| **ORGANIZATION** | Companies, teams, departments |
| **PERSON** | Users, stakeholders, contacts |
| **PROJECT** | Initiatives, epics, campaigns |
| **DOCUMENT** | Contracts, specs, reports |
| **CONCEPT** | Metrics, KPIs, methodologies |
| **EVENT** | Meetings, launches, incidents |

### Key Capabilities

- **Multi-hop expansion** — Scored recursive CTEs (depth 1–3)
- **Leiden community detection** — Clusters for summarization
- **JIT verification** — Facts checked on-demand with citations
- **Hybrid search** — Graph + vector + keyword combined

> 📖 Deep dive: [GraphRAG](../intelligence/graphrag.md) | [Context Memory](../architecture/CONTEXT_MEMORY.md)

---

## Episodic Memory (Experience-Driven Learning)

**What**: Full conversation + tool use + outcomes stored as episodes  
**Purpose**: Agents learn from past executions (successes & failures)

### Episode Structure

```
Episode
├── Segments (turns grouped by topic)
├── Outcome (success/failure/partial)
├── Verified flag (human-validated)
├── Agent maturity at time
└── Canvas presentations (if any)
```

### Retrieval Modes (4)

| Mode | Query | Use Case |
|------|-------|----------|
| **Temporal** | "Last 5 runs" | Recent context |
| **Semantic** | "Similar to current task" | Analogical reasoning |
| **Outcome-filtered** | "Failed runs only" | Avoid past mistakes |
| **Graduation-gated** | "Gold-tier episodes only" | High-confidence learning |

### Graduation Pipeline

```
10 clean episodes  →  BRONZE  →  STUDENT → INTERN
25 clean episodes  →  SILVER  →  INTERN → SUPERVISED
50 clean episodes  →  GOLD    →  SUPERVISED → AUTONOMOUS
```

**Clean** = no governance violations + verified outcome = success

---

## Self-Evolution (Reflection Pool)

> **New in 2026**: Agents critique their own failures and generate improvements.

```
Failure Episode
     ↓
Reflection Pool stores: {mistake, critique, suggested_fix}
     ↓
Memento-Skill Generator → New skill proposal
     ↓
AlphaEvolver optimizes existing skills
     ↓
Human reviews → Install → Agent graduates
```

### Components

| Component | Purpose |
|-----------|---------|
| **Reflection Pool** | Vector store of (mistake, critique) pairs |
| **Memento-Skills** | Auto-generated skills from failures |
| **AlphaEvolver** | Genetic optimization of skill code |
| **Graduation Gate** | Human approval before install |

---

## Memory Integration in Agent Loop

```
User Request
     ↓
1. Classify complexity + intent
     ↓
2. Retrieve context:
   - Tier 1: Exact fact match (sub-ms)
   - Tier 2: Semantic similarity (if needed)
   - Tier 3: Graph multi-hop (if complex)
   - Episodes: Similar past runs (outcome-filtered)
     ↓
3. Build prompt with retrieved context
     ↓
4. LLM + Tools execute
     ↓
5. Extract facts (sync_turn)
6. Store episode (outcome + verified)
7. Check graduation eligibility
```

---

## Configuration Summary

```bash
# Per-turn fact extraction (Tier 1 + 2)
TURN_FACT_EXTRACTION_ENABLED=true
TURN_FACT_PRE_COMPRESS_ENABLED=true
TURN_FACT_VECTOR_RECALL_ENABLED=true
TURN_FACT_MAX_PER_TURN=5
TURN_FACT_QUEUE_MAXSIZE=100

# Episodic memory
EPISODIC_MEMORY_ENABLED=true
EPISODE_SEGMENTATION_ENABLED=true
AGENT_GRADUATION_ENABLED=true

# GraphRAG
GRAPHRAG_ENABLED=true
GRAPHRAG_COMMUNITY_DETECTION=true
JIT_FACT_VERIFICATION=true

# Self-evolution
SELF_EVOLUTION_ENABLED=true
REFLECTION_POOL_ENABLED=true
```

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Facts not persisting | Extractor not running | Check `TURN_FACT_EXTRACTION_ENABLED`, verify model available |
| Semantic recall empty | LanceDB not populated | Verify `TURN_FACT_VECTOR_RECALL_ENABLED`, run embedding job |
| Episodes not linking | Segmentation failed | Check `EPISODE_SEGMENTATION_ENABLED`, review segmenter logs |
| GraphRAG missing entities | Extractor not run | Run `build_graphrag` job, check entity extractor |
| Agent not graduating | Unverified outcomes | Ensure `outcome_verified=true` on executions |
| Memory growing unbounded | No retention policy | Configure `EPISODE_RETENTION_DAYS`, run sweep job |

---

## Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| Tier 1 fact lookup | < 1ms | 0.2ms P99 |
| Tier 2 semantic search | < 20ms | 10–20ms |
| Tier 3 graph multi-hop | < 100ms | 50–80ms |
| Episode retrieval | < 50ms | 20ms |
| Fact extraction/turn | < 500ms | 200ms |

---

## Related Documentation

- [Context Memory](../architecture/CONTEXT_MEMORY.md) — Architecture + hooks
- [Episodic Memory](../intelligence/episodic-memory.md) — Framework details
- [GraphRAG](../intelligence/graphrag.md) — Knowledge graph
- [JIT Fact Provision](../intelligence/jit-facts.md) — Verification
- [Self-Evolution](../intelligence/self-evolution.md) — Reflection Pool
- [Hermes Comparison](../architecture/HERMES_COMPARISON.md) — Design decisions
- [Agent Graduation](../agents/graduation.md) — Promotion criteria
- [Memory Tool](../tools/memory_tool.py) — Agent-facing API

---

*Last Updated: August 2026*