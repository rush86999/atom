# Deployment Documentation

Production deployment, monitoring, and operations guides.

## 📚 Quick Navigation

### Deployment Guides
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Complete deployment instructions
- **[Cloud Deployment](CLOUD_DEPLOYMENT.md)** - AWS, GCP, Azure deployment
- **[Docker Deployment](DOCKER_DEPLOYMENT.md)** - Container deployment
- **[Production Deployment](PRODUCTION_DEPLOYMENT.md)** - Production setup
- **[Production Deployment Summary](PRODUCTION_DEPLOYMENT_SUMMARY.md)** - Deployment overview

### CI/CD
- **[CI/CD Runbook](CI_CD_RUNBOOK.md)** - CI/CD pipeline operations
- **[CI/CD Troubleshooting](CI_CD_TROUBLESHOOTING.md)** - Pipeline troubleshooting

### Monitoring
- **[Monitoring Setup](MONITORING_SETUP.md)** - Health checks and metrics
- **[Deployment Runbook](DEPLOYMENT_RUNBOOK.md)** - Deployment procedures

## 🚀 Quick Start

### Docker Deployment
```bash
# Clone and setup
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env

# Start with Docker Compose
docker-compose -f docker-compose-personal.yml up -d

# Check health
curl http://localhost:8000/health/live
```

### Cloud Deployment
- **DigitalOcean**: [1-Click Deploy](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)
- **AWS**: See Cloud Deployment guide
- **GCP**: See Cloud Deployment guide
- **Azure**: See Cloud Deployment guide

## 📊 Monitoring

### Health Checks
- **Liveness**: `/health/live` - Service is running
- **Readiness**: `/health/ready` - Service is ready to accept traffic
- **Metrics**: `/health/metrics` - Prometheus metrics

### Key Metrics
- HTTP request rates and error rates
- Agent execution performance
- Database connection pool health
- Disk space and memory usage

## 🔧 Operations

### Daily Operations
- **[Operations Guide](../operations/OPERATIONS_GUIDE.md)** - Daily tasks and procedures
- **[Troubleshooting](../operations/TROUBLESHOOTING.md)** - Common issues and solutions

### Rollback Procedure
```bash
# Rollback to previous version
git log --oneline -n 10
git checkout <previous-commit>
docker-compose -f docker-compose-personal.yml up -d --build
```

## 📖 Related Documentation

- **[Operations](../operations/README.md)** - Operations guides
- **[Security](../SECURITY/README.md)** - Security best practices
- **[Development](../DEVELOPMENT/README.md)** - Development setup

---

*Last Updated: April 12, 2026*
