<div align="center">

# ATOM Platform

> **Developer Note:** For current status, architecture, and handover instructions, please see [docs/developer_handover.md](docs/developer_handover.md).

ATOM (Advanced Task Orchestration & Management) is an AI-powered automation platform.

![WhatsApp Video 2025-11-04 at 12 23 11 AM](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue)](https://www.typescriptlang.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15.5-black)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

*"Just talk to Atom - your AI agent that automates complex workflows through simple conversation"*

</div>

## ✨ Meet Your Atom Agent

Atom is your conversational AI agent that automates complex workflows through natural language chat. Now with Computer Use Agent capabilities, Atom can see and interact with your desktop applications, automate repetitive tasks, and create visual workflows that bridge web services with local desktop software.

**Key Features:**
- ✅ **Universal BYOK (Bring Your Own Key)** - User-managed API keys with budget guardrails
- ✅ **External Stakeholder Governance** - HITL "Learning Phase" for all agent communications
- ✅ **GraphRAG & Cognitive Search** - Knowledge graph + vector search for perfect AI recall
- ✅ **Autonomous Business Swarm** - Multi-agent orchestration for project management (PM Swarm)
- ✅ **Computer Use Agent System** - Desktop automation with visual understanding
- ✅ **AI Sales & CRM Automation** - Lead scoring, deal health, & Order-to-Cash bridge
- ✅ **Small Business Mastery** - Smart scheduling, no-show recovery, & autonomous collections
- ✅ **AI Accounting Engine** - Confidence-based categorization, continuous reconciliation
- ✅ **Financial Ops** - Cost leak detection, budget guardrails, invoice reconciliation
- ✅ **33+ service integrations** - Slack, WhatsApp, Meta, Google, Salesforce, HubSpot, and more
- ✅ **Natural language workflow creation** - Just describe what you want

### 🧠 Knowledge Graph & AI Memory

Atom doesn't just connect to your apps — it **remembers everything**:

| Feature | How It Works |
|---------|--------------|
| **Unified Memory** | All emails, tasks, documents indexed in LanceDB vector store |
| **Cross-App Context** | Ask "What did we discuss about Project X?" across Gmail, Slack, Notion |
| **Semantic Search** | Find related content even with different keywords |
| **Workflow Intelligence** | Automations use past context for smarter decisions |
| **Continuous Ingestion** | Real-time sync keeps memory up-to-date |


### 🎯 The Atom Difference

| Traditional Approach | With Atom |
|---------------------|-----------|
| ❌ Complex workflow builders | ✅ **"Just describe what you want"** |
| ❌ Manual setup | ✅ **Conversational automation** |
| ❌ Separate tools | ✅ **One chat interface for everything** |
| ❌ Web-only automation | ✅ **Desktop + Web integration** |
| ❌ Can't see your screen | ✅ **Visual understanding & interaction** |

## 🚀 Quick Start

### Option 1: Setup Wizard (Recommended)
```bash
# 1. Clone the repository
git clone https://github.com/rush86999/atom.git
cd atom

# 2. Run interactive setup wizard
python3 backend/scripts/setup_wizard.py

# 3. Validate your configuration
python3 backend/scripts/validate_credentials.py

# 4. Start the backend
cd backend && python3 main_api_app.py

# 5. Start the frontend (new terminal)
cd frontend-nextjs && npm install && npm run dev
```

### Option 2: Manual Setup
```bash
# 1. Clone & configure
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.example .env

# 2. Edit .env with your credentials
# See docs/missing_credentials_guide.md for details

# 3. Install dependencies
cd frontend-nextjs && npm install
cd ../backend && pip install -r requirements.txt

# 4. Start services
python3 backend/main_api_app.py  # Terminal 1
npm run dev --prefix frontend-nextjs  # Terminal 2
```

**Access the application:** http://localhost:3000

📖 **Documentation:**
- [Credentials Guide](docs/missing_credentials_guide.md) - Configure 117+ integrations
- [Developer Handover](docs/developer_handover.md) - Architecture & status
- [NextAuth Setup](docs/nextauth_production_setup.md) - Authentication config

### 2. Start Backend
```bash
cd backend
python main_api_app.py
# or use: python start_simple_backend.py
```

### 3. Start Frontend
```bash
cd frontend-nextjs
npm install
npm run dev
```

### 4. Start Talking
Open `http://localhost:3000` and try these commands:

**"Atom, search for my project documents"**
**"Show me my messages from Sarah"**
**"What tasks are due today?"**
**"Automate my meeting follow-ups"**
**"Schedule a team meeting for next week"**
**"Open Excel and create a sales report"**
**"Copy data from my desktop app to Google Sheets"**
**"Automate filling out this form on my screen"**
**"Who are my top leads to follow up on?"**
**"Which deals in my pipeline are at risk?"**
**"Summarize my last sales call with GrowthCorp"**

## 🔍 Specialized Interfaces

### 🎯 Search UI
- Cross-platform semantic search
- Real-time indexing across all services
- Context-aware results

### 💬 Communication UI  
- Unified inbox (email, Slack, Teams)
- Smart notifications and prioritization
- Cross-platform messaging

### 📋 Task UI
- Aggregated tasks from all services
- AI-powered prioritization
- Project coordination

### ⚙️ Workflow Automation UI
- Natural language workflow creation
- Visual drag-and-drop designer
- Multi-step automation builder
- **AI-Generated DB Queries** - Natural language to structured Notion filters
- **Knowledge Search Nodes** - Integrated search across all platforms
- **Computer Use Agent** - Desktop application control

### 🖥️ Desktop Automation UI
- Screen capture and visual understanding
- Desktop application integration
- Automated form filling and data entry
- Cross-platform desktop workflows

### 📅 Scheduling UI
- Unified calendar view
- Smart scheduling and conflict detection
- Meeting coordination

### 🚀 AI Sales & CRM
- **Lead IQ** - Automated lead scoring and qualification
- **Deal Health** - AI analysis of pipeline risk and health
- **Talk-to-Task** - Call transcriptions to automated action items
- **Order-to-Cash Bridge** - Automated invoicing upon winning deals
- **Small Business Mastery** - Smart scheduling, no-show recovery, & autonomous collections
- **Lifecycle Communication** - Professional AI-generated responses for POs, shipping, and quotes

### 🧾 AI Accounting (NEW)
- **Transaction Categorization** - AI-powered with 85% confidence threshold
- **Continuous Reconciliation** - Daily bank ↔ ledger matching
- **Anomaly Detection** - Unusual amounts, duplicates, missing transactions
- **AP Automation** - Invoice intake, auto-approve under threshold
- **AR & Collections** - Invoice generation, smart reminder escalation
- **Chart of Accounts Learning** - Adapts to your categorization patterns

### 🛡️ Security & Governance (NEW)
- **Universal BYOK** - Bring your own keys for OpenAI, Anthropic, and Google Gemini
- **Budget Guardrails** - Enforce spending limits on agent-driven AI requests
- **External Safety Layer** - Mandatory "Learning Phase" for all external messaging
- **HITL Approval** - Human-in-the-loop queue for sensitive agent actions
- **Encrypted Secrets** - Zero-trust architecture for integration credentials

## 🛠️ Architecture

### Frontend
- **Next.js 15.5** with TypeScript
- **React 18** with Chakra UI + Material-UI
- **Real-time collaboration** across all services

### Backend  
- **Python FastAPI/Flask** APIs
- **PostgreSQL** with robust data persistence
- **LanceDB** vector database for AI memory
- **OAuth 2.0** security across all integrations

### AI & Orchestration
- **Advanced NLU System** - Understands complex requests
- **Multi-Agent Coordination** - Specialized AI teams
- **Context Management** - Remembers conversation history
- **Voice Integration** - Seamless voice-to-action

## 🔗 Available Integrations

### 📄 Document Storage
- Google Drive, OneDrive, Dropbox, Box

### 💬 Communication
- Slack, Microsoft Teams, Discord, Gmail, Outlook

### 🎯 Productivity  
- Asana, Notion, Linear, Monday.com, Trello

### 💻 Development
- GitHub, GitLab, Jira

### 🏢 CRM & Business
- Salesforce, HubSpot, Zendesk, Freshdesk

### 💰 Financial
- Stripe, QuickBooks, Xero
- **Built-in AI Accounting** - Transaction engine, AP/AR, reconciliation

## 📊 Current Status

**Platform Status: Production Ready**  
- ✅ 8/8 core claims validated
- ✅ 33 services registered
- ✅ 5 services actively connected
- ✅ Natural language workflow generation
- ✅ Complete BYOK system
- ✅ 132 blueprints loaded
- ✅ **Computer Use Engine**: Finance, Sales, Operations Agents (Logic Verified)

## 🚢 Deployment

### Docker (Recommended)
```bash
docker-compose up -d
```

### Manual Setup
```bash
# Backend
cd backend
pip install -r requirements.txt
python main_api_app.py

# Frontend  
cd frontend-nextjs
npm install
npm run build
npm start
```

## 🤝 Contributing

We welcome contributions! Please see our development guidelines in the `docs/` directory.

## 📄 License

AGPL License - See [LICENSE.md](LICENSE.md) for details.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues)
- **Documentation**: Check `docs/` directory
- **Integration Guides**: Service-specific implementation docs

---

<div align="center">

**Start talking to Atom today and experience the future of workflow automation!**

</div>