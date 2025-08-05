# Environment Separation Guide

## 🔧 Local Development vs Cloud-Hosted Deployment

This document explains how to separate local development environments from cloud-hosted deployments, ensuring secure credential management and proper configuration handling.

## 📋 Quick Start

### Local Development
```bash
# Install PostgreSQL locally or use Docker
chmod +x test-local.sh
./test-local.sh setup          # Set up local environment
./test-local.sh test           # Run complete local E2E tests
./test-local.sh start          # Start local services
```

### Cloud Deployment
```bash
# Deploy to any cloud platform
./test-cloud.sh               # Auto-detect cloud platform
./test-cloud.sh fly          # Specifically test Fly.io
./test-cloud.sh vercel       # Specifically test Vercel
```

## 🌍 Environment Differences

| Feature | Local | Cloud |
|---------|--------|--------|
| **Database** | Local PostgreSQL | Managed PostgreSQL |
| **Redis** | Local Redis | Managed Redis/Cloud instances |
| **Secrets** | `.env.local` file | Cloud secrets/environment variables |
| **URLs** | `http://localhost:3000` | `https://yourapp.com` |
| **SSL** | Disabled | Required (HTTPS only) |
| **Variables** | Individual DB params | `DATABASE_URL` combined string |

## 🔐 Security Configuration

### Local Environment (.env.local)
```bash
# Never commit this file
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=atom_local
POSTGRES_USER=atom_user
POSTGRES_PASSWORD=local_dev_secure_password
JWT_SECRET=local-dev-secret-32-char-key
OPENAI_API_KEY=your_openai_key_here
```

### Cloud Environment (Cloud Variables)
```bash
# Set these in your cloud provider's dashboard
DATABASE_URL=postgresql://user:pass@cloudhost.com:5432/atom_prod
JWT_SECRET=cloud_production_secret_very_long
OPENAI_API_KEY=your_actual_openai_key
VERCEL_URL=your-app-123.vercel.app
```

## 🚀 Cloud Platform Setup

### Railway
1. Set environment variables in Railway Dashboard
2. Uses `DATABASE_URL` automatically
3. Include `init-test-db.sql` in deployment

### Fly.io
```bash
# Deploy with Fly.io
fly launch
fly apps create atom-app
fly secrets set DATABASE_URL=... JWT_SECRET=... OPENAI_API_KEY=...
```

### Vercel
```bash
# Deploy to Vercel
vercel --prod
vercel env add DATABASE_URL production
```

## 🧪 Testing Commands

### Local Tests
```bash
# Complete local E2E testing
npm run test:local

# Local database setup
./test-local.sh setup

# Local ready check
./test-local.sh test
```

### Cloud Tests
```bash
# Deploy then test
./deploy-to-cloud.sh && ./test-cloud.sh

# Specific platform testing
./test-cloud.sh fly
./test-cloud.sh railway
```

### Database Migration Testing
```bash
# Local migrations
npm run db:migrate:local

# Cloud migrations (handled by cloud provider)
npm run db:migrate:cloud
```

## 📊 Configuration Files

### Local Directory Structure
```
app_build_docker/
├── .env.local          # NEVER COMMIT - your local config
├── docker-compose.local.yml    # Local development stack
├── config/
│   ├── environments.js           # Environment detection
│   └── secrets/                  # Local secrets (gitignored)
├── docker-configs/               # Cloud-specific files
│   ├── fly.toml
│   ├── railway.json
│   ├── vercel.json
│   └── render.yaml
└── scripts/
    ├── test-local.sh
    └── test-cloud.sh
```

### Cloud Deployment Files
- `fy.toml` - Fly.io configuration
- `railway.json` - Railway deployment
- `vercel.json` - Vercel settings
- `render.yaml` - Render.com setup

## 🔍 Testing Checklist

### **Before Committing**
- [ ] Ensure `.env.local` is in `.gitignore`
- [ ] No hardcoded credentials in source code
- [ ] All tests pass locally (`./test-local.sh test`)
- [ ] Cloud environment validates (`./test-cloud.sh`)

### **Before Deployment**
- [ ] Set all secrets in cloud provider
- [ ] Verify `DATABASE_URL` is configured
- [ ] Check build compiles successfully
- [ ] Test endpoints respond correctly
- [ ] Validate PostgreSQL connection

### **Production Validation**
- [ ] Test complete E2E workflow
- [ ] Verify HTTPS endpoints work
- [ ] Check database migrations
- [ ] Validate external API integrations

## 🚨 Common Issues & Solutions

### Local PostgreSQL Not Starting
```bash
# Check if PostgreSQL is installed
which pg_isready || brew install postgres

# Start with Docker
docker compose -f docker-compose.local.yml up -d
```

### Cloud Database Connection
```bash
# Test cloud database
node -e "const Client=require('pg').Client; new Client({connectionString:process.env.DATABASE_URL}).connect().then(c=>c.query('SELECT NOW()').then(r=>console.log(r.rows[0])).finally(()=>c.end()))"
```

### Environment Detection
```javascript
// In your code
const { getConfig } = require('./config/environments');
const config = getConfig();
// config.isLocal === true on local
// config.isCloudHosted === true on cloud
```

## 📞 Support and Next Steps

1. **Security Review**: Ensure all credentials are encrypted
2. **Data Migration**: Import production data safely
3. **Monitoring Setup**: Enable CloudWatch, Sentry, Datadog
4. **Backup Strategy**: Implement automated PostgreSQL backups
5. **Performance Testing**: Use `./test-cloud.sh performance`

For specific cloud provider setup, see individual platform guides in `docker-configs/` directory.