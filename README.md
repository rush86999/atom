<div align="center">

# ATOM Platform
### Open-Source AI Agent Platform for Self-Hosted Automation

> **Developer Note:** For technical setup and architecture, please see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

</div>

## ✨ What is Atom?

Atom is an **open-source, self-hosted AI agent platform** that combines the flexibility of visual workflow builders (like Zapier/Activepieces) with the intelligence of LLM-based agents.

Just **speak** or **type** your request, and Atom's specialty agents — from Sales to Engineering — will plan, verify, and execute complex workflows across your entire tech stack.

**🎓 Key Difference**: Unlike SaaS alternatives, Atom runs entirely in your own infrastructure. Your data never leaves your environment, and you maintain full control over:
- Where your agents run (local, Docker, or your own cloud)
- Which LLM providers to use (OpenAI, Anthropic, DeepSeek, Gemini, etc.)
- How your data is stored and processed

---

## 🚀 Key Features

### 🎙️ **Voice Interface**
**"Hey Atom, create a workflow to sync new Shopify orders to Slack."**
- **Hands-Free Automation**: Build complex workflows using just your voice
- **Natural Language Understanding**: No need to learn proprietary syntax
- **Real-Time Feedback**: Watch as Atom visualizes its reasoning process step-by-step

### 🤖 **Specialty Agents**
Why rely on generic AI when you can hire experts?
- **Sales Agent**: Manages CRM pipelines, scores leads, and drafts outreach
- **Marketing Agent**: Automates campaigns, social posting, and analytics reports
- **Engineering Agent**: Handles PR notifications, deployments, and incident response
- **Governance**: Agents start as "Students" and earn "Autonomy" as they gain your trust

### 🛡️ **Agent Governance System**
- **Maturity Levels**: Agents progress from 'Student' to 'Autonomous' based on performance
- **Approval Workflows**: Sensitive actions (like deployments) require human approval until confidence is high
- **Safety First**: All agent actions are logged, timestamped, and traceable

### 🧠 **Universal Memory & Context**
Atom remembers everything so you don't have to repeat yourself.
- **Capability Recall**: Agents use long-term memory to remember which services you've connected, enabling proactive suggestions
- **Unified Index**: Emails, Notion docs, Jira tickets, and Slack threads are indexed for instant retrieval
- **Knowledge Graph**: Atom builds a graph of your people, projects, and tasks to understand *relationships*, not just keywords
- **Trusted Memory**: Store critical business facts (policies, compliance rules) with **JIT Citations**. Agents must "Trust but Verify" these facts against source documents before acting
- **Privacy First**: Sensitive data like API keys and PII are automatically redacted and encrypted (Fernet at-rest)
- **Self-Evolving World Model**: Agents store and retrieve past "experiences" to learn from success and failure. See [docs/ai-world-model.md](docs/ai-world-model.md)

### 🛠️ **Dynamic Skill Creation & Execution**
- **Runtime Tool Discovery**: Agents can identify gaps in their toolset and "build" new tools on-the-fly
- **Skill Runner UI**: A dedicated dashboard to browse, test, and execute local agent skills with real-time feedback
- **Real-Time Streaming**: Watch skill execution line-by-line via the new streaming CLI backend
- **Multi-Runtime Support**: Automated generation of Script, API, and Docker-based skills from natural language
- **Self-Hosted Execution**: All skills execute locally in your environment using Docker or Node.js VM

### 🔌 **Deep Integrations & Desktop Access**
- **Hybrid Engine**: Python orchestration + Node.js Piece Engine for the full **ActivePieces** catalog
- **System Tray & Background Mode**: Run ATOM in the background with quick access from the system tray (macOS/Windows)
- **Desktop Memory Ingestion**: Local folder access for the Tauri application, enabling seamless indexing of `$DESKTOP` knowledge
- **Node-on-Demand**: Integrations are installed dynamically on-the-fly to ensure the catalog is always up-to-date

### 🌐 **Universal Communication Bridge**
Seamlessly interact with your workforce from any platform.
- **Unified Messaging**: One standard interface for **11+ platforms**, including Slack, WhatsApp, Discord, Microsoft Teams, Telegram, Google Chat, Twilio (SMS), Matrix, Facebook Messenger, Line, and Signal
- **Platform Native Commands**: Use `/run`, `/workflow`, and `/agents` directly from your favorite chat app
- **Agent-to-Agent Communication**: Agents can discover and delegate tasks to each other directly via the bridge
- **Async Feedback**: Delegated tasks automatically route their results back to the requester

---

## 🎯 Example Use Cases

| Department | Scenario |
|------------|----------|
| **Sales** | **Lead Enrichment**: "When a new lead arrives in HubSpot, research their company on LinkedIn, score them based on fit, and slack the relevant account executive." |
| **Finance** | **Invoice Reconciliation**: "Watch for PDF invoices in Gmail, extract the data, match it against QuickBooks, and flag any discrepancies for review." |
| **Support** | **Ticket Triage**: "Analyze incoming Zendesk tickets for sentiment, route urgent issues to the #escalations channel, and draft a polite initial response." |
| **HR** | **Onboarding**: "When a new employee is added to BambooHR, provision their Google Workspace account, invite them to Slack channels, and schedule their orientation." |

---

## 🏎️ Getting Started

### Quick Start (Docker)
The fastest way to experience Atom is using Docker:

```bash
git clone https://github.com/rush86999/atom.git
cd atom
docker-compose up -d
```

Access the dashboard at: **http://localhost:3000**

> For detailed installation guides, configuration options, and architecture diagrams, please refer to our **[Development Guide](docs/DEVELOPMENT.md)**.

---

## 🔒 Security & Privacy

### Data Sovereignty
- **Self-Hosted Only**: Atom is designed to run entirely in your own infrastructure
- **No Data Egress**: Your data never leaves your environment
- **Full Control**: You control where agents run, how data is stored, and who has access

### BYOK (Bring Your Own Key)
- Use your own OpenAI, Anthropic, Gemini, DeepSeek, or other LLM provider keys
- Support for multiple LLM providers with intelligent cost-based routing
- No vendor lock-in - switch providers anytime

### Enterprise-Grade Security
- **Human-in-the-Loop**: Designated workflows require manual approval before execution
- **Audit Logs**: Every action taken by an agent is logged, timestamped, and traceable
- **Encrypted Storage**: Sensitive data encrypted at-rest using Fernet
- **Agent Governance**: Configurable approval policies based on agent maturity levels

---

## 🏗️ Architecture

Atom is built with modern, scalable technologies:

### Backend
- **FastAPI** - High-performance Python API framework
- **PostgreSQL** - Reliable relational database
- **SQLAlchemy** - Powerful ORM for database operations
- **Redis** - Caching and message queue
- **WebSocket** - Real-time communication

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - Beautiful, accessible component library
- **Tauri** - Desktop application framework

### AI/ML
- **Multi-LLM Support** - OpenAI, Anthropic, DeepSeek, Gemini, and more
- **ReAct Framework** - Reasoning + Acting agent loop
- **Vector Database** - Semantic search and memory retrieval
- **Knowledge Graph** - Relationship-aware information storage

---

## 📦 What's Included

- ✅ Complete backend API with FastAPI
- ✅ Modern Next.js frontend with TypeScript
- ✅ Desktop app support (Tauri)
- ✅ 46+ pre-built integrations (Slack, Gmail, HubSpot, Salesforce, etc.)
- ✅ Multi-platform communication bridge (11+ platforms)
- ✅ Dynamic skill creation system
- ✅ Agent governance and maturity system
- ✅ Memory and knowledge graph systems
- ✅ Voice interface support
- ✅ Docker deployment configuration

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
# Clone the repository
git clone https://github.com/rush86999/atom.git
cd atom

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd ../src
npm install

# Start development servers
# Backend (terminal 1):
cd backend && uvicorn main:app --reload

# Frontend (terminal 2):
cd src && npm run dev
```

---

## 📖 Documentation

- [Development Guide](docs/DEVELOPMENT.md) - Technical setup and architecture
- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [Integration Guide](docs/INTEGRATIONS.md) - Adding new integrations
- [Agent Governance](docs/AGENT_GOVERNANCE.md) - Understanding agent maturity and approval workflows

---

## 📞 Support & Community

- **Documentation**: Check the `docs/` directory for in-depth guides
- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **License**: AGPL v3 - See [LICENSE.md](LICENSE.md)

---

## 🙏 Acknowledgments

Atom is built on top of amazing open-source projects:
- [ActivePieces](https://www.activepieces.com/) - Workflow automation engine
- [LangChain](https://langchain.com/) - LLM application framework
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework
- [Tauri](https://tauri.app/) - Desktop application framework

<div align="center">

**Experience the future of self-hosted AI automation.**

[Get Started](#-getting-started) | [Documentation](docs/) | [Contributing](CONTRIBUTING.md)

</div>
