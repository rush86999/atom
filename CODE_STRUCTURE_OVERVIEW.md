# ATOM Agent Memory System - Complete Code Structure Overview

## 🏗️ System Architecture

```
ATOM Agent Memory System
├── Frontend Web App (Next.js + TypeScript)
│   ├── Uses shared src/services for business logic
│   ├── Custom UI components
│   ├── Integration components (Google Drive, OneDrive, etc.)
│   └── Backend API integration
├── Desktop App (Tauri + React + TypeScript)
│   ├── Uses shared src/services for business logic
│   ├── Desktop-specific UI components
│   └── Embedded Python backend
├── Shared Services (TypeScript)
│   ├── AI & ML Services
│   ├── Integration Services
│   ├── Workflow Services
│   └── Utility Services
├── Backend API Service (Python/Flask)
│   ├── Core API Endpoints
│   ├── Integration Services (180+ services)
│   ├── LanceDB Memory Pipeline
│   ├── OAuth Authentication
│   └── Document Processing Pipeline
└── Storage & Memory
    ├── LanceDB (Vector Database)
    ├── Local File Storage (Desktop)
    ├── Database Storage (Web)
    └── Integration Memory (Google Drive, OneDrive, etc.)
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
└── oneDriveService.ts               # OneDrive integration
```

### 🔄 Workflow Services (`src/services/workflows/`)
```
workflows/
├── autonomousWorkflowService.ts     # Autonomous workflow execution
└── workflowService.ts               # Core workflow management
```

### 🛠️ Utility Services (`src/services/utils/`)
```
utils/
└── config.ts                        # Shared configuration management
```

## 📁 Frontend Web Application (`frontend-nextjs/`)

### Technology Stack
- **Framework**: Next.js 15.5.0 with TypeScript
- **UI Library**: React 18.2.0 + Chakra UI
- **State Management**: React Context + Custom Hooks
- **Build Tool**: Next.js built-in + Webpack

### Key Features
- Multi-tenant web interface
- Real-time collaboration
- Integration with external services
- Database-backed persistent storage

### Configuration
- **Next.js Config**: Transpiles shared `src/` directory
- **Path Mapping**: `@shared-*` aliases for shared services
- **API Integration**: Connects to backend on port 5058

### Directory Structure
```
frontend-nextjs/
├── src/
│   ├── components/                  # React components
│   ├── contexts/                    # React contexts
│   ├── config.js                    # App configuration
│   └── constants.ts                 # App constants
├── pages/                           # Next.js pages
│   ├── integrations/                # Integration-specific pages
│   │   ├── gdrive.tsx              # Google Drive integration
│   │   ├── onedrive.tsx            # OneDrive integration
│   │   └── [other integrations]
│   └── google-drive.tsx             # Google Drive main page
├── public/                          # Static assets
└── package.json                     # Dependencies
```

## 📁 Desktop Application (`desktop/tauri/`)

### Technology Stack
- **Framework**: Tauri 1.0.0 + React 18.2.0 + TypeScript
- **Backend**: Rust + Embedded Python
- **Storage**: Local file system with encryption
- **Build Tool**: esbuild

### Key Features
- Local-first architecture
- Encrypted local storage
- Voice/audio processing
- Wake word detection
- Offline functionality

### Configuration
- **TypeScript Config**: Includes shared `src/services/**/*`
- **Path Mapping**: `@shared-*` aliases for shared services
- **Backend**: Embedded Python backend on port 8084

### Directory Structure
```
desktop/tauri/
├── src/
│   ├── components/                  # Desktop-specific components
│   ├── services/                    # Desktop-specific services
│   ├── hooks/                       # Custom React hooks
│   ├── types/                       # TypeScript types
│   └── integrations/                # Desktop integration components
├── src-tauri/
│   ├── python-backend/              # Embedded Python backend
│   ├── src/                         # Rust backend code
│   └── Cargo.toml                   # Rust dependencies
└── package.json                     # Frontend dependencies
```

## 📁 Backend Directory Structure

### Main Backend (`backend/python-api-service/`)
```
backend/python-api-service/
├── 📄 Main Application Files
│   ├── main_api_app.py              # Main Flask application
│   ├── api_service.py               # Core API service
│   ├── comprehensive_integration_api.py
│   └── startup.py                   # Application startup
│
├── 🔧 Configuration & Environment
│   ├── config.py                    # Application configuration
│   ├── logging_config.py            # Logging configuration
│   └── constants.py                 # Application constants
│
├── 🗄️ Database & Storage
│   ├── models/                      # SQLAlchemy database models
│   ├── database_manager.py          # Database operations
│   └── lancedb_handler.py           # Vector database operations
│
├── 🔐 Authentication & Security
│   ├── auth_service.py              # Authentication service
│   ├── crypto.py                    # Encryption utilities
│   └── oauth_integration.py         # OAuth integration
│
└── 🔗 Integration Services
    ├── asana_service.py             # Asana integration
    ├── dropbox_service.py           # Dropbox integration
    ├── outlook_service.py           # Outlook integration
    ├── google_drive_service.py      # Google Drive integration
    ├── onedrive_service.py          # OneDrive integration
    ├── onedrive_routes.py           # OneDrive API routes
    ├── auth_handler_onedrive.py     # OneDrive OAuth authentication
    ├── onedrive_health_handler.py   # OneDrive health monitoring
    ├── onedrive_integration_register.py # OneDrive registration
    ├── onedrive_document_processor.py   # OneDrive document processing
    └── [180+ other integrations]
```

### Consolidated Backend (`backend/consolidated/`)
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
│   └── onedrive_routes.py
├── workflows/                       # Workflow engine
└── api/                             # API endpoints
```

## 🚀 Integration Categories & Status

### 📄 Document Storage Integrations
- **Dropbox**: ✅ Enhanced service with file operations
- **Google Drive**: ✅ Full integration with OAuth & LanceDB memory
- **OneDrive**: ✅ Complete Microsoft Graph API integration with LanceDB memory
- **Box**: ✅ Enterprise file sharing

### 💬 Communication Integrations
- **Slack**: ✅ Enhanced API with workflow automation
- **Microsoft Teams**: ✅ Complete integration
- **Outlook**: ✅ Email and calendar management
- **Gmail**: ✅ Enhanced service with workflows

### 🎯 Productivity Integrations
- **Asana**: ✅ Project and task management
- **Notion**: ✅ Database and page operations
- **Trello**: ✅ Board and card management
- **Linear**: ✅ Issue tracking

### 💻 Development Integrations
- **GitHub**: ✅ Repository and issue management
- **GitLab**: ✅ Complete DevOps integration
- **Jira**: ✅ Agile project management
- **Figma**: ✅ Design collaboration

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

*Last Updated: 2025*
*Version: 2.1 - Enhanced Integration Architecture*
*OneDrive Integration: Complete with LanceDB memory system*
*Google Drive Integration: Enhanced with memory features*