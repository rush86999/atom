# Fleet Admiral - Multi-Agent Orchestration

> **Last Updated**: April 5, 2026
> **Phase**: 256-07 (Intent Classification & Fleet Admiralty)
> **Status**: ✅ Production Ready

---

## Overview

**FleetAdmiral** is Atom's dynamic multi-agent orchestration system for unstructured complex tasks. It intelligently recruits, coordinates, and manages teams of specialist agents to accomplish long-horizon objectives that require multiple domains of expertise.

### Key Capabilities

- **Dynamic Agent Recruitment** - Assembles specialist teams on-demand
- **Blackboard Coordination** - Shared context via DelegationChain
- **Intelligent Task Analysis** - LLM-powered decomposition
- **Performance Optimization** - FleetOptimizationService tuning
- **Governance Integration** - Maturity-based access control

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FleetAdmiral                          │
│  (Dynamic Agent Recruitment & Orchestration)             │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────────────┐  ┌──────────────────────────────┐
│ AgentFleetService│  │ RecruitmentIntelligenceService│
│ (Delegation Chain│  │ (Specialist Matching)         │
│  Management)     │  │                              │
└─────────────────┘  └──────────────────────────────┘
    │                 │
    ▼                 ▼
┌─────────────────┐  ┌──────────────────────────────┐
│ DelegationChain │  │ FleetOptimizationService      │
│ (Blackboard)    │  │ (Performance Tuning)          │
└─────────────────┘  └──────────────────────────────┘
```

### Core Services

| Service | Responsibility |
|---------|----------------|
| **AgentFleetService** | Manages DelegationChain, recruits members, handles blackboard |
| **RecruitmentIntelligenceService** | Matches tasks to specialist agents based on capabilities |
| **FleetOptimizationService** | Optimizes team composition and execution parameters |
| **LLMService** | Provides task analysis and structured output |

---

## Workflow

### 1. Task Analysis

```python
from core.fleet_admiral import FleetAdmiral
from core.llm_service import LLMService

# Initialize
llm = LLMService()
admiral = FleetAdmiral(db, llm)

# Analyze task
analysis = await admiral.analyze_task(
    "Research competitors and build a Slack integration"
)

# Result:
# {
#     "complexity": "high",
#     "required_capabilities": ["market_research", "api_integration", "slack_api"],
#     "estimated_duration": "2-3 hours",
#     "specialist_count": 3,
#     "reasoning": "Requires research, technical integration, and testing"
# }
```

### 2. Fleet Initialization

```python
# Create DelegationChain (Blackboard)
chain = fleet_service.initialize_fleet(
    tenant_id="default",
    root_agent_id="atom_main",
    root_task="Research competitors and build Slack integration",
    root_execution_id="exec_abc123",
    initial_metadata={"goal": "Competitive analysis + Slack integration"}
)

# Chain ID for all subsequent operations
chain_id = chain.id  # e.g., "fleet_xyz789"
```

### 3. Specialist Recruitment

```python
# Define sub-tasks
sub_tasks = [
    {"domain": "research", "task": "Analyze top 5 competitors", "use_optimizer": True},
    {"domain": "engineering", "task": "Build Slack integration", "use_optimizer": True},
    {"domain": "testing", "task": "Test integration endpoints", "use_optimizer": True}
]

# Recruit specialists
for i, sub_task in enumerate(sub_tasks):
    # Get optimization parameters
    optimization = optimizer.get_optimization_parameters(
        tenant_id="default",
        domain=sub_task["domain"],
        task_description=sub_task["task"]
    )

    # Get specialist agent
    specialist = get_specialized_agent(sub_task["domain"], workspace_id)

    # Create link in delegation chain
    link = fleet_service.recruit_member(
        chain_id=chain_id,
        parent_agent_id="atom_main",
        child_agent_id=specialist.id,
        task_description=sub_task["task"],
        context_json={"fleet_goal": "Competitive analysis + Slack integration"},
        link_order=i,
        optimization_metadata=optimization
    )
```

### 4. Blackboard Coordination

All specialists share a **global blackboard** via the DelegationChain:

```python
# Blackboard state
blackboard = {
    "chain_id": "fleet_xyz789",
    "root_task": "Research competitors and build Slack integration",
    "status": "in_progress",
    "members": [
        {
            "agent_id": "research_agent_abc",
            "task": "Analyze top 5 competitors",
            "status": "completed",
            "output": "Identified 5 key competitors with feature matrix"
        },
        {
            "agent_id": "engineering_agent_def",
            "task": "Build Slack integration",
            "status": "in_progress",
            "input_from": ["research_agent_abc"]  # Uses research output
        }
    ],
    "shared_context": {
        "competitors": ["CompA", "CompB", "CompC", "CompD", "CompE"],
        "integration_requirements": {"webhooks": true, "commands": true}
    }
}
```

---

## Domain Specialists

### Built-in Specialists

| Domain | Agent | Capabilities |
|--------|-------|--------------|
| `finance` | Finance Analyst | reconciliation, expense_analysis, budget_tracking |
| `sales` | Sales Assistant | lead_scoring, crm_sync, email_outreach |
| `marketing` | Marketing Analyst | campaign_analysis, audience_insights, content_suggestions |
| `logistics` | Operations Coordinator | inventory_check, order_tracking, vendor_management |
| `hr` | HR Assistant | onboarding, policy_lookup, leave_tracking |
| `purchasing` | Procurement Specialist | b2b_extract_po, b2b_create_draft_order, b2b_push_to_integrations |
| `accounting` | Accounting Agent | transaction_categorization, anomaly_detection, reconciliation |
| `research` | Knowledge Analyst | ingest_knowledge, query_knowledge_graph, web_search |

### Custom Specialists

```python
# Define custom specialist
custom_specialist = {
    "name": "Legal Analyst",
    "domain": "legal",
    "capabilities": ["contract_review", "compliance_check", "risk_assessment"],
    "module_path": "core.business_agents",
    "class_name": "LegalAgent"
}

# Register and spawn
from core.atom_meta_agent import AtomMetaAgent
atom = AtomMetaAgent(workspace_id="default")
agent = await atom.spawn_agent(
    template_name="custom",
    custom_params=custom_specialist,
    persist=True
)
```

---

## API Reference

### recruit_and_execute

Main entry point for fleet-based task execution.

```python
async def recruit_and_execute(
    task: str,
    user_id: str,
    root_agent_id: str = "atom_main"
) -> Dict[str, Any]:
    """
    Recruit fleet and execute task.

    Args:
        task: User's natural language task description
        user_id: User identifier (single-tenant)
        root_agent_id: Root agent requesting fleet

    Returns:
        {
            "chain_id": "fleet_xyz789",
            "specialists_count": 3,
            "status": "task_routed",
            "result": {...}
        }
    """
```

### analyze_task

LLM-powered task analysis for decomposition.

```python
async def analyze_task(
    self,
    task: str
) -> TaskAnalysis:
    """
    Analyze task complexity and requirements.

    Returns:
        TaskAnalysis with:
        - complexity: "low" | "medium" | "high"
        - required_capabilities: List[str]
        - estimated_duration: "minutes" | "hours" | "days"
        - specialist_count: 1-10
        - reasoning: str
    """
```

### initialize_fleet

Create the delegation chain (blackboard).

```python
def initialize_fleet(
    tenant_id: str,
    root_agent_id: str,
    root_task: str,
    root_execution_id: str,
    initial_metadata: Dict[str, Any] = None
) -> DelegationChain:
    """
    Initialize fleet with delegation chain.

    Returns:
        DelegationChain with blackboard state
    """
```

### recruit_member

Add specialist to fleet.

```python
def recruit_member(
    chain_id: str,
    parent_agent_id: str,
    child_agent_id: str,
    task_description: str,
    context_json: Dict[str, Any] = None,
    link_order: int = 0,
    optimization_metadata: Dict[str, Any] = None
) -> ChainLink:
    """
    Recruit specialist to fleet.

    Returns:
        ChainLink connecting parent to child specialist
    """
```

---

## Performance Optimization

### FleetOptimizationService

Automatically optimizes team composition and execution:

```python
from analytics.fleet_optimization_service import FleetOptimizationService

optimizer = FleetOptimizationService(db)

# Get optimization parameters
params = optimizer.get_optimization_parameters(
    tenant_id="default",
    domain="finance",
    task_description="Reconcile Q1 transactions"
)

# Result:
# {
#     "optimization_reason": "High-velocity financial task",
#     "llm_model": "fast",
#     "parallel_execution": true,
#     "cache_enabled": true,
#     "timeout_seconds": 300,
#     "max_retries": 3
# }
```

### Optimization Strategies

| Strategy | Use Case | Configuration |
|----------|----------|---------------|
| **High-Velocity** | Simple, repetitive tasks | Fast LLM, parallel execution, cache enabled |
| **Deep-Reasoning** | Complex analysis | Smart LLM, sequential execution, reflection enabled |
| **Balanced** | General purpose | Standard LLM, mixed execution, default cache |

---

## Monitoring & Observability

### Fleet Metrics

```python
# Get fleet status
chain = fleet_service.get_chain(chain_id="fleet_xyz789")

# Metrics available:
metrics = {
    "chain_id": chain.id,
    "status": chain.status,  # "in_progress" | "completed" | "failed"
    "member_count": len(chain.links),
    "started_at": chain.created_at,
    "completed_at": chain.completed_at,
    "duration_seconds": (chain.completed_at - chain.created_at).total_seconds(),
    "success_rate": sum(1 for l in chain.links if l.status == "completed") / len(chain.links)
}
```

### Logging

```python
# Fleet operations are logged with structured context
logger.info(
    "Fleet recruited",
    extra={
        "chain_id": chain.id,
        "specialist_count": len(sub_tasks),
        "domains": [st["domain"] for st in sub_tasks],
        "optimization_enabled": any(st.get("use_optimizer") for st in sub_tasks)
    }
)
```

---

## Testing

### Unit Tests

```bash
# Fleet Admiral Tests
pytest tests/test_fleet_admiral.py -v

# Fleet Service Tests
pytest tests/test_agent_fleet_service.py -v

# Recruitment Intelligence Tests
pytest tests/test_recruitment_intelligence.py -v
```

### Integration Tests

```bash
# Multi-Agent Coordination
pytest tests/e2e/test_multi_agent_coordination.py -v

# Fleet Optimization
pytest tests/e2e/test_fleet_optimization.py -v

# Blackboard Communication
pytest tests/e2e/test_blackboard_communication.py -v
```

---

## Troubleshooting

### Issue: Fleet recruitment fails

**Symptoms**: `recruit_and_execute` returns error, no specialists recruited

**Solutions**:

1. Check specialist availability:
```python
from core.business_agents import get_specialized_agent
agent = get_specialized_agent("finance", workspace_id)
assert agent is not None, "Specialist not found"
```

2. Verify governance permissions:
```python
from core.agent_governance_service import AgentGovernanceService
gov = AgentGovernanceService(db)
check = gov.can_perform_action("atom_main", "recruit_fleet")
assert check["allowed"], f"Governance blocked: {check['reason']}"
```

3. Check fleet service initialization:
```python
from core.agent_fleet_service import AgentFleetService
fleet_service = AgentFleetService(db)
assert fleet_service is not None, "Fleet service not initialized"
```

### Issue: Blackboard not updating

**Symptoms**: Specialists don't see each other's outputs

**Solutions**:

1. Verify delegation chain status:
```python
chain = fleet_service.get_chain(chain_id)
print(f"Chain status: {chain.status}")
print(f"Members: {len(chain.links)}")
```

2. Check link status:
```python
for link in chain.links:
    print(f"{link.child_agent_id}: {link.status} - {link.task_description}")
```

3. Enable debug logging:
```python
import logging
logging.getLogger("core.agent_fleet_service").setLevel(logging.DEBUG)
```

### Issue: Performance degradation

**Symptoms**: Fleet execution takes >10s for simple tasks

**Solutions**:

1. Check optimization parameters:
```python
params = optimizer.get_optimization_parameters(...)
print(f"LLM Model: {params['llm_model']}")
print(f"Parallel: {params['parallel_execution']}")
```

2. Enable caching:
```python
params["cache_enabled"] = True
```

3. Reduce specialist count:
```python
# Merge related sub-tasks
sub_tasks = [
    {"domain": "finance", "task": "Reconcile and analyze Q1 transactions"}
]
```

---

## See Also

- **Unstructured Complex Tasks**: `docs/UNSTRUCTURED_COMPLEX_TASKS.md`
- **Intent Classification**: `core/intent_classifier.py`
- **Meta Agent**: `core/atom_meta_agent.py`
- **Business Agents**: `core/business_agents.py`
- **Fleet Service**: `core/agent_fleet_service.py`
- **Recruitment Intelligence**: `core/recruitment_intelligence_service.py`
- **Fleet Optimization**: `analytics/fleet_optimization_service.py`
- **Governance**: `docs/AGENT_GOVERNANCE.md`

---

**Summary**: FleetAdmiral provides intelligent multi-agent orchestration for unstructured complex tasks. With dynamic recruitment, blackboard coordination, and performance optimization, it enables Atom to tackle long-horizon objectives that require multiple specialist agents working together.
