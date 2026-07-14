<div align="center">

# ATOM Platform
### Open-Source AI Agent Platform for Self-Hosted Automation

> **Developer Note**: For technical setup and architecture, see [docs/development/overview.md](docs/development/overview.md).

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/rush86999/atom/ci.yml?branch=main&label=CI)](https://github.com/rush86999/atom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-204%2B-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Stars](https://img.shields.io/github/stars/rush86999/atom?style=social)]()

</div>

## What is Atom?

Atom is an **open-source, self-hosted AI agent platform** that combines visual workflow builders with intelligent LLM-based agents.

Just **speak** or **type** your request, and Atom's specialty agents will plan, verify, and execute complex workflows across your entire tech stack.

**Key Difference**: Atom is self-hosted — your workflow data, agent state, and memory stay on your infrastructure. LLM inference uses your own API keys (BYOK) with cloud providers (OpenAI, Anthropic, DeepSeek); local model support (Ollama, Llama.cpp) is available for fully private deployments.

> **Comparing alternatives?** See [Atom vs OpenClaw](docs/features/atom-vs-openclaw.md) for a detailed feature comparison.

---

## Atom vs OpenClaw: Quick Comparison

| Aspect | Atom | OpenClaw |
|--------|------|----------|
| **Best For** | Business automation, multi-agent workflows | Personal productivity, messaging workflows |
| **Agent Model** | Multi-agent system with specialty agents | Single-agent runtime |
| **Governance** | ✅ 4-tier maturity (Student → Autonomous) | ❌ No maturity levels |
| **Memory** | ✅ Episodic memory + per-turn fact extraction + agent memory tools | ✅ Persistent Markdown files |
| **Integrations** | 46+ business (CRM, support, dev tools) | 50+ personal (smart home, media, messaging) |
| **Office Automation** | ✅ Real-time Excel/Word/PPTX co-editing on Canvas | ❌ None |
| **Architecture** | Python + FastAPI + PostgreSQL/SQLite | Node.js + local filesystem |
| **Setup** | Docker Compose (~15-30 min) | Single script (~10-30 min) |

[Full Comparison →](docs/features/atom-vs-openclaw.md)

---

## Atom vs Hermes Agent: Quick Comparison

Hermes (Nous Research) is an open-source personal agent known for its memory-provider architecture. Atom adopted its strongest ideas (per-turn fact extraction, pre-compression hooks, circuit breaker, FTS5 search) and deliberately avoided its weakest (custom LLM-summarizing compressor — Hermes' own has 3 documented production bugs).

| Aspect | Atom | Hermes Agent |
|--------|------|--------------|
| **Best For** | Business automation, governed multi-agent workflows | Personal coding/productivity assistant |
| **Memory extraction** | ✅ Per-turn durable-fact extraction (5 categories, Mem0 taxonomy) | ✅ Memory-provider ABC with 7 hooks (reference design) |
| **Context compression** | ✅ Boundary protection + tool-pair sanitization (deterministic only) | ◐ 4-phase compressor incl. LLM summary (3 documented bugs) |
| **Agent memory tools** | ✅ `memory_remember` / `memory_forget` (maturity-gated) | ✅ `lancedb_remember` / `mem0_*` tool family |
| **Governance** | ✅ 4-tier maturity (Student → Autonomous) + HITL supervision | ❌ None |
| **Multi-agent** | ✅ Queen + Fleet Admiral + specialty agents | ❌ Single agent loop |
| **Canvas / rich UI** | ✅ 7 canvas types, WebSocket, a11y | ❌ Terminal + messaging |
| **Office Automation** | ✅ Real-time Excel/Word/PPTX co-editing on Canvas | ❌ None |
| **Cost routing** | ✅ 5-tier cognitive classification | ◐ Aux-model only |
| **Observability** | ✅ Prometheus + `/health/*` + structlog | ❌ WARNING logs |
| **Retrieval** | Tier-1 SQL + Tier-2 vector + FTS5 lexical | Vector + BM25 hybrid + cross-encoder reranker |
| **Circuit breaker** | ✅ 5 failures → 120s cooldown → half-open probe | ✅ 2-min/5-failure (fixed window) |
| **Deployment** | Python + FastAPI + SQLite/PostgreSQL + embedded LanceDB | Python self-hosted + embedded LanceDB |

[Full Comparison →](docs/architecture/HERMES_COMPARISON.md) · [Context Memory Design →](docs/architecture/CONTEXT_MEMORY.md)

---


---

## Architecture

### Single-Tenant Deployment

Atom is designed for **self-hosted deployment**:

- **Simpler Setup**: No tenant isolation, no subdomain routing
- **Better Performance**: Direct database access without overhead
- **Self-Hosted**: Agent state, memory, and workflow data stay on your infrastructure. LLM prompts are sent to your configured API provider (BYOK). Use local models (Ollama/Llama.cpp) for fully private setups.
- **Unlimited Usage**: No subscription fees or quota limits

**Key Features:**
- Uses `user_id` for user identification
- No billing system or quota enforcement
- Fleet recruitment limited by system resources only
- All governance, routing, and graduation features work identically

Full Architecture Guide →

### Data Flow & Privacy

Understanding where your data goes:

| Component | Where Data Goes | Configurable? |
|-----------|----------------|---------------|
| **LLM inference** (chat, reasoning, agent decisions) | Cloud API provider via your BYOK keys (OpenAI, Anthropic, DeepSeek) | ✅ Use local models (Ollama, Llama.cpp) for fully private |
| **Embeddings** (document vectors) | Local (FastEmbed, ONNX runtime) | Always local |
| **Vector storage** (episodic memory) | Local (LanceDB on disk) | Always local |
| **Database** (agents, users, workflows) | Local (SQLite) or your PostgreSQL server | Always your infra |
| **File uploads** | Local filesystem (`./data/`) | Always your infra |
| **Integration data** (Slack, Gmail, etc.) | Third-party APIs per integration | Per-integration |

> **For maximum privacy**: Set `ATOM_LOCAL_ONLY=true` (blocks cloud integrations) AND configure local LLM models (Ollama/Llama.cpp) instead of cloud API keys.

### Meta-Agent Routing ✨
Intelligent CHAT/WORKFLOW/TASK routing with governance checks and dynamic fleet recruitment

[Meta-Agent Guide →](docs/agents/meta-agent.md)

---

## Quick Start

The fastest path to a running local server (verified working June 2026):

```bash
git clone https://github.com/rush86999/atom.git
cd atom

# Backend deps in a venv
cd backend
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt

# Frontend deps
cd ../frontend-nextjs
npm install --legacy-peer-deps
cd ..

# Configure (DATABASE_URL, SECRET_KEY, at least one LLM key)
cp backend/.env.example backend/.env
# Edit backend/.env — generate SECRET_KEY with: openssl rand -base64 48

# Launch backend (FROM REPO ROOT — main.py uses backend.* imports)
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main:app --reload --port 8000

# In a second terminal: frontend
cd frontend-nextjs && npm run dev
```

- **Frontend (UI)**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API docs (Swagger)**: http://localhost:8000/docs
- **Admin password**: auto-generated at `backend/logs/bootstrap_admin_password.txt` (mode 0600)

That's it! 🚀

**Choose your edition:**
- **Personal Edition** (default) — Free, single-user, SQLite, zero external services
- **Enterprise Edition** — Multi-user, PostgreSQL, monitoring (set `DATABASE_URL` to a Postgres DSN)

For alternative paths (Docker, DigitalOcean 1-click) and the full walkthrough, see:
- **[Quick Start (verified)](docs/getting_started/quick-start.md)** ⭐ — step-by-step with troubleshooting
- **[First Steps after install](docs/getting_started/FIRST_STEPS.md)** — what to do once the server is running
- **[Troubleshooting](docs/getting_started/TROUBLESHOOTING.md)** — common errors and fixes
- **[Full Installation Guide](docs/getting_started/INSTALLATION.md)** — all installation variants
- **[Development Setup](docs/development/DEVELOPMENT_SETUP.md)** — for contributors

---

## Key Features

### 🎙️ Voice Interface
- Build complex workflows using just your voice
- Natural language understanding — no proprietary syntax
- Real-time feedback as Atom visualizes its reasoning

### 🤖 Specialty Agents & Orchestration ✨ Enhanced 2026
- **Sales, Marketing, Engineering**: CRM pipelines, campaigns, deployments, incidents
- **Hive Orchestration**: Queen Agent (structured workflows) and FleetAdmiral (dynamic recruitment)
- **Conductor Agent**: 5 execution strategies (SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE)
- **Workflow State Machine**: Validated transitions with automatic rollback
- **Event Bus**: Event-driven workflow triggering with pub/sub
- **Self-Evolving Capabilities**: Memento Skills learns from failures, AlphaEvolver optimizes via mutation

[Queen Agent →](docs/agents/QUEEN_AGENT.md) | [Auto-Dev →](docs/guides/AUTO_DEV_USER_GUIDE.md)

### 🎨 Canvas Presentations & Real-Time Guidance ✨
Rich interactive presentations (charts, forms, markdown) with live operation visibility, multi-view orchestration, smart error resolution, and AI accessibility (canvas state exposed to agents)

[Canvas Guide →](docs/archive/implementation/CANVAS_IMPLEMENTATION_COMPLETE.md)

### 💼 Office Automation & Document Co-Editing ✨
- **Real-Time Collaboration**: Co-edit Excel spreadsheets, Word documents, and PowerPoint presentations directly on the interactive Canvas.
- **AI-Driven Office Workflows**: Automate document generation, spreadsheet analysis, formatting, and reporting through voice or chat.
- **Agent Integration**: Full synchronization between agent actions and document state for autonomous office task execution.

[Office Automation Guide →](docs/guides/ATOM_OFFICE_AUTOMATION_GUIDE.md)

### 🧠 Autonomous Self-Evolution & Graduation ✨
Experience-based learning with recursive self-evolution, dual-trigger graduation (SUPERVISED → AUTONOMOUS), and hybrid PostgreSQL + LanceDB storage

[Agent Graduation Guide →](docs/archive/legacy/AGENT_GRADUATION_GUIDE.md)

### 💾 Memory & Context (Hermes-style) ✨ New 2026
Durable-fact extraction layer that survives context compression — the agent remembers what matters across sessions:
- **Per-turn extraction**: 5 durable-fact categories (exact values, hard constraints, decision reasoning, cross-task deps, implicit preferences) extracted fire-and-forget after each ReAct step
- **Two-tier recall**: Tier-1 pure-SQL `DURABLE FACTS` prompt block (sub-ms) + Tier-2 LanceDB semantic recall (opt-in) + FTS5 lexical fallback for exact-match queries
- **Agent memory tools**: `memory_remember` / `memory_forget` let the agent explicitly persist or invalidate facts mid-turn (maturity-gated, deletion-safe)
- **Pre-compression queue**: drains prompts before truncation drops facts (strictly additive, default ON)
- **Circuit breaker**: 5 failures → 120s cooldown → half-open probe (prevents extraction storms)
- **Boundary-protection compression**: head + tail preserved, stale middle elided (deterministic; no buggy LLM-summary phase)

[Context Memory Design →](docs/architecture/CONTEXT_MEMORY.md) · [Atom vs. Hermes →](docs/architecture/HERMES_COMPARISON.md)

### 🛡️ Agent Governance System ✨ Enhanced 2026
- **4-tier maturity**: Student → Intern → Supervised → Autonomous
- **Three-layer governance**: OPERATIONAL (<10ms), TACTICAL (<100ms), STRATEGIC (human-in-the-loop)
- **Policy engine**: Context-aware evaluation with priority resolution
- **AI-powered training**: Duration estimation with historical data
- **Complete audit trail**: Every action logged, timestamped, and traceable

[Governance Documentation →](docs/governance/) | [Enhancement Plan →](archive/root_files/ATOM_ENHANCEMENT_PLAN.md)

### 🔌 Deep Integrations
- **46+ business integrations**: Slack, Gmail, HubSpot, Salesforce, Zendesk
- **9 messaging platforms**: Real-time communication
- **Marketplace Connection**: Access 5,000+ community skills and agent templates ✨ NEW
- Use `/run`, `/workflow`, `/agents` from your favorite chat app

### 🔍 Knowledge Graph & GraphRAG ✨ Enhanced 2026
Recursive knowledge retrieval via BFS traversal, canonical anchoring to database records, bidirectional sync, and D3-powered visual explorer
- **Multi-Hop Expansion**: Cue-driven activation for entity relationships — wired into the production `local_search` path (scored, prioritized multi-hop paths via `SQLMultiHopExpander`)
- **Dynamic Graph Construction**: Incremental updates without full rebuilds
- **Enhanced Community Detection**: Leiden algorithm clustering (with Louvain fallback) — wired into `GraphRAGEngine.build_communities`, populating the `graph_communities` table for global search

[GraphRAG Documentation →](docs/intelligence/graphrag.md)

### 🌐 Community Skills & Package Marketplace ✨
5,000+ OpenClaw/ClawHub skills with PostgreSQL marketplace, LLM-powered security scanning (21+ malicious patterns), DAG skill composition, Python + npm auto-installation with vulnerability scanning, and supply chain protection

[Community Skills Guide →](docs/integrations/community-skills.md) | [Python Packages →](docs/security/python-packages.md) | [npm Packages →](docs/security/npm-packages.md)

### 🔍 Browser & Device Automation
- Browser automation via CDP (scraping, form filling)
- Device control (camera, location, notifications)
- Maturity-governed for security
- **Pre-action match-confidence** ✨ — selectors scored `high/partial/ambiguous` before clicking; partial/ambiguous route through human review even for AUTONOMOUS agents. See [Match-Confidence Layer](docs/architecture/MATCH_CONFIDENCE.md)

---

## 🚀 2026 Enhancement Plan

Based on cutting-edge 2025-2026 AI research, Atom has been enhanced with 5 major feature phases:

**Phase 1: Memory & Graduation** ✅ Complete
- POMDP memory framework for experience-driven learning
- Offline memory consolidation (inspired by human sleep)
- Quality-weighted graduation criteria (20% improvement)

**Phase 2: GraphRAG Enhancement** ✅ Complete
- Multi-hop expansion with cue-driven activation
- Dynamic graph construction (incremental updates)
- Enhanced community detection (Leiden algorithm)

**Phase 3: Learning-Based LLM Routing** ✅ Complete
- Per-model satisfaction predictors that re-rank BPC candidates from observed outcomes
- DB-persisted feedback (`llm_routing_feedback`), live `/api/chat/feedback`, quality signals
- Model visibility badge on chat responses + routing dashboard at `/settings/routing`
- Flag-gated (`ATOM_LEARNING_ROUTER`, default off) — augments, doesn't replace, the Cognitive Tier System
- See [docs/architecture/LEARNING_LLM_ROUTER.md](docs/architecture/LEARNING_LLM_ROUTER.md)

**Phase 4: Zero-Trust Federation Identity** ✅ Complete
- DID (Decentralized Identifiers) for cryptographic identity — reachable via `POST /api/federation/dids`
- Verifiable Credentials (VCs) for signed claims — reachable via `POST /api/federation/credentials`
- Zero-trust security framework with per-request verification — reachable via `POST /api/federation/verify`
- Automatic credential rotation (90-day)
- Note: identity/federation state is in-memory (resets on restart); DB persistence is a documented follow-up

**Phase 5: Enhanced Orchestration Patterns** ✅ Complete
- Conductor Agent (5 execution strategies: SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE) — wired into the live workflow engine; reachable via `POST /api/v1/workflows/conductor/execute`
- Workflow State Machine (validated transitions with rollback)
- Event Bus (pub/sub event-driven triggering) — every live workflow publishes lifecycle events (WORKFLOW_STARTED/STEP_STARTED/STEP_COMPLETED/STEP_FAILED/WORKFLOW_COMPLETED)
- Workflow Templates & Composition (9 primitives: SEQUENCE, PARALLEL, CHOICE, MERGE, SPLIT, JOIN, LOOP, TRY_CATCH, COMPENSATE)

**Performance**: 27,000+ tests across unit, integration, E2E, and regression suites; comprehensive validation metrics documented

[Enhancement Plan →](archive/root_files/ATOM_ENHANCEMENT_PLAN.md) | [Validation Metrics →](backend/docs/VALIDATION_METRICS.md)

---

## Installation Options

### 🐳 Docker (5 minutes)
```bash
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env
docker-compose -f docker-compose-personal.yml up -d
```

### 🚀 DigitalOcean (1-Click Deploy)
Launch Atom on DigitalOcean App Platform with one click:

[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

[See Cloud Deployment Guide →](docs/deployment/CLOUD_DEPLOYMENT.md)

### 💻 Native (10 minutes)
```bash
git clone https://github.com/rush86999/atom.git
cd atom
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ../frontend-nextjs && npm install
cp .env.personal .env
# Start backend: cd backend && python -m uvicorn main_api_app:app --reload
# Start frontend: cd frontend-nextjs && npm run dev
```

---

## Marketplace (Commercial Service)

Commercial marketplace for agents, domains, components, and skills at [atomagentos.com](https://atomagentos.com). Requires API token connection. Core platform is AGPL v3 (open source), marketplace items are proprietary. See [LICENSE.md](LICENSE.md#marketplace-commercial-appendix) for terms.

**Setup**: Add `ATOM_SAAS_API_TOKEN` to `.env` and restart. [Marketplace Documentation →](docs/marketplace/)

---

## Example Use Cases

| **Department** | **Scenario** |
|----------------|-------------|
| **Sales** | New lead in HubSpot → Research → Score → Notify Slack |
| **Finance** | PDF invoice in Gmail → Extract → Match QuickBooks → Flag discrepancies |
| **Support** | Zendesk ticket → Analyze sentiment → Route urgent → Draft response |
| **HR** | New employee in BambooHR → Provision → Invite → Schedule orientation |

---

## Security & Privacy

Self-hosted deployment, BYOK (OpenAI/Anthropic/Gemini/DeepSeek/MiniMax), encrypted storage (Fernet), audit logs, human-in-the-loop approvals, package security scanning, supply chain protection, **5-phase execution sandbox layer** (filesystem scope, tool whitelist, tripwires, Firecracker microVM isolation, dual-proxy egress, resource caps, KillRun, provenance tagging, LLM ActionJudge — Rounds 43-47), comprehensive testing (27,000+ tests across unit, integration, E2E, and regression suites), AI-enhanced bug discovery, and stress testing

[Security Documentation →](docs/security/) | [Sandbox Layer →](docs/architecture/SANDBOX_LAYER.md) | [Testing Guide →](backend/tests/e2e_ui/README.md)

---

## Documentation

### User Guides ⭐
- **[User Guide Index](docs/USER_GUIDE_INDEX.md)** - Complete user documentation (START HERE)
- [Quick Start Guide](docs/getting_started/quick-start.md) - Get started in 15 minutes
- [User Guide](docs/guides/USER_GUIDE.md) - Core features and daily workflows

### Core Features
- [Agent System](docs/agents/overview.md) - Multi-agent governance and orchestration
- [Community Skills Guide](docs/integrations/community-skills.md) - 5,000+ skills with Python & npm packages
- [Office Automation & Co-Editing](docs/guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) - Real-time Excel/Word/PPTX co-editing on Canvas ✨ NEW
- [Python Package Support](docs/security/python-packages.md) - NumPy, Pandas, 350K+ packages
- [npm Package Support](docs/security/npm-packages.md) - Lodash, Express, 2M+ packages
- [Episodic Memory](docs/intelligence/episodic-memory.md) - Agent learning system
- [Agent Graduation](docs/agents/graduation.md) - Promotion framework
- [Student Training](docs/agents/training.md) - Maturity routing

### Testing & Quality ✨ NEW
- [Quality Assurance Guide](docs/testing/QUALITY_ASSURANCE.md) - Comprehensive QA practices and standards
- [Quality Metrics Dashboard](docs/testing/QUALITY_DASHBOARD.md) - Live quality metrics and trends
- [Bug Fix Process](docs/testing/BUG_FIX_PROCESS.md) - TDD-based bug fixing workflow
- [Coverage Report Guide](docs/testing/COVERAGE_REPORT_GUIDE.md) - Coverage measurement and improvement
- [E2E Testing Guide](backend/tests/e2e_ui/README.md) - 91+ comprehensive end-to-end tests
- [Bug Discovery Infrastructure](docs/testing/BUG_DISCOVERY_INFRASTRUCTURE.md) - AI-enhanced bug discovery
- [Test Quality Standards](docs/testing/TEST_QUALITY_STANDARDS.md) - Testing best practices
- Cross-Platform Testing - Mobile/desktop testing

### Platform
- [Development Guide](docs/development/overview.md) - Technical setup
- [Installation Guide](docs/getting_started/INSTALLATION.md) - Complete instructions
- [Atom vs OpenClaw](docs/features/atom-vs-openclaw.md) - Feature comparison

### Advanced
- [Canvas Reference](docs/canvas/reference.md) - Canvas operations
- [Agent Governance](docs/agents/governance.md) - Maturity levels and permissions
- [Meta-Agent Routing](docs/agents/meta-agent.md) - Intent classification and fleet recruitment
- [Personal Edition](docs/operations/personal-edition.md) - Local deployment

**[Complete Documentation Index →](docs/INDEX.md)** | **[Reorganization Plan →](docs/archive/plans/DOCUMENTATION_REORGANIZATION_PLAN.md)**

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quality Standards

All contributions must meet quality standards:
1. **Tests pass (100% pass rate)** - All tests must pass before merge
2. **Coverage adequate (≥70%)** - New code must have test coverage
3. **Code reviewed** - At least one approval required
4. **Documentation updated** - Update docs for new features

See [Quality Assurance Guide](docs/testing/QUALITY_ASSURANCE.md) for details.

---

## Support

- **Documentation**: [docs/INDEX.md](docs/INDEX.md) - Complete index
- **Developer Guide**: [docs/development/overview.md](docs/development/overview.md) - Setup
- **User Guide Index**: [docs/USER_GUIDE_INDEX.md](docs/USER_GUIDE_INDEX.md) - User documentation
- **Blog**: [Substack](https://substack.com/@rish2atom/posts) - Latest updates & insights
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **License**: AGPL v3 - [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [FastAPI](https://fastapi.tiangolo.com/) **|** [SQLAlchemy](https://www.sqlalchemy.org/) **|** [LangChain](https://langchain.com/) **|** [Playwright](https://playwright.dev/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation.**

⭐ Star us on GitHub — it helps!

</div>