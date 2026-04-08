# Domain Marketplace Guide

**Last Updated:** 2026-04-07

Learn how to browse, install, and use specialist domains from the atomagentos.com marketplace.

⚠️ **Commercial Service:** Domains are proprietary content from the atomagentos.com marketplace. Requires valid API token. See [LICENSE.md](../../LICENSE.md#marketplace-commercial-appendix) for details.

## Overview

Specialist domains provide expert knowledge and governance templates for specific business areas. When you install a domain, agents gain specialized expertise and can handle complex tasks in that domain more effectively.

### What Are Domains?

Domains are knowledge packages that include:
- **Specialist Knowledge** - Domain-specific information and best practices
- **Governance Templates** - Pre-configured maturity and permission rules
- **Vocabulary** - Domain-specific terminology and concepts
- **Workflows** - Common domain tasks and processes
- **Integration Patterns** - Preferred tools and services for the domain

### Available Domains

- **💰 Finance** - Financial analysis, reporting, compliance, budgeting
- **💼 Sales** - Sales processes, CRM workflows, lead management
- **🔧 Engineering** - Development workflows, CI/CD, incident response
- **🎧 Support** - Customer service, ticket management, escalation
- **👥 HR** - Recruiting, onboarding, employee management
- **📢 Marketing** - Campaigns, analytics, social media
- **🚚 Operations** - Logistics, supply chain, inventory
- **⚖️ Legal** - Contracts, compliance, document review

## Quick Start

### 1. Browse Available Domains

```bash
# List all domains
curl http://localhost:8000/api/v1/marketplace/domains

# Filter by category
curl http://localhost:8000/api/v1/marketplace/domains?category=finance

# Search by name
curl http://localhost:8000/api/v1/marketplace/domains?query=financial+analysis
```

**Response:**
```json
{
  "domains": [
    {
      "id": "domain_financial_analysis_001",
      "domain_name": "Financial Analysis",
      "description": "Expert financial analysis and reporting domain",
      "category": "finance",
      "version": "1.5.0",
      "author": "atomagentos",
      "rating": 4.9,
      "installs": 850,
      "capabilities": [
        "financial_report_generation",
        "budget_analysis",
        "variance_detection",
        "forecasting"
      ]
    }
  ],
  "total": 1,
  "page": 1
}
```

### 2. Get Domain Details

```bash
# Get full domain details
curl http://localhost:8000/api/v1/marketplace/domains/domain_financial_analysis_001
```

**Response:**
```json
{
  "id": "domain_financial_analysis_001",
  "domain_name": "Financial Analysis",
  "description": "Expert financial analysis and reporting domain",
  "long_description": "Comprehensive financial analysis domain...",

  "category": "finance",
  "version": "1.5.0",
  "author": "atomagentos",
  "license": "Proprietary",

  "capabilities": [
    {
      "name": "financial_report_generation",
      "description": "Generate comprehensive financial reports",
      "maturity_required": "SUPERVISED"
    },
    {
      "name": "budget_analysis",
      "description": "Analyze budgets and detect variances",
      "maturity_required": "INTERN"
    },
    {
      "name": "variance_detection",
      "description": "Detect budget variances and anomalies",
      "maturity_required": "AUTONOMOUS"
    },
    {
      "name": "forecasting",
      "description": "Forecast financial metrics",
      "maturity_required": "SUPERVISED"
    }
  ],

  "integrations": [
    {"service": "quickbooks", "required": false},
    {"service": "xero", "required": false},
    {"service": "stripe", "required": false}
  ],

  "knowledge_base": [
    "GAAP accounting standards",
    "Financial KPIs and metrics",
    "Budgeting best practices",
    "Variance analysis methods"
  ],

  "governance_template": {
    "default_maturity": "INTERN",
    "approval_required": [
      "financial_report_generation",
      "forecasting"
    ],
    "auto_approved": [
      "budget_analysis",
      "variance_detection"
    ]
  },

  "rating": 4.9,
  "rating_count": 85,
  "installs": 850,
  "created_at": "2026-02-15T10:00:00Z"
}
```

### 3. Install a Domain

```bash
# Install domain to your instance
curl -X POST http://localhost:8000/api/v1/marketplace/domains/domain_financial_analysis_001/install \
  -H "Content-Type: application/json" \
  -d '{
    "custom_name": "My Financial Analysis"
  }'
```

**Response:**
```json
{
  "success": true,
  "domain_id": "domain_local_abc123",
  "domain_name": "My Financial Analysis",
  "message": "Domain installed successfully"
}
```

### 4. Use Domain in Agent

After installation, agents can leverage the domain:

```python
from core.agent_service import AgentService

agent_service = AgentService(db)

# Create agent with domain expertise
agent = agent_service.create_agent(
    name="Financial Analyst",
    agent_type="specialist",
    domains=["domain_financial_analysis_001"],  # Use installed domain
    capabilities=["financial_report_generation", "budget_analysis"]
)
```

## Domain Categories

### Finance Domain

**Capabilities:**
- Financial report generation (Balance Sheet, P&L, Cash Flow)
- Budget vs actual analysis
- Variance detection and explanation
- Financial forecasting and projections
- KPI tracking and dashboards

**Integrations:**
- QuickBooks, Xero, FreshBooks
- Stripe, PayPal
- Excel, Google Sheets

**Use Cases:**
- Monthly financial reporting
- Budget planning and analysis
- Expense tracking and categorization
- Financial health assessment

### Sales Domain

**Capabilities:**
- Lead scoring and qualification
- CRM workflow automation
- Sales pipeline management
- Opportunity forecasting
- Commission calculations

**Integrations:**
- Salesforce, HubSpot, Pipedrive
- Gmail, Outlook
- Slack, Microsoft Teams

**Use Cases:**
- Lead prioritization
- Sales pipeline tracking
- Automated follow-ups
- Deal forecasting

### Engineering Domain

**Capabilities:**
- CI/CD pipeline monitoring
- Incident response and escalation
- Code review automation
- Deployment coordination
- Performance monitoring

**Integrations:**
- GitHub, GitLab, Bitbucket
- Jenkins, CircleCI, GitHub Actions
- PagerDuty, Opsgenie
- Slack, Microsoft Teams

**Use Cases:**
- Automated incident triage
- Deployment coordination
- Code review prioritization
- Performance analysis

### Support Domain

**Capabilities:**
- Ticket routing and categorization
- Response drafting
- Escalation management
- Knowledge base search
- Customer sentiment analysis

**Integrations:**
- Zendesk, Freshdesk, Intercom
- Slack, Microsoft Teams
- Confluence, Notion

**Use Cases:**
- Automated ticket routing
- Suggested responses
- Escalation triggers
- Customer satisfaction tracking

### HR Domain

**Capabilities:**
- Recruiting workflow automation
- Onboarding coordination
- Employee inquiries
- Performance review summaries
- Policy explanations

**Integrations:**
- BambooHR, Workday
- Greenhouse, Lever
- Slack, Microsoft Teams

**Use Cases:**
- Candidate screening
- Onboarding task tracking
- HR policy Q&A
- Performance review assistance

### Marketing Domain

**Capabilities:**
- Campaign performance analysis
- Social media posting
- Content calendar management
- A/B test analysis
- Lead attribution

**Integrations:**
- HubSpot, Marketo
- Twitter, LinkedIn, Facebook
- Google Analytics
- Mailchimp, SendGrid

**Use Cases:**
- Campaign reporting
- Social media automation
- Content optimization
- Lead source tracking

### Operations Domain

**Capabilities:**
- Inventory monitoring
- Supply chain tracking
- Logistics coordination
- Demand forecasting
- Supplier management

**Integrations:**
- SAP, Oracle
- Shopify, WooCommerce
- Slack, Microsoft Teams

**Use Cases:**
- Stock level alerts
- Order tracking
- Supplier performance
- Demand planning

### Legal Domain

**Capabilities:**
- Contract review and analysis
- Compliance checking
- Document summarization
- Risk assessment
- Clause extraction

**Integrations:**
- DocuSign, Adobe Sign
- SharePoint, Google Drive
- Slack, Microsoft Teams

**Use Cases:**
- Contract review assistance
- Compliance verification
- Legal research
- Risk analysis

## Domain Architecture

### Domain Structure

```
┌─────────────────────────────────────────────────────────┐
│                  Installed Domain                       │
├─────────────────────────────────────────────────────────┤
│  Knowledge Base                                         │
│  - Domain concepts and terminology                      │
│  - Best practices and patterns                          │
│  - Common workflows                                     │
├─────────────────────────────────────────────────────────┤
│  Capabilities                                           │
│  - Specific skills and tasks                            │
│  - Maturity requirements                                │
│  - Approval rules                                       │
├─────────────────────────────────────────────────────────┤
│  Governance Template                                    │
│  - Default maturity level                               │
│  - Permission rules                                     │
│  - Approval workflows                                   │
├─────────────────────────────────────────────────────────┤
│  Integration Patterns                                   │
│  - Preferred services and tools                         │
│  - API configurations                                   │
│  - Data mappings                                        │
└─────────────────────────────────────────────────────────┘
```

### Agent-Domain Interaction

```python
# Agent with domain expertise
agent = Agent(
    name="Sales Agent",
    domains=["domain_sales_001"],
    maturity="INTERN"
)

# Agent can now:
# 1. Use domain knowledge
agent.query("What's the best way to qualify a lead?")
# → Uses sales domain best practices

# 2. Follow domain workflows
agent.execute("qualify_lead", lead_data)
# → Follows sales qualification process

# 3. Observe domain governance
agent.execute("send_email", customer_email)
# → Requires approval (INTERN maturity)

# 4. Leverage domain integrations
agent.execute("update_crm", opportunity_data)
# → Updates Salesforce using domain integration
```

## Configuration

### Domain Installation Options

```bash
# Install with default name
curl -X POST http://localhost:8000/api/v1/marketplace/domains/{domain_id}/install \
  -H "Content-Type: application/json" \
  -d '{}'

# Install with custom name
curl -X POST http://localhost:8000/api/v1/marketplace/domains/{domain_id}/install \
  -H "Content-Type: application/json" \
  -d '{
    "custom_name": "My Custom Domain"
  }'
```

### Domain Permissions

Domains respect maturity-based governance:

| Maturity | Domain Access | Approval Required |
|----------|--------------|------------------|
| STUDENT | Read-only knowledge | N/A |
| INTERN | Basic capabilities | High-risk tasks |
| SUPERVISED | Most capabilities | Critical tasks |
| AUTONOMOUS | All capabilities | None |

**Example - Finance Domain:**

```json
{
  "governance_template": {
    "default_maturity": "INTERN",
    "capability_permissions": {
      "budget_analysis": {
        "min_maturity": "INTERN",
        "approval_required": false
      },
      "financial_report_generation": {
        "min_maturity": "SUPERVISED",
        "approval_required": true
      },
      "variance_detection": {
        "min_maturity": "AUTONOMOUS",
        "approval_required": false
      }
    }
  }
}
```

## Troubleshooting

### Domain Installation Failed

**Problem:** Installation returns error

**Common causes:**
- Domain already installed
- Invalid domain ID
- Insufficient permissions
- Database connection issues

**Solutions:**
1. Check if domain already exists: `GET /api/domains`
2. Verify domain ID: `GET /api/v1/marketplace/domains/{id}`
3. Check logs: `tail -f logs/atom.log | grep domain`
4. Ensure database is writable

### Agent Can't Use Domain

**Problem:** Agent doesn't have domain expertise

**Solutions:**
1. Verify domain is installed: `GET /api/domains`
2. Check agent configuration includes domain
3. Verify agent has required maturity level
4. Check domain capabilities match agent tasks

### Domain Knowledge Not Working

**Problem:** Agent doesn't use domain knowledge

**Solutions:**
1. Verify domain is loaded: `GET /api/domains/{id}/knowledge`
2. Check agent has domain in configuration
3. Review agent context includes domain
4. Check logs for domain loading errors

## Best Practices

### Domain Selection

✅ **Do:**
- Choose domains matching your business needs
- Check domain ratings and reviews
- Verify domain capabilities cover your use cases
- Test domain with sample tasks first

❌ **Don't:**
- Install unnecessary domains
- Use domains with low ratings
- Ignore domain maturity requirements
- Assume domain expertise replaces training

### Agent-Domain Configuration

✅ **Do:**
- Assign relevant domains to agents
- Match agent maturity to domain requirements
- Test agent capabilities with domain
- Monitor agent performance with domain

❌ **Don't:**
- Assign too many domains to one agent
- Ignore domain governance rules
- Assume domain overrides agent training
- Skip domain testing

### Domain Updates

✅ **Do:**
- Keep domains updated for latest knowledge
- Test domain updates before deploying
- Review domain changelog
- Monitor agent performance after updates

❌ **Don't:**
- Update domains without testing
- Ignore domain version compatibility
- Skip domain changelog review
- Assume updates are always improvements

## API Reference

### Browse Domains

```bash
GET /api/v1/marketplace/domains

Query Parameters:
- limit: number of results (default: 20, max: 100)
- offset: pagination offset (default: 0)
- category: filter by category
- query: search by name/description
- sort: sort order (name, rating, installs, created)
```

### Get Domain Details

```bash
GET /api/v1/marketplace/domains/{domain_id}

Returns:
- Full domain metadata
- Capabilities and maturity requirements
- Integration patterns
- Governance template
- Knowledge base overview
```

### Install Domain

```bash
POST /api/v1/marketplace/domains/{domain_id}/install

Body:
{
  "custom_name": "string (optional)"
}

Returns:
{
  "success": true,
  "domain_id": "string",
  "domain_name": "string"
}
```

### List Installed Domains

```bash
GET /api/domains

Returns:
{
  "domains": [
    {
      "id": "string",
      "domain_name": "string",
      "category": "string",
      "parent_domain_id": "string",
      "installed_at": "timestamp"
    }
  ]
}
```

### Get Domain Knowledge

```bash
GET /api/domains/{domain_id}/knowledge

Returns domain knowledge base for review
```

## Examples

### Complete Example: Financial Analyst Agent

```bash
# 1. Install Finance domain
curl -X POST http://localhost:8000/api/v1/marketplace/domains/domain_financial_analysis_001/install \
  -H "Content-Type: application/json" \
  -d '{
    "custom_name": "Corporate Finance"
  }'

# 2. Create agent with domain expertise
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Financial Analyst",
    "agent_type": "specialist",
    "domains": ["domain_financial_analysis_001"],
    "maturity": "INTERN",
    "capabilities": [
      "financial_report_generation",
      "budget_analysis"
    ]
  }'

# 3. Use agent for financial analysis
curl -X POST http://localhost:8000/api/agents/financial_analyst/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Generate monthly P&L report",
    "context": {
      "period": "2026-03",
      "include_variance": true
    }
  }'
```

### Complete Example: Sales Agent with Multiple Domains

```bash
# 1. Install Sales and Marketing domains
curl -X POST http://localhost:8000/api/v1/marketplace/domains/domain_sales_001/install
curl -X POST http://localhost:8000/api/v1/marketplace/domains/domain_marketing_001/install

# 2. Create agent with both domains
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales Rep",
    "agent_type": "specialist",
    "domains": [
      "domain_sales_001",
      "domain_marketing_001"
    ],
    "maturity": "SUPERVISED",
    "capabilities": [
      "lead_qualification",
      "deal_forecasting",
      "campaign_analysis"
    ]
  }'

# 3. Agent can now leverage both domains
# - Sales domain for lead qualification
# - Marketing domain for campaign insights
```

## Support

### Documentation

- **Domain Architecture**: [agents/domains.md](../agents/domains.md)
- **Agent Governance**: [agents/governance.md](../agents/governance.md)
- **Connection Guide**: [marketplace/connection.md](connection.md)

### Community

- **Marketplace**: [https://atomagentos.com/marketplace/domains](https://atomagentos.com/marketplace/domains)
- **Documentation**: [https://docs.atomagentos.com/domains](https://docs.atomagentos.com/domains)
- **GitHub Issues**: [https://github.com/rush86999/atom/issues](https://github.com/rush86999/atom/issues)

---

**Version:** 1.0
**Platform:** Atom Open Source + atomagentos.com Marketplace
**Last Updated:** 2026-04-07
