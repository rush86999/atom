# Marketplace Connection Guide (Commercial Service)

**Last Updated:** 2026-04-07

⚠️ **Important:** The Atom marketplace is a **commercial service** operated by atomagentos.com. Marketplace items are proprietary content licensed under the atomagentos.com Terms of Service. See [LICENSE.md](../../LICENSE.md#marketplace-commercial-appendix) for details.

## Overview

The Atom Agent OS marketplace is hosted at `https://atomagentos.com` and provides:

- **🤖 Agents**: Pre-configured AI agents for specific tasks
- **🎓 Domains**: Specialist knowledge domains (Sales, Engineering, Support)
- **🎨 Components**: Reusable canvas workflow components
- **⚡ Skills**: Agent capabilities and integrations
- **🔒 Proprietary Content**: All marketplace items are commercially licensed
- **📈 Real-Time Updates**: Automatic synchronization with the marketplace

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              atomagentos.com (Mothership)                   │
│         Commercial Marketplace - Proprietary Content         │
└─────────────────────────────────────────────────────────────┘
                              ↑
                              │ HTTPS + X-API-Token
                              │
┌─────────────────────────────────────────────────────────────┐
│                atom-upstream (Satellite)                    │
│         Self-Hosted Instance - AGPL v3 Licensed              │
└─────────────────────────────────────────────────────────────┘
```

**License Distinction:**
- **Core Platform**: AGPL v3 (open source) - Agent runtime, cognitive architecture, governance
- **Marketplace Service**: Commercial/Proprietary - Requires atomagentos.com connection and API token

## Quick Start

### 1. Get Your Commercial API Token

1. Visit [https://atomagentos.com](https://atomagentos.com)
2. Sign up or log in to your account
3. Navigate to **Settings → API Tokens**
4. Generate a new marketplace API token
5. Copy the token (format: `at_saas_xxxxx...`)

⚠️ **Required:** The marketplace requires a valid API token from atomagentos.com. Without a token, marketplace features will be unavailable.

### 2. Configure Your Environment

Add the following to your `.env` file:

```bash
# ==============================================================================
# MARKETPLACE CONNECTION (COMMERCIAL SERVICE)
# ==============================================================================

# Marketplace API URL (atomagentos.com commercial mothership)
ATOM_SAAS_API_URL=https://atomagentos.com/api/v1/marketplace

# Your Commercial API Token (required)
ATOM_SAAS_API_TOKEN=at_saas_your_token_here

# Enable/disable marketplace (default: true)
MARKETPLACE_ENABLED=true
```

**Minimum Required:**
- `ATOM_SAAS_API_TOKEN` - Your commercial API token from atomagentos.com

### 3. Restart Your Atom Instance

```bash
# Docker deployment
docker-compose restart

# Native deployment
cd backend
python -m uvicorn main_api_app:app --reload
```

### 4. Verify Connection

```bash
# Test marketplace health
curl http://localhost:8000/api/v1/marketplace/health

# Expected response when connected:
{
  "status": "healthy",
  "marketplace_url": "https://atomagentos.com/api/v1/marketplace",
  "connected": true
}

# Expected response when token missing:
{
  "status": "unavailable",
  "message": "Marketplace unavailable - Configure ATOM_SAAS_API_TOKEN to enable marketplace features"
}
```

## Marketplace Types

### 🤖 Agent Marketplace

Browse and install pre-configured AI agents:

```bash
# List available agents
curl http://localhost:8000/api/v1/marketplace/agents?limit=20

# Search agents by category
curl http://localhost:8000/api/v1/marketplace/agents?category=sales

# Get agent details
curl http://localhost:8000/api/v1/marketplace/agents/{agent_id}

# Install an agent
curl -X POST http://localhost:8000/api/v1/marketplace/agents/{agent_id}/install
```

**Available Agent Categories:**
- Sales (CRM pipelines, lead scoring, outreach)
- Marketing (Campaigns, social posting, analytics)
- Engineering (PR notifications, deployments, incidents)
- Support (Ticket routing, responses, escalation)
- Finance (Invoices, expenses, reporting)

### 🎓 Domain Marketplace

Browse and install specialist knowledge domains:

```bash
# List available domains
curl http://localhost:8000/api/v1/marketplace/domains?limit=20

# Search domains by category
curl http://localhost:8000/api/v1/marketplace/domains?category=finance

# Get domain details
curl http://localhost:8000/api/v1/marketplace/domains/{domain_id}

# Install a domain
curl -X POST http://localhost:8000/api/v1/marketplace/domains/{domain_id}/install
```

**What are Domains?**
Domains provide specialist knowledge and governance templates for specific business areas. When you install a domain, agents can leverage its expertise for tasks in that domain.

**Available Domain Categories:**
- Finance (Financial analysis, reporting, compliance)
- Sales (Sales processes, CRM workflows, lead management)
- Engineering (Development workflows, CI/CD, incident response)
- Support (Customer service, ticket management, escalation)
- HR (Recruiting, onboarding, employee management)
- Marketing (Campaigns, analytics, social media)
- Operations (Logistics, supply chain, inventory)
- Legal (Contracts, compliance, document review)

### 🎨 Canvas Component Marketplace

Browse and install canvas presentation components:

```bash
# List available components
curl http://localhost:8000/api/v1/marketplace/components?limit=20

# Search components by category
curl http://localhost:8000/api/v1/marketplace/components?category=charts

# Get component details
curl http://localhost:8000/api/v1/marketplace/components/{component_id}

# Install a component
curl -X POST http://localhost:8000/api/v1/marketplace/components/{component_id}/install
```

**What are Canvas Components?**
Canvas components are reusable UI elements for agent presentations:
- **Charts**: Line, bar, pie charts for data visualization
- **Forms**: Interactive forms for data collection
- **Tables**: Data tables with sorting and filtering
- **Markdown**: Rich text and documentation
- **Media**: Images, videos, audio players
- **Interactive**: Custom interactive widgets

**Available Component Categories:**
- charts (Line, Bar, Pie, Area, Scatter)
- forms (Input forms, surveys, configurations)
- tables (Data grids, pivot tables)
- markdown (Rich text, documentation)
- media (Images, videos, audio)
- interactive (Custom widgets, calculators)
- layouts (Grid systems, containers)

### ⚡ Skills Marketplace

Browse and install agent skills and integrations:

```bash
# List available skills
curl http://localhost:8000/api/v1/marketplace/skills?limit=20

# Search skills by category
curl http://localhost:8000/api/v1/marketplace/skills?category=integration

# Get skill details
curl http://localhost:8000/api/v1/marketplace/skills/{skill_id}

# Install a skill
curl -X POST http://localhost:8000/api/v1/marketplace/skills/{skill_id}/install
```

**What are Skills?**
Skills are agent capabilities and integrations that extend what agents can do:
- **Integrations**: Connect to external services (Slack, Gmail, Salesforce)
- **Automation**: Pre-built workflow automations
- **Data Processing**: Data transformation and analysis
- **Communication**: Messaging and notification skills

## Configuration Options

### Marketplace Toggle

```bash
# Enable/disable marketplace (default: true)
MARKETPLACE_ENABLED=true
```

When disabled, marketplace features are completely unavailable. This is useful for:
- Air-gapped environments
- Development without marketplace access
- Compliance requirements

### API Timeout

```bash
# Marketplace API timeout in seconds (default: 30)
ATOM_SAAS_TIMEOUT=60
```

Increase for slow networks or large marketplace responses.

### Cache TTL

```bash
# Marketplace cache duration in seconds (default: 300)
ATOM_SAAS_CACHE_TTL=600
```

Longer cache reduces API calls but may show stale data.

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to marketplace

```bash
# Test connectivity to mothership
curl -I https://atomagentos.com/health

# Expected: HTTP 200
```

**Solutions:**
1. Check internet connectivity
2. Verify firewall allows outbound HTTPS to atomagentos.com
3. Confirm DNS resolution: `nslookup atomagentos.com`
4. Verify API token is valid and not expired

### Authentication Errors

**Problem:** 401 Unauthorized or 403 Forbidden

```bash
# Verify API token directly with mothership
curl -H "X-API-Token: $ATOM_SAAS_API_TOKEN" \
  https://atomagentos.com/api/v1/marketplace/health

# Expected: HTTP 200 with healthy status
```

**Solutions:**
1. Regenerate API token in atomagentos.com dashboard
2. Verify token format: `at_saas_xxxxx...` (minimum 20 characters)
3. Check for extra spaces in `.env` file
4. Ensure token has marketplace access permissions

### Marketplace Unavailable

**Problem:** Empty results or "unavailable" message

```bash
# Check if marketplace is enabled
curl http://localhost:8000/api/v1/marketplace/health

# Response will show connection status
```

**Solutions:**
1. Set `MARKETPLACE_ENABLED=true` in `.env`
2. Verify `ATOM_SAAS_API_TOKEN` is set
3. Check application logs for connection errors
4. Verify mothership is operational at https://atomagentos.com

### Installation Failures

**Problem:** Agent/domain/component/skill installation fails

```bash
# Check installation logs
tail -f logs/atom.log | grep -i marketplace

# Look for specific error messages
```

**Common causes:**
1. Insufficient permissions
2. Database connection issues
3. Invalid item ID
4. Network timeout during download

**Solutions:**
1. Verify database is writable
2. Check available disk space
3. Increase `ATOM_SAAS_TIMEOUT` if needed
4. Review error logs for specific failures

## Security Best Practices

### API Token Security

- ✅ Store tokens in environment variables (never in code)
- ✅ Use separate tokens for dev/staging/production
- ✅ Rotate tokens every 90 days
- ✅ Monitor token usage in atomagentos.com dashboard
- ✅ Revoke unused tokens immediately
- ❌ Never commit tokens to git
- ❌ Never share tokens in plaintext
- ❌ Never log tokens in error messages

### Network Security

- ✅ Use HTTPS for all marketplace connections
- ✅ Validate SSL certificates (disable only for local testing)
- ✅ Restrict outbound access to atomagentos.com IPs if possible
- ✅ Monitor marketplace API usage for anomalies
- ✅ Implement rate limiting for marketplace requests

### Data Privacy

⚠️ **Important:** When you install items from the marketplace:
- Installation metadata is sent to atomagentos.com
- Usage analytics may be collected for marketplace improvements
- Your API token provides access to your account data

**Recommendations:**
1. Review marketplace privacy policy at atomagentos.com
2. Only install from trusted marketplace publishers
3. Monitor your marketplace installation history
4. Be aware that marketplace items are proprietary content

### Commercial Terms

⚠️ **License Restrictions:**
- Marketplace items are **proprietary content**
- **Redistribution prohibited**: Items may not be resold or shared outside the platform
- **API Token Required**: Access requires valid atomagentos.com token
- **Service Availability**: Marketplace is provided "as is" with no availability guarantee

**For full legal terms, see:**
- [LICENSE.md - Marketplace Commercial Appendix](../../LICENSE.md#marketplace-commercial-appendix)
- [atomagentos.com Terms of Service](https://atomagentos.com/terms)

## Advanced Usage

### Custom Marketplace Endpoint

For enterprise deployments with custom marketplace endpoints:

```bash
ATOM_SAAS_API_URL=https://custom.marketplace.example.com/api/v1/marketplace
```

⚠️ **Note:** Custom endpoints must implement the atomagentos.com marketplace API specification.

### Graceful Degradation

When marketplace is unavailable, your Atom instance will:
- Continue functioning with locally installed items
- Show helpful error messages for marketplace operations
- Log connection errors for debugging
- Retry failed connections automatically

```python
# Example error response when marketplace unavailable
{
  "agents": [],
  "total": 0,
  "source": "none",
  "message": "Marketplace unavailable - Configure ATOM_SAAS_API_TOKEN to enable marketplace features",
  "documentation_url": "https://docs.atomagentos.com/marketplace/setup"
}
```

### Health Monitoring

Monitor marketplace connection health:

```bash
# Check health status
curl http://localhost:8000/api/v1/marketplace/health

# Response includes connection status, marketplace URL, and any errors
{
  "connected": true,
  "marketplace_url": "https://atomagentos.com/api/v1/marketplace",
  "message": "Connected to marketplace"
}
```

## API Reference

### Agent Marketplace

```bash
# List agents
GET /api/v1/marketplace/agents?limit=20&offset=0&category=sales

# Get agent details
GET /api/v1/marketplace/agents/{agent_id}

# Install agent
POST /api/v1/marketplace/agents/{agent_id}/install
Body: {"tenant_id": "your_tenant_id"}
```

### Domain Marketplace

```bash
# List domains
GET /api/v1/marketplace/domains?limit=20&offset=0&category=finance

# Get domain details
GET /api/v1/marketplace/domains/{domain_id}

# Install domain
POST /api/v1/marketplace/domains/{domain_id}/install
Body: {"tenant_id": "your_tenant_id"}
```

### Component Marketplace

```bash
# List components
GET /api/v1/marketplace/components?limit=20&offset=0&category=charts

# Get component details
GET /api/v1/marketplace/components/{component_id}

# Install component
POST /api/v1/marketplace/components/{component_id}/install
Body: {"canvas_id": "your_canvas_id"}
```

### Skills Marketplace

```bash
# List skills
GET /api/v1/marketplace/skills?limit=20&offset=0&category=integration

# Get skill details
GET /api/v1/marketplace/skills/{skill_id}

# Install skill
POST /api/v1/marketplace/skills/{skill_id}/install
Body: {"agent_id": "your_agent_id"}
```

### Health Check

```bash
# Check marketplace connection
GET /api/v1/marketplace/health
```

## Support

### Documentation

- **Agent Marketplace**: [agents/marketplace.md](../agents/marketplace.md)
- **Domain Guide**: [agents/domains.md](../agents/domains.md)
- **Canvas Components**: [canvas/components.md](../canvas/components.md)
- **Skills Guide**: [marketplace/skills.md](skills.md)

### Community

- **Marketplace**: [https://atomagentos.com/marketplace](https://atomagentos.com/marketplace)
- **Documentation**: [https://docs.atomagentos.com](https://docs.atomagentos.com)
- **GitHub Issues**: [https://github.com/rush86999/atom/issues](https://github.com/rush86999/atom/issues)

### Getting Help

1. Check troubleshooting section above
2. Review [LICENSE.md](../../LICENSE.md) for commercial terms
3. Search existing GitHub issues
4. Contact atomagentos.com support
5. Open new issue with logs and error messages

---

**Version:** 2.0 (Commercial Marketplace)
**Platform:** Atom Open Source (Satellite) + atomagentos.com (Mothership)
**Last Updated:** 2026-04-07
