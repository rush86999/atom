# Self-Evolution & Reflection Pool

**Last Updated**: April 12, 2026
**Reading Time**: 15 minutes
**Difficulty**: Advanced

---

## Overview

Atom's **Self-Evolution** system enables agents to learn from their mistakes, critique their own performance, and automatically improve their capabilities over time. This is achieved through three interconnected systems:

1. **Reflection Pool** - Stores agent self-critiques and mistakes
2. **Memento-Skills** - Generates new skills from failure patterns
3. **AlphaEvolver** - Optimizes existing skills through mutation

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Self-Evolution System                  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Reflection  │    │   Episodic   │    │  Graduation  │
│    Pool      │    │   Memory     │    │  Framework   │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        │                     └──────────┬──────────┘
        │                                │
        ▼                                ▼
┌──────────────┐              ┌──────────────┐
│  Auto-Dev    │◄────────────►│  Experience  │
│  Module      │   Feedback   │   Tracking   │
└──────────────┘              └──────────────┘
        │
    ┌───┴───┐
    │       │
    ▼       ▼
┌─────────┐ ┌─────────┐
│Memento  │ │  Alpha  │
│ Skills  │ │Evolver  │
└─────────┘ └─────────┘
```

---

## 1. Reflection Pool (Critique-Based Mistakes Storage)

### What is the Reflection Pool?

The **Reflection Pool** is a vector database (LanceDB) that stores agent self-critiques - structured records of what an agent tried, what went wrong, and what it learned.

### Why It Matters

- 🧠 **Pattern Recognition**: Identify recurring mistakes across episodes
- 🎯 **Contextual Learning**: Retrieve relevant past mistakes for current situations
- 📊 **Measurable Improvement**: Track reduction in error rates over time
- 🔄 **Continuous Feedback**: Feed critiques into skill generation (Memento-Skills)

### Data Model

Each critique record contains:

```python
class Critique:
    id: str                    # Unique critique ID
    agent_id: str              # Agent that created this critique
    tenant_id: str             # Workspace/organization
    intent: str                # What the agent was trying to do
    action_taken: str          # What action the agent performed
    outcome_state: str         # Result (success/failure/partial)
    critique: str              # Self-critique (LLM-generated)
    timestamp: str             # When this occurred
    vector: List[float]        # Embedding for semantic search
```

### How It Works

#### 1. Agent Self-Critique

After each task, agents can generate self-critiques:

```python
from core.reflection_service import ReflectionService

reflection = ReflectionService(tenant_id="workspace_123")

# Agent critiques its own performance
await reflection.add_critique(
    agent_id="agent_abc",
    intent="Schedule a meeting with the sales team",
    action_taken="Called calendar API with Monday 2pm",
    outcome_state="failure",
    critique_text="Failed because Monday is a holiday. Should check for holidays first."
)
```

#### 2. Vector Storage & Retrieval

Critiques are embedded and stored in LanceDB for semantic search:

```python
# Find relevant past critiques for current task
critiques = await reflection.get_relevant_critiques(
    agent_id="agent_abc",
    current_intent="Schedule client meeting for next week",
    limit=3
)

# Returns critiques about similar scheduling mistakes
# Example: "Forgot to check attendee availability"
#          "Didn't consider time zone differences"
```

#### 3. Pattern Detection

The **ReflectionEngine** monitors the event bus for recurring failure patterns:

```python
from core.auto_dev.reflection_engine import ReflectionEngine

engine = ReflectionEngine(db, failure_threshold=2)
engine.register()  # Monitors all task failures

# When 2+ similar failures occur:
# → Triggers MementoEngine to generate a new skill
```

### Integration with Episodic Memory

The Reflection Pool complements Episodic Memory:

| Aspect | Episodic Memory | Reflection Pool |
|--------|----------------|-----------------|
| **Purpose** | Track complete agent interactions | Store self-critiques and lessons |
| **Storage** | PostgreSQL (hot) + LanceDB (cold) | LanceDB (vector search) |
| **Retrieval** | Temporal, semantic, sequential | Semantic similarity only |
| **Use Case** | Graduation requirements, audit trail | Skill generation, pattern detection |
| **Content** | Full episodes (messages, actions, canvas) | Structured critiques (intent, outcome, lesson) |

---

## 2. Memento-Skills: Learning from Mistakes

### What are Memento-Skills?

**Memento-Skills** are automatically generated skills that address recurring failure patterns. When an agent makes the same mistake multiple times, the system:

1. **Detects the pattern** (ReflectionEngine)
2. **Analyzes the failure** (MementoEngine)
3. **Generates skill code** (LLM)
4. **Tests in sandbox** (ContainerSandbox)
5. **Requests approval** (User)
6. **Installs the skill** (SkillBuilderService)

### Example: Learning from API Timeout Mistakes

**Pattern Detected:**
```
Episode 1: Agent calls external API → times out after 30s → fails
Episode 2: Agent calls same API → times out after 30s → fails
Episode 3: Agent calls same API → times out after 30s → fails
```

**ReflectionEngine Triggers MementoEngine:**
```python
# ReflectionEngine detects 3 similar failures
failure_pattern = {
    "task_description": "Fetch customer data from CRM API",
    "error_trace": "TimeoutError: Request timed out after 30s",
    "occurrences": 3
}

# Triggers MementoEngine
memento = MementoEngine(db)
skill_candidate = await memento.analyze_episode(episode_id="ep_123")
```

**MementoEngine Generates Skill:**
```python
# LLM generates skill code with retry logic
skill_code = '''
async def fetch_crm_data_with_retry(customer_id: str, max_retries: int = 3):
    """Fetch CRM data with exponential backoff retry."""
    import asyncio
    import httpx

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.crm.com/customers/{customer_id}",
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except (httpx.TimeoutException, httpx.HTTPError) as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2.0 * (2 ** attempt)
            await asyncio.sleep(wait_time)

    return {}
'''
```

**Result:** Agent now has a new skill that handles API timeouts gracefully!

### Memento-Skill vs AlphaEvolver

| Aspect | Memento-Skills | AlphaEvolver |
|--------|---------------|--------------|
| **Purpose** | Generate NEW capabilities | Optimize EXISTING skills |
| **Trigger** | Recurring failures (auto) | Performance issues (manual/auto) |
| **Input** | Failed episodes | Successful episodes |
| **Output** | New skill proposal | Optimized skill variant |
| **Maturity Required** | INTERN+ | SUPERVISED+ (manual), AUTONOMOUS (auto) |
| **Example** | Learn to retry API calls | Optimize retry logic for speed |

---

## 3. AlphaEvolver: Optimizing Through Mutation

### What is AlphaEvolver?

**AlphaEvolver** improves existing skills through iterative mutation and fitness-based selection. It's inspired by genetic algorithms:

1. **Generate Variants** - Create 3-5 mutations of skill code
2. **Test in Sandbox** - Run each variant against test cases
3. **Measure Fitness** - Score on latency, accuracy, token usage
4. **Select Best** - Keep highest-scoring variant
5. **Repeat** - Iterate for N generations

### Example: Optimizing Data Analysis Skill

**Current Skill** (slow):
```python
async def analyze_sales_data(sales_records: list) -> dict:
    """Analyze sales data and generate insights."""
    insights = {}

    for record in sales_records:  # O(n²) - slow for large datasets
        for category in insights:
            # ... complex processing ...
            pass

    return insights
```

**AlphaEvolver Generates Variants:**
```python
# Variant 1: Use pandas for vectorization
async def analyze_sales_data(sales_records: list) -> dict:
    import pandas as pd
    df = pd.DataFrame(sales_records)
    # ... vectorized operations ...
    return insights

# Variant 2: Add caching
async def analyze_sales_data(sales_records: list) -> dict:
    cache_key = hash(str(sales_records))
    if cache_key in _cache:
        return _cache[cache_key]
    # ... analysis ...
    _cache[cache_key] = insights
    return insights

# Variant 3: Parallel processing
async def analyze_sales_data(sales_records: list) -> dict:
    import asyncio
    chunks = [sales_records[i::4] for i in range(4)]
    results = await asyncio.gather(*[
        _analyze_chunk(chunk) for chunk in chunks
    ])
    # ... merge results ...
    return insights
```

**Fitness Comparison:**
| Variant | Latency | Token Usage | Accuracy | Score |
|---------|---------|-------------|----------|-------|
| Original | 5.2s | 1200 | 100% | 0.65 |
| Variant 1 (pandas) | 0.8s | 800 | 100% | 0.95 ✅ |
| Variant 2 (cache) | 4.9s | 1200 | 100% | 0.68 |
| Variant 3 (parallel) | 1.4s | 1100 | 100% | 0.88 |

**Result:** Variant 1 is selected - 6.5x faster!

### Evolution Triggers

**Manual Trigger** (SUPERVISED+ agents):
```bash
curl -X POST http://localhost:8000/api/v1/auto-dev/evolve \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "analyze_sales_data",
    "optimization_goal": "latency",
    "generations": 5
  }'
```

**Automatic Trigger** (AUTONOMOUS agents):
- Latency > 5 seconds
- Token usage > 5000
- Low fitness score detected
- Workspace has enabled auto-evolution

---

## 4. How It All Fits Together

### The Complete Learning Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                    1. Agent Task Execution                    │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    2. Episode Recorded                        │
│  - Stores in Episodic Memory (PostgreSQL + LanceDB)           │
│  - Tracks success/failure for graduation                     │
└────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
         ┌──────────────────┐   ┌──────────────────┐
         │    SUCCESS       │   │    FAILURE       │
         └──────────────────┘   └──────────────────┘
                    │                   │
                    │                   ▼
                    │      ┌──────────────────────────────┐
                    │      │  3. Reflection Pool Update   │
                    │      │  - Generate self-critique    │
                    │      │  - Store in LanceDB          │
                    │      └──────────────────────────────┘
                    │                   │
                    │                   ▼
                    │      ┌──────────────────────────────┐
                    │      │  4. Pattern Detection        │
                    │      │  - ReflectionEngine monitors │
                    │      │  - Detects recurring fails  │
                    │      └──────────────────────────────┘
                    │                   │
                    │           ┌───────┴───────┐
                    │           │               │
                    │           ▼               ▼
                    │  ┌─────────────┐  ┌─────────────┐
                    │  │ Threshold   │  │ No Pattern  │
                    │  │ Met (≥2)    │  │ Detected    │
                    │  └──────┬──────┘  └─────────────┘
                    │         │
                    │         ▼
                    │  ┌──────────────────────────────┐
                    │  │  5. Memento-Skill Generation │
                    │  │  - Analyze failure pattern   │
                    │  │  - Generate skill code       │
                    │  │  - Test in sandbox           │
                    │  │  - Request user approval     │
                    │  └──────────────────────────────┘
                    │           │
                    │           ▼
                    │  ┌──────────────────────────────┐
                    │  │  6. Skill Installation       │
                    │  │  - User approves             │
                    │  │  - SkillBuilderService       │
                    │  │  - Agent now has new skill  │
                    │  └──────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────────┐
         │  7. AlphaEvolver (Optional)  │
         │  - Monitor skill performance │
         │  - Trigger optimization      │
         │  - Generate variants         │
         │  - Deploy best performer     │
         └──────────────────────────────┘
```

### Integration with Agent Graduation

The Self-Evolution system directly impacts **Agent Graduation**:

| Graduation Metric | Self-Evolution Impact |
|-------------------|----------------------|
| **Episode Count** | Memento-Skills reduce failures → More successful episodes |
| **Intervention Rate** | Learned skills reduce need for human corrections |
| **Constitutional Score** | Critiques improve governance compliance |
| **Confidence Score** | Pattern recognition increases decision quality |

**Example:**
```
Agent: customer-support-bot (INTERN level)

Before Memento-Skills:
- 15 episodes completed
- 8 interventions (53% rate)
- 0.72 constitutional score
- ❌ Not ready for SUPERVISED promotion

After learning "Handle API Timeouts" skill:
- 20 episodes completed
- 3 interventions (15% rate) ✅
- 0.88 constitutional score ✅
- ✅ Ready for SUPERVISED promotion!
```

### Feedback Loops

```
┌──────────────────────────────────────────────────────────────┐
│                    Positive Feedback Loop                    │
└──────────────────────────────────────────────────────────────┘
     Better Skills → Fewer Failures → Higher Success Rate
          ↑                                            ↓
          └────────────── Lower Intervention Rate ────────┘
                            ↓
                   Faster Graduation → More Autonomy


┌──────────────────────────────────────────────────────────────┐
│                    Negative Feedback Loop (Prevented)        │
└──────────────────────────────────────────────────────────────┘
     Recurring Failures → Pattern Detection → Memento-Skills
                            ↓
                     New Skill Created → Breaks the Cycle
```

---

## 5. Architecture & Implementation

### Core Components

#### ReflectionService (`backend/core/reflection_service.py`)
```python
class ReflectionService:
    async def add_critique(agent_id, intent, action, outcome, critique)
    async def get_relevant_critiques(agent_id, current_intent, limit)
```

#### ReflectionEngine (`backend/core/auto_dev/reflection_engine.py`)
```python
class ReflectionEngine:
    def register()  # Register on event bus
    async def process_failure(event)  # Monitor failures
    def _find_similar_failures(agent_id, task_description)
```

#### MementoEngine (`backend/core/auto_dev/memento_engine.py`)
```python
class MementoEngine:
    async def analyze_episode(episode_id)  # Extract failure pattern
    async def propose_code_change(failure_pattern)  # Generate skill
    async def validate_change(skill_candidate)  # Sandbox test
    async def promote_skill(skill_candidate)  # Install skill
```

#### AlphaEvolverEngine (`backend/core/auto_dev/alpha_evolver_engine.py`)
```python
class AlphaEvolverEngine:
    async def analyze_episode(episode_id)  # Identify optimization targets
    async def generate_tool_mutation(skill_code)  # Create variants
    async def sandbox_execute_mutation(variant)  # Test in sandbox
    async def spawn_workflow_variant(variant)  # Track for comparison
    async def run_research_experiment(generations)  # Evolution loop
```

#### EvolutionEngine (`backend/core/auto_dev/evolution_engine.py`)
```python
class EvolutionEngine:
    def register()  # Register on event bus
    async def process_execution(event)  # Monitor skill performance
    def _check_optimization_triggers(event)  # Latency, tokens, etc.
```

### Database Schema

**LanceDB: reflection_pool**
```python
{
    "id": "uuid",
    "agent_id": "string",
    "tenant_id": "string",
    "intent": "string",
    "action_taken": "string",
    "outcome_state": "string",  # success/failure/partial
    "critique": "string",
    "timestamp": "iso8601",
    "vector": [float]  # 384-dim embedding
}
```

**PostgreSQL: skill_candidates** (Memento proposals)
```python
{
    "id": "uuid",
    "agent_id": "string",
    "skill_name": "string",
    "skill_code": "text",
    "failure_pattern": "jsonb",
    "sandbox_result": "jsonb",
    "status": "pending|approved|rejected",
    "created_at": "timestamp"
}
```

**PostgreSQL: tool_mutations** (AlphaEvolver variants)
```python
{
    "id": "uuid",
    "skill_name": "string",
    "parent_mutation_id": "uuid",
    "mutation_code": "text",
    "fitness_score": "float",
    "generation": "int",
    "status": "candidate|deployed|rejected"
}
```

### Event Bus Integration

Auto-Dev components publish/subscribe to the global event bus:

```python
from core.auto_dev.event_hooks import event_bus

# Publish events
event_bus.publish_task_fail(
    agent_id="agent_123",
    episode_id="ep_456",
    task_description="Send email to customer",
    error_trace="SMTPException: Connection refused"
)

event_bus.publish_skill_execution(
    agent_id="agent_123",
    skill_name="send_email",
    latency_seconds=8.5,  # Trigger: >5s
    token_usage=6500,      # Trigger: >5000
    success=True
)

# Subscribe to events
event_bus.on_task_fail(reflection_engine.process_failure)
event_bus.on_skill_execution(evolution_engine.process_execution)
```

---

## 6. Usage & Configuration

### Enable Auto-Dev for Workspace

**Via API:**
```bash
curl -X PATCH http://localhost:8000/api/v1/workspaces/{workspace_id} \
  -H "Content-Type: application/json" \
  -d '{
    "configuration": {
      "auto_dev": {
        "enabled": true,
        "memento_enabled": true,
        "alpha_evolver_enabled": true,
        "reflection_enabled": true,
        "failure_threshold": 2,
        "evolution_generations": 5
      }
    }
  }'
```

**Via Database:**
```sql
UPDATE workspaces
SET configuration = jsonb_set(
    configuration,
    '{auto_dev,enabled}',
    'true'
)
WHERE id = 'workspace_123';
```

### Environment Variables

```bash
# Auto-Dev Configuration
AUTO_DEV_ENABLED=true
MEMENTO_SKILLS_ENABLED=true
ALPHA_EVOLVER_ENABLED=true
REFLECTION_POOL_ENABLED=true

# Sandbox Configuration
SANDBOX_TYPE=docker  # docker | mock
DOCKER_IMAGE=python:3.11-slim
SANDBOX_TIMEOUT_SECONDS=300

# Evolution Thresholds
EVOLUTION_LATENCY_THRESHOLD_SECONDS=5.0
EVOLUTION_TOKEN_THRESHOLD=5000
EVOLUTION_FITNESS_THRESHOLD=0.7
```

### Maturity Gates

Auto-Dev features are gated by agent maturity:

| Feature | STUDENT | INTERN | SUPERVISED | AUTONOMOUS |
|---------|---------|--------|------------|------------|
| **Generate Critiques** | ❌ | ✅ | ✅ | ✅ |
| **Reflection Pool** | ❌ | ✅ | ✅ | ✅ |
| **Memento-Skills (Auto)** | ❌ | ✅ | ✅ | ✅ |
| **AlphaEvolver (Manual)** | ❌ | ❌ | ✅ | ✅ |
| **AlphaEvolver (Auto)** | ❌ | ❌ | ❌ | ✅ |

**Rationale:**
- **STUDENT**: Too risky - agents still learning basics
- **INTERN**: Can learn from own mistakes but needs oversight
- **SUPERVISED**: Trusted to optimize with manual approval
- **AUTONOMOUS**: Full self-evolution capability

---

## 7. Monitoring & Observability

### Key Metrics

**Reflection Pool Health:**
```python
# Total critiques stored
reflection_pool_count = db.query(Critique).count()

# Critiques per agent (last 30 days)
critiques_per_agent = db.query(Critique.agent_id, func.count(Critique.id))
    .filter(Critique.timestamp > datetime.now() - timedelta(days=30))
    .group_by(Critique.agent_id)
    .all()

# Pattern detection rate
patterns_detected = reflection_engine.patterns_detected_count
skills_generated = memento_engine.skills_created_count
```

**Memento-Skills Performance:**
```python
# Skills proposed vs approved
skills_proposed = db.query(SkillCandidate).count()
skills_approved = db.query(SkillCandidate).filter_by(status='approved').count()
approval_rate = skills_approved / skills_proposed

# Failure reduction after skill installation
failure_rate_before = calculate_failure_rate(agent_id, before_skill_install)
failure_rate_after = calculate_failure_rate(agent_id, after_skill_install)
improvement = failure_rate_before - failure_rate_after
```

**AlphaEvolver Effectiveness:**
```python
# Optimization success rate
optimizations_attempted = db.query(ToolMutation).count()
optimizations_deployed = db.query(ToolMutation).filter_by(status='deployed').count()
success_rate = optimizations_deployed / optimizations_attempted

# Average improvement per optimization
avg_latency_improvement = db.query(func.avg(ToolMutation.latency_reduction)).all()
avg_token_reduction = db.query(func.avg(ToolMutation.token_reduction)).all()
```

### Prometheus Metrics

Auto-Dev exposes metrics for monitoring:

```python
# Reflection Pool
atom_reflection_pool_critiques_total{agent_id, tenant_id}
atom_reflection_pool_retrieval_count{agent_id}

# Memento-Skills
atom_memento_patterns_detected_total
atom_memento_skills_proposed_total
atom_memento_skills_approved_total
atom_memento_failure_rate{agent_id}

# AlphaEvolver
atom_evolver_mutations_total{skill_name}
atom_evolver_deployments_total{skill_name}
atom_evolver_latency_improvement{skill_name}
atom_evolver_token_improvement{skill_name}
```

### Logging

```python
import logging

logger = logging.getLogger("atom.auto_dev")

# ReflectionEngine
logger.info(f"Pattern detected: {failure_pattern}")
logger.info(f"Triggering MementoEngine for agent {agent_id}")

# MementoEngine
logger.info(f"Skill proposal generated: {skill_name}")
logger.warning(f"Sandbox validation failed: {error}")

# AlphaEvolver
logger.info(f"Variant {variant_id} outperformed parent: {fitness_score}")
logger.info(f"Deploying optimized skill version {generation}")
```

---

## 8. Best Practices & Patterns

### When to Use Each Component

**Use Reflection Pool when:**
- ✅ Agent needs to learn from specific mistakes
- ✅ You want to track error patterns over time
- ✅ Agent should avoid repeating past failures

**Use Memento-Skills when:**
- ✅ Agent makes the same mistake ≥2 times
- ✅ A new capability would prevent failures
- ✅ Agent is INTERN level or higher

**Use AlphaEvolver when:**
- ✅ Skill is slow (latency > 5s)
- ✅ Skill uses too many tokens (>5000)
- ✅ Skill has edge cases or partial failures
- ✅ Agent is SUPERVISED level or higher

### Common Pitfalls

**❌ Don't enable Auto-Dev for STUDENT agents**
- They lack sufficient experience to generate meaningful critiques
- Risk of generating low-quality skills

**❌ Don't ignore sandbox validation**
- Always test generated skills before deployment
- Unvalidated code can introduce security vulnerabilities

**❌ Don't set failure_threshold too low**
- threshold=1 generates too many false positives
- Recommended: threshold=2 or threshold=3

**❌ Don't allow fully automatic evolution for critical skills**
- Skills that modify data, send emails, or make payments should require manual approval
- Use `requires_approval=True` for high-risk skills

### Example: Complete Workflow

```python
# 1. Enable Auto-Dev for workspace
workspace = await update_workspace_config(
    workspace_id="ws_123",
    config={
        "auto_dev": {
            "enabled": True,
            "memento_enabled": True,
            "alpha_evolver_enabled": True,
            "failure_threshold": 2
        }
    }
)

# 2. Agent generates critiques after tasks
await reflection_service.add_critique(
    agent_id="agent_abc",
    intent="Process customer refund",
    action_taken="Called refund API with amount $500",
    outcome_state="failure",
    critique="Failed because amount > approval threshold. Need manager approval first."
)

# 3. ReflectionEngine detects pattern (2+ similar failures)
# → Triggers MementoEngine automatically

# 4. MementoEngine generates skill proposal
skill_candidate = await memento_engine.analyze_episode(episode_id="ep_456")
# → Generates: check_refund_approval_limit()

# 5. User approves skill
await skill_builder_service.install_skill(
    skill_id=skill_candidate.id,
    approved_by="user_123"
)

# 6. Agent now has new skill - avoids future failures!

# 7. Later, AlphaEvolver optimizes the skill
await evolution_engine.trigger_optimization(
    skill_name="check_refund_approval_limit",
    optimization_goal="latency"
)
# → Generates faster variant with caching
```

---

## 9. Advanced Topics

### Multi-Agent Reflection Sharing

Agents can share critiques within a workspace (with governance):

```python
# Enable shared reflection pool
await workspace_service.update_config(
    workspace_id="ws_123",
    config={"shared_reflection_pool": True}
)

# Agent A learns from Agent B's mistakes
critiques = await reflection_service.get_relevant_critiques(
    agent_id="agent_a",
    current_intent="Process refund",
    limit=5,
    include_shared=True  # Include critiques from other agents
)
```

### Custom Fitness Functions

Define custom optimization goals:

```python
from core.auto_dev.fitness_service import FitnessService

def custom_fitness_fn(result: dict) -> float:
    """Custom fitness: prioritize accuracy over speed."""
    accuracy_score = result.get("accuracy", 0.0) * 0.7  # 70% weight
    latency_score = (1.0 / result.get("latency", 1.0)) * 0.3  # 30% weight
    return accuracy_score + latency_score

await alpha_evolver.optimize_skill(
    skill_name="data_analysis",
    fitness_fn=custom_fitness_fn,
    generations=10
)
```

### Critique-Based Prompt Engineering

Use critiques to improve agent prompts:

```python
# Retrieve relevant past critiques
critiques = await reflection_service.get_relevant_critiques(
    agent_id="agent_abc",
    current_intent="Schedule meeting with client",
    limit=3
)

# Inject into agent prompt
critique_context = "\n\n".join([
    f"Past Mistake: {c['critique']}\nAvoid: {c['action_taken']}"
    for c in critiques
])

enhanced_prompt = f"""
You are a scheduling assistant. When scheduling meetings:

{critique_context}

Best Practices:
- Always check for holidays first
- Verify attendee availability
- Consider time zone differences
"""
```

---

## 10. Troubleshooting

### Reflection Pool Empty

**Problem**: No critiques stored despite agent failures

**Diagnosis**:
```bash
# Check if reflection is enabled
curl http://localhost:8000/api/v1/workspaces/{workspace_id} | jq .configuration.auto_dev.reflection_enabled

# Check agent maturity
curl http://localhost:8000/api/v1/agents/{agent_id} | jq .maturity_level
```

**Solutions**:
1. Enable `reflection_enabled=true` in workspace config
2. Ensure agent is INTERN level or higher
3. Check LanceDB connection: `python -c "from core.lancedb_service import LanceDBService; LanceDBService().get_or_create_reflection_pool_table()"`

### Memento-Skills Not Generating

**Problem**: No skill proposals despite recurring failures

**Diagnosis**:
```bash
# Check failure threshold
curl http://localhost:8000/api/v1/workspaces/{workspace_id} | jq .configuration.auto_dev.failure_threshold

# Check ReflectionEngine logs
tail -f logs/atom.log | grep ReflectionEngine
```

**Solutions**:
1. Lower `failure_threshold` to 2 (default is 3)
2. Ensure failures are similar (task description + error trace)
3. Check that MementoEngine is registered on event bus

### AlphaEvolver Not Optimizing

**Problem**: No skill variants generated

**Diagnosis**:
```bash
# Check if auto-evolution is enabled
curl http://localhost:8000/api/v1/workspaces/{workspace_id} | jq .configuration.auto_dev.alpha_evolver_enabled

# Check agent maturity
curl http://localhost:8000/api/v1/agents/{agent_id} | jq .maturity_level
```

**Solutions**:
1. For automatic evolution: Agent must be AUTONOMOUS
2. For manual evolution: Agent must be SUPERVISED+
3. Trigger manually: `POST /api/v1/auto-dev/evolve`

### Sandbox Validation Failures

**Problem**: All skill proposals fail sandbox validation

**Diagnosis**:
```bash
# Check sandbox logs
docker logs atom-sandbox-{container_id}

# Check skill code for syntax errors
python -m py_compile skill_code.py
```

**Solutions**:
1. Ensure Docker is available: `docker ps`
2. Check sandbox timeout: Increase `SANDBOX_TIMEOUT_SECONDS`
3. Review skill code for missing imports or dependencies

---

## 11. Related Documentation

### Core Systems
- **[Episodic Memory](episodic-memory.md)** - Episode tracking and retrieval
- **[Agent Graduation](../agents/graduation.md)** - Maturity promotion framework
- **[Vector Embeddings](vector-embeddings.md)** - Semantic search infrastructure

### Auto-Dev Module
- **[Auto-Dev User Guide](../GUIDES/AUTO_DEV_USER_GUIDE.md)** - Getting started with Auto-Dev
- **[Event Bus Architecture](../reference/ARCHITECTURE_DIAGRAMS.md)** - Event-driven system design

### Development
- **[Testing Guide](../../DEVELOPMENT/TESTING_GUIDE.md)** - Property-based testing for Auto-Dev
- **[Code Quality](../../DEVELOPMENT/code-quality.md)** - Auto-Dev code standards

### API Reference
- **Reflection Service API**: `POST /api/v1/reflection/critiques`
- **Memento Skills API**: `GET /api/v1/auto-dev/skills/candidates`
- **AlphaEvolver API**: `POST /api/v1/auto-dev/evolve`

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **Reflection Pool** | Vector database storing agent self-critiques for pattern recognition |
| **Critique** | Structured record of intent, action, outcome, and learned lesson |
| **Memento-Skills** | Auto-generated skills from recurring failure patterns |
| **AlphaEvolver** | Skill optimization system through mutation and fitness selection |
| **Failure Pattern** | Set of ≥2 similar task failures that trigger skill generation |
| **Fitness Score** | Multi-metric score (latency, tokens, accuracy) for variant comparison |
| **Sandbox** | Isolated Docker environment for testing skill code |
| **Variant** | Mutated version of a skill generated by AlphaEvolver |
| **Evolution Loop** | Iterative process: mutate → test → compare → select |
| **Graduation** | Agent maturity promotion (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) |

---

**Next Steps:**
- 📖 Read [Auto-Dev User Guide](../GUIDES/AUTO_DEV_USER_GUIDE.md) for practical examples
- 🔧 Set up your first self-evolving agent
- 📊 Monitor reflection pool metrics in your dashboard
- 🎯 Enable Memento-Skills to reduce agent failure rates
