# Queen Agent vs Fleet Admiral: Which Orchestrator Do I Need?

**Last Updated:** April 10, 2026
**Reading Time:** 6 minutes
**Difficulty:** Beginner

---

## Overview

Atom has two powerful orchestration systems for automating complex tasks:

| Orchestrator | Best For | Task Type |
|--------------|----------|-----------|
| **Queen Agent** (Queen Hive) | Structured, repeatable workflows | WORKFLOW |
| **Fleet Admiral** | Unstructured, complex problem-solving | TASK |

**Key Question:** Can you define all the steps before starting?

- ✅ **Yes** → Use **Queen Agent**
- ❌ **No** → Use **Fleet Admiral**

---

## Quick Decision Guide

### Use Queen Agent When...

✅ **Your task is:**
- Predefined and repeatable
- Executed regularly (daily, weekly, monthly)
- A standard business process
- Documented with known steps

✅ **Examples:**
- "Generate daily sales report"
- "Execute employee onboarding checklist"
- "Process monthly invoices"
- "Run daily data backup"
- "Send weekly newsletter"

### Use Fleet Admiral When...

✅ **Your task is:**
- Novel or unique
- Requires research and exploration
- Complex with unknown steps
- Adaptive planning needed

✅ **Examples:**
- "Research competitors and build integration"
- "Analyze market trends and create strategy"
- "Investigate system performance issues"
- "Design new feature architecture"
- "Solve complex business problem"

---

## Detailed Comparison

### Architecture

| Aspect | Queen Agent | Fleet Admiral |
|--------|-------------|---------------|
| **Planning** | Predefined blueprints | Dynamic discovery |
| **Steps** | Fixed, linear | Adaptive, branching |
| **Agents** | Single agent or fixed team | Dynamic recruitment |
| **Execution** | Consistent, repeatable | Variable, exploratory |
| **Use Case** | Workflow automation | Complex problem-solving |
| **Best For** | Business processes | Research & strategy |

### Task Characteristics

| Characteristic | Queen Agent | Fleet Admiral |
|----------------|-------------|---------------|
| **Structure** | Known upfront | Discovered during execution |
| **Complexity** | Moderate to high | High to very high |
| **Duration** | Predictable (minutes to hours) | Variable (hours to days) |
| **Reliability** | High (repeatable) | Variable (adaptive) |
| **Human Input** | Initial setup only | Ongoing guidance |

### Maturity Requirements

| Agent Level | Queen Agent | Fleet Admiral |
|-------------|-------------|---------------|
| **STUDENT** | ❌ Blocked | ❌ Blocked |
| **INTERN** | ⚠️ Approval required | ⚠️ Approval required |
| **SUPERVISED** | ✅ Supervised | ✅ Supervised |
| **AUTONOMOUS** | ✅ Full access | ✅ Full access |

---

## Real-World Examples

### Example 1: Daily Sales Report

**Task:** "Generate and email daily sales report"

**Use Queen Agent because:**
- ✅ Steps are known (fetch data → generate charts → email)
- ✅ Executed daily (repeatable)
- ✅ Consistent format
- ✅ Predictable duration (~10 minutes)

**Blueprint:**
```json
{
  "name": "daily_sales_report",
  "steps": [
    {"action": "fetch_sales_data", "source": "crm"},
    {"action": "generate_charts", "type": "line_bar"},
    {"action": "create_pdf", "template": "report_v1"},
    {"action": "send_email", "recipients": ["sales@company.com"]}
  ]
}
```

### Example 2: Competitor Research

**Task:** "Research top 5 competitors and build integration strategy"

**Use Fleet Admiral because:**
- ✅ Unknown competitors (need discovery)
- ✅ Research required (adaptive steps)
- ✅ Strategy development (creative work)
- ✅ Variable duration (hours to days)

**Execution:**
1. Fleet Admiral recruits research specialist agent
2. Discovers competitors through web search
3. Analyzes each competitor's features
4. Identifies integration opportunities
5. Recruits technical specialist for feasibility
6. Develops implementation strategy
7. Presents findings with recommendations

### Example 3: Employee Onboarding

**Task:** "Onboard new employee with standard provisioning"

**Use Queen Agent because:**
- ✅ Standardized process (same steps every time)
- ✅ Predefined checklist
- ✅ Consistent experience
- ✅ Measurable completion

**Blueprint:**
```json
{
  "name": "employee_onboarding",
  "steps": [
    {"action": "create_user_accounts", "systems": ["slack", "github", "email"]},
    {"action": "assign_permissions", "role": "{{department}}"},
    {"action": "send_welcome_email", "template": "welcome"},
    {"action": "schedule_checkin", "days": 30},
    {"action": "notify_manager", "channel": "hr"}
  ]
}
```

### Example 4: System Performance Investigation

**Task:** "Investigate why application is slow and propose solutions"

**Use Fleet Admiral because:**
- ✅ Unknown root cause (needs investigation)
- ✅ Multiple potential issues (database, network, code)
- ✅ Adaptive diagnosis (findings inform next steps)
- ✅ Creative problem-solving (solution design)

**Execution:**
1. Fleet Admiral recruits performance specialist
2. Analyzes metrics and logs
3. Identifies bottlenecks (database queries)
4. Recruits database specialist for optimization
5. Tests proposed solutions
6. Measures performance improvements
7. Documents recommendations

---

## Performance Characteristics

### Queen Agent Performance

| Metric | Target | Use Case |
|--------|--------|----------|
| Blueprint Loading | <50ms | Fast startup |
| Step Execution | Variable | Blueprint-dependent |
| Error Recovery | <100ms | Quick retry |
| Total Execution | Consistent | Predictable timing |
| Typical Duration | 1-5 minutes | Standard workflows |

### Fleet Admiral Performance

| Metric | Target | Use Case |
|--------|--------|----------|
| Intent Classification | <100ms | Quick routing |
| Fleet Recruitment | <500ms | Dynamic assembly |
| Agent Coordination | Variable | Task complexity |
| Total Execution | Variable | Depends on task |
| Typical Duration | 1-24 hours | Complex projects |

---

## API Usage

### Queen Agent API

```bash
# Execute blueprint
curl -X POST http://localhost:8000/api/v1/queen/execute \
  -H "Content-Type: application/json" \
  -d '{
    "blueprint_name": "daily_report_v1",
    "parameters": {
      "report_type": "sales",
      "recipients": ["team@company.com"]
    }
  }'

# List blueprints
curl http://localhost:8000/api/v1/queen/blueprints

# Get execution status
curl http://localhost:8000/api/v1/queen/executions/{execution_id}
```

### Fleet Admiral API

```bash
# Submit complex task
curl -X POST http://localhost:8000/api/v1/fleet/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Research competitors and build integration",
    "context": {
      "domain": "sales",
      "priority": "high",
      "deadline": "2026-04-15"
    }
  }'

# List active fleets
curl http://localhost:8000/api/v1/fleet/active

# Get fleet status
curl http://localhost:8000/api/v1/fleet/{fleet_id}/status
```

---

## Best Practices

### Queen Agent Best Practices

1. **Design Reusable Blueprints**
   - Parameterize for flexibility
   - Keep steps focused and single-purpose
   - Include error handling and rollback

2. **Test Before Production**
   - Validate with sample data
   - Test error scenarios
   - Monitor execution times

3. **Document Your Blueprints**
   - Clear descriptions and examples
   - Parameter documentation
   - Expected outcomes

4. **Schedule Regular Executions**
   - Use cron expressions for recurring tasks
   - Set appropriate timeouts
   - Configure alerting

### Fleet Admiral Best Practices

1. **Provide Clear Context**
   - Define task objectives
   - Specify constraints and requirements
   - Set deadlines and priorities

2. **Monitor Progress**
   - Check fleet status regularly
   - Review agent communications
   - Intervene if needed

3. **Review Results**
   - Validate findings
   - Test recommendations
   - Document outcomes

4. **Learn from Executions**
   - Save successful strategies
   - Create blueprints from repeatable patterns
   - Share insights with team

---

## Hybrid Approach

Sometimes the best solution combines both orchestrators:

### Example: Research + Automation

**Task:** "Research competitors, then create automated weekly competitor analysis report"

**Approach:**
1. **Phase 1: Fleet Admiral** (Research)
   - Research top 5 competitors
   - Identify key metrics to track
   - Design analysis framework

2. **Phase 2: Queen Agent** (Automation)
   - Create blueprint from research findings
   - Schedule weekly execution
   - Automate report generation

**Implementation:**
```bash
# Phase 1: Use Fleet Admiral for research
curl -X POST http://localhost:8000/api/v1/fleet/submit \
  -d '{"task": "Research competitors and design analysis framework"}'

# Phase 2: Create Queen Agent blueprint from research
curl -X POST http://localhost:8000/api/v1/queen/blueprints \
  -d '{"name": "weekly_competitor_analysis", "steps": [...]}'

# Schedule recurring execution
curl -X POST http://localhost:8000/api/v1/queen/schedules \
  -d '{"blueprint": "weekly_competitor_analysis", "schedule": "0 9 * * 1"}'
```

---

## Decision Flowchart

```
Start
  ↓
Can you define all steps upfront?
  ↓
NO → Use Fleet Admiral
     ↓
     Research and explore
     ↓
     Discover solution
     ↓
     Can this become a repeatable process?
       ↓
       YES → Create Queen Agent blueprint
       ↓
       Automate for future use

YES → Use Queen Agent
     ↓
     Create blueprint
     ↓
     Execute reliably
     ↓
     Schedule if recurring
```

---

## Maturity Path

### Start with Queen Agent

If you're new to Atom:
1. Learn Queen Agent blueprints
2. Automate simple workflows
3. Build confidence and experience
4. Promote agents to higher maturity

### Graduate to Fleet Admiral

As your agents mature:
1. Tackle more complex tasks
2. Use Fleet Admiral for research
3. Combine both orchestrators
4. Build hybrid solutions

---

## Next Steps

### Learn More
- **[Queen Agent User Guide](QUEEN_AGENT_USER_GUIDE.md)** - Complete Queen Agent documentation
- **[Fleet Admiral Guide](fleet-admiral.md)** - Fleet Admiral deep dive
- **[Agent System Overview](../agents/overview.md)** - Complete agent documentation

### Explore Examples
- **[Use Cases](../features/use-cases.md)** - Real-world automation examples
- **[Blueprint Library](../marketplace/)** - Community-built blueprints
- **[Fleet Strategies](../agents/fleet-admiral.md)** - Advanced fleet patterns

### Get Help
- **Documentation:** [docs.atomagentos.com](https://docs.atomagentos.com)
- **Issues:** [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Community:** [Atom Discord](https://discord.gg/atom)

---

## Quick Reference

### Decision Matrix

| Task Type | Use Queen Agent | Use Fleet Admiral |
|-----------|----------------|-------------------|
| Daily reports | ✅ | ❌ |
| Data backups | ✅ | ❌ |
| Employee onboarding | ✅ | ❌ |
| Invoice processing | ✅ | ❌ |
| Competitor research | ❌ | ✅ |
| Strategy development | ❌ | ✅ |
| Problem investigation | ❌ | ✅ |
| System optimization | ❌ | ✅ |
| Known workflow | ✅ | ❌ |
| Unknown solution | ❌ | ✅ |

### Key Differences

| Aspect | Queen Agent | Fleet Admiral |
|--------|-------------|---------------|
| **Planning** | Upfront | Adaptive |
| **Steps** | Fixed | Dynamic |
| **Duration** | Predictable | Variable |
| **Reliability** | High | Medium |
| **Best For** | Automation | Discovery |

---

**Still unsure?** Start with Queen Agent for structured tasks, then use Fleet Admiral when you need research and discovery. Both orchestrators can work together for hybrid solutions.

*Last Updated: April 10, 2026*
