# Atom Feature Matrix

> **Compare Personal and Enterprise editions**

| Feature | Personal | Enterprise | Description |
|---------|----------|------------|-------------|
| **Price** | Free | Paid | Licensing |
| **Users** | 1 | Unlimited | User seats |
| **Support** | Community | Priority | Support level |

---

## Core Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| Local Agent Execution | ✅ | ✅ |
| Workflow Automation | ✅ | ✅ |
| Canvas Presentations | ✅ | ✅ |
| Browser Automation | ✅ | ✅ |
| Episodic Memory | ✅ | ✅ |
| Agent Governance | ✅ | ✅ |
| Agent Graduation | ✅ | ✅ |
| Community Skills | ✅ | ✅ (5,000+ skills) |
| Telegram Connector | ✅ | ✅ |
| Vector Embeddings (Local) | ✅ | ✅ |

---

## Collaboration Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| Multi-User | ❌ | ✅ |
| Workspace Isolation | ❌ | ✅ |
| Team Sharing | ❌ | ✅ |
| Role-Based Access Control | ❌ | ✅ |
| Agent Collaboration | ✅ | ✅ |
| Social Feed | ✅ | ✅ |

---

## Integration Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| Gmail Integration | ✅ | ✅ |
| Slack Integration | ✅ | ✅ |
| Telegram Bot | ✅ | ✅ |
| Webhooks | ✅ | ✅ |
| API Access | ✅ | ✅ |
| Custom Integrations | ✅ | ✅ |

---

## Enterprise Features

| Feature | Personal | Enterprise |
|---------|----------|------------|
| PostgreSQL Database | ❌ | ✅ |
| Multi-User Support | ❌ | ✅ |
| Workspace Isolation | ❌ | ✅ |
| SSO (Okta, Auth0, SAML) | ❌ | ✅ |
| Audit Trail | Basic | Full |
| Monitoring | Basic | Prometheus + Grafana |
| Advanced Analytics | ❌ | ✅ |
| BI Dashboard | ❌ | ✅ |
| Rate Limiting | ❌ | ✅ |
| Priority Support | ❌ | ✅ |
| SLA | ❌ | ✅ |

---

## Feature Details

### Local Agent Execution

Run AI agents on your local machine with governance controls.

**Personal:** Single agent, local execution
**Enterprise:** Multiple agents, distributed execution

### Workflow Automation

Create visual workflows with triggers, actions, and conditions.

**Personal:** 10 workflows max
**Enterprise:** Unlimited workflows

### Canvas Presentations

Rich interactive presentations with charts, forms, and sheets.

**Personal:** 5 concurrent canvases
**Enterprise:** Unlimited canvases

### Browser Automation

Web scraping, form filling, screenshots via Playwright CDP.

**Personal:** 1 browser session
**Enterprise:** 10 concurrent sessions

### Episodic Memory

Agents remember and learn from past interactions.

**Personal:** 1000 episodes max
**Enterprise:** Unlimited episodes

### Agent Governance

Maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) with permissions.

**Personal:** Manual promotion
**Enterprise:** Auto-graduation with compliance validation

### Community Skills

Import 5,000+ OpenClaw/ClawHub community skills with security sandbox.

**Personal:** Untrusted skills require approval
**Enterprise:** LLM security scanning + governance

### Vector Embeddings

Semantic search and memory retrieval.

**Personal:** FastEmbed (local, 384-dim)
**Enterprise:** OpenAI/Cohere (cloud, higher dim)

### Multi-User Support

Multiple users with separate workspaces.

**Personal:** Not available
**Enterprise:** Unlimited users

### SSO Integration

Single sign-on with Okta, Auth0, or SAML.

**Personal:** Not available
**Enterprise:** All providers

### Monitoring

Application metrics and dashboards.

**Personal:** Basic logging
**Enterprise:** Prometheus metrics + Grafana dashboards

### Audit Trail

Compliance logging for all agent actions.

**Personal:** Local logs only
**Enterprise:** Structured audit logs, 90-day retention

### Advanced Analytics

Workflow performance analytics and BI dashboards.

**Personal:** Not available
**Enterprise:** Full analytics suite

---

## Edition Comparison by Use Case

### Personal Use

**Best for:** Individuals, students, researchers

**Features:**
- Local automation
- Agent experimentation
- Learning AI governance
- Privacy-focused (data stays local)

**Limitations:**
- Single user
- SQLite database (not production-ready)
- No SSO
- Basic monitoring

### Small Teams

**Best for:** Startups, small teams

**Features:**
- Multi-user support
- Workspace isolation
- Team sharing
- PostgreSQL database

**Limitations:**
- No SSO
- No advanced analytics

### Enterprise

**Best for:** Large organizations, regulated industries

**Features:**
- Everything in Small Teams
- SSO integration
- Full monitoring stack
- Compliance audit trail
- Advanced analytics
- Priority support
- SLA guarantees

---

## Feature Flag API

Programmatically check feature availability:

```python
from core.package_feature_service import get_package_feature_service, Feature

service = get_package_feature_service()

# Check edition
if service.is_enterprise:
    print("Enterprise features available")

# Check specific feature
if service.is_feature_enabled(Feature.MULTI_USER):
    print("Multi-user support available")

# Require feature (raises error if not available)
service.require_feature(Feature.SSO)
```

---

## Upgrading Editions

### Personal → Enterprise

```bash
# Via CLI
atom enable enterprise

# Via API
curl -X POST http://localhost:8000/api/edition/enable \
    -H "Content-Type: application/json" \
    -d '{"database_url": "postgresql://..."}'
```

**What changes:**
- ATOM_EDITION=personal → ATOM_EDITION=enterprise
- SQLite → PostgreSQL
- Single-user → Multi-user
- Basic → Full monitoring

**Migration required:**
- Export SQLite database
- Import to PostgreSQL
- Update DATABASE_URL in .env
- Restart Atom

---

## See Also

- [Installation Guide](INSTALLATION.md)
- [Personal Edition Guide](PERSONAL_EDITION.md)
- [Package Feature Service API](../backend/core/package_feature_service.py)
