# 🏗️ ATOM Code Structure Overview

## 📁 Project Architecture

ATOM is a comprehensive AI assistant platform with hybrid architecture combining Next.js frontend, Python backend, and Tauri desktop application.

### Core Components

#### 🐍 **Backend (Python/FastAPI)**
```
backend/
├── python-api-service/          # Main API service
│   ├── main_api_app.py              # FastAPI application entry point
│   ├── auth_handler_*.py            # OAuth handlers for 10+ services
│   │   ├── auth_handler_gmail.py    # Gmail OAuth integration
│   │   ├── auth_handler_slack.py    # Slack OAuth integration
│   │   ├── auth_handler_github.py   # GitHub OAuth integration
│   │   ├── auth_handler_outlook.py  # Outlook OAuth integration
│   │   ├── auth_handler_teams.py    # Teams OAuth integration
│   │   ├── auth_handler_trello.py   # Trello API integration
│   │   ├── auth_handler_asana.py    # Asana OAuth integration
│   │   ├── auth_handler_notion.py   # Notion OAuth integration
│   │   ├── auth_handler_dropbox.py  # Dropbox OAuth integration
│   │   ├── auth_handler_gdrive.py   # Google Drive OAuth integration
│   │   └── auth_handler_box.py      # Box OAuth integration
│   ├── user_api_key_service.py      # BYOK API key management
│   ├── user_api_key_routes.py       # API key endpoints
│   ├── workflow_agent_integration.py    # LLM-based workflow generation
│   ├── nlu_bridge_service.py            # Bridge to TypeScript NLU system
│   ├── context_management_service.py    # Conversation history & preferences
│   ├── transcription_service.py         # Voice transcription (Deepgram)
│   ├── workflow_automation_api.py      # Workflow automation endpoints
│   ├── service_registry_routes.py       # Service registry endpoints
│   └── service_handlers/                # External service integrations
│       ├── gmail_handler.py        # Gmail API integration
│       ├── slack_handler.py        # Slack API integration
│       ├── github_handler.py       # GitHub API integration
│       ├── outlook_handler.py      # Outlook API integration
│       ├── teams_handler.py        # Teams API integration
│       ├── trello_handler.py       # Trello API integration
│       ├── asana_handler.py        # Asana API integration
│       ├── notion_handler.py       # Notion API integration
│       ├── dropbox_handler.py      # Dropbox API integration
│       ├── gdrive_handler.py       # Google Drive API integration
│       └── box_handler.py          # Box API integration
├── integrations/                # Service integration classes
│   ├── google_integration.py    # Google API integration
│   ├── microsoft_integration.py # Microsoft API integration
│   ├── slack_integration.py     # Slack API integration
│   ├── github_integration.py    # GitHub API integration
│   └── oauth_integration.py     # OAuth management system
└── docker/                     # Docker configurations
    ├── docker-compose.yaml      # Main development environment
    ├── docker-compose.prod.yml # Production environment
    └── postgres/               # PostgreSQL configuration
```

#### ⚡ **Frontend (Next.js/TypeScript)**
```
frontend-nextjs/
├── pages/
│   ├── index.tsx                 # Main dashboard
│   ├── settings.tsx              # User settings and service connections
│   ├── voice.tsx                 # Voice interface
│   ├── search.tsx                # Cross-platform search
│   ├── communication.tsx         # Unified communication hub
│   ├── tasks.tsx                 # Task management
│   └── api/                      # Next.js API routes
│       ├── auth/                 # Authentication endpoints
│       └── agent/                 # Agent coordination endpoints
├── components/
│   ├── AIProviders/             # BYOK AI provider settings
│   ├── Settings/                # Service connection management
│   │   ├── ServiceManager.tsx   # Unified service connections
│   │   └── ConnectionStatus.tsx # Real-time service status
│   └── OAuth/                   # OAuth flow components
├── lib/
│   ├── api-backend-helper.ts    # Backend API client
│   ├── constants.ts             # API URLs & configuration
│   └── auth.ts                  # Authentication utilities
└── tests/                      # Frontend tests
```

#### 🧠 **AI & NLU System (TypeScript)**
```
src/
├── nlu_agents/                 # LLM-based Natural Language Understanding
│   ├── nlu_lead_agent.ts       # Orchestrates multiple agents
│   ├── workflow_agent.ts       # Workflow intent detection
│   ├── analytical_agent.ts     # Logical analysis
│   ├── creative_agent.ts       # Creative interpretation
│   └── practical_agent.ts      # Feasibility assessment
├── orchestration/              # Agent orchestration engine
│   ├── workflow_coordinator.ts # Multi-service workflow coordination
│   ├── service_selector.ts     # Intelligent service selection
│   └── task_scheduler.ts       # Task scheduling and execution
├── skills/                     # Specialized AI skills
│   ├── calendar_skill.ts       # Calendar management
│   ├── communication_skill.ts  # Email/messaging
│   ├── task_management_skill.ts # Task creation/tracking
│   └── integration_skill.ts    # External service integration
└── services/                   # Backend service connectors
    ├── gmail_service.ts        # Gmail API client
    ├── slack_service.ts        # Slack API client
    ├── github_service.ts       # GitHub API client
    └── notion_service.ts       # Notion API client
```

#### 🖥️ **Desktop App (Tauri/Rust)**
```
desktop/tauri/
├── src-tauri/
│   ├── main.rs                # Rust backend entry point
│   ├── python-backend/         # Python backend integration
│   │   └── main_api_app.py    # Desktop backend server
│   └── src/                    # Desktop UI components
│       ├── main.rs            # Tauri application
│       ├── Settings.tsx       # Desktop settings interface
│       └── AIProviderSettings.tsx # Desktop AI provider interface
├── src/                       # React frontend components
│   ├── components/            # Shared UI components
│   └── lib/                   # Desktop utilities
└── package.json               # Desktop app dependencies
```

#### 🔐 **Authentication & Security**
```
🔐 **OAuth Authentication System - 10/10 Services**
├── Gmail/Google Drive - Google OAuth ✅
├── Slack - Slack OAuth ✅
├── GitHub - GitHub OAuth ✅
├── Outlook - Microsoft OAuth ✅
├── Teams - Microsoft OAuth ✅
├── Trello - Trello API ✅
├── Asana - Asana OAuth ✅
├── Notion - Notion OAuth ✅
├── Dropbox - Dropbox OAuth ✅
└── Box - Box OAuth ✅

🔧 **OAuth Server Architecture**
├── Consolidated endpoints for all 10 services
├── Environment-based credential management
├── Frontend proxy integration (Next.js API routes)
├── Desktop app backend connectivity
└── Security features (CSRF protection, token encryption)
```

#### 🔑 **BYOK (Bring Your Own Keys) System**
```
🤖 **Multi-Provider AI Ecosystem**
├── OpenAI: GPT models - Baseline ✅
├── DeepSeek AI: 40-60% cost savings - Code generation ✅
├── Anthropic Claude: Advanced reasoning - Long context ✅
├── Google Gemini: 93% cost savings - Multimodal ✅
└── Azure OpenAI: Enterprise security - Compliance ready ✅

🔐 **Security Features**
├── Fernet encryption for API key storage
├── User isolation and key masking
├── 7 RESTful endpoints for key management
└── Frontend feature parity (web + desktop)
```

### 🗄️ Data & Storage

#### Databases
- **PostgreSQL**: Primary relational database (production)
- **SQLite**: Development and fallback database
- **LanceDB**: Vector embeddings for semantic search
- **Redis**: Caching and session management

#### Service Registry
- **33 Registered Services**: Comprehensive external service coverage
- **10 Active Services**: Fully integrated with OAuth
- **Service Health Monitoring**: Real-time status tracking
- **Dynamic Service Selection**: Based on user preferences

### 🔄 System Integration Flow

### 1. User Input Processing
```
User Input → Voice/Text → NLU Bridge → TypeScript NLU Agents → Intent Analysis
```

### 2. Workflow Generation
```
Intent Analysis → Workflow Agent → Service Mapping → Workflow Definition → Execution
```

### 3. Context Management
```
User Input → Conversation History → User Preferences → Enhanced Context
```

### 4. Voice Integration
```
Audio Input → Deepgram Transcription → NLU Processing → Action Execution
```

### 5. Multi-Service Coordination
```
Workflow Definition → Service Selection → Parallel Execution → Result Aggregation
```

## 🛠️ Key Integration Points

### Python ↔ TypeScript Bridge
- **NLU Bridge Service**: Connects Python backend to TypeScript NLU system
- **API Endpoints**: `/api/agent/nlu` for NLU processing
- **Workflow Automation**: `/api/workflow-automation/generate`

### Service Integration Architecture
- **OAuth Authentication**: Secure authentication for 10 major services
- **Service Handlers**: Specialized handlers for each external service
- **Health Monitoring**: Real-time service status and connectivity
- **Error Recovery**: Graceful handling of service failures

### Cross-Platform Support
- **Web Frontend**: Next.js with comprehensive UI components
- **Desktop App**: Tauri with native performance
- **Feature Parity**: Consistent experience across platforms
- **Shared Components**: Reusable UI and service components

## 🚀 Development Workflow

### Environment Setup
```bash
# Clone and initialize
git clone <repository>
cd atom
git submodule update --init --recursive

# Setup environment
cp .env.example .env
# Configure your API keys in .env

# Install dependencies
npm install
cd frontend-nextjs && npm install
```

### Development Services
```bash
# Start development services
docker-compose -f backend/docker/docker-compose.yaml up -d

# Start backend
cd backend/python-api-service
python main_api_app.py

# Start frontend
cd frontend-nextjs
npm run dev

# Start desktop (optional)
cd desktop/tauri
npm run tauri dev
```

### Production Deployment
```bash
# Production deployment
docker-compose -f backend/docker/docker-compose.prod.yml --profile prod up -d

# Build frontend
cd frontend-nextjs
npm run build

# Build desktop
cd desktop/tauri
npm run tauri build
```

## 📊 Current Implementation Status

### ✅ **Completed Features**
- **OAuth Authentication**: 10/10 services with production credentials
- **BYOK System**: Multi-provider AI with secure key management
- **Service Integration**: 33 services registered, 10 actively connected
- **Workflow Automation**: Natural language to automated workflows
- **Voice Processing**: Deepgram integration for voice commands
- **Cross-Platform Support**: Web and desktop feature parity
- **Security Framework**: Enterprise-grade encryption and authentication
- **API Infrastructure**: Comprehensive REST API with health monitoring

### 🔧 **In Progress**
- **Advanced Workflows**: Complex multi-service orchestration
- **Real-time Updates**: WebSocket integration for live updates
- **Performance Optimization**: Load testing and caching
- **Documentation**: User guides and API documentation

### 🎯 **Next Steps**
1. Complete advanced workflow automation
2. Implement real-time collaboration features
3. Optimize performance for production scale
4. Expand service integrations to additional platforms

---

**Last Updated**: 2025-11-02  
**Status**: Production Ready with Comprehensive Service Integration