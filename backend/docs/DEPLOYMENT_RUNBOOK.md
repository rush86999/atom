# Atom Deployment Runbook

> **Version:** 1.0
> **Last Updated:** 2026-02-16
> **Purpose:** Step-by-step deployment and rollback procedures for production environments

---

## Overview

This runbook provides comprehensive procedures for deploying Atom to production environments, including pre-deployment checklists, step-by-step deployment instructions, rollback procedures, and post-deployment verification.

**Deployment Architecture:**
- **Backend:** FastAPI with Python 3.11
- **Database:** PostgreSQL 14+ with Alembic migrations
- **Cache:** Redis 7+ for WebSocket and caching
- **Container:** Docker with rolling restarts
- **Monitoring:** Prometheus metrics and structured logging

**Target Environments:**
- Staging: Automatic deployment on merge to main
- Production: Manual approval required

---

## Pre-Deployment Checklist

### 1. Code Quality

- [ ] All tests passing: `pytest tests/ --cov`
- [ ] Code coverage threshold met: `>=25%`
- [ ] No critical security vulnerabilities: `bandit -r backend/`
- [ ] Linting passes: `ruff check backend/`
- [ ] Type checking passes: `mypy backend/`

### 2. Database

- [ ] Migration script created: `alembic revision -m "description"`
- [ ] Migration reviewed for backward compatibility
- [ ] Rollback script tested: `alembic downgrade -1`
- [ ] Database backup created: `pg_dump atom > backup_$(date +%Y%m%d).sql`

### 3. Configuration

- [ ] Environment variables documented in `.env.example`
- [ ] Secrets updated in production secrets manager
- [ ] Docker image version tagged: `atom:$VERSION`
- [ ] Configuration file changes reviewed

### 4. Monitoring

- [ ] Alerts configured for deployment window
- [ ] On-call engineer notified
- [ ] Rollback plan documented and reviewed
- [ ] Metrics dashboard open and monitoring

### 5. Documentation

- [ ] CHANGELOG.md updated with version notes
- [ ] Breaking changes documented
- [ ] Feature flags documented
- [ ] API changes communicated to stakeholders

---

## Deployment Steps

### Step 1: Prepare Release

```bash
# Set version
export VERSION=$(date +%Y%m%d-%H%M%S)
echo "Deploying version: $VERSION"

# Create git tag
git tag -a v$VERSION -m "Release $VERSION"
git push origin v$VERSION

# Verify tests pass
pytest tests/ --cov --cov-report=term-missing
```

### Step 2: Run Database Migrations

```bash
# Check current migration version
alembic current

# Review migration plan
alembic history | head -20

# Run migrations (dry run first)
alembic upgrade head --sql

# Execute migrations
alembic upgrade head

# Verify migration success
alembic current
```

**Migration Verification:**
```sql
-- Check schema version
SELECT * FROM alembic_version;

-- Verify tables exist
\dt

-- Check row counts for critical tables
SELECT 'agent_registry' as table_name, COUNT(*) FROM agent_registry
UNION ALL
SELECT 'agent_execution', COUNT(*) FROM agent_execution
UNION ALL
SELECT 'episode', COUNT(*) FROM episode;
```

### Step 3: Build Docker Image

```bash
# Build image with version tag
docker build -t atom:$VERSION -t atom:latest .

# Tag for registry
docker tag atom:$VERSION registry.example.com/atom:$VERSION
docker tag atom:$VERSION registry.example.com/atom:latest

# Push to registry
docker push registry.example.com/atom:$VERSION
docker push registry.example.com/atom:latest

# Verify image exists
docker images | grep atom
```

### Step 4: Update Deployment Configuration

**For Kubernetes:**
```bash
# Update deployment image
kubectl set image deployment/atom atom=registry.example.com/atom:$VERSION

# Verify rollout status
kubectl rollout status deployment/atom

# Check pod status
kubectl get pods -l app=atom
```

**For Docker Compose:**
```bash
# Update docker-compose.yml with new image version
sed -i "s/image: atom:.*/image: atom:$VERSION/" docker-compose.yml

# Pull new image
docker-compose pull atom

# Restart services
docker-compose up -d atom
```

### Step 5: Rolling Restart

```bash
# For Kubernetes - rolling update is automatic
kubectl rollout restart deployment/atom

# For manual rolling restart (Docker)
# Restart containers one at a time
for container in $(docker ps -q -f name=atom); do
    echo "Restarting container: $container"
    docker restart $container
    sleep 10  # Wait for health check
done
```

### Step 6: Verify Health Checks

```bash
# Check liveness (service is running)
curl -f http://atom.example.com/health/live || echo "FAILED: Liveness check"

# Check readiness (service can accept traffic)
curl -f http://atom.example.com/health/ready || echo "FAILED: Readiness check"

# Check database connectivity
curl -f http://atom.example.com/health/ready | jq '.checks.database'

# Check Redis connectivity
curl -f http://atom.example.com/health/ready | jq '.checks.redis'

# Check LLM provider connectivity
curl -f http://atom.example.com/health/ready | jq '.checks.llm'
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "$VERSION",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "llm": "healthy"
  },
  "timestamp": "2026-02-16T19:00:00Z"
}
```

### Step 7: Monitor Metrics

```bash
# Check Prometheus metrics
curl http://atom.example.com/metrics | grep -E "atom_|http_"

# Key metrics to monitor:
# - atom_http_requests_total: Request rate
# - agent_executions_total: Agent execution rate
# - governance_cache_hit_rate: Cache performance
# - atom_error_rate: Error percentage
# - atom_latency_seconds: Response latency

# View in Grafana dashboard
# http://grafana.example.com/d/atom-overview
```

**Baseline Metrics (First 15 Minutes):**
- Error rate: <1% (baseline)
- P95 latency: <1s (baseline)
- Request rate: Stable or increasing
- Database connections: <80% max
- Memory usage: <80% limit

---

## Rollback Procedure

### Trigger Rollback If:

- Error rate >5% for 5 minutes
- P95 latency >2s for 5 minutes
- Health checks failing for 2 minutes
- Database connection errors >10%
- Critical bug discovered in production

### Rollback Steps

#### Step 1: Identify Bad Version

```bash
# Check current deployment version
kubectl get deployment atom -o jsonpath='{.spec.template.spec.containers[0].image}'

# Check recent deployments
kubectl rollout history deployment/atom

# Check logs for errors
kubectl logs -l app=atom --tail=100 | grep -i error

# Check metrics for degradation
# http://prometheus.example.com/graph?g0.expr=rate(atom_error_rate[5m])
```

#### Step 2: Revert Deployment Configuration

**Kubernetes Rollback:**
```bash
# Rollback to previous revision
kubectl rollout undo deployment/atom

# Rollback to specific revision
kubectl rollout undo deployment/atom --to-revision=3

# Verify rollback status
kubectl rollout status deployment/atom

# Check pods are restarting
kubectl get pods -l app=atom
```

**Docker Rollback:**
```bash
# Get previous image version
export PREV_VERSION=$(docker images --format "{{.Tag}}" | grep atom | sort -r | sed -n '2p')

# Update docker-compose.yml
sed -i "s/image: atom:.*/image: atom:$PREV_VERSION/" docker-compose.yml

# Pull and restart
docker-compose pull atom
docker-compose up -d atom
```

#### Step 3: Rolling Restart with Previous Version

```bash
# Verify old version is running
kubectl get pods -l app=atom -o jsonpath='{.items[*].spec.containers[0].image}'

# Watch pod startup
kubectl get pods -l app=atom -w

# Check logs
kubectl logs -l app=atom --tail=50 -f
```

#### Step 4: Verify Health Checks Return to Healthy

```bash
# Check liveness
curl -f http://atom.example.com/health/live

# Check readiness
curl -f http://atom.example.com/health/ready

# Verify all checks passing
curl -s http://atom.example.com/health/ready | jq '.status == "healthy"'
```

**Expected Rollback Timeline:**
- T+0 min: Rollback initiated
- T+2 min: All pods restarted with old version
- T+5 min: Health checks passing
- T+10 min: Metrics return to baseline

#### Step 5: Database Rollback (If Needed)

```bash
# Check current migration version
alembic current

# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Verify rollback
alembic current

# Check data integrity
# Run data validation queries for your schema
```

**Warning:** Database rollbacks may cause data loss if migration included destructive changes. Only rollback if absolutely necessary.

#### Step 6: Post-Mortem

```bash
# Document the incident
# Create incident report with:
# - Timeline of events
# - Root cause analysis
# - Impact assessment
# - Actions taken
# - Prevention measures

# Example incident template:
cat > incident_$(date +%Y%m%d).md <<EOF
# Incident Report: Deployment Failure $VERSION

## Timeline
- T+0 min: Deployed version $VERSION
- T+5 min: Error rate spiked to 15%
- T+10 min: Rollback initiated
- T+15 min: Service restored

## Root Cause
[Describe what went wrong]

## Impact
- Duration: 10 minutes
- Users affected: X
- Requests failed: Y

## Actions Taken
1. Identified error rate spike from metrics
2. Rolled back to previous version
3. Verified health checks passing

## Prevention
- [ ] Add pre-deployment smoke tests
- [ ] Improve monitoring alerts
- [ ] Fix bug in next release
EOF
```

---

## Post-Deployment Verification

### Health Checks

```bash
# All health checks passing
curl -s http://atom.example.com/health/ready | jq '.status == "healthy"'
# Expected: true

# Database connectivity
curl -s http://atom.example.com/health/ready | jq '.checks.database == "healthy"'
# Expected: true

# Redis connectivity
curl -s http://atom.example.com/health/ready | jq '.checks.redis == "healthy"'
# Expected: true

# LLM provider connectivity
curl -s http://atom.example.com/health/ready | jq '.checks.llm == "healthy"'
# Expected: true
```

### Error Rate

```bash
# Check error rate (Prometheus query)
curl -s 'http://prometheus.example.com/api/v1/query?query=rate(atom_http_errors_total[5m])' | jq '.data.result[0].value[1]'
# Expected: <0.01 (1%)

# Compare to baseline (last 24 hours)
curl -s 'http://prometheus.example.com/api/v1/query?query=rate(atom_http_errors_total[5m])' | jq '.data.result[0].value[1]'
```

### Latency

```bash
# Check P95 latency
curl -s 'http://prometheus.example.com/api/v1/query?query=histogram_quantile(0.95, atom_latency_seconds)' | jq '.data.result[0].value[1]'
# Expected: <1.0

# Check P99 latency
curl -s 'http://prometheus.example.com/api/v1/query?query=histogram_quantile(0.99, atom_latency_seconds)' | jq '.data.result[0].value[1]'
# Expected: <2.0
```

### Database

```bash
# Check database connection errors
curl -s 'http://prometheus.example.com/api/v1/query?query=rate(atom_db_errors_total[5m])' | jq '.data.result[0].value[1]'
# Expected: 0

# Check connection pool usage
curl -s 'http://prometheus.example.com/api/v1/query?query=atom_db_pool_active_connections' | jq '.data.result[0].value[1]'
# Expected: <80% of max connections
```

### Smoke Tests

```bash
# Test agent execution
curl -X POST http://atom.example.com/api/agents/execute \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent", "query": "hello"}'

# Test canvas presentation
curl -X POST http://atom.example.com/api/canvas/present \
  -H "Content-Type: application/json" \
  -d '{"canvas_type": "generic", "content": "test"}'

# Test skill execution
curl -X POST http://atom.example.com/api/skills/execute \
  -H "Content-Type: application/json" \
  -d '{"skill_name": "test_skill", "inputs": {}}'
```

---

## Deployment Scenarios

### Scenario 1: Zero-Downtime Deployment

**Use Case:** Routine feature deployment, no breaking changes

**Steps:**
1. Follow standard deployment steps (Steps 1-7)
2. Use rolling restart to maintain availability
3. Monitor metrics for 30 minutes
4. No rollback expected

**Timeline:** 15-30 minutes

### Scenario 2: Breaking Change Deployment

**Use Case:** API changes, database schema modifications

**Steps:**
1. Deploy new version alongside old version (canary)
2. Route 10% traffic to new version
3. Monitor for 30 minutes
4. Gradually increase traffic to 100%
5. Rollback immediately if errors spike

**Timeline:** 2-3 hours

### Scenario 3: Emergency Hotfix

**Use Case:** Critical security patch, production bug fix

**Steps:**
1. Skip non-critical pre-deployment checks
2. Deploy directly to production
3. Monitor intensively for 1 hour
4. Have rollback plan ready

**Timeline:** 10-15 minutes

### Scenario 4: Database Migration

**Use Case:** Schema changes requiring data migration

**Steps:**
1. Create migration script with rollback
2. Test migration on staging database
3. Deploy application code first (backward compatible)
4. Run database migration
5. Monitor for 1 hour
6. Deploy new application code

**Timeline:** 1-2 hours

---

## Troubleshooting

### Deployment Fails

**Symptom:** kubectl rollout status fails

**Diagnosis:**
```bash
kubectl describe deployment atom
kubectl logs -l app=atom --tail=100
```

**Resolution:**
- Check image pull errors
- Verify resource limits
- Check pod crash loops
- See TROUBLESHOOTING.md for common issues

### Health Checks Fail After Deployment

**Symptom:** /health/ready returns 503

**Diagnosis:**
```bash
curl http://atom.example.com/health/ready | jq '.checks'
kubectl logs -l app=atom --tail=100 | grep -i error
```

**Resolution:**
- Check database connectivity
- Verify environment variables
- Restart pods if stuck
- Rollback if issues persist

### High Error Rate After Deployment

**Symptom:** Error rate >5% in metrics

**Diagnosis:**
```bash
# Check error types
kubectl logs -l app=atom --tail=1000 | grep ERROR | sort | uniq -c

# Check application logs
jq '.level == "error"' /var/log/atom/atom.log | tail -100
```

**Resolution:**
- Identify error pattern
- Check for configuration issues
- Rollback if critical bug
- See TROUBLESHOOTING.md

---

## Contacts

**Deployment Team:**
- DevOps Lead: devops@example.com
- Database Admin: dba@example.com
- On-Call Engineer: oncall@example.com (pager: +1-555-0100)

**Escalation:**
- Level 1: On-call engineer (immediate)
- Level 2: Engineering manager (30 minutes)
- Level 3: CTO (1 hour)

**Resources:**
- Monitoring Dashboard: http://grafana.example.com/d/atom-overview
- Run Manager: http://run-manager.example.com
- Incident Response: See INCIDENT_RESPONSE.md

---

## References

- **Operations Guide:** backend/docs/OPERATIONS_GUIDE.md
- **Troubleshooting:** backend/docs/TROUBLESHOOTING.md
- **Monitoring:** backend/docs/MONITORING.md
- **Architecture:** CLAUDE.md
- **Database Migrations:** backend/alembic/README.md
