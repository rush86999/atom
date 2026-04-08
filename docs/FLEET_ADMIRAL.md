# Fleet Admiral - Multi-Agent Fleet Coordination

**Component**: Unstructured Complex Tasks System
**Files**: `backend/core/fleet_admiral.py`, `backend/core/atom_meta_agent.py`
**Status**: ✅ Production Ready

## Overview

Fleet Admiral is a dynamic agent recruitment and coordination system for handling unstructured, complex tasks that require multiple specialist agents working together. Unlike structured workflows, unstructured tasks cannot be easily broken down into predefined steps and require adaptive agent selection and coordination.

## Architecture

### Core Components

1. **Intent Classifier** (`core/intent_classifier.py`)
   - Classifies user requests into CHAT, WORKFLOW, or TASK intents
   - Routes to appropriate execution path
   - **Performance**: <100ms classification

2. **Fleet Admiral** (`core/fleet_admiral.py`)
   - Recruits specialist agents dynamically based on task requirements
   - Coordinates multi-agent execution via blackboard pattern
   - Manages agent lifecycle and communication
   - **Performance**: <500ms fleet recruitment

3. **Atom Meta Agent** (`core/atom_meta_agent.py`)
   - Central orchestrator for agent spawning and domain creation
   - Manages SpecialtyAgentTemplate system
   - Tracks agent capabilities and graduation

## Intent Classification

| Intent | Description | Routing | Governance |
|--------|-------------|---------|------------|
| **CHAT** | Simple queries, information requests | LLMService | ❌ Bypasses governance |
| **WORKFLOW** | Structured, repeatable tasks | QueenAgent | ✅ Requires maturity check |
| **TASK** | Unstructured, complex tasks | FleetAdmiral | ✅ Requires maturity check |

## Domain Templates

Fleet Admiral supports 8+ pre-configured domain templates:

| Template | Description | Capabilities |
|----------|-------------|--------------|
| `finance_analyst` | Financial analysis, reporting | Data analysis, forecasting, budgeting |
| `sales_assistant` | Sales support, CRM integration | Lead management, pipeline tracking |
| `ops_coordinator` | Operations management | Workflow optimization, scheduling |
| `hr_assistant` | HR tasks, employee management | Onboarding, benefits, policies |
| `procurement_specialist` | Purchasing, vendor management | RFPs, contracts, negotiations |
| `knowledge_analyst` | Research, documentation | Information synthesis, reporting |
| `marketing_analyst` | Marketing campaigns, analytics | Campaign management, ROI analysis |
| `king_agent` | General-purpose orchestration | Multi-domain coordination |

## Agent Spawning

### Creating Custom Agents

```python
from core.atom_meta_agent import AtomMetaAgent

meta_agent = AtomMetaAgent()

# Spawn a new specialty agent
agent = meta_agent.spawn_agent(
    domain="finance_analyst",
    capabilities=["data_analysis", "forecasting"],
    maturity_level="INTERN",
    training_data={...}
)

# Track capability graduation
agent.graduation_tracker.record_execution(
    capability="data_analysis",
    success=True,
    intervention_required=False
)
```

### Fleet Recruitment

```python
from core.fleet_admiral import FleetAdmiral

fleet = FleetAdmiral()

# Recruit agents for complex task
task = "Analyze Q1 sales data, create forecast, and prepare executive presentation"

recruited_agents = fleet.recruit_agents(
    task_description=task,
    required_capabilities=[
        "data_analysis",
        "financial_modeling",
        "presentation_creation"
    ],
    max_agents=5
)

# Execute with fleet coordination
result = fleet.execute_with_fleet(
    agents=recruited_agents,
    task=task,
    coordination_mode="blackboard"
)
```

## Fleet Coordination Patterns

### 1. Blackboard Pattern
- Shared workspace for agent communication
- Agents read/write to shared state
- Fleet Admiral manages coordination

### 2. Pipeline Pattern
- Sequential agent execution
- Output of one agent feeds into next
- Useful for multi-stage processing

### 3. Parallel Pattern
- Multiple agents work simultaneously
- Results aggregated at end
- Useful for independent subtasks

## Governance Integration

### Maturity-Based Access

| Agent Maturity | Fleet Access | Coordination |
|----------------|--------------|--------------|
| **STUDENT** | ❌ Blocked | N/A |
| **INTERN** | ⚠️ Limited | Proposal required |
| **SUPERVISED** | ✅ Allowed | Real-time supervision |
| **AUTONOMOUS** | ✅ Full | Self-coordinating |

### Permission Checks

```python
from core.governance_cache import GovernanceCache

cache = GovernanceCache()

# Check fleet recruitment permission
can_recruit = cache.check_fleet_permission(
    agent_id="agent-123",
    task_complexity="high",
    agent_maturity="SUPERVISED"
)
```

## Performance Metrics

| Operation | Target | Actual |
|-----------|--------|--------|
| Intent Classification | <100ms | ~80ms |
| Fleet Recruitment | <500ms | ~400ms |
| Agent Spawning | <1s | ~800ms |
| Fleet Coordination | <2s | ~1.5s |
| Blackboard Operations | <50ms | ~30ms |

## API Endpoints

### Intent Classification
```bash
POST /api/v1/agent/classify-intent
{
  "request": "Research competitors and build Slack integration"
}

# Response
{
  "intent": "TASK",
  "confidence": 0.92,
  "required_capabilities": ["research", "integration"],
  "recommended_fleet_size": 3
}
```

### Fleet Operations
```bash
# Recruit fleet
POST /api/v1/fleet/recruit
{
  "task": "Analyze sales data and create marketing strategy",
  "max_agents": 5,
  "coordination_mode": "blackboard"
}

# Execute with fleet
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
# Spawn custom agent
POST /api/v1/agent/spawn
{
  "domain": "finance_analyst",
  "capabilities": ["data_analysis", "forecasting"],
  "maturity_level": "INTERN"
}

# List active agents
GET /api/v1/agent/fleet/active
```

## Usage Examples

### Complex Task Execution

```python
from core.intent_classifier import IntentClassifier
from core.fleet_admiral import FleetAdmiral

# 1. Classify intent
classifier = IntentClassifier()
intent = classifier.classify_intent(
    "Research competitors, analyze market trends, and create marketing strategy"
)

# 2. Route to Fleet Admiral for TASK intent
if intent == "TASK":
    fleet = FleetAdmiral()

    # 3. Recruit specialist agents
    agents = fleet.recruit_agents(
        task_description="...",
        required_capabilities=["research", "analysis", "strategy"],
        max_agents=4
    )

    # 4. Execute with fleet coordination
    result = fleet.execute_with_fleet(
        agents=agents,
        task="...",
        coordination_mode="blackboard"
    )
```

## Testing

```bash
# Run intent classifier tests
pytest backend/tests/test_intent_classifier.py -v

# Run fleet admiral tests
pytest backend/tests/test_fleet_admiral.py -v

# Run meta agent tests
pytest backend/tests/test_atom_meta_agent.py -v
```

## Troubleshooting

### Common Issues

1. **Intent Misclassification**
   - Review training data for IntentClassifier
   - Adjust confidence thresholds
   - Add domain-specific examples

2. **Fleet Recruitment Failures**
   - Check available agent pool
   - Verify capability requirements
   - Review agent maturity levels

3. **Coordination Bottlenecks**
   - Adjust blackboard update frequency
   - Optimize agent communication
   - Consider parallel execution patterns

## See Also

- **Intent Classifier**: `backend/core/intent_classifier.py`
- **Atom Meta Agent**: `backend/core/atom_meta_agent.py`
- **Domain Templates**: `backend/core/business_agents.py`
- **Governance**: `backend/core/agent_governance_service.py`
