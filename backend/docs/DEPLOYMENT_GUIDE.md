# Atom Deployment Guide

**Purpose**: Step-by-step guide for deploying Atom to staging and production
**Last Updated**: 2026-02-20
**Audience**: DevOps engineers, SREs

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Staging Deployment](#staging-deployment)
4. [Production Deployment](#production-deployment)
5. [Health Checks](#health-checks)
6. [Canary Deployment](#canary-deployment)
7. [Monitoring](#monitoring)

---

## Prerequisites

### Required Tools

- **kubectl**: 1.28+
  ```bash
  # Verify installation
  kubectl version --client

  # Install if missing (macOS)
  brew install kubectl

  # Install if missing (Linux)
  curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
  ```

- **Docker**: 24.0+
  ```bash
  # Verify installation
  docker --version

  # Install if missing (macOS)
  brew install --cask docker

  # Install if missing (Linux)
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  ```

- **GitHub CLI**: 2.40+
  ```bash
  # Verify installation
  gh --version

  # Install if missing (macOS)
  brew install gh

  # Install if missing (Linux)
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt update
  sudo apt install gh
  ```

- **Python**: 3.11+
  ```bash
  # Verify installation
  python --version

  # Install if missing (macOS)
  brew install python@3.11

  # Install if missing (Linux)
  sudo apt update
  sudo apt install python3.11 python3.11-venv
  ```

- **Prometheus**: 2.45+ (for monitoring)
  ```bash
  # Verify installation
  prometheus --version

  # Install if needed
  wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
  tar xvfz prometheus-2.45.0.linux-amd64.tar.gz
  cd prometheus-2.45.0.linux-amd64
  ./prometheus --version
  ```

### Required Access

**GitHub Access**:
- Repository write access
- Workflow trigger permissions
- Environment approval permissions (production)

**Kubernetes Access**:
- Cluster admin access (staging and production)
- kubectl context configured for both clusters
- Service account with deployment permissions

**Container Registry Access**:
- Push/pull access to registry
- Authentication configured in Docker/Kubernetes

**Monitoring Access**:
- Prometheus query access
- Grafana dashboard update access

### Required Secrets

Configure these secrets in GitHub repository settings (`Settings → Secrets and variables → Actions`):

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `KUBECONFIG_STAGING` | Staging cluster config (base64) | `base64 ~/.kube/config-staging` |
| `KUBECONFIG_PRODUCTION` | Production cluster config (base64) | `base64 ~/.kube/config-production` |
| `REGISTRY_USERNAME` | Container registry username | `dockerhub-user` |
| `REGISTRY_PASSWORD` | Container registry password | `dckr_pat_xxxxx` |
| `SMOKE_TEST_USERNAME` | Smoke test user | `smoke_test` |
| `SMOKE_TEST_PASSWORD` | Smoke test password | `changeme123` |
| `STAGING_URL` | Staging environment URL | `https://staging.atom.example.com` |
| `PRODUCTION_URL` | Production environment URL | `https://atom.example.com` |
| `PROMETHEUS_URL` | Monitoring endpoint | `http://prometheus:9090` |
| `GRAFANA_URL` | Dashboard URL | `http://grafana:3000` |
| `GRAFANA_API_KEY` | Grafana service account token | `eyJr...` |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | `https://hooks.slack.com/...` |

**Example: Setting a secret**:
```bash
# Encode kubeconfig
base64 ~/.kube/config-staging > kubeconfig-staging.base64

# Set secret via GitHub CLI
gh secret set KUBECONFIG_STAGING < kubeconfig-staging.base64

# Verify secret is set (value hidden)
gh secret list
```

---

## Environment Setup

### Kubernetes Cluster Setup

**Staging Cluster**:
```bash
# Create namespace
kubectl create namespace atom-staging

# Create secrets
kubectl create secret generic atom-secrets \
  --from-literal=database-url="postgresql://user:pass@host:5432/atom_staging" \
  --from-literal=byok-encryption-key="your-encryption-key-here" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --namespace=atom-staging

# Verify secrets
kubectl get secrets atom-secrets --namespace=atom-staging

# Deploy application (first time)
kubectl apply -f k8s/staging/ --namespace=atom-staging

# Verify deployment
kubectl get deployments --namespace=atom-staging
kubectl get pods --namespace=atom-staging
kubectl get services --namespace=atom-staging
```

**Production Cluster**:
```bash
# Create namespace
kubectl create namespace atom-production

# Create secrets
kubectl create secret generic atom-secrets \
  --from-literal=database-url="postgresql://user:pass@host:5432/atom_production" \
  --from-literal=byok-encryption-key="your-production-encryption-key" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --namespace=atom-production

# Verify secrets
kubectl get secrets atom-secrets --namespace=atom-production

# Deploy application (first time)
kubectl apply -f k8s/production/ --namespace=atom-production

# Verify deployment
kubectl get deployments --namespace=atom-production
kubectl get pods --namespace=atom-production
kubectl get services --namespace=atom-production
```

### Database Migration Setup

**Run migrations manually** (before first deployment):
```bash
# Activate virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Alembic migrations
alembic upgrade head

# Verify migrations
alembic current
alembic history | tail -5
```

**Verify smoke test user**:
```bash
# Check if smoke test user exists
psql -c "SELECT username, is_smoke_test_user FROM users WHERE username='smoke_test'"

# If not exists, create manually
python -c "
from backend.core.models import User
from backend.core.security import get_password_hash
from backend.core.database import SessionLocal

db = SessionLocal()
user = User(
    username='smoke_test',
    email='smoke-test@example.com',
    hashed_password=get_password_hash('smoke_test_password_change_in_prod'),
    is_smoke_test_user=True
)
db.add(user)
db.commit()
print('Smoke test user created successfully')
"
```

### Monitoring Setup

**Prometheus Configuration**:
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'atom'
    static_configs:
      - targets: ['atom-backend:8000']
    metrics_path: '/metrics'
```

**Grafana Dashboard**:
```bash
# Create dashboard via API
curl -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @backend/monitoring/grafana/deployment-overview.json

# Verify dashboard
curl -X GET "$GRAFANA_URL/api/dashboards/uid/atom-deployment-overview" \
  -H "Authorization: Bearer $GRAFANA_API_KEY"
```

---

## Staging Deployment

### Deployment Workflow

```mermaid
graph LR
    A[Push to main] --> B[CI Workflow]
    B --> C{Tests Pass?}
    C -->|No| D[Fail CI]
    C -->|Yes| E[Build Docker Image]
    E --> F[Push to Registry]
    F --> G[Deploy to Staging]
    G --> H{Smoke Tests Pass?}
    H -->|No| I[Automatic Rollback]
    H -->|Yes| J[Deployment Complete]
    I --> J
```

### Step-by-Step Procedure

**Step 1: Push to main branch**
```bash
# Ensure your branch is up to date
git checkout main
git pull origin main

# Merge your feature branch
git merge feature/my-new-feature

# Push to trigger deployment
git push origin main
```

**Step 2: Monitor CI workflow**
```bash
# Watch CI pipeline progress
gh workflow view ci

# Watch latest run
gh run watch --interval 10

# Expected output:
# ✓ backend-test (3m 30s)
# ✓ frontend-build (1m 15s)
# ✓ backend-test-full (8m 45s)
# ✓ test-quality-gates (4m 20s)
# ✓ build-docker (2m 10s)
```

**Step 3: Monitor deployment workflow**
```bash
# Watch deployment progress
gh workflow view deploy
gh run watch --interval 30

# Expected output:
# ✓ test (5m 10s)
# ✓ build (3m 20s)
# → deploy-staging (in progress)
```

**Step 4: Verify deployment**
```bash
# Check health endpoints
curl -f https://staging.atom.example.com/health/live
curl -f https://staging.atom.example.com/health/ready
curl -f https://staging.atom.example.com/health/db

# Expected output:
# {"status":"healthy","timestamp":"2026-02-20T10:30:00Z"}
```

**Step 5: Run manual smoke tests** (optional)
```bash
# Run automated smoke tests
./scripts/smoke-tests.sh staging

# Or manual smoke tests
./scripts/manual-smoke-tests.sh staging

# Expected output:
# ✓ Authentication: Success
# ✓ Health endpoints: All pass
# ✓ Agent execution: API responds
# ✓ Canvas presentation: API responds
# ✓ Skills endpoint: API responds
```

**Step 6: Verify metrics**
```bash
# Check error rate
curl "$PROMETHEUS_URL/api/v1/query?query=error_rate{environment=\"staging\"}"

# Check deployment success rate
curl "$PROMETHEUS_URL/api/v1/query?query=deployment_success_rate"

# Check in Grafana
# Visit: https://grafana.example.com/d/atom-deployment-overview
```

**Success Criteria**:
- [ ] CI workflow passes (all tests, linting, type checking)
- [ ] Docker image builds successfully
- [ ] Deployment to staging completes
- [ ] Smoke tests pass (authentication, health checks, API endpoints)
- [ ] Error rate <1% (Prometheus query)
- [ ] Dashboard updated in Grafana

---

## Production Deployment

### Deployment Workflow

```mermaid
graph LR
    A[Staging Verified] --> B[Manual Approval]
    B --> C[Deploy to Production]
    C --> D[Canary 10%]
    D --> E{Error Rate OK?}
    E -->|No| F[Automatic Rollback]
    E -->|Yes| G[Canary 50%]
    G --> H{Error Rate OK?}
    H -->|No| F
    H -->|Yes| I[Canary 100%]
    I --> J{Smoke Tests Pass?}
    J -->|No| F
    J -->|Yes| K[Deployment Complete]
```

### Step-by-Step Procedure

**Step 1: Verify staging deployment**
```bash
# Run comprehensive smoke tests against staging
./scripts/smoke-tests.sh staging --comprehensive

# Check staging metrics
curl "$PROMETHEUS_URL/api/v1/query?query=deployment_success_rate{environment=\"staging\"}"
curl "$PROMETHEUS_URL/api/v1/query?query=error_rate{environment=\"staging\"}"

# Verify staging error rate <1%
# Verify staging latency P95 <500ms

# If staging metrics unhealthy:
# - Do NOT proceed to production
# - Fix issues first
# - Re-deploy to staging
```

**Step 2: Trigger production deployment**
```bash
# Via GitHub UI:
# 1. Visit: https://github.com/org/repo/actions/workflows/deploy.yml
# 2. Click "Run workflow"
# 3. Select "production" environment
# 4. Click "Run workflow"

# Or via CLI:
gh workflow run deploy.yml --ref main -f environment=production

# Wait for manual approval
# Engineering lead must approve in GitHub Actions UI
```

**Step 3: Monitor canary deployment**
```bash
# Watch canary progress
gh run watch --interval 60

# Expected output:
# → deploy-production (in progress)
#   - Canary 10% traffic (5m wait)
#   - Canary 50% traffic (5m wait)
#   - Canary 100% traffic

# Check canary traffic percentage
curl "$PROMETHEUS_URL/api/v1/query?query=canary_traffic_percentage"
```

**Step 4: Verify production deployment**
```bash
# Check health endpoints
curl -f https://atom.example.com/health/live
curl -f https://atom.example.com/health/ready
curl -f https://atom.example.com/health/db

# Run smoke tests against production
./scripts/smoke-tests.sh production

# Check production metrics
curl "$PROMETHEUS_URL/api/v1/query?query=error_rate{environment=\"production\"}"
curl "$PROMETHEUS_URL/api/v1/query?query=latency_p95{environment=\"production\"}"
```

**Success Criteria**:
- [ ] Staging deployment verified (smoke tests pass, metrics healthy)
- [ ] Manual approval obtained
- [ ] Production deployment completes
- [ ] Canary deployment passes (10% → 50% → 100% traffic)
- [ ] Smoke tests pass (production)
- [ ] Error rate <0.1% (stricter than staging)
- [ ] Latency P95 <200ms (production threshold)

---

## Health Checks

### Liveness Probe

**Endpoint**: `/health/live`
**Purpose**: Check if application is alive
**Method**: GET
**Timeout**: 2 seconds
**Interval**: 10 seconds

**Request**:
```bash
curl https://staging.atom.example.com/health/live
```

**Response (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-20T10:30:00.000Z"
}
```

**Response (503 Service Unavailable)**:
```json
{
  "status": "unhealthy",
  "timestamp": "2026-02-20T10:30:00.000Z",
  "error": "Application not responding"
}
```

**Kubernetes Configuration**:
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 2
  failureThreshold: 3
```

### Readiness Probe

**Endpoint**: `/health/ready`
**Purpose**: Check if application is ready to handle requests
**Method**: GET
**Timeout**: 5 seconds
**Interval**: 10 seconds

**Request**:
```bash
curl https://staging.atom.example.com/health/ready
```

**Response (200 OK)**:
```json
{
  "status": "ready",
  "timestamp": "2026-02-20T10:30:00.000Z",
  "checks": {
    "database": {"status": "ok"},
    "redis": {"status": "ok"},
    "lancedb": {"status": "ok"}
  }
}
```

**Response (503 Service Unavailable)**:
```json
{
  "status": "not_ready",
  "timestamp": "2026-02-20T10:30:00.000Z",
  "checks": {
    "database": {"status": "failed", "error": "Connection refused"}
  }
}
```

**Kubernetes Configuration**:
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Database Connectivity Check

**Endpoint**: `/health/db`
**Purpose**: Check database connectivity and query performance
**Method**: GET
**Timeout**: 5 seconds

**Request**:
```bash
curl https://staging.atom.example.com/health/db
```

**Response (200 OK)**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-20T10:30:00.000Z",
  "database": {
    "connected": true,
    "query_time_ms": 5.23,
    "pool_status": {
      "size": 10,
      "checked_in": 8,
      "checked_out": 2,
      "overflow": 0,
      "max_overflow": 10
    }
  }
}
```

**Response (503 Service Unavailable)**:
```json
{
  "status": "unhealthy",
  "timestamp": "2026-02-20T10:30:00.000Z",
  "database": {
    "connected": false,
    "error": "Connection refused: port 5432"
  }
}
```

---

## Canary Deployment

### Canary Strategy

**Progressive Traffic Splitting**:
- **10% traffic** (5 minutes): Initial canary, monitor error rate
- **50% traffic** (5 minutes): Scale up, monitor for regressions
- **100% traffic**: Full deployment, complete rollout

**Error Rate Thresholds**:
- **Staging**: <1% (10 errors per 1000 requests)
- **Production**: <0.1% (1 error per 1000 requests)

**Automatic Rollback**:
- Triggered if error rate exceeds threshold during canary period
- Rollback command: `kubectl rollout undo deployment/atom`
- Rollback timeout: 5 minutes

### Monitoring Canary Deployment

**Check canary traffic percentage**:
```bash
curl "$PROMETHEUS_URL/api/v1/query?query=canary_traffic_percentage"
```

**Check error rate during canary**:
```bash
curl "$PROMETHEUS_URL/api/v1/query?query=error_rate{environment=\"production\"}"
```

**Expected output**:
```json
{
  "data": {
    "result": [
      {
        "metric": {},
        "value": [1708456800, "10.0"]
      }
    ]
  }
}

# 10% canary
# {"result": "10.0"}

# 50% canary
# {"result": "50.0"}

# 100% canary
# {"result": "100.0"}
```

**Kubernetes Canary Configuration**:
```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: atom
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: atom
  service:
    port: 8000
  analysis:
    interval: 1m
    threshold: 5
    maxWeight: 100
    stepWeight: 10
    stepWeightPromotion: 50
    metrics:
    - name: error-rate
      thresholdRange:
        max: 0.1
      interval: 1m
    - name: latency
      thresholdRange:
        max: 200
      interval: 1m
```

---

## Monitoring

### Prometheus Metrics

**Key Metrics**:
- `deployment_total`: Total deployments (success, failed, rolled_back)
- `deployment_duration_seconds`: Deployment duration histogram
- `deployment_rollback_total`: Total rollbacks by reason
- `canary_traffic_percentage`: Current canary traffic percentage
- `smoke_test_total`: Smoke test results (passed, failed)
- `prometheus_query_total`: Prometheus query success rate

**Query Examples**:
```bash
# Deployment success rate
curl "$PROMETHEUS_URL/api/v1/query?query=\
  sum(rate(deployment_total{status=\"success\"}[5m])) / \
  sum(rate(deployment_total[5m])) * 100"

# Deployment rollback rate
curl "$PROMETHEUS_URL/api/v1/query?query=\
  sum(rate(deployment_rollback_total[5m])) by (environment)"

# Smoke test pass rate
curl "$PROMETHEUS_URL/api/v1/query?query=\
  sum(rate(smoke_test_total{result=\"passed\"}[5m])) / \
  sum(rate(smoke_test_total[5m])) * 100"

# Error rate by environment
curl "$PROMETHEUS_URL/api/v1/query?query=\
  sum(rate(http_requests_total{status=~\"5..\"}[5m])) by (environment) / \
  sum(rate(http_requests_total[5m])) by (environment) * 100"

# Latency P95 by environment
curl "$PROMETHEUS_URL/api/v1/query?query=\
  histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, environment))"
```

### Grafana Dashboards

**Deployment Overview Dashboard**:
- URL: `https://grafana.example.com/d/atom-deployment-overview`
- Panels:
  - Deployment Success Rate
  - Deployment Rollback Rate
  - Smoke Test Pass Rate
  - Deployment Duration
  - Canary Traffic Percentage
  - Error Rate by Environment
  - Latency P95 by Environment

**API Performance Dashboard**:
- URL: `https://grafana.example.com/d/atom-api-performance`
- Panels:
  - Request Rate
  - Error Rate
  - Latency P50, P95, P99
  - Endpoint Breakdown
  - Database Connection Pool
  - Redis Connection Pool

**Update Grafana Dashboards**:
```bash
# Trigger manual dashboard update (if auto-update fails)
curl -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @backend/monitoring/grafana/deployment-overview.json

# Verify dashboard update
curl -X GET "$GRAFANA_URL/api/dashboards/uid/atom-deployment-overview" \
  -H "Authorization: Bearer $GRAFANA_API_KEY"
```

---

## Troubleshooting

See [CI/CD Troubleshooting Guide](./CI_CD_TROUBLESHOOTING.md) for common deployment issues and solutions.

**Quick Troubleshooting Commands**:
```bash
# Check deployment status
kubectl rollout status deployment/atom --namespace=staging

# Check pod status
kubectl get pods --namespace=staging -l app=atom

# Check pod logs
kubectl logs --namespace=staging -l app=atom --tail=100 --follow

# Describe pod for errors
kubectl describe pod --namespace=staging <pod-name>

# Check events
kubectl get events --namespace=staging --sort-by='.lastTimestamp'
```

---

## Related Documentation

- [CI/CD Runbook](./CI_CD_RUNBOOK.md)
- [CI/CD Troubleshooting](./CI_CD_TROUBLESHOOTING.md)
- [Monitoring Setup](./MONITORING_SETUP.md)
- [Kubernetes Deployment](./KUBERNETES_DEPLOYMENT.md)
