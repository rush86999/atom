<div align="center">

# ATOM Platform
### Open-Source AI Agent Workforce for Your Team

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Give every employee a team of AI agents — trusted and safe by design.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/rush86999/atom/ci.yml?branch=main&label=CI)](https://github.com/rush86999/atom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-27%2C000%2B-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Stars](https://img.shields.io/github/stars/rush86999/atom?style=social)]()

</div>

---

## What is Atom?

Atom is an open-source, self-hosted **AI agent workforce** for your employees. Instead of one assistant, Atom runs a team of specialty agents — sales, support, finance, engineering — that your people delegate to in plain language. Agents plan, verify, and execute complex workflows across your entire tech stack.

**Trusted by design**: every agent action is governed by a 4-tier maturity model, executed inside a default-on sandbox, and recorded in a complete audit trail — with human-in-the-loop approval wherever you want it. Your employees get capable help; you keep control.

**Your data stays yours**: workflow data, agent state, and memory live on your infrastructure. LLM inference uses your own API keys (BYOK) — or local models (Ollama/Llama.cpp) for fully private deployments.

**💰 Budget-friendly AI agents**: OpenCode Go subscription (~90% savings vs pay-per-token) — one $10/mo key unlocks **general-purpose models** (DeepSeek V4 **1M ctx**, Kimi K3 **1M ctx**, GLM 5.2, MiniMax M3, Qwen 3.7, Nemotron 3 Ultra, Grok 4.5) with **full tool-calling, structured output, up to 1M context** — not just for coding, works for any agent workload.

**No lock-in**: 16+ LLM providers (OpenAI, Anthropic, DeepSeek, Gemini, MiniMax, Groq…) with automatic cost-aware routing, fallback, and self-healing.

---

## 🚀 AI-Generated Workflow Automation

**Describe the outcome. Atom builds and runs the workflow.**

| What you say | What Atom delivers |
|---|---|
| *"When a lead comes in HubSpot, research the company, score it, create an Asana task for the rep, and ping Slack"* | A governed, replayable workflow with Human-in-the-Loop approval gates |
| *"Extract invoice data from Gmail PDFs, match against QuickBooks, flag discrepancies"* | End-to-end pipeline: Gmail → PDF OCR → QuickBooks reconciliation → Slack alert |
| *"Monitor Zendesk tickets for sentiment, auto-escalate urgent ones, draft replies"* | Real-time triage agent with approval before send |
| *"Generate a weekly sales report from Salesforce, format in Excel, email the team"* | Scheduled workflow: SOQL query → formula-evaluated Excel → Office 365 send |

**Why it's different from Zapier/Make/n8n:**
- **Agents, not just steps** — Agents *reason* (not just execute): they research, decide, retry, and self-correct
- **Governance built-in** — Maturity gates, HITL approval, audit trail, sandbox isolation
- **Self-hosted & private** — Your data, your keys, your infrastructure
- **Office-native** — Real Excel/Word/PPTX with formula evaluation, live Canvas co-editing
- **Agent-authored** — You can *chat with an agent* to build/modify workflows (no drag-and-drop required)

[Workflow Automation Guide →](docs/guides/FEATURES.md#-agent-skills) · [Quick Start →](docs/getting_started/quick-start.md)

---

## ⚡ The AI Agent Landscape — Where Atom Fits

```
                    ┌─────────────────────────────────────────────────────┐
                    │              AI AGENT SPECTRUM                      │
                    ├─────────────────┬─────────────────┬─────────────────┤
                    │   CONSUMER      │   DEVELOPER     │   ENTERPRISE    │
                    │   ASSISTANTS    │   FRAMEWORKS    │   WORKFORCE     │
                    ├─────────────────┼─────────────────┼─────────────────┤
                    │ ChatGPT/Claude  │ LangGraph       │ ✅ ATOM         │
                    │ Notion AI       │ AutoGPT         │                 │
                    │ Copilot         │ CrewAI          │                 │
                    │ Perplexity      │ AutoGen         │                 │
                    ├─────────────────┼─────────────────┼─────────────────┤
                    │ Single chat     │ Code-first      │ Team delegation │
                    │ No governance   │ Build-your-own  │ Governed by     │
                    │ Cloud-only      │ Self-hosted     │ design          │
                    │ No integrations │ Bring integrations│ 46+ native    │
                    └─────────────────┴─────────────────┴─────────────────┘
```

**Atom is the only open-source platform that delivers:**
- **Enterprise governance** (maturity tiers, HITL, audit) — without vendor lock-in
- **Self-hosted privacy** — your data, your keys, your infrastructure
- **Agent-authored workflows** — chat to build, no drag-and-drop
- **Office/Canvas native** — real Excel formulas, live co-editing
- **46+ business integrations** — Salesforce, HubSpot, Slack, Jira, Stripe, QuickBooks…

---

## 📊 Comparisons

| Alternative | Focus | Key Difference | Deep Dive |
|---|---|---|---|
| **Hermes Agent** (Nous Research) | Personal coding/productivity assistant | Single-agent, no governance, no integrations, no sandbox | [Atom vs Hermes →](docs/architecture/HERMES_COMPARISON.md) |
| **OpenClaw** | Personal productivity, messaging-first | Single-agent, Markdown memory, smart home focus | [Atom vs OpenClaw →](docs/features/atom-vs-openclaw.md) |
| **LangGraph / CrewAI / AutoGen** | Developer frameworks | Code-first, build-your-own governance & integrations | [Why Atom?](#-why-atom) |
| **Zapier / Make / n8n** | Workflow automation | Step-based (not agents), no reasoning, no governance | [AI-Generated Workflow Automation](#-ai-generated-workflow-automation) |

**TL;DR**: If you're evaluating personal agents → Hermes/OpenClaw. If you need governed multi-agent business automation → Atom.

---

## ⚡ Key Capabilities

| Category | Features |
|---|---|
| **🤖 Multi-Agent Orchestration** | Queen Agent (structured workflows) + Fleet Admiral (open-ended tasks) + Conductor (5 execution strategies) + validated state machine with rollback |
| **🛡️ Governance & Safety** | 4-tier maturity (Student→Autonomous), 3-layer policy engine, HITL approval, complete audit trail, AI-powered training |
| **🧠 Memory & Learning** | Per-turn fact extraction, 2-tier recall (SQL + LanceDB), episodic memory, `memory_remember/forget`, self-evolution (Memento/AlphaEvolver) |
| **💼 Office Automation** | Real-time Excel/Word/PPTX co-editing on Canvas; formula-evaluating workbook runtime; agent↔document sync |
| **🧩 Mini-Apps** | Agent-authored stateful canvas apps (spreadsheets/docs/decks) — Firecracker microVM isolation, per-instance chat co-editing |
| **🔍 GraphRAG & Intelligence** | Multi-hop expansion, Leiden community detection, JIT fact verification, D3 visual explorer |
| **🌐 46+ Business Integrations** | Salesforce, HubSpot, Slack, Teams, Gmail, Notion, Jira, Linear, Stripe, QuickBooks, Shopify, GitHub, GitLab, Zoom… |
| **🛰️ LLM Gateway** | OpenAI/Anthropic-compatible API over your BYOK — point Claude Code, n8n, or any OpenAI-SDK app at Atom |
| **💰 Cost-Aware Routing** | 5-tier cognitive classification, 16+ providers, learning router (feedback-based re-ranking), RTK token compression |

---

## 🛡️ Production-Ready Security (Default-On)

| Layer | What you get |
|---|---|
| **Execution Sandbox** | Filesystem scope, tool whitelist, tripwires, resource caps, KillRun — enforced on *every* dispatch path |
| **Encrypted Credentials** | OAuth integration tokens encrypted at rest (Fernet); production fails closed without key |
| **Per-Agent Capability Bindings** | Zero-trust tool scoping — agent can never exceed its tier floor |
| **Outbound Gatekeeper** | Rate limiting, response masking, HITL mutation approval on integration calls |
| **Data-Taint Tracking** | Restricted data observed in a run blocks external outbound actions |
| **External MCP Client** | Connect to arbitrary external MCP servers (Cloudflare portals) |

[Security Architecture →](docs/architecture/CLOUDFLARE_OS_SECURITY.md) · [Sandbox Deep-Dive →](docs/guides/EXECUTION_SANDBOX.md)

---

## 💻 Quick Start

```bash
git clone https://github.com/rush86999/atom.git && cd atom
make setup                 # one-shot dev bootstrap (venv, deps, .env, frontend)
make backend               # full backend on :8001
# in a second terminal:
make frontend              # Next.js UI on :3001
```

**Then set one LLM key in `backend/.env`:**
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `GOOGLE_API_KEY` … or
- `OPENCODE_API_KEY` for low-cost subscription coding models (~90% savings) or
- `ATOM_LOCAL_ONLY=true` + `OLLAMA_BASE_URL=http://localhost:11434/v1` for fully local

**Open http://localhost:3001** — Sign in as `admin@example.com` (password in `backend/logs/bootstrap_admin_password.txt`)

[Full Quick Start →](docs/getting_started/quick-start.md) · [Docker →](docs/operations/personal-edition.md) · [DigitalOcean 1-Click →](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

---

## 📚 Documentation & Discoverability

| Start Here | Deep Dives | Guides |
|---|---|---|
| [User Guide Index ⭐](docs/USER_GUIDE_INDEX.md) | [Agent System](docs/agents/overview.md) | [Quick Start](docs/getting_started/quick-start.md) |
| [Docs Index](docs/INDEX.md) | [Governance](docs/agents/governance.md) | [User Guide](docs/guides/USER_GUIDE.md) |
| [Env Variables](docs/reference/ENVIRONMENT_VARIABLES.md) | [Episodic Memory](docs/intelligence/episodic-memory.md) | [Workflow Automation](docs/guides/FEATURES.md) |
| [Architecture](docs/architecture/README.md) | [GraphRAG](docs/intelligence/graphrag.md) | [Mini-Apps](docs/guides/MINI_APPS_GUIDE.md) |
| | [Context Memory](docs/architecture/CONTEXT_MEMORY.md) | [Office Automation](docs/guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) |
| | [Learning Router](docs/architecture/LEARNING_LLM_ROUTER.md) | [Third-Party Integrations](docs/integrations/THIRD_PARTY_INTEGRATIONS.md) |
| | [LLM Gateway](docs/architecture/LLM_GATEWAY.md) | [OAuth Setup](docs/guides/OAUTH_QUICK_SETUP_GUIDE.md) |
| | [Mini-Apps Architecture](docs/architecture/MINI_APPS.md) | [Personal Edition](docs/operations/personal-edition.md) |
| | [Sandbox Layer](docs/architecture/SANDBOX_LAYER.md) | [Cloud Deployment](docs/deployment/CLOUD_DEPLOYMENT.md) |

---

## 🎯 Example Use Cases by Department

| Department | Scenario | Key Integrations |
|---|---|---|
| **Sales** | New HubSpot lead → Research company → Score → Asana task → Slack notify | HubSpot, Asana, Slack, LinkedIn |
| **Finance** | Gmail PDF invoice → OCR extract → QuickBooks match → Flag discrepancies | Gmail, QuickBooks, Excel, Slack |
| **Support** | Zendesk ticket → Sentiment analysis → Auto-escalate urgent → Draft reply | Zendesk, Slack, Email |
| **HR** | BambooHR new hire → Provision accounts → Invite to Slack → Schedule orientation | BambooHR, Google Workspace, Slack, Calendar |
| **Engineering** | GitHub PR → Run tests → Security scan → Post summary → Auto-merge if green | GitHub, GitLab, Slack, Jira |
| **Marketing** | Content calendar → Generate posts → Human review → Schedule multi-platform | Notion, Slack, LinkedIn, Twitter, Meta |

---

## 🏗️ Repository Layout

```
atom/
├── backend/            # FastAPI app — main_api_app:app (full) / minimal_app:app (smoke)
├── frontend-nextjs/    # Next.js web UI
├── mobile/             # React Native (Expo) companion app
├── menubar/            # Tauri macOS menubar companion
├── scripts/ · infra/ · installer/ · examples/
├── docs/               # project documentation
├── Dockerfile          # dual-app image (backend + frontend)
└── Makefile            # common tasks (start here)
```

---

## 🌟 Why Teams Choose Atom

| | Atom | Zapier/Make/n8n | LangGraph/CrewAI | OpenClaw | LangChain |
|---|---|---|---|---|---|
| **AI Agents (reason, not just execute)** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Governance (maturity + HITL + audit)** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Default-on Sandbox (all dispatch paths)** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Self-Hosted / Private (your keys, your infra)** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Office/Canvas Native (Excel formulas, co-edit)** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Agent-Authored Workflows (chat to build)** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **46+ Business Integrations (CRM, finance, support)** | ✅ | ✅ | — | 50+ personal | — |
| **Cost-Aware LLM Routing (16+ providers)** | ✅ | ❌ | ◐ | ◐ | ◐ |
| **Mini-Apps (agent-authored stateful apps)** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **GraphRAG / Episodic Memory** | ✅ | ❌ | ◐ | ◐ | ◐ |

---

## 🤝 Contributing & Support

We welcome contributions — see [CONTRIBUTING.md](CONTRIBUTING.md). Quality bar: tests pass (100%), coverage ≥70%, review required, docs updated.

- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Blog**: [Substack](https://substack.com/@rish2atom/posts)
- **License**: AGPL v3 — [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [FastAPI](https://fastapi.tiangolo.com/) **|** [SQLAlchemy](https://www.sqlalchemy.org/) **|** [LangChain](https://langchain.com/) **|** [Playwright](https://playwright.dev/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation — safe enough for your whole team.**

⭐ Star us on GitHub — it helps!

</div>