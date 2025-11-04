# CRUSH.md - ATOM AI Assistant Development Guide

## 🚀 Project Overview

ATOM is a comprehensive AI assistant platform with a hybrid architecture combining Next.js frontend, Python FastAPI backend, and Tauri desktop application. The system features multi-service orchestration, OAuth integrations, and advanced AI capabilities.

## 🏗️ Architecture

### Core Components
- **Frontend**: Next.js 15.5 + TypeScript + Chakra UI/Material-UI
- **Backend**: Python 3.11 + Flask/FastAPI + PostgreSQL + LanceDB
- **Desktop**: Tauri + React
- **Services**: 15+ containerized microservices
- **Authentication**: OAuth 2.0 + SuperTokens + JWT
- **AI/ML**: OpenAI, local Llama, vector search with LanceDB

### Database Strategy
- **PostgreSQL**: Relational data (users, tasks, OAuth tokens)
- **LanceDB**: Vector embeddings and semantic search
- **Redis**: Caching and session management

## 🛠️ Essential Commands

### Development Setup
```bash
# Clone and initialize submodules
git submodule update --init --recursive

# Setup environment
cp .env.example .env
# Configure your API keys in .env

# Install dependencies
npm install                    # Root dependencies
cd frontend-nextjs && npm install && cd ..  # Frontend dependencies

# Start development services
docker-compose -f backend/docker/docker-compose.yaml up -d

# Start frontend development server
npm run dev
# or
cd frontend-nextjs && npm run dev
```

### Build Commands
```bash
# Build frontend
npm run build

# Build TypeScript services
npm run build:services
npm run build:new-services
npm run build:isolated-services

# Build Tauri desktop app
cd desktop/tauri && cargo build
```

### Testing Commands
```bash
# Run all tests
npm test

# Run comprehensive test suite
npm run test:comprehensive

# Run E2E tests
npm run test:e2e
npm run test:e2e:all
npm run test:e2e:alex
npm run test:e2e:ben
npm run test:e2e:maria

# Run integration tests
npm run test:integration
npm run test:integration:all
npm run test:integration:comprehensive

# Python backend tests
npm run test:python

# Test coverage
npm run test:coverage
```

### Orchestration Commands
```bash
# Start orchestration engine
npm run orchestration

# Orchestration demos
npm run orchestration:demo
npm run orchestration:demo:financial
npm run orchestration:demo:business

# Orchestration management
npm run orchestration:health
npm run orchestration:monitor
npm run orchestration:optimize
npm run orchestration:reset
npm run orchestration:stats
```

### Llama.cpp Setup
```bash
# Setup local LLM
npm run llama:setup
npm run llama:download
npm run llama:download-model
npm run llama:start
npm run llama:stop
npm run llama:status
npm run llama:test
```

### Desktop App Development
```bash
# Tauri development
cd desktop/tauri && npm run tauri dev

# Build desktop app
cd desktop/tauri && npm run tauri build

# Test desktop integration
npm run test:integration:desktop
```

## 📁 Project Structure

```
atom/
├── frontend-nextjs/          # Next.js web application
│   ├── src/                  # React components and pages
│   ├── pages/               # Next.js pages with API routes
│   └── tests/               # Frontend tests
├── src/                     # Core TypeScript services
│   ├── orchestration/        # Agent orchestration engine
│   ├── skills/              # AI skill implementations
│   ├── services/            # Backend services
│   ├── nlu_agents/          # Natural language agents
│   └── ui-shared/          # Shared UI components
├── backend/
│   ├── python-api-service/   # Main Python API service
│   └── docker/              # Docker configurations
├── desktop/
│   └── tauri/               # Desktop application
├── tests/                   # E2E and integration tests
├── deployment/              # Infrastructure as code
└── docs/                   # Documentation
```

## 🔧 Configuration Management

### Environment Variables
Critical environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/atom_development

# Authentication
JWT_SECRET=your_super_secure_jwt_secret_key_here_change_in_production
SUPERTOKENS_POSTGRESQL_CONNECTION_URI=postgresql://...

# AI Services
OPENAI_API_KEY=sk-your-openai-key
DEEPGRAM_API_KEY=your_deepgram_key

# OAuth Providers (10+ supported)
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
MICROSOFT_CLIENT_ID=your_microsoft_client_id
# ... and more OAuth providers

# Service URLs
NEXT_PUBLIC_API_BASE_URL=http://localhost:5058
PYTHON_API_SERVICE_BASE_URL=http://localhost:5058
```

### Path Aliases (TypeScript)
```json
{
  "baseUrl": "./",
  "paths": {
    "@/*": ["src/*"],
    "@components/*": ["components/*"],
    "@lib/*": ["lib/*"],
    "@shared/*": ["../../src/ui-shared/*"]
  }
}
```

## 🧪 Testing Framework

### Frontend Testing
- **Framework**: Jest + React Testing Library
- **Coverage Target**: 85%+
- **Test Files**: `**/*.test.ts`, `**/*.test.tsx`
- **Mock Strategy**: Comprehensive API and browser API mocking

### Backend Testing  
- **Framework**: pytest
- **Health Checks**: Automated service health verification
- **Integration Tests**: Real API endpoint testing

### E2E Testing
- **Framework**: Playwright
- **Personas**: Alex, Ben, Maria (user personas for testing)
- **Test Suites**: Core journeys, workflows, cross-platform scenarios

## 🐳 Docker & Services

### Key Services
- **Traefik**: Reverse proxy with SSL termination
- **PostgreSQL**: Primary database
- **SuperTokens**: Authentication service
- **PostGraphile**: GraphQL API layer
- **Redis**: Caching and session storage
- **MinIO**: S3-compatible object storage
- **Kafka**: Message streaming
- **Python Agent**: AI processing service
- **Functions**: Serverless functions
- **Live Meeting Worker**: Meeting transcription
- **OptaPlanner**: Scheduling optimization

### Service Ports
- Frontend: `3000`
- Backend API: `5058`
- PostgreSQL: `5432`
- Redis: `6379`
- MinIO: `8484` (API), `9001` (Console)
- Traefik Dashboard: `9090`
- PostGraphile: `5000`

## 🔐 Security Patterns

### OAuth Integration
- 10+ OAuth providers supported
- Encrypted token storage using Fernet
- Secure key management via environment variables
- HTTPS required for production OAuth callbacks

### Authentication Flow
1. SuperTokens handles session management
2. JWT tokens for API access
3. OAuth2 for external service integrations
4. Role-based access control (RBAC)

## 🚨 Development Gotchas

### Common Issues
1. **Environment Variables**: Always check `.env.example` for required variables
2. **Database Dependencies**: PostgreSQL must be running before backend services
3. **OAuth HTTPS**: Production OAuth requires HTTPS callbacks
4. **Port Conflicts**: Multiple services use different ports - check docker-compose.yaml
5. **Container Dependencies**: Services have specific startup order requirements
6. **Vector Database**: LanceDB requires separate mounting for persistence
7. **Submodules**: Remember to initialize git submodules

### Service Startup Order
1. PostgreSQL (with health check)
2. Redis, Traefik
3. SuperTokens, PostGraphile
4. Background services (Kafka, MinIO)
5. Application services (Python agent, Functions)
6. Frontend application

## 📊 Monitoring & Debugging

### Health Endpoints
```bash
# Backend health
curl http://localhost:5058/healthz

# Service-specific health
curl http://localhost:5058/api/calendar/health
curl http://localhost:5058/api/gmail/health
```

### Logging Patterns
- Structured logging with JSON format
- Service-specific log files
- Docker container log aggregation
- Real-time monitoring via orchestration tools

## 🎯 Code Patterns & Conventions

### Frontend Patterns
- **Component Architecture**: Atomic design with shared components
- **State Management**: React Context + local state
- **API Communication**: Centralized API helpers with got wrapper
- **Error Handling**: Consistent try-catch with toast notifications
- **Path Aliases**: Extensive use of `@/` for clean imports

### Backend Patterns
- **Service Layer**: Separate service classes for business logic
- **Blueprint Architecture**: Modular Flask blueprints
- **Database Abstraction**: Dual database support (PostgreSQL + SQLite fallback)
- **Background Tasks**: Celery + Redis for async processing
- **API Standards**: RESTful design with GraphQL option

### TypeScript Patterns
- **Strict Mode**: `strict: true`, `strictNullChecks: false`
- **Interface-Driven**: Strong typing for all data structures
- **Modular Exports**: Clear separation of concerns
- **Error Types**: Typed error handling

## 🔄 Workflow Integration

### Skills System
- Modular skill architecture in `src/skills/`
- Each skill is a self-contained module
- Skills registry for dynamic loading
- Integration with orchestration engine

### Orchestration Engine
- Agent-based task execution
- Dynamic task scheduling
- Resource optimization
- Performance monitoring

### Autonomous Triggers
- Webhook-based automation
- Event-driven architecture
- Real-time response capabilities
- Integration with external services

## 📚 Key Documentation

- **Architecture**: `ATOM_ARCHITECTURE_SPEC.md`
- **OAuth Setup**: `OAUTH_AUTHENTICATION_IMPLEMENTATION_SUMMARY.md`
- **BYOK System**: `BYOK_IMPLEMENTATION_SUMMARY.md`
- **API Documentation**: `docs/API.md`
- **User Guide**: `END_USER_GUIDE.md`
- **Deployment**: `DEPLOYMENT_GUIDE.md`

## 🚀 Deployment

### Production Deployment
```bash
# Full automated deployment
./deploy_production.sh

# Component-specific deployment
./deploy_production.sh --backend-only
./deploy_production.sh --frontend-only
```

### Infrastructure
- **AWS**: ECS, RDS, ElastiCache
- **Kubernetes**: Production-ready k8s configs
- **Terraform**: Infrastructure as code
- **CDK**: AWS Cloud Development Kit

## 🔍 Best Practices

1. **Environment Management**: Always use `.env.example` as template
2. **Database Migrations**: Run migrations before starting services
3. **Testing**: Run comprehensive test suite before commits
4. **Security**: Never commit secrets or API keys
5. **Performance**: Monitor service health and response times
6. **Documentation**: Keep documentation updated with code changes
7. **Code Style**: Follow established TypeScript and Python patterns
8. **Error Handling**: Implement comprehensive error handling
9. **Monitoring**: Use health checks and structured logging
10. **Scaling**: Design services with horizontal scaling in mind

## 🆘 Troubleshooting

### Quick Health Check
```bash
# Check all services
docker-compose ps

# Check service logs
docker-compose logs [service-name]

# Test API endpoints
curl http://localhost:5058/healthz
```

### Common Fixes
- **Port conflicts**: Stop conflicting services or change ports
- **Database connection**: Verify PostgreSQL is running and accessible
- **OAuth failures**: Check HTTPS setup and callback URLs
- **Container issues**: Restart services with `docker-compose restart`
- **Environment issues**: Verify all required variables are set

This guide provides the essential information for working effectively with the ATOM codebase. Always check the latest documentation and environment configurations before starting development.