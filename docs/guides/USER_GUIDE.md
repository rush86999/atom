# Atom User Guide

> **Last Updated:** August 2026  
> **Platform:** Atom Open Source — AI Agent Workforce

---

## Welcome to Atom

Atom is a **self-hosted AI agent workforce** — a team of governed, sandboxed agents your employees can delegate work to with confidence. Instead of one assistant, Atom runs a team of specialty agents (sales, support, finance, engineering) that your people delegate to in plain language. Agents plan, verify, and execute complex workflows across your entire tech stack.

**Key Principles:**
- **Trusted by design**: Every agent action is governed by a 4-tier maturity model, executed inside a default-on sandbox, and recorded in a complete audit trail — with human-in-the-loop approval wherever you want it
- **Your data stays yours**: Workflow data, agent state, and memory live on your infrastructure. LLM inference uses your own API keys (BYOK) — or local models (Ollama) for fully private deployments
- **No lock-in**: 16+ LLM providers with automatic cost-aware routing, fallback, and self-healing

---

## Getting Started

### First Time Setup

1. **Deploy Atom**
   - **Quick local**: `git clone && make setup && make backend` (see [Quick Start](getting_started/quick-start.md))
   - **Docker**: `docker compose -f docker-compose-personal.yml up -d --build`
   - **DigitalOcean 1-click**: [Deploy →](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

2. **Configure LLM Provider** (optional — server boots without one, LLM features disabled)
   ```bash
   # backend/.env — set a provider key, or add one later via Settings > AI
   OPENCODE_API_KEY=oc_...  # Low-cost subscription (~90% savings, recommended)
   # OPENAI_API_KEY=sk-...
   # ANTHROPIC_API_KEY=sk-ant-...
   # DEEPSEEK_API_KEY=...
   # GOOGLE_API_KEY=...
   # ATOM_LOCAL_ONLY=true + OLLAMA_BASE_URL=http://localhost:11434/v1  # Fully local
   ```

3. **Access the UI**
   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8001
   - API Docs (Swagger): http://localhost:8001/docs
   - Admin user: `admin@example.com` (password in `backend/logs/bootstrap_admin_password.txt`)

---

## Core Capabilities

### 🤖 Multi-Agent Workforce

| Agent Type | Purpose | Governance |
|------------|---------|------------|
| **Queen Agent** | Structured workflow automation (scheduled, repeatable) | Workflow-level |
| **Fleet Admiral** | Open-ended task resolution (dynamic specialist recruitment) | Task-level |
| **Specialist Agents** | Domain-specific: research, coding, data analysis, sales, support | Maturity-gated |

**Maturity Tiers (4-Level Governance):**
- **STUDENT** (<0.5 confidence): Read-only — charts, markdown, presentations
- **INTERN** (0.5–0.7): Streaming, forms, browser automation — requires approval for state changes
- **SUPERVISED** (0.7–0.9): Full access with real-time supervision monitoring
- **AUTONOMOUS** (>0.9): Complete independence, no oversight required

Agents **graduate** automatically based on clean execution history (10/25/50 episodes for Bronze/Silver/Gold).

### 🎯 AI-Generated Workflow Automation

**Describe the outcome. Atom builds and runs the workflow.**

| What you say | What Atom delivers |
|--------------|-------------------|
| *"When a lead comes in HubSpot, research the company, score it, create an Asana task for the rep, and ping Slack"* | A governed, replayable workflow with Human-in-the-Loop approval gates |
| *"Extract invoice data from Gmail PDFs, match against QuickBooks, flag discrepancies"* | End-to-end pipeline: Gmail → PDF OCR → QuickBooks reconciliation → Slack alert |
| *"Monitor Zendesk tickets for sentiment, auto-escalate urgent ones, draft replies"* | Real-time triage agent with approval before send |
| *"Generate a weekly sales report from Salesforce, format in Excel, email the team"* | Scheduled workflow: SOQL query → formula-evaluated Excel → Office 365 send |

**Why it's different from Zapier/Make/n8n:**
- **Agents, not just steps** — Agents *reason*: they research, decide, retry, and self-correct
- **Governance built-in** — Maturity gates, HITL approval, audit trail, sandbox isolation
- **Self-hosted & private** — Your data, your keys, your infrastructure
- **Office-native** — Real Excel/Word/PPTX with formula evaluation, live Canvas co-editing
- **Agent-authored** — You can *chat with an agent* to build/modify workflows (no drag-and-drop required)

### 💼 Office Automation & Canvas Co-Editing

- **Real-time Excel/Word/PowerPoint editing** — no Microsoft Office required
- **Formula-evaluating workbook runtime** — LibreOffice → `formulas` lib → openpyxl fallback
- **Interactive Canvas co-editing** with real-time sync (WebSocket `canvas:update`)
- **Bi-directional sync** — Agent edits on Canvas appear in Office file and vice versa
- **CLI and REST API** integration tools for programmatic access

### 🧩 Mini-Apps (Aug 2026)

**Stateful, resumable canvas apps you build by chatting with an agent:**
- Agent-driven authoring: scaffold → write logic → acceptance tests → publish → install
- State persists between runs (versioned, latest-wins) with live WebSocket updates
- Each logic run executes in a **Firecracker microVM** (read-only rootfs, no host FS, no network)
- An app's declared scopes are always capped by the viewer's tier — **no privilege escalation**
- Versioned copy-on-install: publishing snapshots a credential-stripped blueprint; installs are fresh instances
- **Per-instance user↔agent chat** — talk to the agent about *this specific app instance*

[Mini-Apps User Guide →](guides/MINI_APPS_GUIDE.md)

### 🔌 46+ Business Integrations

| Category | Services |
|----------|----------|
| **CRM** | Salesforce, HubSpot, Pipedrive, Zoho CRM |
| **Communication** | Slack, Microsoft Teams, Discord, Gmail, Outlook, Google Chat, Zoom |
| **Project Management** | Jira, Linear, Asana, Trello, Notion, Monday, ClickUp, GitHub, GitLab, GitLab |
| **Finance** | Stripe, QuickBooks, Xero, Plaid, PayPal |
| **Support** | Zendesk, Freshdesk, Intercom |
| **Storage** | Google Drive, OneDrive, Dropbox, Box |
| **Marketing** | Mailchimp, Meta Ads, Google Ads, LinkedIn Ads |
| **E-Commerce** | Shopify |
| **Development** | GitHub, GitLab, Figma, Bitbucket |
| **HR** | BambooHR, Greenhouse, Workday |

Each integration supports OAuth 2.0 with encrypted token storage (Fernet), auto-refresh, and webhook verification.

[Third-Party Integrations Guide →](integrations/THIRD_PARTY_INTEGRATIONS.md)

### 🧠 Memory & Intelligence

| System | Purpose |
|--------|---------|
| **Per-Turn Fact Extraction** | Durable facts (5 categories) extracted every turn; sub-ms SQL recall + LanceDB semantic |
| **Episodic Memory** | Hybrid PG+LanceDB; 4 retrieval modes (temporal, semantic, outcome-filtered, graduation-gated) |
| **GraphRAG** | 6 entity types, multi-hop expansion, Leiden community detection, JIT fact verification |
| **Learning LLM Router** | Per-model satisfaction predictors re-rank candidates from observed outcomes + user feedback |
| **Self-Evolution** | Reflection Pool → Memento-Skills → AlphaEvolver optimization → human approval → install |

### 🛡️ Production-Ready Security (Default-On)

| Layer | What You Get |
|-------|--------------|
| **Execution Sandbox** | FS scope, tool whitelist, tripwires, caps, KillRun, Firecracker microVM — enforced on *every* dispatch path |
| **Encrypted Credentials** | OAuth tokens encrypted at rest (Fernet); production fails closed without key |
| **Per-Agent Capability Bindings** | Zero-trust tool scoping — agent can never exceed its tier floor |
| **Outbound Gatekeeper** | Rate limiting, response masking, HITL mutation approval on integration calls |
| **Data-Taint Tracking** | Restricted data observed in a run blocks external outbound actions |
| **External MCP Client** | Connect to arbitrary external MCP servers (Cloudflare portals) |

[Security Architecture →](docs/architecture/CLOUDFLARE_OS_SECURITY.md)

---

## Daily Workflows by Role

### For End Users (Employees)

1. **Chat with agents** — "Research this lead and draft an outreach email"
2. **View Canvas presentations** — Charts, forms, markdown rendered by agents
3. **Co-edit Office files** — Live sync between Canvas and Excel/Word/PPTX
4. **Approve proposals** — HITL approvals for agent actions requiring supervision
5. **Run Mini-Apps** — Use agent-authored apps; chat with the co-pilot agent

### For Workflow Creators

1. **Describe outcomes** — "When X happens, do Y with approval from Z"
2. **Use Queen Agent** — Structured, scheduled workflows with visual builder
3. **Use Fleet Admiral** — Open-ended tasks requiring dynamic specialist recruitment
4. **Monitor via Canvas** — Real-time execution tracking, progress, errors

### For Developers

1. **Extend via MCP** — Add custom tools exposed to agents
2. **Build integrations** — OAuth + service class pattern
3. **Custom agents** — Define capabilities, maturity, prompts
4. **API access** — REST (`/api/*`), MCP (`/mcp`), RPC (`/api/rpc/*`)

### For Administrators

1. **Configure governance** — Maturity thresholds, capability bindings, sandbox policies
2. **Manage integrations** — OAuth credentials, webhook secrets, sync schedules
3. **Monitor health** — `/health/live`, `/health/ready`, `/health/metrics` (Prometheus)
4. **Audit trails** — Agent executions, canvas audits, sandbox violations, governance decisions

---

## Platform Access

| Platform | Status | Access |
|----------|--------|--------|
| **Web (Next.js)** | ✅ Full | http://localhost:3001 |
| **Mobile (React Native/Expo)** | ✅ Full | iOS/Android via Expo |
| **Desktop (Tauri Menubar)** | ✅ Full | macOS menubar companion |
| **CLI** | ✅ Full | `atom-os` daemon, skills, status |

---

## Troubleshooting

### Common Issues

| Issue | Resolution |
|-------|------------|
| **"No providers configured"** | Set at least one LLM key in `backend/.env` |
| **"Could not validate credentials"** | `SECRET_KEY` not set — tokens reset on restart |
| **Admin password lost** | Read `backend/logs/bootstrap_admin_password.txt` |
| **Port in use** | Use different `--port`; update `NEXT_PUBLIC_API_URL` |
| **ModuleNotFoundError (backend.api)** | Run uvicorn from repo root with `PYTHONPATH=$PWD:$PWD/backend` |

[Full Troubleshooting →](getting_started/TROUBLESHOOTING.md)

### Getting Help

1. **Documentation** — [Docs Index](INDEX.md) | [Architecture](architecture/README.md)
2. **GitHub Issues** — [Report bugs](https://github.com/rush86999/atom/issues)
3. **Discussions** — [GitHub Discussions](https://github.com/rush86999/atom/discussions)
4. **Marketplace** — [atomagentos.com](https://atomagentos.com)

---

## Quick Links

| Topic | Link |
|-------|------|
| **Quick Start** | [getting_started/quick-start.md](getting_started/quick-start.md) |
| **Installation Options** | [getting_started/INSTALLATION.md](getting_started/INSTALLATION.md) |
| **LLM Providers** | [guides/LLM_PROVIDERS.md](guides/LLM_PROVIDERS.md) |
| **Agent Governance** | [guides/AGENT_MATURITY_GOVERNANCE.md](guides/AGENT_MATURITY_GOVERNANCE.md) |
| **Memory Systems** | [guides/MEMORY_SYSTEMS.md](guides/MEMORY_SYSTEMS.md) |
| **Execution Sandbox** | [guides/EXECUTION_SANDBOX.md](guides/EXECUTION_SANDBOX.md) |
| **Mini-Apps** | [guides/MINI_APPS_GUIDE.md](guides/MINI_APPS_GUIDE.md) |
| **Office Automation** | [guides/ATOM_OFFICE_AUTOMATION_GUIDE.md](guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) |
| **Third-Party Integrations** | [integrations/THIRD_PARTY_INTEGRATIONS.md](integrations/THIRD_PARTY_INTEGRATIONS.md) |
| **API Reference** | [api/OVERVIEW.md](api/OVERVIEW.md) |
| **Environment Variables** | [reference/ENVIRONMENT_VARIABLES.md](reference/ENVIRONMENT_VARIABLES.md) |

---

**Atom is constantly evolving.** We welcome your feedback and contributions — see [CONTRIBUTING.md](../CONTRIBUTING.md).