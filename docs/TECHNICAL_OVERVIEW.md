# 🔧 Atom Technical Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Next.js 15.5  │  │   React 18.2    │  │   TypeScript    │ │
│  │                 │  │                 │  │                 │ │
│  │ • Pages Router  │  │ • Hooks & State │  │ • Type Safety   │ │
│  │ • API Routes    │  │ • Context API   │  │ • Interfaces    │ │
│  │ • SSR/SSG       │  │ • Performance   │  │ • Validation    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Chakra UI     │  │   TailwindCSS   │  │   Framer Motion │ │
│  │                 │  │                 │  │                 │ │
│  │ • Component Lib │  • Utility Classes │  • Animations     │ │
│  │ • Theme System  │  • Responsive      │  • Transitions    │ │
│  │ • Accessibility │  • Customization   │  • Interactions   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────┐
│                      Backend Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   FastAPI       │  │   PostgreSQL    │  │   Redis         │ │
│  │                 │  │                 │  │                 │ │
│  │ • REST API      │  • Primary DB      │  • Caching        │ │
│  │ • OAuth 2.0     │  • ORM (Prisma)    │  • Session Store  │ │
│  │ • WebSockets    │  • Migrations      │  • Pub/Sub        │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Celery        │  │   Docker        │  │   Nginx         │ │
│  │                 │  │                 │  │                 │ │
│  • Task Queue      │  • Containerization│  • Reverse Proxy  │ │
│  • Background Jobs │  • Orchestration   │  • Load Balancing  │ │
│  • Scheduled Tasks │  • Deployment      │  • SSL/TLS        │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Layer                            │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐  │
│  │ Calendar│  Email  │   Task  │   File  │ Finance │   CRM   │  │
│  │         │         │         │         │         │         │  │
│  │• Google │• Gmail  │• Notion │• Drive  │• Plaid  │•Salesforce│ │
│  │• Outlook│• Outlook│• Trello │• Dropbox│•QuickBooks│• HubSpot │ │
│  │         │         │• Asana  │• OneDrive│• Xero   │         │ │
│  │         │         │• Jira   │• Box    │• Stripe │         │ │
│  └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘  │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐  │
│  │  Social │  Chat   │  Voice  │   AI    │ Payment │  Other  │  │
│  │         │         │         │         │         │         │  │
│  │• Twitter│• Slack  │• STT/TTS│• OpenAI │• PayPal │• GitHub │ │
│  │•LinkedIn│• Teams  │• Wake   │• Claude │         │• Zapier │ │
│  │         │• Discord│  Word   │• Gemini │         │         │ │
│  │         │         │         │         │         │         │ │
│  └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### Frontend Components

#### Dashboard & Navigation
- **Dashboard.tsx** - Main dashboard with overview tabs
- **Baseof.tsx** - Root layout component
- **Navigation** - Tab-based navigation system

#### Core Feature Components
- **CalendarManagement.tsx** - Calendar events and scheduling
- **TaskManagement.tsx** - Task creation and organization
- **CommunicationHub.tsx** - Unified messaging interface
- **FinancialDashboard.tsx** - Financial tracking and insights

#### Advanced Feature Components
- **AgentManager.tsx** - Multi-agent system management
- **RoleSettings.tsx** - Agent role configuration
- **CoordinationView.tsx** - Agent task coordination
- **WorkflowEditor.tsx** - Visual automation builder
- **TriggerSettings.tsx** - Automation trigger configuration
- **WorkflowMonitor.tsx** - Automation execution monitoring
- **WakeWordDetector.tsx** - Voice activation system
- **VoiceCommands.tsx** - Voice command processing
- **ChatInterface.tsx** - AI-powered conversation interface

### Backend Services

#### Core API Services
- **main_api_app.py** - FastAPI main application
- **email_service.py** - Email integration and processing
- **calendar_integration_service.py** - Calendar synchronization
- **task_service.py** - Task management and coordination

#### Integration Services
- **notion_service.py** - Notion API integration
- **trello_service.py** - Trello board management
- **asana_service.py** - Asana project coordination
- **jira_service.py** - Jira issue tracking
- **file_storage_service.py** - Cloud storage integration
- **salesforce_service.py** - CRM data synchronization
- **hubspot_service.py** - Marketing automation
- **finance_service.py** - Financial data processing
- **social_media_service.py** - Social platform management

#### Advanced Services
- **universal_webhook_bridge.py** - Multi-platform message standardization
- **agent_integration_gateway.py** - Centralized response routing hub
- **messenger_service.py** - Facebook Messenger API interaction
- **line_service.py** - Line Messaging API interaction
- **signal_service.py** - signal-cli-rest-api interaction
- **agent_service.py** - Multi-agent coordination
- **workflow_service.py** - Automation execution
- **voice_service.py** - Speech processing
- **ai_service.py** - LLM integration and management
- **self_evolution_service.py** - Agent learning and self-improvement coordinator
- **agent_evolution_loop.py** - GEA (Group-Evolving Agents) full evolution cycle

## Database Schema

### Core Tables (NextAuth + Application)
```sql
-- NextAuth Authentication (Nov 2025)
users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255),
  email_verified TIMESTAMP,
  image TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
)

password_reset_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token VARCHAR(255) UNIQUE NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  used BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
)

-- OAuth Integration Tokens
oauth_tokens (
  id UUID,
  user_id UUID REFERENCES users(id),
  service VARCHAR(255),
  access_token TEXT ENCRYPTED,
  refresh_token TEXT ENCRYPTED,
  expires_at TIMESTAMP
)

-- Calendar & Scheduling
calendar_events (id, user_id, title, start_time, end_time, location, status)
event_templates (id, user_id, name, settings, created_at)

-- Task Management
tasks (id, user_id, title, description, status, priority, due_date, project_id)
projects (id, user_id, name, description, status, created_at)

-- Communication
messages (id, user_id, platform, from_user, subject, content, timestamp, unread)
threads (id, user_id, platform, participants, last_message_at)

-- Financial
transactions (id, user_id, account_id, amount, description, category, date)
accounts (id, user_id, name, type, balance, currency)
budgets (id, user_id, category, amount, period)
```

### Integration Tables
```sql
-- Service Connections
service_connections (id, user_id, service_type, config, sync_status, last_sync)
external_ids (id, user_id, service_type, external_id, internal_id)

-- Advanced Features
agents (id, user_id, name, role, status, capabilities, config, performance)
workflows (id, user_id, name, description, triggers, actions, enabled, version)
voice_commands (id, user_id, phrase, action, parameters, enabled, usage_count)
ai_sessions (id, user_id, title, messages, model, created_at, updated_at)
```

## Authentication & Security

### NextAuth Production System (Nov 2025)

**Authentication Flow:**
```
User → Email/Password or OAuth → NextAuth → bcrypt/OAuth verify → JWT Session → API Access
```

**Supported Methods:**
- Email/password with bcrypt hashing (10 rounds)
- OAuth 2.0 (Google, GitHub)
- Password reset with secure tokens (1-hour expiry)

**Key Components:**
- `frontend-nextjs/lib/auth.ts` - NextAuth configuration
- `frontend-nextjs/lib/db.ts` - Direct PostgreSQL connection
- `backend/migrations/` - Database schemas

**API Endpoints:**
- `POST /api/auth/register` - User registration
- `POST /api/auth/[...nextauth]` - NextAuth handlers
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset with token
- `GET /api/auth/callback/{provider}` - OAuth callbacks

### Security Features
- **bcrypt Hashing** - Industry-standard password hashing
- **JWT Sessions** - Stateless session management with secure secrets
- **OAuth 2.0** - Secure third-party authentication
- **Token Encryption** - Service tokens encrypted with AES
- **Input Validation** - Comprehensive request validation
- **XSS Prevention** - HTML sanitization and CSP headers
- **CSRF Protection** - Token-based request verification
- **Rate Limiting** - API request throttling
- **Data Encryption** - Sensitive data encrypted at rest

## Performance Architecture

### Frontend Optimization
- **Code Splitting** - Lazy-loaded components
- **Virtual Scrolling** - Efficient large list rendering
- **Caching Strategy** - SWR and React Query for data
- **Bundle Optimization** - Tree shaking and minification
- **Image Optimization** - Next.js image optimization

### Backend Optimization
- **Database Indexing** - Optimized query performance
- **Connection Pooling** - Efficient database connections
- **Caching Layer** - Redis for frequent data
- **Background Processing** - Celery for long-running tasks
- **API Rate Limiting** - Request throttling and queuing

### Monitoring & Metrics
- **Response Times** - API latency tracking
- **Error Rates** - Application error monitoring
- **Resource Usage** - CPU, memory, and storage
- **User Analytics** - Feature usage and engagement
- **Integration Health** - External service status

## Deployment Architecture

### Development Environment
```yaml
# docker-compose.yml
services:
  frontend:
    build: ./frontend-nextjs
    ports: ["3000:3000"]
    environment:
      - NODE_ENV=development
      - NEXTAUTH_URL=http://localhost:3000
  
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://...
  
  database:
    image: postgres:15
    environment:
      - POSTGRES_DB=atom
      - POSTGRES_USER=atom
      - POSTGRES_PASSWORD=atom
  
  redis:
    image: redis:7-alpine
```

### Production Deployment
```yaml
# Kubernetes Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atom-frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: atom-frontend
  template:
    metadata:
      labels:
        app: atom-frontend
    spec:
      containers:
      - name: frontend
        image: atom/frontend:latest
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: production
```

## Testing Strategy

### Unit Testing
- **Jest** - JavaScript/TypeScript testing
- **React Testing Library** - Component testing
- **Pytest** - Python backend testing
- **Test Coverage** - 95%+ coverage target

### Integration Testing
- **API Testing** - End-to-end API validation
- **Database Testing** - Data integrity tests
- **External Service Testing** - Integration verification
- **Performance Testing** - Load and stress testing

### Security Testing
- **Penetration Testing** - Vulnerability assessment
- **Input Validation** - Security boundary testing
- **Authentication Testing** - Access control verification
- **Data Protection** - Privacy compliance testing

## Development Workflow

### Local Development
```bash
# Frontend Development
cd frontend-nextjs
npm install
npm run dev

# Backend Development  
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main_api_app.py

# Database Setup
docker-compose up -d postgres redis
```

### CI/CD Pipeline
```yaml
# GitHub Actions
name: CI/CD Pipeline
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
      - name: Install dependencies
        run: npm install
      - name: Run tests
        run: npm test
      - name: Build application
        run: npm run build
```

## Technology Stack

### Frontend Technologies
- **Next.js 15.5** - React framework with SSR
- **TypeScript 5.9** - Type-safe JavaScript
- **Chakra UI 2.5** - Component library
- **TailwindCSS 3.2** - Utility-first CSS
- **Framer Motion 10.2** - Animation library
- **React Query** - Data fetching and caching

### Backend Technologies
- **Python 3.11** - Backend programming language
- **FastAPI** - Modern Python web framework
- **PostgreSQL 15** - Primary database
- **Redis 7** - Caching and session storage (optional)
- **Celery** - Distributed task queue (optional)
- **SQLAlchemy** - Database ORM

### Infrastructure & DevOps
- **Docker** - Containerization
- **Docker Compose** - Local development
- **Kubernetes** - Production orchestration
- **Nginx** - Reverse proxy and load balancer
- **GitHub Actions** - CI/CD pipeline
- **AWS/Azure/GCP** - Cloud deployment options

## Future Architecture Roadmap

### Phase 1: Scalability (Next 6 Months)
- **Microservices** - Decompose monolith
- **Event-Driven Architecture** - Message bus implementation
- **Advanced Caching** - Distributed cache strategy
- **Database Sharding** - Horizontal scaling

### Phase 2: Intelligence (Next 12 Months)
- **Machine Learning** - Predictive features
- **Advanced NLP** - Enhanced language understanding
- **Personalization Engine** - Adaptive user experiences
- **Automated Optimization** - Self-improving system

### Phase 3: Platform (Next 18 Months)
- **Multi-Tenancy** - Enterprise support
- **API Marketplace** - Third-party extensions
- **Mobile Applications** - Native iOS/Android apps
- **Internationalization** - Global deployment

---

## Getting Started

### Development Setup
1. Clone the repository
2. Install dependencies: `npm install` (frontend) and `pip install -r requirements.txt` (backend)
3. Set up environment variables
4. Run database migrations
5. Start development servers

### Production Deployment
1. Build Docker images
2. Configure environment variables
3. Deploy to cloud platform
4. Run database migrations
5. Configure monitoring and logging

For detailed setup instructions, see the individual component documentation and deployment guides.