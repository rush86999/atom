# Queen Agent (Queen Hive) - Workflow Automation System

**Component**: Structured Complex Tasks Orchestration
**File**: `backend/core/agents/queen_agent.py`
**Status**: ✅ Production Ready

## Overview

**Queen Agent** (aka **Queen Hive**) is Atom's orchestrator for **structured complex tasks** that can be broken down into predefined, repeatable workflows. Unlike Fleet Admiral which handles unstructured tasks requiring adaptive planning, Queen Agent excels at executing known business processes with reliable, repeatable steps.

**Key Distinction**:
- **Queen Agent** (Queen Hive) → **Structured Complex Tasks** → **Workflow Automation**
- **Fleet Admiral** → **Unstructured Complex Long-Horizon Tasks** → **Dynamic Fleet Coordination**

## What are Structured Tasks?

### Structured vs Unstructured

| Aspect | Structured Tasks (Queen Agent) | Unstructured Tasks (Fleet Admiral) |
|--------|------------------------------|----------------------------------|
| **AKA** | Queen Hive, Workflow Automation | Fleet Coordination |
| **Steps** | Predefined, linear | Dynamic, adaptive |
| **Planning** | Known upfront | Discovered during execution |
| **Agents** | Single agent or fixed team | Dynamically recruited |
| **Coordination** | Blueprint execution | Fleet Admiral |
| **Examples** | Data entry pipelines, report generation | Research, strategy, creative work |
| **Use Case** | Repeatable business processes | Novel, complex challenges |

### Examples of Structured Tasks

- "Execute the Q3 sales outreach blueprint" (predefined steps)
- "Generate monthly financial reports from Salesforce data" (known template)
- "Onboard new employees with standard provisioning" (repeatable process)
- "Process daily data backup and validation" (automated routine)
- "Execute inventory reconciliation workflow" (structured steps)

## Architecture

### Intent Classification

```
User Request
     ↓
IntentClassifier
     ↓
┌─────────────────────────────────────────┐
│  Is this a structured, repeatable      │
│  business process with known steps?     │
└────────────┬────────────────────────────┘
             ↓
         YES  →  WORKFLOW → QueenAgent
          NO →  TASK → FleetAdmiral
```

### Core Components

1. **Intent Classifier** (`core/intent_classifier.py`)
   - Classifies requests as CHAT, WORKFLOW, or TASK
   - Routes WORKFLOW intents to Queen Agent
   - **Performance**: <100ms classification

2. **Queen Agent** (`core/agents/queen_agent.py`)
   - Executes predefined blueprints and workflows
   - Manages structured task pipelines
   - Ensures reliable, repeatable execution

3. **Blueprint System**
   - Predefined workflow templates
   - Parameterizable steps
   - Validation and error handling

## Blueprint Execution

### Blueprint Structure

```python
{
  "name": "sales_outreach_blueprint",
  "description": "Execute structured sales outreach campaign",
  "steps": [
    {
      "name": "fetch_leads",
      "action": "query_crm",
      "parameters": {
        "source": "hubspot",
        "filters": {"status": "new", "days_ago": 7}
      }
    },
    {
      "name": "enrich_leads",
      "action": "enrich_data",
      "parameters": {
        "provider": "clearbit"
      }
    },
    {
      "name": "personalize_outreach",
      "action": "generate_email",
      "parameters": {
        "template": "sales_outreach_v1"
      }
    },
    {
      "name": "send_emails",
      "action": "send_via_gmail",
      "parameters": {
        "batch_size": 50
      }
    },
    {
      "name": "log_to_crm",
      "action": "update_records",
      "parameters": {
        "source": "hubspot",
        "status": "contacted"
      }
    }
  ]
}
```

### Execution Flow

```python
from core.agents.queen_agent import QueenAgent

queen = QueenAgent()

# Execute blueprint
result = queen.execute_blueprint(
    blueprint_name="sales_outreach_blueprint",
    parameters={
        "days_ago": 7,
        "batch_size": 50,
        "template": "sales_outreach_v1"
    }
)

# Returns:
# {
#     "success": true,
#     "blueprint": "sales_outreach_blueprint",
#     "steps_completed": 5,
#     "steps_total": 5,
#     "execution_time": 45.2,
#     "results": {
#         "leads_processed": 127,
#         "emails_sent": 127,
#         "errors": []
#     }
# }
```

## When to Use Queen Agent

### Ideal Use Cases

✅ **Use Queen Agent when**:
- Task has a known, repeatable structure
- Steps can be predefined in a blueprint
- Process is executed regularly (daily, weekly, monthly)
- Requirements call for consistent, reliable execution
- Business process is well-documented and standardized

### Examples

1. **Data Pipeline Jobs**
   - Daily ETL operations
   - Report generation schedules
   - Data validation workflows

2. **CRM Workflows**
   - Lead qualification and routing
   - Customer onboarding sequences
   - Renewal reminder campaigns

3. **Financial Operations**
   - Invoice processing workflows
   - Expense reconciliation
   - Budget allocation processes

4. **HR Processes**
   - Employee onboarding checklists
   - Performance review workflows
   - Payroll processing

5. **DevOps Tasks**
   - Deployment pipelines
   - Backup and maintenance routines
   - Monitoring and alerting workflows

### When NOT to Use Queen Agent

❌ **Use Fleet Admiral instead when**:
- Task requires research and exploration
- Steps cannot be predetermined
- Task is novel or unique
- Adaptive planning is required
- Multiple specialist agents need coordination

## API Endpoints

### Blueprint Management

```bash
# List available blueprints
GET /api/v1/queen/blueprints

# Execute blueprint
POST /api/v1/queen/execute
{
  "blueprint_name": "sales_outreach",
  "parameters": {
    "days_ago": 7,
    "batch_size": 50
  }
}

# Create custom blueprint
POST /api/v1/queen/blueprints
{
  "name": "custom_workflow",
  "description": "My custom workflow",
  "steps": [...]
}

# Update blueprint
PATCH /api/v1/queen/blueprints/{blueprint_id}
{
  "steps": [...]
}
```

### Execution Monitoring

```bash
# Get execution status
GET /api/v1/queen/executions/{execution_id}

# List recent executions
GET /api/v1/queen/executions?blueprint=sales_outreach&limit=10

# Cancel running execution
POST /api/v1/queen/executions/{execution_id}/cancel
```

## Performance Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Blueprint Loading | <50ms | ~35ms |
| Step Execution | Varies | Blueprint-dependent |
| Error Recovery | <100ms | ~80ms |
| Total Execution | Blueprint-dependent | Typically 1-5 minutes |

## Governance Integration

### Maturity Requirements

| Agent Maturity | Blueprint Execution | Custom Blueprint Creation |
|----------------|---------------------|---------------------------|
| **STUDENT** | ❌ Blocked | ❌ Blocked |
| **INTERN** | ⚠️ Proposal Required | ❌ Blocked |
| **SUPERVISED** | ✅ Supervised | ⚠️ Approval Required |
| **AUTONOMOUS** | ✅ Full | ✅ Full |

### Permission Checks

```python
from core.governance_cache import GovernanceCache

cache = GovernanceCache()

# Check blueprint execution permission
can_execute = cache.check_blueprint_permission(
    agent_id="agent-123",
    blueprint_name="sales_outreach",
    agent_maturity="SUPERVISED"
)

# Returns: True/False
```

## Testing

```bash
# Run Queen Agent tests
pytest backend/tests/test_queen_agent.py -v

# Run blueprint execution tests
pytest backend/tests/test_blueprint_execution.py -v

# Run workflow automation tests
pytest backend/tests/test_workflow_automation.py -v
```

## Best Practices

1. **Blueprint Design**
   - Keep steps focused and single-purpose
   - Include error handling and rollback
   - Parameterize for reusability
   - Document assumptions and dependencies

2. **Error Handling**
   - Define clear error conditions per step
   - Implement retry logic for transient failures
   - Log all failures for debugging
   - Provide meaningful error messages

3. **Performance**
   - Optimize database queries in steps
   - Use async operations where possible
   - Cache frequently accessed data
   - Monitor execution times

4. **Monitoring**
   - Track blueprint execution metrics
   - Alert on failures or performance degradation
   - Log all executions for audit trail
   - Review and optimize regularly

## Troubleshooting

### Common Issues

1. **Blueprint Execution Fails**
   - Verify blueprint syntax and structure
   - Check parameter values and types
   - Review step permissions
   - Check agent maturity level

2. **Step Timeout**
   - Increase timeout for long-running steps
   - Optimize step operations
   - Break into smaller sub-steps

3. **Permission Denied**
   - Verify agent maturity level
   - Check blueprint governance settings
   - Ensure required integrations are configured

## Comparison with Fleet Admiral

| Aspect | Queen Agent | Fleet Admiral |
|--------|-------------|---------------|
| **Task Type** | Structured, repeatable | Unstructured, novel |
| **Planning** | Predefined blueprints | Dynamic discovery |
| **Agents** | Fixed team | Dynamic recruitment |
| **Use Case** | Workflow automation | Complex problem-solving |
| **Execution Time** | Consistent | Variable |
| **Reliability** | High (repeatable) | Variable (adaptive) |
| **Best For** | Business processes | Research and strategy |

## See Also

- **Fleet Admiral**: `docs/FLEET_ADMIRAL.md` - Unstructured task coordination
- **Intent Classification**: `docs/UNSTRUCTURED_COMPLEX_TASKS.md` - CHAT/WORKFLOW/TASK routing
- **Meta Agent**: `docs/agents/meta-agent.md` - Central orchestrator
- **Agent Governance**: `docs/AGENT_GOVERNANCE_LEARNING_INTEGRATION.md` - Maturity and permissions
- **Implementation**: `backend/core/agents/queen_agent.py`
