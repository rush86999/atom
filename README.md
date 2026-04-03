<div align="center">

# ATOM Platform
### Open-Source AI Agent Platform for Self-Hosted Automation

> **Developer Note**: For technical setup and architecture, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

</div>

## What is Atom?

Atom is an **open-source, self-hosted AI agent platform** that combines visual workflow builders with intelligent LLM-based agents.

Just **speak** or **type** your request, and Atom's specialty agents will plan, verify, and execute complex workflows across your entire tech stack.

**Key Difference**: Unlike SaaS alternatives, Atom runs entirely on your infrastructure. Your data never leaves your environment.

> **Note**: This is the open-source version of Atom with single-tenant deployment. For multi-tenant SaaS features (billing, quotas, tenant isolation), see [atom-saas](https://github.com/rush86999/atom-saas). See [SINGLE_TENANT.md](SINGLE_TENANT.md) for architecture details.

> **Comparing alternatives?** See [Atom vs OpenClaw](docs/ATOM_VS_OPENCLAW.md) for a detailed feature comparison.

---

## Atom vs OpenClaw: Quick Comparison

| Aspect | Atom | OpenClaw |
|--------|------|----------|
| **Best For** | Business automation, multi-agent workflows | Personal productivity, messaging workflows |
| **Agent Model** | Multi-agent system with specialty agents | Single-agent runtime |
| **Governance** | ✅ 4-tier maturity (Student → Autonomous) | ❌ No maturity levels |
| **Memory** | ✅ Episodic memory with graduation validation | ✅ Persistent Markdown files |
| **Integrations** | 46+ business (CRM, support, dev tools) | 50+ personal (smart home, media, messaging) |
| **Architecture** | Python + FastAPI + PostgreSQL/SQLite | Node.js + local filesystem |
| **Setup** | Docker Compose (~15-30 min) | Single script (~10-30 min) |

[Full Comparison →](docs/ATOM_VS_OPENCLAW.md)

---

## Quick Start

```bash
# Install Atom
pip install atom-os

# Initialize
atom init

# Add your API keys to .env
# OPENAI_API_KEY=sk-...
# MINIMAX_API_KEY=...  (optional, for MiniMax M2.7 support)

# Start Atom
atom start

# Open dashboard
open http://localhost:8000
```

That's it! 🚀

**Choose your edition:**
- **Personal Edition** - Free, single-user, SQLite (default)
- **Enterprise Edition** - Multi-user, PostgreSQL, monitoring → `pip install atom-os[enterprise]`

[Full Installation Guide →](docs/INSTALLATION.md)

---

## Key Features

### 🎙️ Voice Interface
- Build complex workflows using just your voice
- Natural language understanding — no proprietary syntax
- Real-time feedback as Atom visualizes its reasoning

### 🤖 Specialty Agents
- **Sales Agent**: CRM pipelines, lead scoring, outreach
- **Marketing Agent**: Campaigns, social posting, analytics
- **Engineering Agent**: PR notifications, deployments, incidents
- **Hive Orchestration**: Autonomous multi-agent coordination with **Queen** (Architectural Design) and **King** (Execution Orchestration). ✨ NEW
- **Intelligent request routing**: Automatic intent classification to route requests to the most capable specialty agent. ✨ NEW
- **Autonomous Workflow Realization**: Convert natural language requests into persistent, executable blueprints via the Queen Agent. ✨ NEW
- **Meta-Agent Routing**: Governance-gated routing with CHAT/WORKFLOW/TASK intent classification and auto-takeover proposal mode. ✨ NEW (v13.0)
- **Dynamic Fleet Recruitment**: FleetAdmiral automatically recruits specialist agents based on task requirements. ✨ NEW (v13.0)
- **Governance**: Progress from "Student" to "Autonomous" as they gain trust

### 🎨 Canvas Presentations & Real-Time Guidance ✨
- Rich interactive presentations (charts, forms, markdown)
- **Live operation visibility**: See exactly what agents are doing
- Multi-view orchestration (browser, terminal, canvas)
- Smart error resolution with actionable suggestions
- [Full Details →](docs/CANVAS_IMPLEMENTATION_COMPLETE.md)

### 🧠 Autonomous Self-Evolution & Graduation ✨ NEW
- **Experience-based learning**: Agents store and retrieve past experiences using the Reflection Pool.
- **Recursive Self-Evolution**: Autonomous critique-based optimization loop (optimized for MiniMax M2.7).
- **Dual-Trigger Graduation**: Skills progress from `SUPERVISED` to `AUTONOMOUS` via post-task event hooks and background audits.
- **Dynamic Streak Rule**: Promotion based on "Clean Run" streaks (Success + No Intervention + High Compliance).
- **Hybrid storage**: PostgreSQL for state + LanceDB for mistake memory.
- [Agent Graduation Guide →](docs/AGENT_GRADUATION_GUIDE.md)

### 🛡️ Agent Governance System
- 4-tier maturity-based routing and approval system
- AI-powered training duration estimation
- Every action logged, timestamped, and traceable

### 🔌 Deep Integrations
- **46+ business integrations**: Slack, Gmail, HubSpot, Salesforce, Zendesk
- **9 messaging platforms**: Real-time communication
- **Atom SaaS Sync**: Bidirectional sync with Atom marketplace for skills and ratings ✨ NEW
- Use `/run`, `/workflow`, `/agents` from your favorite chat app

### 🔍 Knowledge Graph & GraphRAG ✨ NEW
- **Recursive Knowledge Retrieval**: Higher-order reasoning via BFS graph traversal.
- **Canonical Anchoring**: Link graph nodes to concrete database records (Users, Tickets, Formulas).
- **Bidirectional Sync**: Update entity metadata directly from the Graph UI.
- **Visual Explorer**: Interactive D3-powered graph visualization at `/graph`.
- [GraphRAG Documentation →](docs/GRAPHRAG_PORTED.md)

### 🌐 Community Skills & Package Marketplace ✨
- **5,000+ OpenClaw/ClawHub skills**: Import community-built tools
- **Skill Marketplace**: PostgreSQL-based with search, ratings, categories
- **Enterprise security**: LLM-powered scanning (21+ malicious patterns) with hazard sandbox
- **Skills Registry**: Import with status tracking (Untrusted → Active → Banned)
- **Dynamic Skill Loading**: importlib-based hot-reload with watchdog monitoring
- **Skill Composition**: DAG workflows with parallel execution and rollback
- **Auto-Installation**: Python + npm with conflict detection and automatic rollback
- **Python Package Support**: NumPy, Pandas, 350K+ PyPI packages with vulnerability scanning
- **npm Package Support**: Lodash, Express, 2M+ npm packages with governance
- **Supply Chain Security**: Typosquatting detection, dependency confusion prevention, postinstall malware blocking
- [Community Skills Guide →](docs/COMMUNITY_SKILLS.md)

### 🔍 Browser & Device Automation
- Browser automation via CDP (scraping, form filling)
- Device control (camera, location, notifications)
- Maturity-governed for security

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

[See Cloud Deployment Guide →](docs/DEPLOYMENT/CLOUD_DEPLOYMENT.md)

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

## Example Use Cases

| **Department** | **Scenario** |
|----------------|-------------|
| **Sales** | New lead in HubSpot → Research → Score → Notify Slack |
| **Finance** | PDF invoice in Gmail → Extract → Match QuickBooks → Flag discrepancies |
| **Support** | Zendesk ticket → Analyze sentiment → Route urgent → Draft response |
| **HR** | New employee in BambooHR → Provision → Invite → Schedule orientation |

---

## Security & Privacy

- **Self-Hosted Only**: Your data never leaves your environment
- **BYOK**: Bring your own OpenAI, Anthropic, Gemini, DeepSeek, or MiniMax keys
- **Encrypted Storage**: Sensitive data encrypted at-rest (Fernet)
- **Audit Logs**: Every agent action logged and traceable
- **Human-in-the-Loop**: Configurable approval policies
- **Package Security**: Vulnerability scanning (pip-audit, Safety), postinstall script blocking, container isolation
- **Supply Chain Protection**: Typosquatting detection, dependency confusion prevention, malicious pattern detection
- **Comprehensive Testing**: 495+ tests with 99%+ pass rate, E2E validation with real services ✨
- **AI-Enhanced Bug Discovery**: Automated fuzzing, property-based testing, chaos engineering ✨ NEW
- **Stress Testing**: Load testing with k6 (10/50/100 concurrent users), network simulation, failure injection ✨ NEW

---

## Documentation

### Core
- [Community Skills Guide](docs/COMMUNITY_SKILLS.md) - 5,000+ skills with Python & npm packages
- [Python Package Support](docs/PYTHON_PACKAGES.md) - NumPy, Pandas, 350K+ packages
- [npm Package Support](docs/NPM_PACKAGE_SUPPORT.md) - Lodash, Express, 2M+ packages ✨ NEW
- [Episodic Memory](docs/EPISODIC_MEMORY_IMPLEMENTATION.md) - Learning system
- [Agent Graduation](docs/AGENT_GRADUATION_GUIDE.md) - Promotion framework
- [Student Training](docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Maturity routing

### Testing & Quality ✨ NEW
- [E2E Testing Guide](backend/tests/e2e_ui/README.md) - 91+ comprehensive end-to-end tests
- [Bug Discovery Infrastructure](backend/docs/BUG_DISCOVERY_INFRASTRUCTURE.md) - AI-enhanced bug discovery
- [Test Quality Standards](backend/docs/TEST_QUALITY_STANDARDS.md) - Testing best practices
- [Cross-Platform Testing](.planning/phases/236-cross-platform-and-stress-testing/236-VERIFICATION.md) - Mobile/desktop testing

### Platform
- [Development Guide](docs/DEVELOPMENT.md) - Technical setup
- [Installation Guide](docs/INSTALLATION.md) - Complete instructions
- [Atom vs OpenClaw](docs/ATOM_VS_OPENCLAW.md) - Feature comparison

### Advanced
- [Canvas Implementation](docs/CANVAS_IMPLEMENTATION_COMPLETE.md) - Canvas details
- [Agent Governance](docs/AGENT_GOVERNANCE.md) - Maturity levels
- [Personal Edition](docs/PERSONAL_EDITION.md) - Local deployment
- [IM Adapter Setup](backend/docs/IM_ADAPTER_SETUP.md) - Messaging integration

**[Complete Documentation Index →](docs/INDEX.md)**

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Support

- **Documentation**: [docs/INDEX.md](docs/INDEX.md) - Complete index
- **Developer Guide**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Setup
- **Implementation History**: [docs/IMPLEMENTATION_HISTORY.md](docs/IMPLEMENTATION_HISTORY.md) - Recent changes
- **Blog**: [Substack](https://substack.com/@rish2atom/posts) - Latest updates & insights
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **License**: AGPL v3 - [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [ActivePieces](https://www.activepieces.com/) **|** [LangChain](https://langchain.com/) **|** [FastAPI](https://fastapi.tiangolo.com/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation.**

⭐ Star us on GitHub — it helps!

</div>