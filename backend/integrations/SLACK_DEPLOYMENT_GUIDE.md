# ATOM Slack Integration - Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the ATOM Slack Integration in production environments. The integration includes backend services, frontend components, database schemas, and configuration management.

## Prerequisites

### System Requirements

- **Python**: 3.8+ (backend)
- **Node.js**: 16+ (frontend)
- **Database**: PostgreSQL 12+ or MongoDB 4.4+
- **Redis**: 6.0+ (caching, optional)
- **Load Balancer**: Nginx or similar
- **SSL Certificate**: For HTTPS
- **Domain**: Custom domain for the application

### External Services

- **Slack App**: Created and configured
- **OAuth Credentials**: Client ID and Client Secret
- **Webhook URL**: Configured in Slack App settings
- **API Access**: Required scopes granted

### Infrastructure Components

- **Application Server**: Python Flask/FastAPI
- **Frontend Server**: Next.js or React
- **Database Server**: PostgreSQL/MongoDB
- **Cache Server**: Redis (optional)
- **Web Server**: Nginx (reverse proxy)
- **Container Runtime**: Docker (recommended)

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Slack API     │◄──►│  ATOM Backend  │◄──►│   Database      │
│                 │    │                 │    │                 │
│ - OAuth 2.0     │    │ - API Endpoints │    │ - Workspaces     │
│ - Webhooks      │    │ - Event Handler │    │ - Channels       │
│ - Real-time     │    │ - Rate Limiting │    │ - Messages       │
│                 │    │ - Cache Layer   │    │ - Users          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  Redis Cache    │              │
         └──────────────►│                 │◄─────────────┘
                        │ - API Response  │
                        │ - Session Data  │
                        │ - Rate Limits   │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │  Frontend UI    │
                        │                 │
                        │ - Slack Manager │
                        │ - Configuration │
                        │ - Analytics     │
                        └─────────────────┘
```

## Installation Steps

### 1. Environment Setup

#### Clone Repository
```bash
git clone https://github.com/atom-platform/slack-integration.git
cd slack-integration
```

#### Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Database Setup

#### PostgreSQL Setup
```bash
# Create database
createdb atom_slack_integration

# Run migrations
python -m alembic upgrade head
```

#### MongoDB Setup (alternative)
```bash
# Create database
use atom_slack_integration

# Create collections
db.workspaces.createIndex({ "id": 1 }, { unique: true })
db.channels.createIndex({ "id": 1 })
db.messages.createIndex({ "ts": 1 })
```

### 3. Configuration

#### Environment Variables
Create `.env` file:

```bash
# Slack Configuration
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
SLACK_SIGNING_SECRET=your_slack_signing_secret
SLACK_REDIRECT_URI=https://your-domain.com/integrations/slack/callback
SLACK_WEBHOOK_URL=https://your-domain.com/api/integrations/slack/events

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/atom_slack_integration
# or
MONGODB_URI=mongodb://user:password@localhost:27017/atom_slack_integration

# Cache Configuration (Redis)
REDIS_URL=redis://localhost:6379/0
SLACK_CACHE_ENABLED=true
SLACK_CACHE_TTL=300

# API Configuration
FLASK_SECRET_KEY=your_flask_secret_key
API_HOST=0.0.0.0
API_PORT=5058
CORS_ORIGINS=https://your-domain.com

# Logging
LOG_LEVEL=info
LOG_FILE=/var/log/atom/slack-integration.log
SLACK_DEBUG=false

# Rate Limiting
SLACK_RATE_LIMIT_TIER1=1
SLACK_RATE_LIMIT_TIER2=1
SLACK_RATE_LIMIT_TIER3=20

# Sync Configuration
SLACK_SYNC_FREQUENCY=realtime
SLACK_SYNC_BATCH_SIZE=100
SLACK_MAX_CONCURRENT_REQUESTS=5
SLACK_DATE_RANGE_DAYS=90

# Analytics
SLACK_ANALYTICS_ENABLED=true
SLACK_SENTIMENT_ANALYSIS=false

# Notifications
SLACK_NOTIFICATION_WEBHOOK_URL=https://hooks.slack.com/...
SLACK_NOTIFY_NEW_MESSAGES=true
SLACK_NOTIFY_MENTIONS=true
```

#### Configuration Validation
```bash
python -c "from integrations.slack_config import validate_slack_config; errors = validate_slack_config(); print(f'Errors: {errors}')" 
```

### 4. Slack App Configuration

#### 1. Create Slack App
1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From scratch"
4. Enter app name and workspace
5. Click "Create App"

#### 2. Configure OAuth
1. Navigate to "OAuth & Permissions"
2. Add redirect URI: `https://your-domain.com/integrations/slack/callback`
3. Add required scopes:
   ```
   channels:read
   channels:history
   groups:read
   groups:history
   im:read
   im:history
   mpim:read
   mpim:history
   users:read
   users:read.email
   team:read
   files:read
   reactions:read
   ```

#### 3. Configure Webhooks
1. Navigate to "Event Subscriptions"
2. Enable events
3. Request URL: `https://your-domain.com/api/integrations/slack/events`
4. Subscribe to events:
   ```
   app_mention
   message
   message_changed
   message_deleted
   file_shared
   file_deleted
   channel_created
   channel_deleted
   channel_archive
   channel_unarchive
   team_join
   team_leave
   ```

#### 4. Configure Interactivity
1. Navigate to "Interactivity & Shortcuts"
2. Enable interactivity
3. Request URL: `https://your-domain.com/api/integrations/slack/interactive`

#### 5. Install App
1. Navigate to "Install App"
2. Click "Install to Workspace"
3. Copy credentials to `.env` file

### 5. Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5058

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5058/api/integrations/slack/health || exit 1

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:5058", "--workers", "4", "--timeout", "60", "main_api_app:app"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  slack-integration:
    build: .
    ports:
      - "5058:5058"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/atom_slack
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5058/api/integrations/slack/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=atom_slack
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  redis:
    image: redis:6-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - slack-integration
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

#### Deploy with Docker Compose
```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f slack-integration

# Check health status
docker-compose ps

# Scale services
docker-compose up -d --scale slack-integration=3
```

### 6. Nginx Configuration

#### nginx.conf
```nginx
events {
    worker_connections 1024;
}

http {
    upstream slack_integration {
        server slack-integration:5058;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

        # Rate limiting
        limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
        limit_req zone=api burst=20 nodelay;

        location /api/integrations/slack {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://slack_integration;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        location / {
            proxy_pass http://slack_integration;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### 7. Systemd Service (Optional)

#### slack-integration.service
```ini
[Unit]
Description=ATOM Slack Integration
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=atom
Group=atom
WorkingDirectory=/opt/atom-slack-integration
Environment=PATH=/opt/atom-slack-integration/venv/bin
EnvironmentFile=/opt/atom-slack-integration/.env
ExecStart=/opt/atom-slack-integration/venv/bin/gunicorn --bind 0.0.0.0:5058 --workers 4 main_api_app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Enable Service
```bash
sudo cp slack-integration.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slack-integration
sudo systemctl start slack-integration
```

## Testing

### 1. Health Check
```bash
curl -X POST https://your-domain.com/api/integrations/slack/health
```

Expected response:
```json
{
  "ok": true,
  "status": "healthy",
  "service": "slack_integration",
  "version": "2.0.0"
}
```

### 2. OAuth Flow Test
```bash
# Test OAuth start
curl -X POST https://your-domain.com/api/auth/slack/authorize \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'
```

### 3. API Endpoints Test
```bash
# Test workspaces
curl -X POST https://your-domain.com/api/integrations/slack/workspaces \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Test channels
curl -X POST https://your-domain.com/api/integrations/slack/channels \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "workspace_id": "T1234567890",
    "include_private": false
  }'
```

### 4. Integration Tests
```bash
# Run test suite
python -m pytest integrations/test_slack_integration.py -v

# Run with coverage
python -m pytest integrations/test_slack_integration.py --cov=integrations.slack --cov-report=html
```

### 5. Load Testing
```bash
# Install locust
pip install locust

# Run load test
locust -f load_test.py --host=https://your-domain.com
```

## Monitoring

### 1. Application Metrics

#### Prometheus Metrics
```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
REQUEST_COUNT = Counter('slack_requests_total', 'Total requests', ['endpoint', 'status'])
REQUEST_DURATION = Histogram('slack_request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('slack_active_connections', 'Active connections')
RATE_LIMIT_HITS = Counter('slack_rate_limit_hits_total', 'Rate limit hits')
```

#### Grafana Dashboard
- Request rate and response time
- Error rates by endpoint
- Rate limit hits
- Active connections
- Database query performance
- Cache hit rates

### 2. Logging

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()
logger.info("Processing webhook event", event_type=event['type'], event_id=event['event_id'])
```

#### Log Aggregation
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Fluentd + Elasticsearch
- Papertrail
- DataDog

### 3. Health Monitoring

#### Custom Health Checks
```python
@app.route('/health/detailed')
def detailed_health():
    return {
        "status": "healthy",
        "checks": {
            "database": check_database(),
            "redis": check_redis(),
            "slack_api": check_slack_api(),
            "disk_space": check_disk_space()
        }
    }
```

#### Monitoring Services
- Uptime Robot
- Pingdom
- DataDog Uptime
- PagerDuty alerts

## Security

### 1. SSL/TLS Configuration

#### Certificate Setup
```bash
# Generate self-signed certificate (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Use Let's Encrypt (production)
sudo certbot --nginx -d your-domain.com
```

#### SSL Configuration
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
```

### 2. Webhook Security

#### Signature Verification
```python
def verify_webhook_signature(body: bytes, timestamp: str, signature: str) -> bool:
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)
```

### 3. Rate Limiting

#### Application-Level Rate Limiting
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour", "100 per minute"]
)
```

### 4. Access Control

#### IP Whitelisting
```nginx
location /admin {
    allow 192.168.1.0/24;
    deny all;
    proxy_pass http://localhost:5058;
}
```

## Backup and Recovery

### 1. Database Backup

#### PostgreSQL Backup Script
```bash
#!/bin/bash
BACKUP_DIR="/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="atom_slack_integration"

mkdir -p $BACKUP_DIR

pg_dump $DB_NAME | gzip > $BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz

# Keep last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

#### Automated Backup
```bash
# Add to crontab
0 2 * * * /opt/backup-slack-db.sh
```

### 2. Configuration Backup

```bash
# Backup environment file
cp .env .env.backup.$(date +%Y%m%d)

# Backup to S3
aws s3 cp .env s3://your-backup-bucket/slack-config/
```

### 3. Recovery Procedures

#### Database Recovery
```bash
# Restore from backup
gunzip < backup.sql.gz | pslack slack_integration
```

#### Service Recovery
```bash
# Restart services
docker-compose restart slack-integration
systemctl restart slack-integration
```

## Performance Optimization

### 1. Database Optimization

#### Indexes
```sql
-- PostgreSQL indexes
CREATE INDEX CONCURRENTLY idx_messages_ts ON messages (ts DESC);
CREATE INDEX CONCURRENTLY idx_messages_channel ON messages (channel_id, ts DESC);
CREATE INDEX CONCURRENTLY idx_messages_user ON messages (user_id, ts DESC);
```

#### Query Optimization
```sql
-- Use prepared statements
EXPLAIN ANALYZE SELECT * FROM messages WHERE channel_id = $1 ORDER BY ts DESC LIMIT 100;
```

### 2. Caching Strategy

#### Redis Cache
```python
import redis

redis_client = redis.Redis(host='redis', port=6379, db=0)

@functools.lru_cache(maxsize=1000)
def get_workspace(workspace_id):
    cached = redis_client.get(f"workspace:{workspace_id}")
    if cached:
        return json.loads(cached)
    
    workspace = fetch_workspace_from_db(workspace_id)
    redis_client.setex(f"workspace:{workspace_id}", 3600, json.dumps(workspace))
    return workspace
```

### 3. Application Scaling

#### Horizontal Scaling
```yaml
# Docker Compose scaling
version: '3.8'
services:
  slack-integration:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
```

## Troubleshooting

### Common Issues

#### 1. OAuth Flow Fails
**Symptoms:** OAuth redirect fails or callback not received
**Solutions:**
- Verify redirect URI matches Slack App configuration
- Check CORS settings
- Ensure SSL certificate is valid
- Review logs for detailed error messages

#### 2. Webhook Events Not Received
**Symptoms:** No events from Slack
**Solutions:**
- Verify webhook URL is accessible
- Check signing secret configuration
- Ensure event subscriptions are enabled
- Test with Slack's Event Testing tool

#### 3. Rate Limiting Issues
**Symptoms:** Frequent 429 errors
**Solutions:**
- Implement exponential backoff
- Use batching for multiple operations
- Monitor rate limit headers
- Optimize API call patterns

#### 4. Database Connection Issues
**Symptoms:** Database connection errors
**Solutions:**
- Check database server status
- Verify connection string
- Monitor connection pool
- Check network connectivity

### Debug Mode

#### Enable Debug Logging
```bash
export LOG_LEVEL=debug
export SLACK_DEBUG=true
```

#### Debug Endpoints
```python
@app.route('/debug/info')
def debug_info():
    return {
        "config": {
            "client_id_configured": bool(os.getenv('SLACK_CLIENT_ID')),
            "cache_enabled": config.cache.enabled
        },
        "stats": service_status
    }
```

## Maintenance

### 1. Regular Tasks

#### Daily
- Check error logs
- Monitor system health
- Verify backup completion

#### Weekly
- Review performance metrics
- Update SSL certificates (if needed)
- Clean up old log files

#### Monthly
- Apply security updates
- Review and rotate secrets
- Update dependencies

### 2. Updates and Upgrades

#### Dependency Updates
```bash
# Update Python dependencies
pip install --upgrade -r requirements.txt

# Update Node.js dependencies
npm update
```

#### Schema Migrations
```bash
# Run database migrations
python -m alembic upgrade head
```

### 3. Security Audits

#### Regular Security Checks
```bash
# Scan for vulnerabilities
safety check
npm audit

# Check for exposed secrets
git-secrets --scan
```

## Support

### Documentation
- [API Documentation](./SLACK_API_DOCUMENTATION.md)
- [Configuration Guide](./slack_config.py)
- [Test Suite](./test_slack_integration.py)

### Contact
- **Support Email**: slack-support@atom.com
- **GitHub Issues**: https://github.com/atom-platform/slack-integration/issues
- **Documentation**: https://docs.atom.com/slack-integration

### Community
- **Slack Community**: https://community.atom.com
- **Stack Overflow**: Use tag `atom-slack-integration`

---

*Deployment Guide v2.0.0 - Last updated: December 1, 2023*