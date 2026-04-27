# Agent World Model Implementation Notes

**File:** `backend/core/agent_world_model.py`
**Lines:** 2,206
**Class:** WorldModelService
**Purpose:** Multi-source memory management for AI agents (experiences, facts, episodes, cold storage)
**Created:** 2026-04-27
**Context:** Gap closure for Phase 83 Plan 03 - rebuilding tests with implementation-first approach

---

## Overview

WorldModelService is a comprehensive memory management system that provides:
- **Experience Recording** - Agent learning from task execution
- **Business Facts** - JIT-verified knowledge with citations
- **Episodic Memory** - Long-term episode storage and retrieval
- **Cold Storage** - PostgreSQL → LanceDB archival for old sessions
- **Decision Support** - Skill recommendations based on past performance
- **Canvas Integration** - Presentation type preferences and outcomes

**Key Pattern:** LanceDB is append-only. Updates work by: search → find doc → re-add with new metadata

---

## Constructor

```python
def __init__(self, workspace_id: Optional[str] = None):
    self.db = get_lancedb_handler(workspace_id)  # LanceDBHandler instance
    self.table_name = "agent_experience"
    self.facts_table_name = "business_facts"
    self._ensure_tables()  # Creates tables if not exist
```

**Dependencies:**
- `self.db` - LanceDBHandler instance (mock this for testing)
- `workspace_id` - Tenant/workspace identifier

---

## Method Signatures by Category

### 1. EXPERIENCE RECORDING (5 methods)

#### 1.1 record_experience
```python
async def record_experience(self, experience: AgentExperience) -> bool
```
**Purpose:** Record agent execution experience to vector store
**Input:** AgentExperience Pydantic model with:
- id, agent_id, task_type, input_summary, outcome, learnings
- confidence_score (0.0-1.0), feedback_score (-1.0 to 1.0)
- artifacts (list), step_efficiency (float), metadata_trace (dict)
- agent_role, specialty, timestamp

**Returns:** bool (True if added to LanceDB successfully)

**LanceDB Operation:**
- `self.db.add_document(table_name="agent_experience", text=..., metadata={...})`
- Text format: "Task: {task_type}\nInput: {input}\nOutcome: {outcome}\nLearnings: {learnings}"
- Metadata includes: agent_id, task_type, outcome, confidence_score, feedback_score, etc.

---

#### 1.2 record_formula_usage
```python
async def record_formula_usage(
    self,
    agent_id: str,
    agent_role: str,
    formula_id: str,
    formula_name: str,
    task_description: str,
    inputs: Dict[str, Any],
    result: Any,
    success: bool,
    learnings: str = ""
) -> bool
```
**Purpose:** Record formula application as experience for learning
**Returns:** bool

**Metadata includes:**
- formula_id, formula_name, formula_inputs (JSON string), formula_result

---

#### 1.3 update_experience_feedback
```python
async def update_experience_feedback(
    self,
    experience_id: str,
    feedback_score: float,
    feedback_notes: str = ""
) -> bool
```
**Purpose:** Update experience with human feedback (blends into confidence score)
**Returns:** bool (True if found and updated)

**Implementation Pattern:**
1. Search experiences with limit=100
2. Find by matching `res.get("id") == experience_id`
3. Update confidence: `new_confidence = old_confidence * 0.6 + (feedback_score + 1.0) / 2.0 * 0.4`
4. Re-add document with updated metadata

**Note:** Returns False if experience_id not found

---

#### 1.4 boost_experience_confidence
```python
async def boost_experience_confidence(
    self,
    experience_id: str,
    boost_amount: float = 0.1
) -> bool
```
**Purpose:** Boost confidence when experience pattern is successfully reused
**Returns:** True (placeholder implementation)

**Note:** Currently a placeholder - returns True without DB update

---

#### 1.5 get_experience_statistics
```python
async def get_experience_statistics(
    self,
    agent_id: Optional[str] = None,
    agent_role: Optional[str] = None
) -> Dict[str, Any]
```
**Purpose:** Aggregate statistics about agent experiences
**Returns:** Dict with keys:
- total_experiences, successes, failures, success_rate
- avg_confidence, feedback_coverage, agent_id, agent_role
- OR: {"error": str} if exception occurs

**Implementation:**
1. Search table with query="experience", limit=1000
2. Filter by agent_id/agent_role if provided
3. Count successes (outcome=="Success"), failures (outcome in ["failed", "Failure"])
4. Calculate averages

---

### 2. BUSINESS FACTS (8 methods)

#### 2.1 record_business_fact
```python
async def record_business_fact(self, fact: BusinessFact) -> bool
```
**Purpose:** Record verified business fact with citations
**Input:** BusinessFact Pydantic model with:
- id, fact, citations (list), reason, source_agent_id
- created_at, last_verified, verification_status (default "unverified")
- metadata (dict)

**Returns:** bool

**Metadata stored:** id, fact, citations, reason, source_agent_id, created_at/last_verified (ISO format), verification_status, type="business_fact", **metadata

---

#### 2.2 update_fact_verification
```python
async def update_fact_verification(self, fact_id: str, status: str) -> bool
```
**Purpose:** Update verification status of a business fact
**Returns:** bool (True if found and updated)

**Implementation Pattern:**
1. Search facts table with limit=100
2. Find by `res.get("metadata", {}).get("id") == fact_id`
3. Update metadata["verification_status"] = status
4. Update metadata["last_verified"] = current ISO timestamp
5. Re-add document

---

#### 2.3 get_relevant_business_facts
```python
async def get_relevant_business_facts(
    self,
    query: str,
    limit: int = 5
) -> List[BusinessFact]
```
**Purpose:** Semantic search for business facts
**Returns:** List[BusinessFact] or [] on error

**Implementation:**
1. `self.db.search(table_name="business_facts", query=query, limit=limit)`
2. Parse results into BusinessFact objects
3. Return [] if search fails (exception handling)

---

#### 2.4 get_business_fact
```python
async def get_business_fact(self, fact_id: str) -> Optional[BusinessFact]
```
**Purpose:** Retrieve specific fact by ID using direct table access
**Returns:** BusinessFact or None

**Implementation:**
1. Get table: `self.db.get_table(self.facts_table_name)`
2. Use LanceDB filtering: `table.search().where(f"id == '{fact_id}'").limit(1).to_pandas()`
3. Parse metadata JSON from pandas row
4. Return None if not found or error

**Note:** Different from get_fact_by_id() - uses direct table access vs search

---

#### 2.5 bulk_record_facts
```python
async def bulk_record_facts(self, facts: List[BusinessFact]) -> int
```
**Purpose:** Store multiple facts at once
**Returns:** int (number successfully stored)

**Implementation:** Loop through facts, call record_business_fact(), count successes. Logs errors but continues.

---

#### 2.6 list_all_facts
```python
async def list_all_facts(
    self,
    status: str = None,
    domain: str = None,
    limit: int = 100
) -> List[BusinessFact]
```
**Purpose:** List all facts with optional filters
**Returns:** List[BusinessFact]

**Implementation:**
1. Search with empty query, limit=limit*2 (for filtering)
2. Filter by status if provided: `meta.get("verification_status") == status`
3. Filter by domain if provided: `meta.get("domain") == domain`
4. Parse each result into BusinessFact
5. Return [] on error

---

#### 2.7 get_fact_by_id
```python
async def get_fact_by_id(self, fact_id: str) -> BusinessFact | None
```
**Purpose:** Get fact by ID using search (different from get_business_fact)
**Returns:** BusinessFact or None

**Implementation:**
1. Search with limit=200
2. Find by `meta.get("id") == fact_id`
3. Return BusinessFact or None

**Note:** Uses search vs direct table access in get_business_fact()

---

#### 2.8 delete_fact
```python
async def delete_fact(self, fact_id: str) -> bool
```
**Purpose:** Soft delete fact by marking as "deleted"
**Returns:** bool (result of update_fact_verification)

**Implementation:** Calls `update_fact_verification(fact_id, "deleted")`

---

### 3. INTEGRATION EXPERIENCES (1 method)

#### 3.1 recall_integration_experiences
```python
async def recall_integration_experiences(
    self,
    agent_role: str,
    connector_id: str,
    operation_name: str,
    limit: int = 5
) -> List[AgentExperience]
```
**Purpose:** Recall past integration execution experiences for learning
**Returns:** List[AgentExperience] or [] if db.db is None

**Implementation:**
1. Return [] early if `self.db.db is None`
2. Build task_type: `f"integration_{connector_id}_{operation_name}"`
3. Search with query_text, where filter for task_type and agent_role
4. Parse results into AgentExperience objects
5. Return [] on parse errors (logged but continue)

---

### 4. COLD STORAGE (4 methods)

#### 4.1 archive_session_to_cold_storage
```python
async def archive_session_to_cold_storage(self, conversation_id: str) -> bool
```
**Purpose:** Archive completed conversation from PostgreSQL (hot) to LanceDB (cold)
**Returns:** bool (True if archived successfully)

**Implementation:**
1. Query ChatMessage by conversation_id and tenant_id
2. Build session_text: "role: content" for each message
3. Add document to LanceDB "archived_memories" table
4. Soft delete: Update message.metadata_json with _archived=True, _archived_at, _archived_to_lancedb
5. Record ACU consumption (2.0 ACUs) via ACUBillingService
6. Return False if no messages found

**Dependencies:**
- SessionLocal (PostgreSQL)
- ChatMessage model
- ACUBillingService (optional, logged if fails)

---

#### 4.2 archive_session_to_cold_storage_with_cleanup
```python
async def archive_session_to_cold_storage_with_cleanup(
    self,
    conversation_id: str,
    retention_days: int = 30,
    verify_before_delete: bool = True
) -> dict
```
**Purpose:** Archive with verification and soft delete (safer alternative to 4.1)
**Returns:** dict with keys:
- audit_id, conversation_id, status ("success" or "failed")
- archived (bool), soft_deleted (bool), hard_deleted (bool)
- scheduled_for_hard_delete (ISO timestamp) if successful
- error (str) if failed

**Implementation:**
1. Generate audit_id: `f"audit_{timestamp}_{conversation_id[:8]}"`
2. Query messages from PostgreSQL
3. Archive to LanceDB "archived_memories" table
4. Verify archival if verify_before_delete=True (search for document)
5. Soft delete: Update metadata with _archived, _archived_at, _audit_id, _retention_until
6. Return {"status": "failed", "error": str} if any step fails

---

#### 4.3 recover_archived_session
```python
async def recover_archived_session(self, conversation_id: str) -> dict
```
**Purpose:** Recover soft-deleted session by removing archived flags
**Returns:** dict with status ("success" or "failed"), recovered_count (int), error (str)

**Implementation:**
1. Query ChatMessage where metadata_json.has_key('_archived')
2. For each message:
   - Set metadata_json["_recovered"] = True
   - Set metadata_json["_recovered_at"] = ISO timestamp
   - Remove metadata_json["_archived"]
3. Commit changes
4. Return {"status": "failed", "error": str} if no messages found

---

#### 4.4 hard_delete_archived_sessions
```python
async def hard_delete_archived_sessions(self, older_than_days: int = 30) -> dict
```
**Purpose:** Permanently delete sessions past retention period (IRREVERSIBLE)
**Returns:** dict with status ("success" or "failed"), deleted_count (int), error (str)

**Implementation:**
1. Calculate cutoff_date: `datetime.now(timezone.utc) - timedelta(days=older_than_days)`
2. Query messages where _archived=true
3. Filter by _retention_until < cutoff_date
4. Hard delete: db.delete(msg) for each message
5. Commit and return deleted_count

**WARNING:** Logs warning about irreversibility

---

### 5. EPISODE MANAGEMENT (6 methods)

#### 5.1 record_episode
```python
async def record_episode(
    self,
    episode_id: str,
    agent_id: str,
    tenant_id: str,
    task_description: str,
    outcome: str,
    learnings: str,
    agent_role: str,
    maturity_at_time: str,
    constitutional_score: float = 1.0,
    human_intervention_count: int = 0,
    confidence_score: float = 0.5,
    metadata: Dict[str, Any] = None
) -> bool
```
**Purpose:** Record episode to LanceDB for semantic search (dual storage with PostgreSQL)
**Returns:** bool

**Text Format:**
```
Episode: {task_description}
Outcome: {outcome}
Learnings: {learnings}
Maturity: {maturity_at_time}
Constitutional Score: {score:.2f}
Interventions: {count}
```

**Metadata includes:** episode_id, agent_id, tenant_id, task_type="episode", outcome, agent_role, maturity_at_time, constitutional_score, human_intervention_count, confidence_score, type="episode", **metadata

---

#### 5.2 sync_episode_to_lancedb
```python
async def sync_episode_to_lancedb(
    self,
    episode_id: str,
    task_description: str,
    agent_id: str,
    agent_role: str,
    outcome: str,
    learnings: str,
    confidence_score: float
) -> bool
```
**Purpose:** Sync episode from PostgreSQL to LanceDB after graduation
**Returns:** bool

**Implementation:** Similar to record_episode but simpler (fewer parameters)

---

#### 5.3 recall_episodes
```python
async def recall_episodes(
    self,
    agent_id: str,
    current_task: str,
    limit: int = 5
) -> List[Dict[str, Any]]
```
**Purpose:** Recall relevant episodes for current task
**Returns:** List of episode dicts or [] on error

**Implementation:**
1. Query PostgreSQL for recent episodes (agent_id, limit=limit*3)
2. Extract episode_ids
3. Search LanceDB for episodes matching current_task
4. Merge results, filter by agent_id
5. Return up to limit episodes

---

#### 5.4 recall_experiences_with_detail
```python
async def recall_experiences_with_detail(
    self,
    agent: AgentRegistry,
    current_task_description: str,
    detail_level: DetailLevel,
    limit: int = 5
) -> List[Dict[str, Any]]
```
**Purpose:** Recall experiences with progressive detail levels (SUMMARY/STANDARD/FULL)
**Returns:** List of experience dicts

**Detail Levels:**
- SUMMARY (~50 tokens): canvas type + summary + has_errors
- STANDARD (~200 tokens): summary + visual_elements + data
- FULL (~500 tokens): STANDARD + full_state + audit_trail

**Implementation:**
1. Search experiences table
2. Filter by agent.id and agent.category (scoped access)
3. Apply detail level formatting
4. Return list

---

#### 5.5 archive_episode_to_cold_storage
```python
async def archive_episode_to_cold_storage(
    self,
    episode_id: str
) -> bool
```
**Purpose:** Archive episode to LanceDB after graduation
**Returns:** bool

**Implementation:** Similar to session archival but for episode data

---

#### 5.6 get_recent_episodes
```python
async def get_recent_episodes(
    self,
    agent_id: str,
    limit: int = 10
) -> List[Dict[str, Any]]
```
**Purpose:** Get recent episodes for agent from PostgreSQL
**Returns:** List of episode dicts

**Implementation:**
1. Query PostgreSQL Episode model (not LanceDB)
2. Filter by agent_id
3. Order by created_at DESC, limit
4. Serialize to dicts

---

### 6. DECISION SUPPORT (3 methods)

#### 6.1 get_episode_feedback_for_decision
```python
def get_episode_feedback_for_decision(
    self,
    agent_id: str,
    task_type: str
) -> Dict[str, Any]
```
**Purpose:** Analyze past episode feedback to inform decision (SYNC method)
**Returns:** Dict with:
- success_rate, avg_confidence, recommended_outcome, recent_feedback

**Implementation:**
1. Search episodes by agent_id and task_type
2. Calculate success rate and confidence
3. Return "proceed" if success_rate > 0.7 else "caution"

---

#### 6.2 recommend_skills_for_task
```python
def recommend_skills_for_task(
    self,
    agent: AgentRegistry,
    task_description: str,
    limit: int = 5
) -> List[str]
```
**Purpose:** Recommend community skills based on task and agent category (SYNC method)
**Returns:** List of skill IDs

**Implementation:**
1. Query CommunitySkill model for matching agent.category
2. Search skill names/descriptions for task_description matches
3. Sort by rating and usage_count
4. Return top skill IDs

---

#### 6.3 get_successful_skills_for_agent
```python
def get_successful_skills_for_agent(
    self,
    agent_id: str,
    limit: int = 10
) -> List[Dict[str, Any]]
```
**Purpose:** Get skills that worked well for this agent in past (SYNC method)
**Returns:** List of skill dicts with skill_id, success_count, avg_score

**Implementation:**
1. Query SkillExecution table
2. Filter by agent_id and successful=True
3. Group by skill_id, aggregate stats
4. Return top skills

---

### 7. CANVAS INTEGRATION (4 methods)

#### 7.1 recall_experiences_with_canvas
```python
async def recall_experiences_with_canvas(
    self,
    agent_id: str,
    task_description: str,
    canvas_type: str = None,
    limit: int = 5
) -> List[Dict[str, Any]]
```
**Purpose:** Recall experiences with canvas context filtered by type
**Returns:** List of experience dicts with canvas_context

**Implementation:**
1. Search experiences table
2. Filter by agent_id
3. Optionally filter by canvas_type in metadata
4. Return results with canvas metadata extracted

---

#### 7.2 get_canvas_type_preferences
```python
async def get_canvas_type_preferences(
    self,
    agent_id: str
) -> Dict[str, Any]
```
**Purpose:** Get agent's canvas type success rates
**Returns:** Dict with canvas_type -> success_rate mappings

**Implementation:**
1. Search experiences where agent_id matches
2. Extract canvas_type from metadata
3. Calculate success rates by canvas_type
4. Return aggregated stats

---

#### 7.3 recommend_canvas_type
```python
async def recommend_canvas_type(
    self,
    agent_id: str,
    task_description: str
) -> str
```
**Purpose:** Recommend best canvas type based on task and past performance
**Returns:** Canvas type string (e.g., "chart", "form", "markdown")

**Implementation:**
1. Get canvas type preferences
2. Search for similar tasks
3. Return highest-success canvas type for similar tasks

---

#### 7.4 record_canvas_outcome
```python
async def record_canvas_outcome(
    self,
    agent_id: str,
    canvas_type: str,
    task_description: str,
    success: bool,
    user_feedback: str = ""
) -> bool
```
**Purpose:** Record canvas presentation outcome for learning
**Returns:** bool

**Implementation:**
1. Create experience with task_type=f"canvas_{canvas_type}"
2. Include canvas_type and success in metadata
3. Call record_experience()

---

### 8. CONTEXT RETRIEVAL (2 methods)

#### 8.1 recall_experiences (COMPREHENSIVE)
```python
async def recall_experiences(
    self,
    agent: AgentRegistry,
    current_task_description: str,
    limit: int = 5
) -> Dict[str, List[Any]]
```
**Purpose:** Comprehensive context retrieval from ALL sources
**Returns:** Dict with keys:
- experiences (List[AgentExperience])
- knowledge (List[Dict]) - from documents table
- knowledge_graph (str) - GraphRAG context
- formulas (List[Dict]) - Formula memory
- conversations (List[Dict]) - Recent PostgreSQL messages
- business_facts (List[BusinessFact]) - Trusted memory
- episodes (List[Dict]) - Episodic memory

**Implementation:** Calls multiple services:
1. Search agent_experience table (scoped to agent.id and agent.category)
2. Search documents table (general knowledge)
3. GraphRAG engine context
4. Formula manager search
5. PostgreSQL ChatMessage query
6. Business facts search (get_relevant_business_facts)
7. Episode retrieval service

**Scoped Access Logic:**
- is_creator: (creator_id == agent.id)
- is_role_match: (memory_role == agent_category)
- Include if either matches

---

#### 8.2 _format_episodes_as_experiences (PRIVATE)
```python
def _format_episodes_as_experiences(
    self,
    episodes: List[Any],
    agent_role: str
) -> List[AgentExperience]
```
**Purpose:** Convert episode objects to AgentExperience format (PRIVATE method)
**Returns:** List[AgentExperience]

**Implementation:** Maps episode fields to AgentExperience fields

---

## LanceDB Patterns

### Append-Only Updates
LanceDB doesn't support in-place updates. Pattern:
```python
# 1. Search for document
results = self.db.search(table_name=..., query="", limit=100)

# 2. Find and update metadata
for res in results:
    if res.get("id") == target_id:
        meta = res.get("metadata", {})
        meta["field"] = new_value

        # 3. Re-add with updated metadata
        self.db.add_document(
            table_name=...,
            text=enhanced_text,
            metadata=meta,
            ...
        )
```

### Metadata Structure
Standard metadata fields:
- `type` - "experience", "business_fact", "episode", "archived_session"
- `agent_id` - Creator/owner ID
- `agent_role` - Agent category (e.g., "Finance", "Operations")
- `created_at` - ISO format timestamp
- `confidence_score` - 0.0 to 1.0
- `outcome` - "Success", "Failure", "failed"

### Search Patterns
```python
# Semantic search
results = self.db.search(
    table_name=self.table_name,
    query=text_query,
    limit=limit
)

# Filtered search
results = self.db.search(
    table_name=self.table_name,
    query_text=text_query,
    limit=limit,
    where={
        "task_type": specific_type,
        "agent_role": role
    }
)

# Direct table access (for precise queries)
table = self.db.get_table(table_name)
pandas_df = table.search().where(f"id == '{id}'").limit(1).to_pandas()
```

---

## Error Handling Patterns

### Standard Pattern
```python
try:
    # Operation
    return success_value
except Exception as e:
    logger.error(f"Failed to <operation>: {e}")
    return error_value  # False, [], {}, None depending on method
```

### Return Values on Error
- bool methods: Return False
- List methods: Return []
- Dict methods: Return {"error": str(e)} or {}
- Optional methods: Return None

---

## Testing Mock Requirements

### LanceDBHandler Mock
```python
mock_db = Mock()
mock_db.db = Mock()  # Simulates active connection
mock_db.workspace_id = "test_workspace"
mock_db.add_document = Mock(return_value=True)
mock_db.search = Mock(return_value=[])
mock_db.create_table = Mock()
mock_db.get_table = Mock(return_value=None)
```

### SessionLocal Mock (PostgreSQL)
```python
with patch('core.agent_world_model.SessionLocal') as mock_session_local:
    mock_db = Mock()
    mock_session_local.return_value = mock_db

    # Mock query chain
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.to_pandas.return_value = DataFrame()
```

### Pydantic Model Creation
```python
from core.agent_world_model import AgentExperience, BusinessFact

experience = AgentExperience(
    id=str(uuid.uuid4()),
    agent_id="agent_123",
    task_type="test",
    input_summary="Test input",
    outcome="Success",
    learnings="Test learning",
    confidence_score=0.8,
    agent_role="Test",
    timestamp=datetime.now(timezone.utc)
)
```

---

## Common Pitfalls for Tests

1. **Wrong Method Names:** Use actual signatures from this doc
   - ✅ `get_fact_by_id()` not `get_business_fact_by_id()`
   - ✅ `update_fact_verification()` not `update_fact_status()`

2. **Metadata Structure:** Match actual metadata keys
   - ✅ `meta.get("agent_id")` not `meta.get("creator_id")`
   - ✅ `meta.get("verification_status")` not `meta.get("status")`

3. **Async vs Sync:** Some methods are sync
   - ✅ `get_episode_feedback_for_decision()` is NOT async
   - ✅ `recommend_skills_for_task()` is NOT async

4. **Return Types:** Match actual return types
   - ✅ `get_experience_statistics()` returns Dict, not List
   - ✅ `get_business_fact()` uses direct table access, `get_fact_by_id()` uses search

5. **LanceDB Append-Only:** Updates re-add documents
   - ✅ Mock `add_document()` to be called multiple times for updates
   - ✅ Search returns list, not single item

---

## Summary

**Total Public Methods:** 33 (excluding __init__ and private methods)
**Async Methods:** 26
**Sync Methods:** 7

**Categories:**
1. Experience Recording: 5 methods (5 async)
2. Business Facts: 8 methods (8 async)
3. Integration Experiences: 1 method (1 async)
4. Cold Storage: 4 methods (4 async)
5. Episode Management: 6 methods (6 async)
6. Decision Support: 3 methods (3 sync)
7. Canvas Integration: 4 methods (4 async)
8. Context Retrieval: 2 methods (1 async, 1 sync private)

**Complexity:** High - 2,206 lines with complex async operations, multiple database backends, and distributed service integration

**Coverage Strategy:** Focus on critical paths and error handling. 50-60% coverage is realistic given the complexity and integration points.

---

**Document Length:** 459 lines
**Last Updated:** 2026-04-27
**Purpose:** Gap closure reference for Phase 83 Plan 03-FIX test rebuild
