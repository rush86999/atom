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

### 🎨 Canvas Presentations & Agent Guidance ✨ NEW
- Rich interactive presentations (charts, forms, markdown)
- **Real-time operation visibility**: See exactly what agents are doing in plain English
- Multi-view orchestration (browser, terminal, canvas)
- Smart error resolution with actionable suggestions
- Complete transparency and governance integration

[Full Details →](docs/CANVAS_IMPLEMENTATION_COMPLETE.md)

### 🔍 Browser & Device Automation
- Browser automation via CDP (web scraping, form filling)
- Device control (camera, location, notifications, terminal)
- Governance-first: all actions require appropriate maturity level

### 🧠 Universal Memory & Context
- **Capability Recall**: Agents remember your connected services
- **Unified Index**: Search emails, docs, tickets, and Slack instantly
- **Knowledge Graph**: Understands relationships, not just keywords
- **Episodic Memory**: Agents learn from past experiences with automatic segmentation
- **Graduation Validation**: Promote agents only when they demonstrate reliable performance
- **Privacy First**: API keys and PII automatically encrypted

### 🛡️ Agent Governance System
- Agents progress from 'Student' → 'Autonomous' based on performance
- **Maturity-based routing**: Student agents blocked from automated triggers
- **AI-powered training**: Personalized learning scenarios with duration estimation
- Sensitive actions require approval until confidence is high
- Every action logged, timestamped, and traceable
- Real-time supervision for learning agents

### 🔌 Deep Integrations
- **46+ pre-built integrations**: Slack, Gmail, HubSpot, Salesforce, etc.
- **Multi-platform bridge**: 12+ platforms (Slack, WhatsApp, Discord, Teams, etc.)
- Use `/run`, `/workflow`, `/agents` from your favorite chat app

### 🛠️ Dynamic Skills
- Agents build new tools on-the-fly
- Skill Runner UI to test and execute agent skills
- Real-time streaming execution

---

## Quick Start

**Fastest way (Docker)**:
```bash
git clone https://github.com/rush86999/atom.git
cd atom
docker-compose up -d
```

Access at: **http://localhost:3000**

[Detailed Setup →](docs/DEVELOPMENT.md)

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

## What's Included

✅ Complete backend (FastAPI) + frontend (Next.js) + desktop app (Tauri)
✅ 46+ pre-built integrations
✅ Multi-platform communication bridge (12+ platforms)
✅ Agent governance and maturity system
✅ Episodic memory and graduation framework
✅ Memory and knowledge graph
✅ Voice interface
✅ Docker deployment

---

## Recent Features (February 2026)

### Episodic Memory & Graduation Framework ✨ NEW
- **Experience-based learning**: Agents automatically segment, store, and retrieve past experiences
- **Hybrid storage architecture**: PostgreSQL (hot data) + LanceDB (cold archives) for efficient scaling
- **Four retrieval modes**: Temporal (time-based), Semantic (vector search), Sequential (full episodes), Contextual (hybrid)
- **Graduation validation**: Assess agent readiness using episodic memory before maturity promotions
- **Constitutional compliance**: Track intervention rates and validate against governance rules
- **Use cases**: MedScribe (clinical documentation), Brennan.ca (pricing validation), workflow optimization
- [Full Documentation →](docs/EPISODIC_MEMORY_IMPLEMENTATION.md)

### Student Agent Training System
- **Maturity-based routing**: Prevents STUDENT agents from automated triggers
- **AI training proposals**: Personalized learning with duration estimation
- **Real-time supervision**: Monitor SUPERVISED agents with intervention controls
- **Action proposals**: INTERN agents require human approval before execution
- **Confidence boosting**: Performance-based maturity progression
- [Full Documentation →](docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md)

### Canvas & Agent Guidance System
- Real-time operation tracking with plain English explanations
- Multi-view orchestration (browser, terminal, canvas)
- Smart error resolution with learning feedback
- Interactive permission/decision requests

### Recording & Governance Integration ✨ NEW
- **Auto-recording**: Autonomous agents automatically record sessions for governance
- **AI-powered review**: Analyzes recordings to update agent confidence
- **Learning loop**: Successful/failed patterns feed into world model
- **Confidence scoring**: Approved actions increase confidence, failures decrease it
- Full audit trail for compliance

---

## Documentation

- [Development Guide](docs/DEVELOPMENT.md) - Technical setup and architecture
- [Episodic Memory](docs/EPISODIC_MEMORY_IMPLEMENTATION.md) - Experience-based learning system
- [Agent Graduation Guide](docs/AGENT_GRADUATION_GUIDE.md) - Promotion validation framework
- [Student Agent Training](docs/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Maturity-based routing system
- [Canvas Implementation](docs/CANVAS_IMPLEMENTATION_COMPLETE.md) - Canvas system details
- [Agent Governance](docs/AGENT_GOVERNANCE.md) - Maturity levels and approvals
- [Recording System](docs/CANVAS_RECORDING_IMPLEMENTATION.md) - Recording and playback
- [Review Integration](docs/RECORDING_REVIEW_INTEGRATION.md) - Governance & learning

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Support

- **Documentation**: `docs/` directory
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **License**: AGPL v3 - See [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [ActivePieces](https://www.activepieces.com/) **|** [LangChain](https://langchain.com/) **|** [FastAPI](https://fastapi.tiangolo.com/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation.**

⭐ Star us on GitHub — it helps!

</div>
