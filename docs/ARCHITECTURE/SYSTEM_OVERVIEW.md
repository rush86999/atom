# ATOM Architecture Documentation

## Overview

ATOM is a multi-platform AI-powered task orchestration and management system with both web and desktop applications. This document describes the reorganized architecture after consolidation.

## Architecture Overview

```
atom/
├── frontend-nextjs/          # Web application (Next.js + TypeScript)
├── desktop/tauri/            # Desktop application (Tauri + React + TypeScript)
├── src/                      # Shared frontend services (TypeScript)
├── backend/                  # Backend services (Python)
│   ├── consolidated/         # Consolidated backend structure
│   ├── python-api-service/   # Main backend for web app
│   └── integrations/         # Integration services
└── shared/                   # Shared utilities and configurations
```

## Application Architecture

### Frontend Web Application (`frontend-nextjs/`)

**Technology Stack:**
- Next.js 15.5.0 with TypeScript
- React 18.2.0
- Chakra UI for components
- Various integration libraries (Google APIs, Stripe, etc.)

**Key Features:**
- Multi-tenant web interface
- Real-time collaboration
- Integration with external services
- Database-backed persistent storage

**Backend Connection:**
- Connects to `backend/python-api-service` on port 5058
- Uses backend database for persistent storage
- REST API communication

### Desktop Application (`desktop/tauri/`)

**Technology Stack:**
- Tauri 1.0.0 (Rust backend + WebView frontend)
- React 18.2.0 with TypeScript
- Local file system storage with encryption
- Embedded Python backend

**Key Features:**
- Local-first architecture
- Encrypted local storage
- Voice/audio processing capabilities
- Wake word detection
- Offline functionality

**Backend Connection:**
- Embedded Python backend in `src-tauri/python-backend/`
- Local encrypted JSON storage via Tauri APIs
- File system access for local data persistence

## Service Organization

### Frontend Services (`src/services/`)

Organized by domain for better maintainability:

```
src/services/
├── ai/                          # AI and ML services
│   ├── ChatOrchestrationService.ts
│   ├── hybridLLMService.ts
│   ├── llmSettingsManager.ts
│   ├── nluHybridIntegrationService.ts
│   ├── nluService.ts
│   ├── openaiService.ts
│   ├── skillService.ts
│   ├── financeAgentService.ts
│   ├── tradingAgentService.ts
│   └── trading/                 # Trading-specific services
├── integrations/                # External service integrations
│   ├── apiKeyService.ts
│   ├── authService.ts
│   └── connection-status-service.ts
├── workflows/                   # Workflow automation
│   ├── autonomousWorkflowService.ts
│   └── workflowService.ts
└── utils/                       # Utility services (to be populated)
```

### Backend Services (`backend/`)

Consolidated structure for better code reuse:

```
backend/
├── consolidated/               # Consolidated backend services
│   ├── core/                   # Core backend functionality
│   │   ├── database_manager.py
│   │   └── auth_service.py
│   ├── integrations/           # External service integrations
│   │   ├── asana_service.py
│   │   ├── asana_routes.py
│   │   ├── dropbox_service.py
│   │   ├── dropbox_routes.py
│   │   ├── outlook_service.py
│   │   └── outlook_routes.py
│   ├── workflows/              # Workflow engine
│   └── api/                    # API endpoints (to be populated)
├── python-api-service/         # Main backend for web app
└── integrations/               # Legacy integration services
```

## Storage Architecture

### Web Application Storage
- **Primary**: PostgreSQL/SQLite database via backend
- **Cache**: In-memory caching for performance
- **Files**: Cloud storage integration (Dropbox, Google Drive, etc.)
- **Sessions**: Backend-managed user sessions

### Desktop Application Storage
- **Primary**: Encrypted JSON files in app data directory
- **Encryption**: AES encryption using crypto-js
- **Location**: Platform-specific app data directories
- **Backup**: Manual export/import capabilities

## Integration Patterns

### External Service Integrations

**Supported Services:**
- Asana (project management)
- Dropbox (file storage)
- Outlook (email/calendar)
- GitHub (code management)
- Slack (team communication)
- Jira (issue tracking)
- Notion (documentation)
- And 180+ other services

**Authentication:**
- OAuth 2.0 for external services
- API key management with encryption
- Token refresh and validation
- Secure credential storage

### Communication Patterns

**Web App:**
- REST APIs for synchronous operations
- WebSocket for real-time updates
- Server-Sent Events for notifications

**Desktop App:**
- Inter-process communication (Tauri commands)
- Local HTTP server for embedded backend
- File system watchers for local changes

## Development Workflow

### Starting Development Environment

```bash
# Start all services
./start-dev.sh

# Start backend only
./start-backend.sh

# Start desktop app
cd desktop/tauri && npm run dev
```

### Service Ports

- **Frontend**: http://localhost:3000
- **Python API**: http://localhost:5058
- **Workflows API**: http://localhost:8003
- **Desktop Backend**: http://localhost:8084

## Deployment

### Web Application
- Docker containerization
- Cloud deployment (AWS, GCP, Azure)
- Database migrations
- Environment-based configuration

### Desktop Application
- Cross-platform builds (Windows, macOS, Linux)
- Code signing for distribution
- Auto-update mechanisms
- App store deployment

## Security Considerations

### Data Protection
- Encryption at rest for sensitive data
- Secure API key storage
- OAuth token management
- Regular security audits

### Access Control
- Role-based access control (RBAC)
- Multi-tenant data isolation
- API rate limiting
- Audit logging

## Monitoring and Observability

### Metrics Collection
- Application performance monitoring
- Error tracking and reporting
- User behavior analytics
- Integration health checks

### Logging
- Structured logging across all services
- Centralized log aggregation
- Real-time monitoring dashboards
- Alerting for critical issues

## Future Architecture Directions

### Planned Improvements
- Microservices architecture for scalability
- Event-driven architecture for real-time features
- GraphQL API for flexible data queries
- Edge computing for performance optimization

### Technology Evolution
- Migration to newer React patterns
- Enhanced TypeScript usage
- Improved testing strategies
- Better developer tooling

---

*This document is maintained by the ATOM development team. Last updated: 2025*