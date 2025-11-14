# ATOM Production Deployment Guide

## 🚀 Overview

This guide covers the complete production deployment process for the ATOM Integration Platform, including infrastructure setup, security hardening, monitoring, and maintenance procedures.

## 📋 Prerequisites

### Infrastructure Requirements
- **Kubernetes Cluster**: v1.24+ with RBAC enabled
- **Database**: PostgreSQL 13+ with replication
- **Cache**: Redis 7+ with persistence
- **Load Balancer**: NGINX or equivalent
- **SSL/TLS**: Wildcard certificate for domain
- **Storage**: Persistent volumes for Redis and logs

### Tooling Requirements
- **Docker**: v20+ for containerization
- **kubectl**: Latest version for K8s management
- **Helm**: v3+ for package management (optional)
- **CI/CD**: GitHub Actions or equivalent

## 🔧 Environment Setup

### 1. Clone and Prepare Repository
```bash
git clone https://github.com/your-org/atom.git
cd atom/frontend-nextjs
```

### 2. Environment Variables
```bash
# Copy production environment template
cp .env.production.example .env.local

# Fill in your actual values
nano .env.local
```

### 3. Install Dependencies
```bash
npm install --production
```

## 🐳 Container Build and Deploy

### 1. Build Production Image
```bash
# Build optimized production image
npm run build

# Build Docker image
docker build -t atom:production .
```

### 2. Tag and Push to Registry
```bash
# Tag with version
docker tag atom:production ghcr.io/your-org/atom:v1.0.0

# Push to registry
docker push ghcr.io/your-org/atom:v1.0.0
```

## ☸️ Kubernetes Deployment

### 1. Create Secrets
```bash
# Create namespace
kubectl create namespace atom-production

# Apply secrets (encrypt sensitive values)
kubectl apply -f k8s/secrets.yaml
```

### 2. Deploy Infrastructure
```bash
# Deploy Redis first
kubectl apply -f k8s/redis.yaml

# Deploy application
kubectl apply -f k8s/deployment.yaml

# Apply networking
kubectl apply -f k8s/ingress.yaml
```

### 3. Verify Deployment
```bash
# Check pod status
kubectl get pods -n atom-production

# Check services
kubectl get services -n atom-production

# Check ingress
kubectl get ingress -n atom-production
```

## 🔒 Security Configuration

### 1. SSL/TLS Setup
```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml

# Create cluster issuer
kubectl apply -f k8s/cert-manager.yaml
```

### 2. Network Policies
```bash
# Apply network policies
kubectl apply -f k8s/network-policy.yaml
```

### 3. Security Context
```yaml
# All containers should run as non-root
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  capabilities:
    drop:
      - ALL
```

## 📊 Monitoring Setup

### 1. Health Checks
```bash
# Verify health endpoint
curl https://yourdomain.com/api/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "checks": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "auth": {"status": "healthy"}
  }
}
```

### 2. Metrics Collection
```bash
# Setup Prometheus monitoring
kubectl apply -f k8s/monitoring/

# Setup Grafana dashboards
kubectl apply -f k8s/grafana/
```

### 3. Alert Configuration
```bash
# Setup Alertmanager
kubectl apply -f k8s/alertmanager/
```

## 🔄 CI/CD Pipeline

### 1. GitHub Actions Setup
```yaml
# Workflow already defined in .github/workflows/production-deploy.yml
# Add repository secrets:
# - NEXTAUTH_SECRET
# - DATABASE_URL
# - REDIS_URL
# - Various API keys
```

### 2. Automated Testing
```bash
# Run test suite
npm run test:ci

# Type checking
npm run type-check

# Lighthouse audit
npm run lighthouse:ci
```

### 3. Deployment Triggers
- **Automatic**: On merge to main branch
- **Manual**: Via GitHub Actions UI
- **Scheduled**: Health check deployments

## 🚀 Performance Optimization

### 1. Bundle Optimization
```bash
# Analyze bundle size
npm run analyze

# Optimize images
npx next-optimized-images

# Enable compression
# Configure in next.config.js
```

### 2. Caching Strategy
```javascript
// Configure caching headers
async headers() {
  return [
    {
      source: '/_next/static/:path*',
      headers: [
        {
          key: 'Cache-Control',
          value: 'public, max-age=31536000, immutable',
        },
      ],
    },
  ];
}
```

### 3. CDN Configuration
```bash
# Configure Cloudflare/CDN
# Enable caching for static assets
# Setup DDoS protection
# Configure geographic routing
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Pods Not Starting
```bash
# Check pod status
kubectl describe pod -n atom-production

# Check logs
kubectl logs -n atom-production -f deployment/atom-frontend

# Common causes:
# - Missing environment variables
# - Image pull failures
# - Resource constraints
```

#### 2. Health Check Failures
```bash
# Check database connection
kubectl exec -n atom-production deployment/atom-frontend -- npm run health:db

# Check Redis connection
kubectl exec -n atom-production deployment/atom-frontend -- npm run health:redis

# Common causes:
# - Network connectivity issues
# - Authentication failures
# - Resource exhaustion
```

#### 3. Performance Issues
```bash
# Check resource usage
kubectl top pods -n atom-production

# Check HPA status
kubectl get hpa -n atom-production

# Common causes:
# - Memory leaks
# - CPU throttling
# - Database query performance
```

### Debugging Commands
```bash
# Port forward for local debugging
kubectl port-forward -n atom-production svc/atom-frontend 3000:3000

# Access pod shell
kubectl exec -n atom-production -it deployment/atom-frontend -- /bin/sh

# Check events
kubectl get events -n atom-production --sort-by='.lastTimestamp'
```

## 📈 Maintenance Procedures

### 1. Regular Maintenance
```bash
# Daily: Check health status
curl https://yourdomain.com/api/health

# Weekly: Rotate secrets
kubectl create secret generic atom-secrets-new --from-env-file=.env.local
kubectl patch deployment atom-frontend -p '{"spec":{"template":{"spec":{"containers":[{"name":"atom-frontend","envFrom":[{"secretRef":{"name":"atom-secrets-new"}}]}]}}}}'

# Monthly: Update dependencies
npm update
npm audit fix
```

### 2. Backup Procedures
```bash
# Database backup
kubectl exec -n atom-production deployment/postgres -- pg_dump atom_prod > backup.sql

# Redis backup
kubectl exec -n atom-production deployment/redis -- redis-cli BGSAVE

# Application state backup
kubectl get deployment -n atom-production -o yaml > deployment-backup.yaml
```

### 3. Scaling Operations
```bash
# Manual scaling
kubectl scale deployment atom-frontend --replicas=5 -n atom-production

# Enable auto-scaling
kubectl apply -f k8s/hpa.yaml
```

## 🔧 Advanced Configuration

### 1. Feature Flags
```javascript
// Environment-based feature flags
const FEATURES = {
  NEW_DASHBOARD: process.env.FEATURE_NEW_DASHBOARD === 'true',
  ADVANCED_SEARCH: process.env.FEATURE_ADVANCED_SEARCH === 'true',
  AI_POWERED: process.env.FEATURE_AI_POWERED === 'true',
};
```

### 2. A/B Testing
```javascript
// Implement using experiments
const experiment = useExperiment('new-dashboard');
const showNewDashboard = experiment.variant === 'treatment';
```

### 3. Blue-Green Deployments
```yaml
# Use ArgoCD or similar for blue-green
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: atom-frontend
spec:
  strategy:
    blueGreen:
      activeService: atom-frontend-active
      previewService: atom-frontend-preview
```

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] Secrets created and encrypted
- [ ] SSL certificates in place
- [ ] Database migrations tested
- [ ] Performance benchmarks set
- [ ] Monitoring alerts configured
- [ ] Backup procedures verified
- [ ] Rollback plan documented

### Post-Deployment
- [ ] Health checks passing
- [ ] Monitoring metrics normal
- [ ] Performance tests passed
- [ ] Security scans passed
- [ ] User acceptance testing
- [ ] Documentation updated
- [ ] Team notified

## 🚨 Emergency Procedures

### 1. Service Outage
```bash
# Immediate rollback to previous version
kubectl rollout undo deployment/atom-frontend -n atom-production

# Check rollback status
kubectl rollout status deployment/atom-frontend -n atom-production
```

### 2. Database Issues
```bash
# Connect to database for troubleshooting
kubectl exec -it -n atom-production deployment/postgres -- psql -U postgres

# Check replication status
SELECT * FROM pg_stat_replication;
```

### 3. High Resource Usage
```bash
# Scale up resources
kubectl patch hpa atom-hpa -n atom-production -p '{"spec":{"maxReplicas":20}}'

# Add resource limits
kubectl patch deployment atom-frontend -n atom-production -p '{"spec":{"template":{"spec":{"containers":[{"name":"atom-frontend","resources":{"limits":{"memory":"1Gi","cpu":"1000m"}}}]}}}}'
```

## 📞 Support and Contacts

- **Infrastructure Team**: infra@yourdomain.com
- **Security Team**: security@yourdomain.com
- **Development Team**: dev@yourdomain.com
- **On-call Engineer**: oncall@yourdomain.com
- **Emergency Hotline**: +1-555-EMERG

## 📚 Additional Resources

- [Next.js Production Deployment](https://nextjs.org/docs/deployment)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Security Hardening Guide](https://owasp.org/)
- [Performance Optimization](https://web.dev/)

---

**Version**: 1.0.0  
**Last Updated**: 2024-01-01  
**Next Review**: 2024-04-01