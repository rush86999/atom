# Skill Composition Patterns

Skill composition enables chaining multiple skills into complex workflows with automatic dependency resolution, error handling, and transaction rollback. This guide covers workflow design patterns, best practices, and real-world examples.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Basic Patterns](#basic-patterns)
3. [Advanced Patterns](#advanced-patterns)
4. [Data Passing](#data-passing)
5. [API Usage](#api-usage)
6. [Common Workflows](#common-workflows)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Performance Optimization](#performance-optimization)
10. [Examples](#examples)

---

## Core Concepts

### DAG Workflows

Workflows are **Directed Acyclic Graphs (DAGs)**:

- **Directed**: Steps flow in one direction (A → B → C)
- **Acyclic**: No circular dependencies (A → B → A is invalid)
- **Graph**: Steps are nodes, dependencies are edges

**Why DAGs?**
- ✅ Clear execution order (topological sort)
- ✅ Automatic cycle detection
- ✅ Parallel execution support
- ✅ Deadlock prevention

**Example DAG**:
```
    fetch
    /    \
analyze  extract
    \    /
     merge
```

### Step Execution Order

Steps execute in **topological order**:

1. Steps with no dependencies execute first
2. Dependent steps execute after their dependencies
3. Multiple branches execute in parallel when possible
4. Independent steps have no ordering constraint

**Example**:
```python
steps = [
    SkillStep("start", "init", {}, []),           # 1st (no deps)
    SkillStep("branch1", "task_a", {}, ["start"]), # 2nd (depends on start)
    SkillStep("branch2", "task_b", {}, ["start"]), # 2nd (parallel with branch1)
    SkillStep("final", "merge", {}, ["branch1", "branch2"]) # 3rd (wait for both)
]
```

**Execution Order**: start → [branch1, branch2] → final

### DAG Validation

NetworkX automatically validates workflows:

```python
import networkx as nx

graph = nx.DiGraph()
for step in steps:
    graph.add_node(step.step_id)
    for dep in step.dependencies:
        graph.add_edge(dep, step.step_id)

# Check for cycles
if not nx.is_directed_acyclic_graph(graph):
    cycles = list(nx.simple_cycles(graph))
    raise ValueError(f"Workflow contains cycles: {cycles}")

# Get execution order
execution_order = list(nx.topological_sort(graph))
```

---

## Basic Patterns

### Linear Pipeline

Sequential steps where each depends on the previous:

**Pattern**:
```
step1 → step2 → step3 → step4
```

**Use Cases**:
- Data processing pipelines
- Multi-stage transformations
- Sequential validation

**Example**:
```python
from core.skill_composition_engine import SkillCompositionEngine, SkillStep

engine = SkillCompositionEngine(db)

steps = [
    SkillStep("fetch", "http_get", {"url": "api.example.com/data"}, []),
    SkillStep("parse", "json_parse", {}, ["fetch"]),
    SkillStep("validate", "schema_check", {"schema": "v1"}, ["parse"]),
    SkillStep("save", "database_insert", {"table": "results"}, ["validate"])
]

result = await engine.execute_workflow("etl-pipeline", steps, "my-agent")
```

**Execution Flow**:
```
fetch → parse → validate → save
```

**Data Flow**:
```
fetch output → parse input
parse output → validate input
validate output → save input
```

### Fan-Out / Fan-In

One step produces data used by multiple steps, then results merge:

**Pattern**:
```
     fetch
     /    \
analyze  extract
     \    /
      merge
```

**Use Cases**:
- Parallel data processing
- Multi-source data aggregation
- Diversionary workflows

**Example**:
```python
steps = [
    SkillStep("fetch", "http_get", {"url": "api.example.com"}, []),
    SkillStep("analyze", "sentiment_analysis", {"model": "bert"}, ["fetch"]),
    SkillStep("extract", "entity_extraction", {"types": ["person", "org"]}, ["fetch"]),
    SkillStep("merge", "combine_results", {}, ["analyze", "extract"])
]

result = await engine.execute_workflow("fanout-fanin", steps, "my-agent")
```

**Execution Flow**:
```
     fetch
     /    \
analyze  extract  (parallel)
     \    /
      merge
```

**Data Flow**:
```
fetch output → analyze input + extract input
analyze output + extract output → merge input
```

### Conditional Branching

Execute steps based on conditions:

**Pattern**:
```
fetch → (if success) → notify
     → (if failure) → log_error
```

**Use Cases**:
- Error handling workflows
- A/B testing
- Feature flags

**Example**:
```python
steps = [
    SkillStep("fetch", "http_get", {"url": "api.example.com"}, []),
    SkillStep(
        "notify",
        "send_email",
        {"template": "success_notification"},
        ["fetch"],
        condition="fetch.get('success') == True"
    ),
    SkillStep(
        "log_error",
        "log_to_file",
        {"level": "error", "file": "errors.log"},
        ["fetch"],
        condition="fetch.get('success') == False"
    )
]

result = await engine.execute_workflow("conditional-workflow", steps, "my-agent")
```

**Conditional Logic**:
- `condition` field evaluated before step execution
- Python expression syntax
- Access to dependency outputs via step name
- Step skipped if condition evaluates to False

### Error Handling with Rollback

Failed workflows automatically roll back executed steps:

**Pattern**:
```
fetch → process → save
        ↑        ↑
        |        └───── rollback (undo save)
        |              rollback (undo fetch)
        └── failure point
```

**Use Cases**:
- Transactional workflows
- Multi-step operations with side effects
- Data consistency requirements

**Example**:
```python
steps = [
    SkillStep("create_file", "write_file", {"path": "/tmp/data.txt"}, []),
    SkillStep("process", "transform_data", {}, ["create_file"]),
    SkillStep("upload", "s3_upload", {"bucket": "my-bucket"}, ["process"])
]

# If "upload" fails, "create_file" and "process" are rolled back
result = await engine.execute_workflow("transactional-workflow", steps, "my-agent")
```

**Rollback Strategy**:
1. Execute steps in topological order
2. If step fails, stop execution
3. Execute compensation actions in reverse order
4. Return error with rollback details

**Compensation Handlers** (skill-specific):
```python
COMPENSATION_HANDLERS = {
    "write_file": "delete_file",
    "s3_upload": "s3_delete",
    "database_insert": "database_delete",
    "send_email": "delete_email"
}
```

---

## Advanced Patterns

### Map-Reduce

Process data in parallel then aggregate:

**Pattern**:
```
split → process1 ─┐
       → process2 ─→ aggregate
       → process3 ─┘
```

**Use Cases**:
- Batch data processing
- Parallel ETL jobs
- Distributed computations

**Example**:
```python
steps = [
    SkillStep("split", "split_data", {"chunk_size": 100}, []),
    SkillStep("process1", "transform_chunk", {"chunk_id": 1}, ["split"]),
    SkillStep("process2", "transform_chunk", {"chunk_id": 2}, ["split"]),
    SkillStep("process3", "transform_chunk", {"chunk_id": 3}, ["split"]),
    SkillStep("aggregate", "combine_chunks", {}, ["process1", "process2", "process3"])
]

result = await engine.execute_workflow("map-reduce", steps, "my-agent")
```

**Execution Flow**:
```
split → process1 ─┐
     → process2 ──┼→ aggregate (parallel execution)
     → process3 ─┘
```

### Retry Pattern

Add retry policy to steps for transient failures:

**Pattern**:
```
step (with retry_policy)
```

**Use Cases**:
- Network operations
- External API calls
- Database operations

**Example**:
```python
steps = [
    SkillStep(
        "fetch",
        "http_get",
        {"url": "flaky-api.com"},
        [],
        retry_policy={
            "max_retries": 3,
            "backoff": "exponential",
            "initial_delay": 1.0,
            "max_delay": 10.0
        }
    )
]

result = await engine.execute_workflow("retry-workflow", steps, "my-agent")
```

**Retry Logic**:
- `max_retries`: Maximum number of retry attempts
- `backoff`: "linear" or "exponential"
- `initial_delay`: Initial delay in seconds
- `max_delay`: Maximum delay between retries

**Exponential Backoff**:
```
Attempt 1: 0s delay
Attempt 2: 1s delay (2^0 * 1s)
Attempt 3: 2s delay (2^1 * 1s)
Attempt 4: 4s delay (2^2 * 1s)
```

### Timeout Handling

Set timeout for individual steps:

**Pattern**:
```
step (with timeout_seconds)
```

**Use Cases**:
- Prevent runaway operations
- SLA enforcement
- Resource management

**Example**:
```python
steps = [
    SkillStep(
        "quick_operation",
        "fast_task",
        {"data": "small"},
        [],
        timeout_seconds=10
    ),
    SkillStep(
        "slow_operation",
        "heavy_computation",
        {"data": "large"},
        [],
        timeout_seconds=300  # 5 minutes
    )
]

result = await engine.execute_workflow("timeout-workflow", steps, "my-agent")
```

**Timeout Behavior**:
- Step execution cancelled after timeout
- Workflow marked as failed
- Rollback executed for completed steps
- Timeout logged to audit trail

### Sub-Workflow Composition

Embed workflows within workflows:

**Pattern**:
```
main_workflow → sub_workflow_1 → main_workflow_continues
             → sub_workflow_2
```

**Use Cases**:
- Modular workflow design
- Reusable workflow components
- Hierarchical task decomposition

**Example**:
```python
# Define sub-workflows
data_ingestion_workflow = [
    SkillStep("fetch", "http_get", {"url": "api.example.com"}, []),
    SkillStep("parse", "json_parse", {}, ["fetch"])
]

data_enrichment_workflow = [
    SkillStep("enrich", "add_metadata", {}, []),
    SkillStep("validate", "schema_check", {}, ["enrich"])
]

# Combine in main workflow
main_workflow = [
    SkillStep("ingest", "sub_workflow", {"workflow": data_ingestion_workflow}, []),
    SkillStep("enrich", "sub_workflow", {"workflow": data_enrichment_workflow}, ["ingest"]),
    SkillStep("save", "database_insert", {}, ["enrich"])
]

result = await engine.execute_workflow("nested-workflow", main_workflow, "my-agent")
```

---

## Data Passing

### Automatic Output Merging

Step outputs are automatically merged into dependent step inputs:

**Example**:
```python
steps = [
    SkillStep("step1", "skill_a", {"x": 1, "y": 2}, []),
    SkillStep("step2", "skill_b", {"z": 3}, ["step1"])
]
```

**step2 receives**: `{"x": 1, "y": 2, "z": 3, "step1_output": {...}}`

**Merge Rules**:
1. Step's own inputs take precedence
2. Dependency outputs are merged in
3. Conflict: step's inputs override dependency outputs
4. Full dependency output available as `{step_id}_output`

### Explicit Data Passing

Reference specific step outputs using template syntax:

**Example**:
```python
steps = [
    SkillStep("get_user", "fetch_user", {"user_id": 123}, []),
    SkillStep("send_email", {
        "to": "{{get_user.email}}",
        "subject": "Welcome",
        "template": "welcome_email",
        "user_name": "{{get_user.name}}"
    }, ["get_user"])
]
```

**Template Syntax**:
- `{{step_id.field}}`: Reference specific field from step output
- `{{step_id}}`: Reference entire step output
- Templates are resolved before execution

### Data Transformation

Transform data between steps:

**Example**:
```python
steps = [
    SkillStep("fetch", "http_get", {"url": "api.example.com/users"}, []),
    SkillStep("transform", "map_data", {
        "mapping": {
            "user_id": "id",
            "full_name": "name",
            "email_address": "email"
        },
        "source": "{{fetch}}"
    }, ["fetch"]),
    SkillStep("save", "database_insert", {
        "table": "users",
        "data": "{{transform}}"
    }, ["transform"])
]
```

**Transformation Flow**:
```
fetch → transform (remap fields) → save (use transformed data)
```

### Data Aggregation

Aggregate data from multiple steps:

**Example**:
```python
steps = [
    SkillStep("fetch_users", "http_get", {"url": "api.example.com/users"}, []),
    SkillStep("fetch_orders", "http_get", {"url": "api.example.com/orders"}, []),
    SkillStep("fetch_products", "http_get", {"url": "api.example.com/products"}, []),
    SkillStep("merge", "merge_data", {
        "strategy": "join_on_user_id",
        "sources": ["{{fetch_users}}", "{{fetch_orders}}", "{{fetch_products}}"]
    }, ["fetch_users", "fetch_orders", "fetch_products"])
]
```

**Aggregation Flow**:
```
fetch_users ─┐
fetch_orders ─┼→ merge (join data)
fetch_products┘
```

---

## API Usage

### Execute Workflow

```bash
curl -X POST "http://localhost:8000/composition/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "my-workflow",
    "agent_id": "my-agent",
    "steps": [
      {
        "step_id": "fetch",
        "skill_id": "http_get",
        "inputs": {"url": "api.example.com"},
        "dependencies": []
      },
      {
        "step_id": "process",
        "skill_id": "json_parse",
        "inputs": {},
        "dependencies": ["fetch"]
      }
    ]
  }'
```

**Response**:
```json
{
  "success": true,
  "workflow_id": "my-workflow",
  "execution_id": "exec_abc123",
  "results": {
    "fetch": {"status": 200, "data": {...}},
    "process": {"parsed": true, "records": 42}
  },
  "execution_time_seconds": 3.2,
  "steps_executed": 2,
  "steps_succeeded": 2,
  "steps_failed": 0
}
```

### Validate Workflow

Check workflow without executing:

```bash
curl -X POST "http://localhost:8000/composition/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {
        "step_id": "fetch",
        "skill_id": "http_get",
        "inputs": {"url": "api.example.com"},
        "dependencies": []
      },
      {
        "step_id": "process",
        "skill_id": "json_parse",
        "inputs": {},
        "dependencies": ["fetch"]
      }
    ]
  }'
```

**Response**:
```json
{
  "valid": true,
  "node_count": 2,
  "edge_count": 1,
  "execution_order": ["fetch", "process"],
  "parallel_groups": [
    ["fetch"],
    ["process"]
  ],
  "cycles": [],
  "warnings": []
}
```

**Validation Checks**:
- ✅ DAG structure (no cycles)
- ✅ All dependencies reference existing steps
- ✅ No orphaned steps
- ✅ Single root node (no multiple starting points)

### Check Execution Status

```bash
curl "http://localhost:8000/composition/status/{execution_id}"
```

**Response**:
```json
{
  "execution_id": "exec_abc123",
  "workflow_id": "my-workflow",
  "status": "running",
  "current_step": "process",
  "steps_completed": ["fetch"],
  "steps_remaining": ["process", "save"],
  "started_at": "2026-02-19T21:00:00Z",
  "estimated_completion": "2026-02-19T21:00:10Z"
}
```

**Status Values**:
- `pending`: Waiting to start
- `running`: Currently executing
- `completed`: All steps succeeded
- `failed`: One or more steps failed
- `rolled_back`: Workflow failed and was rolled back

---

## Common Workflows

### ETL Pipeline

Extract, Transform, Load pattern:

**Workflow**:
```python
etl_steps = [
    SkillStep("extract", "api_fetch", {
        "endpoint": "/data",
        "params": {"since": "2026-01-01"}
    }, []),
    SkillStep("transform", "data_clean", {
        "operations": ["remove_nulls", "normalize_dates", "deduplicate"]
    }, ["extract"]),
    SkillStep("validate", "schema_check", {
        "schema": "production_v1",
        "strict": true
    }, ["transform"]),
    SkillStep("load", "database_bulk_insert", {
        "table": "analytics_events",
        "batch_size": 1000
    }, ["validate"])
]
```

**Flow**: extract → transform → validate → load

**Use Cases**:
- Data warehouse ETL
- Analytics pipelines
- Data migration

### Data Enrichment

Fetch data, enrich from multiple sources:

**Workflow**:
```python
enrichment_steps = [
    SkillStep("base", "fetch_user", {"user_id": 123}, []),
    SkillStep("enrich_profile", "fetch_profile", {}, ["base"]),
    SkillStep("enrich_activity", "fetch_activity", {"days": 30}, ["base"]),
    SkillStep("enrich_preferences", "fetch_preferences", {}, ["base"]),
    SkillStep("merge", "merge_user_data", {
        "strategy": "merge_all",
        "conflict": "latest_wins"
    }, ["enrich_profile", "enrich_activity", "enrich_preferences"])
]
```

**Flow**:
```
        base
    /     |     \
profile  activity  preferences
    \     |     /
       merge
```

**Use Cases**:
- User profile enrichment
- Lead scoring
- Customer 360 view

### Multi-Channel Notification

Notify via multiple channels:

**Workflow**:
```python
notification_steps = [
    SkillStep("prepare", "format_message", {
        "template": "alert",
        "data": {"event": "system_down", "severity": "critical"}
    }, []),
    SkillStep("email", "send_email", {
        "to": ["admin@example.com"],
        "subject": "Critical Alert"
    }, ["prepare"]),
    SkillStep("slack", "slack_post", {
        "channel": "#alerts",
        "username": "System Bot"
    }, ["prepare"]),
    SkillStep("sms", "send_sms", {
        "to": "+1234567890",
        "message": "{{prepare.short_message}}"
    }, ["prepare"])
]
```

**Flow**:
```
      prepare
    /    |    \
  email slack  sms (parallel)
```

**Use Cases**:
- Incident notifications
- Marketing campaigns
- Status updates

### Web Scraping Pipeline

Scrape, parse, store data:

**Workflow**:
```python
scraping_steps = [
    SkillStep("start", "get_urls", {
        "source": "sitemap.xml",
        "domain": "example.com"
    }, []),
    SkillStep("scrape1", "http_get", {"url": "{{start.urls[0]}"}}, ["start"]),
    SkillStep("scrape2", "http_get", {"url": "{{start.urls[1]}"}}, ["start"]),
    SkillStep("scrape3", "http_get", {"url": "{{start.urls[2]}"}}, ["start"]),
    SkillStep("parse", "parse_html", {
        "selectors": [".title", ".content", ".date"]
    }, ["scrape1", "scrape2", "scrape3"]),
    SkillStep("store", "database_insert", {
        "table": "scraped_data",
        "upsert": true
    }, ["parse"])
]
```

**Flow**:
```
      start
    /   |   \
scrape1 scrape2 scrape3 (parallel)
    \   |   /
       parse
         |
       store
```

**Use Cases**:
- Price monitoring
- Content aggregation
- Competitive intelligence

---

## Best Practices

### Design Principles

**1. Idempotency**
Steps should produce same output for same input:
```python
# GOOD: Idempotent
SkillStep("insert", "upsert_record", {"id": 123, "data": {...}}, [])

# BAD: Not idempotent (duplicates on retry)
SkillStep("insert", "insert_record", {"data": {...}}, [])
```

**2. Isolation**
Each step should do one thing well:
```python
# GOOD: Single responsibility
SkillStep("fetch", "http_get", {"url": "..."}, [])
SkillStep("parse", "json_parse", {}, ["fetch"])

# BAD: Multiple responsibilities
SkillStep("fetch_and_parse", "http_get_and_parse", {"url": "..."}, [])
```

**3. Fail Fast**
Validate inputs early in workflow:
```python
# GOOD: Validate first
SkillStep("validate", "check_inputs", {"schema": "strict"}, [])
SkillStep("process", "transform", {}, ["validate"])

# BAD: Validate late (wastes processing)
SkillStep("process", "transform", {}, [])
SkillStep("validate", "check_inputs", {}, ["process"])
```

**4. Compensation**
Design rollback actions for each step:
```python
# Each step should have undo operation
COMPENSATION_MAP = {
    "create_record": "delete_record",
    "send_email": "delete_email",
    "upload_file": "delete_file",
    "start_transaction": "rollback_transaction"
}
```

### Performance

**1. Minimize Depth**
Reduce workflow depth for faster execution:
```python
# GOOD: Shallow workflow (parallelizable)
steps = [
    SkillStep("a", "task", {}, []),
    SkillStep("b", "task", {}, []),
    SkillStep("merge", "combine", {}, ["a", "b"])
]

# BAD: Deep chain (sequential)
steps = [
    SkillStep(f"step{i}", "task", {}, [f"step{i-1}"] if i > 0 else [])
    for i in range(10)
]
```

**2. Parallel Branches**
Fan-out for independent operations:
```python
# GOOD: Parallel execution
steps = [
    SkillStep("start", "init", {}, []),
    SkillStep("branch1", "process_a", {}, ["start"]),
    SkillStep("branch2", "process_b", {}, ["start"]),
    SkillStep("branch3", "process_c", {}, ["start"])
]

# BAD: Sequential (slower)
steps = [
    SkillStep("branch1", "process_a", {}, []),
    SkillStep("branch2", "process_b", {}, ["branch1"]),
    SkillStep("branch3", "process_c", {}, ["branch2"])
]
```

**3. Batch Operations**
Process multiple items together:
```python
# GOOD: Batch processing
SkillStep("batch", "bulk_insert", {
    "records": "{{all_records}}",
    "batch_size": 1000
}, [])

# BAD: Individual processing
for record in records:
    SkillStep(f"insert_{record.id}", "insert", {"record": record}, [])
```

**4. Cache Results**
Store expensive computations:
```python
# Use cache for expensive operations
SkillStep("expensive", "compute_with_cache", {
    "cache_key": "daily_stats_2026-02-19",
    "ttl": 86400
}, [])
```

### Error Handling

**1. Define Rollback**
Each step needs compensation action:
```python
# Implement compensation handlers
async def compensate_step(step_id, context):
    if step_id == "create_file":
        await delete_file(context["file_path"])
    elif step_id == "send_email":
        await delete_email(context["message_id"])
```

**2. Retry Intelligently**
Only retry transient failures:
```python
# GOOD: Retry transient failures
SkillStep("fetch", "http_get", {}, [],
    retry_policy={"max_retries": 3, "retry_on": ["timeout", "connection_error"]})

# BAD: Retry all failures (wastes resources)
SkillStep("fetch", "http_get", {}, [],
    retry_policy={"max_retries": 3, "retry_on": ["all"]})
```

**3. Log Context**
Include step ID in error messages:
```python
# GOOD: Contextual errors
raise WorkflowError(f"Step {step_id} failed: {error}")

# BAD: Generic errors
raise WorkflowError("Something went wrong")
```

**4. Set Timeouts**
Prevent runaway steps:
```python
# GOOD: Timeout set
SkillStep("process", "heavy_task", {}, [], timeout_seconds=300)

# BAD: No timeout (runs forever)
SkillStep("process", "heavy_task", {}, [])
```

---

## Troubleshooting

### Workflow Validation Fails

**Problem**: "Workflow contains cycles"

**Example**:
```python
# BAD: Cycle (A → B → A)
steps = [
    SkillStep("A", "task1", {}, ["B"]),
    SkillStep("B", "task2", {}, ["A"])
]
```

**Solution**:
1. Review step dependencies:
   ```bash
   curl -X POST "http://localhost:8000/composition/validate" \
     -H "Content-Type: application/json" \
     -d '{"steps": [...]}'
   ```

2. Break cycles by introducing intermediate steps:
   ```python
   # GOOD: No cycle (A → C → B)
   steps = [
       SkillStep("A", "task1", {}, []),
       SkillStep("C", "task3", {}, ["A"]),
       SkillStep("B", "task2", {}, ["C"])
   ]
   ```

### Step Not Found

**Problem**: "Skill not found" during execution

**Solution**:
1. Verify skill is installed or registered:
   ```bash
   curl "http://localhost:8000/api/skills/list?status=Active"
   ```

2. Check skill_id matches exactly:
   ```python
   # GOOD: Exact skill_id
   SkillStep("fetch", "http_get", {}, [])

   # BAD: Typo in skill_id
   SkillStep("fetch", "http_get_wrong", {}, [])
   ```

3. Ensure skill is available to agent (maturity check):
   ```bash
   curl "http://localhost:8000/api/agents/my-agent"
   ```

### Rollback Incomplete

**Problem**: Rollback didn't fully clean up

**Solution**:
1. Implement compensation handlers for skills:
   ```python
   COMPENSATION_HANDLERS = {
       "create_record": "delete_record",
       "upload_file": "delete_file"
   }
   ```

2. Check logs for rollback failures:
   ```bash
   curl "http://localhost:8000/composition/status/{execution_id}" | jq '.rollback_log'
   ```

3. Manual cleanup may be required:
   ```python
   # Manual cleanup script
   await manual_cleanup_workflow(execution_id)
   ```

### Performance Issues

**Problem**: Workflow execution too slow

**Diagnosis**:
1. Check execution time per step:
   ```bash
   curl "http://localhost:8000/composition/status/{execution_id}" | jq '.step_timings'
   ```

2. Identify bottlenecks:
   ```python
   # Find slowest step
   slowest_step = max(step_timings, key=lambda x: x['duration'])
   ```

3. Optimize workflow structure:
   ```python
   # Parallelize independent steps
   # Add caching for expensive operations
   # Batch similar operations
   ```

---

## Performance Optimization

### Minimize Workflow Depth

**Before** (Deep Chain):
```python
steps = [
    SkillStep(f"step{i}", "task", {}, [f"step{i-1}"] if i > 0 else [])
    for i in range(10)
]
# Execution time: 10 * task_time (sequential)
```

**After** (Shallow Tree):
```python
steps = [
    SkillStep("start", "init", {}, []),
    *[SkillStep(f"branch{i}", "task", {}, ["start"]) for i in range(9)],
    SkillStep("merge", "combine", {}, [f"branch{i}" for i in range(9)])
]
# Execution time: 2 * task_time (parallel branches)
```

### Use Parallel Execution

**Before** (Sequential):
```python
steps = [
    SkillStep("fetch1", "http_get", {"url": "api1.com"}, []),
    SkillStep("fetch2", "http_get", {"url": "api2.com"}, ["fetch1"]),
    SkillStep("fetch3", "http_get", {"url": "api3.com"}, ["fetch2"])
]
# Time: 3 * http_time
```

**After** (Parallel):
```python
steps = [
    SkillStep("fetch1", "http_get", {"url": "api1.com"}, []),
    SkillStep("fetch2", "http_get", {"url": "api2.com"}, []),
    SkillStep("fetch3", "http_get", {"url": "api3.com"}, []),
    SkillStep("merge", "combine", {}, ["fetch1", "fetch2", "fetch3"])
]
# Time: 1 * http_time (parallel)
```

### Batch Similar Operations

**Before** (Individual):
```python
for record in records:
    SkillStep(f"insert_{record.id}", "insert", {"record": record}, [])
# Time: N * insert_time
```

**After** (Batch):
```python
SkillStep("batch_insert", "bulk_insert", {
    "records": records,
    "batch_size": 1000
}, [])
# Time: (N / 1000) * insert_time
```

### Cache Expensive Operations

**Before** (No Cache):
```python
# Recomputes every time
SkillStep("expensive", "compute_daily_stats", {}, [])
```

**After** (With Cache):
```python
SkillStep("expensive", "compute_daily_stats", {
    "cache_key": "stats_2026-02-19",
    "ttl": 86400  # Cache for 24 hours
}, [])
```

---

## Examples

### Example 1: Web Scraping with Enrichment

```python
from core.skill_composition_engine import SkillCompositionEngine, SkillStep

engine = SkillCompositionEngine(db)

steps = [
    # Start: Get URLs to scrape
    SkillStep("get_urls", "sitemap_parser", {
        "domain": "example.com",
        "max_urls": 10
    }, []),

    # Scrape pages in parallel
    SkillStep("scrape1", "http_get", {"url": "{{get_urls.urls[0]}"}}, ["get_urls"]),
    SkillStep("scrape2", "http_get", {"url": "{{get_urls.urls[1]}"}}, ["get_urls"]),
    SkillStep("scrape3", "http_get", {"url": "{{get_urls.urls[2]}"}}, ["get_urls"]),

    # Parse scraped HTML
    SkillStep("parse", "parse_html", {
        "selectors": {
            "title": "h1",
            "content": ".article-content",
            "author": ".author-name"
        }
    }, ["scrape1", "scrape2", "scrape3"]),

    # Enrich with additional data
    SkillStep("enrich", "add_metadata", {
        "add_timestamp": True,
        "add_word_count": True
    }, ["parse"]),

    # Store in database
    SkillStep("store", "database_bulk_insert", {
        "table": "scraped_articles",
        "upsert": True,
        "conflict_columns": ["url"]
    }, ["enrich"])
]

result = await engine.execute_workflow("scraping-workflow", steps, "my-agent")
```

**Execution Flow**:
```
get_urls
   /  |  \
scrape1 scrape2 scrape3 (parallel)
   \  |  /
    parse
      |
    enrich
      |
    store
```

### Example 2: Data Pipeline with Error Handling

```python
steps = [
    # Extract data from API
    SkillStep("extract", "api_fetch", {
        "endpoint": "/analytics/events",
        "params": {"since": "2026-02-01"}
    }, [],
    retry_policy={"max_retries": 3, "backoff": "exponential"}),

    # Validate schema
    SkillStep("validate", "schema_check", {
        "schema": "analytics_events_v2",
        "strict": True
    }, ["extract"]),

    # Transform data
    SkillStep("transform", "data_transform", {
        "operations": [
            "normalize_timestamps",
            "remove_pii",
            "enrich_user_data"
        ]
    }, ["validate"]),

    # Load to data warehouse
    SkillStep("load", "warehouse_load", {
        "table": "analytics.events",
        "mode": "append",
        "partition": "date"
    }, ["transform"],
    timeout_seconds=600),  # 10 minute timeout

    # Update metrics
    SkillStep("metrics", "update_metrics", {
        "metric_name": "etl.last_success",
        "value": "{{transform.timestamp}}"
    }, ["load"])
]

result = await engine.execute_workflow("data-pipeline", steps, "my-agent")
```

**Features**:
- Retry on API failures
- Schema validation
- Timeout protection
- Metrics update

### Example 3: Multi-Channel Alerting

```python
steps = [
    # Detect incident
    SkillStep("detect", "check_system_health", {
        "services": ["api", "database", "cache"],
        "threshold": "critical"
    }, []),

    # Prepare notification (if critical)
    SkillStep("prepare", "format_alert", {
        "template": "incident_notification",
        "severity": "{{detect.severity}}"
    }, ["detect"],
    condition="{{detect.status}} == 'critical'"),

    # Send to multiple channels (parallel)
    SkillStep("email", "send_email", {
        "to": ["oncall@example.com"],
        "subject": "CRITICAL: {{prepare.title}}",
        "body": "{{prepare.message}}"
    }, ["prepare"],
    condition="{{detect.status}} == 'critical'"),

    SkillStep("slack", "slack_post", {
        "channel": "#incidents",
        "username": "Incident Bot",
        "message": "{{prepare.slack_message}}"
    }, ["prepare"],
    condition="{{detect.status}} == 'critical'"),

    SkillStep("pagerduty", "pagerduty_trigger", {
        "service_key": "{{SECRETS.PAGERDUTY_KEY}}",
        "description": "{{prepare.title}}"
    }, ["prepare"],
    condition="{{detect.status}} == 'critical'"),

    # Log incident
    SkillStep("log", "log_incident", {
        "table": "incidents",
        "severity": "{{detect.severity}}",
        "channels_sent": ["email", "slack", "pagerduty"]
    }, ["email", "slack", "pagerduty"])
]

result = await engine.execute_workflow("incident-alerting", steps, "my-agent")
```

**Features**:
- Conditional execution (only on critical)
- Parallel notifications
- Multiple channels
- Audit logging

---

## Summary

Skill composition enables complex workflows with:

- ✅ **DAG Validation**: Automatic cycle detection
- ✅ **Data Passing**: Automatic output merging and templates
- ✅ **Error Handling**: Rollback and compensation
- ✅ **Parallel Execution**: Independent steps run concurrently
- ✅ **Retry Logic**: Handle transient failures
- ✅ **Timeout Protection**: Prevent runaway operations
- ✅ **Conditional Execution**: Skip steps based on conditions
- ✅ **Performance Optimization**: Minimize depth, maximize parallelism

**Next Steps**:
1. Review basic patterns (linear, fan-out/fan-in, conditional)
2. Design workflows with DAG structure
3. Use parallel execution for independent steps
4. Implement compensation handlers for rollback
5. Test workflows with validation endpoint

---

**See Also**:
- [Advanced Skill Execution](./ADVANCED_SKILL_EXECUTION.md) - Phase 60 overview
- [Skill Marketplace Guide](./SKILL_MARKETPLACE_GUIDE.md) - Finding skills to compose
- [Performance Tuning](./PERFORMANCE_TUNING.md) - Optimization guide

**Last Updated**: February 19, 2026
