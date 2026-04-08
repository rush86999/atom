# docs.atomagentos.com Documentation Guide

**Last Updated:** 2026-04-07

Complete guide to the atomagentos.com documentation platform and how it integrates with the self-hosted Atom Agent OS documentation.

## 🌐 Overview

**docs.atomagentos.com** is the official documentation platform for the Atom Agent OS commercial marketplace service. It complements the self-hosted documentation by providing:

- **Marketplace Documentation** - Commercial service guides
- **API References** - Complete marketplace API documentation
- **Account Management** - User account and billing guides
- **Support Portal** - Help center and troubleshooting
- **Release Notes** - Platform updates and changelogs

### Documentation Split

```
┌─────────────────────────────────────────────────────────────┐
│                  docs.atomagentos.com                       │
│         Commercial Mothership Documentation                   │
│                                                              │
│  - Marketplace overview and features                        │
│  - Account management (API tokens, billing)                  │
│  - Commercial API references                                │
│  - Terms of service and licensing                            │
│  - Support and troubleshooting                              │
└─────────────────────────────────────────────────────────────┘
                              ↕ Integration
┌─────────────────────────────────────────────────────────────┐
│            atom-upstream/docs/ (Self-Hosted)                 │
│         Open Source Platform Documentation                    │
│                                                              │
│  - Installation and setup                                   │
│  - Agent system documentation                               │
│  - Canvas system documentation                              │
│  - Integration guides                                       │
│  - Development and testing                                  │
└─────────────────────────────────────────────────────────────┘
```

## 📚 Documentation Coverage

### docs.atomagentos.com (Commercial)

| Topic | Description | URL |
|-------|-------------|-----|
| **Marketplace Overview** | Introduction to the commercial marketplace | `/marketplace` |
| **Getting Started** | Quick start for marketplace users | `/marketplace/getting-started` |
| **Account Management** | API tokens, billing, subscriptions | `/account` |
| **API Reference** | Complete marketplace API documentation | `/api` |
| **Terms of Service** | Commercial terms and licensing | `/legal/terms` |
| **Privacy Policy** | Data handling and privacy | `/legal/privacy` |
| **Support** | Help center and FAQs | `/support` |
| **Release Notes** | Platform updates and changelogs | `/releases` |

### atom-upstream/docs/ (Open Source)

| Topic | Description | URL |
|-------|-------------|-----|
| **Installation** | Platform installation guides | `/GETTING_STARTED/installation.md` |
| **Marketplace Connection** | Connect self-hosted instance to marketplace | `/marketplace/connection.md` |
| **Agent System** | Agent governance, graduation, training | `/agents/` |
| **Canvas System** | Canvas presentation system | `/canvas/` |
| **Integrations** | Service integration guides | `/INTEGRATIONS/` |
| **Development** | Developer guides and reference | `/DEVELOPMENT/` |
| **Operations** | Deployment and monitoring | `/operations/` |

## 🚀 Getting Started with docs.atomagentos.com

### 1. Access the Documentation

**URL:** https://docs.atomagentos.com

**No Authentication Required:** Public documentation is accessible without logging in.

### 2. Navigate the Documentation

**Main Sections:**
- **Marketplace** - Marketplace features and usage
- **Account** - Account management and billing
- **API** - API references and guides
- **Legal** - Terms and policies
- **Support** - Help center

### 3. Search Documentation

Use the search bar at the top of any page:
- **Search by keyword** - Finds relevant pages
- **Search by tag** - Filter by topic tags
- **Search by category** - Browse by category

## 🔑 Account Management

### API Token Management

**Guide:** https://docs.atomagentos.com/account/api-tokens

**Steps:**
1. Log in to atomagentos.com
2. Navigate to Settings → API Tokens
3. Generate new marketplace token
4. Copy token to clipboard
5. Use token in self-hosted instance

**Token Types:**
- **Marketplace Token** - Access marketplace (atom-upstream)
- **Federation Token** - Share agents across instances
- **Analytics Token** - Push usage analytics

### Billing Management

**Guide:** https://docs.atomagentos.com/account/billing

**Topics Covered:**
- Subscription plans and pricing
- Payment methods
- Invoice management
- Usage quotas
- Plan upgrades/downgrades

## 📖 Marketplace Documentation

### Marketplace Overview

**URL:** https://docs.atomagentos.com/marketplace

**Contents:**
- Marketplace introduction
- Available marketplace types
- Commercial terms overview
- Feature comparison

### Agent Marketplace

**URL:** https://docs.atomagentos.com/marketplace/agents

**Contents:**
- Agent templates
- Publishing agents
- Installing agents
- Agent ratings and reviews

### Domain Marketplace

**URL:** https://docs.atomagentos.com/marketplace/domains

**Contents:**
- Domain templates
- Domain capabilities
- Governance templates
- Installing domains

### Canvas Component Marketplace

**URL:** https://docs.atomagentos.com/marketplace/components

**Contents:**
- Component types
- Component development
- Publishing components
- Installing components

### Skills Marketplace

**URL:** https://docs.atomagentos.com/marketplace/skills

**Contents:**
- Skill types
- Skill development
- Publishing skills
- Installing skills

## 🔌 API Documentation

### API Overview

**URL:** https://docs.atomagentos.com/api

**Contents:**
- API authentication (X-API-Token)
- Rate limiting
- Error handling
- Response formats

### API Endpoints

**Marketplace API:**
```
GET  /api/v1/marketplace/agents          # List agents
GET  /api/v1/marketplace/agents/{id}     # Agent details
POST /api/v1/marketplace/agents/{id}/install # Install agent

GET  /api/v1/marketplace/domains         # List domains
GET  /api/v1/marketplace/domains/{id}    # Domain details
POST /api/v1/marketplace/domains/{id}/install # Install domain

GET  /api/v1/marketplace/components      # List components
GET  /api/v1/marketplace/components/{id} # Component details
POST /api/v1/marketplace/components/{id}/install # Install component

GET  /api/v1/marketplace/skills          # List skills
GET  /api/v1/marketplace/skills/{id}     # Skill details
POST /api/v1/marketplace/skills/{id}/install # Install skill

GET  /api/v1/marketplace/health          # Health check
```

### Authentication

**Header:** `X-API-Token: at_saas_your_token_here`

**Example:**
```bash
curl -H "X-API-Token: at_saas_your_token_here" \
  https://atomagentos.com/api/v1/marketplace/agents
```

## 🤝 Integration with Self-Hosted Docs

### Cross-References

**From self-hosted to commercial:**
```markdown
See [Marketplace API Reference](https://docs.atomagentos.com/api)
for complete API documentation.
```

**From commercial to self-hosted:**
```markdown
See [Connection Guide](https://github.com/rush86999/atom/tree/main/docs/marketplace/connection.md)
for setup instructions.
```

### Linking Strategy

**Self-Hosted Docs (atom-upstream):**
- Focus on installation, configuration, usage
- Link to docs.atomagentos.com for:
  - Account management
  - API references
  - Commercial terms

**Commercial Docs (docs.atomagentos.com):**
- Focus on marketplace, accounts, API
- Link to self-hosted docs for:
  - Installation guides
  - Feature documentation
  - Development guides

## 🛠️ Common Tasks

### Task 1: Set Up Marketplace Connection

**docs.atomagentos.com:**
1. Go to https://docs.atomagentos.com/account/api-tokens
2. Follow instructions to generate API token
3. Copy token

**Self-hosted docs:**
1. Go to [marketplace/connection.md](https://github.com/rush86999/atom/blob/main/docs/marketplace/connection.md)
2. Follow setup instructions
3. Configure token in `.env`

### Task 2: Install Marketplace Component

**docs.atomagentos.com:**
1. Go to https://docs.atomagentos.com/marketplace/components
2. Browse available components
3. Choose component

**Self-hosted docs:**
1. Go to [canvas-components.md](https://github.com/rush86999/atom/blob/main/docs/marketplace/canvas-components.md)
2. Follow installation instructions
3. Use component in canvas

### Task 3: Troubleshoot Connection Issues

**docs.atomagentos.com:**
1. Go to https://docs.atomagentos.com/support/troubleshooting
2. Check service status
3. Review common issues

**Self-hosted docs:**
1. Go to [connection.md](https://github.com/rush86999/atom/blob/main/docs/marketplace/connection.md#troubleshooting)
2. Follow troubleshooting steps
3. Check logs and configuration

## 📋 Documentation Structure

### docs.atomagentos.com Structure

```
docs.atomagentos.com/
├── marketplace/
│   ├── overview.md
│   ├── agents/
│   │   ├── browsing.md
│   │   ├── publishing.md
│   │   └── installing.md
│   ├── domains/
│   │   ├── browsing.md
│   │   ├── publishing.md
│   │   └── installing.md
│   ├── components/
│   │   ├── browsing.md
│   │   ├── publishing.md
│   │   └── installing.md
│   └── skills/
│       ├── browsing.md
│       ├── publishing.md
│       └── installing.md
├── account/
│   ├── api-tokens.md
│   ├── billing.md
│   ├── subscriptions.md
│   └── security.md
├── api/
│   ├── authentication.md
│   ├── endpoints/
│   │   ├── agents.md
│   │   ├── domains.md
│   │   ├── components.md
│   │   └── skills.md
│   ├── rate-limits.md
│   └── errors.md
├── legal/
│   ├── terms.md
│   ├── privacy.md
│   └── licensing.md
├── support/
│   ├── faqs.md
│   ├── troubleshooting.md
│   └── contact.md
└── releases/
    ├── v1.0.md
    ├── v1.1.md
    └── changelog.md
```

## 🔍 Finding Documentation

### By Use Case

| Use Case | Documentation Location |
|----------|----------------------|
| **Generate API Token** | docs.atomagentos.com/account/api-tokens |
| **Connect to Marketplace** | self-hosted: marketplace/connection.md |
| **Browse Marketplace** | docs.atomagentos.com/marketplace |
| **Install from Marketplace** | self-hosted: marketplace/* |
| **API Documentation** | docs.atomagentos.com/api |
| **Troubleshoot Issues** | docs.atomagentos.com/support + self-hosted: marketplace/connection.md#troubleshooting |
| **Account/Billing** | docs.atomagentos.com/account |

### By Topic

| Topic | docs.atomagentos.com | Self-Hosted |
|-------|----------------------|-------------|
| **Marketplace** | `/marketplace/*` | `/marketplace/connection.md` |
| **API Reference** | `/api/*` | - |
| **Account Management** | `/account/*` | - |
| **Support** | `/support/*` | `/operations/troubleshooting.md` |
| **Installation** | - | `/GETTING_STARTED/installation.md` |
| **Features** | - | `/GUIDES/*`, `/agents/*`, `/canvas/*` |
| **Development** | - | `/DEVELOPMENT/*` |

## 🔗 Key Links

### Documentation

- **Main Docs:** https://docs.atomagentos.com
- **Marketplace:** https://docs.atomagentos.com/marketplace
- **API Reference:** https://docs.atomagentos.com/api
- **Account:** https://docs.atomagentos.com/account
- **Support:** https://docs.atomagentos.com/support

### Platform

- **Marketplace:** https://atomagentos.com/marketplace
- **Documentation:** https://docs.atomagentos.com
- **GitHub:** https://github.com/rush86999/atom
- **Self-Hosted Docs:** https://github.com/rush86999/atom/tree/main/docs

## 📝 Contributing to Documentation

### docs.atomagentos.com

**Managed by:** atomagentos.com team

**To contribute:**
1. Contact atomagentos.com support
2. Submit documentation improvements via support portal
3. Follow contribution guidelines in docs.atomagentos.com

### atom-upstream/docs/ (Self-Hosted)

**Open Source:** Community contributions welcome

**To contribute:**
1. Read [CONTRIBUTING.md](../CONTRIBUTING.md)
2. Follow documentation guidelines (see [DOCUMENTATION_STRUCTURE_GUIDE.md](../docs/DOCUMENTATION_STRUCTURE_GUIDE.md))
3. Submit pull request to GitHub
4. Include `documentation` label

## 🔄 Documentation Updates

### docs.atomagentos.com

**Update Frequency:** Continuous

**Notification Channels:**
- RSS feed: https://docs.atomagentos.com/rss
- Release notes: https://docs.atomagentos.com/releases
- Email notifications (account setting)

### atom-upstream/docs/

**Update Frequency:** With each release

**Notification Channels:**
- GitHub releases: https://github.com/rush86999/atom/releases
- CHANGELOG.md in repository
- Commit messages

## 🆘 Getting Help

### Documentation Issues

**docs.atomagentos.com:**
- Support portal: https://atomagentos.com/support
- Email: support@atomagentos.com
- Submit documentation feedback via support portal

**Self-hosted docs:**
- GitHub issues: https://github.com/rush86999/atom/issues
- Label: `documentation`
- Include document name and section

### Live Chat

**Availability:** Business hours (9 AM - 5 PM UTC)

**Access:** https://atomagentos.com/support/chat

### Community

- **GitHub Discussions:** https://github.com/rush86999/atom/discussions
- **Discord Server:** [Invite link in GitHub README](../README.md)
- **Stack Overflow:** Tag questions with `atom-agent-os`

## 📊 Documentation Metrics

### docs.atomagentos.com

| Metric | Value |
|--------|-------|
| **Total Pages** | 150+ |
| **Total Words** | 200,000+ |
| **API Endpoints Documented** | 50+ |
| **Code Examples** | 300+ |
| **Languages** | English (primary), Japanese (beta) |

### atom-upstream/docs/

| Metric | Value |
|--------|-------|
| **Total Pages** | 150+ |
| **Total Words** | 250,000+ |
| **Code Examples** | 450+ |
| **Languages** | English |

---

**Version:** 1.0
**Last Updated:** 2026-04-07
**Platform:** atomagentos.com (Commercial) + GitHub (Open Source)
