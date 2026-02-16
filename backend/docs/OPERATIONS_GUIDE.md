# Atom Operations Guide

> **Version:** 1.0
> **Last Updated:** 2026-02-16
> **Purpose:** Daily operations and common tasks for production environments

---

## Overview

This guide provides operational procedures for running Atom in production, including daily operations, common administrative tasks, monitoring best practices, and incident response.

**Target Audience:** DevOps engineers, SREs, system administrators

**Prerequisites:**
- Access to production infrastructure (Kubernetes/Docker)
- Database admin access (PostgreSQL)
- Monitoring system access (Prometheus/Grafana)
- Basic understanding of Atom architecture

---

## Daily Operations

### Morning Checklist (Daily 9:00 AM)

**Health Status:**
```bash
# Check liveness (service is running)
curl -f http://atom.example.com/health/live || echo "ALERT: Service down"

# Check readiness (service can accept traffic)
curl -f http://atom.example.com/health/ready || echo "ALERT: Service not ready"

# Check all components
curl -s http://atom.example.com/health/ready | jq '.checks'
# Expected: All "healthy"
```

**Database Status:**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check database size
psql -U atom -d atom -c "SELECT pg_size_pretty(pg_database_size('atom'));"

# Check table row counts
psql -U atom -d atom -c "
SELECT
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC
LIMIT 10;
"

# Check active connections
psql -U atom -d atom -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'atom';"
```

**Redis Status:**
```bash
# Check Redis is running
redis-cli ping
# Expected: PONG

# Check memory usage
redis-cli INFO memory | grep used_memory_human

# Check connected clients
redis-cli INFO clients | grep connected_clients
```

**Review Error Logs:**
```bash
# Check for errors in last 24 hours
jq 'select(.level == "error")' /var/log/atom/atom.log | tail -100

# Count errors by type
jq -r 'select(.level == "error") | .error_code' /var/log/atom/atom.log | sort | uniq -c | sort -rn

# Check for critical errors
grep -i "critical\|emergency\|fatal" /var/log/atom/atom.log | tail -50
```

**Monitor Metrics:**
```bash
# Check error rate (Prometheus)
curl -s 'http://prometheus.example.com/api/v1/query?query=rate(atom_http_errors_total[5m])' | jq '.data.result[0].value[1]'
# Alert if: >0.01 (1%)

# Check P95 latency
curl -s 'http://prometheus.example.com/api/v1/query?query=histogram_quantile(0.95, atom_latency_seconds)' | jq '.data.result[0].value[1]'
# Alert if: >1.0

# Check request rate
curl -s 'http://prometheus.example.com/api/v1/query?query=rate(atom_http_requests_total[5m])' | jq '.data.result[0].value[1]'
# Baseline: Track trend over time
```

**Agent Execution Rates:**
```bash
# Check agent executions in last hour
psql -U atom -d atom -c "
SELECT
    COUNT(*) as total_executions,
    COUNT(DISTINCT agent_id) as unique_agents,
    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) as avg_duration_sec
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '1 hour';
"

# Check execution status distribution
psql -U atom -d atom -c "
SELECT
    status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '1 hour'
GROUP BY status
ORDER BY count DESC;
"
```

### End-of-Day Checklist (Daily 6:00 PM)

**Review Alerts:**
```bash
# Check Prometheus alerting rules
curl -s 'http://prometheus.example.com/api/v1/rules' | jq '.data.groups[].rules[] | select(.type=="alerting") | {name: .name, state: .state}'

# Check resolved alerts
# Grafana Dashboard: http://grafana.example.com/d/atom-alerts
```

**Backup Verification:**
```bash
# Verify last backup completed
ls -lh /backups/atom/ | tail -5

# Check backup integrity
pg_restore --list /backups/atom/backup_$(date +%Y%m%d).sql | head -20
```

**Capacity Planning:**
```bash
# Check disk usage
df -h /var/lib/postgresql
df -h /var/lib/redis
df -h /var/log/atom

# Check memory usage
free -h

# Check CPU usage
top -bn1 | head -20
```

---

## Common Tasks

### Restarting Services Gracefully

**Kubernetes Rolling Restart:**
```bash
# Restart deployment with zero downtime
kubectl rollout restart deployment/atom

# Monitor rollout status
kubectl rollout status deployment/atom

# Watch pod restart
kubectl get pods -l app=atom -w

# Check logs during restart
kubectl logs -l app=atom --tail=100 -f
```

**Docker Graceful Restart:**
```bash
# Restart containers one at a time
for container in $(docker ps -q -f name=atom); do
    echo "Restarting container: $container"
    docker restart $container
    sleep 10  # Wait for health check
    curl -f http://localhost:8000/health/ready || echo "Health check failed"
done

# Verify all containers running
docker ps -f name=atom
```

**Systemd Service Restart:**
```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart atom service
sudo systemctl restart atom

# Check service status
sudo systemctl status atom

# View logs
sudo journalctl -u atom -n 100 -f
```

### Running Database Migrations

**Before Migration:**
```bash
# Backup database
pg_dump atom > backup_$(date +%Y%m%d_%H%M%S).sql

# Check current migration version
alembic current

# Review migration script
alembic show <revision_id>
```

**Execute Migration:**
```bash
# Dry run (SQL only)
alembic upgrade head --sql

# Execute migration
alembic upgrade head

# Verify migration success
alembic current

# Check for errors
tail -100 /var/log/atom/atom.log | grep -i migration
```

**After Migration:**
```bash
# Verify schema
psql -U atom -d atom -c "\dt"

# Verify data integrity
psql -U atom -d atom -c "
SELECT COUNT(*) FROM agent_registry;
SELECT COUNT(*) FROM agent_execution;
SELECT COUNT(*) FROM episode;
"

# Test application
curl -f http://atom.example.com/health/ready
```

**Rollback if Needed:**
```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Restore from backup
psql atom < backup_YYYYMMDD_HHMMSS.sql
```

### Checking Agent Status

**List All Agents:**
```bash
psql -U atom -d atom -c "
SELECT
    id,
    name,
    status,
    maturity_level,
    created_at
FROM agent_registry
ORDER BY created_at DESC
LIMIT 20;
"
```

**Check Agent Executions:**
```bash
# Recent executions for an agent
psql -U atom -d atom -c "
SELECT
    id,
    status,
    error_message,
    started_at,
    ended_at,
    EXTRACT(EPOCH FROM (ended_at - started_at)) as duration_sec
FROM agent_execution
WHERE agent_id = 'agent_id_here'
ORDER BY started_at DESC
LIMIT 10;
"
```

**Check Agent Performance:**
```bash
# Average execution time by agent
psql -U atom -d atom -c "
SELECT
    agent_id,
    COUNT(*) as executions,
    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))) as avg_duration_sec,
    MIN(EXTRACT(EPOCH FROM (ended_at - started_at))) as min_duration_sec,
    MAX(EXTRACT(EPOCH FROM (ended_at - started_at))) as max_duration_sec
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_id
ORDER BY avg_duration_sec DESC;
"
```

**Check Agent Errors:**
```bash
# Recent failed executions
psql -U atom -d atom -c "
SELECT
    agent_id,
    error_message,
    COUNT(*) as failure_count
FROM agent_execution
WHERE status = 'failed'
AND started_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_id, error_message
ORDER BY failure_count DESC
LIMIT 10;
"
```

### Viewing Skill Execution Logs

**Community Skills:**
```bash
# Recent skill executions
psql -U atom -d atom -c "
SELECT
    skill_name,
    skill_source,
    status,
    error_message,
    created_at
FROM skill_execution
ORDER BY created_at DESC
LIMIT 20;
"
```

**Skill Performance:**
```bash
# Skill execution statistics
psql -U atom -d atom -c "
SELECT
    skill_name,
    COUNT(*) as executions,
    AVG(EXTRACT(EPOCH FROM (ended_at - created_at))) as avg_duration_sec,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM skill_execution
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY skill_name
ORDER BY executions DESC;
"
```

**Skill Errors:**
```bash
# Recent skill failures
psql -U atom -d atom -c "
SELECT
    skill_name,
    error_message,
    COUNT(*) as failure_count
FROM skill_execution
WHERE status = 'failed'
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY skill_name, error_message
ORDER BY failure_count DESC
LIMIT 10;
"
```

### Managing User Permissions

**List All Users:**
```bash
# Assuming user management is implemented
psql -U atom -d atom -c "
SELECT
    id,
    username,
    email,
    role,
    created_at
FROM users
ORDER BY created_at DESC;
"
```

**Update User Role:**
```bash
# Promote user to admin
psql -U atom -d atom -c "
UPDATE users
SET role = 'admin', updated_at = NOW()
WHERE id = 'user_id_here';
"
```

**Check User Permissions:**
```bash
# Verify agent access permissions
psql -U atom -d atom -c "
SELECT
    user_id,
    agent_id,
    permission_level,
    granted_at
FROM agent_permissions
WHERE user_id = 'user_id_here';
"
```

### Managing Episodic Memory

**Check Episode Storage:**
```bash
# Episode count by status
psql -U atom -d atom -c "
SELECT
    storage_tier,
    COUNT(*) as episode_count,
    MIN(created_at) as oldest_episode,
    MAX(created_at) as newest_episode
FROM episode
GROUP BY storage_tier;
"
```

**Episode Lifecycle:**
```bash
# Check for episodes ready for consolidation
psql -U atom -d atom -c "
SELECT
    storage_tier,
    COUNT(*) as episode_count,
    SUM(access_count) as total_accesses,
    AVG(ROUND(100.0 * relevance_score, 2)) as avg_relevance
FROM episode
WHERE created_at < NOW() - INTERVAL '30 days'
AND storage_tier = 'hot'
GROUP BY storage_tier;
"
```

**Memory Usage:**
```bash
# Check database size for episodic memory
psql -U atom -d atom -c "
SELECT
    pg_size_pretty(pg_total_relation_size('episode')) as episode_table_size,
    pg_size_pretty(pg_total_relation_size('episode_segment')) as segment_table_size;
"
```

---

## Monitoring Alerts

### Alert Configuration

**High Error Rate:**
```yaml
# Prometheus alerting rule
- alert: HighErrorRate
  expr: rate(atom_http_errors_total[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "High error rate detected"
    description: "Error rate is {{ $value }}% (threshold: 5%)"
```

**Slow Response Times:**
```yaml
- alert: HighLatency
  expr: histogram_quantile(0.95, atom_latency_seconds) > 1.0
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High P95 latency detected"
    description: "P95 latency is {{ $value }}s (threshold: 1s)"
```

**Database Connection Failures:**
```yaml
- alert: DatabaseConnectionFailure
  expr: atom_db_connection_errors_total > 10
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Database connection failures detected"
    description: "{{ $value }} connection errors in last 5 minutes"
```

**Disk Space Low:**
```yaml
- alert: DiskSpaceLow
  expr: node_filesystem_avail_bytes{mountpoint="/var/lib/postgresql"} / node_filesystem_size_bytes{mountpoint="/var/lib/postgresql"} < 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Low disk space on PostgreSQL mount"
    description: "Only {{ $value | humanizePercentage }} free space remaining"
```

**Memory Usage High:**
```yaml
- alert: HighMemoryUsage
  expr: atom_memory_usage_bytes / atom_memory_limit_bytes > 0.8
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High memory usage detected"
    description: "Memory usage is {{ $value | humanizePercentage }} (threshold: 80%)"
```

### Alert Response Procedures

**Severity: Critical**
1. Acknowledge alert immediately
2. Check health status: `curl /health/ready`
3. Check application logs for errors
4. Verify database connectivity
5. Prepare to rollback if needed
6. Notify on-call engineer

**Severity: Warning**
1. Acknowledge alert
2. Investigate root cause
3. Document findings
4. Create ticket if issue persists

---

## Performance Tuning

### Database Optimization

**Check Slow Queries:**
```sql
-- Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = 1000; -- 1 second

-- View slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

**Optimize Indexes:**
```sql
-- Missing indexes query
SELECT
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY n_distinct DESC;
```

**Vacuum and Analyze:**
```bash
# Run vacuum on large tables
psql -U atom -d atom -c "VACUUM ANALYZE agent_execution;"
psql -U atom -d atom -c "VACUUM ANALYZE episode;"
psql -U atom -d atom -c "VACUUM ANALYZE episode_segment;"
```

### Cache Optimization

**Governance Cache:**
```bash
# Check cache hit rate
curl -s http://prometheus.example.com/api/v1/query?query=governance_cache_hit_rate | jq '.data.result[0].value[1]'
# Target: >90%

# Clear cache if needed
curl -X POST http://atom.example.com/api/admin/cache/clear
```

**Redis Optimization:**
```bash
# Check Redis memory usage
redis-cli INFO memory | grep used_memory_human

# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits

# Clear cache (use with caution)
redis-cli FLUSHDB
```

### Application Performance

**Check Worker Pool:**
```bash
# Monitor active workers
curl -s http://prometheus.example.com/api/v1/query?query=atom_active_workers | jq '.data.result[0].value[1]'

# Check queue depth
curl -s http://prometheus.example.com/api/v1/query?query=atom_queue_depth | jq '.data.result[0].value[1]'
```

**Profile Agent Execution:**
```bash
# Enable profiling for specific agent
curl -X POST http://atom.example.com/api/agents/agent_id/profile \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

---

## Security Operations

### Certificate Management

**Check Certificate Expiry:**
```bash
# Check TLS certificate expiry
echo | openssl s_client -connect atom.example.com:443 2>/dev/null | openssl x509 -noout -dates

# Check if certificate expires in next 30 days
cert_expiry=$(echo | openssl s_client -connect atom.example.com:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
expiry_epoch=$(date -d "$cert_expiry" +%s)
current_epoch=$(date +%s)
days_until_expiry=$(( ($expiry_epoch - $current_epoch) / 86400 ))
if [ $days_until_expiry -lt 30 ]; then
    echo "WARNING: Certificate expires in $days_until_expiry days"
fi
```

### Security Audits

**Review Audit Logs:**
```bash
# Recent agent executions by user
psql -U atom -d atom -c "
SELECT
    user_id,
    agent_id,
    COUNT(*) as executions,
    MAX(started_at) as last_execution
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY user_id, agent_id
ORDER BY executions DESC;
"
```

**Check for Suspicious Activity:**
```bash
# Failed authentication attempts
grep -i "failed authentication\|unauthorized" /var/log/atom/atom.log | tail -100

# Unusual agent execution patterns
psql -U atom -d atom -c "
SELECT
    agent_id,
    user_id,
    COUNT(*) as execution_count,
    ARRAY_AGG(DISTINCT ip_address) as ip_addresses
FROM agent_execution
WHERE started_at > NOW() - INTERVAL '1 hour'
GROUP BY agent_id, user_id
HAVING COUNT(*) > 100
ORDER BY execution_count DESC;
"
```

---

## Backup and Recovery

### Database Backup

**Automated Backups:**
```bash
# Daily backup script (cron: 0 2 * * *)
#!/bin/bash
BACKUP_DIR="/backups/atom"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

pg_dump atom | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete
```

**Restore from Backup:**
```bash
# Stop application
kubectl scale deployment atom --replicas=0

# Restore database
gunzip < /backups/atom/backup_YYYYMMDD_HHMMSS.sql.gz | psql atom

# Restart application
kubectl scale deployment atom --replicas=3

# Verify health
curl http://atom.example.com/health/ready
```

### Configuration Backup

```bash
# Backup environment variables
kubectl get configmap atom-config -o yaml > atom_config_$(date +%Y%m%d).yaml

# Backup secrets
kubectl get secret atom-secrets -o yaml > atom_secrets_$(date +%Y%m%d).yaml

# Backup deployment configuration
kubectl get deployment atom -o yaml > atom_deployment_$(date +%Y%m%d).yaml
```

---

## References

- **Deployment Runbook:** backend/docs/DEPLOYMENT_RUNBOOK.md
- **Troubleshooting:** backend/docs/TROUBLESHOOTING.md
- **Monitoring:** backend/docs/MONITORING.md
- **Architecture:** CLAUDE.md
- **Database:** backend/alembic/README.md
