# CI/CD Troubleshooting Guide

**Purpose**: Common CI/CD failures and solutions
**Last Updated**: 2026-02-20
**Audience**: DevOps engineers, developers

## Table of Contents

1. [CI Pipeline Failures](#ci-pipeline-failures)
2. [Docker Build Failures](#docker-build-failures)
3. [Deployment Failures](#deployment-failures)
4. [Smoke Test Failures](#smoke-test-failures)
5. [Monitoring Issues](#monitoring-issues)
6. [Rollback Issues](#rollback-issues)

---

## CI Pipeline Failures

### Issue: Tests Failing in CI but Passing Locally

**Symptoms**:
- CI workflow fails at backend-test-full job
- Tests pass when run locally: `pytest tests/`
- Error logs show "UNIQUE constraint failed" or "database locked"

**Root Causes**:
1. **Test state leakage**: Tests sharing state via database or file system
2. **Parallel test execution**: Tests not isolated for pytest-xdist
3. **Missing fixtures**: CI-specific fixtures not available locally
4. **Environment differences**: CI environment variables not set locally

**Solutions**:

**Solution 1: Check test isolation**
```bash
# Run tests in random order (detects ordering dependencies)
pytest tests/ --random-order -v

# If tests fail, fix isolation issues:
# - Use unique_resource_name fixture for all test resources
# - Use db_session fixture with transaction rollback
# - Avoid global variables in tests
# - Prefer function-scoped fixtures over session/class-scoped
```

**Solution 2: Run tests in sequential mode**
```bash
# Run tests sequentially (disable parallel execution)
pytest tests/ -v --maxfail=10

# If sequential tests pass, parallel tests fail:
# - Test has shared state issue
# - Add unique_resource_name fixture
# - Use file lock for session fixtures
```

**Solution 3: Check CI environment variables**
```bash
# View CI environment variables in workflow log
gh run view --log | grep "DATABASE_URL"
gh run view --log | grep "ATOM_"

# Set missing variables locally
export DATABASE_URL="sqlite:///:memory:"
export ATOM_DISABLE_LANCEDB=true
export ATOM_MOCK_DATABASE=true

# Re-run tests locally
pytest tests/ -v
```

**Prevention**:
- Always use `unique_resource_name` fixture for test resources
- Use `db_session` fixture with automatic rollback
- Run tests with `--random-order` before pushing
- Add CI environment variables to local `.env` file

---

### Issue: Import Errors in CI

**Symptoms**:
- CI workflow fails at "Verify backend imports" step
- Error: `ModuleNotFoundError: No module named 'xxx'`
- Tests pass locally but imports fail in CI

**Root Causes**:
1. **Missing dependency**: Package not in requirements.txt
2. **Import order**: Module imported before installation
3. **Python path**: PYTHONPATH not set correctly in CI

**Solutions**:

**Solution 1: Check requirements.txt**
```bash
# Verify missing package
grep "package-name" backend/requirements.txt

# Add missing package
echo "package-name==1.0.0" >> backend/requirements.txt

# Commit and push
git add requirements.txt
git commit -m "Add missing dependency: package-name"
git push
```

**Solution 2: Verify import order**
```bash
# Check debug_ci_imports.py
cat backend/debug_ci_imports.py

# Ensure imports after pip install
# - Import errors usually mean circular dependencies
# - Use lazy imports (import inside function) if needed
```

**Solution 3: Set PYTHONPATH in CI**
```yaml
# In .github/workflows/ci.yml
- name: Run tests
  env:
    PYTHONPATH: /Users/runner/work/atom/atom/backend
  run: |
    pytest tests/ -v
```

---

### Issue: Type Checking (MyPy) Failures

**Symptoms**:
- CI workflow fails at type checking step
- Error: `error: Argument 1 to "function" has incompatible type`
- MyPy passes locally but fails in CI

**Root Causes**:
1. **Missing type hints**: Function parameters not annotated
2. **Import errors**: MyPy can't find imported modules
3. **Version mismatch**: Different mypy version locally vs CI

**Solutions**:

**Solution 1: Add type hints**
```python
# Before (missing type hints):
def process_agent(agent_id, query):
    pass

# After (with type hints):
from typing import Dict, Any

def process_agent(agent_id: str, query: str) -> Dict[str, Any]:
    pass
```

**Solution 2: Ignore specific errors**
```python
# Add type: ignore comment for false positives
result = external_library.function(arg)  # type: ignore
```

**Solution 3: Configure mypy**
```ini
# In mypy.ini
[mypy]
ignore_missing_imports = True
warn_return_any = False
```

---

### Issue: Coverage Threshold Not Met

**Symptoms**:
- CI workflow fails at coverage check
- Error: "Coverage below 25% threshold"
- Coverage is 24.8% (just below threshold)

**Root Causes**:
1. **Missing tests**: New code not covered by tests
2. **Excluded paths**: Coverage excludes too many files
3. **Threshold too high**: 25% threshold not met for new features

**Solutions**:

**Solution 1: Add tests for new code**
```python
# Add tests for uncovered functions
def test_new_function():
    result = new_function(input_data)
    assert result == expected_output
```

**Solution 2: Check coverage report**
```bash
# View coverage report locally
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term-missing

# Identify uncovered lines
# Look for lines marked with ">>>>>>"
```

**Solution 3: Temporarily lower threshold** (not recommended)
```yaml
# In .github/workflows/ci.yml
- name: Check coverage threshold
  run: |
    coverage=$(cd backend && coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')
    echo "Coverage: $coverage%"
    if (( $(echo "$coverage < 20" | bc -l) )); then  # Lowered to 20%
      echo "Coverage below 20% threshold"
      exit 1
    fi
```

---

## Docker Build Failures

### Issue: Docker Build Timeout

**Symptoms**:
- Build job fails after 10+ minutes
- Error: "context canceled"
- Build hangs at "COPY requirements.txt"

**Root Causes**:
1. **Large build context**: Too many files copied into Docker image
2. **Slow network**: Pip downloads taking too long
3. **Cache miss**: No layer caching, rebuilding everything

**Solutions**:

**Solution 1: Optimize .dockerignore**
```bash
# Check build context size
du -sh backend/

# Add exclusions to .dockerignore
cat > backend/.dockerignore <<EOF
tests/
*.md
.git/
.github/
__pycache__/
*.pyc
.coverage
htmlcov/
.pytest_cache/
EOF

# Re-run build
docker build -t atom-backend:test ./backend
```

**Solution 2: Use BuildKit cache**
```yaml
# In .github/workflows/ci.yml
- name: Build Docker image
  uses: docker/build-push-action@v5
  with:
    cache-from: type=gha,mode=max
    cache-to: type=gha,mode=max
```

**Solution 3: Increase timeout**
```yaml
# In .github/workflows/ci.yml
- name: Build Docker image
  timeout-minutes: 30  # Increase from default 10
  uses: docker/build-push-action@v5
```

---

### Issue: Docker Layer Cache Not Working

**Symptoms**:
- Build takes same time every run (no improvement)
- Docker logs show "CACHED" for 0 layers
- cache-from step shows "Cache not found"

**Root Causes**:
1. **mode=min**: Only final layer cached
2. **Cache key mismatch**: cache-from and cache-to keys don't match
3. **BuildKit not enabled**: Using legacy builder

**Solutions**:

**Solution 1: Switch to mode=max**
```yaml
# In .github/workflows/ci.yml
cache-to: type=gha,mode=max  # Was: mode=min
```

**Solution 2: Match cache keys**
```yaml
# Ensure cache-from and cache-to match
cache-from: type=gha,scope=buildx
cache-to: type=gha,mode=max,scope=buildx
```

**Solution 3: Enable BuildKit**
```yaml
# In .github/workflows/ci.yml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3
```

---

### Issue: Docker Image Push Failed

**Symptoms**:
- Build succeeds but push fails
- Error: "denied: permission_denied"
- Error: "no basic auth credentials"

**Root Causes**:
1. **Invalid credentials**: REGISTRY_USERNAME or REGISTRY_PASSWORD wrong
2. **Registry URL wrong**: Pushing to wrong registry
3. **Authentication failed**: Docker login failed

**Solutions**:

**Solution 1: Verify registry credentials**
```bash
# Check secrets are set
gh secret list | grep REGISTRY

# Update secrets if needed
gh secret set REGISTRY_USERNAME <<< "dockerhub-user"
gh secret set REGISTRY_PASSWORD <<< "dckr_pat_xxxxx"

# Test credentials locally
docker login registry.example.com -u "$REGISTRY_USERNAME" -p "$REGISTRY_PASSWORD"
```

**Solution 2: Verify registry URL**
```yaml
# In .github/workflows/deploy.yml
env:
  REGISTRY: registry.example.com  # Verify this is correct
  IMAGE_NAME: atom
```

**Solution 3: Debug authentication**
```bash
# Check GitHub Actions log for login step
gh run view --log | grep "Log in to container registry"

# Verify login succeeded
# Expected: "Login Succeeded"
```

---

## Deployment Failures

### Issue: kubectl Command Failed

**Symptoms**:
- Deploy job fails at "Update deployment image" step
- Error: "error: you must be logged in to the server"
- kubectl commands fail with "Unauthorized"

**Root Causes**:
1. **Invalid kubeconfig**: KUBECONFIG secret expired or invalid
2. **Wrong context**: kubectl pointing to wrong cluster
3. **RBAC denied**: Service account lacks permissions

**Solutions**:

**Solution 1: Refresh kubeconfig secret**
```bash
# Generate new kubeconfig
kubectl config use-context staging
base64 ~/.kube/config > kubeconfig-staging.base64

# Update GitHub secret
gh secret set KUBECONFIG_STAGING < kubeconfig-staging.base64

# Re-run deployment
gh workflow run deploy.yml
```

**Solution 2: Verify kubectl context**
```bash
# Check current context
kubectl config current-context

# Set correct context
kubectl config use-context staging-context

# Verify cluster connectivity
kubectl cluster-info

# Test kubectl command
kubectl get pods --namespace=staging
```

**Solution 3: Check RBAC permissions**
```bash
# Check service account permissions
kubectl auth can-i update deployments/deploy --namespace=staging
kubectl auth can-i rollout undo deployment/atom --namespace=staging

# If denied, update RBAC rules
kubectl apply -f k8s/rbac.yaml
```

---

### Issue: Smoke Tests Fail with 401 Unauthorized

**Symptoms**:
- Smoke tests fail immediately after deployment
- Error: "HTTP/1.1 401 Unauthorized"
- Login request returns null token

**Root Causes**:
1. **Missing smoke test user**: User not created in database
2. **Wrong credentials**: SMOKE_TEST_PASSWORD mismatch
3. **Database migration failed**: smoke_test user not created

**Solutions**:

**Solution 1: Create smoke test user**
```bash
# Check if user exists
psql -c "SELECT username FROM users WHERE username='smoke_test'"

# If not exists, create migration
alembic revision -m "create smoke test user"
# Edit migration file to create user
alembic upgrade head
```

**Solution 2: Update GitHub secrets**
```bash
# Set smoke test credentials
gh secret set SMOKE_TEST_USERNAME <<< "smoke_test"
gh secret set SMOKE_TEST_PASSWORD <<< "changeme123"

# Re-run deployment
gh workflow run deploy.yml
```

**Solution 3: Verify user is active**
```bash
# Check user status
psql -c "SELECT username, is_active, is_smoke_test_user FROM users WHERE username='smoke_test'"

# If inactive, activate
psql -c "UPDATE users SET is_active=true WHERE username='smoke_test'"
```

---

### Issue: Pods Not Ready After Deployment

**Symptoms**:
- Deployment completes but pods stuck in "NotReady" state
- kubectl get pods shows 0/1 ready
- Pod logs show startup errors

**Root Causes**:
1. **Missing secrets**: Environment variables not set
2. **Database connection failed**: Database not reachable
3. **Resource limits**: Insufficient CPU/memory

**Solutions**:

**Solution 1: Check pod status**
```bash
# Get pod name
POD=$(kubectl get pods --namespace=staging -l app=atom -o jsonpath='{.items[0].metadata.name}')

# Describe pod
kubectl describe pod $POD --namespace=staging

# Check pod logs
kubectl logs $POD --namespace=staging --tail=100
```

**Solution 2: Check missing secrets**
```bash
# Verify secrets exist
kubectl get secrets --namespace=staging

# Check environment variables in pod
kubectl exec -it $POD --namespace=staging -- env | grep ATOM

# If missing, create secrets
kubectl create secret generic atom-secrets \
  --from-literal=database-url="postgresql://..." \
  --namespace=staging
```

**Solution 3: Check resource limits**
```bash
# View deployment resource limits
kubectl describe deployment atom --namespace=staging | grep -A 5 "Limits"

# Increase resource limits if needed
kubectl set resources deployment atom \
  --limits=cpu=2000m,memory=4Gi \
  --requests=cpu=1000m,memory=2Gi \
  --namespace=staging
```

---

## Smoke Test Failures

### Issue: Smoke Test Timeout

**Symptoms**:
- Smoke tests fail with timeout error
- Health checks don't respond within timeout
- Smoke test script hangs

**Root Causes**:
1. **Application not starting**: Crash loop before health check
2. **Readiness probe failing**: Dependencies not ready
3. **Network timeout**: Firewall blocking requests

**Solutions**:

**Solution 1: Check pod logs**
```bash
# Get pod name
POD=$(kubectl get pods --namespace=staging -l app=atom -o jsonpath='{.items[0].metadata.name}')

# Check pod logs
kubectl logs $POD --namespace=staging --tail=100 --follow

# Look for errors
kubectl logs $POD --namespace=staging | grep -i "error\|exception\|failed"
```

**Solution 2: Check health endpoints**
```bash
# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=atom --namespace=staging --timeout=5m

# Test health endpoint
kubectl exec -it $POD --namespace=staging -- curl -f http://localhost:8000/health/live
```

**Solution 3: Increase smoke test timeout**
```yaml
# In .github/workflows/deploy.yml
- name: Run smoke tests
  run: |
    timeout 300 ./scripts/smoke-tests.sh staging  # 5 minutes
```

---

### Issue: Smoke Test Authentication Failed

**Symptoms**:
- Smoke tests fail at authentication step
- Error: "Invalid credentials"
- Token request returns 401

**Root Causes**:
1. **Wrong password**: SMOKE_TEST_PASSWORD incorrect
2. **User disabled**: is_active flag set to false
3. **Database not migrated**: User table doesn't exist

**Solutions**:

**Solution 1: Test authentication manually**
```bash
# Test login endpoint
curl -X POST https://staging.atom.example.com/api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=smoke_test&password=your_password"

# Expected: {"access_token": "...", "token_type": "bearer"}
# If 401: Check password is correct
```

**Solution 2: Verify user in database**
```bash
# Check user exists and is active
psql -c "SELECT username, is_active, is_smoke_test_user FROM users WHERE username='smoke_test'"

# If not found or inactive:
psql -c "UPDATE users SET is_active=true WHERE username='smoke_test'"
```

**Solution 3: Reset smoke test password**
```bash
# Generate new password hash
python -c "
from backend.core.security import get_password_hash
print(get_password_hash('new_password'))
"

# Update database
psql -c "UPDATE users SET hashed_password='$2b$12$...' WHERE username='smoke_test'"

# Update GitHub secret
gh secret set SMOKE_TEST_PASSWORD <<< "new_password"
```

---

## Monitoring Issues

### Issue: Prometheus Query Fails

**Symptoms**:
- Monitoring check step fails
- Error: "Connection refused" or "timeout"
- Smoke tests pass but deployment fails

**Root Causes**:
1. **Prometheus unreachable**: PROMETHEUS_URL not set or wrong
2. **Query syntax error**: Invalid PromQL expression
3. **Timeout**: Query takes too long (>10 seconds)

**Solutions**:

**Solution 1: Verify Prometheus URL**
```bash
# Check if PROMETHEUS_URL secret is set
gh secret list | grep PROMETHEUS_URL

# Test Prometheus connectivity
curl "$PROMETHEUS_URL/-/healthy"

# If unreachable, skip monitoring (deployment continues)
# Monitoring check is non-blocking (graceful degradation)
```

**Solution 2: Validate PromQL query**
```bash
# Test query in Prometheus UI
# Visit: http://prometheus:9090/graph
# Enter query: sum(rate(http_requests_total[5m]))
# Click "Execute"

# Fix query syntax errors
# Common errors:
# - Missing quotes: status=~"5.." (correct)
# - Wrong function: rate(deployment_total) (correct: sum(rate(...)))
```

**Solution 3: Increase query timeout**
```yaml
# In .github/workflows/deploy.yml
curl -s -G "$PROMETHEUS_URL/api/v1/query" \
  --max-time 30 \  # Increase from default 10
  --data-urlencode "query=$QUERY"
```

---

### Issue: Grafana Dashboard Update Fails

**Symptoms**:
- Dashboard update step fails
- Error: "401 Unauthorized" or "404 Not Found"
- Grafana API returns error

**Root Causes**:
1. **Invalid API key**: GRAFANA_API_KEY expired or wrong
2. **Wrong dashboard UID**: Dashboard not found in Grafana
3. **Permission denied**: Service account lacks dashboard update permission

**Solutions**:

**Solution 1: Refresh Grafana API key**
```bash
# Create new service account token in Grafana
# Visit: http://grafana:3000/org/serviceaccounts
# Create service account → Add token → Copy token

# Update GitHub secret
gh secret set GRAFANA_API_KEY <<< "eyJr..."

# Re-run deployment
gh workflow run deploy.yml
```

**Solution 2: Verify dashboard UID**
```bash
# Check dashboard exists
curl -X GET "$GRAFANA_URL/api/dashboards/uid/atom-deployment-overview" \
  -H "Authorization: Bearer $GRAFANA_API_KEY"

# If 404, create dashboard first
curl -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @backend/monitoring/grafana/deployment-overview.json
```

**Solution 3: Check service account permissions**
```bash
# Verify service account has admin role
curl -X GET "$GRAFANA_URL/api/serviceaccounts" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" | jq

# If role is Viewer or Editor, update to Admin
# Visit: http://grafana:3000/org/serviceaccounts
# Edit service account → Role: Admin
```

---

## Rollback Issues

### Issue: Rollback Command Hangs

**Symptoms**:
- Rollback step starts but never completes
- kubectl rollout status waits indefinitely
- Deployment stuck in "Progressing" state

**Root Causes**:
1. **Pods not ready**: New pods failing to start
2. **Missing replicas**: Deployment has 0 replicas
3. **Resource limits**: Insufficient CPU/memory

**Solutions**:

**Solution 1: Check pod status**
```bash
# List pods with status
kubectl get pods -l app=atom

# Describe failing pod
kubectl describe pod <pod-name>

# Check pod logs
kubectl logs <pod-name>
```

**Solution 2: Force rollback timeout**
```bash
# Rollback with shorter timeout
kubectl rollout undo deployment/atom --timeout=1m

# If timeout fails, scale deployment manually
kubectl scale deployment atom --replicas=0
kubectl scale deployment atom --replicas=3
```

**Solution 3: Check resource limits**
```bash
# View deployment resource limits
kubectl describe deployment atom | grep -A 5 "Limits"

# Increase resource limits if needed
kubectl set resources deployment atom \
  --limits=cpu=2000m,memory=4Gi \
  --requests=cpu=1000m,memory=2Gi
```

---

### Issue: Rollback Doesn't Fix Error Rate

**Symptoms**:
- Rollback completes but error rate remains high
- Previous version also has issues
- Error rate doesn't return to baseline

**Root Causes**:
1. **Database migration issue**: Rollback doesn't revert database
2. **External dependency**: Third-party service down
3. **Traffic spike**: Normal traffic increase, not deployment issue

**Solutions**:

**Solution 1: Rollback database migration**
```bash
# Check current migration version
alembic current

# Rollback migration
alembic downgrade -1

# Verify error rate improves
curl "$PROMETHEUS_URL/api/v1/query?query=error_rate"
```

**Solution 2: Check external dependencies**
```bash
# Check third-party service status
curl https://api.openai.com/v1/models
curl https://api.anthropic.com/v1/messages

# If external service down, wait for recovery
# Check status page: https://status.openai.com
```

**Solution 3: Analyze traffic patterns**
```bash
# Check request rate
curl "$PROMETHEUS_URL/api/v1/query?query=rate(http_requests_total[5m])"

# Compare to baseline
curl "$PROMETHEUS_URL/api/v1/query?query=rate(http_requests_total[5m] offset 1h)"

# If traffic spike is legitimate, scale up pods
kubectl scale deployment atom --replicas=10
```

---

## Escalation Procedures

**When to escalate**:
- Issue not resolved after 30 minutes
- Production deployment blocked
- Customer impact (P0/P1 incident)

**Escalation contacts**:
- **DevOps Lead**: devops-lead@atom.example.com
- **Engineering Manager**: eng-mgr@atom.example.com
- **On-Call Engineer**: on-call@atom.example.com

**Escalation template**:
```markdown
## CI/CD Issue Escalation

**Issue**: [Brief description]
**Impact**: [Production/Staging blocked]
**Duration**: [X minutes]
**Attempted Solutions**: [List steps tried]
**Error Logs**: [Paste relevant logs]
**Workflow Run**: [GitHub Actions link]

**Request**: [Specific help needed]
```
