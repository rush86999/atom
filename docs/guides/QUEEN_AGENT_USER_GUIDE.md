# Queen Agent (Queen Hive) - User Guide

**Last Updated:** June 18, 2026
**Reading Time:** 10 minutes
**Difficulty:** Beginner

---

## What is Queen Agent?

**Queen Agent** (also called **Queen Hive**) is Atom's workflow automation system for **structured, repeatable tasks**. Think of it as your reliable automation assistant that excels at executing known business processes with consistent, predictable steps.

### 🆕 2026 Enhancement: Orchestration Engine

The Queen Agent now includes **advanced orchestration capabilities** based on enterprise workflow research:

- **Conductor Agent** - Centralized orchestrator with 5 execution strategies
- **Workflow State Machine** - Validated state transitions with rollback support
- **Event Bus** - Event-driven workflow triggering with pub/sub
- **Workflow Templates** - Pre-built enterprise patterns
- **Workflow Composition** - 8 reusable primitives (SEQUENCE, PARALLEL, CHOICE, LOOP, etc.)
- **Workflow Versioning** - Schema evolution with migration plans

### Perfect For:

✅ **Daily Operations**
- Generating and sending daily reports
- Processing data backups
- Running scheduled maintenance tasks
- Executing standard checklists

✅ **Business Processes**
- Employee onboarding workflows
- Invoice processing pipelines
- Lead qualification sequences
- Customer follow-up campaigns

✅ **Data Operations**
- ETL (Extract, Transform, Load) jobs
- Data validation workflows
- Report generation schedules
- Inventory reconciliation

✅ **🆕 Complex Orchestration**
- Multi-step workflows with branching logic
- Parallel execution patterns
- Event-driven automation
- Rollback and recovery

---

## Queen Agent vs. Fleet Admiral: Which One Do I Need?

### Quick Decision Guide

**Use Queen Agent when:**
- ✅ Your task has **known, repeatable steps**
- ✅ You can **define the workflow upfront**
- ✅ You need **consistent, reliable execution**
- ✅ The process is executed regularly (daily, weekly, monthly)

**Use Fleet Admiral when:**
- ✅ Your task requires **research and exploration**
- ✅ Steps are **unknown or will change** during execution
- ✅ You need **adaptive planning** and problem-solving
- ✅ The task is **novel or complex**

### Examples

| Task | Use Queen Agent | Use Fleet Admiral |
|------|----------------|-------------------|
| "Generate monthly sales report" | ✅ Perfect - Known template | ❌ Overkill |
| "Research competitors and build integration" | ❌ Too complex | ✅ Perfect - Requires research |
| "Process daily data backup" | ✅ Perfect - Repeatable | ❌ Overkill |
| "Analyze market trends and create strategy" | ❌ Too dynamic | ✅ Perfect - Needs discovery |
| "Execute employee onboarding checklist" | ✅ Perfect - Standardized | ❌ Overkill |
| "🆕 Multi-step workflow with branches" | ✅ Perfect - Workflow composer | ⚠️ Possible both |

---

## Getting Started with Queen Agent

### Step 1: Check Your Agent's Maturity Level

Queen Agent requires agents to have sufficient maturity:

| Agent Level | Can Execute Blueprints | Can Create Blueprints | Can Use Conductor Agent |
|-------------|----------------------|----------------------|-------------------------|
| **STUDENT** | ❌ Blocked | ❌ Blocked | ❌ Blocked |
| **INTERN** | ⚠️ Requires Approval | ❌ Blocked | ⚠️ Requires Approval |
| **SUPERVISED** | ✅ Yes (Supervised) | ⚠️ Requires Approval | ✅ Yes (Supervised) |
| **AUTONOMOUS** | ✅ Full Access | ✅ Full Access | ✅ Full Access |

**Check your agent's maturity:**
```bash
curl http://localhost:8000/api/v1/agents/{agent_id}/maturity
```

### Step 2: Explore Available Blueprints

```bash
# List all available blueprints
curl http://localhost:8000/api/v1/queen/blueprints
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "sales_outreach_v1",
      "name": "Sales Outreach Blueprint",
      "description": "Execute structured sales outreach campaign",
      "category": "sales",
      "estimated_duration_minutes": 45,
      "maturity_required": "SUPERVISED"
    },
    {
      "id": "daily_report_v1",
      "name": "Daily Report Generator",
      "description": "Generate and email daily business reports",
      "category": "reporting",
      "estimated_duration_minutes": 10,
      "maturity_required": "INTERN"
    }
  ]
}
```

### Step 3: Execute a Blueprint

```bash
# Execute a blueprint with parameters
curl -X POST http://localhost:8000/api/v1/queen/execute \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "daily_report_v1",
    "parameters": {
      "report_type": "sales",
      "recipients": ["manager@company.com"],
      "include_charts": true
    }
  }'
```

---

## 🆕 Enhanced Orchestration (2026)

### Conductor Agent

The Conductor Agent provides advanced execution strategies beyond simple sequential execution:

| Strategy | Description | Use Case |
|-----------|-------------|----------|
| **SEQUENTIAL** | Execute steps one-by-one | Simple workflows |
| **PARALLEL** | Execute independent steps simultaneously | Performance optimization |
| **HYBRID** | Mix of sequential and parallel | Complex workflows |
| **ADAPTIVE** | Adjust strategy based on execution context | Dynamic workflows |
| **ROLLBACK_SAFE** | Atomic execution with automatic rollback | Critical workflows |

**Usage:**
```python
from core.orchestration.conductor_agent import ConductorAgent, ExecutionStrategy

conductor = ConductorAgent()

# Execute with PARALLEL strategy
result = conductor.execute_workflow(
    steps=[
        {"step_id": "fetch_data", "action": "fetch"},
        {"step_id": "process_data", "action": "transform"},
        {"step_id": "save_data", "action": "save"}
    ],
    start_step="fetch_data",
    strategy=ExecutionStrategy.PARALLEL  # Enable parallel execution
)
```

### Workflow State Machine

Validated state transitions ensure reliable workflow execution:

```
CREATED → VALIDATED → QUEUED → RUNNING → COMPLETED
   ↓            ↓          ↓         ↓
CANCELLED   PAUSED    WAITING   FAILED
                           ↓
                      ROLLING_BACK → ROLLED_BACK
```

**Usage:**
```python
from core.orchration.workflow_state_machine import WorkflowStateMachine, WorkflowState

machine = WorkflowStateMachine()

# Initialize state
machine.initialize_state("workflow_123", "exec_456", WorkflowState.CREATED)

# Transition through states
machine.transition("workflow_123", "exec_456", WorkflowState.VALIDATED)
machine.transition("workflow_123", "exec_456", WorkflowState.QUEUED)
machine.transition("workflow_123", "exec_456", WorkflowState.RUNNING)

# Create rollback plan if needed
if error_occurs:
    plan = machine.create_rollback_plan(
        workflow_id="workflow_123",
        execution_id="exec_456",
        compensation_actions=["undo_step_1", "undo_step_2"]
    )
```

### Event Bus

Event-driven workflow triggering:

```python
from core.orchration.event_bus import EventBus, EventType

bus = EventBus()
bus.start()

# Subscribe to workflow events
def handle_workflow_created(event):
    print(f"Workflow created: {event.source}")
    # Trigger downstream process

bus.subscribe(
    subscriber_id="subscriber_1",
    event_types=[EventType.WORKFLOW_CREATED],
    handler=handle_workflow_created
)

# Publish event
bus.publish(
    event_type=EventType.WORKFLOW_CREATED,
    source="my_workflow",
    data={"workflow_id": "wf_123"}
)
```

### Workflow Templates

Pre-built enterprise workflow templates:

```python
from core.orchration.workflow_templates import get_template_library

library = get_template_library()

# Browse templates by category
templates = library.get_templates_by_category(TemplateCategory.AUTOMATION)

# Instantiate a template
template = library.get_template("data_sync_automation")

workflow = template.instantiate({
    "source_system": "postgres",
    "target_system": "s3",
    "sync_mode": "incremental"
})
```

### Workflow Composition

Compose workflows from primitives:

```python
from core.orchration.workflow_composer import WorkflowComposer, CompositionPrimitive

composer = WorkflowComposer()

# Compose workflow from primitives
workflow = composer.compose(
    primitives=[
        (CompositionPrimitive.SEQUENCE, {}),
        (CompositionPrimitive.PARALLEL, {}),
        (CompositionPrimitive.CHOICE, {"condition": "data_size > 1000"})
    ],
    strategy=CompositionStrategy.DEPENDENCY_AWARE
)
```

---

## Creating Custom Blueprints

### Blueprint Structure

A blueprint defines the steps of your workflow:

```json
{
  "name": "employee_onboarding_v1",
  "description": "Complete employee onboarding workflow",
  "category": "hr",
  "estimated_duration_minutes": 120,
  "parameters": {
    "employee_email": {
      "type": "string",
      "required": true,
      "description": "New employee email address"
    },
    "department": {
      "type": "string",
      "required": true,
      "description": "Department assignment"
    },
    "send_welcome_email": {
      "type": "boolean",
      "default": true
    }
  },
  "steps": [
    {
      "name": "create_user_accounts",
      "action": "provision_user",
      "parameters": {
        "systems": ["slack", "github", "google_workspace"]
      }
    },
    {
      "name": "assign_access",
      "action": "grant_permissions",
      "parameters": {
        "department": "{{parameters.department}}"
      }
    },
    {
      "name": "send_welcome",
      "action": "send_email",
      "parameters": {
        "template": "welcome_onboarding",
        "to": "{{parameters.employee_email}}",
        "condition": "{{parameters.send_welcome_email}}"
      }
    }
  ]
}
```

### 🆕 Enhanced Blueprint (2026)

With orchestration primitives:

```json
{
  "name": "employee_onboarding_v2",
  "description": "Complete employee onboarding with parallel tasks",
  "category": "hr",
  "estimated_duration_minutes": 90,
  "execution_strategy": "HYBRID",
  "steps": [
    {
      "name": "provision_accounts",
      "action": "provision_user",
      "execution": "parallel",
      "children": [
        {"name": "slack", "action": "provision_slack"},
        {"name": "github", "action": "provision_github"},
        {"name": "google", "action": "provision_google_workspace"}
      ]
    },
    {
      "name": "assign_access",
      "action": "grant_permissions",
      "depends_on": ["provision_accounts"],
      "rollback": {"action": "revoke_access", "on_failure": true}
    },
    {
      "name": "send_welcome",
      "action": "send_email",
      "condition": "{{parameters.send_welcome_email}}"
    }
  ]
}
```

### Create a Blueprint

```bash
# Create a new blueprint
curl -X POST http://localhost:8000/api/v1/queen/blueprints \
  -H "Content-Type: application/json" \
  -d @my_blueprint.json
```

---

## Common Use Cases

### 1. Daily Sales Report

**Blueprint:** `daily_sales_report_v1`

**What it does:**
- Fetches sales data from your CRM
- Generates charts and visualizations
- Creates a PDF report
- Emails it to stakeholders

**Execute:**
```bash
curl -X POST http://localhost:8000/api/v1/queen/execute \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "daily_sales_report_v1",
    "parameters": {
      "date_range": "yesterday",
      "recipients": ["sales@company.com"],
      "include_forecast": true
    }
  }'
```

### 2. Lead Qualification

**Blueprint:** `lead_qualification_v1`

**What it does:**
- Fetches new leads from web forms
- Enriches lead data with external sources
- Calculates lead score
- Routes to appropriate sales rep
- Logs activities in CRM

**Execute:**
```bash
curl -X POST http://localhost:8000/api/v1/queen/execute \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "lead_qualification_v1",
    "parameters": {
      "source": "website",
      "min_score": 70,
      "auto_assign": true
    }
  }'
```

### 3. 🆕 Data Sync with Rollback

**Blueprint:** `data_sync_rollback_v1`

**What it does:**
- Extracts data from source
- Transforms and validates
- Loads to target
- Validates result
- **Rolls back on failure**

**Execute:**
```python
from core.orchration.conductor_agent import ConductorAgent, ExecutionStrategy

conductor = ConductorAgent()

result = conductor.execute_workflow(
    steps=[
        {"step_id": "extract", "action": "extract_data"},
        {"step_id": "transform", "action": "transform_data"},
        {"step_id": "load", "action": "load_data"}
    ],
    strategy=ExecutionStrategy.ROLLBACK_SAFE  # Enable rollback
)
```

---

## Best Practices

### 1. Keep Steps Focused
Each step should do one thing well:
- ✅ Good: "fetch_leads", "enrich_leads", "route_leads"
- ❌ Bad: "handle_entire_lead_process"

### 2. Include Error Handling
Define what happens when steps fail:
```json
{
  "name": "send_email",
  "on_failure": "continue",
  "retry_attempts": 3,
  "retry_delay_seconds": 60
}
```

### 3. 🆕 Use Appropriate Execution Strategies

Choose the right strategy for your workflow:

- **SEQUENTIAL**: For simple, dependent tasks
- **PARALLEL**: For independent tasks that can run simultaneously
- **HYBRID**: For mixed parallel/sequential workflows
- **ADAPTIVE**: For workflows that need to adapt during execution
- **ROLLBACK_SAFE**: For critical workflows where failure is unacceptable

### 4. Use Parameters Effectively
Make blueprints reusable with parameters:
```json
{
  "parameters": {
    "department": {"type": "string"},
    "send_notifications": {"type": "boolean", "default": true}
  }
}
```

### 5. Document Your Blueprints
Add clear descriptions:
```json
{
  "name": "monthly_close",
  "description": "Execute monthly financial close process (runs on last business day of month)",
  "estimated_duration_minutes": 240
}
```

### 6. 🆕 Test Before Production
Always test blueprints with non-critical data first:
```bash
curl -X POST http://localhost:8000/api/v1/queen/execute \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "my_blueprint",
    "parameters": {"test_mode": true}
  }'
```

---

## Monitoring and Troubleshooting

### Check Execution Status

```bash
# Get specific execution
curl http://localhost:8000/api/v1/queen/executions/{execution_id}

# List recent executions
curl http://localhost:8000/api/v1/queen/executions?limit=10
```

### 🆕 State Machine Monitoring

```bash
# Get current workflow state
curl http://localhost:8000/api/v1/orchestration/workflows/{workflow_id}/state

# Get state transition history
curl http://localhost://localhost:8000/api/v1/orchestration/workflows/{workflow_id}/transitions
```

### Cancel Running Execution

```bash
curl -X POST http://localhost:8000/api/v1/queen/executions/{execution_id}/cancel
```

### 🆕 Pause and Resume

```bash
# Pause a running workflow
curl -X POST http://localhost:8000/api/v1/orchestration/workflows/{workflow_id}/pause

# Resume a paused workflow
curl -X POST http://localhost:8000/api/v1/orchestration/workflows/{workflow_id}/resume
```

### View Execution Logs

```bash
# Get logs for specific execution
curl http://localhost:8000/api/v1/queen/executions/{execution_id}/logs
```

### Common Issues

**Issue:** "Agent maturity insufficient"
- **Solution:** Your agent needs to be promoted. Check graduation requirements.

**Issue:** "Blueprint execution timeout"
- **Solution:** Increase timeout or break blueprint into smaller steps.

**Issue:** "Permission denied"
- **Solution:** Verify agent has required permissions for the actions.

**Issue:** "Step failed with error"
- **Solution:** Check execution logs for detailed error messages.

**🆕 Issue:** "Invalid state transition"
- **Solution:** Check state machine documentation for valid transitions.

**🆕 Issue:** "Workflow rollback required"
- **Solution:** Verify compensation actions are defined.

---

## Scheduling Blueprints

### Schedule via API

```bash
# Create a scheduled execution
curl -X POST http://localhost:8000/api/v1/queen/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "daily_report_v1",
    "schedule": "0 9 * * *",
    "parameters": {
      "recipients": ["team@company.com"]
    },
    "timezone": "America/New_York"
  }'
```

**Cron Format:** `0 9 * * *` = 9:00 AM daily
- Minute (0-59)
- Hour (0-23)
- Day of month (1-31)
- Month (1-12)
- Day of week (0-6, Sunday = 0)

### 🆕 Event-Driven Scheduling

```python
from core.orchration.event_bus import EventBus, EventType

# Create workflow trigger
bus = get_event_bus()

# Trigger on data arrival
bus.create_workflow_trigger(
    workflow_id="data_processing_workflow",
    trigger_event=EventType.DATA_RECEIVED,
    condition="data_type == 'csv'"
)
```

---

## Related Documentation

### Core
- **[Agent System Overview](../agents/overview.md)** - Complete agent documentation
- **Fleet Admiral Guide** - Unstructured task orchestration
- **[Agent Graduation](../agents/graduation.md)** - Promote your agent to higher maturity

### 🆕 Enhanced Features
- **[VALIDATION_METRICS.md](../../backend/docs/VALIDATION_METRICS.md)** - Performance validation
- **[ATOM_ENHANCEMENT_PLAN.md](../../ATOM_ENHANCEMENT_PLAN.md)** - Research-based enhancements
- **[Workflow Orchestration](../workflow_automation/README.md)** - Complete orchestration guide

### Implementation
- **[Conductor Agent](../../backend/core/orchestration/conductor_agent.py)** - Implementation
- **[State Machine](../../backend/core/orchestration/workflow_state_machine.py)** - Implementation
- **[Event Bus](../../backend/core/orchestration/event_bus.py)** - Implementation

---

## Quick Reference

### Key Endpoints (Original)

| Action | Endpoint | Method |
|--------|----------|--------|
| List Blueprints | `/api/v1/queen/blueprints` | GET |
| Execute Blueprint | `/api/v1/queen/execute` | POST |
| Get Execution Status | `/api/v1/queen/executions/{id}` | GET |
| List Executions | `/api/v1/queen/executions` | GET |
| Cancel Execution | `/api/v1/queen/executions/{id}/cancel` | POST |
| Create Schedule | `/api/v1/queen/schedules` | POST |
| List Schedules | `/api/v1/queen/schedules` | GET |

### 🆕 Key Endpoints (Enhanced 2026)

| Action | Endpoint | Method |
|--------|----------|--------|
| List Workflow Templates | `/api/v1/orchestration/templates` | GET |
| Compose Workflow | `/api/v1/orchestration/compose` | POST |
| Get Workflow State | `/api/v1/orchestration/workflows/{id}/state` | GET |
| Pause/Resume Workflow | `/api/v1/orchestration/workflows/{id}/pause` | POST |
| Create Event Trigger | `/api/v1/orchestration/triggers` | POST |
| List State Transitions | `/api/v1/orchestration/workflows/{id}/transitions` | GET |

### Maturity Requirements

| Blueprint Operation | STUDENT | INTERN | SUPERVISED | AUTONOMOUS |
|---------------------|---------|--------|------------|------------|
| Execute Predefined | ❌ | ⚠️ | ✅ | ✅ |
| Create Custom | ❌ | ❌ | ⚠️ | ✅ |
| Schedule Execution | ❌ | ❌ | ⚠️ | ✅ |
| 🆕 Use Conductor Agent | ❌ | ⚠️ | ✅ | ✅ |
| 🆕 Use State Machine | ❌ | ⚠️ | ✅ | ✅ |
| 🆕 Create Event Triggers | ❌ | ❌ | ⚠️ | ✅ |

---

**Ready to automate your workflows?** Start with the [Quick Start Guide](../getting_started/quick-start.md) or explore [Marketplace Blueprints](../marketplace/).

*Last Updated: June 18, 2026*
*Version: 2.0 (Enhanced Orchestration)*
*Status: ✅ Foundation Stable | ✅ Enhanced Features Complete (92 tests passing)*
