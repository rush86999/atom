# Atom CI/CD Runbook

**Purpose**: Operational procedures for Atom CI/CD pipelines
**Last Updated**: 2026-02-20
**Maintainer**: DevOps Team

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Deployment Procedures](#deployment-procedures)
3. [Rollback Procedures](#rollback-procedures)
4. [Verification Checklist](#verification-checklist)
5. [Emergency Procedures](#emergency-procedures)
6. [Quality Gates](#quality-gates)

---

## Quick Reference

### Workflow URLs
- **CI Pipeline**: `.github/workflows/ci.yml`
- **Deploy Pipeline**: `.github/workflows/deploy.yml`
- **LanceDB Integration**: `.github/workflows/lancedb-integration.yml`

### Key Commands

```bash
# Trigger deployment
gh workflow run deploy.yml --ref main

# Watch workflow run
gh run watch --interval 10

# View workflow logs
gh run view --log

# Cancel workflow run
gh run cancel <run-id>

# Retry failed workflow
gh run rerun <run-id>
```

### Critical Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | Database connection | `postgresql://user:pass@host:5432/db` |
| `PROMETHEUS_URL` | Monitoring endpoint | `http://prometheus:9090` |
| `GRAFANA_URL` | Dashboard URL | `http://grafana:3000` |
| `STAGING_URL` | Staging environment | `https://staging.atom.example.com` |
| `PRODUCTION_URL` | Production environment | `https://atom.example.com` |

---

## Deployment Procedures

### Staging Deployment

**Trigger**: Automatic on push to `main` branch
**Approval**: None required (automatic deployment)
**Duration**: 5-10 minutes

**Procedure**:

1. **Push to main branch**
   ```bash
   git checkout main
   git pull
   git merge feature-branch
   git push origin main
   ```

2. **Monitor CI workflow**
   ```bash
   # Watch CI pipeline
   gh workflow view ci

   # Watch latest run
   gh run watch --interval 10
   ```

3. **Verify staging deployment**
   ```bash
   # Check staging health
   curl https://staging.atom.example.com/health/live
   curl https://staging.atom.example.com/health/ready
   curl https://staging.atom.example.com/health/db

   # Check smoke test results
   gh run view --log | grep "Smoke test"
   ```

4. **Verify deployment metrics**
   ```bash
   # Check Prometheus metrics
   curl "$PROMETHEUS_URL/api/v1/query?query=deployment_success_rate"

   # Check Grafana dashboard
   # Visit: https://grafana.example.com/d/atom-deployment-overview
   ```

**Success Criteria**:
- [ ] CI workflow passes (all tests, linting, type checking)
- [ ] Docker image builds successfully
- [ ] Deployment to staging completes
- [ ] Smoke tests pass (authentication, health checks, API endpoints)
- [ ] Error rate <1% (Prometheus query)
- [ ] Dashboard updated in Grafana

**Failure Handling**:
- If CI fails: Fix test failures, push new commit
- If build fails: Check Dockerfile syntax, dependencies
- If deploy fails: Check kubectl configuration, cluster connectivity
- If smoke tests fail: Automatic rollback triggered, investigate GitHub issue

### Production Deployment

**Trigger**: Manual approval after staging deployment
**Approval**: Required via GitHub Actions environment
**Duration**: 10-15 minutes (including canary deployment)

**Procedure**:

1. **Verify staging deployment**
   ```bash
   # Run smoke tests against staging
   ./scripts/smoke-tests.sh staging

   # Check staging metrics
   curl "$PROMETHEUS_URL/api/v1/query?query=deployment_success_rate{environment=\"staging\"}"
   ```

2. **Trigger production deployment**
   ```bash
   # Manual trigger via GitHub UI
   # Visit: https://github.com/org/repo/actions/workflows/deploy.yml
   # Click "Run workflow" → Select "production" environment
   ```

   Or via CLI:
   ```bash
   gh workflow run deploy.yml --ref main -f environment=production
   ```

3. **Monitor canary deployment**
   ```bash
   # Watch canary progress
   gh run watch --interval 30

   # Check canary traffic percentage
   curl "$PROMETHEUS_URL/api/v1/query?query=canary_traffic_percentage"
   ```

4. **Verify production deployment**
   ```bash
   # Check production health
   curl https://atom.example.com/health/live
   curl https://atom.example.com/health/ready
   curl https://atom.example.com/health/db

   # Run smoke tests against production
   ./scripts/smoke-tests.sh production
   ```

**Success Criteria**:
- [ ] Staging deployment verified (smoke tests pass, metrics healthy)
- [ ] Manual approval obtained
- [ ] Production deployment completes
- [ ] Canary deployment passes (10% → 50% → 100% traffic)
- [ ] Smoke tests pass (production)
- [ ] Error rate <0.1% (stricter than staging)
- [ ] Latency P95 <200ms (production threshold)

**Failure Handling**:
- If staging fails: Do NOT proceed to production, fix issues first
- If canary fails: Automatic rollback triggered, investigate error spike
- If smoke tests fail: Automatic rollback triggered, GitHub issue created
- If metrics degraded: Pause deployment, investigate, rollback if needed

---

## Rollback Procedures

### Automatic Rollback

**Trigger Conditions**:
- Smoke test failure (authentication, health checks, API endpoints)
- Error rate exceeds threshold (>1% staging, >0.1% production)
- Latency exceeds threshold (>500ms staging, >200ms production)
- Canary deployment failure (error spike during canary period)

**Automatic Rollback Process**:

1. **Detection**: Smoke test or monitoring check detects failure
2. **Trigger**: GitHub Actions workflow executes rollback step
3. **Rollback**: `kubectl rollout undo deployment/atom` executed
4. **Verification**: Rollback status wait (5-minute timeout)
5. **Notification**: Slack alert sent, GitHub issue created

**Example Rollback Log**:
```
=== 🚨 Smoke tests failed - initiating automatic rollback ===
Step 1: Rolling back deployment...
deployment.apps/atom rolled back
Step 2: Waiting for rollback to complete...
rollback condition met (5s)
=== ✅ Rollback completed ===
```

### Manual Rollback

**When to Use**:
- Gradual performance degradation (no automatic trigger)
- Customer-reported issues (not caught by automated checks)
- Feature flag needs to be disabled
- Database migration issues (post-deployment)

**Procedure**:

1. **Verify need for rollback**
   ```bash
   # Check error rate
   curl "$PROMETHEUS_URL/api/v1/query?query=error_rate"

   # Check customer reports
   # Check Slack alerts, PagerDuty, etc.
   ```

2. **Execute rollback**
   ```bash
   # Option 1: Rollback to previous deployment
   kubectl rollout undo deployment/atom

   # Option 2: Rollback to specific revision
   kubectl rollout undo deployment/atom --to-revision=3

   # Wait for rollback to complete
   kubectl rollout status deployment/atom --timeout=5m
   ```

3. **Verify rollback**
   ```bash
   # Check deployment status
   kubectl get deployments atom

   # Check pods are running
   kubectl get pods -l app=atom

   # Run smoke tests
   ./scripts/smoke-tests.sh production
   ```

4. **Communicate rollback**
   ```bash
   # Send Slack notification
   curl -X POST "$SLACK_WEBHOOK_URL" \
     -H 'Content-Type: application/json' \
     -d '{"text": "🚨 Manual rollback executed for production"}'

   # Create GitHub issue
   gh issue create \
     --title "Production Rollback - Manual" \
     --body "Rollback executed manually due to..." \
     --label "production,rollback"
   ```

**Rollback Verification Checklist**:
- [ ] Deployment rolled back to previous version
- [ ] Pods are healthy (no crash loops)
- [ ] Smoke tests pass
- [ ] Error rate returns to baseline (<0.1%)
- [ ] Latency returns to baseline (P95 <200ms)
- [ ] Slack notification sent
- [ ] GitHub issue created for investigation

---

## Verification Checklist

### Post-Deployment Verification

**Execute after EVERY deployment** (staging or production):

1. **Health Checks**
   ```bash
   # Liveness probe
   curl -f https://staging.atom.example.com/health/live

   # Readiness probe
   curl -f https://staging.atom.example.com/health/ready

   # Database connectivity
   curl -f https://staging.atom.example.com/health/db
   ```

   **Expected Output**:
   ```json
   {"status": "healthy", "timestamp": "2026-02-20T10:30:00Z"}
   ```

2. **Smoke Tests**
   ```bash
   # Run automated smoke tests
   ./scripts/smoke-tests.sh staging

   # Or manual smoke tests
   ./scripts/manual-smoke-tests.sh staging
   ```

   **Expected Results**:
   - Authentication: ✅ Success
   - Health endpoints: ✅ All pass
   - Agent execution: ✅ API responds
   - Canvas presentation: ✅ API responds
   - Skills endpoint: ✅ API responds

3. **Metrics Verification**
   ```bash
   # Error rate
   curl "$PROMETHEUS_URL/api/v1/query?query=error_rate{environment=\"staging\"}"

   # Latency P95
   curl "$PROMETHEUS_URL/api/v1/query?query=latency_p95{environment=\"staging\"}"

   # Deployment success rate
   curl "$PROMETHEUS_URL/api/v1/query?query=deployment_success_rate"
   ```

   **Expected Thresholds**:
   - Error rate (staging): <1%
   - Error rate (production): <0.1%
   - Latency P95 (staging): <500ms
   - Latency P95 (production): <200ms
   - Deployment success rate: >95%

4. **Dashboard Verification**
   - Visit Grafana: `https://grafana.example.com/d/atom-deployment-overview`
   - Verify no error spikes
   - Verify latency within threshold
   - Verify deployment success rate stable

5. **Log Verification**
   ```bash
   # Check application logs
   kubectl logs -l app=atom --tail=100 | grep ERROR

   # Check for error patterns
   kubectl logs -l app=atom --tail=100 | grep -i "exception\|error\|failed"

   # Verify no crash loops
   kubectl get pods -l app=atom | grep -c "CrashLoopBackOff"
   # Expected: 0
   ```

---

## Emergency Procedures

### Emergency Rollback (<5 minutes)

**Scenario**: Critical failure detected (error rate >5%, P0 incident)

**Procedure**:
1. **Execute immediate rollback**
   ```bash
   # Rollback to previous version (fastest method)
   kubectl rollout undo deployment/atom

   # Wait for rollback (with timeout)
   kubectl rollout status deployment/atom --timeout=3m
   ```

2. **Verify rollback**
   ```bash
   # Check pods are restarting
   kubectl get pods -l app=atom

   # Check error rate decreasing
   curl "$PROMETHEUS_URL/api/v1/query?query=error_rate"
   ```

3. **Communicate incident**
   ```bash
   # Send critical Slack alert
   curl -X POST "$SLACK_WEBHOOK_CRITICAL" \
     -H 'Content-Type: application/json' \
     -d '{"text": "🚨🚨 EMERGENCY ROLLBACK EXECUTED 🚨🚨"}'

   # Declare incident (PagerDuty, etc.)
   # Follow incident response runbook
   ```

4. **Create post-mortem ticket**
   ```bash
   gh issue create \
     --title "P0 Incident - Emergency Rollback" \
     --body "Emergency rollback executed due to..." \
     --label "incident,p0,critical"
   ```

### Incident Communication

**Stakeholder Notification**:
- **Engineering**: Slack #incident channel
- **Product**: Email product@atom.example.com
- **Support**: Email support@atom.example.com
- **Customers** (if production outage): Status page update

**Communication Template**:
```
Subject: INCIDENT - Production Deployment Issue

Summary: Automatic rollback triggered due to smoke test failure
Impact: [X] users affected for [Y] minutes
Timeline: [Start time] - [End time]
Root Cause: [To be determined]
Resolution: Rolled back to previous deployment
Next Steps: Investigating root cause, will provide updates
```

---

## Quality Gates

### TQ-01: Test Independence

**Purpose**: Validate tests run independently without ordering dependencies

**Enforcement**: Random order test execution in CI

**Command**:
```bash
pytest tests/ --random-order --random-order-seed=random -v --maxfail=5
```

**Pass Criteria**: All tests pass in random order

**Failure Impact**: CI workflow fails, deployment blocked

### TQ-02: Test Pass Rate

**Purpose**: Ensure 98% minimum test pass rate

**Enforcement**: Pass rate calculated from pytest JSON output

**Command**:
```bash
pytest tests/ --json-report --json-report-file=pytest_report.json
python tests/scripts/parse_pytest_output.py pytest_report.json
```

**Pass Criteria**: Pass rate >=98%

**Failure Impact**: CI workflow fails, deployment blocked

### TQ-03: Test Performance

**Purpose**: Ensure test suite completes in reasonable time

**Enforcement**: Test duration measured in CI

**Pass Criteria**: Full test suite <60 minutes

**Failure Impact**: Warning only, deployment continues

### TQ-04: Test Determinism

**Purpose**: Ensure tests produce consistent results

**Enforcement**: Flaky test detection with pytest-rerunfailures

**Command**:
```bash
pytest tests/ --reruns 2 --reruns-delay 1
```

**Pass Criteria**: Tests pass after 2 retries

**Failure Impact**: Test marked as flaky, investigation required

### TQ-05: Coverage Quality

**Purpose**: Ensure adequate code coverage

**Enforcement**: Coverage percentage measured in CI

**Command**:
```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-fail-under=25
```

**Pass Criteria**: Coverage >=25% (current threshold)

**Target**: Coverage >=50% (future goal)

**Failure Impact**: Warning only, deployment continues

---

## Appendix

### Useful Commands

```bash
# View workflow history
gh run list --workflow=deploy.yml --limit 10

# View specific workflow run
gh run view <run-id>

# Download workflow artifacts
gh run download <run-id>

# Retry failed workflow
gh run rerun <run-id>

# Cancel running workflow
gh run cancel <run-id>

# Check deployment status
kubectl rollout status deployment/atom

# View deployment history
kubectl rollout history deployment/atom --revision=0

# Check pod health
kubectl get pods -l app=atom

# View pod logs
kubectl logs -l app=atom --tail=100 --follow

# Execute command in pod
kubectl exec -it <pod-name> -- /bin/bash
```

### Contacts

- **DevOps On-Call**: devops@atom.example.com
- **Engineering Lead**: eng-lead@atom.example.com
- **Product Manager**: product@atom.example.com

### Related Documentation

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Troubleshooting Guide](./CI_CD_TROUBLESHOOTING.md)
- [Monitoring Setup](./MONITORING_SETUP.md)
- [Docker Deployment](./DOCKER_DEPLOYMENT.md)

---

## Pre-Deployment Checklist

### Code Quality Gates

- [ ] All tests passing: `pytest tests/ --cov`
- [ ] Code coverage threshold met: `>=25%`
- [ ] No critical security vulnerabilities: `bandit -r backend/`
- [ ] Linting passes: `ruff check backend/`
- [ ] Type checking passes: `mypy backend/`

### Database Readiness

- [ ] Migration script created: `alembic revision -m "description"`
- [ ] Migration reviewed for backward compatibility
- [ ] Rollback script tested: `alembic downgrade -1`
- [ ] Database backup created: `pg_dump atom > backup_$(date +%Y%m%d).sql`

### Configuration Verification

- [ ] Environment variables documented in `.env.example`
- [ ] Secrets updated in production secrets manager
- [ ] Docker image version tagged: `atom:$VERSION`
- [ ] Configuration file changes reviewed

### Monitoring Setup

- [ ] Alerts configured for deployment window
- [ ] On-call engineer notified
- [ ] Rollback plan documented and reviewed
- [ ] Metrics dashboard open and monitoring

### Documentation Updates

- [ ] CHANGELOG.md updated with version notes
- [ ] Breaking changes documented
- [ ] Feature flags documented
- [ ] API changes communicated to stakeholders

---

## Deployment Scenarios

### Scenario 1: Zero-Downtime Rolling Deployment

**Use Case:** Routine feature deployment, no breaking changes

**Prerequisites**:
- All tests passing
- No database schema changes
- No breaking API changes
- Feature flags ready for gradual rollout

**Steps**:
1. Follow standard deployment steps (Steps 1-7)
2. Use rolling restart to maintain availability
3. Monitor metrics for 30 minutes
4. No rollback expected

**Timeline:** 15-30 minutes

**Rollback Plan**: Standard `kubectl rollout undo` if issues detected

### Scenario 2: Canary Deployment

**Use Case:** Breaking API changes, database schema modifications

**Prerequisites**:
- Feature flags implemented
- Database migrations backward compatible
- Monitoring alerts configured
- Rollback plan reviewed

**Steps**:
1. Deploy new version alongside old version
2. Route 10% traffic to new version (5 min wait)
3. Monitor error rate, latency, logs
4. If metrics healthy: 50% traffic (5 min wait)
5. If metrics healthy: 100% traffic
6. Rollback immediately if errors spike

**Timeline:** 2-3 hours (including validation)

**Rollback Plan**: Immediate rollback on any metric degradation

### Scenario 3: Blue-Green Deployment

**Use Case:** Major version upgrade, database migration

**Prerequisites**:
- Separate environment (green) ready
- Database migration tested
- Traffic switching mechanism ready
- Full rollback capability

**Steps**:
1. Deploy new version to green environment
2. Run smoke tests against green
3. Migrate database (if backward compatible)
4. Switch traffic from blue to green
5. Monitor green environment for 1 hour
6. If successful, decommission blue

**Timeline:** 3-4 hours

**Rollback Plan**: Switch traffic back to blue immediately

### Scenario 4: Emergency Hotfix

**Use Case:** Critical security patch, production bug fix

**Prerequisites**:
- Security vulnerability confirmed
- Fix tested in staging
- Emergency approval obtained
- On-call team ready

**Steps**:
1. Skip non-critical pre-deployment checks
2. Deploy directly to production
3. Monitor intensively for 1 hour
4. Have rollback plan ready
5. Create post-mortem after validation

**Timeline:** 10-15 minutes

**Rollback Plan**: Immediate rollback if new issues introduced

---

## Database Migration Procedures

### Pre-Migration Checks

```bash
# Check current migration version
alembic current

# Review pending migrations
alembic history | head -20

# Test migration on staging database
alembic upgrade head --sql
```

### Migration Execution

```bash
# Backup database before migration
pg_dump atom > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration
alembic upgrade head

# Verify migration success
alembic current

# Check data integrity
psql -c "SELECT COUNT(*) FROM alembic_version"
```

### Migration Verification

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

### Migration Rollback

**Warning**: Database rollbacks may cause data loss if migration included destructive changes. Only rollback if absolutely necessary.

```bash
# Check current migration version
alembic current

# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Verify rollback
alembic current

# Restore from backup if needed
psql atom < backup_20260220_103000.sql
```

---

## Smoke Test Procedures

### Authentication Smoke Test

```bash
# Test smoke test user login
curl -X POST https://staging.atom.example.com/api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$SMOKE_TEST_USERNAME&password=$SMOKE_TEST_PASSWORD"

# Expected response:
# {"access_token": "...", "token_type": "bearer"}
```

### Health Endpoint Smoke Test

```bash
# Test liveness probe
curl -f https://staging.atom.example.com/health/live
# Expected: {"status": "healthy", "timestamp": "..."}

# Test readiness probe
curl -f https://staging.atom.example.com/health/ready
# Expected: {"status": "ready", "checks": {...}}

# Test database connectivity
curl -f https://staging.atom.example.com/health/db
# Expected: {"status": "healthy", "database": {...}}
```

### Agent Execution Smoke Test

```bash
# Get auth token first
TOKEN=$(curl -s -X POST https://staging.atom.example.com/api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$SMOKE_TEST_USERNAME&password=$SMOKE_TEST_PASSWORD" \
  | jq -r '.access_token')

# Test agent execution
curl -X POST https://staging.atom.example.com/api/agents/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent", "query": "hello"}'

# Expected: Agent response with execution ID
```

### Canvas Presentation Smoke Test

```bash
# Test canvas presentation
curl -X POST https://staging.atom.example.com/api/canvas/present \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"canvas_type": "generic", "content": "test"}'

# Expected: Canvas ID and presentation details
```

### Skills Endpoint Smoke Test

```bash
# Test skills endpoint
curl -X GET https://staging.atom.example.com/api/skills \
  -H "Authorization: Bearer $TOKEN"

# Expected: List of available skills
```

---

## Incident Response Procedures

### P0 Incident (Critical)

**Definition**: Production service down, all users affected

**Response Time**: Immediate (<5 minutes)

**Escalation**:
1. On-call engineer: Immediate
2. Engineering manager: +15 minutes
3. CTO: +30 minutes

**Actions**:
1. Declare incident in Slack #incident channel
2. Execute emergency rollback if needed
3. Send status page update
4. Create incident ticket
5. Begin root cause analysis

### P1 Incident (High)

**Definition**: Major functionality degraded, significant user impact

**Response Time**: 15 minutes

**Escalation**:
1. On-call engineer: Immediate
2. Engineering manager: +30 minutes

**Actions**:
1. Assess impact and scope
2. Implement workaround if available
3. Create incident ticket
4. Communicate to stakeholders
5. Plan fix for next deployment

### P2 Incident (Medium)

**Definition**: Minor functionality issue, limited user impact

**Response Time**: 1 hour

**Escalation**:
1. On-call engineer: Immediate
2. Team lead: Next business day

**Actions**:
1. Document issue in ticket
2. Assess priority
3. Schedule fix in upcoming sprint

---

## Post-Incident Procedures

### Post-Mortem Process

**Timeline**: Complete within 5 business days

**Sections**:
1. Executive Summary
2. Timeline of Events
3. Root Cause Analysis
4. Impact Assessment
5. Resolution Steps
6. Action Items (with owners and due dates)
7. Prevention Measures

**Post-Mortem Template**:

```markdown
# Incident Post-Mortem: [Title]

**Date**: [Date of incident]
**Severity**: [P0/P1/P2]
**Duration**: [Start time] - [End time]
**Author**: [Incident lead]

## Executive Summary

[Brief 2-3 sentence summary for executives]

## Timeline of Events

- **T+0 min**: [Event description]
- **T+5 min**: [Event description]
- **T+10 min**: [Event description]

## Root Cause Analysis

### What happened?
[Detailed description of the incident]

### Why did it happen?
[Root cause analysis using 5 Whys]

### Contributing Factors
- [Factor 1]
- [Factor 2]

## Impact Assessment

- **Users affected**: [Number or percentage]
- **Duration**: [Total downtime]
- **Requests failed**: [Number]
- **Revenue impact**: [Amount if applicable]

## Resolution Steps

1. [Step 1]
2. [Step 2]
3. [Step 3]

## Action Items

| Item | Owner | Due Date | Status |
|------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | [Open/Done] |
| [Action 2] | [Name] | [Date] | [Open/Done] |

## Prevention Measures

1. [Prevention measure 1]
2. [Prevention measure 2]
3. [Prevention measure 3]

## Lessons Learned

[What did we learn from this incident?]
```

---

## Metrics Dashboard Reference

### Key Deployment Metrics

**Deployment Success Rate**:
```promql
sum(rate(deployment_total{status="success"}[5m])) /
sum(rate(deployment_total[5m])) * 100
```

**Deployment Duration**:
```promql
histogram_quantile(0.95, deployment_duration_seconds)
```

**Rollback Rate**:
```promql
sum(rate(deployment_rollback_total[5m])) by (environment)
```

**Smoke Test Pass Rate**:
```promql
sum(rate(smoke_test_total{result="passed"}[5m])) /
sum(rate(smoke_test_total[5m])) * 100
```

### Key Application Metrics

**Error Rate**:
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

**Request Rate**:
```promql
sum(rate(http_requests_total[5m])) by (endpoint)
```

**Latency P95**:
```promql
histogram_quantile(0.95, http_request_duration_seconds)
```

**Database Connection Pool Usage**:
```promql
db_pool_active_connections / db_pool_max_connections * 100
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Error Rate | >1% | >5% |
| P95 Latency | >500ms | >2000ms |
| Deployment Success Rate | <95% | <90% |
| Smoke Test Pass Rate | <98% | <95% |
| Database Pool Usage | >80% | >90% |
