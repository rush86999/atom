# Unstructured Complex Tasks System

**Component**: Intent Classification & Fleet Coordination
**Files**: `backend/core/intent_classifier.py`, `backend/core/fleet_admiral.py`, `backend/core/atom_meta_agent.py`
**Status**: ✅ Production Ready

## Overview

The Unstructured Complex Tasks system handles tasks that cannot be easily broken down into predefined workflows. Unlike structured tasks with clear steps, unstructured tasks require adaptive planning, dynamic agent recruitment, and flexible coordination.

## What are Unstructured Tasks?

### Structured vs Unstructured

| Aspect | Structured Tasks | Unstructured Tasks |
|--------|-----------------|-------------------|
| **Steps** | Predefined, linear | Dynamic, adaptive |
| **Planning** | Known upfront | Discovered during execution |
| **Agents** | Single agent or fixed team | Dynamically recruited |
| **Coordination** | Workflow engine | Fleet Admiral |
| **Examples** | Data entry, report generation | Research, strategy, creative work |

### Examples of Unstructured Tasks

- "Research competitors and create a comprehensive market analysis"
- "Analyze customer feedback and propose product improvements"
- "Investigate system performance issues and recommend optimizations"
- "Design a marketing campaign for a new product launch"
- "Troubleshoot complex technical issue across multiple systems"

## System Architecture

### 1. Intent Classification

The first step is classifying the user's request to determine the appropriate execution path.

```python
from core.intent_classifier import IntentClassifier

classifier = IntentClassifier()

# Classify user request
result = classifier.classify_intent(
    "Research competitors and build Slack integration"
)

# Returns:
# {
#     "intent": "TASK",
#     "confidence": 0.92,
#     "complexity": "high",
#     "required_capabilities": ["research", "integration"],
#     "estimated_duration": "2-4 hours"
# }
```

### Intent Types

| Intent | Description | Routing | Governance |
|--------|-------------|---------|------------|
| **CHAT** | Simple queries, information requests | Direct to LLM | ❌ Bypasses governance |
| **WORKFLOW** | Structured, repeatable processes | QueenAgent | ✅ Maturity check |
| **TASK** | Unstructured, complex tasks | FleetAdmiral | ✅ Maturity check |

### 2. Fleet Recruitment

Once classified as a TASK, Fleet Admiral recruits specialist agents.

```python
from core.fleet_admiral import FleetAdmiral

fleet = FleetAdmiral()

# Analyze task requirements
analysis = fleet.analyze_task(
    task_description="Research competitors and build Slack integration",
    complexity="high"
)

# Recruit appropriate agents
agents = fleet.recruit_agents(
    task_analysis=analysis,
    available_agents=get_all_agents(),
    max_fleet_size=5
)

# Returns:
# [
#     Agent(id="research-1", capabilities=["market_research", "competitive_analysis"]),
#     Agent(id="dev-1", capabilities=["slack_api", "integration"]),
#     Agent(id="writer-1", capabilities=["technical_writing", "documentation"])
# ]
```

### 3. Task Execution

The fleet executes the task using blackboard coordination.

```python
# Execute with fleet coordination
result = fleet.execute_with_fleet(
    agents=agents,
    task="Research competitors and build Slack integration",
    coordination_mode="blackboard",
    timeout=3600  # 1 hour
)

# Returns:
# {
#     "success": true,
#     "result": {...},
#     "agent_contributions": [
#         {"agent_id": "research-1", "contribution": "Competitor analysis report"},
#         {"agent_id": "dev-1", "contribution": "Slack integration code"},
#         {"agent_id": "writer-1", "contribution": "Documentation"}
#     ],
#     "execution_time": 3420  # seconds
# }
```

## Domain Templates

The system includes pre-configured domain templates for common specialist roles:

| Template | Capabilities | Use Cases |
|----------|--------------|-----------|
| `finance_analyst` | Data analysis, forecasting, budgeting | Financial reports, investment analysis |
| `sales_assistant` | Lead management, CRM, pipeline tracking | Sales operations, customer management |
| `ops_coordinator` | Workflow optimization, scheduling | Operations management, process improvement |
| `hr_assistant` | Employee management, benefits, policies | HR tasks, onboarding, compliance |
| `procurement_specialist` | Vendor management, contracts, RFPs | Purchasing, supplier relationships |
| `knowledge_analyst` | Research, documentation, synthesis | Information gathering, knowledge management |
| `marketing_analyst` | Campaigns, analytics, ROI | Marketing strategy, performance tracking |
| `king_agent` | Multi-domain coordination | Complex cross-functional tasks |

## Agent Spawning

### Creating Custom Agents

```python
from core.atom_meta_agent import AtomMetaAgent

meta_agent = AtomMetaAgent()

# Spawn a new specialist agent
agent = meta_agent.spawn_agent(
    domain="custom_analyst",
    capabilities=["data_mining", "visualization", "reporting"],
    maturity_level="INTERN",
    training_data={
        "examples": [...],
        "guidelines": [...]
    }
)

# Agent is now available for fleet recruitment
```

### Capability Graduation

Agents track their capability execution and graduate over time.

```python
# Record execution
agent.graduation_tracker.record_execution(
    capability="data_mining",
    success=True,
    intervention_required=False,
    quality_score=0.9
)

# Check graduation readiness
readiness = agent.graduation_tracker.check_readiness(
    target_maturity="SUPERVISED"
)

# Returns:
# {
#     "ready": True,
#     "current_level": "INTERN",
#     "episodes": 28,
#     "intervention_rate": 0.18,
#     "constitutional_score": 0.87
# }
```

## Fleet Coordination Patterns

### 1. Blackboard Pattern

Agents share a common workspace and read/write information as needed.

```python
result = fleet.execute_with_fleet(
    agents=agents,
    task=task,
    coordination_mode="blackboard"
)

# Blackboard state evolves as agents contribute:
# {
#     "research_findings": {...},
#     "integration_spec": {...},
#     "documentation": {...},
#     "final_report": {...}
# }
```

### 2. Pipeline Pattern

Sequential execution where output of one agent feeds into the next.

```python
result = fleet.execute_with_fleet(
    agents=agents,
    task=task,
    coordination_mode="pipeline"
)

# Agent 1 → Agent 2 → Agent 3
# Research → Development → Documentation
```

### 3. Parallel Pattern

Multiple agents work simultaneously on different aspects.

```python
result = fleet.execute_with_fleet(
    agents=agents,
    task=task,
    coordination_mode="parallel"
)

# All agents work concurrently
# Results aggregated at the end
```

## Governance Integration

### Maturity Requirements

| Agent Maturity | TASK Execution | Fleet Participation |
|----------------|----------------|---------------------|
| **STUDENT** | ❌ Blocked | N/A |
| **INTERN** | ⚠️ With approval | Limited roles |
| **SUPERVISED** | ✅ Allowed | Full participation |
| **AUTONOMOUS** | ✅ Full | Fleet leadership |

### Permission Checks

```python
from core.governance_cache import GovernanceCache

cache = GovernanceCache()

# Check if agent can participate in fleet
can_participate = cache.check_fleet_permission(
    agent_id="agent-123",
    task_complexity="high",
    agent_maturity="SUPERVISED"
)

# Returns: True/False
```

## Performance Metrics

| Operation | Target | Actual |
|-----------|--------|--------|
| Intent Classification | <100ms | ~80ms |
| Task Analysis | <500ms | ~400ms |
| Fleet Recruitment | <1s | ~850ms |
| Blackboard Update | <50ms | ~35ms |
| Fleet Coordination | <2s | ~1.5s per cycle |

## API Endpoints

### Task Classification

```bash
POST /api/v1/agent/classify-intent
Content-Type: application/json

{
  "request": "Research competitors and build Slack integration"
}

# Response
{
  "intent": "TASK",
  "confidence": 0.92,
  "complexity": "high",
  "required_capabilities": ["research", "integration"],
  "recommended_fleet_size": 3
}
```

### Fleet Operations

```bash
# Recruit fleet for task
POST /api/v1/fleet/recruit
{
  "task": "...",
  "max_agents": 5,
  "coordination_mode": "blackboard"
}

# Execute task with fleet
POST /api/v1/fleet/execute
{
  "fleet_id": "fleet-123",
  "task": "...",
  "parameters": {...}
}

# Monitor fleet status
GET /api/v1/fleet/{fleet_id}/status
```

### Agent Spawning

```bash
# Spawn custom specialist
POST /api/v1/agent/spawn
{
  "domain": "custom_analyst",
  "capabilities": ["data_mining", "visualization"],
  "maturity_level": "INTERN"
}

# List active agents
GET /api/v1/agent/fleet/active
```

## Usage Examples

### Complete Task Execution Flow

```python
from core.intent_classifier import IntentClassifier
from core.fleet_admiral import FleetAdmiral

# 1. User submits complex task
user_request = "Research our top 5 competitors, analyze their pricing strategies, and create a recommendation report for our Q2 pricing"

# 2. Classify intent
classifier = IntentClassifier()
result = classifier.classify_intent(user_request)

if result["intent"] == "TASK":
    # 3. Initialize Fleet Admiral
    fleet = FleetAdmiral()

    # 4. Recruit specialist agents
    agents = fleet.recruit_agents(
        task_description=user_request,
        required_capabilities=[
            "competitive_research",
            "pricing_analysis",
            "report_writing"
        ],
        max_fleet_size=4
    )

    # 5. Execute with fleet coordination
    final_result = fleet.execute_with_fleet(
        agents=agents,
        task=user_request,
        coordination_mode="blackboard",
        timeout=7200  # 2 hours
    )

    # 6. Return comprehensive result
    print(f"Task completed: {final_result['success']}")
    print(f"Execution time: {final_result['execution_time']}s")
    print(f"Contributions: {len(final_result['agent_contributions'])}")
```

## Testing

```bash
# Intent classifier tests
pytest backend/tests/test_intent_classifier.py -v

# Fleet admiral tests
pytest backend/tests/test_fleet_admiral.py -v

# Meta agent tests
pytest backend/tests/test_atom_meta_agent.py -v

# Integration tests
pytest backend/tests/test_unstructured_tasks_integration.py -v
```

## Best Practices

1. **Task Definition**
   - Provide clear, detailed task descriptions
   - Specify desired outcomes
   - Include relevant context

2. **Fleet Composition**
   - Balance agent capabilities
   - Consider agent maturity levels
   - Limit fleet size (3-5 agents optimal)

3. **Coordination Mode**
   - Use blackboard for collaborative tasks
   - Use pipeline for sequential work
   - Use parallel for independent subtasks

4. **Monitoring**
   - Track fleet progress
   - Monitor agent contributions
   - Set appropriate timeouts

## Troubleshooting

### Common Issues

1. **Intent Misclassification**
   - Improve task description clarity
   - Add domain-specific examples
   - Adjust confidence thresholds

2. **Fleet Recruitment Failures**
   - Verify available agent pool
   - Check capability requirements
   - Review agent maturity levels

3. **Coordination Bottlenecks**
   - Optimize blackboard update frequency
   - Reduce fleet size if needed
   - Consider alternative coordination modes

4. **Task Timeout**
   - Increase timeout for complex tasks
   - Break task into smaller subtasks
   - Optimize agent performance

## See Also

- **Fleet Admiral**: `docs/FLEET_ADMIRAL.md`
- **Intent Classifier**: `backend/core/intent_classifier.py`
- **Atom Meta Agent**: `backend/core/atom_meta_agent.py`
- **Agent Governance**: `backend/core/agent_governance_service.py`
- **Episodic Memory**: `docs/EPISODIC_MEMORY_IMPLEMENTATION.md`
