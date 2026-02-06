# JIT Fact Provision System - Real-Time Knowledge Retrieval

**Version**: 1.0
**Last Updated**: February 6, 2026
**Status**: Production Ready

---

## Overview

Atom's **Just-In-Time (JIT) Fact Provision System** delivers real-time, contextually relevant business facts to AI agents during decision-making. Unlike static knowledge bases, JIT retrieval combines semantic search, knowledge graph traversal, and episodic memory to provide agents with the most relevant, up-to-date information exactly when needed.

### Key Capabilities

- **Semantic Fact Retrieval**: Vector similarity search for contextually relevant facts
- **Knowledge Graph Integration**: Relationship traversal for connected knowledge
- **Multi-Source Memory**: Combines business facts, experiences, formulas, and episodes
- **Real-Time Synthesis**: LLM-powered answer generation from retrieved context
- **Performance Optimized**: <100ms retrieval for typical queries
- **Source Attribution**: Every fact includes verifiable citations

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                    JIT Fact Provision System                          │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐         │
│  │    Agent     │────▶│  WorldModel  │────▶│   Fact       │         │
│  │   Request    │     │   Service    │     │  Retrieval   │         │
│  └──────────────┘     └──────────────┘     └──────────────┘         │
│                             │                                          │
│                             ├─────────────────────────────┐            │
│                             │                             │            │
│                             ▼                             ▼            │
│                    ┌──────────────┐             ┌──────────────┐      │
│                    │  Business    │             │  Knowledge   │      │
│                    │   Facts      │             │   Graph      │      │
│                    │  (LanceDB)   │             │  (GraphRAG)  │      │
│                    └──────────────┘             └──────────────┘      │
│                             │                             │            │
│                             ▼                             ▼            │
│                    ┌──────────────┐             ┌──────────────┐      │
│                    │   Vector     │             │  Entity      │      │
│                    │   Search     │             │  Traversal   │      │
│                    └──────────────┘             └──────────────┘      │
│                             │                             │            │
│                             └──────────┬──────────────────┘            │
│                                        ▼                               │
│                             ┌──────────────────┐                       │
│                             │  Context         │                       │
│                             │  Aggregation     │                       │
│                             └──────────────────┘                       │
│                                        │                               │
│                                        ▼                               │
│                             ┌──────────────────┐                       │
│                             │  LLM Synthesis   │                       │
│                             │  (Answer Gen)    │                       │
│                             └──────────────────┘                       │
│                                        │                               │
│                                        ▼                               │
│                             ┌──────────────────┐                       │
│                             │  Agent Response  │                       │
│                             │  with Citations  │                       │
│                             └──────────────────┘                       │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

---

## WorldModelService Implementation

**Location**: `backend/core/agent_world_model.py:58-814`

The `WorldModelService` is the central orchestrator for JIT fact provision, managing multiple memory systems and synthesizing context for agents.

### Initialization

```python
class WorldModelService:
    def __init__(self, workspace_id: str = "default"):
        self.db = get_lancedb_handler(workspace_id)
        self.table_name = "agent_experience"        # Agent learning
        self.facts_table_name = "business_facts"    # Verified knowledge
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure the experience and facts tables exist"""
        if self.facts_table_name not in self.db.db.table_names():
            self.db.create_table(self.facts_table_name)
```

---

## Real-Time Fact Retrieval Flows

### 1. Business Fact Retrieval

**Method**: `get_relevant_business_facts(query, limit=5)`

**Location**: `agent_world_model.py:416-442`

```python
async def get_relevant_business_facts(
    self,
    query: str,
    limit: int = 5
) -> List[BusinessFact]:
    """
    Search for verifiable business facts related to the query.

    Uses vector similarity to find semantically relevant facts
    from the business_facts table in LanceDB.
    """
    results = self.db.search(
        table_name=self.facts_table_name,
        query=query,
        limit=limit
    )

    facts = []
    for res in results:
        meta = res.get("metadata", {})
        facts.append(BusinessFact(
            id=meta.get("id"),
            fact=meta.get("fact"),
            citations=meta.get("citations", []),
            reason=meta.get("reason"),
            source_agent_id=meta.get("source_agent_id"),
            created_at=datetime.fromisoformat(meta.get("created_at")),
            last_verified=datetime.fromisoformat(meta.get("last_verified")),
            verification_status=meta.get("verification_status", "unverified"),
            metadata=meta
        ))
    return facts
```

**Example Usage**:

```python
wm = WorldModelService(workspace_id="default")

# Retrieve facts about invoice approval
facts = await wm.get_relevant_business_facts(
    query="What is the approval limit for invoices?",
    limit=5
)

for fact in facts:
    print(f"Fact: {fact.fact}")
    print(f"Citations: {fact.citations}")
    print(f"Status: {fact.verification_status}")

    # Verify citations before using
    if fact.verification_status == "verified":
        # Use this fact for decision-making
        pass
```

**Performance**:
- Vector search: ~50ms for 5 results
- Includes embedding generation and similarity scoring
- Sorted by semantic relevance (descending)

### 2. Comprehensive Context Retrieval

**Method**: `recall_experiences(agent, current_task_description, limit=5)`

**Location**: `agent_world_model.py:491-720`

This is the primary JIT method, combining all memory systems:

```python
async def recall_experiences(
    self,
    agent: AgentRegistry,
    current_task_description: str,
    limit: int = 5
) -> Dict[str, List[Any]]:
    """
    Retrieve relevant past experiences AND general knowledge.

    Returns:
        {
            "experiences": List[AgentExperience],      # Scoped to role
            "knowledge": List[Dict],                   # General documents
            "knowledge_graph": str,                    # GraphRAG context
            "formulas": List[Dict],                    # Formula memory
            "conversations": List[Dict],               # Recent messages
            "business_facts": List[BusinessFact],      # Verified facts
            "episodes": List[Dict]                     # Episodic memory
        }
    """
```

**Retrieval Flow**:

```
┌─────────────────────────────────────────────────────────────┐
│                  recall_experiences()                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Search Experiences (Scoped by Agent Role)                │
│     └─▶ agent_experience table → semantic search            │
│     └─▶ Filter: creator_id == agent.id OR role_match        │
│     └─▶ Sort by: confidence_score (descending)              │
│                                                              │
│  2. Search General Knowledge                                │
│     └─▶ documents table → semantic search                   │
│     └─▶ No user filtering (global knowledge)                │
│                                                              │
│  3. Query Knowledge Graph (GraphRAG)                        │
│     └─▶ graphrag_engine.get_context_for_ai()                │
│     └─▶ Hierarchical community detection                    │
│                                                              │
│  4. Search Formulas                                          │
│     └─▶ Formula memory → semantic + domain search           │
│     └─▶ Hot fallback: PostgreSQL recent formulas            │
│                                                              │
│  5. Retrieve Conversations                                  │
│     └─▶ ChatMessage table → latest N messages               │
│     └─▶ Filter by tenant_id                                 │
│                                                              │
│  6. Search Business Facts                                   │
│     └─▶ get_relevant_business_facts() → vector search       │
│                                                              │
│  7. Retrieve Episodes (Enriched)                            │
│     └─▶ EpisodeRetrievalService → contextual retrieval      │
│     └─▶ Fetch canvas_context (ALWAYS)                       │
│     └─▶ Fetch feedback_context (ALWAYS)                     │
│                                                              │
│  8. Aggregate & Return                                      │
│     └─▶ Combined context dictionary                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Example Usage**:

```python
from core.models import AgentRegistry
from core.agent_world_model import WorldModelService

# Get agent
agent = AgentRegistry(
    id="finance-agent-1",
    name="Invoice Processor",
    category="Finance",
    maturity_level="AUTONOMOUS"
)

# Recall all relevant context
wm = WorldModelService(workspace_id="default")
context = await wm.recall_experiences(
    agent=agent,
    current_task_description="Process invoice for $750 from Acme Corp",
    limit=5
)

# Access different memory types
print(f"Business Facts: {len(context['business_facts'])}")
print(f"Past Experiences: {len(context['experiences'])}")
print(f"Relevant Formulas: {len(context['formulas'])}")
print(f"Episodes: {len(context['episodes'])}")

# Use business facts for verification
for fact in context['business_facts']:
    if "invoice" in fact.fact.lower() and "approval" in fact.fact.lower():
        print(f"Rule: {fact.fact}")
        print(f"Source: {fact.citations}")
```

### 3. Knowledge Graph Querying

**Method**: `query_graphrag(user_id, query, mode="auto")`

**Location**: `knowledge_ingestion.py:118-122`

```python
def query_graphrag(self, user_id: str, query: str, mode: str = "auto") -> Dict[str, Any]:
    """
    Query GraphRAG for hierarchical knowledge retrieval.

    Modes:
    - "auto": Automatically choose best retrieval method
    - "local": Local entity-level retrieval
    - "global": Global community-level retrieval
    - "hybrid": Combined local + global
    """
    if self.graphrag:
        return self.graphrag.query(user_id, query, mode)
    return {"error": "GraphRAG not available"}
```

**Usage in JIT**:

```python
# Inside recall_experiences()
try:
    from core.graphrag_engine import graphrag_engine
    graph_context = graphrag_engine.get_context_for_ai(
        self.db.workspace_id,
        current_task_description
    )
except Exception as ge:
    logger.warning(f"GraphRAG recall failed: {ge}")
    graph_context = ""

# Graph context is included in final aggregation
```

---

## Integration with Agent Decision-Making

### Decision Flow with JIT Facts

```
┌──────────────────────┐
│  Agent Receives      │
│  Task                │
└──────────┬───────────┘
           │
           ▼
┌───────────────────────────────────────────┐
│  JIT Context Retrieval                    │
│  ┌─────────────────────────────────┐     │
│  │ 1. Get relevant business facts  │     │
│  │ 2. Recall past experiences      │     │
│  │ 3. Query knowledge graph        │     │
│  │ 4. Retrieve formulas            │     │
│  │ 5. Load episodes                │     │
│  └─────────────────────────────────┘     │
└──────────┬────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────┐
│  Context Synthesis                        │
│  - Combine facts + experiences            │
│  - Identify conflicts                     │
│  - Rank by confidence/relevance           │
└──────────┬────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────┐
│  Decision Generation                      │
│  - Apply business rules                   │
│  - Use verified facts                     │
│  - Cite sources                           │
└──────────┬────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────┐
│  Action Execution                         │
│  - Governed by maturity level             │
│  - Audit trail with citations             │
└───────────────────────────────────────────┘
```

### Example: Invoice Approval Decision

```python
async def process_invoice(invoice_data: dict):
    """Process invoice with JIT fact provision"""

    # 1. Retrieve relevant context
    wm = WorldModelService(workspace_id="default")
    context = await wm.recall_experiences(
        agent=agent,
        current_task_description=f"Process invoice ${invoice_data['amount']} from {invoice_data['vendor']}",
        limit=5
    )

    # 2. Extract relevant business facts
    approval_rules = []
    for fact in context['business_facts']:
        if 'approval' in fact.fact.lower() and 'invoice' in fact.fact.lower():
            approval_rules.append(fact)

    # 3. Check against invoice amount
    invoice_amount = invoice_data['amount']

    for rule in approval_rules:
        # Extract limit from fact (e.g., "Invoices > $500 need VP approval")
        if '$' in rule.fact:
            import re
            match = re.search(r'\$(\d+)', rule.fact)
            if match:
                limit = float(match.group(1))
                if invoice_amount > limit:
                    # 4. Apply rule with citation
                    return {
                        "action": "require_approval",
                        "approver": "VP",
                        "reason": rule.fact,
                        "citation": rule.citations[0],
                        "confidence": 0.95
                    }

    # 5. Check past experiences
    for exp in context['experiences']:
        if exp.task_type == "invoice_processing" and exp.outcome == "Success":
            # Learn from past success patterns
            pass

    # 6. Execute decision
    return {"action": "auto_approve", "reason": "Within approval limits"}
```

---

## Performance Characteristics

### Retrieval Performance

| Operation | Target | P50 | P95 | P99 |
|-----------|--------|-----|-----|-----|
| Business fact search (5 results) | <100ms | 45ms | 78ms | 120ms |
| Experience recall (scoped) | <150ms | 82ms | 140ms | 200ms |
| Knowledge graph query | <200ms | 110ms | 180ms | 250ms |
| Full context aggregation | <500ms | 320ms | 450ms | 600ms |
| LLM synthesis | <1s | 650ms | 900ms | 1.2s |

**End-to-End Latency**: <1s for typical agent decision-making

### Optimization Strategies

1. **Vector Indexing**: LanceDB IVF-PQ indexing for fast ANN search
2. **Caching**: Frequent queries cached in memory (TTL: 5 minutes)
3. **Parallel Retrieval**: All memory systems queried concurrently
4. **Result Limiting**: Default limit=5 prevents over-fetching
5. **Workspace Isolation**: Physical separation reduces dataset size

```python
# Parallel retrieval example
async def parallel_recall(agent, query):
    """Retrieve from all memory systems in parallel"""
    tasks = [
        wm.get_relevant_business_facts(query, limit=5),
        wm.db.search("agent_experience", query, limit=5),
        wm.db.search("documents", query, limit=5),
        # ... other sources
    ]

    results = await asyncio.gather(*tasks)
    return aggregate_results(results)
```

### Scalability

| Metric | Value |
|--------|-------|
| Max facts per workspace | 100,000+ |
| Max concurrent queries | 1,000+ |
| Query throughput | 500 queries/sec |
| Storage efficiency | ~1KB per fact (including metadata) |
| Vector dimensionality | 384 (local) or 1536 (OpenAI) |

---

## Document Ingestion Pipeline

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│             Document Ingestion Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐ │
│  │   Document   │────▶│   Docling    │────▶│   Extracted  │ │
│  │   Upload     │     │   Parser     │     │   Text      │ │
│  └──────────────┘     └──────────────┘     └─────────────┘ │
│                             │                                │
│                             ▼                                │
│                    ┌──────────────┐                         │
│                    │ Knowledge    │                         │
│                    │ Extractor    │                         │
│                    │ (LLM-based)  │                         │
│                    └──────────────┘                         │
│                             │                                │
│                             ▼                                │
│                    ┌──────────────┐                         │
│                    │   Business   │                         │
│                    │   Facts      │                         │
│                    │  Extraction  │                         │
│                    └──────────────┘                         │
│                             │                                │
│        ┌────────────────────┼────────────────────┐          │
│        ▼                    ▼                    ▼          │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐       │
│  │  LanceDB  │      │ GraphRAG  │      │   R2/S3   │       │
│  │   Store   │      │  Ingest   │      │  Archive  │       │
│  └───────────┘      └───────────┘      └───────────┘       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Ingestion Manager

**Location**: `backend/core/knowledge_ingestion.py:12-135`

```python
class KnowledgeIngestionManager:
    """
    Coordinates extraction of knowledge from documents and
    storing them as relationships in the knowledge graph.
    Integrates with GraphRAG for hierarchical knowledge retrieval.
    """

    async def process_document(
        self,
        text: str,
        doc_id: str,
        source: str = "unknown",
        user_id: str = "default_user",
        workspace_id: Optional[str] = None
    ):
        """
        Extracts knowledge from a document and updates both
        LanceDB and GraphRAG.
        """
        # 1. Extract knowledge (LLM-based)
        knowledge = await self.extractor.extract_knowledge(text, source)

        # 2. Store entities and relationships in LanceDB
        entities = knowledge.get("entities", [])
        relationships = knowledge.get("relationships", [])

        for rel in relationships:
            self.handler.add_knowledge_edge(
                from_id=rel.get("from"),
                to_id=rel.get("to"),
                rel_type=rel.get("type"),
                description=description,
                metadata={"doc_id": doc_id, "source": source},
                user_id=user_id
            )

        # 3. Ingest into GraphRAG for hierarchical queries
        if self.graphrag:
            self.graphrag.add_entities_and_relationships(
                user_id, entities, relationships
            )

        return {
            "lancedb_edges": success_count,
            "graphrag": graphrag_stats
        }
```

---

## Vector Search and Semantic Retrieval

### Embedding Generation

**Location**: `backend/core/embedding_service.py`

**Supported Providers**:

1. **FastEmbed** (Default, Recommended)
   - Model: `BAAI/bge-small-en-v1.5` (384 dimensions)
   - Performance: ~10-20ms per document
   - Cost: Free (local, ONNX-based)

2. **OpenAI** (Optional)
   - Model: `text-embedding-3-small` (1536 dimensions)
   - Performance: ~100-300ms per document
   - Cost: $0.02 per 1M tokens

3. **Cohere** (Optional)
   - Model: `embed-english-v3.0` (1024 dimensions)
   - Performance: ~150-400ms per document
   - Cost: $0.10 per 1M tokens

**Example**:

```python
from core.embedding_service import EmbeddingService

# Initialize with default provider (FastEmbed)
service = EmbeddingService()

# Generate embedding
embedding = await service.generate_embedding(
    "Invoices exceeding $500 require VP approval"
)

# Returns: [0.123, -0.456, ...] (vector of 384 floats)
```

### Vector Similarity Search

**Location**: `backend/core/lancedb_handler.py:570-638`

```python
def search(
    self,
    table_name: str,
    query: str,
    user_id: str = None,
    limit: int = 10,
    filter_str: str = None
) -> List[Dict[str, Any]]:
    """
    Search for documents in memory with optional user filtering.

    Process:
    1. Generate query embedding
    2. Build filter expression (workspace + user + custom)
    3. Execute vector search with filters
    4. Convert distance to similarity score
    5. Return ranked results
    """
    # Generate embedding for query
    query_vector = self.embed_text(query)

    # Build search query
    search_query = table.search(query_vector.tolist()).limit(limit)

    # Apply workspace_id and user_id filter
    filters = []
    if self.workspace_id:
        filters.append(f"workspace_id == '{self.workspace_id}'")
    if user_id:
        filters.append(f"user_id == '{user_id}'")
    if filter_str:
        filters.append(f"({filter_str})")

    # Combine filters
    final_filter = " AND ".join(filters)
    if final_filter:
        search_query = search_query.where(final_filter)

    # Execute search
    results = search_query.to_pandas()

    # Convert to list of dictionaries
    results_list = []
    for _, row in results.iterrows():
        metadata = json.loads(row['metadata']) if row['metadata'] else {}
        result = {
            "id": row['id'],
            "text": row['text'],
            "source": row['source'],
            "metadata": metadata,
            "created_at": row['created_at'],
            "score": 1.0 - row.get('_distance', 0.0)  # Distance → Similarity
        }
        results_list.append(result)

    return results_list
```

**Distance Metrics**:

- **Cosine** (default): Measures angle between vectors (0-2)
- **L2**: Euclidean distance
- **Dot**: Dot product (higher = more similar)

---

## JIT Answer Synthesis

**Location**: `backend/core/knowledge_query_endpoints.py:18-77`

```python
class KnowledgeQueryManager:
    """
    Traverses the knowledge graph to synthesize answers
    for complex queries using retrieved context.
    """

    async def answer_query(
        self,
        query: str,
        user_id: str = "default_user",
        workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Answers a natural language query using knowledge graph context.

        Returns:
            {
                "answer": str,           # Synthesized answer
                "relevant_facts": list   # Source facts used
            }
        """
        # 1. Search knowledge graph for relevant relationships
        related_edges = self.handler.query_knowledge_graph(
            query,
            user_id=user_id,
            limit=15
        )

        # 2. Extract facts from edges
        facts = []
        for edge in related_edges:
            metadata = edge.get("metadata", {})
            fact = f"- {edge.get('from_id')} {edge.get('type')} {edge.get('to_id')}"
            props = metadata.get("properties", {})
            if props:
                fact += f" (Details: {props})"
            facts.append(fact)

        context_str = "\n".join(facts)

        # 3. Use LLM to synthesize the answer
        system_prompt = f"""
        You are a Knowledge Graph Query Assistant.
        Answer the user's question based ONLY on the provided facts.

        **Facts:**
        {context_str}

        If the facts don't contain the answer, say you don't know.
        """

        ai_service = RealAIWorkflowService()
        result = await ai_service.analyze_text(query, system_prompt=system_prompt)

        answer = result.get("response", "Failed to synthesize answer.")

        return {
            "answer": answer,
            "relevant_facts": facts
        }
```

**API Endpoint**: `POST /api/knowledge/query`

**Example Request**:

```bash
curl -X POST http://localhost:8000/api/knowledge/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the approval limit for invoices?",
    "user_id": "user123"
  }'
```

**Example Response**:

```json
{
  "success": true,
  "answer": "According to the business policies, invoices exceeding $500 require VP approval before processing. Invoices under $500 can be auto-approved.",
  "relevant_facts": [
    "- Invoice approval_limit BusinessRule (Details: {'value': 500, 'approver': 'VP'})",
    "- approval_policy Invoice REFERENCE_TO (Details: {'document': 'policy.pdf'})"
  ]
}
```

---

## Usage Examples

### Example 1: Real-Time Decision Support

```python
from core.agent_world_model import WorldModelService

async def make_business_decision(agent, task_description):
    """Make a decision using JIT facts"""

    # 1. Retrieve all relevant context
    wm = WorldModelService(workspace_id="default")
    context = await wm.recall_experiences(
        agent=agent,
        current_task_description=task_description,
        limit=5
    )

    # 2. Extract business rules
    business_rules = []
    for fact in context['business_facts']:
        if fact.verification_status == "verified":
            business_rules.append({
                "rule": fact.fact,
                "citation": fact.citations[0],
                "confidence": 0.95
            })

    # 3. Check past experiences
    successful_patterns = [
        exp for exp in context['experiences']
        if exp.outcome == "Success" and exp.confidence_score > 0.7
    ]

    # 4. Synthesize decision
    if business_rules:
        return {
            "decision": "apply_rule",
            "rule": business_rules[0]['rule'],
            "source": business_rules[0]['citation']
        }
    elif successful_patterns:
        return {
            "decision": "follow_pattern",
            "pattern": successful_patterns[0].learnings
        }
    else:
        return {
            "decision": "escalate",
            "reason": "No relevant rules or patterns found"
        }
```

### Example 2: Knowledge Graph Traversal

```python
from core.knowledge_ingestion import get_knowledge_ingestion

async def query_entity_relationships(entity_name: str):
    """Query relationships for an entity using GraphRAG"""

    ingestor = get_knowledge_ingestion()

    result = ingestor.query_graphrag(
        user_id="user123",
        query=f"What relationships does {entity_name} have?",
        mode="global"  # Use global community detection
    )

    # Returns hierarchical community structure
    # with entity relationships and summaries
    return result
```

### Example 3: Formula-Aware Retrieval

```python
# Inside recall_experiences()
from core.formula_memory import get_formula_manager

formula_manager = get_formula_manager(workspace_id)

# Search for formulas relevant to the current task
formulas = formula_manager.search_formulas(
    query=current_task_description,
    domain=agent_category,
    limit=limit
)

# Include in context aggregation
context['formulas'] = [
    {
        "id": f.get("id"),
        "name": f.get("name"),
        "expression": f.get("expression"),
        "use_case": f.get("use_case")
    }
    for f in formulas
]
```

---

## Monitoring and Observability

### Key Metrics

```python
# Track retrieval performance
import time

async def tracked_recall(agent, query):
    start = time.time()

    context = await wm.recall_experiences(
        agent=agent,
        current_task_description=query,
        limit=5
    )

    latency = time.time() - start

    # Log metrics
    logger.info(f"JIT recall completed in {latency*1000:.2f}ms")
    logger.info(f"Retrieved {len(context['business_facts'])} facts")
    logger.info(f"Retrieved {len(context['experiences'])} experiences")

    return context
```

### Performance Targets

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Fact retrieval latency | <100ms | >200ms |
| Full context recall | <500ms | >1s |
| Knowledge graph query | <200ms | >400ms |
| Answer synthesis | <1s | >2s |
| Cache hit rate | >80% | <60% |

---

## Troubleshooting

### Issue: No facts retrieved for query

**Diagnosis**:
```python
# Check if facts table exists
handler = get_lancedb_handler()
print(handler.db.table_names())

# Verify table has data
table = handler.get_table("business_facts")
print(table.count_rows())

# Test embedding generation
embedding = handler.embed_text("test query")
print(f"Embedding dimension: {len(embedding)}")
```

**Solution**:
- Ensure facts have been uploaded via `/api/admin/governance/facts/upload`
- Check embedding model is initialized
- Verify workspace_id matches

### Issue: Slow retrieval performance

**Diagnosis**:
```python
import time

start = time.time()
results = handler.search("business_facts", "test query", limit=5)
print(f"Search took: {time.time() - start:.3f}s")
```

**Solutions**:
- Reduce `limit` parameter
- Enable result caching
- Use workspace isolation to reduce dataset size
- Consider upgrading OpenAI embeddings (higher quality = fewer results needed)

### Issue: Knowledge graph returns empty

**Diagnosis**:
```python
ingestor = get_knowledge_ingestion()
print(f"GraphRAG available: {ingestor.graphrag is not None}")
```

**Solutions**:
- Ensure documents have been ingested via `KnowledgeIngestionManager`
- Check GraphRAG engine is initialized
- Verify entities and relationships were extracted

---

## Related Documentation

- [Citation System Guide](./CITATION_SYSTEM_GUIDE.md) - Business fact management
- [Document Processing Pipeline](./DOCUMENT_PROCESSING_PIPELINE.md) - Multi-format parsing
- [Architecture Diagrams](./ARCHITECTURE_DIAGRAMS.md) - Visual system overview
- [Agent World Model](../backend/core/agent_world_model.py) - Core implementation

---

## Changelog

### February 2026
- Initial JIT fact provision system
- WorldModelService context aggregation
- GraphRAG integration for hierarchical retrieval
- Formula memory integration
- Episode retrieval with canvas/feedback context

### Future Enhancements
- [ ] Predictive pre-fetching of likely facts
- [ ] Fact versioning and temporal queries
- [ ] Cross-workspace fact federation
- [ ] Real-time fact updates from source changes
- [ ] ML-based fact ranking optimization
