# Unstructured Complex Tasks & Domain Creation

> **Last Updated**: April 5, 2026
> **Phase**: 256-07 (Intent Classification & Fleet Admiralty)
> **Status**: ✅ Production Ready

---

## Overview

Atom's **Unstructured Complex Tasks** system enables intelligent routing and execution of user requests through three distinct paths:

1. **CHAT** - Simple conversational queries (no execution needed)
2. **WORKFLOW** - Structured, repeatable business processes (blueprint-based)
3. **TASK** - Long-horizon unstructured tasks requiring dynamic agent recruitment

This system is powered by:
- **IntentClassifier** - LLM-powered request classification
- **FleetAdmiral** - Dynamic multi-agent orchestration
- **SpecialtyAgentTemplate** - Domain-specific agent creation system

---

## Architecture

```
User Request → IntentClassifier → Route Decision
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
                  CHAT          WORKFLOW          TASK
                    ↓               ↓               ↓
              LLMService      QueenAgent      FleetAdmiral
              (Direct         (Blueprint      (Multi-Agent
               Response)      Execution)      Recruitment)
```

### Intent Classification

The `IntentClassifier` analyzes each request and categorizes it:

| Category | Description | Handler | Example |
|----------|-------------|---------|---------|
| **CHAT** | Simple informational queries | LLMService | "Explain how agent maturity works" |
| **WORKFLOW** | Structured, automatable processes | QueenAgent | "Execute the sales outreach blueprint" |
| **TASK** | Unstructured, long-horizon, multi-phase | FleetAdmiral | "Research competitors and build a Slack integration" |

**Classification Features**:
- LLM-powered semantic analysis
- Heuristic fallback for reliability
- Multi-factor classification (structured, long_horizon, requires_agent_recruitment, blueprint_applicable)
- <100ms classification latency

---

## Fleet Admiral System

### Overview

`FleetAdmiral` is the orchestrator for unstructured complex tasks that require multiple specialist agents. It:

1. **Analyzes Task Requirements** - Decomposes request into sub-tasks
2. **Recruits Specialists** - Dynamically assembles domain expert agents
3. **Coordinates Execution** - Manages blackboard-based communication
4. **Optimizes Performance** - Uses RecruitmentIntelligenceService for team selection

### Architecture

```
FleetAdmiral
    ├── AgentFleetService (Delegation Chain Management)
    ├── RecruitmentIntelligenceService (Specialist Matching)
    ├── FleetOptimizationService (Performance Tuning)
    └── LLMService (Task Analysis)
```

### Workflow

1. **Task Analysis** - LLM analyzes complexity and required capabilities
2. **Fleet Initialization** - Creates DelegationChain with blackboard context
3. **Specialist Recruitment** - Recruits domain experts (Finance, Sales, Marketing, etc.)
4. **Blackboard Coordination** - All agents share global context via delegation chain
5. **Result Synthesis** - Combines specialist outputs into final response

### Performance

- **Task Analysis**: <200ms via LLM
- **Fleet Recruitment**: <500ms for 5 specialists
- **Blackboard Updates**: <50ms per synchronization
- **End-to-End**: Typically 2-5s for multi-agent tasks

---

## Domain Creation System

### SpecialtyAgentTemplate

Atom includes **8 built-in domain templates** for instant specialist creation:

| Template | Domain | Capabilities |
|----------|--------|--------------|
| `finance_analyst` | Finance | reconciliation, expense_analysis, budget_tracking, query_financial_metrics |
| `sales_assistant` | Sales | lead_scoring, crm_sync, email_outreach, update_crm_lead/deal |
| `ops_coordinator` | Operations | inventory_check, order_tracking, vendor_management |
| `hr_assistant` | HR | onboarding, policy_lookup, leave_tracking |
| `procurement_specialist` | Operations | b2b_extract_po, b2b_create_draft_order, b2b_push_to_integrations |
| `knowledge_analyst` | Intelligence | ingest_knowledge_from_text/file, query_knowledge_graph, web_search |
| `marketing_analyst` | Marketing | campaign_analysis, audience_insights, content_suggestions |
| `king_agent` | Governance | execute_blueprint, sovereign_governance, delegate_task |

### Spawning Agents

```python
from core.atom_meta_agent import AtomMetaAgent

atom = AtomMetaAgent(workspace_id="default")

# Spawn from template
agent = await atom.spawn_agent(
    template_name="finance_analyst",
    persist=True  # Register in database
)

# Spawn custom agent
custom_agent = await atom.spawn_agent(
    template_name="custom",
    custom_params={
        "name": "Legal Analyst",
        "category": "Legal",
        "description": "Analyzes contracts and compliance",
        "capabilities": ["contract_review", "compliance_check"],
        "default_params": {"jurisdiction": "US"}
    }
)
```

### Capability Graduation

All spawned agents automatically register their capabilities at **STUDENT** maturity level:

```python
# Capabilities are auto-registered on spawn
# GraduationService tracks usage and promotes agents:
# STUDENT → INTERN → SUPERVISED → AUTONOMOUS
```

---

## Usage Examples

### Example 1: Simple Query (CHAT)

```python
from core.intent_classifier import IntentClassifier

classifier = IntentClassifier()
result = await classifier.classify_intent("Explain how agent maturity works")

# Result:
# category: "chat"
# handler: "llm_service"
# requires_execution: False
```

### Example 2: Structured Workflow (WORKFLOW)

```python
result = await classifier.classify_intent("Execute the monthly sales report automation")

# Result:
# category: "workflow"
# handler: "queen_agent"
# is_structured: True
# blueprint_applicable: True
```

### Example 3: Unstructured Complex Task (TASK)

```python
result = await classifier.classify_intent("Research competitors and build a Slack integration")

# Result:
# category: "task"
# handler: "fleet_admiral"
# is_long_horizon: True
# requires_agent_recruitment: True
```

### Example 4: Fleet Recruitment

```python
from core.atom_meta_agent import AtomMetaAgent

atom = AtomMetaAgent(workspace_id="default")
result = await atom.execute(
    request="Research competitors and build a Slack integration",
    trigger_mode=AgentTriggerMode.MANUAL
)

# FleetAdmiral automatically:
# 1. Analyzes task (requires: research_analyst, integration_specialist)
# 2. Recruits specialists (2 agents)
# 3. Coordinates via blackboard
# 4. Returns synthesized result
```

---

## Governance Integration

### Routing with Governance

All routes except CHAT require governance checks:

```python
from core.intent_classifier import IntentCategory

# CHAT bypasses governance
if intent.category == IntentCategory.CHAT:
    return await atom._route_to_chat(request, user_id)

# WORKFLOW/TASK require maturity checks
allowed, reason = await atom._check_governance(
    user_id, agent_id, intent.category.value
)

if not allowed:
    # Auto-takeover: propose CHAT alternative
    return await atom._propose_chat_alternative(
        original_request=request,
        denied_route=intent.category.value,
        denial_reason=reason,
        user_id=user_id
    )
```

### Maturity Requirements

| Route | Minimum Maturity | Notes |
|-------|------------------|-------|
| CHAT | Any | No governance check |
| WORKFLOW | INTERN+ | Requires approval at INTERN level |
| TASK | SUPERVISED+ | Requires supervision below SUPERVISED |

---

## API Endpoints

### Intent Classification

```bash
POST /api/v1/intent/classify
{
  "request": "Research competitors and build Slack integration"
}

# Response:
{
  "category": "task",
  "confidence": 0.92,
  "reasoning": "Multi-phase task requiring research and integration work",
  "is_structured": false,
  "is_long_horizon": true,
  "requires_agent_recruitment": true,
  "blueprint_applicable": false,
  "suggested_handler": "fleet_admiral"
}
```

### Fleet Recruitment

```bash
POST /api/v1/fleet/recruit
{
  "goal": "Research competitors and build Slack integration",
  "sub_tasks": [
    {"domain": "research", "task": "Analyze top 5 competitors"},
    {"domain": "engineering", "task": "Build Slack integration"}
  ]
}

# Response:
{
  "chain_id": "fleet_abc123",
  "specialists_count": 2,
  "status": "recruited",
  "members": [
    {"agent": "Knowledge Analyst", "task": "Analyze top 5 competitors", "status": "recruited"},
    {"agent": "Engineering Specialist", "task": "Build Slack integration", "status": "recruited"}
  ]
}
```

### Agent Spawning

```bash
POST /api/v1/agents/spawn
{
  "template_name": "finance_analyst",
  "persist": true
}

# Response:
{
  "agent_id": "spawned_finance_analyst_abc123",
  "name": "Finance Analyst",
  "category": "Finance",
  "status": "student",
  "capabilities": [
    "reconciliation", "expense_analysis", "budget_tracking",
    "query_financial_metrics", "ingest_knowledge_from_text",
    "query_knowledge_graph", "search_formulas"
  ]
}
```

---

## Performance Metrics

| Operation | Target | Actual |
|-----------|--------|--------|
| Intent Classification | <150ms | ~80ms P50, ~120ms P99 |
| Fleet Recruitment (5 agents) | <1s | ~500ms avg |
| Blackboard Sync | <100ms | ~40ms avg |
| Task Analysis | <300ms | ~180ms avg |
| End-to-End Multi-Agent Task | <10s | ~3-5s typical |

---

## Testing

### Unit Tests

```bash
# Intent Classifier Tests
pytest tests/test_intent_classifier.py -v

# Fleet Admiral Tests
pytest tests/test_fleet_admiral.py -v

# Agent Spawning Tests
pytest tests/test_atom_meta_agent.py -v
```

### Integration Tests

```bash
# End-to-End Fleet Recruitment
pytest tests/e2e/test_fleet_recruitment.py -v

# Multi-Agent Coordination
pytest tests/e2e/test_multi_agent_coordination.py -v
```

---

## Troubleshooting

### Issue: Intent classification defaults to CHAT

**Solution**: Check LLM provider availability and fallback heuristic keywords.

```python
# Check LLM status
from core.llm_service import get_llm_service
llm = get_llm_service()
print(llm.get_status())

# Fallback keywords
chat_keywords = ["explain", "what is", "how does"]
workflow_keywords = ["execute", "run", "automation"]
task_keywords = ["research", "analyze", "build", "create integration"]
```

### Issue: Fleet recruitment fails

**Solution**: Verify specialist agents are registered and governance allows recruitment.

```python
# Check available specialists
from core.business_agents import get_specialized_agent
agent = get_specialized_agent("finance", workspace_id)
print(agent.name if agent else "Not found")

# Check governance
from core.agent_governance_service import AgentGovernanceService
gov = AgentGovernanceService(db)
check = gov.can_perform_action("atom_main", "recruit_fleet")
print(check)
```

### Issue: Spawned agent not visible

**Solution**: Ensure `persist=True` and check database registration.

```python
# Spawn with persistence
agent = await atom.spawn_agent("finance_analyst", persist=True)

# Verify in database
from core.models import AgentRegistry
agents = db.query(AgentRegistry).filter(
    AgentRegistry.name == "Finance Analyst"
).all()
print([a.id for a in agents])
```

---

## See Also

- **Intent Classifier**: `core/intent_classifier.py`
- **Fleet Admiral**: `core/fleet_admiral.py`
- **Meta Agent**: `core/atom_meta_agent.py`
- **Business Agents**: `core/business_agents.py`
- **Fleet Service**: `core/agent_fleet_service.py`
- **Recruitment Intelligence**: `core/recruitment_intelligence_service.py`
- **Governance**: `docs/AGENT_GOVERNANCE.md`
- **Capability Graduation**: `docs/AGENT_GRADUATION_GUIDE.md`

---

**Summary**: Atom's Unstructured Complex Tasks system enables intelligent routing, dynamic agent recruitment, and domain-specific specialist creation. With IntentClassifier, FleetAdmiral, and SpecialtyAgentTemplate, users can delegate complex multi-phase tasks to coordinated teams of AI agents with full governance and maturity tracking.
