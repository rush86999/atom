# Atom SaaS Sync Troubleshooting Guide

**Purpose**: Comprehensive guide for diagnosing and resolving Atom SaaS sync issues

**Last Updated**: 2026-02-19

**Target Audience**: Operations teams, SREs, platform engineers

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Common Issues](#common-issues)
4. [Diagnosis Steps](#diagnosis-steps)
5. [Resolution Procedures](#resolution-procedures)
6. [Performance Tuning](#performance-tuning)
7. [Escalation Path](#escalation-path)
8. [Runbooks](#runbooks)

---

## Overview

### What is Atom SaaS Sync?

Atom SaaS sync is a background service that keeps your local Atom marketplace synchronized with the Atom SaaS platform. It syncs:

- **Skills**: Community skills from Atom SaaS marketplace
- **Categories**: Skill categories and taxonomy
- **Ratings**: User ratings and reviews (bidirectional)
- **Updates**: Real-time updates via WebSocket

### Sync Components

1. **Background Sync Service** (Plan 61-01)
   - Scheduled sync every 30 minutes
   - Full skill and category sync
   - Incremental updates for efficiency

2. **Rating Sync Service** (Plan 61-02)
   - Bidirectional rating sync
   - Batch uploads every 30 minutes
   - Failed upload retry mechanism

3. **WebSocket Client** (Plan 61-03)
   - Real-time updates from Atom SaaS
   - Automatic reconnection with backoff
   - Skill/rating update notifications

4. **Conflict Resolution** (Plan 61-04)
   - Automatic conflict detection
   - Manual resolution workflows
   - Version conflict handling

### Data Flow

```
┌─────────────────┐
│  Local Atom DB  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│          Sync Health Monitor                │
│  - Health checks (/health/sync)             │
│  - Metrics (/metrics/sync)                  │
│  - Admin API (/api/admin/sync/*)            │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│         Background Sync Service             │
│  - Scheduled sync (30 min interval)         │
│  - Batch processing (100 skills/batch)      │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│          Atom SaaS API                      │
│  - Skills endpoint                          │
│  - Categories endpoint                      │
│  - Ratings endpoint                         │
│  - WebSocket updates                        │
└─────────────────────────────────────────────┘
```

---

## Architecture

### Key Services

| Service | File | Purpose |
|---------|------|---------|
| SyncHealthMonitor | `core/sync_health_monitor.py` | Health checks for Kubernetes probes |
| SyncService | `core/sync_service.py` | Background sync orchestration |
| RatingSyncService | `core/rating_sync_service.py` | Bidirectional rating sync |
| AtomSaaSWebSocketClient | `core/websocket_client.py` | Real-time updates |
| ConflictResolutionService | `core/conflict_resolution.py` | Conflict detection and resolution |

### Database Models

| Model | Table | Purpose |
|-------|-------|---------|
| SyncState | sync_state | Current sync status and timestamps |
| SkillRating | skill_ratings | User ratings and reviews |
| CommunitySkill | community_skills | Local skill cache |

### Admin API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/sync/trigger` | POST | Trigger manual sync |
| `/api/admin/sync/status` | GET | Get sync status |
| `/api/admin/sync/config` | GET | Get sync configuration |
| `/api/admin/sync/ratings` | POST | Trigger rating sync |
| `/api/admin/sync/ratings/status` | GET | Get rating sync status |
| `/api/admin/sync/ratings/failed-uploads` | GET | List failed uploads |
| `/api/admin/sync/websocket/status` | GET | Get WebSocket status |
| `/api/admin/sync/websocket/reconnect` | POST | Force WebSocket reconnect |
| `/api/admin/sync/conflicts` | GET | List conflicts |
| `/api/admin/sync/conflicts/{id}/resolve` | POST | Resolve conflict |

### Monitoring Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health/sync` | Health check for Kubernetes probes |
| `/metrics/sync` | Prometheus metrics for sync operations |

---

## Common Issues

### Issue 1: Sync Not Running

**Symptoms**:
- Last sync timestamp is old (> 1 hour)
- Skills cache is empty or outdated
- `/health/sync` returns `unhealthy` status

**Diagnosis**:
```bash
# Check sync status
curl http://localhost:8000/api/admin/sync/status

# Check health
curl http://localhost:8000/health/sync

# Check logs
grep "sync" logs/atom.log | tail -50

# Check scheduler
ps aux | grep sync
```

**Common Causes**:
1. Scheduler process stopped
2. Database connection issues
3. Atom SaaS API unavailable
4. Sync disabled in configuration

**Resolution**:
1. Restart scheduler service
2. Check database connectivity
3. Verify Atom SaaS API status
4. Trigger manual sync: `curl -X POST http://localhost:8000/api/admin/sync/trigger`

---

### Issue 2: WebSocket Won't Connect

**Symptoms**:
- WebSocket status shows `disconnected`
- High reconnection rate in metrics
- Real-time updates not received

**Diagnosis**:
```bash
# Check WebSocket status
curl http://localhost:8000/api/admin/sync/websocket/status

# Check reconnection metrics
curl http://localhost:8000/metrics/sync | grep websocket_reconnects_total

# Check network connectivity
ping api.atomsaas.com
telnet api.atomsaas.com 443

# Check firewall rules
sudo iptables -L | grep 443
```

**Common Causes**:
1. Network connectivity issues
2. Firewall blocking WebSocket
3. Atom SaaS WebSocket service down
4. Authentication token expired

**Resolution**:
1. Check network connectivity
2. Verify firewall rules allow outbound 443
3. Force reconnect: `curl -X POST http://localhost:8000/api/admin/sync/websocket/reconnect`
4. Re-authenticate if token expired

---

### Issue 3: Sync Failing with 500 Errors

**Symptoms**:
- High sync error rate in metrics
- Logs show HTTP 500 errors from Atom SaaS API
- Skills not appearing in cache

**Diagnosis**:
```bash
# Check error metrics
curl http://localhost:8000/metrics/sync | grep sync_errors_total

# Check logs for errors
grep "500" logs/atom.log | grep sync | tail -20

# Check Atom SaaS API status
curl -I https://api.atomsaas.com/health

# Test API manually
curl -H "Authorization: Bearer $TOKEN" https://api.atomsaas.com/skills
```

**Common Causes**:
1. Atom SaaS API experiencing issues
2. Invalid API credentials
3. Rate limiting from Atom SaaS
4. Malformed requests

**Resolution**:
1. Check Atom SaaS status page
2. Verify API credentials in `.env`
3. Reduce sync frequency if rate limited
4. Contact Atom SaaS support if API is down

---

### Issue 4: Skills Not Appearing in Cache

**Symptoms**:
- Sync completes successfully but skills don't appear
- `sync_skills_cached` metric shows 0
- Marketplace is empty in UI

**Diagnosis**:
```bash
# Check cache metrics
curl http://localhost:8000/metrics/sync | grep sync_skills_cached

# Check database
sqlite3 atom_dev.db "SELECT COUNT(*) FROM community_skills;"

# Check sync logs
grep "skills_cached" logs/atom.log | tail -20

# Check sync state
curl http://localhost:8000/api/admin/sync/status
```

**Common Causes**:
1. Sync not completing (network errors)
2. Database write errors
3. Sync logic issues
4. Atom SaaS returning empty results

**Resolution**:
1. Trigger manual sync and monitor logs
2. Check database disk space
3. Clear cache and re-sync (see Resolution Procedures below)
4. Verify Atom SaaS API returns data

---

### Issue 5: Ratings Not Syncing

**Symptoms**:
- User ratings not appearing on Atom SaaS
- `rating_sync_failed_uploads` metric increasing
- Ratings pending count high

**Diagnosis**:
```bash
# Check rating sync status
curl http://localhost:8000/api/admin/sync/ratings/status

# Check failed uploads
curl http://localhost:8000/api/admin/sync/ratings/failed-uploads

# Check rating metrics
curl http://localhost:8000/metrics/sync | grep rating_sync

# Check logs
grep "rating_sync" logs/atom.log | tail -30
```

**Common Causes**:
1. Atom SaaS rating API down
2. Invalid rating data
3. Network issues during upload
4. Rate limiting

**Resolution**:
1. Check Atom SaaS API status
2. Retry failed uploads: `curl -X POST http://localhost:8000/api/admin/sync/ratings/failed-uploads/{id}/retry`
3. Verify rating data integrity
4. Reduce batch size if rate limited

---

### Issue 6: Conflicts Not Resolving

**Symptoms**:
- High `conflicts_unresolved` count
- Conflicts list not empty
- Manual resolution not working

**Diagnosis**:
```bash
# List conflicts
curl http://localhost:8000/api/admin/sync/conflicts

# Check conflict metrics
curl http://localhost:8000/metrics/sync | grep conflicts

# Get conflict details
curl http://localhost:8000/api/admin/sync/conflicts/{id}

# Check logs
grep "conflict" logs/atom.log | tail -20
```

**Common Causes**:
1. Version conflicts not auto-resolvable
2. Data inconsistencies
3. Resolution logic bugs
4. Manual resolution required

**Resolution**:
1. Review conflict details
2. Choose resolution strategy (local_wins, remote_wins, merge)
3. Resolve conflicts: `curl -X POST http://localhost:8000/api/admin/sync/conflicts/{id}/resolve?strategy=local_wins`
4. Bulk resolve if needed: `curl -X POST http://localhost:8000/api/admin/sync/conflicts/bulk-resolve?strategy=remote_wins`

---

## Diagnosis Steps

### Step 1: Check Health Endpoint

```bash
curl http://localhost:8000/health/sync
```

**Expected Output**:
```json
{
  "status": "healthy",
  "last_sync": "2026-02-19T10:00:00Z",
  "sync_age_minutes": 5,
  "websocket_connected": true,
  "scheduler_running": true,
  "recent_errors": 0,
  "checks": {
    "last_sync": {"healthy": true},
    "websocket": {"healthy": true},
    "scheduler": {"healthy": true},
    "errors": {"healthy": true}
  }
}
```

**What to Look For**:
- `status` should be `healthy` or `degraded` (not `unhealthy`)
- `sync_age_minutes` should be < 30
- `websocket_connected` should be `true`
- `scheduler_running` should be `true`
- `recent_errors` should be 0

---

### Step 2: Check Sync Status

```bash
curl http://localhost:8000/api/admin/sync/status
```

**Expected Output**:
```json
{
  "status": "idle",
  "last_sync": "2026-02-19T10:00:00Z",
  "sync_age_minutes": 5,
  "skills_cached": 500,
  "categories_cached": 20,
  "last_error": null
}
```

**What to Look For**:
- `status` should be `idle` (sync complete) or `syncing` (in progress)
- `skills_cached` should be > 0
- `categories_cached` should be > 0
- `last_error` should be `null`

---

### Step 3: Check Logs

```bash
# Recent sync logs
grep "sync" logs/atom.log | tail -50

# Error logs
grep "ERROR" logs/atom.log | grep sync | tail -20

# WebSocket logs
grep "websocket" logs/atom.log | tail -30

# Rating sync logs
grep "rating_sync" logs/atom.log | tail -20
```

**What to Look For**:
- ERROR or CRITICAL messages
- Connection timeout errors
- HTTP 500 errors from Atom SaaS API
- Authentication failures

---

### Step 4: Check Metrics

```bash
curl http://localhost:8000/metrics/sync | grep -E "(sync_duration|sync_errors|websocket_connected)"
```

**What to Look For**:
- `sync_duration_seconds` should be < 60s for typical sync
- `sync_errors_total` should not be increasing rapidly
- `websocket_connected` should be 1 (connected)

---

### Step 5: Check WebSocket Status

```bash
curl http://localhost:8000/api/admin/sync/websocket/status
```

**Expected Output**:
```json
{
  "connected": true,
  "last_message": "2026-02-19T10:05:00Z",
  "reconnect_count": 0,
  "enabled": true
}
```

**What to Look For**:
- `connected` should be `true`
- `reconnect_count` should be low (< 10)
- `enabled` should be `true`

---

## Resolution Procedures

### Procedure 1: Trigger Manual Sync

**When to Use**: Sync is stale or skills are outdated

**Steps**:
```bash
# Trigger manual sync
curl -X POST http://localhost:8000/api/admin/sync/trigger

# Monitor sync status
watch -n 5 'curl -s http://localhost:8000/api/admin/sync/status | jq .'

# Check logs for progress
tail -f logs/atom.log | grep sync
```

**Expected Result**:
- Sync starts within 10 seconds
- Status changes from `idle` to `syncing`
- Sync completes within 5 minutes (depending on data size)

**If It Fails**:
1. Check network connectivity to Atom SaaS
2. Verify API credentials
3. Check Atom SaaS API status page
4. Review logs for errors

---

### Procedure 2: Restart WebSocket

**When to Use**: WebSocket disconnected, not reconnecting automatically

**Steps**:
```bash
# Check current status
curl http://localhost:8000/api/admin/sync/websocket/status

# Force reconnect
curl -X POST http://localhost:8000/api/admin/sync/websocket/reconnect

# Monitor reconnection
watch -n 2 'curl -s http://localhost:8000/api/admin/sync/websocket/status | jq .connected'

# Check logs
tail -f logs/atom.log | grep websocket
```

**Expected Result**:
- WebSocket connects within 30 seconds
- `connected` status changes to `true`
- Reconnection count increases by 1

**If It Fails**:
1. Check network connectivity
2. Verify firewall rules
3. Check Atom SaaS WebSocket service status
4. Re-authenticate if token expired

---

### Procedure 3: Clear Cache and Re-sync

**When to Use**: Cache is corrupted or inconsistent

**Steps**:
```bash
# Backup current data
cp atom_dev.db atom_dev.db.backup

# Stop sync service
systemctl stop atom-sync

# Clear sync cache (SQLite)
sqlite3 atom_dev.db "DELETE FROM community_skills;"
sqlite3 atom_dev.db "DELETE FROM sync_state;"

# Restart sync service
systemctl start atom-sync

# Trigger manual sync
curl -X POST http://localhost:8000/api/admin/sync/trigger

# Monitor sync progress
tail -f logs/atom.log | grep sync
```

**Expected Result**:
- Cache is cleared
- Sync starts from scratch
- All skills re-downloaded from Atom SaaS
- Sync completes successfully

**If It Fails**:
1. Restore from backup: `cp atom_dev.db.backup atom_dev.db`
2. Check database integrity
3. Verify Atom SaaS API is accessible
4. Contact support if issue persists

---

### Procedure 4: Resolve Conflicts

**When to Use**: Unresolved conflicts blocking sync

**Steps**:
```bash
# List conflicts
curl http://localhost:8000/api/admin/sync/conflicts | jq .

# Get conflict details
curl http://localhost:8000/api/admin/sync/conflicts/{conflict_id}

# Resolve single conflict
curl -X POST "http://localhost:8000/api/admin/sync/conflicts/{conflict_id}/resolve?strategy=local_wins"

# Bulk resolve conflicts
curl -X POST "http://localhost:8000/api/admin/sync/conflicts/bulk-resolve?strategy=remote_wins" \
  -H "Content-Type: application/json" \
  -d '{"conflict_ids": ["id1", "id2", "id3"]}'

# Verify resolution
curl http://localhost:8000/api/admin/sync/conflicts
```

**Resolution Strategies**:
- `local_wins`: Use local data (discard Atom SaaS changes)
- `remote_wins`: Use Atom SaaS data (overwrite local)
- `merge`: Attempt to merge both versions (if compatible)

**Expected Result**:
- Conflicts marked as resolved
- Sync continues
- No new conflicts created

**If It Fails**:
1. Verify conflict ID exists
2. Check resolution strategy is valid
3. Review conflict details to choose correct strategy
4. Contact support for complex conflicts

---

## Performance Tuning

### Tuning Parameter: Sync Interval

**Current**: 30 minutes

**When to Adjust**:
- **Decrease** (e.g., 15 minutes): Need more fresh data
- **Increase** (e.g., 60 minutes): Reduce API load

**How to Change**:
```bash
# Edit .env file
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15

# Restart sync service
systemctl restart atom-sync
```

**Trade-offs**:
- More frequent sync = fresher data but higher API load
- Less frequent sync = lower API load but stale data

---

### Tuning Parameter: Batch Size

**Current**: 100 skills per batch

**When to Adjust**:
- **Increase** (e.g., 200): Faster sync, fewer API calls
- **Decrease** (e.g., 50): Slower sync, less memory per batch

**How to Change**:
```bash
# Edit .env file
ATOM_SAAS_SYNC_BATCH_SIZE=200

# Restart sync service
systemctl restart atom-sync
```

**Trade-offs**:
- Larger batches = faster sync but more memory
- Smaller batches = slower sync but less memory

---

### Tuning Parameter: WebSocket Backoff

**Current**: Exponential backoff (1s, 2s, 4s, 8s, max 30s)

**When to Adjust**:
- **Increase** (e.g., max 60s): Atom SaaS WebSocket unreliable
- **Decrease** (e.g., max 15s): Want faster reconnection

**How to Change**:
```python
# Edit core/websocket_client.py
BACKOFF_MAX_SECONDS = 60  # Change from 30
```

**Trade-offs**:
- Longer backoff = less reconnection attempts but slower recovery
- Shorter backoff = faster recovery but more reconnection attempts

---

## Escalation Path

### Level 1: Operations Team

**Can Handle**:
- Manual sync triggers
- WebSocket restarts
- Failed upload retries
- Conflict resolution
- Configuration changes

**Tools Available**:
- Admin API endpoints
- Health checks
- Metrics dashboards
- Log access

**Escalate to Level 2 if**:
- Issue persists after standard procedures
- Database corruption suspected
- Atom SaaS API issues
- Unknown error patterns

---

### Level 2: Platform Engineers

**Can Handle**:
- Database recovery
- Sync service restarts
- Code-level debugging
- Atom SaaS API coordination
- Performance tuning

**Tools Available**:
- Database access
- Service deployment
- Code repository
- Atom SaaS support contact

**Escalate to Level 3 if**:
- Critical data loss
- Security incidents
- Atom SaaS platform-wide outage
- Requires architectural changes

---

### Level 3: Engineering Leadership

**Can Handle**:
- Critical incidents
- Security incidents
- Architectural decisions
- Atom SaaS vendor escalation
- Emergency deployments

**Tools Available**:
- Full system access
- Vendor contacts
- Incident management
- Emergency procedures

---

## Runbooks

### Runbook: Sync Stale

**Alert**: `SyncStale` or `SyncVeryStale`

**Severity**: Warning / Critical

**Impact**: Skills and categories may be outdated

**Diagnosis**:
1. Check health: `curl http://localhost:8000/health/sync`
2. Check sync status: `curl http://localhost:8000/api/admin/sync/status`
3. Check logs: `grep "sync" logs/atom.log | tail -50`

**Resolution**:
1. Trigger manual sync: `curl -X POST http://localhost:8000/api/admin/sync/trigger`
2. Monitor sync progress: `tail -f logs/atom.log | grep sync`
3. If sync fails, check Atom SaaS API status
4. If API is down, contact Atom SaaS support

**Verification**:
- Health check returns `healthy`
- `sync_age_minutes` < 30
- Skills and categories count > 0

---

### Runbook: WebSocket Disconnected

**Alert**: `WebSocketDisconnected` or `WebSocketDisconnectedCritical`

**Severity**: Warning / Critical

**Impact**: Real-time updates unavailable

**Diagnosis**:
1. Check WebSocket status: `curl http://localhost:8000/api/admin/sync/websocket/status`
2. Check metrics: `curl http://localhost:8000/metrics/sync | grep websocket`
3. Check network: `ping api.atomsaas.com`

**Resolution**:
1. Force reconnect: `curl -X POST http://localhost:8000/api/admin/sync/websocket/reconnect`
2. If reconnect fails, check network connectivity
3. Verify firewall rules allow outbound 443
4. Check Atom SaaS WebSocket service status

**Verification**:
- WebSocket `connected` = `true`
- `reconnect_count` stable (not increasing rapidly)
- Real-time updates working

---

### Runbook: High Error Rate

**Alert**: `HighSyncErrorRate` or `VeryHighSyncErrorRate`

**Severity**: Warning / Critical

**Impact**: Many sync operations failing

**Diagnosis**:
1. Check error metrics: `curl http://localhost:8000/metrics/sync | grep sync_errors`
2. Check error logs: `grep "ERROR" logs/atom.log | grep sync | tail -20`
3. Check Atom SaaS API: `curl -I https://api.atomsaas.com/health`

**Resolution**:
1. Identify error type from logs
2. If Atom SaaS API error, check status page
3. If rate limiting, reduce sync frequency
4. If authentication error, verify API credentials
5. Contact Atom SaaS support if API is down

**Verification**:
- Error rate < 10%
- Logs show successful sync operations
- No 500 errors from Atom SaaS

---

### Runbook: Unresolved Conflicts

**Alert**: `UnresolvedConflictsHigh` or `UnresolvedConflictsCritical`

**Severity**: Warning / Critical

**Impact**: Sync operations may be blocked

**Diagnosis**:
1. Check conflict count: `curl http://localhost:8000/api/admin/sync/conflicts`
2. Check conflict metrics: `curl http://localhost:8000/metrics/sync | grep conflicts`
3. Review conflict types and causes

**Resolution**:
1. List conflicts: `curl http://localhost:8000/api/admin/sync/conflicts`
2. Choose resolution strategy (local_wins, remote_wins, merge)
3. Resolve conflicts individually or in bulk
4. Trigger manual sync to verify resolution

**Verification**:
- `conflicts_unresolved` < 100
- Conflict list empty or manageable
- Sync continues without conflict errors

---

## Appendix

### Useful Commands

```bash
# Check all sync health
curl http://localhost:8000/health/sync | jq .

# Get all sync metrics
curl http://localhost:8000/metrics/sync

# Trigger manual sync
curl -X POST http://localhost:8000/api/admin/sync/trigger

# Get sync status
curl http://localhost:8000/api/admin/sync/status | jq .

# Get WebSocket status
curl http://localhost:8000/api/admin/sync/websocket/status | jq .

# List conflicts
curl http://localhost:8000/api/admin/sync/conflicts | jq .

# Get rating sync status
curl http://localhost:8000/api/admin/sync/ratings/status | jq .

# Get failed uploads
curl http://localhost:8000/api/admin/sync/ratings/failed-uploads | jq .

# Watch sync logs
tail -f logs/atom.log | grep sync

# Count skills in cache
sqlite3 atom_dev.db "SELECT COUNT(*) FROM community_skills;"

# Check sync state
sqlite3 atom_dev.db "SELECT * FROM sync_state ORDER BY last_sync DESC LIMIT 1;"
```

### Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables (API keys, sync interval) |
| `docker-compose.yml` | Service orchestration |
| `monitoring/alerts/prometheus-alerts.yml` | Alerting rules |
| `monitoring/grafana/sync-dashboard.json` | Grafana dashboard |

### Related Documentation

- [Atom SaaS API Documentation](https://docs.atomsaas.com/api)
- [Prometheus Alerting Guide](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)
- [Kubernetes Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

---

**Document Version**: 1.0
**Last Reviewed**: 2026-02-19
**Next Review**: 2026-03-19
