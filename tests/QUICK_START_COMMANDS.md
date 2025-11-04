# 🚀 ATOM Quick Start Commands
# Production Deployment & Usage Reference

## 📋 System Status

**Current Status**: ✅ **PRODUCTION READY**  
**Backend**: http://localhost:5059  
**Frontend**: http://localhost:3001  
**Database**: PostgreSQL (Docker)  
**Features**: 43/43 Implemented & Verified

---

## 🚀 Deployment Commands

### Full Automated Deployment
```bash
# Complete system deployment
./deploy_production.sh
```

### Component-Specific Deployment
```bash
# Backend only
./deploy_production.sh --backend-only

# Frontend only
./deploy_production.sh --frontend-only

# Desktop app build
./deploy_production.sh --desktop-only

# Verification only
./deploy_production.sh --verify-only

# Cleanup services
./deploy_production.sh --cleanup
```

### Manual Deployment
```bash
# Start database
docker-compose -f docker-compose.postgres.yml up -d

# Start backend
export $(grep -v '^#' .env.production | xargs)
cd backend/python-api-service && python main_api_app.py

# Start frontend
cd frontend-nextjs && npm run dev
```

---

## 🔧 Configuration Commands

### Environment Setup
```bash
# Create production environment
cp .env.production.template .env.production
nano .env.production

# Validate configuration
./setup_external_services.sh

# Quick validation
./setup_external_services.sh --quick
```

### Service Configuration
```bash
# Required API Keys (update in .env.production):
# OPENAI_API_KEY="sk-your-key"                    # AI conversations
# ATOM_GDRIVE_CLIENT_ID="your-client-id"         # Google OAuth
# ATOM_GDRIVE_CLIENT_SECRET="your-secret"        # Google OAuth
# NOTION_CLIENT_ID="your-client-id"              # Notion integration
# NOTION_CLIENT_SECRET="your-secret"             # Notion integration
# TRELLO_API_KEY="your-key"                      # Trello API
# TRELLO_API_TOKEN="your-token"                  # Trello API
```

---

## 🧪 Testing Commands

### System Health
```bash
# Backend health
curl http://localhost:5059/healthz

# Frontend health
curl http://localhost:3001

# Database health
docker exec atom-postgres pg_isready -U atom_user -d atom_db
```

### Core Features
```bash
# Test AI conversation
curl -X POST http://localhost:5059/api/atom/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello ATOM", "user_id": "test"}'

# Calendar integration
curl http://localhost:5059/api/calendar/events

# Task management
curl http://localhost:5059/api/tasks

# Unified search
curl "http://localhost:5059/api/search?query=test"
```

### OAuth Testing
```bash
# Google OAuth
curl "http://localhost:5059/api/auth/gdrive/initiate?user_id=test"

# Notion OAuth
curl "http://localhost:5059/api/auth/notion/initiate?user_id=test"

# Dropbox OAuth
curl "http://localhost:5059/api/auth/dropbox/initiate?user_id=test"

# Asana OAuth
curl "http://localhost:5059/api/auth/asana/initiate?user_id=test"
```

---

## 📊 Monitoring Commands

### Application Logs
```bash
# Backend logs
tail -f backend.log

# Frontend logs
tail -f frontend.log

# Database logs
docker logs atom-postgres -f
```

### Performance Monitoring
```bash
# Check running processes
ps aux | grep "python main_api_app.py"
ps aux | grep "npm run dev"

# Database performance
docker stats atom-postgres

# API response times
time curl -s http://localhost:5059/healthz > /dev/null
```

### Service Status
```bash
# All services status
docker ps
curl -s http://localhost:5059/healthz | python -m json.tool

# Configuration status
./setup_external_services.sh --quick
```

---

## 🔄 Maintenance Commands

### Database Operations
```bash
# Database backup
docker exec atom-postgres pg_dump -U atom_user atom_db > backup.sql

# Database restore
docker exec -i atom-postgres psql -U atom_user atom_db < backup.sql

# Reset database
docker-compose -f docker-compose.postgres.yml down
docker-compose -f docker-compose.postgres.yml up -d
```

### Service Management
```bash
# Restart backend
pkill -f "python main_api_app.py"
cd backend/python-api-service && python main_api_app.py &

# Restart frontend
pkill -f "npm run dev"
cd frontend-nextjs && npm run dev &

# Stop all services
./deploy_production.sh --cleanup
```

### Updates & Dependencies
```bash
# Update Python dependencies
cd backend/python-api-service
pip install -r requirements.txt

# Update Node.js dependencies
cd frontend-nextjs && npm install
cd desktop/tauri && npm install
```

---

## 🎯 Real-World Usage Commands

### User Management
```bash
# Create test user
curl -X POST http://localhost:5059/api/accounts \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "email": "user@example.com", "name": "Test User"}'

# Set user preferences
curl -X POST http://localhost:5059/api/calendar/preferences \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "working_hours": {"start": "09:00", "end": "17:00"}}'
```

### Productivity Scenarios
```bash
# Smart scheduling
curl -X POST http://localhost:5059/api/atom/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Find 30-minute slot for team meeting", "user_id": "user-001"}'

# Task creation
curl -X POST http://localhost:5059/api/atom/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Create task for quarterly report", "user_id": "user-001"}'

# Cross-platform search
curl "http://localhost:5059/api/search?query=project+documentation&user_id=user-001"
```

### Integration Testing
```bash
# Test calendar sync
curl http://localhost:5059/api/calendar/events?user_id=user-001

# Test email search
curl "http://localhost:5059/api/messages/search?query=important&user_id=user-001"

# Test financial data
curl http://localhost:5059/api/financial/accounts?user_id=user-001
```

---

## 🚨 Troubleshooting Commands

### Common Issues
```bash
# Port conflicts
lsof -i :5059
lsof -i :3001

# Database connection issues
docker exec atom-postgres psql -U atom_user -d atom_db -c "SELECT 1;"

# API key validation
curl -X POST http://localhost:5059/api/atom/message \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "user_id": "test"}'

# OAuth configuration
curl "http://localhost:5059/api/auth/gdrive/initiate?user_id=test"
```

### Debugging
```bash
# Check error logs
grep -E "(ERROR|WARNING)" backend.log
grep -E "(ERROR|WARNING)" frontend.log

# Service connectivity
curl -v http://localhost:5059/healthz
curl -v http://localhost:3001

# Database queries
docker exec atom-postgres psql -U atom_user -d atom_db -c "SELECT * FROM pg_stat_activity;"
```

---

## 📚 Documentation References

### Key Files
- `PRODUCTION_DEPLOYMENT_EXECUTION_SUMMARY.md` - Complete deployment status
- `EXTERNAL_SERVICE_SETUP_GUIDE.md` - Service configuration guide
- `REAL_WORLD_USAGE_EXECUTION_PLAN.md` - Usage implementation plan
- `PROGRESS_TRACKER.md` - Development progress and status

### Configuration Files
- `.env.production` - Production environment variables
- `docker-compose.postgres.yml` - Database configuration
- `deploy_production.sh` - Automated deployment script

### Verification Scripts
- `setup_external_services.sh` - Configuration validator
- `verify_all_readme_features.py` - Feature verification
- `verify_all_features_locally.py` - System testing

---

## 🎉 Quick Start Summary

### 1. Deploy System
```bash
./deploy_production.sh
```

### 2. Configure Services
```bash
nano .env.production  # Add API keys
./setup_external_services.sh  # Validate
```

### 3. Test Integration
```bash
curl http://localhost:5059/healthz
curl -X POST http://localhost:5059/api/atom/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "user_id": "test"}'
```

### 4. Access Applications
- **Backend API**: http://localhost:5059
- **Frontend App**: http://localhost:3001
- **Health Check**: http://localhost:5059/healthz

---

**Last Updated**: October 18, 2025  
**Status**: 🟢 **PRODUCTION READY** 🚀