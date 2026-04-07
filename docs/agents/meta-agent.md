# Meta-Agent Routing System

> **Last Updated**: April 7, 2026
> **Phase**: 256-07 (Intent Classification & Fleet Admiralty)
> **Status**: ✅ Production Ready

---

## Overview

The **Meta-Agent** (AtomMetaAgent) is Atom's central orchestrator responsible for:
- **Domain Creation** - Dynamically creating specialist agent templates
- **Intent-Based Routing** - Classifying requests and routing to appropriate handlers
- **Fleet Recruitment** - Assembling multi-agent teams for complex tasks
- **Agent Lifecycle Management** - Overseeing agent creation, deployment, and evolution

---

## Architecture

```
User Request
     ↓
IntentClassifier
     ↓
┌─────────────────────────────────────────┐
│         Route Decision                   │
│  (CHAT / WORKFLOW / TASK)               │
└────┬───────────────┬────────────────────┘
     ↓               ↓                    ↓
  CHAT          WORKFLOW              TASK
     ↓               ↓                    ↓
LLMService      QueenAgent        FleetAdmiral
(Direct)      (Blueprint)      (Multi-Agent)
                                      ↓
                              AtomMetaAgent
                              (Domain Creation
                               & Recruitment)
```

---

## Core Components

### 1. IntentClassifier

**File**: `core/intent_classifier.py`

Classifies incoming requests into one of three categories:

```python
from core.intent_classifier import IntentClassifier

classifier = IntentClassifier()
result = classifier.classify_intent(
    user_message="Research competitors and build Slack integration"
)

# Returns: {
#   "category": "TASK",
#   "confidence": 0.92,
#   "reasoning": "Multi-phase, unstructured, long-horizon"
# }
```

**Categories**:
| Category | Description | Handler | Example |
|----------|-------------|---------|---------|
| **CHAT** | Simple informational queries | LLMService | "Explain agent maturity" |
| **WORKFLOW** | Structured, repeatable processes | QueenAgent | "Execute sales blueprint" |
| **TASK** | Unstructured, complex tasks | FleetAdmiral | "Research competitors + build integration" |

### 2. AtomMetaAgent

**File**: `core/atom_meta_agent.py`

Central orchestrator for domain creation and fleet recruitment.

```python
from core.atom_meta_agent import AtomMetaAgent

atom = AtomMetaAgent(workspace_id="default")

# Create a new domain template
domain = await atom.create_domain(
    domain_name="finance_analyst",
    capabilities=["financial_analysis", "budget_planning"],
    system_prompt="You are a financial analysis specialist..."
)

# Recruit agents for a task
fleet = await atom.recruit_fleet(
    task_description="Analyze Q1 financial reports",
    required_capabilities=["financial_analysis", "data_visualization"],
    max_agents=5
)
```

**Key Methods**:
- `create_domain()` - Create new specialty agent template
- `recruit_fleet()` - Assemble multi-agent team
- `coordinate_fleet()` - Manage agent collaboration
- `spawn_agent()` - Create agent instance from template

### 3. FleetAdmiral

**File**: `core/fleet_admiral.py`

Dynamic multi-agent orchestration for complex tasks.

**See**: [Fleet Admiral Documentation](./fleet-admiral.md)

---

## Domain Creation System

### SpecialtyAgentTemplate

Atom supports 8+ pre-configured domain templates:

| Domain | Capabilities | Use Cases |
|--------|-------------|-----------|
| **finance_analyst** | Financial analysis, budgeting, forecasting | Financial reports, expense tracking |
| **sales_assistant** | Lead qualification, CRM updates, outreach | Sales pipeline management |
| **ops_coordinator** | Supply chain, inventory, logistics | Operations optimization |
| **hr_assistant** | Employee onboarding, benefits, policies | HR workflow automation |
| **procurement_specialist** | Vendor management, purchasing, negotiation | Procurement workflows |
| **knowledge_analyst** | Research, documentation, knowledge management | Knowledge base operations |
| **marketing_analyst** | Campaign analysis, content creation, analytics | Marketing automation |
| **support_agent** | Ticket triage, customer support, escalation | Customer service |

### Creating Custom Domains

```python
from core.atom_meta_agent import AtomMetaAgent

atom = AtomMetaAgent(workspace_id="default")

# Define new domain
custom_domain = await atom.create_domain(
    domain_name="legal_analyst",
    capabilities=["contract_review", "compliance_checking", "legal_research"],
    system_prompt="""You are a legal analysis specialist with expertise in:
    - Contract review and risk assessment
    - Regulatory compliance checking
    - Legal research and case law analysis
    """,
    tools=["contract_parser", "compliance_database", "legal_search_api"],
    maturity_level="INTERN"  # Start at INTERN level
)

# Spawn agent from domain
agent = await atom.spawn_agent(
    domain_name="legal_analyst",
    agent_name="Legal Assistant 1",
    configuration={
        "specialization": "contract_review",
        "jurisdiction": "US"
    }
)
```

---

## Intent-Based Routing

### Routing Logic

```python
# api/agent_routes.py

@router.post("/api/agent/route")
async def route_request(request: AgentRequest):
    classifier = IntentClassifier()
    result = classifier.classify_intent(request.message)

    if result["category"] == "CHAT":
        # Direct LLM response
        return await handle_chat(request)

    elif result["category"] == "WORKFLOW":
        # Blueprint-based execution
        return await handle_workflow(request)

    elif result["category"] == "TASK":
        # Multi-agent orchestration
        return await handle_task(request, meta_agent)
```

### Route Decision Matrix

| Request Characteristics | Route | Handler |
|------------------------|-------|---------|
| Informational question | CHAT | LLMService |
| Single-step action | CHAT | LLMService |
| Blueprint exists | WORKFLOW | QueenAgent |
| Multi-phase task | TASK | FleetAdmiral |
| Requires multiple domains | TASK | FleetAdmiral |
| Long-horizon planning | TASK | FleetAdmiral |

---

## Fleet Recruitment

### Recruitment Intelligence

The `RecruitmentIntelligenceService` analyzes task requirements and recruits appropriate agents:

```python
from core.recruitment_intelligence_service import RecruitmentIntelligenceService

recruiter = RecruitmentIntelligenceService(db)

# Analyze task requirements
analysis = await recruiter.analyze_task(
    task_description="Research competitors, create comparison matrix,
                    build Slack integration, and deploy to production",
    workspace_id="default"
)

# Returns: {
#   "required_capabilities": [
#     "market_research",
#     "competitive_analysis",
#     "api_integration",
#     "devops"
#   ],
#   "complexity": "HIGH",
#   "estimated_duration_hours": 40,
#   "optimal_team_size": 4
# }

# Recruit agents
fleet = await recruiter.recruit_fleet(
    task_analysis=analysis,
    max_agents=5,
    maturity_requirement="SUPERVISED"
)
```

### Fleet Composition

```
Task: "Research competitors and build Slack integration"

Recruited Fleet:
┌────────────────────────────────────────────┐
│  Research Specialist (INTERN)              │
│  - Market research                         │
│  - Competitive analysis                    │
└────────────────────────────────────────────┘
           ↓ (shares findings via Blackboard)
┌────────────────────────────────────────────┐
│  Integration Specialist (SUPERVISED)       │
│  - API development                         │
│  - Slack app configuration                 │
└────────────────────────────────────────────┘
           ↓ (coordinates deployment)
┌────────────────────────────────────────────┐
│  DevOps Specialist (AUTONOMOUS)            │
│  - Deployment automation                   │
│  - Production monitoring                   │
└────────────────────────────────────────────┘
```

---

## Agent Lifecycle Management

### Spawn Process

```python
# Spawn agent from domain template
agent = await atom.spawn_agent(
    domain_name="finance_analyst",
    agent_name="Finance Assistant 1",
    configuration={
        "specialization": "budget_planning",
        "tools": ["excel_export", "chart_generator"],
        "maturity": "INTERN"
    }
)

# Agent is automatically:
# 1. Created in AgentRegistry
# 2. Assigned capabilities from domain
# 3. Configured with domain system prompt
# 4. Made available for routing
```

### Graduation Tracking

Agents spawned from templates follow the standard graduation path:

```
SPAWNED (INTERN)
    ↓ (5 successful operations)
CAPABLE (INTERN++)
    ↓ (20 successful operations)
TRUSTED (SUPERVISED)
    ↓ (50 successful operations)
EXPERT (AUTONOMOUS)
```

**Capability Graduation**:
Individual capabilities progress independently:

```python
# Track capability-specific progress
await atom.record_capability_usage(
    agent_id=agent.id,
    capability="financial_analysis",
    success=True
)

# Automatic progression:
# 5 successes → INTERN level for this capability
# 20 successes → SUPERVISED level for this capability
# 50 successes → AUTONOMOUS level for this capability
```

---

## Configuration

### Environment Variables

```bash
# Meta-Agent Settings
META_AGENT_ENABLED=true
DEFAULT_MATURITY_LEVEL="INTERN"
MAX_FLEET_SIZE=10
FLEET_RECRUITMENT_TIMEOUT=300

# Intent Classification
INTENT_CLASSIFIER_MODEL="gpt-4"
INTENT_CONFIDENCE_THRESHOLD=0.7

# Domain Creation
DOMAIN_TEMPLATES_PATH="core/domain_templates/"
ALLOW_CUSTOM_DOMAINS=true
```

### Domain Template Configuration

```python
# core/domain_templates/finance_analyst.json

{
  "domain_name": "finance_analyst",
  "capabilities": [
    "financial_analysis",
    "budget_planning",
    "forecasting"
  ],
  "system_prompt": "You are a financial analysis specialist...",
  "default_tools": [
    "excel_export",
    "chart_generator",
    "financial_calculator"
  ],
  "maturity_requirements": {
    "minimum": "INTERN",
    "recommended": "SUPERVISED"
  },
  "training_episodes": 25,
  "constitutional_threshold": 0.85
}
```

---

## Performance

### Routing Performance

| Metric | Value |
|--------|-------|
| Intent classification | <100ms |
| Domain creation | <500ms |
| Fleet recruitment | <1s |
| Agent spawn | <200ms |

### Scalability

- **Concurrent fleets**: Up to 10 fleets per workspace
- **Agents per fleet**: 2-10 agents (auto-scaled)
- **Domain templates**: 8+ pre-configured, unlimited custom

---

## Best Practices

### 1. Use Appropriate Routing

```python
# GOOD - Let IntentClassifier decide
result = classifier.classify_intent(request)
handler = ROUTER_MAP[result["category"]]

# BAD - Always use FleetAdmiral
fleet = await fleet_admiral.recruit(...)  # Wasteful for simple tasks
```

### 2. Define Clear Capabilities

```python
# GOOD - Specific, actionable capabilities
capabilities = [
    "contract_review",  # Clear what this means
    "risk_assessment"
]

# BAD - Vague capabilities
capabilities = [
    "legal_stuff",  # Too ambiguous
    "help_with_things"
]
```

### 3. Set Appropriate Maturity Levels

```python
# GOOD - Start low, let agents prove themselves
agent = await atom.spawn_agent(
    domain_name="finance_analyst",
    maturity="INTERN"  # Earn autonomy through performance
)

# BAD - Start at AUTONOMOUS without validation
agent = await atom.spawn_agent(
    domain_name="finance_analyst",
    maturity="AUTONOMOUS"  # Risky, untested
)
```

---

## Troubleshooting

### Issue: Incorrect routing

**Symptom**: Requests routed to wrong handler

**Solution**:
1. Check IntentClassifier confidence score
2. Verify prompt provides clear context
3. Review training examples for classifier

### Issue: Fleet recruitment fails

**Symptom**: No agents recruited for task

**Solution**:
1. Verify required_capabilities exist in system
2. Check agent maturity requirements
3. Review RecruitmentIntelligenceService logs

### Issue: Agent spawn fails

**Symptom**: spawn_agent() raises error

**Solution**:
1. Verify domain template exists
2. Check workspace_id is valid
3. Ensure required tools are configured

---

## Related Documentation

- **[Intent Classification](./unstructured-tasks.md)** - Routing logic
- **[Fleet Admiral](./fleet-admiral.md)** - Multi-agent orchestration
- **[Agent Graduation](./graduation.md)** - Learning and promotion
- **[Agent Governance](./governance.md)** - Maturity levels and permissions

---

## Summary

The Meta-Agent Routing System provides:

✅ **Intelligent Routing** - LLM-powered intent classification
✅ **Dynamic Domains** - 8+ pre-configured specialist templates
✅ **Fleet Recruitment** - Automatic multi-agent team assembly
✅ **Lifecycle Management** - Spawn, track, and graduate agents
✅ **Scalability** - Support for concurrent fleets and custom domains

**Key Principle**: Route requests to the most appropriate handler based on complexity and structure.
