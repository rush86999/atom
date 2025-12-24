# ATOM Architecture Documentation

## Overview

ATOM is a comprehensive AI-powered task orchestration and management platform with web and desktop applications. This document describes the current architecture focusing on the unified authentication system and integration framework.

## Architecture Overview

```
atom/
├── frontend-nextjs/          # Web + Desktop application (Next.js + TypeScript)
├── src-tauri/                # Desktop wrapper (Tauri + Rust)
├── src/                      # Shared frontend services and components
├── backend/                  # Backend services (Python FastAPI)
│   ├── core/                 # Core backend modules
│   ├── integrations/         # 100+ integration services
│   ├── ai/                   # AI/LLM services
│   ├── accounting/           # Financial ledger and automations
│   ├── sales/                # CRM and Sales intelligence
│   └── migrations/           # Database migrations
├── packages/                 # Shared packages (AI, integrations, utils)
└── docs/                     # Documentation

```

## Application Architecture

### Unified Frontend Application (`frontend-nextjs/`)

**Technology Stack:**
- Next.js 15.5.0 with TypeScript
- React 18.2.0
- Chakra UI + Tailwind CSS (mixed - consolidation planned)
- NextAuth for authentication

**Dual Purpose:**
- **Web App:** Standalone Next.js progressive web application
- **Desktop App:** Same codebase wrapped by Tauri (`src-tauri/`)

**Key Features:**
- 48 integration UI pages
- Unified task, calendar, and search experiences
- Real-time collaboration
- OAuth 2.0 social login (Google, GitHub)
- Password reset functionality

**Backend Connection:**
- REST API to `backend/` on port 5059
- PostgreSQL database for persistent storage
- Direct SQL queries via `lib/db.ts`

### Desktop Application (`src-tauri/`)

**Technology Stack:**
- Tauri wrapper around Next.js frontend
- Rust backend for system integration
- Same UI as web app

**Key Features:**
- Local-first architecture  
- Native system integration
- File system access
- Offline functionality

## Authentication & Security

### NextAuth Production System
**Migration Completed:** Nov 23, 2025

**Features:**
- ✅ Email/password authentication with bcrypt hashing
- ✅ OAuth providers (Google, GitHub)
- ✅ User registration API
- ✅ Password reset flow (forgot password + token-based reset)
- ✅ JWT session management
- ✅ PostgreSQL-backed user storage

**Removed:**
- ❌ Supabase Auth (deprecated)
- ❌ SuperTokens (deprecated)
- ❌ Mock users (deprecated)

**Key Files:**
- `frontend-nextjs/lib/auth.ts` - NextAuth configuration
- `frontend-nextjs/lib/db.ts` - Direct PostgreSQL connection
- `backend/migrations/001_create_users_table.sql` - User schema
- `backend/migrations/002_create_password_reset_tokens.sql` - Reset tokens

**API Endpoints:**
- `POST /api/auth/register` - User registration
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset with token
- `/api/auth/callback/{provider}` - OAuth callbacks

### OAuth Integration Storage
- **Tokens:** Encrypted in database with `ATOM_ENCRYPTION_KEY`
- **Refresh:** Automatic token refresh via OAuth providers
- **Revocation:** User can revoke access per integration

## Service Organization

### Frontend Services (`src/services/`)

Organized by domain:

```
src/services/
├── ai/                       # AI and ML services
│   ├── ChatOrchestrationService.ts
│   ├── hybridLLMService.ts
│   └── nluService.ts
├── integrations/             # External service integrations
│   ├── apiKeyService.ts
│   ├── authService.ts
│   └── connection-status-service.ts
└── workflows/                # Workflow automation
    ├── autonomousWorkflowService.ts
    └── workflowService.ts
```

### Backend Services (`backend/`)

Modular FastAPI application:

```
backend/
├── core/                     # Core backend functionality
│   ├── integration_loader.py    # Dynamic integration loading
│   ├── api_routes.py            # Core API endpoints
│   ├── workflow_ui_endpoints.py
│   ├── unified_task_endpoints.py
│   └── database_manager.py
├── integrations/             # 88 integration route files (344 total files)
│   ├── *_routes.py          # FastAPI route definitions
│   └── *_service.py         # Business logic
├── ai/                       # AI services
│   └── Multi-provider LLM support
├── migrations/               # Database schema migrations
├── accounting/               # Financial Engine
│   ├── ledger.py             # Double-entry ledger engine
│   ├── categorizer.py        # AI-driven transaction categorization
│   └── fpa_service.py        # Forecasting and strategic planning
└── sales/                    # CRM & Sales Intelligence
    ├── lead_manager.py       # Lead intake and AI scoring
    ├── intelligence.py       # Deal health and risk analysis
    ├── call_service.py       # Meeting transcription and task extraction
    └── order_to_cash.py      # Sales-to-Finance automation bridge
```

## Storage Architecture

### Web Application Storage
- **Primary**: PostgreSQL database
  - Users and authentication
  - Application data
  - Integration metadata
- **Cache**: Redis (optional)
- **Files**: Cloud storage integrations (Google Drive, Dropbox, etc.)

### Desktop Application Storage  
- **Primary**: Same PostgreSQL database as web
- **Local Cache**: Encrypted local storage via Tauri
- **Files** Platform-specific app data directories

## Integration Patterns

### Supported Integrations (35-40 services)

**Project Management:** Asana, Jira, Monday.com, Notion, Linear, Trello, Airtable, ClickUp
**Communication:** Slack, Teams, Zoom, Discord, Gmail, Outlook, WhatsApp
**Storage:** Google Drive, Dropbox, OneDrive, Box, SharePoint  
**CRM:** Salesforce, HubSpot, Zendesk, Freshdesk, Intercom
**Development:** GitHub, GitLab, Bitbucket, Figma
**Finance:** Stripe, QuickBooks, Xero, Shopify
**AI/Voice:** Deepgram, ElevenLabs, AssemblyAI

### Authentication Pattern
All integrations use OAuth 2.0:

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