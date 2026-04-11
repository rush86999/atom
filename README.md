<div align="center">

# ATOM Platform
### Open-Source AI Agent Platform for Self-Hosted Automation

> **Developer Note**: For technical setup and architecture, see [docs/development/overview.md](docs/development/overview.md).

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

</div>

## What is Atom?

Atom is an **open-source, self-hosted AI agent platform** that combines visual workflow builders with intelligent LLM-based agents.

Just **speak** or **type** your request, and Atom's specialty agents will plan, verify, and execute complex workflows across your entire tech stack.

**Key Difference**: Atom runs entirely on your infrastructure. Your data never leaves your environment.

> **Comparing alternatives?** See [Atom vs OpenClaw](docs/features/atom-vs-openclaw.md) for a detailed feature comparison.

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

[Full Comparison →](docs/features/atom-vs-openclaw.md)

---


---

## Architecture

### Single-Tenant Deployment

Atom is designed for **self-hosted deployment**:

- **Simpler Setup**: No tenant isolation, no subdomain routing
- **Better Performance**: Direct database access without overhead
- **Self-Hosted**: Your data never leaves your infrastructure
- **Unlimited Usage**: No subscription fees or quota limits

**Key Features:**
- Uses `user_id` for user identification
- No billing system or quota enforcement
- Fleet recruitment limited by system resources only
- All governance, routing, and graduation features work identically

[Full Architecture Guide →](docs/SINGLE_TENANT.md)

### Meta-Agent Routing ✨
Intelligent CHAT/WORKFLOW/TASK routing with governance checks and dynamic fleet recruitment

[Meta-Agent Guide →](docs/agents/meta-agent.md)

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

# (Optional) Connect to marketplace for commercial specialty skills
# MARKETPLACE_API_TOKEN=at_saas_your_token  # Get from https://atomagentos.com


# Start Atom
atom start

# Open dashboard
open http://localhost:8000
```

That's it! 🚀

**[Optional: Connect to Marketplace →](#marketplace-connection-new)**

**Choose your edition:**
- **Personal Edition** - Free, single-user, SQLite (default)
- **Enterprise Edition** - Multi-user, PostgreSQL, monitoring → `pip install atom-os[enterprise]`

[Full Installation Guide →](docs/getting-started/installation.md)

---

## Key Features

### 🎙️ Voice Interface
- Build complex workflows using just your voice
- Natural language understanding — no proprietary syntax
- Real-time feedback as Atom visualizes its reasoning

### 🤖 Specialty Agents
- **Sales, Marketing, Engineering**: CRM pipelines, campaigns, deployments, incidents
- **Hive Orchestration**: Queen Agent (architectural design) and FleetAdmiral (dynamic specialist recruitment)
- **Self-Evolving Capabilities**: Memento Skills learns from failures, AlphaEvolver optimizes via mutation ✨ NEW
- **Governance**: Progress from "Student" to "Autonomous" as they gain trust

[Special Agents Guide →](docs/agents/special-agents.md) | [Queen Agent →](docs/QUEEN_AGENT.md) | [Auto-Dev →](docs/GUIDES/AUTO_DEV_USER_GUIDE.md)

### 🎨 Canvas Presentations & Real-Time Guidance ✨
Rich interactive presentations (charts, forms, markdown) with live operation visibility, multi-view orchestration, smart error resolution, and AI accessibility (canvas state exposed to agents)

[Canvas Guide →](docs/CANVAS_IMPLEMENTATION_COMPLETE.md)

### 🧠 Autonomous Self-Evolution & Graduation ✨
Experience-based learning with recursive self-evolution, dual-trigger graduation (SUPERVISED → AUTONOMOUS), and hybrid PostgreSQL + LanceDB storage

[Agent Graduation Guide →](docs/AGENT_GRADUATION_GUIDE.md)

### 🛡️ Agent Governance System
- 4-tier maturity-based routing and approval system
- AI-powered training duration estimation
- Every action logged, timestamped, and traceable

### 🔌 Deep Integrations
- **46+ business integrations**: Slack, Gmail, HubSpot, Salesforce, Zendesk
- **9 messaging platforms**: Real-time communication
- **Marketplace Connection**: Access 5,000+ community skills and agent templates ✨ NEW
- Use `/run`, `/workflow`, `/agents` from your favorite chat app

### 🔍 Knowledge Graph & GraphRAG ✨
Recursive knowledge retrieval via BFS traversal, canonical anchoring to database records, bidirectional sync, and D3-powered visual explorer

[GraphRAG Documentation →](docs/GRAPHRAG_PORTED.md)

### 🌐 Community Skills & Package Marketplace ✨
5,000+ OpenClaw/ClawHub skills with PostgreSQL marketplace, LLM-powered security scanning (21+ malicious patterns), DAG skill composition, Python + npm auto-installation with vulnerability scanning, and supply chain protection

[Community Skills Guide →](docs/COMMUNITY_SKILLS.md) | [Python Packages →](docs/security/python-packages.md) | [npm Packages →](docs/security/npm-packages.md)

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

Self-hosted deployment, BYOK (OpenAI/Anthropic/Gemini/DeepSeek/MiniMax), encrypted storage (Fernet), audit logs, human-in-the-loop approvals, package security scanning, supply chain protection, comprehensive testing (495+ tests), AI-enhanced bug discovery, and stress testing

[Security Documentation →](docs/security/) | [Testing Guide →](backend/tests/e2e_ui/README.md)

---

## Documentation

### User Guides ⭐
- **[User Guide Index](docs/USER_GUIDE_INDEX.md)** - Complete user documentation (START HERE)
- [Quick Start Guide](docs/getting-started/quick-start.md) - Get started in 15 minutes
- [User Guide](docs/guides/USER_GUIDE.md) - Core features and daily workflows

### Core Features
- [Agent System](docs/agents/overview.md) - Multi-agent governance and orchestration
- [Community Skills Guide](docs/integrations/community-skills.md) - 5,000+ skills with Python & npm packages
- [Python Package Support](docs/security/python-packages.md) - NumPy, Pandas, 350K+ packages
- [npm Package Support](docs/security/npm-packages.md) - Lodash, Express, 2M+ packages
- [Episodic Memory](docs/intelligence/episodic-memory.md) - Agent learning system
- [Agent Graduation](docs/agents/graduation.md) - Promotion framework
- [Student Training](docs/agents/training.md) - Maturity routing

### Testing & Quality ✨ NEW
- [E2E Testing Guide](backend/tests/e2e_ui/README.md) - 91+ comprehensive end-to-end tests
- [Bug Discovery Infrastructure](backend/docs/BUG_DISCOVERY_INFRASTRUCTURE.md) - AI-enhanced bug discovery
- [Test Quality Standards](backend/docs/TEST_QUALITY_STANDARDS.md) - Testing best practices
- [Cross-Platform Testing](.planning/phases/236-cross-platform-and-stress-testing/236-VERIFICATION.md) - Mobile/desktop testing

### Platform
- [Development Guide](docs/development/overview.md) - Technical setup
- [Installation Guide](docs/getting-started/installation.md) - Complete instructions
- [Atom vs OpenClaw](docs/features/atom-vs-openclaw.md) - Feature comparison

### Advanced
- [Canvas Reference](docs/canvas/reference.md) - Canvas operations
- [Agent Governance](docs/agents/governance.md) - Maturity levels and permissions
- [Meta-Agent Routing](docs/agents/meta-agent.md) - Intent classification and fleet recruitment
- [Personal Edition](docs/operations/personal-edition.md) - Local deployment

**[Complete Documentation Index →](docs/INDEX.md)** | **[Reorganization Plan →](docs/DOCUMENTATION_REORGANIZATION_PLAN.md)**

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

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

**Built with** [ActivePieces](https://www.activepieces.com/) **|** [LangChain](https://langchain.com/) **|** [FastAPI](https://fastapi.tiangolo.com/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation.**

⭐ Star us on GitHub — it helps!

</div>