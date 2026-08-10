# Third-Party App Integrations — Complete Guide

> **Status**: 44+ native integrations + Activepieces catalog fallback  
> **Architecture**: `UniversalIntegrationService` + `IntegrationRegistry` + MCP tool exposure  
> **Governance**: Maturity-gated, capability-bound, sandbox-enforced (P9 default-on)  
> **Last Updated**: August 2026

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT / WORKFLOW REQUEST                          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    UniversalIntegrationService.execute()                 │
│  1. Circuit breaker check                                               │
│  2. Governance middleware (risk assessment, HITL approval)              │
│  3. IntegrationRegistry.get_service_instance() → OAuth token resolution │
│  4. Service-specific handler (_execute_salesforce, _execute_slack, ...) │
│  5. Spend attribution + circuit breaker record                          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         INTEGRATION REGISTRY                             │
│  • Per-tenant service instances (SalesforceService, SlackService, ...)  │
│  • Token storage/retrieval (encrypted at rest via BYOK_ENCRYPTION_KEY)  │
│  • OAuth 2.0 flow management (refresh, scopes, PKCE)                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      THIRD-PARTY SERVICE APIs                            │
│  Salesforce, HubSpot, Slack, Teams, Notion, GitHub, Jira, Stripe, ...   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `UniversalIntegrationService` | `integrations/universal_integration_service.py` | Unified execute/search interface |
| `IntegrationRegistry` | `core/integration_registry.py` | Service instance management, token resolution |
| `MCP Service` | `integrations/mcp_service.py` | Exposes integrations as tools to agents |
| `Governance Middleware` | `middleware/governance_middleware.py` | Risk assessment, HITL, rate limits, masking |
| `Circuit Breaker` | `core/circuit_breaker.py` | Failure isolation per service |

---

## Supported Integrations (44+ Native)

### Sales & CRM
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Salesforce** | CRUD (contact, account, opportunity, lead), SOQL query | ✅ Contacts, accounts, opportunities | ✅ | Full REST + Bulk API |
| **HubSpot** | CRUD (contacts, companies, deals, tickets), associations | ✅ | ✅ | CRM + Marketing |
| **Zoho CRM** | CRUD, search | ✅ | | |
| **Pipedrive** | CRUD | | | Via Activepieces |

### Communication & Collaboration
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Slack** | Post message, create channel, list users, reactions, files | ✅ Messages, users, channels | ✅ | Bot + User tokens |
| **Microsoft Teams** | Post, channels, meetings, chat | ✅ | ✅ | Graph API |
| **Discord** | Send message, create channel, roles | ✅ | | Bot token |
| **Google Chat** | Send message, spaces, threads | ✅ | | |
| **Telegram** | Send message, inline keyboards | | | Bot API |
| **WhatsApp** | Business API: templates, media, sessions | ✅ | ✅ | Meta Business |
| **Zoom** | Meetings, recordings, users | ✅ | ✅ | OAuth |
| **Zoho Mail** | Send, folders, search | | | |

### Project Management
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Asana** | Tasks, projects, sections, tags, users | ✅ | ✅ | PAT |
| **Jira** | Issues, projects, sprints, transitions, comments | ✅ | ✅ | Cloud + Server |
| **Linear** | Issues, projects, teams, cycles | ✅ | ✅ | GraphQL |
| **Trello** | Boards, lists, cards, labels, members | ✅ | ✅ | |
| **Monday.com** | Boards, items, columns, updates | ✅ | ✅ | |
| **Zoho Projects** | Projects, tasks, milestones | | | |

### Storage & Knowledge
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Google Drive** | Files, folders, permissions, export | ✅ | ✅ | Full Drive API |
| **Dropbox** | Files, folders, sharing, search | ✅ | ✅ | |
| **OneDrive** | Files, folders, permissions | ✅ | ✅ | Graph API |
| **Box** | Files, folders, collaborations | ✅ | ✅ | |
| **Notion** | Pages, databases, blocks, queries | ✅ | ✅ | Internal integration |
| **Zoho WorkDrive** | Files, folders | | | |

### Support & Ticketing
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Zendesk** | Tickets, users, organizations, views | ✅ | ✅ | |
| **Freshdesk** | Tickets, contacts, agents | ✅ | ✅ | |
| **Intercom** | Conversations, contacts, tags | ✅ | ✅ | |

### Development
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **GitHub** | Repos, issues, PRs, actions, workflows | ✅ | ✅ | Apps + PAT |
| **GitLab** | Projects, issues, MRs, pipelines | ✅ | ✅ | |
| **Figma** | Files, components, comments | ✅ | | |

### Finance & Payments
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Stripe** | Charges, customers, subscriptions, refunds | ✅ | ✅ | |
| **QuickBooks** | Invoices, customers, expenses, reports | ✅ | ✅ | OAuth |
| **Xero** | Invoices, contacts, bank transactions | ✅ | ✅ | |
| **Zoho Books** | Invoices, contacts, items | | | |
| **Zoho Inventory** | Items, warehouses, orders | | | |
| **AWS SES** | Send email, templates | | | |

### Marketing & Analytics
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Mailchimp** | Campaigns, audiences, templates | ✅ | ✅ | |
| **HubSpot Marketing** | Emails, forms, workflows | ✅ | | |
| **Meta Ads** | Campaigns, ad sets, insights | | | |
| **Google Ads** | Campaigns, keywords, reports | | | |
| **LinkedIn Ads** | Campaigns, analytics | | | |
| **Google Analytics** | Reports, real-time | ✅ | | GA4 |
| **Tableau** | Workbooks, datasources | | | |
| **Google Reviews** | Place reviews | ✅ | | |

### E-Commerce
| Service | Actions | Search | Webhooks | Notes |
|---------|---------|--------|----------|-------|
| **Shopify** | Products, orders, customers, webhooks | ✅ | ✅ | GraphQL + REST |

---

## How to Use Integrations

### 1. Via Agent (MCP Tools) — Primary Path

Every integration is exposed as MCP tools through `integrations/mcp_service.py`. Agents call them naturally:

```python
# Agent automatically discovers and calls:
await mcp.call_tool("salesforce_create_contact", {"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
await mcp.call_tool("slack_post_message", {"channel": "#general", "text": "Hello!"})
await mcp.call_tool("github_create_issue", {"repo": "owner/repo", "title": "Bug", "body": "..."})
await mcp.call_tool("notion_query_database", {"database_id": "...", "filter": {...}})
```

**Tool naming**: `{service}_{action}_{entity}` (e.g., `salesforce_list_contacts`, `slack_post_message`)

### 2. Via UniversalIntegrationService (Direct)

```python
from integrations.universal_integration_service import UniversalIntegrationService

service = UniversalIntegrationService(workspace_id="ws-123")

# Execute action
result = await service.execute(
    service="salesforce",
    action="create",
    params={"entity": "contact", "data": {"FirstName": "John", "LastName": "Doe", "Email": "john@example.com"}},
    context={"user_id": "user-123", "agent_id": "agent-456"}
)

# Search
results = await service.search(
    service="hubspot",
    query="Acme Corp",
    entity_type="company",
    context={"user_id": "user-123"}
)
```

### 3. Via REST API (Frontend/External)

```bash
# Execute integration action
curl -X POST http://localhost:8000/api/rpc/universal_integration_execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "salesforce",
    "action": "list",
    "params": {"entity": "contact"},
    "context": {"user_id": "user-123"}
  }'

# Search
curl -X POST http://localhost:8000/api/rpc/universal_integration_search \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"service": "hubspot", "query": "Acme", "entity_type": "company"}'
```

---

## OAuth Configuration

### Environment Variables (backend/.env)

```bash
# Salesforce
SALESFORCE_CLIENT_ID=your_client_id
SALESFORCE_CLIENT_SECRET=your_client_secret
SALESFORCE_REDIRECT_URI=http://localhost:3000/oauth/callback/salesforce

# HubSpot
HUBSPOT_CLIENT_ID=your_client_id
HUBSPOT_CLIENT_SECRET=your_client_secret
HUBSPOT_REDIRECT_URI=http://localhost:3000/oauth/callback/hubspot

# Slack
SLACK_CLIENT_ID=your_client_id
SLACK_CLIENT_SECRET=your_client_secret
SLACK_SIGNING_SECRET=your_signing_secret
SLACK_REDIRECT_URI=http://localhost:3000/oauth/callback/slack

# Microsoft Teams / Outlook / OneDrive / Graph
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:3000/oauth/callback/microsoft

# GitHub
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_REDIRECT_URI=http://localhost:3000/oauth/callback/github

# Google (Drive, Calendar, Gmail, Chat, Analytics)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/callback/google

# ... (46+ total providers)
```

### OAuth Flow

```
1. User clicks "Connect" in UI → GET /api/oauth/authorize?provider=slack
2. Redirects to provider OAuth consent screen
3. User grants permission → Redirect to /api/oauth/callback/slack?code=...
4. Backend exchanges code for tokens → Stores encrypted (Fernet) in IntegrationToken table
5. Tokens auto-refreshed on 401 via UniversalIntegrationService
```

### Token Storage

- **Table**: `IntegrationToken` (access_token, refresh_token encrypted at rest)
- **Encryption**: Fernet via `BYOK_ENCRYPTION_KEY` (persisted to `./data/byok_encryption_key`, 0600)
- **Fail-closed in prod**: Missing key → startup error (not throwaway key)
- **Scope**: Per-user, per-provider, per-workspace

---

## Governance & Security

### Maturity Gates

| Complexity | Actions | Min Tier |
|------------|---------|----------|
| 1 (LOW) | search, read, get, list | STUDENT+ |
| 2 (MODERATE) | analyze, stream_chat, post_message, send | INTERN+ |
| 3 (HIGH) | create, update, submit_form, delete | SUPERVISED+ |
| 4 (CRITICAL) | execute, payment | AUTONOMOUS only |

### Capability Bindings (P2)

Agents declare `capabilities: string[]` in `AgentRegistry`. At dispatch:

```
effective = agent.capabilities ∩ tier_floor ∩ sandbox_policy
```

Integration capabilities:
- `salesforce_read`, `salesforce_write`, `salesforce_delete`
- `slack_post`, `slack_read`, `slack_admin`
- `github_read`, `github_write`, `github_admin`
- etc.

### Sandbox Gate (P9 Default-On)

Every integration call flows through:
```
mcp_service.call_tool → sandbox_gate.evaluate_tool_call
  → Phase A: Policy + Audit
  → Phase B: FS scope
  → Phase C: Tripwires + Caps + KillRun
  → Phase D: Firecracker microVM (opt-in)
  → Phase E: Provenance + ActionJudge (opt-in)
```

### Outbound Gatekeeper (P3)

Per-service policy at `middleware/governance_middleware.py`:
- OAuth token auto-refresh
- Rate limiting (per-service RPM/TPM)
- Response field masking (PII redaction)
- HITL mutation approval for CRITICAL actions
- Audit logging

### Data Taint Tracking (P4)

- Sensitivity labels: `public` → `internal` → `confidential` → `restricted`
- PII auto-classification
- Blocks restricted data egress (`VT_PROVENANCE` violation)

---

## Webhook Handling

### Supported Webhooks (Auto-Verified)

| Service | Secret Env Var | Verification |
|---------|----------------|--------------|
| Slack | `SLACK_SIGNING_SECRET` | HMAC-SHA256 |
| GitHub | `GITHUB_WEBHOOK_SECRET` | HMAC-SHA256 |
| Stripe | `STRIPE_WEBHOOK_SECRET` | HMAC-SHA256 |
| Shopify | `SHOPIFY_WEBHOOK_SECRET` | HMAC-SHA256 (fail-closed) |
| HubSpot | `HUBSPOT_WEBHOOK_SECRET` | HMAC-SHA256 |
| Salesforce | — | Replay ID + certificate |
| Microsoft Teams | `MICROSOFT_WEBHOOK_SECRET` | Bearer token |
| Gmail | `ATOM_GMAIL_WEBHOOK_SECRET` | Pub/Sub OIDC |
| Zoom | `ZOOM_WEBHOOK_SECRET` | HMAC-SHA256 |

### Webhook Endpoints

```
POST /api/webhooks/slack
POST /api/webhooks/github
POST /api/webhooks/stripe
POST /api/webhooks/shopify
POST /api/webhooks/hubspot
POST /api/webhooks/teams
POST /api/webhooks/gmail
POST /api/webhooks/zoom
POST /api/webhooks/discord
POST /api/webhooks/intercom
POST /api/webhooks/zendesk
```

**Fail-closed**: Missing secret → 503/401 (not processed unverified)

---

## Activepieces Fallback (1000+ Apps)

For services not in `NATIVE_INTEGRATIONS`, Atom falls back to **Activepieces** catalog:

```python
# In UniversalIntegrationService._dispatch_execution:
elif service in NATIVE_INTEGRATIONS:
    return await self._execute_generic_native(service, action, params, context)
else:
    return await self._execute_activepieces(service, action, params, context)
```

### Activepieces Integration

- **Catalog**: 1000+ pre-built pieces (Zapier-compatible)
- **Execution**: Via `piece-engine` (Node.js runtime)
- **Auth**: Piece-specific OAuth handled by Activepieces
- **Limitation**: Less governance granularity than native

---

## Adding a Custom Integration

### 1. Create Service Module

```python
# integrations/my_service.py
from typing import Dict, Any
from integrations.integration_helpers import with_governance_check, create_execution_record

class MyService:
    def __init__(self, access_token: str):
        self.token = access_token
        self.base_url = "https://api.myservice.com/v1"
    
    async def list_items(self) -> Dict[str, Any]:
        # HTTP call with self.token
        pass
    
    async def create_item(self, data: Dict) -> Dict[str, Any]:
        pass
```

### 2. Register in UniversalIntegrationService

```python
# In _dispatch_execution:
elif service == "my_service":
    return await self._execute_my_service(action, params, context)
```

### 3. Add to NATIVE_INTEGRATIONS

```python
# integrations/universal_integration_service.py
NATIVE_INTEGRATIONS = {
    # ... existing
    "my_service",
}
```

### 4. Add to IntegrationRegistry

```python
# core/integration_registry.py
async def get_service_instance(self, service: str, tenant_id: str):
    if service == "my_service":
        token = await self.get_token("my_service", tenant_id)
        return MyService(token)
```

### 5. Add OAuth Config

```python
# core/oauth_config.py
OAUTH_CONFIGS["my_service"] = {
    "authorize_url": "https://myservice.com/oauth/authorize",
    "token_url": "https://myservice.com/oauth/token",
    "scopes": ["read", "write"],
    "pkce": True,
}
```

### 6. Add Environment Variables

```bash
# backend/.env
MY_SERVICE_CLIENT_ID=...
MY_SERVICE_CLIENT_SECRET=...
MY_SERVICE_REDIRECT_URI=...
```

### 7. Register MCP Tools

```python
# tools/registry.py -> _register_integration_tools()
self.register(
    name="my_service_list_items",
    function=my_service_list_items,
    category="integration",
    complexity=1,
    maturity_required="STUDENT",
    # ...
)
```

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| "Circuit breaker is OPEN" | Too many failures | Wait for cooldown, check service health |
| "Could not authenticate" | Token expired/missing | Re-run OAuth flow, check token storage |
| "Action paused for manual review" | Governance HITL triggered | Approve via `/api/governance/interventions/{id}/approve` |
| "Agent not permitted" | Maturity/capability mismatch | Upgrade agent tier or add capability |
| "user_id required" | No user context | Pass `user_id` in context, or use system agent |
| Webhook 401/503 | Missing secret | Set `*_WEBHOOK_SECRET` env var |
| Rate limited | Service RPM/TPM exceeded | Back off, check `OPENCODE_RPM` style limits |

### Debug Commands

```bash
# Check circuit breaker status
curl http://localhost:8000/api/debug/circuit-breaker

# Check integration registry
curl http://localhost:8000/api/integrations/registry

# Test specific service
curl -X POST http://localhost:8000/api/rpc/universal_integration_execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"service": "slack", "action": "health", "params": {}}'

# View governance interventions
curl http://localhost:8000/api/governance/interventions
```

---

## Performance & Limits

| Metric | Target |
|--------|--------|
| Native integration latency | < 500ms p99 |
| Activepieces fallback latency | < 2s p99 |
| Circuit breaker threshold | 5 failures → 60s cooldown |
| Rate limits (per service) | Configurable via env (e.g., `SLACK_RPM=60`) |
| Token refresh | Automatic on 401 |
| Concurrent connections | 10,000+ |

---

## Related Documentation

- [Integration Overview](OVERVIEW.md) — High-level ecosystem
- [Universal Integration Service](../backend/integrations/universal_integration_service.py) — Code reference
- [Integration Registry](../core/integration_registry.py) — Token management
- [Governance Middleware](../middleware/governance_middleware.py) — Security layer
- [Circuit Breaker](../core/circuit_breaker.py) — Failure isolation
- [OAuth Quick Setup](../guides/OAUTH_QUICK_SETUP_GUIDE.md) — 5-minute OAuth
- [OAuth Setup Checklist](../guides/OAUTH_SETUP_CHECKLIST.md) — Complete config
- [Execution Sandbox](../guides/EXECUTION_SANDBOX.md) — Blast-radius defense
- [Agent Maturity & Governance](../guides/AGENT_MATURITY_GOVERNANCE.md) — Tier system

---

*Last Updated: August 2026 · 44+ native integrations + Activepieces catalog*