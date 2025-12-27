# Atom Platform - Development Guide

> **Note:** This document contains technical setup instructions for developers. For the main project overview, see [README.md](../README.md).

## 🛠️ Architecture

### Frontend
- **Next.js 15.5** with TypeScript
- **React 18** with Chakra UI + Material-UI
- **Real-time collaboration** across all services

### Backend  
- **Python FastAPI/Flask** APIs (Py 3.11+)
- **PostgreSQL / SQLite** with robust data persistence
- **LanceDB** vector database for agent "World Model" and memory
- **Secure Multi-tenancy**: OAuth 2.0 with per-user credential encryption (Fernet)
- **Hybrid Piece Engine**: Node.js runtime executing the full ActivePieces ecosystem
- **Swarm Discovery**: Centralized MCP toolset for all specialty agents

### AI & Orchestration
- **Advanced NLU System** - Understands complex requests
- **Multi-Agent Coordination** - Specialized AI teams
- **Context Management** - Remembers conversation history
- **Voice Integration** - Seamless voice-to-action

## 🚀 Developer Setup

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
npm start --prefix backend/piece-engine # Terminal 3 (New: Integration Engine)
```

**Access the application:** http://localhost:3000

## 🚢 Deployment

### Docker (Recommended)
```bash
docker-compose up -d
```

### Manual Production Setup
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

## 📖 Documentation Resources
- [Credentials Guide](missing_credentials_guide.md) - Configure 117+ integrations
- [Developer Handover](developer_handover.md) - Architecture & status
- [NextAuth Setup](nextauth_production_setup.md) - Authentication config
