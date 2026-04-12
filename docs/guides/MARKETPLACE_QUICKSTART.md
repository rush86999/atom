# Atom Marketplace - Quick Start Guide

**Last Updated:** April 10, 2026
**Reading Time:** 5 minutes
**Difficulty:** Beginner

---

## What is the Atom Marketplace?

The Atom Marketplace is your gateway to **thousands of pre-built automation components** created by the Atom community. Instead of building everything from scratch, you can browse, install, and use:

- 🤖 **Agent Templates** - Complete autonomous agents with pre-learned capabilities
- 🛠️ **Skills** - 5,000+ pre-built automation components
- 🎨 **Canvas Components** - Reusable UI elements for presentations
- 📚 **Domains** - Specialist knowledge packages

### Why Use the Marketplace?

✅ **Save Time** - Install pre-built solutions in seconds
✅ **Learn from Experts** - See how others solve similar problems
✅ **Stay Updated** - Get automatic updates from community publishers
✅ **Quality Assured** - Community ratings and reviews guide your choices

---

## Prerequisites

Before connecting to the marketplace, ensure you have:

1. ✅ **Atom Instance Running** - Your Atom instance is installed and running
2. ✅ **Marketplace Account** - Account at [atomagentos.com](https://atomagentos.com)
3. ✅ **API Token** - Generated from your marketplace account

---

## Quick Start (5 Minutes)

### Step 1: Get Your API Token

1. Visit [https://atomagentos.com](https://atomagentos.com)
2. Sign up or log in to your account
3. Navigate to **Settings → API Tokens**
4. Click **"Generate New Token"**
5. Copy your token (format: `at_saas_xxxxx`)

⚠️ **Security Tip:** Treat your API token like a password. Never share it publicly.

### Step 2: Configure Your Atom Instance

Add the following to your `.env` file:

```bash
# Marketplace Connection
MARKETPLACE_API_URL=https://atomagentos.com
MARKETPLACE_API_TOKEN=at_saas_your_token_here
MARKETPLACE_SYNC_ENABLED=true
```

**For Personal Edition (Docker):**
```bash
# Edit docker-compose-personal.yml
environment:
  - MARKETPLACE_API_URL=https://atomagentos.com
  - MARKETPLACE_API_TOKEN=at_saas_your_token_here
  - MARKETPLACE_SYNC_ENABLED=true
```

### Step 3: Restart Atom

```bash
# Personal Edition (Docker)
docker-compose -f docker-compose-personal.yml restart

# Native Installation
atom restart
# or
systemctl restart atom  # Linux
brew services restart atom  # macOS
```

### Step 4: Verify Connection

```bash
# Check sync status
curl http://localhost:8000/api/admin/sync/status
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "marketplace_connected": true,
    "last_sync": "2026-04-10T10:30:00Z",
    "next_sync": "2026-04-10T10:45:00Z"
  }
}
```

✅ **Connected!** You're now ready to browse and install marketplace resources.

---

## Browse and Install Skills

### List Available Skills

```bash
# Get all skills (paginated)
curl http://localhost:8000/api/marketplace/skills?limit=20

# Search by category
curl http://localhost:8000/api/marketplace/skills?category=data

# Search by query
curl http://localhost:8000/api/marketplace/skills?q=slack
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "skill_slack_notification_v1",
      "name": "Slack Notification",
      "description": "Send notifications to Slack channels",
      "category": "integration",
      "version": "1.2.0",
      "rating": 4.8,
      "install_count": 1250,
      "publisher": "atom-official",
      "maturity_required": "INTERN"
    }
  ]
}
```

### Install a Skill

```bash
curl -X POST http://localhost:8000/api/marketplace/skills/install \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "skill_slack_notification_v1"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "skill_id": "skill_slack_notification_v1",
    "status": "installed",
    "version": "1.2.0",
    "installed_at": "2026-04-10T10:35:00Z"
  }
}
```

### Use an Installed Skill

Once installed, your agents can use the skill immediately:

```python
# In your agent code or via API
from core.skill_adapter import SkillAdapter

skill = SkillAdapter()
result = skill.execute_skill(
    skill_name="slack_notification",
    parameters={
        "channel": "#notifications",
        "message": "Task completed successfully!"
    }
)
```

---

## Browse and Install Agents

### List Available Agents

```bash
curl http://localhost:8000/api/marketplace/agents?limit=20
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "agent_finance_analyst_v2",
      "name": "Finance Analyst Agent",
      "description": "Complete financial analysis and reporting agent",
      "domain": "finance",
      "version": "2.0.0",
      "rating": 4.9,
      "install_count": 856,
      "starting_maturity": "INTERN",
      "capabilities": [
        "financial_analysis",
        "report_generation",
        "forecasting",
        "budget_tracking"
      ]
    }
  ]
}
```

### Install an Agent Template

```bash
curl -X POST http://localhost:8000/api/marketplace/agents/install \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_finance_analyst_v2",
    "agent_name": "My Finance Agent"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "agent_id": "agent_finance_analyst_v2",
    "local_agent_id": "agent_local_abc123",
    "name": "My Finance Agent",
    "maturity_level": "INTERN",
    "created_at": "2026-04-10T10:40:00Z"
  }
}
```

---

## Browse and Install Canvas Components

### List Available Components

```bash
curl http://localhost:8000/api/marketplace/canvas-components?limit=20
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "component_sales_dashboard_v1",
      "name": "Sales Dashboard",
      "type": "dashboard",
      "description": "Interactive sales performance dashboard",
      "version": "1.0.0",
      "rating": 4.7,
      "install_count": 423
    }
  ]
}
```

### Install a Component

```bash
curl -X POST http://localhost:8000/api/marketplace/canvas-components/install \
  -H "Content-Type: application/json" \
  -d '{
    "component_id": "component_sales_dashboard_v1"
  }'
```

---

## Browse and Install Domains

### List Available Domains

```bash
curl http://localhost:8000/api/marketplace/domains?limit=20
```

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "domain_healthcare_compliance",
      "name": "Healthcare Compliance",
      "description": "HIPAA compliance knowledge and workflows",
      "version": "1.5.0",
      "rating": 5.0,
      "install_count": 312
    }
  ]
}
```

### Install a Domain

```bash
curl -X POST http://localhost:8000/api/marketplace/domains/install \
  -H "Content-Type: application/json" \
  -d '{
    "domain_id": "domain_healthcare_compliance"
  }'
```

---

## Rate and Review

After using a marketplace resource, you can rate it to help others:

```bash
curl -X POST http://localhost:8000/api/marketplace/ratings \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "skill",
    "resource_id": "skill_slack_notification_v1",
    "rating": 5,
    "review": "Works perfectly! Easy to configure."
  }'
```

---

## Sync Settings

Configure how often Atom syncs with the marketplace:

```bash
# .env file
MARKETPLACE_SYNC_INTERVAL_MINUTES=15  # Default: 15 minutes
MARKETPLACE_RATING_SYNC_INTERVAL_MINUTES=30  # Default: 30 minutes
```

**Manual Sync:**
```bash
curl -X POST http://localhost:8000/api/admin/sync/trigger
```

---

## Privacy and Analytics

### Opt-In Analytics

By default, analytics are **disabled**. Enable them to help improve the marketplace:

```bash
# .env file
ANALYTICS_ENABLED=true
INSTANCE_NAME=My-Atom-Instance  # Optional friendly name
```

**What We Collect:**
- ✅ Aggregate metrics (execution counts, success rates)
- ✅ Performance data (load times, error rates)
- ❌ **No individual user data**
- ❌ **No message contents or task data**

**All data is anonymized and aggregated.**

---

## Troubleshooting

### Issue: "Connection Refused"

**Solution:**
1. Check your internet connection
2. Verify `MARKETPLACE_API_URL` is correct
3. Check if atomagentos.com is accessible:
   ```bash
   curl -I https://atomagentos.com
   ```

### Issue: "Invalid API Token"

**Solution:**
1. Regenerate your token at atomagentos.com
2. Update your `.env` file with the new token
3. Restart Atom:
   ```bash
   docker-compose -f docker-compose-personal.yml restart
   ```

### Issue: "Skills Not Syncing"

**Solution:**
1. Check sync status:
   ```bash
   curl http://localhost:8000/api/admin/sync/status
   ```
2. Verify `MARKETPLACE_SYNC_ENABLED=true`
3. Check logs for sync errors:
   ```bash
   docker-compose -f docker-compose-personal.yml logs -f atom
   ```

### Issue: "Installation Failed"

**Solution:**
1. Check agent maturity level (some skills require INTERN+)
2. Verify sufficient disk space
3. Check logs for specific error messages

---

## Advanced Configuration

### Conflict Resolution Strategy

Configure how sync conflicts are resolved:

```bash
# .env file
MARKETPLACE_SYNC_CONFLICT_STRATEGY=local_wins  # Options: local_wins, remote_wins, latest_wins, manual
```

### Federation (Optional)

Enable cross-instance agent sharing:

```bash
# .env file
FEDERATION_ENABLED=true
FEDERATION_API_KEY=sk-federation-shared-key
```

⚠️ **Note:** Federation requires all instances to use the same federation API key.

### Debug Mode

Enable detailed marketplace logs:

```bash
# .env file
LOG_LEVEL=DEBUG
MARKETPLACE_DEBUG=true
```

---

## Best Practices

### 1. Review Before Installing

Always check:
- ✅ Rating and reviews (4.0+ recommended)
- ✅ Install count (popular = tested)
- ✅ Last updated date
- ✅ Publisher reputation

### 2. Test in Development

Install and test skills in development first:
```bash
# Install with test mode
curl -X POST http://localhost:8000/api/marketplace/skills/install \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "skill_example",
    "test_mode": true
  }'
```

### 3. Keep Skills Updated

Enable automatic updates or update manually:
```bash
# Check for updates
curl http://localhost:8000/api/marketplace/skills/updates

# Update a skill
curl -X POST http://localhost:8000/api/marketplace/skills/update \
  -H "Content-Type: application/json" \
  -d '{"skill_id": "skill_example"}'
```

### 4. Monitor Performance

Track installed skill performance:
```bash
curl http://localhost:8000/api/marketplace/skills/installed?include_stats=true
```

---

## Next Steps

### Explore the Marketplace
- **[Marketplace Hub](../marketplace/)** - Complete marketplace documentation
- **[Skill Marketplace](../marketplace/skills.md)** - Skills deep dive
- **[Agent Marketplace](../agents/marketplace.md)** - Agent templates

### Create and Share
- **[Publish Your Skills](../marketplace/skills.md#publishing)** - Share with the community
- **[Publish Your Agents](../agents/marketplace.md#publishing)** - Monetize your agents

### Get Help
- **Documentation:** [docs.atomagentos.com](https://docs.atomagentos.com)
- **Support:** [support@atomagentos.com](mailto:support@atomagentos.com)
- **Issues:** [GitHub Issues](https://github.com/rush86999/atom/issues)

---

## Quick Reference

### Key Endpoints

| Action | Endpoint | Method |
|--------|----------|--------|
| Sync Status | `/api/admin/sync/status` | GET |
| Manual Sync | `/api/admin/sync/trigger` | POST |
| List Skills | `/api/marketplace/skills` | GET |
| Install Skill | `/api/marketplace/skills/install` | POST |
| List Agents | `/api/marketplace/agents` | GET |
| Install Agent | `/api/marketplace/agents/install` | POST |
| List Components | `/api/marketplace/canvas-components` | GET |
| Install Component | `/api/marketplace/canvas-components/install` | POST |
| List Domains | `/api/marketplace/domains` | GET |
| Install Domain | `/api/marketplace/domains/install` | POST |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MARKETPLACE_API_URL` | Yes | - | Marketplace URL |
| `MARKETPLACE_API_TOKEN` | Yes | - | Your API token |
| `MARKETPLACE_SYNC_ENABLED` | No | `false` | Enable sync |
| `MARKETPLACE_SYNC_INTERVAL_MINUTES` | No | `15` | Sync frequency |
| `ANALYTICS_ENABLED` | No | `false` | Enable analytics |
| `INSTANCE_NAME` | No | `unnamed` | Instance name |

---

**Ready to explore?** Visit the [Marketplace](https://atomagentos.com) or check the [complete marketplace guide](../marketplace/).

*Last Updated: April 10, 2026*
