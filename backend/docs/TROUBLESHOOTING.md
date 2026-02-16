# Atom Troubleshooting Guide

> **Version:** 1.0
> **Last Updated:** 2026-02-16
> **Purpose:** Common issues and solutions for production operations

---

## Overview

This guide provides troubleshooting procedures for common issues encountered when running Atom in production. Each issue includes symptoms, causes, diagnostic steps, and resolution procedures.

**How to Use This Guide:**
1. Identify the symptom you're experiencing
2. Follow the diagnostic steps
3. Apply the resolution procedure
4. Verify the fix worked
5. Document the incident for future reference

**Emergency Contacts:**
- On-Call Engineer: oncall@example.com (pager: +1-555-0100)
- DevOps Lead: devops@example.com
- Database Admin: dba@example.com

---

## Common Issues

### Database Connection Errors

#### Symptom
- /health/ready returns 503 for database check
- Application logs show "database connection failed"
- Agents unable to execute

#### Diagnosis
```bash
# Check database is running
pg_isready -h localhost -p 5432
# Expected: server is accepting connections

# Check database is accessible
psql -U atom -d atom -c "SELECT 1;"
# Expected: returns 1

# Check connection count
psql -U atom -d atom -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'atom';"
# Expected: < max_connections (usually 100)

# Check for connection errors in logs
grep -i "database.*error\|connection.*failed" /var/log/atom/atom.log | tail -20
```

#### Causes

**Cause 1: Database is Down**
```bash
# Check PostgreSQL service status
sudo systemctl status postgresql

# Start PostgreSQL if stopped
sudo systemctl start postgresql
```

**Cause 2: Network Issue**
```bash
# Check connectivity to database host
ping postgres.example.com

# Check port is reachable
telnet postgres.example.com 5432

# Check firewall rules
sudo iptables -L -n | grep 5432
```

**Cause 3: Connection Pool Exhausted**
```bash
# Check idle connections
psql -U atom -d atom -c "
SELECT
    state,
    COUNT(*) as connections
FROM pg_stat_activity
WHERE datname = 'atom'
GROUP BY state;
"

# Kill long-running idle connections
psql -U atom -d atom -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'atom'
AND state = 'idle'
AND state_change < NOW() - INTERVAL '1 hour';
"
```

**Cause 4: Connection String Misconfigured**
```bash
# Check DATABASE_URL environment variable
echo $DATABASE_URL

# Verify connection string format
# postgresql://user:password@host:port/database
```

#### Resolution

**Step 1: Verify Database Status**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Start if stopped
sudo systemctl start postgresql

# Verify database exists
psql -U postgres -c "\l" | grep atom
```

**Step 2: Check Network Connectivity**
```bash
# Test network connectivity
ping postgres.example.com

# Test port connectivity
nc -zv postgres.example.com 5432

# Check DNS resolution
nslookup postgres.example.com
```

**Step 3: Verify Connection String**
```bash
# Test connection string
psql "$DATABASE_URL" -c "SELECT 1;"

# Update connection string if needed
kubectl set env deployment/atom DATABASE_URL="postgresql://..."

# Restart pods to pick up new env var
kubectl rollout restart deployment/atom
```

**Step 4: Check Connection Pool**
```bash
# Increase pool size if needed
# Update SQLAlchemy pool size in config
pool_size = 20
max_overflow = 10

# Restart application
kubectl rollout restart deployment/atom
```

**Step 5: Verify Health Check**
```bash
# Check database health check
curl -f http://atom.example.com/health/ready | jq '.checks.database'
# Expected: "healthy"
```

#### Prevention
- Set up connection pool monitoring
- Configure connection timeout and retry logic
- Use PgBouncer for connection pooling
- Monitor connection count metrics

---

### High Memory Usage

#### Symptom
- Memory >80% of limit
- OOM (Out of Memory) kills
- Containers restarting frequently
- Swap usage high

#### Diagnosis
```bash
# Check memory usage
kubectl top pod -l app=atom
# Or
docker stats --no-stream | grep atom

# Check for OOM kills
kubectl describe pod <pod-name> | grep -i oom
# Or
dmesg | grep -i "out of memory"

# Check application memory metrics
curl -s http://prometheus.example.com/api/v1/query?query=atom_memory_usage_bytes | jq '.data.result[0].value[1]'

# Check for memory leaks (compare over time)
curl -s 'http://prometheus.example.com/api/v1/query?query=atom_memory_usage_bytes[1h]' | jq '.data.result[0].values'
```

#### Causes

**Cause 1: Memory Leak**
```bash
# Check for growing memory usage over time
# Compare memory usage at different time points
```

**Cause 2: Large Episodic Memory Cache**
```bash
# Check episode cache size
psql -U atom -d atom -c "
SELECT
    storage_tier,
    COUNT(*) as episode_count,
    pg_size_pretty(pg_total_relation_size('episode')) as table_size
FROM episode
GROUP BY storage_tier;
"
```

**Cause 3: Too Many Concurrent Agents**
```bash
# Check active agent executions
psql -U atom -d atom -c "
SELECT
    status,
    COUNT(*) as count
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '10 minutes'
GROUP BY status;
"
```

**Cause 4: LLM Response Caching**
```bash
# Check cache size
redis-cli INFO memory | grep used_memory_human

# Check cache keys
redis-cli DBSIZE
```

#### Resolution

**Step 1: Identify Memory-Hungry Component**
```bash
# Profile Python memory usage
python -m memory_profiler backend/core/main.py

# Check object sizes in Python
import sys
sys.getsizeof(object)
```

**Step 2: Clear Episodic Memory Cache**
```bash
# Consolidate old episodes
curl -X POST http://atom.example.com/api/episodes/consolidate

# Archive old episodes to cold storage
curl -X POST http://atom.example.com/api/episodes/archive

# Verify cache size reduced
psql -U atom -d atom -c "SELECT COUNT(*) FROM episode WHERE storage_tier = 'hot';"
```

**Step 3: Tune Episode Lifecycle**
```bash
# Update episode decay configuration
# Reduce episode retention time
episode_decay_days = 30
consolidation_threshold = 100

# Restart application
kubectl rollout restart deployment/atom
```

**Step 4: Increase Memory Limits**
```bash
# Update Kubernetes resource limits
kubectl set resources deployment/atom \
  --limits=memory=4Gi \
  --requests=memory=2Gi
```

**Step 5: Restart Services**
```bash
# Graceful restart to free memory
kubectl rollout restart deployment/atom

# Monitor memory after restart
kubectl top pod -l app=atom -w
```

#### Prevention
- Set up memory usage alerts (>80%)
- Implement episode lifecycle management
- Use memory profiling in development
- Set appropriate resource limits

---

### Slow Agent Execution

#### Symptom
- Agents taking >30s to respond
- User complaints about slowness
- High latency in metrics

#### Diagnosis
```bash
# Check agent execution times
psql -U atom -d atom -c "
SELECT
    agent_id,
    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) as avg_duration_sec,
    MAX(EXTRACT(EPOCH FROM (ended_at - started_at))) as max_duration_sec,
    COUNT(*) as executions
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '1 hour'
GROUP BY agent_id
ORDER BY avg_duration_sec DESC
LIMIT 10;
"

# Check P95 latency
curl -s 'http://prometheus.example.com/api/v1/query?query=histogram_quantile(0.95, atom_latency_seconds)' | jq '.data.result[0].value[1]'

# Check for slow LLM responses
grep -i "llm.*timeout\|llm.*slow" /var/log/atom/atom.log | tail -20
```

#### Causes

**Cause 1: LLM Provider Latency**
```bash
# Check LLM provider status
curl -I https://api.openai.com/v1/models

# Test LLM response time
time curl https://api.openai.com/v1/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{"model": "gpt-4", "prompt": "test"}'
```

**Cause 2: Governance Cache Cold**
```bash
# Check cache hit rate
curl -s http://prometheus.example.com/api/v1/query?query=governance_cache_hit_rate | jq '.data.result[0].value[1]'
# Target: >90%
```

**Cause 3: Database Slow Queries**
```sql
-- Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- Check slow queries
SELECT
    query,
    calls,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

**Cause 4: BYOK Configuration Issues**
```bash
# Check BYOK handler configuration
grep -i "byok\|llm.*provider" /var/log/atom/atom.log | tail -20

# Verify API keys are set
echo $OPENAI_API_KEY | cut -c1-10
echo $ANTHROPIC_API_KEY | cut -c1-10
```

#### Resolution

**Step 1: Check LLM Provider Status**
```bash
# Test LLM provider connectivity
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Switch to backup provider if primary is down
kubectl set env deployment/atom LLM_PROVIDER=anthropic
kubectl rollout restart deployment/atom
```

**Step 2: Warm Governance Cache**
```bash
# Pre-warm cache with common agents
curl -X POST http://atom.example.com/api/admin/cache/warm \
  -H "Content-Type: application/json" \
  -d '{"agent_ids": ["agent1", "agent2", "agent3"]}'

# Verify cache hit rate improved
curl -s http://prometheus.example.com/api/v1/query?query=governance_cache_hit_rate | jq '.data.result[0].value[1]'
```

**Step 3: Optimize Database Queries**
```bash
# Add indexes for slow queries
psql -U atom -d atom -c "CREATE INDEX idx_agent_execution_started_at ON agent_execution(started_at);"

# Run vacuum and analyze
psql -U atom -d atom -c "VACUUM ANALYZE;"
```

**Step 4: Increase Timeouts**
```bash
# Update LLM timeout configuration
llm_timeout = 60  # seconds

# Restart application
kubectl rollout restart deployment/atom
```

**Step 5: Scale Up**
```bash
# Increase replica count
kubectl scale deployment/atom --replicas=5

# Verify scaling
kubectl get pods -l app=atom
```

#### Prevention
- Set up latency monitoring and alerts
- Use multiple LLM providers for redundancy
- Keep governance cache warm
- Optimize database queries regularly

---

### WebSocket Connection Failures

#### Symptom
- Clients unable to connect via WebSocket
- Real-time updates not working
- Errors in browser console

#### Diagnosis
```bash
# Check Redis is running (WebSocket manager uses Redis)
redis-cli ping
# Expected: PONG

# Check Redis connectivity
redis-cli INFO clients | grep connected_clients

# Check WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://atom.example.com/api/social/ws/feed

# Check for WebSocket errors in logs
grep -i "websocket\|ws.*error" /var/log/atom/atom.log | tail -20
```

#### Causes

**Cause 1: Redis is Down**
```bash
# Check Redis service status
sudo systemctl status redis

# Start Redis if stopped
sudo systemctl start redis
```

**Cause 2: WebSocket Manager Issue**
```bash
# Check WebSocket manager process
ps aux | grep websocket

# Check for WebSocket manager errors
grep -i "websocket.*manager" /var/log/atom/atom.log | tail -20
```

**Cause 3: Network/Firewall Issue**
```bash
# Check if WebSocket port is open
telnet atom.example.com 8000

# Check firewall rules
sudo iptables -L -n | grep 8000
```

**Cause 4: Client-Side Issue**
```bash
# Check browser console for WebSocket errors
# Common errors:
# - WebSocket connection failed
# - WebSocket handshake failed
```

#### Resolution

**Step 1: Verify Redis Status**
```bash
# Check Redis is running
sudo systemctl status redis

# Start Redis if stopped
sudo systemctl start redis

# Verify Redis is accepting connections
redis-cli ping
```

**Step 2: Check WebSocket Configuration**
```bash
# Verify WebSocket manager is running
ps aux | grep websocket

# Restart WebSocket manager if needed
sudo systemctl restart atom-websocket
```

**Step 3: Test WebSocket Connectivity**
```bash
# Test WebSocket connection using websocat
websocat ws://atom.example.com/api/social/ws/feed

# Or use Python
python -c "
import asyncio
import websockets
async def test():
    async with websockets.connect('ws://atom.example.com/api/social/ws/feed') as ws:
        print('Connected')
asyncio.run(test())
"
```

**Step 4: Check Network/Firewall**
```bash
# Verify WebSocket port is accessible
nc -zv atom.example.com 8000

# Add firewall rule if needed
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

**Step 5: Restart Services**
```bash
# Restart Atom service
kubectl rollout restart deployment/atom

# Verify WebSocket connectivity
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://atom.example.com/api/social/ws/feed
```

#### Prevention
- Set up Redis monitoring
- Use WebSocket health checks
- Implement reconnection logic in clients
- Monitor WebSocket connection metrics

---

### Skill Execution Failures

#### Symptom
- Skills failing with timeout or error
- Community skills not executing
- Sandbox container issues

#### Diagnosis
```bash
# Check recent skill execution failures
psql -U atom -d atom -c "
SELECT
    skill_name,
    error_message,
    COUNT(*) as failure_count,
    MAX(created_at) as last_failure
FROM skill_execution
WHERE status = 'failed'
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY skill_name, error_message
ORDER BY failure_count DESC
LIMIT 10;
"

# Check Docker container logs for sandbox
docker logs atom-sandbox 2>&1 | tail -100

# Check for skill execution errors in logs
grep -i "skill.*error\|sandbox.*error" /var/log/atom/atom.log | tail -20
```

#### Causes

**Cause 1: Sandbox Container Issue**
```bash
# Check if sandbox container is running
docker ps | grep atom-sandbox

# Check sandbox container logs
docker logs atom-sandbox
```

**Cause 2: Missing Dependencies**
```bash
# Check for import errors in logs
grep -i "import.*error\|module.*not.*found" /var/log/atom/atom.log | tail -20
```

**Cause 3: Skill Code Error**
```bash
# Check for Python syntax errors
grep -i "syntax.*error\|indentation.*error" /var/log/atom/atom.log | tail -20
```

**Cause 4: Timeout**
```bash
# Check for timeout errors
grep -i "timeout" /var/log/atom/atom.log | grep skill | tail -20
```

#### Resolution

**Step 1: Check Sandbox Container**
```bash
# Verify sandbox container is running
docker ps | grep atom-sandbox

# Start sandbox container if stopped
docker start atom-sandbox

# Or recreate container
docker run -d --name atom-sandbox --restart unless-stopped \
  --memory=2g --cpus=2 \
  atom-sandbox:latest
```

**Step 2: Reinstall Dependencies**
```bash
# Rebuild sandbox image with dependencies
docker build -t atom-sandbox:latest -f docker/Dockerfile.sandbox .

# Restart sandbox container
docker stop atom-sandbox
docker rm atom-sandbox
docker run -d --name atom-sandbox --restart unless-stopped \
  --memory=2g --cpus=2 \
  atom-sandbox:latest
```

**Step 3: Fix Skill Code**
```bash
# Test skill locally
python -m pytools.validate_skill /path/to/skill/SKILL.md

# Fix syntax errors
# Update skill code
# Reimport skill
curl -X POST http://atom.example.com/api/skills/import \
  -F "file=@/path/to/skill/SKILL.md"
```

**Step 4: Increase Timeout**
```bash
# Update sandbox timeout configuration
sandbox_timeout = 300  # 5 minutes

# Restart application
kubectl rollout restart deployment/atom
```

**Step 5: Check Resource Limits**
```bash
# Check sandbox container resources
docker inspect atom-sandbox | grep -A 10 "Memory\|Cpu"

# Increase resource limits if needed
docker update --memory=4g --cpus=4 atom-sandbox
```

#### Prevention
- Validate skill code before import
- Use resource limits on sandbox containers
- Implement proper error handling in skills
- Monitor skill execution metrics

---

## Additional Troubleshooting Resources

### Log Analysis

**Structured Logs:**
```bash
# View logs by level
jq 'select(.level == "error")' /var/log/atom/atom.log | tail -100
jq 'select(.level == "warning")' /var/log/atom/atom.log | tail -100

# View logs by component
jq 'select(.service == "agent_governance")' /var/log/atom/atom.log | tail -100

# View logs by time range
jq 'select(.timestamp >= "2026-02-16T10:00:00Z" and .timestamp <= "2026-02-16T11:00:00Z")' /var/log/atom/atom.log
```

### Performance Profiling

**Python Profiling:**
```bash
# Profile CPU usage
python -m cProfile -o profile.stats backend/core/main.py

# Analyze profile
python -m pstats profile.stats

# Profile memory usage
python -m memory_profiler backend/core/main.py
```

### Database Performance

**Query Analysis:**
```sql
-- Find slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;

-- Find missing indexes
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY n_distinct DESC;
```

---

## Emergency Procedures

### Full System Restart

**Use when:** Nothing else works, system is completely unresponsive

```bash
# Stop all services
kubectl scale deployment atom --replicas=0

# Wait for all pods to terminate
kubectl get pods -l app=atom

# Start services
kubectl scale deployment atom --replicas=3

# Monitor startup
kubectl get pods -l app=atom -w

# Verify health
curl http://atom.example.com/health/ready
```

### Emergency Rollback

**See:** backend/docs/DEPLOYMENT_RUNBOOK.md - Rollback Procedure

### Incident Response

**See:** backend/docs/INCIDENT_RESPONSE.md (if exists)

---

## References

- **Deployment Runbook:** backend/docs/DEPLOYMENT_RUNBOOK.md
- **Operations Guide:** backend/docs/OPERATIONS_GUIDE.md
- **Monitoring:** backend/docs/MONITORING.md
- **Architecture:** CLAUDE.md
