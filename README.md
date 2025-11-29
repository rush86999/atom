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

Atom is your conversational AI agent that automates complex workflows through natural language chat. Instead of manual setup, just describe what you want to automate and Atom builds complete workflows across 33+ integrated platforms.

**Key Features:**
- ✅ **8/8 marketing claims verified** - Platform Complete
- ✅ **33+ service integrations** - 5 actively connected (Slack, Google Calendar, Salesforce, HubSpot, Discord)
- ✅ **Natural language workflow creation** - Just describe what you want
- ✅ **Cross-platform coordination** - Works across all your tools
- ✅ **Production-ready architecture** - FastAPI backend, Next.js frontend

### 🎯 The Atom Difference

| Traditional Approach | With Atom |
|---------------------|-----------|
| ❌ Complex workflow builders | ✅ **"Just describe what you want"** |
| ❌ Manual setup | ✅ **Conversational automation** |
| ❌ Separate tools | ✅ **One chat interface for everything** |
| ❌ Voice assistants that can't act | ✅ **Conversation that builds automations** |

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

### 📅 Scheduling UI
- Unified calendar view
- Smart scheduling and conflict detection
- Meeting coordination

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

## 📊 Current Status

**Platform Status: Production Ready**  
- ✅ 8/8 core claims validated
- ✅ 33 services registered
- ✅ 5 services actively connected
- ✅ Natural language workflow generation
- ✅ Complete BYOK system
- ✅ 132 blueprints loaded

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