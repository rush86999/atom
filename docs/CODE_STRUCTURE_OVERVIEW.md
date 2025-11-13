# ATOM Platform - Complete Code Structure Overview

## 🎯 Recent Project Structure Improvements

### ✅ Completed Cleanup & Organization
- **Backend Consolidation**: Reduced from 385+ files to clean, organized structure
- **Shared Services Architecture**: Unified TypeScript services for web and desktop apps
- **Desktop App Fixes**: Resolved build issues with shared service imports
- **Gitignore Optimization**: Comprehensive exclusion of temporary and build files
- **Directory Organization**: Proper separation of core, tests, scripts, and data

### 🔧 Key Technical Improvements
- **Tauri Desktop Build**: Fixed esbuild configuration with shared service externals
- **TypeScript Path Mappings**: Proper `@shared-*` aliases for cross-platform development
- **Service Integration**: Shared AI, integration, and workflow services
- **LanceDB Integration**: Local vector database for desktop app performance
- **Build Optimization**: 2.2MB bundle size with external package handling

### 📁 Current Project Health
- **Build Status**: ✅ Tauri desktop app builds successfully
- **Service Integration**: ✅ Shared services accessible from both platforms
- **Platform Parity**: ✅ Identical features across desktop and web
- **Code Organization**: ✅ Clean, maintainable structure with proper separation

> **File Organization System**: This project uses automated file organization rules defined in `.file-organization-rules.json`. Run `python scripts/organize-files.py --validate` to check structure or `--organize` to auto-organize files.

## 🏗️ System Architecture

```
ATOM Platform - AI-Powered Task Orchestration & Management
├── Frontend Web App (Next.js 15.5 + TypeScript)
│   ├── Uses shared src/services for business logic
│   ├── Custom UI components with Chakra UI/Material-UI
│   ├── Integration components (33+ services)
│   ├── Specialized UIs (Search, Communication, Task, Calendar, Automation)
│   ├── Conversational AI chat interface
│   └── Backend API integration
├── Desktop App (Tauri + React + TypeScript)
│   ├── Uses shared src/services for business logic
│   ├── Desktop-specific UI components
│   ├── Embedded Python backend
│   └── Voice/audio processing
├── Shared Services (TypeScript)
│   ├── AI & ML Services (NLU, Orchestration, Skills)
│   ├── Integration Services (33+ platforms)
│   ├── Workflow Services (Automation, Triggers)
│   ├── UI Components (Shared design system)
│   └── Utility Services (Config, Utils)
├── Backend API Service (Python FastAPI/Flask)
│   ├── Core API Endpoints (health, auth)
│   ├── Integration Services (180+ implemented)
│   ├── LanceDB Memory Pipeline (vector database)
│   ├── OAuth Authentication (10+ providers)
│   ├── Document Processing Pipeline
│   ├── AI Service Integration
│   └── Real-time webhooks
├── AI & Orchestration Engine
│   ├── NLU Agents (specialized AI agents)
│   ├── Workflow Orchestration (multi-agent coordination)
│   ├── Skill System (modular AI capabilities)
│   ├── Memory Management (LanceDB vector search)
│   └── Trigger System (automation engine)
└── Storage & Memory
    ├── LanceDB (Vector Database - AI memory)
    ├── PostgreSQL (Relational data - production)
    ├── SQLite (Local development)
    ├── Local File Storage (Desktop)
    └── Integration Memory (all connected services)
```

## 📁 Shared Services Architecture (`src/`)

The `src/` directory contains shared TypeScript services used by both web and desktop applications, organized by domain:

### 🤖 AI & ML Services (`src/services/ai/`)
```
ai/
├── ChatOrchestrationService.ts      # Main chat orchestration
├── hybridLLMService.ts              # Multi-provider LLM integration
├── llmSettingsManager.ts            # LLM configuration management
├── nluHybridIntegrationService.ts   # NLU service integration
├── nluService.ts                    # Natural Language Understanding
├── openaiService.ts                 # OpenAI API integration
├── skillService.ts                  # Skill management
├── financeAgentService.ts           # Financial analysis agent
├── tradingAgentService.ts           # Trading agent
└── trading/                         # Trading-specific services
```

### 🔗 Integration Services (`src/services/integrations/`)
```
integrations/
├── apiKeyService.ts                 # API key management
├── authService.ts                   # Authentication services
├── connection-status-service.ts     # Service connectivity monitoring
├── googleDriveService.ts            # Google Drive integration
├── onedriveService.ts               # OneDrive integration
└── [20+ core service integrations]
```

### 🔄 Workflow Services (`src/services/workflows/`)
```
workflows/
├── autonomousWorkflowService.ts     # Autonomous workflow execution
├── workflowService.ts               # Core workflow management
└── automation-triggers/             # Trigger system implementation
```

### 🛠️ Utility Services (`src/services/utils/`)
```
utils/
├── config.ts                        # Shared configuration management
├── api.ts                          # API helpers and utilities
└── database.ts                      # Database connection utilities
```

### 🎨 UI Shared Components (`src/ui-shared/`)

Shared React components used by both web and desktop applications:

```
src/ui-shared/
├── components/           # Reusable UI components
├── integrations/         # Integration-specific UI components
│   ├── asana/           # Asana integration components
│   ├── github/          # GitHub integration components  
│   ├── notion/          # Notion integration components
│   └── slack/           # Slack integration components
├── search/              # Search interface components
├── task/                # Task management components
├── calendar/            # Calendar management components
├── communication/       # Communication hub components
└── agent/               # AI agent UI components
```

**Usage in Applications:**
- **Web App** (`frontend-nextjs/`): Imports from `src/ui-shared/`
- **Desktop App** (`desktop/tauri/`): Imports from `src/ui-shared/`
- **Shared Logic**: Both apps use `src/services/` for business logic
- **Shared Directory**: Additional shared components in `shared/components/`
```
ui-shared/
├── components/                      # Reusable UI components
├── integrations/                    # Integration UI components
│   ├── registry.ts                 # Complete integration registry
│   ├── index.ts                    # Integration management
│   ├── freshdesk/                  # Freshdesk components
│   ├── monday/                     # Monday.com components
│   ├── salesforce/                 # Salesforce components
│   └── microsoft365/               # Microsoft 365 components
├── types/                          # TypeScript type definitions
├── hooks/                          # Custom React hooks
├── contexts/                       # React contexts
└── utils/                          # UI utilities
```

### 🧠 NLU Agents (`src/nlu_agents/`)
```
nlu_agents/
├── analytical_agent.ts              # Analytical AI agent
├── creative_agent.ts                # Creative AI agent
├── practical_agent.ts               # Practical AI agent
├── socialMediaAgent.ts              # Social media agent
├── trading_agent.ts                 # Trading agent
├── workflow_agent.ts                # Workflow automation agent
├── llmConversationProcessor.ts      # LLM conversation handling
└── [15+ other specialized agents]
```

### 🎯 Skills System (`src/skills/`)
```
skills/
├── asanaSkills.ts                   # Asana project management
├── gmailSkills.ts                   # Gmail email management
├── slackSkills.ts                   # Slack communication
├── salesforceSkills.ts              # Salesforce CRM
├── githubSkills.ts                  # GitHub development
├── jiraSkills.ts                    # Jira project tracking
├── notionSkills.ts                  # Notion productivity
├── [50+ other skills for all integrations]
└── index.ts                         # Skill registry
```

### 🎭 Orchestration Engine (`src/orchestration/`)
```
orchestration/
├── OrchestrationEngine.ts           # Main orchestration engine
├── OrchestrationManager.ts         # Orchestration management
├── AgentRegistry.ts                 # Agent registration
├── workflows/                       # Workflow implementations
├── examples/                        # Usage examples
└── optimization/                     # Performance optimization
```

## 📁 Frontend Web Application (`frontend-nextjs/`)

### Technology Stack
- **Framework**: Next.js 15.5.0 with TypeScript
- **UI Library**: React 18.2.0 + Chakra UI + Material-UI
- **State Management**: React Context + Custom Hooks
- **Build Tool**: Next.js built-in + Webpack
- **AI Integration**: NLU agents + LLM services

### Key Features
- Multi-tenant web interface with specialized UIs
- Conversational AI chat interface (central coordinator)
- Real-time collaboration across all connected services
- Integration with 33+ external platforms
- Database-backed persistent storage with LanceDB
- Voice/audio processing capabilities
- Advanced workflow automation engine

### Configuration
- **Next.js Config**: Transpiles shared `src/` directory
- **Path Mapping**: `@shared-*` aliases for shared services
- **API Integration**: Connects to backend on port 5058
- **Environment**: Development, staging, production configs

### Directory Structure
```
frontend-nextjs/
├── src/
│   ├── components/                  # React components
│   │   ├── AI/                      # AI-powered components
│   │   ├── Search/                   # Search UI components
│   │   ├── Communication/            # Communication UI
│   │   ├── Tasks/                    # Task management UI
│   │   ├── Calendar/                 # Calendar UI
│   │   ├── Automations/              # Workflow automation UI
│   │   ├── Voice/                    # Voice processing UI
│   │   └── shared/                   # Shared UI components
│   ├── contexts/                    # React contexts
│   ├── hooks/                       # Custom React hooks
│   ├── config/                      # App configuration
│   ├── lib/                         # Utility libraries
│   └── constants.ts                 # App constants
├── pages/                           # Next.js pages
│   ├── integrations/                # Integration-specific pages
│   │   ├── index.tsx               # Main integrations hub
│   │   ├── slack.tsx               # Slack integration
│   │   ├── gdrive.tsx              # Google Drive integration
│   │   ├── onedrive.tsx            # OneDrive integration
│   │   ├── monday.tsx              # Monday.com integration
│   │   ├── salesforce.tsx          # Salesforce integration
│   │   ├── mailchimp.tsx           # Mailchimp integration
│   │   ├── microsoft365.tsx        # Microsoft 365 integration
│   │   ├── freshdesk.tsx           # Freshdesk integration
│   │   └── [25+ other integration pages]
│   ├── dashboard.tsx                # Main dashboard
│   ├── search.tsx                   # Search UI
│   ├── communication.tsx            # Communication UI
│   ├── tasks.tsx                    # Task management UI
│   ├── calendar.tsx                 # Calendar UI
│   ├── automations.tsx              # Workflow automation UI
│   ├── finance.tsx                  # Finance management UI
│   ├── agents.tsx                   # AI agents UI
│   └── index.tsx                    # Home page with chat interface
├── public/                          # Static assets
├── tests/                           # Frontend tests
├── styles/                          # Global styles
└── package.json                     # Dependencies and scripts
```

## 📁 Desktop Application (`desktop/`)

Tauri-based desktop application with shared services architecture:

```
desktop/
├── tauri/              # Tauri application
│   ├── src-tauri/      # Tauri Rust backend
│   │   ├── src/        # Rust source code
│   │   ├── Cargo.toml  # Rust dependencies
│   │   └── tauri.conf.json # Tauri configuration
│   ├── src/            # React frontend
│   │   ├── components/ # Desktop-specific components
│   │   ├── services/   # Desktop-specific services
│   │   └── shared/     # Links to shared services
│   └── package.json    # Node.js dependencies
├── services/           # Desktop-specific service implementations
├── lancedb_client/     # Local LanceDB client for desktop
└── README.md           # Desktop app documentation
```

**Shared Architecture:**
- Uses `src/ui-shared/` components for consistent UI
- Shares business logic from `src/services/`
- Desktop-specific features: voice processing, system integration

### Technology Stack
- **Framework**: Tauri 1.0.0 + React 18.2.0 + TypeScript
- **Backend**: Rust + Shared Python backend services
- **Storage**: Local file system with encryption + LanceDB
- **Build Tool**: esbuild + Vite

### Key Features
- Local-first architecture with LanceDB storage
- Encrypted local storage
- Voice/audio processing
- Wake word detection
- Offline functionality
- Shared services with web app
- Platform-specific optimizations

### Configuration
- **TypeScript Config**: Includes shared `src/services/**/*` and `src/ui-shared/**/*`
- **Path Mapping**: `@shared-*` aliases for shared services (`@shared-ai/*`, `@shared-integrations/*`, `@shared-workflows/*`, `@shared-utils/*`)
- **Build**: esbuild with external package handling for shared services
- **Backend**: Shared Python backend services on port 8084
- **External Packages**: Chakra UI, React, Emotion, Framer Motion, and shared service packages

### Directory Structure
```
desktop/
├── tauri/                           # Tauri application
│   ├── src/
│   │   ├── components/              # Desktop-specific components
│   │   ├── services/                # Desktop-specific services
│   │   ├── hooks/                   # Custom React hooks
│   │   ├── types/                   # TypeScript types
│   │   └── integrations/            # Desktop integration components
│   ├── src-tauri/
│   │   ├── src/                     # Rust backend code
│   │   └── Cargo.toml               # Rust dependencies
│   ├── package.json                 # Frontend dependencies with shared service externals
│   ├── esbuild.config.js            # Build configuration
│   └── tauri.config.ts              # Tauri app configuration
├── services/                        # Desktop-specific service implementations
│   ├── lancedbService.ts            # Local LanceDB integration
│   └── desktopStorageService.ts     # Desktop-specific storage
├── lancedb_client/                  # Local LanceDB client
└── README.md                        # Desktop app documentation
```

## 📁 Backend Directory Structure

### Main Backend (`backend/`)
```
backend/
├── 📄 Main Application Files
│   ├── main_api_app.py              # Main Flask/FastAPI application
│   ├── api_service.py               # Core API service
│   ├── requirements.txt             # Python dependencies
│   └── requirements_stripe.txt      # Stripe-specific dependencies
│
├── 🔧 Core Services (`core/`)
│   ├── config.py                    # Application configuration
│   ├── database_manager.py          # Database operations
│   ├── lancedb_handler.py           # Vector database operations
│   ├── auth_service.py              # Authentication service
│   └── crypto.py                    # Encryption utilities
│
├── 🔗 Integration Services (`integrations/`)
│   ├── airtable_service.py          # Airtable integration
│   ├── asana_service.py             # Asana integration
│   ├── dropbox_service.py           # Dropbox integration
│   ├── github_service.py            # GitHub integration
│   ├── gmail_service.py             # Gmail integration
│   ├── hubspot_service.py            # HubSpot integration
│   ├── jira_service.py              # Jira integration
│   ├── linear_service.py             # Linear integration
│   ├── notion_service.py             # Notion integration
│   ├── outlook_service.py           # Outlook integration
│   ├── salesforce_service.py         # Salesforce integration
│   ├── slack_service.py             # Slack integration
│   ├── teams_service.py              # Microsoft Teams integration
│   ├── stripe_service.py            # Stripe integration
│   ├── google_drive_service.py      # Google Drive integration
│   ├── onedrive_service.py          # OneDrive integration
│   ├── microsoft365_service.py      # Microsoft 365 integration
│   ├── box_service.py               # Box integration
│   └── [25+ core service integrations]
│
├── 🤖 AI Services (`ai/`)
│   ├── nlu_service.py               # Natural Language Understanding
│   ├── skill_service.py             # Skill management
│   ├── orchestration_service.py     # Workflow orchestration
│   └── memory_service.py            # Memory management
│
├── 🔄 Consolidated Services (`consolidated/`)
│   ├── unified_integration_service.py
│   ├── enhanced_workflow_service.py
│   └── comprehensive_api_service.py
│
├── 🧪 Tests (`tests/`)
│   ├── integration_tests/
│   ├── unit_tests/
│   └── test_utilities/
│
├── 🛠️ Scripts (`scripts/`)
│   ├── deployment/
│   ├── testing/
│   └── utilities/
│
└── 📊 Data & Shared Resources
    ├── data/                        # Data files and resources
    ├── shared/                      # Shared utilities
    └── desktop/                     # Desktop-specific backend services
    └── [20+ core services and routes]
```

### Integration Backend (`backend/integrations/` - Now part of main backend)
```
backend/integrations/
├── ai_enhanced_api_routes.py        # AI-enhanced API routes
├── atom_ai_integration.py           # Core AI integration
├── atom_chat_interface.py           # Chat interface implementation
├── atom_enterprise_security_service.py # Enterprise security
├── asana_routes.py                   # Asana API routes
├── dropbox_routes.py                 # Dropbox API routes
├── freshdesk_routes.py              # Freshdesk API routes
├── github_integration_complete.md   # GitHub integration docs
├── hubspot_routes.py                # HubSpot API routes
├── jira_oauth_api.py                # Jira OAuth
├── mailchimp_routes.py              # Mailchimp API routes
├── microsoft_teams_integration_complete.md # Teams docs
├── outlook_routes.py                # Outlook API routes
├── slack_api_documentation.md        # Slack API docs
├── slack_final_status_report.md     # Slack status report
├── stripe_integration_complete.md    # Stripe integration docs
└── [33+ service-specific route files]
```

### AI Backend Services (`backend/ai/`)
```
backend/ai/
├── automation_engine.py             # Workflow automation engine
├── data_intelligence.py             # Data intelligence service
├── nlp_engine.py                     # Natural language processing
├── ai_enhanced_service.py           # AI service integration
└── ai_routes.py                     # AI API routes
```

### Consolidated Services (`backend/consolidated/`)
```
backend/consolidated/
├── core/                            # Core backend functionality
│   ├── database_manager.py
│   └── auth_service.py
├── integrations/                    # External service integrations
│   ├── asana_service.py
│   ├── asana_routes.py
│   ├── dropbox_service.py
│   ├── dropbox_routes.py
│   ├── outlook_service.py
│   ├── outlook_routes.py
│   ├── google_drive_service.py
│   ├── google_drive_routes.py
│   ├── onedrive_service.py
│   ├── onedrive_routes.py
│   ├── freshdesk_service.py
│   ├── freshdesk_routes.py
│   ├── microsoft365_service.py
│   ├── microsoft365_routes.py
│   └── [180+ other integrations]
├── workflows/                       # Workflow engine
└── api/                             # API endpoints
```

## 🚀 Integration Categories & Status

### 📄 Document Storage Integrations
- **Google Drive**: ✅ Full integration with OAuth & LanceDB memory
- **OneDrive**: ✅ Complete Microsoft Graph API integration with LanceDB memory
- **Dropbox**: ✅ Enhanced service with file operations and webhooks
- **Box**: ✅ Enterprise file sharing with advanced security
- **Microsoft 365**: ✅ Unified platform with Teams, Outlook, OneDrive, SharePoint

### 💬 Communication & Customer Service Integrations
- **Slack**: ✅ Enhanced API with workflow automation and real-time events
- **Microsoft Teams**: ✅ Complete integration with meeting management
- **Outlook**: ✅ Email and calendar management with advanced features
- **Gmail**: ✅ Enhanced service with workflows and automation
- **Discord**: ✅ Community and team communication platform

### 🎯 Productivity & Work OS Integrations
- **Asana**: ✅ Project and task management with advanced workflows
- **Notion**: ✅ Database and page operations with real-time sync
- **Linear**: ✅ Modern issue tracking for development teams
- **Monday.com**: ✅ Complete Work OS platform with enterprise features
- **Microsoft 365**: ✅ Enterprise productivity platform with Teams, Outlook, OneDrive, SharePoint
- **Airtable**: ✅ Cloud database platform with workflow automation

### 💻 Development Integrations
- **GitHub**: ✅ Repository and issue management with advanced features
- **GitLab**: ✅ Complete DevOps integration with CI/CD
- **Jira**: ✅ Agile project management with custom workflows

### 🏢 CRM & Marketing Integrations
- **Salesforce**: ✅ Complete CRM with real-time webhooks and advanced analytics
- **HubSpot**: ✅ All-in-one growth platform with marketing automation

### 💰 Financial & Accounting Integrations
- **Stripe**: ✅ Payment processing and financial management

**🔢 Total Integration Count: 25+ Complete Platforms**

**🛠️ Desktop Build Configuration:**
- **Build Tool**: esbuild with platform=browser
- **Bundle Format**: ESM with external package handling
- **Shared Services**: Externalized via `--external:@shared-*` flags
- **UI Framework**: Chakra UI + React 18 + TypeScript
- **Path Resolution**: TypeScript path mappings for shared services
- **Development**: Hot reload with esbuild watch mode

**🆕 Recently Added Integration Services:**
- **Google Drive Service**: Complete file operations with OAuth authentication
- **OneDrive Service**: Microsoft Graph API integration with file management
- **Microsoft 365 Service**: Unified platform integration (Teams, Outlook, Calendar)
- **Box Service**: Enterprise file sharing with advanced security features
- **TypeScript Services**: Frontend integration services for all new platforms

**⚡ Advanced Features:**
- Real-time webhooks for key services
- OAuth 2.0 authentication across platforms
- LanceDB vector memory for document processing
- Cross-platform workflow automation
- Enterprise-grade security and compliance
- AI-powered insights and automation
- Shared service architecture between web and desktop
- Complete TypeScript integration services for all platforms
- Mock implementations for development and testing
- Health monitoring and capability discovery endpoints

## 🔄 LanceDB Memory Pipeline Architecture

### Memory Storage Pipeline
1. **Ingestion**: Documents, conversations, and user data from integrations
2. **Processing**: Text extraction and chunking (Google Drive, OneDrive, etc.)
3. **Embedding**: Vector generation using sentence-transformers
4. **Storage**: LanceDB vector storage with metadata and source tracking
5. **Retrieval**: Semantic search and context retrieval across all integrations

### Memory Categories
- **Conversation Memory**: Chat history and context
- **Document Memory**: Processed documents and files from integrations
- **User Memory**: User preferences and behavior
- **Workflow Memory**: Automated workflow history
- **Integration Memory**: Service-specific data (Google Drive, OneDrive, etc.)

## 🛠️ Core Technologies & Libraries

### Backend Technologies
- **Python 3.8+**: Core programming language
- **Flask**: Web framework with REST API
- **SQLAlchemy**: Database ORM
- **LanceDB**: Vector database for AI memory
- **Pydantic**: Data validation and settings management
- **Microsoft Graph API**: OneDrive integration
- **Google Drive API**: Google Drive integration

### Frontend Technologies
- **TypeScript**: Type-safe JavaScript
- **React 18**: UI library with hooks
- **Next.js 15**: React framework with SSR
- **Chakra UI**: Component library
- **Tauri**: Desktop app framework

### Database & Storage
- **SQLite**: Local development database
- **PostgreSQL**: Production database
- **LanceDB**: Vector database for embeddings
- **Local File System**: Desktop app storage

### Authentication & Security
- **OAuth 2.0**: External service authentication (Google, Microsoft, etc.)
- **JWT**: Stateless authentication tokens
- **AES Encryption**: Data encryption at rest
- **CORS**: Cross-origin resource sharing
- **Azure AD**: Microsoft OneDrive authentication
- **Google Cloud**: Google Drive authentication

## 🧪 Testing Strategy

### Backend Testing
- **Unit Tests**: pytest for individual components
- **Integration Tests**: API endpoint testing
- **Mock Services**: External service simulation
- **Integration Testing**: Google Drive, OneDrive, and other service testing

### Frontend Testing
- **Unit Tests**: Jest + React Testing Library
- **Component Tests**: Isolated component testing
- **E2E Tests**: Playwright for user workflows

## 📦 Deployment Architecture

### Development Environment
- **Local Development**: Docker Compose for backend services
- **Frontend**: Next.js development server with hot reload
- **Desktop**: Tauri development with embedded Python backend
- **Database**: PostgreSQL for production, SQLite for development

### Production Environment
- **Backend**: Docker containers with Python FastAPI/Flask
- **Frontend**: Next.js static export or Vercel deployment
- **Desktop**: Tauri builds for Windows, macOS, Linux
- **Database**: PostgreSQL with LanceDB vector storage
- **Storage**: Local file system for desktop, cloud storage for web

### CI/CD Pipeline
- **Automated Testing**: Vitest, Playwright, pytest
- **Build Automation**: GitHub Actions for all platforms
- **Docker Images**: Multi-stage builds for optimized containers
- **Deployment**: Automated deployment to production environments

## 🔧 Configuration & Environment Files

### Backend Configuration (`backend/`)
```
backend/
├── requirements.txt                 # Core Python dependencies
├── requirements_stripe.txt          # Stripe-specific dependencies
├── .env.template                    # Environment template
└── config.py                        # Application configuration
```

### Frontend Configuration (`frontend-nextjs/`)
```
frontend-nextjs/
├── .env.example                     # Environment template
├── .env.template                    # Development environment template
├── package.json                     # Dependencies and scripts
└── next.config.js                   # Next.js configuration
```

### Desktop Configuration (`desktop/tauri/`)
```
desktop/tauri/
├── package.json                     # Frontend dependencies with shared externals
├── esbuild.config.js                # Build configuration
├── tauri.config.ts                  # Tauri app configuration
├── tsconfig.json                    # TypeScript with shared path mappings
└── .env.google.example              # Google integration template
```

### Shared Configuration (`config/`)
```
config/
├── .env.example                     # Base environment template
├── .env.development.template        # Development environment
├── .env.production.template         # Production environment
├── .env.credentials.template        # Credentials template
├── .env.unified.template            # Unified configuration
└── .env.integrations                # Integration-specific settings
```

### Docker Configuration
```
backend/docker/
├── docker-compose.yaml              # Main Docker Compose
├── docker-compose.local.yaml        # Local development
├── docker-compose.test.yml          # Testing environment
└── docker-compose.local.yml         # Local services

frontend-nextjs/
├── Dockerfile.production            # Production Docker image
└── project/functions/Dockerfile     # Serverless functions

desktop/tauri/
└── Dockerfile                       # Desktop app Docker image
```

### Environment Variables
- **Database**: `DATABASE_URL`, `LANCEDB_PATH`
- **Authentication**: `JWT_SECRET`, `OAUTH_CLIENT_*`
- **AI Services**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- **Integrations**: `*_CLIENT_ID`, `*_CLIENT_SECRET`
- **Security**: `ENCRYPTION_KEY`, `CORS_ORIGINS`

### Development Environment
- **Local Development**: Docker Compose for services
- **Hot Reloading**: Automatic restart on code changes
- **Debugging**: Integrated debugging tools

### Production Environment
- **Containerization**: Docker for consistent deployment
- **Orchestration**: Kubernetes for scaling
- **Monitoring**: Prometheus + Grafana

### CI/CD Pipeline
- **Automated Testing**: GitHub Actions
- **Build Automation**: Multi-stage Docker builds
- **Deployment**: Blue-green deployment strategy

## 📊 Performance Metrics

### System Performance
- **API Response Time**: < 200ms for core endpoints
- **Memory Usage**: Optimized for resource efficiency
- **Concurrent Users**: Scalable architecture

### Integration Performance
- **OAuth Flow**: < 5 seconds for authentication
- **File Upload**: Streaming for large files
- **Search Performance**: Sub-second vector search
- **Document Ingestion**: Parallel processing for Google Drive/OneDrive files
- **Memory Search**: Cross-integration semantic search

### Scalability Metrics
- **Horizontal Scaling**: Stateless API design
- **Database Scaling**: Read replicas and caching
- **CDN Integration**: Static asset delivery
- **Integration Scaling**: Parallel service processing
- **Memory Scaling**: Distributed vector search

## 🔒 Security & Compliance

### Data Protection
- **Encryption**: AES-256 for data at rest
- **TLS/SSL**: HTTPS for all communications
- **Token Security**: Short-lived access tokens

### Compliance Standards
- **GDPR**: User data protection and privacy
- **SOC 2**: Security and availability controls
- **HIPAA**: Healthcare data compliance (planned)

### Security Features
- **Rate Limiting**: API abuse prevention
- **Input Validation**: SQL injection protection
- **Audit Logging**: Comprehensive activity tracking

## 🚀 Future Development Roadmap

### Short-term (1-3 months)
- Enhanced mobile responsiveness
- Additional integration services
- Improved developer documentation
- Advanced workflow automation
- Real-time collaboration features

### Medium-term (3-6 months)
- Microservices architecture
- Advanced AI agent capabilities
- Enterprise feature set
- Performance optimization for 1000+ users
- Advanced monitoring and analytics

### Long-term (6-12 months)
- Mobile applications
- Advanced analytics dashboard
- Marketplace for custom integrations
- AI-powered workflow recommendations
- Enterprise-grade security enhancements

## 📚 Documentation & Resources

### File Organization System

The project includes an automated file organization system to maintain clean structure:

```
.file-organization-rules.json    # Rules for file categorization
scripts/organize-files.py        # Automation script
```

**Key Commands:**
```bash
# Validate current structure
python scripts/organize-files.py --validate

# Organize files automatically
python scripts/organize-files.py --organize

# Dry run (show what would be organized)
python scripts/organize-files.py --organize --dry-run

# Create git pre-commit hook
python scripts/organize-files.py --create-hook
```

**Organization Categories:**
- `docs/` - Documentation files (.md, .txt)
- `scripts/` - Shell scripts and automation (.sh)
- `tests/` - Test files (test_*.py, *.test.*)
- `backups/` - Backup directories
- `logs/` - Log files (.log)
- `temp/` - Temporary files and caches
- `deployment/` - Deployment configuration
- `integration-tests/` - Integration test results
- `config/` - Configuration files (.json, .env)
- `data/` - Database schemas and data files

### Code Documentation
- **API Documentation**: OpenAPI/Swagger specs
- **Architecture Docs**: System design and patterns
- **Migration Guides**: Version upgrade instructions

### Developer Resources
- **Setup Guides**: Local development environment
- **API Reference**: Complete endpoint documentation
### Integration Guides: Service-specific implementation
- **Google Drive Integration Guide**: Complete setup and usage
- **OneDrive Integration Guide**: Microsoft Graph API integration
- **LanceDB Memory Integration**: Document processing and search

### User Documentation
- **Getting Started**: Quick start guides
- **Feature Guides**: Detailed usage instructions
- **Troubleshooting**: Common issues and solutions

## 📞 Support & Contact

### Technical Support
- **GitHub Issues**: Bug reports and feature requests
- **Community Forum**: User discussions and help
- **Email Support**: Direct technical assistance

### Development Team
- **Core Maintainers**: Primary code contributors
- **Integration Specialists**: Service integration experts
- **Documentation Team**: User and developer docs
- **Memory System Engineers**: LanceDB and vector search specialists

---

*Last Updated: November 2025*
*Version: 3.0 - Complete Platform with 33+ Integrations*
*Production Status: ✅ Ready with Advanced AI and Automation*
*All Core Services: ✅ Operational with Real-time Webhooks*