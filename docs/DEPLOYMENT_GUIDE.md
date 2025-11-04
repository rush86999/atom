# Atom Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying Atom in various environments, from local development to production cloud deployments.

## Quick Start

### Local Development (Docker)

```bash
# Clone the repository
git clone https://github.com/your-org/atom.git
cd atom

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Database: localhost:5432
```

### Local Development (Manual)

```bash
# Frontend setup
cd frontend-nextjs
npm install
npm run dev

# Backend setup (in separate terminal)
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main_api_app.py

# Database setup
docker-compose up -d postgres redis
```

## Production Deployment

### Environment Requirements

#### System Requirements
- **CPU**: 2+ cores recommended
- **Memory**: 4GB minimum, 8GB recommended
- **Storage**: 10GB+ for application and data
- **Network**: Stable internet connection for external integrations

#### Software Requirements
- **Docker**: 20.10+ and Docker Compose 2.0+
- **Node.js**: 18+ (for development)
- **Python**: 3.11+ (for development)
- **PostgreSQL**: 15+
- **Redis**: 7+

### Environment Configuration

#### Required Environment Variables

**Frontend (.env.local)**
```bash
NEXT_PUBLIC_API_URL=https://localhost/api
NEXT_PUBLIC_WS_URL=wss://localhost/ws
NEXT_PUBLIC_APP_URL=https://localhost
NEXTAUTH_URL=https://localhost
NEXTAUTH_SECRET=your-secret-key-here
```

**Backend (.env)**
```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/atom
REDIS_URL=redis://host:6379

# Authentication
SUPERTOKENS_CONNECTION_URI=https://localhost/auth
SUPERTOKENS_API_KEY=your-api-key

# External Services
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
PLAID_CLIENT_ID=your-plaid-client-id
PLAID_SECRET=your-plaid-secret

# Security
SECRET_KEY=your-backend-secret-key
CORS_ORIGINS=https://localhost

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### Docker Production Deployment

#### Using Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  frontend:
    image: atom/frontend:latest
    build:
      context: ./frontend-nextjs
      dockerfile: Dockerfile.prod
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=https://localhost/api
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    image: atom/backend:latest
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@database:5432/atom
      - REDIS_URL=redis://redis:6379
    depends_on:
      - database
      - redis
    restart: unless-stopped

  database:
    image: postgres:15
    environment:
      - POSTGRES_DB=atom
      - POSTGRES_USER=atom
      - POSTGRES_PASSWORD=secure-password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
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
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

#### Deployment Commands

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale backend=3

# Update deployment
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes Deployment

#### Configuration Files

**Namespace**
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: atom
```

**Frontend Deployment**
```yaml
# k8s/frontend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atom-frontend
  namespace: atom
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
          value: "production"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: atom-frontend-service
  namespace: atom
spec:
  selector:
    app: atom-frontend
  ports:
  - port: 80
    targetPort: 3000
  type: ClusterIP
```

**Backend Deployment**
```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atom-backend
  namespace: atom
spec:
  replicas: 3
  selector:
    matchLabels:
      app: atom-backend
  template:
    metadata:
      labels:
        app: atom-backend
    spec:
      containers:
      - name: backend
        image: atom/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: atom-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "200m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: atom-backend-service
  namespace: atom
spec:
  selector:
    app: atom-backend
  ports:
  - port: 8000
    targetPort: 8000
```

**Ingress Configuration**
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: atom-ingress
  namespace: atom
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - localhost
    secretName: atom-tls
  rules:
  - host: localhost
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: atom-frontend-service
            port:
              number: 80
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: atom-backend-service
            port:
              number: 8000
```

#### Kubernetes Deployment Commands

```bash
# Apply all configurations
kubectl apply -f k8s/

# Check deployment status
kubectl get all -n atom

# View logs
kubectl logs -l app=atom-frontend -n atom -f
kubectl logs -l app=atom-backend -n atom -f

# Scale deployments
kubectl scale deployment atom-frontend --replicas=5 -n atom
kubectl scale deployment atom-backend --replicas=5 -n atom
```

### Cloud-Specific Deployments

#### AWS ECS Deployment

**Task Definition**
```json
{
  "family": "atom",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account-id:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "atom/frontend:latest",
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/atom",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "frontend"
        }
      }
    }
  ]
}
```

#### Google Cloud Run

```bash
# Deploy frontend
gcloud run deploy atom-frontend \
  --image gcr.io/your-project/atom-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars NODE_ENV=production

# Deploy backend
gcloud run deploy atom-backend \
  --image gcr.io/your-project/atom-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=your-database-url
```

## Database Setup

### PostgreSQL Configuration

```sql
-- Create database and user
CREATE DATABASE atom;
CREATE USER atom_user WITH ENCRYPTED PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE atom TO atom_user;

-- Run migrations
-- This is handled automatically by Prisma on application startup
```

### Database Backups

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups/atom"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
pg_dump -h localhost -U atom_user atom > $BACKUP_DIR/atom_backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/atom_backup_$DATE.sql

# Keep only last 7 days
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
```

## SSL/TLS Configuration

### Using Let's Encrypt

```nginx
# nginx.conf
server {
    listen 80;
    server_name localhost;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name localhost;

    ssl_certificate /etc/letsencrypt/live/localhost/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/localhost/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket for real-time features
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## Monitoring and Logging

### Application Monitoring

**Frontend Monitoring**
```javascript
// frontend-nextjs/lib/monitoring.js
import { init } from '@sentry/nextjs';

init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
});
```

**Backend Monitoring**
```python
# backend/monitoring.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[FastApiIntegration()],
    traces_sample_rate=1.0,
    environment=os.getenv('ENVIRONMENT', 'development')
)
```

### Logging Configuration

```python
# backend/logging_config.py
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/atom/backend.log')
    ]
)
```

## Performance Optimization

### Frontend Optimization

```javascript
// next.config.js
module.exports = {
  compress: true,
  poweredByHeader: false,
  images: {
    domains: ['your-cdn-domain.com'],
    formats: ['image/avif', 'image/webp'],
  },
  experimental: {
    optimizeCss: true,
  },
}
```

### Backend Optimization

```python
# backend/performance.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Database connection pooling
DATABASE_CONFIG = {
    "min_size": 5,
    "max_size": 20,
    "max_queries": 50000,
    "max_inactive_connection_lifetime": 300.0,
}
```

## Security Hardening

### Security Headers

```nginx
# Security headers in nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
```

### Rate Limiting

```python
# backend/security.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request):
    # Your endpoint logic
    pass
```

## Backup and Disaster Recovery

### Automated Backup Strategy

```bash
#!/bin/bash
# backup.sh

# Database backup
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > /backups/db/atom_$(date +%Y%m%d).sql.gz

# File backups
tar -czf /backups/files/atom_files_$(date +%Y%m%d).tar.gz /app/uploads

# Upload to cloud storage
aws s3 cp /backups/db/atom_$(date +%Y%m%d).sql.gz s3://your-backup-bucket/db/
aws s3 cp /backups/files/atom_files_$(date +%Y%m%d).tar.gz s3://your-backup-bucket/files/
```

### Recovery Procedures

```bash
# Database recovery
gunzip -c atom_backup.sql.gz | psql -h $DB_HOST -U $DB_USER $DB_NAME

# File recovery
tar -xzf atom_files.tar.gz -C /app/uploads
```

## Troubleshooting

### Common Issues

**Database Connection Issues**
```bash
# Check database connectivity
psql -h localhost -U atom_user -d atom

# Check connection pool
netstat -an | grep 5432
```

**Application Logs**
```bash
# View application logs
docker-compose logs -f frontend
docker-compose logs -f backend

# Kubernetes logs
kubectl logs -l app=atom-frontend -n atom
```

**Performance Issues**
```bash
# Check resource usage
docker stats
kubectl top pods -n atom

# Database performance
psql -c "SELECT * FROM pg_stat_activity;"
```

### Health Checks

```bash
# Application health
curl https://localhost/health

# API health
curl https://localhost/api/health

# Database health
psql -h localhost -U atom_user -d atom -c "SELECT 1;"

# Redis health
redis-cli ping