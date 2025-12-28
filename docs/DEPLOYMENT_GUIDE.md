# ATOM Platform Deployment Guide

**Version:** 1.0.0
**Last Updated:** December 14, 2025

## Overview

This guide provides comprehensive instructions for deploying the ATOM platform in production environments with the enhanced AI E2E testing framework.

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 50GB SSD
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Windows 10+

### Recommended Requirements
- **CPU**: 8 cores
- **RAM**: 16GB
- **Storage**: 100GB SSD
- **Load Balancer**: Nginx or similar
- **Database**: PostgreSQL 13+
- **Cache**: Redis 6+

## Prerequisites

1. **Node.js** (v18+)
2. **Python** (v3.11+)
3. **PostgreSQL** (optional for production)
4. **Redis** (optional for production)
5. **Nginx** (recommended for production)

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/rush86999/atom.git
cd atom
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations (if using PostgreSQL)
alembic upgrade head

# Fix any existing workflow data
python scripts/fix_workflow_data.py
```

### 3. Frontend Setup

```bash
# Navigate to frontend
cd ../frontend-nextjs

# Install dependencies
npm install

# Configure environment variables
cp .env.example .env.local
# Edit .env.local with your configuration

# Build for production
npm run build
```

### 4. Testing

Run the comprehensive test suite before deployment:

```bash
# Simple bug identification tests
python ../testing/simple_test_runner.py

# Enhanced AI E2E tests (requires MCP server)
python ../testing/enhanced_ai_e2e_integration.py
```

## Production Deployment

### Option 1: Docker Deployment (Recommended)

#### Create Dockerfile for Backend

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main_api_app.py:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Create Dockerfile for Frontend

```dockerfile
# frontend-nextjs/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source code and build
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine AS runner

WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
```

#### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - DATABASE_URL=postgresql://user:pass@db:5432/atom
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  frontend:
    build: ./frontend-nextjs
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=atom
      - POSTGRES_USER=atom
      - POSTGRES_PASSWORD=atom_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:6-alpine
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
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
```

#### Deploy with Docker

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option 2: Manual Deployment

#### Backend Service

```bash
# Using systemd (Linux)
sudo tee /etc/systemd/system/atom-backend.service > /dev/null <<EOF
[Unit]
Description=ATOM Backend API
After=network.target

[Service]
Type=simple
User=atom
WorkingDirectory=/opt/atom/backend
Environment=PATH=/opt/atom/backend/venv/bin
ExecStart=/opt/atom/backend/venv/bin/python main_api_app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable atom-backend
sudo systemctl start atom-backend
```

#### Frontend Service

```bash
# Using PM2
cd frontend-nextjs
npm install -g pm2

# Start application
pm2 start npm --name "atom-frontend" -- start

# Save PM2 configuration
pm2 save
pm2 startup
```

#### Nginx Configuration

```nginx
# /etc/nginx/sites-available/atom
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

## Environment Configuration

### Backend (.env)

```env
# Application
DEBUG=false
SECRET_KEY=your-secret-key-here
API_KEY=your-api-key-here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/atom

# Redis
REDIS_URL=redis://localhost:6379

# AI Services
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=your-google-key

# OAuth (Configure all required OAuth providers)
SLACK_BOT_TOKEN=xoxb-
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret

# Microsoft
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret

# Google
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Add other OAuth providers as needed
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=https://your-domain.com/api
NEXT_PUBLIC_WS_URL=wss://your-domain.com
NEXT_PUBLIC_APP_NAME=ATOM Platform
NEXT_PUBLIC_APP_VERSION=1.0.0
```

## Security Considerations

### 1. HTTPS/SSL

```bash
# Using Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 2. Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 3. Database Security

- Use strong passwords
- Enable SSL connections
- Restrict database access to application servers
- Regular backups

### 4. API Security

- All endpoints are rate-limited by default (120 req/min)
- Input validation is enabled
- Security headers are automatically added
- CORS is configured properly

## Monitoring and Logging

### Application Logs

```bash
# Backend logs
tail -f backend/logs/errors.log
tail -f backend/logs/performance.log

# Frontend logs (if using PM2)
pm2 logs atom-frontend
```

### Health Checks

```bash
# Backend health
curl https://your-domain.com/health

# Frontend health
curl https://your-domain.com/api/health
```

### Performance Monitoring

The application includes built-in performance metrics:

- Response time tracking
- Request count by endpoint
- Error rate monitoring
- Success rate calculation

Access metrics via: `/api/agent/metrics` (protected endpoint)

## Testing in Production

### Run Tests

```bash
# Deploy with test mode
DEBUG=false python testing/simple_test_runner.py

# Full AI E2E tests (requires configuration)
python testing/enhanced_ai_e2e_integration.py
```

### Expected Results

After proper deployment, you should see:
- **Frontend**: 100% pages accessible
- **Backend**: 80%+ endpoints responding
- **Integration**: Frontend-backend communication working
- **Performance**: <2s average response time
- **Security**: All security headers present

## Troubleshooting

### Common Issues

1. **Workflow Validation Errors**
   ```bash
   python backend/scripts/fix_workflow_data.py
   ```

2. **Database Connection Issues**
   - Check DATABASE_URL in .env
   - Ensure database is running
   - Verify credentials

3. **Frontend Build Failures**
   - Clear node_modules: `rm -rf node_modules && npm install`
   - Check environment variables
   - Verify API endpoint configuration

4. **CORS Issues**
   - Update CORS origins in backend
   - Check nginx proxy configuration

5. **OAuth Callbacks**
   - Ensure callback URLs match OAuth app configuration
   - Check HTTPS requirements (some providers require HTTPS)

### Support

For issues:
1. Check logs: `backend/logs/errors.log`
2. Run health checks: `/health` endpoint
3. Review test results: `test_results/` directory
4. Check network configuration

## Scaling Recommendations

### Horizontal Scaling

- Use load balancer (Nginx/HAProxy)
- Deploy multiple backend instances
- Use Redis for session storage
- Implement database read replicas

### Performance Optimization

- Enable gzip compression (included)
- Use CDN for static assets
- Implement database connection pooling
- Cache frequent API responses
- Use async processing for long tasks

### High Availability

- Database replication
- Multi-region deployment
- Health check monitoring
- Automated failover
- Regular backups and disaster recovery

## Maintenance

### Regular Tasks

1. **Daily**: Monitor error logs and performance metrics
2. **Weekly**: Review security updates and dependencies
3. **Monthly**: Run full test suite and security scan
4. **Quarterly**: Update dependencies and review architecture

### Backup Strategy

```bash
# Database backup
pg_dump atom > backup_$(date +%Y%m%d).sql

# Application data backup
tar -czf data_backup_$(date +%Y%m%d).tar.gz \
    backend/workflows.json \
    backend/agent_status.json \
    backend/data/
```

---

## Quick Start Checklist

- [ ] Install dependencies (Node.js, Python, PostgreSQL, Redis)
- [ ] Configure environment variables
- [ ] Run database migrations
- [ ] Fix workflow data: `python scripts/fix_workflow_data.py`
- [ ] Run tests: `python testing/simple_test_runner.py`
- [ ] Build frontend: `npm run build`
- [ ] Configure reverse proxy (Nginx)
- [ ] Set up SSL certificates
- [ ] Configure monitoring
- [ ] Deploy to production
- [ ] Run final smoke tests

---

**Success Criteria**:
- ✅ All frontend pages accessible (100%)
- ✅ Backend API responding (80%+)
- ✅ Integration tests passing
- ✅ Security headers present
- ✅ Performance <2s average response
- ✅ Error monitoring active
- ✅ Backup strategy in place