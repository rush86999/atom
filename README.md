<div align="center">

# ATOM Platform
### The governed agent platform — autonomy, earned.

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**88% of AI agent pilots never reach production.***
**Atom is built for the other path.**

<small>*Industry figure (Turion 2026). Atom makes no claims about its own deployments.</small>

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/rush86999/atom/ci.yml?branch=main&label=CI)](https://github.com/rush86999/atom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-85k%2B%20%E2%80%A2%20CI--gated%20core%20suite-brightgreen)]()
[![Governance](https://img.shields.io/badge/governance-0.027ms%20P99-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Stars](https://img.shields.io/github/stars/rush86999/atom?style=social)]()

</div>

---

## What is Atom?

Atom is an open-source, self-hosted **AI agent workforce** — a team of specialty agents (sales, support, finance, engineering) that your people delegate to in plain language. Where other platforms sell agent *capability*, Atom sells agent *accountability*: autonomy that is earned through verified outcomes, executed inside a deterministic safety net, on your hardware.

**Agents that earn trust, not assume it.** Atom's agents don't just respond to commands — they operate autonomously within governed boundaries, handling routine work end-to-end. Every agent starts as a supervised intern and graduates through a 4-tier maturity model (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) only after **verified** successful runs — 10/25/50 episodes, outcome-checked, not self-reported.

**Verified outcomes, not self-report.** Every mutating action is re-derived against your system of record by an independent postcondition oracle (on by default), and confidence is split into *self-reported* vs *externally verified*. An agent that says "done" is checked, not believed. A prompt-injected agent at any tier acts at that tier's *scoped* blast radius — bounded by a default-on sandbox layer: filesystem scope, tool whitelist, tripwires, resource caps, kill-run, egress allowlist, full provenance audit. 0.027ms P99 per check.

**Your data stays yours.** Workflow data, agent state, and memory live on your infrastructure — embedded store, no cloud required. LLM inference uses your own API keys (BYOK, encrypted at rest) — or local models (Ollama first-class, or any local OpenAI-compatible server: LM Studio, vLLM, llama.cpp server) for fully private deployments. EU AI Act data-governance obligations (Aug 2026)? Designed for, not retrofitted.

**Free edition, full features (AGPL v3)**: everything in this repository — every agent, integration, and governance feature — is free and open source. Keys you configure in `.env` are treated as BYOK and are never gated by plans or tiers. Commercial/managed editions run this same code on the client's own infrastructure; there is no closed-source "pro" build.

**💰 Budget-friendly AI agents**: OpenCode Go subscription (~90% savings vs pay-per-token) — one $10/mo key unlocks **general-purpose models** (DeepSeek V4, Kimi K3, GLM 5.2, MiniMax M3, Qwen 3.7, Nemotron 3 Ultra, Grok 4.5) with **full tool-calling & structured output** — not just for coding, works for any agent workload. [Setup guide →](docs/guides/OPENCODE_GO_PROVIDER.md)

**No lock-in**: 16+ LLM providers (OpenAI, Anthropic, DeepSeek, Gemini, MiniMax, Groq…) with automatic cost-aware routing, fallback, and self-healing — every run makes the next run cheaper (learning router + caching tiers).

---

*Receipts: 0.027ms P99 governance checks (repo benchmark) · 616k ops/s cached throughput · 69+ documented TDD hardening rounds (~1,100 fixes in the deep security sweep alone) · 85k+ test functions (84,737 across 2,759 files, verified Aug 2026). External stats sourced in [docs/marketing/RESEARCH_NOTES.md](docs/marketing/RESEARCH_NOTES.md); copy kit in [COPY_README.md](docs/marketing/COPY_README.md) + [POSITIONING.md](docs/marketing/POSITIONING.md).*

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
                     │ Reactive only   │ Build-your-own  │ Governed by     │
                     │ Cloud-only      │ Self-hosted     │ design          │
                     │ No integrations │ Bring integrations│ 46+ native    │
                     └─────────────────┴─────────────────┴─────────────────┘
```

**Atom is the only open-source platform that delivers:**
- **Enterprise governance** (maturity tiers, HITL, audit) — without vendor lock-in
- **Calibrated autonomy & governed agent organizations** — agents know when to ask; fleets ship with delegation contracts, privilege leases, and alignment sweeps
- **Self-hosted privacy** — your data, your keys, your infrastructure
- **Autonomous agent teammates** — agents that work *with* your people, not just *for* them
- **Agent-authored workflows** — chat to build, no drag-and-drop
- **Office/Canvas native** — real Excel formulas, live co-editing
- **46+ business integrations** — Salesforce, HubSpot, Slack, Jira, Stripe, QuickBooks…

---

## 🤖 Autonomous Agents as Digital Teammates

Atom redefines the relationship between humans and AI in the workplace. Instead of a single chat assistant, your employees get a **team of autonomous digital teammates**:

| Traditional AI Assistant | Atom Autonomous Agent Teammates |
|---|---|
| Reactive — waits for commands | Proactive — handles routine work end-to-end |
| Single-threaded, no memory | Persistent memory, cross-session continuity |
| No governance, no audit | 4-tier maturity, HITL approval, full audit trail |
| One generic model per task | Specialized agents per domain (sales, finance, support, eng) |
| Human does the orchestration | Agents collaborate with each other & humans |
| Cloud-only, data leaves your infra | Self-hosted, your keys, your infrastructure |

**The vision**: Every employee gets a *personal agent team* that knows their workflows, remembers context across days/weeks, and autonomously executes the repetitive 60-80% of work — research, data entry, scheduling, drafting, reconciliation — so people can focus on judgment, creativity, and relationships.

This isn't "AI replacing humans." It's **AI handling the work humans shouldn't be doing**, with governance that keeps you in control.

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
| **🤖 Multi-Agent Orchestration** | Queen Agent (structured workflows) + Fleet Admiral (open-ended tasks) + Conductor (5 execution strategies) + validated state machine with rollback; governed fleet routing with ranked specialist matching |
| **🛡️ Governance & Safety** | 4-tier maturity (Student→Autonomous), policy-gated HITL approval, comprehensive audit trail, AI-powered training, OIDC SSO + SCIM v2 provisioning + 8-role RBAC |
| **✅ Outcome Verification** | Postcondition oracle re-derives success against the system of record — on by default, a refuted self-report is stamped UNVERIFIED (`ATOM_ORACLE_ENFORCE` kill switch); two-tier confidence provenance (self-reported vs externally verified); opt-in reviewer re-delegation loop |
| **🎚️ Trust Calibration** | Per-action allow/ask/block from a Gaussian-process posterior over verified outcomes — *ask* fails safe; relaxing autonomy requires passing a temporal-holdout certification gate (Brier ≤ 0.25, denial-coverage ≥ 0.7) and any regression auto-revokes |
| **🏛️ Agent Org Governance** | Delegation contracts with RACI accountability, default-deny expiring privilege leases, self-recruitment/conflict-of-interest detection, contribution credit feeding graduation, opt-in nightly alignment sweeps over org-dynamics telemetry |
| **🧠 Memory & Learning** | Per-turn fact extraction, 2-tier recall (SQL + LanceDB), episodic memory, `memory_remember/forget`, self-evolution (Memento/AlphaEvolver, self-evolving harness) |
| **🔎 Hybrid Search** | `documents.search` fuses BM25 (FTS5/tsvector) + vector (LanceDB) via Reciprocal Rank Fusion (RRF) — semantic + precise retrieval with citations |
| **🗂️ Knowledge VFS** | Agent-native document tree — `ls`/`cat`/`grep`/`search` with line-numbered citations instead of bespoke per-store queries |
| **📻 Agent Radio** | Lateral peer-to-peer messaging between agents (mention-first, budget-governed) — agents coordinate without hardcoded teams |
| **💼 Office Automation** | Agent-driven Excel/Word/PPTX editing on Canvas with live preview broadcast; formula-evaluating workbook runtime; agent↔document sync |
| **🧩 Mini-Apps** | Agent-authored stateful canvas apps — Firecracker microVM isolation, per-instance chat |
| **🔍 GraphRAG & Intelligence** | Multi-hop expansion, Leiden community detection, JIT fact verification, D3 visual explorer |
| **🌐 46+ Business Integrations** | Salesforce, HubSpot, Slack, Teams, Gmail, Notion, Jira, Linear, Stripe, QuickBooks, Shopify, GitHub, GitLab, Zoom… |
| **🛰️ LLM Gateway** | OpenAI/Anthropic-compatible API over your BYOK — point Claude Code, n8n, or any OpenAI-SDK app at Atom |
| **💰 Cost-Aware Routing** | 5-tier cognitive classification, 16+ providers, opt-in learning router (feedback-based re-ranking), RTK token compression |
| **🤝 Interoperability** | MCP client for external tool servers, ACP endpoint for standard agent clients, A2A Agent Card + `message/send` for agent-to-agent delegation, span tracing with optional Langfuse export |
| **🎯 Goal-Driven Loops** | Agents terminate on a `definition_of_done` predicate instead of always burning to `max_steps`; utility targets, custom action surfaces, stuck-detection |

---

## 🛡️ Production-Ready Security (Default-On)

| Layer | What you get |
|---|---|
| **Execution Sandbox** | Filesystem scope, tool whitelist, tripwires, resource caps, KillRun — enforced at every tool-dispatch hub (in-process policy checks); mini-apps run in Firecracker microVMs |
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

**To use LLM features, set one key in `backend/.env`** (or add via Settings > AI):
- `OPENCODE_API_KEY` for low-cost subscription coding models (~90% savings, recommended) or
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `GOOGLE_API_KEY` … or
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
| | [Hybrid Search](docs/architecture/AGENT_HYBRID_SEARCH.md) · [Knowledge VFS](docs/architecture/KNOWLEDGE_VFS.md) | [Personal Edition](docs/operations/personal-edition.md) |
| | [Agent Radio](docs/architecture/AGENT_RADIO.md) · [Fleet Orchestration](docs/architecture/FLEET_ORCHESTRATION.md) | [Cloud Deployment](docs/deployment/CLOUD_DEPLOYMENT.md) |
| | [Oracle Verification](docs/architecture/ORACLE_VERIFICATION.md) · [Reviewer Loop](docs/architecture/REVIEWER_LOOP.md) | [Agent Environment](docs/architecture/AGENT_ENVIRONMENT.md) |
| | [Mini-Apps Architecture](docs/architecture/MINI_APPS.md) | [Sandbox Layer](docs/architecture/SANDBOX_LAYER.md) |

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
| **Outcome verification (re-derived from system of record, not self-report)** | ✅ | ❌ | ❌ | ❌ | ❌ |
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

We welcome contributions — see [CONTRIBUTING.md](CONTRIBUTING.md). Quality bar: CI-gated core suite green, typecheck clean on changed files, review required, docs updated. See [docs/compliance/COMPLIANCE_MAPPING.md](docs/compliance/COMPLIANCE_MAPPING.md) for the security/compliance control mapping.

- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Blog**: [Substack](https://substack.com/@rish2atom/posts)
- **License**: AGPL v3 — [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [FastAPI](https://fastapi.tiangolo.com/) **|** [SQLAlchemy](https://www.sqlalchemy.org/) **|** [LangChain](https://langchain.com/) **|** [Playwright](https://playwright.dev/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation — safe enough for your whole team.**

⭐ Star us on GitHub — it helps!

</div>