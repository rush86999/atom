# Queen Agent (Queen Hive) - User Guide

**Last Updated:** April 10, 2026
**Reading Time:** 8 minutes
**Difficulty:** Beginner

---

## What is Queen Agent?

**Queen Agent** (also called **Queen Hive**) is Atom's workflow automation system for **structured, repeatable tasks**. Think of it as your reliable automation assistant that excels at executing known business processes with consistent, predictable steps.

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

---

## Getting Started with Queen Agent

### Step 1: Check Your Agent's Maturity Level

Queen Agent requires agents to have sufficient maturity:

| Agent Level | Can Execute Blueprints | Can Create Blueprints |
|-------------|----------------------|----------------------|
| **STUDENT** | ❌ Blocked | ❌ Blocked |
| **INTERN** | ⚠️ Requires Approval | ❌ Blocked |
| **SUPERVISED** | ✅ Yes (Supervised) | ⚠️ Requires Approval |
| **AUTONOMOUS** | ✅ Full Access | ✅ Full Access |

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

**Example Response:**
```json
{
  "success": true,
  "data": {
    "execution_id": "exec_abc123",
    "blueprint": "daily_report_v1",
    "status": "running",
    "started_at": "2026-04-10T10:30:00Z",
    "estimated_completion": "2026-04-10T10:40:00Z"
  }
}
```

### Step 4: Monitor Execution

```bash
# Check execution status
curl http://localhost:8000/api/v1/queen/executions/exec_abc123
```

**Response:**
```json
{
  "success": true,
  "data": {
    "execution_id": "exec_abc123",
    "status": "completed",
    "steps_completed": 5,
    "steps_total": 5,
    "duration_seconds": 542,
    "results": {
      "report_generated": true,
      "emails_sent": 1,
      "errors": []
    }
  }
}
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
    },
    {
      "name": "notify_manager",
      "action": "send_notification",
      "parameters": {
        "channel": "hr-notifications",
        "message": "New employee onboarded: {{parameters.employee_email}}"
      }
    },
    {
      "name": "schedule_checkin",
      "action": "create_calendar_event",
      "parameters": {
        "title": "30-Day Check-in",
        "days_from_now": 30
      }
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

### 3. Data Backup

**Blueprint:** `daily_backup_v1`

**What it does:**
- Backs up database to S3
- Validates backup integrity
- Sends confirmation notification
- Cleans up old backups

**Execute:**
```bash
curl -X POST http://localhost:8000/api/v1/queen/execute \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "daily_backup_v1",
    "parameters": {
      "backup_type": "full",
      "retention_days": 30,
      "notify_on_complete": true
    }
  }'
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

### 3. Use Parameters Effectively
Make blueprints reusable with parameters:
```json
{
  "parameters": {
    "department": {"type": "string"},
    "send_notifications": {"type": "boolean", "default": true}
  }
}
```

### 4. Document Your Blueprints
Add clear descriptions:
```json
{
  "name": "monthly_close",
  "description": "Execute monthly financial close process (runs on last business day of month)",
  "estimated_duration_minutes": 240
}
```

### 5. Test Before Production
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

### Cancel Running Execution

```bash
curl -X POST http://localhost:8000/api/v1/queen/executions/{execution_id}/cancel
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

### List Schedules

```bash
curl http://localhost:8000/api/v1/queen/schedules
```

### Delete Schedule

```bash
curl -X DELETE http://localhost:8000/api/v1/queen/schedules/{schedule_id}
```

---

## Next Steps

### Learn More
- **[Agent System Overview](../agents/overview.md)** - Complete agent documentation
- **[Fleet Admiral Guide](fleet-admiral.md)** - Unstructured task orchestration
- **[Agent Graduation](../agents/graduation.md)** - Promote your agent to higher maturity

### Explore Blueprints
- Browse the [Marketplace](../marketplace/) for community-built blueprints
- Share your blueprints with the community

### Get Help
- **Documentation:** [docs.atomagentos.com](https://docs.atomagentos.com)
- **Issues:** [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Community:** [Atom Discord](https://discord.gg/atom)

---

## Quick Reference

### Key Endpoints

| Action | Endpoint | Method |
|--------|----------|--------|
| List Blueprints | `/api/v1/queen/blueprints` | GET |
| Execute Blueprint | `/api/v1/queen/execute` | POST |
| Get Execution Status | `/api/v1/queen/executions/{id}` | GET |
| List Executions | `/api/v1/queen/executions` | GET |
| Cancel Execution | `/api/v1/queen/executions/{id}/cancel` | POST |
| Create Schedule | `/api/v1/queen/schedules` | POST |
| List Schedules | `/api/v1/queen/schedules` | GET |

### Maturity Requirements

| Blueprint Operation | STUDENT | INTERN | SUPERVISED | AUTONOMOUS |
|---------------------|---------|--------|------------|------------|
| Execute Predefined | ❌ | ⚠️ | ✅ | ✅ |
| Create Custom | ❌ | ❌ | ⚠️ | ✅ |
| Schedule Execution | ❌ | ❌ | ⚠️ | ✅ |

---

**Ready to automate your workflows?** Start with the [Quick Start Guide](../getting-started/quick-start.md) or explore [Marketplace Blueprints](../marketplace/).

*Last Updated: April 10, 2026*
