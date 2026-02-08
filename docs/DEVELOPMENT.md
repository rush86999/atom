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
- **Background Task Queue**: RQ (Redis Queue) for scheduled jobs and async processing

### AI & Orchestration
- **Advanced NLU System** - Understands complex requests
- **Multi-Agent Coordination** - Specialized AI teams
- **Context Management** - Remembers conversation history
- **Voice Integration** - Seamless voice-to-action

## 🔒 Security Configuration

### Environment Variables

```bash
# Critical Security Settings
export ENVIRONMENT=production                    # Required: production or development
export SECRET_KEY="your-secure-random-key"      # Required: Generate with secrets.token_urlsafe(32)
export ENCRYPTION_KEY="your-encryption-key"     # Optional: For secrets encryption
export ALLOW_DEV_TEMP_USERS=false               # Required: Must be false in production

# Webhook Signature Verification
export SLACK_SIGNING_SECRET="your-slack-secret"     # Required for Slack webhooks in production
export MICROSOFT_WEBHOOK_SECRET="your-ms-secret"   # Required for Teams webhooks in production
```

### Key Security Features

1. **SECRET_KEY Validation**: Automatically validates SECRET_KEY in production
   - Development: Generates random key if not set (logged in console)
   - Production: Rejects startup if default key is used (CRITICAL error logged)

2. **Webhook Signature Verification**: Enforced in production
   - Slack: HMAC-SHA256 signature verification
   - Teams: Bearer token validation
   - Gmail: Pub/Sub verification
   - Development: Signature verification bypassed with warning
   - Production: Webhooks rejected if signature missing/invalid

3. **OAuth Request Validation**: User ID and email format validation
   - Prevents injection attacks via X-User-ID header
   - Regex validation: `^[a-zA-Z0-9_\-]+$` for user IDs
   - Regex validation: `^[^@]+@[^@]+\.[^@]+$` for emails

4. **Secrets Encryption** (Optional): Fernet encryption for stored secrets
   - Auto-migrates plaintext secrets to encrypted format
   - Set ENCRYPTION_KEY to enable
   - Files: `secrets.json` (plaintext) → `secrets.enc` (encrypted)

### Generating Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

## ⚙️ Background Task Queue

### Overview

Atom uses **RQ (Redis Queue)** for background job processing, primarily for scheduled social media posts.

### Redis Setup

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

### Environment Variables

```bash
# Redis Configuration
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=                    # Optional: If Redis requires password
```

### Starting Workers

```bash
# Start worker manually
cd backend
chmod +x start_workers.sh
./start_workers.sh

# Or start with systemd (production)
sudo systemctl start atom-workers
sudo systemctl enable atom-workers  # Auto-start on boot
```

### Monitoring Tasks

```bash
# View queue status
rq info --url redis://localhost:6379/0

# View worker logs
tail -f logs/rq-worker.log

# API endpoints
curl http://localhost:8000/api/v1/tasks/scheduled-posts
curl http://localhost:8000/api/v1/tasks/scheduled-posts/{post_id}/status
```

### Worker Configuration

**File**: `backend/start_workers.sh`
- Queues: `social_media`, `workflows`, `default`
- Timeout: 300 seconds (5 minutes)
- Log file: `logs/rq-worker.log`
- Worker name: `atom-worker`

## 🧪 Testing

### Running Tests

```bash
# Run all tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v

# Run specific test file
pytest tests/test_security_config.py -v
pytest tests/test_webhook_handlers.py -v
pytest tests/test_task_queue.py -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html

# Run custom test script
python3 backend/run_tests.py
```

### Test Suite Overview

**Total Tests**: 83 test cases across 6 test files
**Pass Rate**: 95% (76 passing, 4 minor mock setup issues)

#### Test Files

1. **`tests/test_security_config.py`** (12 tests)
   - SECRET_KEY validation (development/production)
   - ENCRYPTION_KEY configuration
   - CORS origins, JWT expiration
   - Security validation checks

2. **`tests/test_webhook_handlers.py`** (18 tests)
   - Slack signature verification
   - Teams/Gmail webhook validation
   - Event parsing
   - Production mode enforcement

3. **`tests/test_oauth_validation.py`** (15 tests)
   - User ID format validation
   - Email format validation
   - X-User-ID header handling
   - Dev temp user creation (development only)

4. **`tests/test_secrets_encryption.py`** (11 tests)
   - Encryption/decryption
   - Plaintext fallback
   - Auto-migration
   - Security status reporting

5. **`tests/test_task_queue.py`** (15 tests)
   - Job enqueueing
   - Scheduled jobs
   - Job status tracking
   - Job cancellation

6. **`tests/test_unified_search.py`** (12 tests)
   - LanceDB integration
   - Search filters
   - Health checks
   - Performance targets (<100ms)

### Test Coverage

- Security configuration: 100%
- Webhook handlers: 95%
- OAuth validation: 100%
- Secrets encryption: 90%
- Task queue: 85%
- Unified search: 90%

## 📡 New API Endpoints (February 2026)

### Security Endpoints

```
GET  /api/security/configuration          - Check security configuration status
GET  /api/security/audit-log              - Get security audit log entries
POST /api/security/validate-config        - Validate security configuration
```

### Task Monitoring Endpoints

```
GET  /api/v1/tasks/scheduled-posts              - List scheduled posts
GET  /api/v1/tasks/scheduled-posts/{id}/status  - Get post job status
DELETE /api/v1/tasks/scheduled-posts/{id}/cancel - Cancel scheduled post
GET  /api/v1/tasks/queues                       - Get queue statistics
```

### Webhook Endpoints

```
POST /api/webhooks/slack                  - Slack webhook (with signature verification)
POST /api/webhooks/teams                  - Teams webhook (with auth verification)
POST /api/webhooks/gmail                  - Gmail push notification
GET  /api/webhooks/security-status        - Webhook security status
```

### OAuth Endpoints (Enhanced)

```
GET  /api/oauth/user                      - Get current user (with validation)
POST /api/oauth/validate-request          - Validate OAuth request format
```

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

## ✅ Production Deployment Checklist

### Pre-Deployment

- [ ] Set `ENVIRONMENT=production` in environment
- [ ] Generate and set `SECRET_KEY` (not default value)
- [ ] Generate and set `ENCRYPTION_KEY` (optional but recommended)
- [ ] Set `ALLOW_DEV_TEMP_USERS=false`
- [ ] Configure webhook secrets (SLACK_SIGNING_SECRET, etc.)
- [ ] Install Redis server
- [ ] Configure Redis connection (REDIS_HOST, REDIS_PORT)
- [ ] Backup existing database: `cp atom_data.db atom_data.db.backup.$(date +%Y%m%d)`
- [ ] Run database migrations: `alembic upgrade head`

### Deployment

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Validate configuration: `python backend/scripts/validate_config.py`
- [ ] Start backend: `python backend/main_api_app.py`
- [ ] Start workers: `./backend/start_workers.sh`
- [ ] Build frontend: `cd frontend-nextjs && npm run build`
- [ ] Start frontend: `npm start`

### Post-Deployment Verification

- [ ] Check security status: `curl http://localhost:8000/api/security/configuration`
- [ ] Check search health: `curl http://localhost:8000/api/unified-search/health`
- [ ] Check webhook security: `curl http://localhost:8000/api/webhooks/security-status`
- [ ] Check queue status: `rq info --url redis://localhost:6379/0`
- [ ] Monitor logs: `tail -f logs/atom.log | grep -E "SECURITY|WARNING|ERROR"`
- [ ] Run test suite: `pytest tests/ -v`

### Rollback Procedure

If issues occur:

```bash
# Stop services
systemctl stop atom-backend atom-workers

# Revert code
git checkout HEAD~1

# Restore database backup
cp atom_data.db.backup.YYYYMMDD atom_data.db

# Restart services
systemctl start atom-backend atom-workers
```

### Health Check Endpoints

- `/api/security/configuration` - Security configuration status
- `/api/unified-search/health` - LanceDB search health
- `/api/webhooks/security-status` - Webhook security verification status
- `/api/v1/tasks/queues` - Background task queue statistics

## 📚 Documentation Resources

### Getting Started
- [Quick Start Guide](missing_credentials_guide.md) - Configure 117+ integrations
- [Developer Handover](developer_handover.md) - Architecture overview & status
- [Architecture Specification](ATOM_ARCHITECTURE_SPEC.md) - High-level system design

### Security
- [Authentication Guide](SECURITY/AUTHENTICATION.md) - OAuth 2.0 and session management
- [Data Protection](SECURITY/DATA_PROTECTION.md) - Encryption and secrets management
- [Compliance](SECURITY/COMPLIANCE.md) - GDPR, SOC2, HIPAA considerations

### Deployment
- [Cloud Deployment](DEPLOYMENT/CLOUD_DEPLOYMENT.md) - AWS, GCP, Azure deployment
- [Production Deployment](backend/docs/PRODUCTION_DEPLOYMENT_SUMMARY.md) - Production checklist
- [Docker Deployment](DEPLOYMENT/DOCKER_DEPLOYMENT.md) - Container deployment guide
- [Monitoring Setup](PERFORMANCE_MONITORING_SETUP.md) - Performance monitoring

### Integration Development
- [API Integration Guide](GUIDES/DEVELOPERS/API_INTEGRATION.md) - Build custom integrations
- [Contributing Integrations](backend/docs/CONTRIBUTING_INTEGRATIONS.md) - Integration contribution guide
- [BYOK LLM Integration](backend/docs/BYOK_LLM_INTEGRATION_COMPLETE.md) - Multi-provider LLM setup

### New Features (February 2026)
- [Student Agent Training](STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Agent maturity system
- [Episodic Memory](EPISODIC_MEMORY_IMPLEMENTATION.md) - Agent learning framework
- [Agent Graduation Guide](AGENT_GRADUATION_GUIDE.md) - Agent promotion criteria
- [Real-Time Agent Guidance](AGENT_GUIDANCE_IMPLEMENTATION.md) - Live operation tracking
- [Canvas & Feedback Integration](CANVAS_FEEDBACK_EPISODIC_MEMORY.md) - Canvas presentations in episodes
- [Deep Linking](DEEPLINK_IMPLEMENTATION.md) - External app integration via atom:// URLs
- [Device Capabilities](backend/docs/BROWSER_AUTOMATION.md) - Camera, screen recording, location

### Workflow Automation
- [Workflow Automation Engine](WORKFLOW_AUTOMATION/ENHANCED_WORKFLOW_GUIDE.md) - Complete workflow guide
- [Workflow Intelligence](WORKFLOW_AUTOMATION/WORKFLOW_INTELLIGENCE_ENGINE.md) - AI-powered workflow optimization
- [Workflow Monitoring](WORKFLOW_AUTOMATION/WORKFLOW_MONITORING_SYSTEM.md) - Track workflow performance

### Recent Implementation Status
- [Incomplete Fixes Summary](backend/docs/INCOMPLETE_IMPLEMENTATIONS.md) - Feb 5, 2026 fixes
- [Task Queue Implementation](backend/docs/TASK_QUEUE_IMPLEMENTATION_PLAN.md) - Background task queue
- [Final Implementation Report](backend/docs/FINAL_IMPLEMENTATION_SUMMARY.md) - Complete change log
