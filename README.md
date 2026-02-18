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
- Natural language understanding — no proprietary syntax to learn
- Real-time feedback as Atom visualizes its reasoning

### 🤖 Specialty Agents
- **Sales Agent**: CRM pipelines, lead scoring, outreach
- **Marketing Agent**: Campaigns, social posting, analytics
- **Engineering Agent**: PR notifications, deployments, incidents
- **Governance**: Agents progress from "Student" to "Autonomous" as they gain trust

### 🎨 Canvas Presentations & Agent Guidance ✨
- Rich interactive presentations (charts, forms, markdown)
- **Real-time operation visibility**: See exactly what agents are doing
- Multi-view orchestration (browser, terminal, canvas)
- Smart error resolution with actionable suggestions
- [Full Details →](docs/CANVAS_IMPLEMENTATION_COMPLETE.md)

### 🧠 Episodic Memory & Graduation
- **Experience-based learning**: Agents automatically segment, store, and retrieve past experiences
- **Hybrid storage**: PostgreSQL (hot data) + LanceDB (cold archives)
- **Four retrieval modes**: Temporal, Semantic, Sequential, Contextual
- **Graduation validation**: Promote agents only when they demonstrate reliable performance
- [Full Documentation →](docs/EPISODIC_MEMORY_IMPLEMENTATION.md)

### 🛡️ Agent Governance System
- Agents progress from 'Student' → 'Autonomous' based on performance
- **Maturity-based routing**: Student agents blocked from automated triggers
- **AI-powered training**: Personalized learning with duration estimation
- Sensitive actions require approval until confidence is high
- Every action logged, timestamped, and traceable

### 🔌 Deep Integrations
- **46+ pre-built integrations**: Slack, Gmail, HubSpot, Salesforce, etc.
- **9 messaging platforms**: Slack, Discord, Teams, WhatsApp, Telegram, Google Chat, Signal, Facebook Messenger, LINE
- Proactive messaging, scheduled messages, condition monitoring
- Use `/run`, `/workflow`, `/agents` from your favorite chat app

### 🌐 Community Skills ✨
- **5,000+ OpenClaw/ClawHub skills**: Import and use community-built skills
- **Enterprise security**: LLM-powered scanning with 21+ malicious pattern detection
- **Hazard Sandbox**: Isolated Docker containers prevent host access
- **Skills Registry**: Easy import with status tracking (Untrusted → Active → Banned)
- [Community Skills Guide →](docs/COMMUNITY_SKILLS.md)

### 🔍 Browser & Device Automation
- Browser automation via CDP (web scraping, form filling)
- Device control (camera, location, notifications, terminal)
- Governance-first: all actions require appropriate maturity level

---

## Installation Options

### 🐳 Docker (5 minutes - No setup required)

```bash
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env
# Edit .env and add your API keys
docker-compose -f docker-compose-personal.yml up -d
```

Access at: **http://localhost:3000**

### 💻 Native Installation (10 minutes - No Docker)

```bash
git clone https://github.com/rush86999/atom.git
cd atom
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ../frontend-nextjs && npm install
cp .env.personal .env
# Edit .env and add your API keys
# Start backend: cd backend && python -m uvicorn main_api_app:app --reload
# Start frontend: cd frontend-nextjs && npm run dev
```

Access at: **http://localhost:3000**

[Full Docker Guide →](docs/PERSONAL_EDITION.md) | [Full Native Guide →](docs/NATIVE_SETUP.md)

---

## Example Use Cases

| **Department** | **Scenario** |
|----------------|-------------|
| **Sales** | New lead in HubSpot → Research company → Score lead → Slack the account executive |
| **Finance** | PDF invoice in Gmail → Extract data → Match against QuickBooks → Flag discrepancies |
| **Support** | Zendesk ticket arrives → Analyze sentiment → Route urgent issues → Draft response |
| **HR** | New employee in BambooHR → Provision Google account → Invite to Slack → Schedule orientation |

---

## Security & Privacy

- **Self-Hosted Only**: Your data never leaves your environment
- **BYOK**: Bring your own OpenAI, Anthropic, Gemini, or DeepSeek keys
- **Encrypted Storage**: Sensitive data encrypted at-rest (Fernet)
- **Audit Logs**: Every agent action logged and traceable
- **Human-in-the-Loop**: Configurable approval policies

---

## Documentation

### Core Features
- [Community Skills Guide](docs/COMMUNITY_SKILLS.md) - Import 5,000+ OpenClaw/ClawHub skills
- [Episodic Memory](docs/EPISODIC_MEMORY_IMPLEMENTATION.md) - Experience-based learning system
- [Agent Graduation Guide](docs/AGENT_GRADUATION_GUIDE.md) - Promotion validation framework
- [Student Agent Training](docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Maturity-based routing system

### Platform
- [Development Guide](docs/DEVELOPMENT.md) - Technical setup and architecture
- [Installation Guide](docs/INSTALLATION.md) - Complete installation instructions
- [Atom vs OpenClaw](docs/ATOM_VS_OPENCLAW.md) - Feature comparison with alternatives

### Advanced
- [Canvas Implementation](docs/CANVAS_IMPLEMENTATION_COMPLETE.md) - Canvas system details
- [Agent Governance](docs/AGENT_GOVERNANCE.md) - Maturity levels and approvals
- [Personal Edition](docs/PERSONAL_EDITION.md) - Local deployment with Docker Compose
- [Agent-to-Agent Execution](docs/PERSONAL_EDITION.md) - Daemon mode and CLI control
- [IM Adapter Setup](backend/docs/IM_ADAPTER_SETUP.md) - Telegram & WhatsApp integration

**[Complete Documentation Index →](docs/INDEX.md)**

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Support

- **Documentation**: See [docs/INDEX.md](docs/INDEX.md) for complete documentation index
- **Developer Guide**: See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup and deployment
- **Implementation History**: See [docs/IMPLEMENTATION_HISTORY.md](docs/IMPLEMENTATION_HISTORY.md) for recent changes
- **Issues**: [GitHub Issues](https://github.com/rush8699/atom/issues)
- **License**: AGPL v3 - See [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [ActivePieces](https://www.activepieces.com/) **|** [LangChain](https://langchain.com/) **|** [FastAPI](https://fastapi.tiangolo.com/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation.**

⭐ Star us on GitHub — it helps!

</div>
