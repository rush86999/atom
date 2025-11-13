#!/bin/bash

# ATOM Production Environment Setup Script
# This script sets up the production environment for the ATOM application

set -e  # Exit on any error

echo "🚀 Starting ATOM Production Environment Setup..."
echo "=================================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo "❌ Please do not run this script as root"
  exit 1
fi

# Check for required tools
echo "🔍 Checking required tools..."
for cmd in docker docker-compose node npm python3; do
  if ! command -v $cmd &> /dev/null; then
    echo "❌ Required tool '$cmd' not found. Please install it first."
    exit 1
  fi
  echo "✅ $cmd found"
done

# Create production directory structure
echo "📁 Creating production directory structure..."
mkdir -p production/{config,logs,data,backups,ssl}

# Set up environment variables
echo "🔧 Setting up environment variables..."
cat > production/.env << 'EOF'
# ATOM Production Environment Configuration
NODE_ENV=production

# Database Configuration
DATABASE_URL=postgresql://atom_user:${DATABASE_PASSWORD}@localhost:5432/atom_production
POSTGRES_DB=atom_production
POSTGRES_USER=atom_user
POSTGRES_PASSWORD=${DATABASE_PASSWORD}

# Redis Configuration
REDIS_URL=redis://localhost:6379

# API Configuration
PYTHON_API_PORT=5058
NEXT_PUBLIC_API_URL=http://localhost:5058
NEXT_PUBLIC_APP_URL=https://localhost

# Security Configuration
FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# External Service Configuration (Set these in production)
# GOOGLE_CLIENT_ID=your_google_client_id
# GOOGLE_CLIENT_SECRET=your_google_client_secret
# PLD_CLIENT_ID=your_plaid_client_id
# PLD_SECRET=your_plaid_secret
# STRIPE_SECRET_KEY=your_stripe_secret_key

# Monitoring
SENTRY_DSN=your_sentry_dsn
LOG_LEVEL=INFO

# Feature Flags
ENABLE_ANALYTICS=true
ENABLE_MONITORING=true
EOF

echo "⚠️  Please update production/.env with your actual production values"
echo "⚠️  Generate secure keys and set database passwords"

# Create Docker Compose for production
echo "🐳 Creating Docker Compose configuration..."
cat > production/docker-compose.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    container_name: atom_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: atom_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

  # Backend API
  backend:
    build:
      context: ../backend/python-api-service
      dockerfile: Dockerfile
    container_name: atom_backend
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY}
      - PYTHON_API_PORT=5058
    ports:
      - "5058:5058"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5058/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Frontend (Next.js)
  frontend:
    build:
      context: ../frontend-nextjs
      dockerfile: Dockerfile.production
    container_name: atom_frontend
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:5058
      - NEXT_PUBLIC_APP_URL=${NEXT_PUBLIC_APP_URL}
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  # Nginx Reverse Proxy (Optional - for production deployment)
  nginx:
    image: nginx:alpine
    container_name: atom_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
EOF

# Create production Dockerfile for frontend
echo "📦 Creating production Dockerfile for frontend..."
cat > frontend-nextjs/Dockerfile.production << 'EOF'
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY yarn.lock ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# Set permissions
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

ENV PORT 3000

CMD ["npm", "start"]
EOF

# Create nginx configuration
echo "🌐 Creating nginx configuration..."
cat > production/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:5058;
    }

    upstream frontend {
        server frontend:3000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=100r/s;

    server {
        listen 80;
        server_name _;

        # Redirect to HTTPS (uncomment when SSL is configured)
        # return 301 https://$server_name$request_uri;

        # Frontend
        location / {
            limit_req zone=general burst=20 nodelay;
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Backend API
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health checks
        location /healthz {
            access_log off;
            proxy_pass http://backend/healthz;
        }

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    }

    # HTTPS server (uncomment and configure when SSL certificates are available)
    # server {
    #     listen 443 ssl http2;
    #     server_name localhost;
    #
    #     ssl_certificate /etc/nginx/ssl/cert.pem;
    #     ssl_certificate_key /etc/nginx/ssl/key.pem;
    #
    #     # SSL configuration
    #     ssl_protocols TLSv1.2 TLSv1.3;
    #     ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    #     ssl_prefer_server_ciphers off;
    #
    #     # Include the same location blocks as above
    #     include /etc/nginx/conf.d/locations.conf;
    # }
}
EOF

# Create startup script
echo "⚡ Creating startup script..."
cat > production/start.sh << 'EOF'
#!/bin/bash

set -e

echo "🚀 Starting ATOM Production Stack..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found. Please create it from .env.example"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build and start services
echo "📦 Building and starting services..."
docker-compose up -d --build

echo "⏳ Waiting for services to be healthy..."
sleep 30

# Check service health
echo "🔍 Checking service health..."
for service in postgres redis backend frontend; do
    if docker-compose ps $service | grep -q "Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service failed to start"
        docker-compose logs $service
        exit 1
    fi
done

echo "🎉 ATOM Production Stack is running!"
echo "📊 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:5058"
echo "🗄️  Database: localhost:5432"
echo "💾 Redis: localhost:6379"
EOF

chmod +x production/start.sh

# Create backup script
echo "💾 Creating backup script..."
cat > production/backup.sh << 'EOF'
#!/bin/bash

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="atom_backup_${TIMESTAMP}.sql"

echo "💾 Starting database backup..."

# Ensure backup directory exists
mkdir -p $BACKUP_DIR

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Backup PostgreSQL database
docker-compose exec -T postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > $BACKUP_DIR/$BACKUP_FILE

if [ $? -eq 0 ]; then
    echo "✅ Backup completed: $BACKUP_DIR/$BACKUP_FILE"

    # Compress backup
    gzip $BACKUP_DIR/$BACKUP_FILE
    echo "✅ Backup compressed: $BACKUP_DIR/${BACKUP_FILE}.gz"

    # Clean up old backups (keep last 7 days)
    find $BACKUP_DIR -name "atom_backup_*.sql.gz" -mtime +7 -delete
    echo "🧹 Old backups cleaned up"
else
    echo "❌ Backup failed"
    exit 1
fi
EOF

chmod +x production/backup.sh

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > production/monitor.sh << 'EOF'
#!/bin/bash

echo "📊 ATOM Production Stack Monitoring"
echo "===================================="

# Check Docker containers
echo "🐳 Container Status:"
docker-compose ps

echo ""
echo "🔍 Service Health:"

# Check backend health
BACKEND_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5058/healthz || echo "DOWN")
if [ "$BACKEND_HEALTH" = "200" ]; then
    echo "✅ Backend API: Healthy (HTTP $BACKEND_HEALTH)"
else
    echo "❌ Backend API: Unhealthy (HTTP $BACKEND_HEALTH)"
fi

# Check frontend health
FRONTEND_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "DOWN")
if [ "$FRONTEND_HEALTH" = "200" ]; then
    echo "✅ Frontend: Healthy (HTTP $FRONTEND_HEALTH)"
else
    echo "❌ Frontend: Unhealthy (HTTP $FRONTEND_HEALTH)"
fi

# Database connections
echo ""
echo "🗄️  Database Connections:"
docker-compose exec postgres psql -U atom_user -d atom_production -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';"

# Redis memory usage
echo ""
echo "💾 Redis Memory:"
docker-compose exec redis redis-cli info memory | grep used_memory_human

echo ""
echo "📈 Recent Logs (last 10 lines):"
docker-compose logs --tail=10
EOF

chmod +x production/monitor.sh

echo ""
echo "🎉 Production environment setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. 📝 Edit production/.env with your actual production values"
echo "2. 🔑 Generate secure keys and set passwords"
echo "3. 🐳 Run: cd production && ./start.sh"
echo "4. 📊 Monitor: cd production && ./monitor.sh"
echo "5. 💾 Set up regular backups: cd production && ./backup.sh"
echo ""
echo "⚠️  Remember to:"
echo "   - Set up SSL certificates for production"
echo "   - Configure domain names and DNS"
echo "   - Set up monitoring and alerting"
echo "   - Configure backup retention policies"
echo "   - Set up security scanning and updates"
echo ""
echo "🚀 ATOM is ready for production deployment!"
