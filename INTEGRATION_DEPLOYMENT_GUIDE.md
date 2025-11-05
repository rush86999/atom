# ATOM Integration Deployment Guide

## 🚀 Production Deployment Overview

This guide provides comprehensive instructions for deploying the ATOM integration ecosystem to production. The platform includes 12 major service integrations with 8 fully production-ready and 4 ready for enhancement.

## 📋 Pre-Deployment Checklist

### ✅ Environment Setup
- [ ] PostgreSQL database configured
- [ ] Redis cache server running
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Domain and DNS configured

### ✅ Service Configuration
- [ ] OAuth credentials for all integrations
- [ ] API keys for enhanced services
- [ ] Database connection strings
- [ ] Encryption keys generated
- [ ] Backup systems configured

### ✅ Security Verification
- [ ] All endpoints secured with HTTPS
- [ ] CORS policies configured
- [ ] Rate limiting enabled
- [ ] Input validation implemented
- [ ] Security headers configured

## 🏗️ Architecture Overview

### Backend Services
```
ATOM Backend (Flask)
├── Main API Server (Port 8000)
├── Database (PostgreSQL)
├── Cache (Redis)
├── File Storage
└── Background Workers (Celery)
```

### Integration Components
```
Integration Layer
├── OAuth Handlers (12 services)
├── Enhanced APIs (8 complete)
├── Database Token Storage
├── Frontend Skills (TypeScript)
└── Monitoring & Logging
```

## 🔧 Deployment Steps

### Step 1: Environment Configuration

#### 1.1 Database Setup
```bash
# Create PostgreSQL database
createdb atom_production
createdb atom_integrations

# Run migrations
python backend/python-api-service/run_migration.py
```

#### 1.2 Environment Variables
Create `.env.production`:
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/atom_production
REDIS_URL=redis://localhost:6379/0

# Flask Configuration
FLASK_SECRET_KEY=your-production-secret-key
FLASK_ENV=production

# OAuth Credentials
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
ASANA_CLIENT_ID=your-asana-client-id
ASANA_CLIENT_SECRET=your-asana-client-secret
NOTION_CLIENT_ID=your-notion-client-id
NOTION_CLIENT_SECRET=your-notion-client-secret
SLACK_CLIENT_ID=your-slack-client-id
SLACK_CLIENT_SECRET=your-slack-client-secret
# ... additional OAuth credentials

# Encryption
ATOM_OAUTH_ENCRYPTION_KEY=your-32-character-encryption-key

# API Configuration
API_BASE_URL=https://api.yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
```

### Step 2: Backend Deployment

#### 2.1 Application Server
```bash
# Install dependencies
pip install -r backend/python-api-service/requirements.txt

# Start production server
gunicorn -w 4 -k gevent -b 0.0.0.0:8000 backend.python-api-service.main_api_app:app
```

#### 2.2 Background Workers
```bash
# Start Celery worker for background tasks
celery -A backend.python-api-service.celery_app worker --loglevel=info

# Start Celery beat for scheduled tasks
celery -A backend.python-api-service.celery_app beat --loglevel=info
```

#### 2.3 Service Configuration
Create `production_config.py`:
```python
# Production configuration
class ProductionConfig:
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CORS
    CORS_ORIGINS = ['https://app.yourdomain.com']
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL')
```

### Step 3: Frontend Deployment

#### 3.1 Build Process
```bash
# Install dependencies
cd frontend-nextjs
npm install

# Build production bundle
npm run build

# Export static files
npm run export
```

#### 3.2 Deployment Configuration
Create `next.config.js` for production:
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://api.yourdomain.com',
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'https://api.yourdomain.com/api/:path*',
      },
    ]
  },
}

module.exports = nextConfig
```

### Step 4: Integration Verification

#### 4.1 Health Check Endpoints
Verify all integration health endpoints:
```bash
# Test health endpoints
curl https://api.yourdomain.com/api/health
curl https://api.yourdomain.com/api/services/health
curl https://api.yourdomain.com/api/integrations/status
```

#### 4.2 OAuth Flow Testing
Test OAuth flows for each integration:
```bash
# Test GitHub OAuth
curl https://api.yourdomain.com/api/oauth/github/url

# Test Asana OAuth  
curl https://api.yourdomain.com/api/oauth/asana/url

# Test Notion OAuth
curl https://api.yourdomain.com/api/oauth/notion/url
```

#### 4.3 API Endpoint Verification
Test key API endpoints:
```bash
# Test GitHub repositories
curl -H "Authorization: Bearer <token>" \
  https://api.yourdomain.com/api/github/enhanced/repositories

# Test Asana tasks
curl -H "Authorization: Bearer <token>" \
  https://api.yourdomain.com/api/asana/enhanced/tasks

# Test Notion pages
curl -H "Authorization: Bearer <token>" \
  https://api.yourdomain.com/api/notion/enhanced/pages
```

## 🔒 Security Configuration

### SSL/TLS Configuration
```nginx
# Nginx configuration
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Rate Limiting
Configure rate limiting in Flask:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Apply specific limits to integration endpoints
@app.route("/api/oauth/<service>/url")
@limiter.limit("10 per minute")
def oauth_url(service):
    # OAuth URL generation
    pass
```

## 📊 Monitoring & Logging

### Application Monitoring
```python
# Configure logging
import logging
from logging.handlers import RotatingFileHandler

# File handler
file_handler = RotatingFileHandler(
    'logs/atom_production.log', 
    maxBytes=10000000, 
    backupCount=10
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

# Integration-specific logging
integration_logger = logging.getLogger('integrations')
integration_handler = RotatingFileHandler(
    'logs/integrations.log',
    maxBytes=5000000,
    backupCount=5
)
integration_logger.addHandler(integration_handler)
```

### Health Monitoring Endpoints
```python
@app.route('/api/monitoring/health')
def monitoring_health():
    """Comprehensive health check"""
    services_status = {
        'database': check_database_health(),
        'redis': check_redis_health(),
        'integrations': check_integrations_health()
    }
    
    overall_health = all(services_status.values())
    return jsonify({
        'status': 'healthy' if overall_health else 'unhealthy',
        'services': services_status,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/monitoring/metrics')
def monitoring_metrics():
    """Application metrics endpoint"""
    return jsonify({
        'active_users': get_active_users_count(),
        'api_requests': get_api_request_count(),
        'integration_calls': get_integration_call_count(),
        'error_rate': get_error_rate(),
        'response_times': get_average_response_times()
    })
```

## 🔄 Continuous Deployment

### Docker Configuration
Create `Dockerfile.production`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 atom
USER atom

# Expose port
EXPOSE 8000

# Start application
CMD ["gunicorn", "-w", "4", "-k", "gevent", "-b", "0.0.0.0:8000", "backend.python-api-service.main_api_app:app"]
```

### Docker Compose
Create `docker-compose.production.yml`:
```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.production
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/atom_production
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=atom_production
      - POSTGRES_USER=atom
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 🚨 Troubleshooting Guide

### Common Issues

#### 1. Database Connection Issues
```bash
# Check database connectivity
psql $DATABASE_URL -c "SELECT version();"

# Check connection pool
python -c "from backend.python-api-service.db_utils import get_db_pool; print(get_db_pool().stats())"
```

#### 2. OAuth Token Issues
```python
# Debug OAuth token flow
def debug_oauth_flow(service):
    tokens = get_tokens(user_id, service)
    if not tokens:
        print(f"No tokens found for {service}")
        return
    
    # Check token expiration
    if is_token_expired(tokens):
        print(f"Tokens expired for {service}")
        refreshed = refresh_tokens(user_id, service)
        if not refreshed:
            print(f"Failed to refresh tokens for {service}")
```

#### 3. Integration API Issues
```bash
# Test integration API connectivity
curl -H "Authorization: Bearer <token>" \
  https://api.yourdomain.com/api/${service}/enhanced/health

# Check integration logs
tail -f logs/integrations.log | grep ${service}
```

### Performance Optimization

#### Database Optimization
```sql
-- Create indexes for integration tables
CREATE INDEX idx_oauth_tokens_user_service ON oauth_tokens(user_id, service);
CREATE INDEX idx_integration_data_user_service ON integration_data(user_id, service);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
```

#### Caching Strategy
```python
# Redis caching for integration data
def get_cached_integration_data(user_id, service, endpoint):
    cache_key = f"integration:{user_id}:{service}:{endpoint}"
    cached_data = redis.get(cache_key)
    
    if cached_data:
        return json.loads(cached_data)
    
    # Fetch from API and cache
    data = fetch_integration_data(user_id, service, endpoint)
    redis.setex(cache_key, 300, json.dumps(data))  # Cache for 5 minutes
    return data
```

## 📞 Support & Maintenance

### Monitoring Dashboard
Access the monitoring dashboard at:
- **Application Metrics**: `https://api.yourdomain.com/api/monitoring/metrics`
- **Integration Status**: `https://api.yourdomain.com/api/integrations/status`
- **Error Logs**: `https://api.yourdomain.com/api/monitoring/errors`

### Support Contacts
- **Technical Support**: support@yourdomain.com
- **Integration Issues**: integrations@yourdomain.com
- **Emergency**: ops@yourdomain.com

### Maintenance Schedule
- **Daily**: Health checks and log monitoring
- **Weekly**: Performance review and optimization
- **Monthly**: Security audit and dependency updates
- **Quarterly**: Integration API version updates

---

**Deployment Status**: ✅ **READY FOR PRODUCTION**  
**Last Updated**: November 4, 2025  
**Next Review**: December 4, 2025