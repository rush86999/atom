# Atom SaaS Sync Deployment Guide

**Phase:** 61-atom-saas-marketplace-sync
**Last Updated:** 2026-02-19
**Purpose:** Production deployment guide for Atom SaaS marketplace synchronization

## Overview

Atom SaaS sync provides bidirectional synchronization between your Atom instance and the Atom SaaS marketplace, enabling agents to access 5,000+ community skills with real-time updates.

### Architecture

The sync system uses a hybrid approach for maximum reliability:

1. **Periodic Polling (Primary)**
   - Skills sync: Every 15 minutes (configurable)
   - Ratings sync: Every 30 minutes (configurable)
   - Categories sync: Every 15 minutes
   - Conflict resolution: Automatic (4 strategies available)

2. **WebSocket Real-Time Updates (Secondary)**
   - Real-time skill updates from Atom SaaS
   - Real-time rating updates
   - Automatic reconnection with exponential backoff
   - Fallback to polling after 3 consecutive failures

3. **Cache Management**
   - 24-hour TTL for cached skills/categories
   - Automatic expiration and cleanup
   - Conflict detection and resolution

### Components

- **SyncService**: Main sync orchestration (598 lines)
- **AtomSaaSClient**: HTTP API client for polling
- **AtomSaaSWebSocketClient**: WebSocket client for real-time updates
- **ConflictResolutionService**: Handles sync conflicts (595 lines)
- **AgentScheduler**: Background job scheduling (APScheduler)
- **RatingSyncService**: Bidirectional rating sync (462 lines)

## Environment Variables

### Required Configuration

```bash
# ==============================================================================
# ATOM SAAS API CONFIGURATION
# ==============================================================================

# Atom SaaS API Base URL
# Default: https://api.atomsaas.com
# Production: https://api.atomsaas.com
# Staging: https://staging-api.atomsaas.com
ATOM_SAAS_API_URL=https://api.atomsaas.com

# Atom SaaS API Token
# Get from: https://atomsaas.com/dashboard/settings/api-tokens
# Required: Yes
# Format: Bearer token (e.g., at_saas_xxxxx)
ATOM_SAAS_API_TOKEN=your_api_token_here

# ==============================================================================
# SYNC INTERVALS
# ==============================================================================

# Skill sync interval in minutes
# Default: 15
# Range: 5-60
# Purpose: How often to poll for skill/category updates
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15

# Rating sync interval in minutes
# Default: 30
# Range: 10-120
# Purpose: How often to upload local ratings to Atom SaaS
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=30

# ==============================================================================
# CONFLICT RESOLUTION
# ==============================================================================

# Conflict resolution strategy
# Options: remote_wins, local_wins, merge, manual
# Default: remote_wins
# remote_wins: Atom SaaS data overwrites local (recommended)
# local_wins: Local data overwrites Atom SaaS
# merge: Intelligent merge (fields-specific)
# manual: Log conflicts for manual resolution
ATOM_SAAS_CONFLICT_STRATEGY=remote_wins

# ==============================================================================
# WEBSOCKET CONFIGURATION
# ==============================================================================

# WebSocket URL for real-time updates
# Default: wss://api.atomsaas.com/ws
# Production: wss://api.atomsaas.com/ws
# Staging: wss://staging-api.atomsaas.com/ws
ATOM_SAAS_WS_URL=wss://api.atomsaas.com/ws

# WebSocket reconnection attempts
# Default: 10
# Range: 0-100
# Purpose: Max reconnection attempts before falling back to polling
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=10

# WebSocket heartbeat interval in seconds
# Default: 30
# Range: 10-120
# Purpose: Detect stale connections
ATOM_SAAS_WS_HEARTBEAT_INTERVAL=30

# ==============================================================================
# SCHEDULER CONFIGURATION
# ==============================================================================

# Enable background scheduler
# Default: false (for API-only replicas)
# Recommended: true (for single-instance deployments)
# Purpose: Run periodic sync jobs
ENABLE_SCHEDULER=true
```

### Example .env Configuration

```bash
# Production Example
ATOM_SAAS_API_URL=https://api.atomsaas.com
ATOM_SAAS_API_TOKEN=at_saas_prod_xxxxx1234567890
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=30
ATOM_SAAS_CONFLICT_STRATEGY=remote_wins
ATOM_SAAS_WS_URL=wss://api.atomsaas.com/ws
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=10
ATOM_SAAS_WS_HEARTBEAT_INTERVAL=30
ENABLE_SCHEDULER=true

# Staging Example
ATOM_SAAS_API_URL=https://staging-api.atomsaas.com
ATOM_SAAS_API_TOKEN=at_saas_stg_xxxxx1234567890
ATOM_SAAS_SYNC_INTERVAL_MINUTES=10
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=20
ATOM_SAAS_CONFLICT_STRATEGY=remote_wins
ATOM_SAAS_WS_URL=wss://staging-api.atomsaas.com/ws
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=5
ATOM_SAAS_WS_HEARTBEAT_INTERVAL=30
ENABLE_SCHEDULER=true
```

## Database Migrations

### Required Migrations

The Atom SaaS sync system requires the following database models:

1. **SyncState** - Track sync status and metrics
2. **WebSocketState** - Track WebSocket connection status
3. **ConflictLog** - Log sync conflicts for manual resolution
4. **FailedRatingUpload** - Track failed rating uploads
5. **SkillCache** - Cache synced skills from Atom SaaS
6. **CategoryCache** - Cache synced categories from Atom SaaS
7. **SkillRating** - Extended with sync tracking fields

### Applying Migrations

```bash
# Navigate to backend directory
cd backend

# Check current migration status
alembic current

# Apply all pending migrations
alembic upgrade head

# Verify migrations
alembic history | grep -E "sync|skill_cache|rating_sync|conflict"

# Expected output:
# 2026-02-19-add-atom-saas-sync-models.py
# 2026-02-19-add-rating-sync-models.py
# 2026-02-19-add-conflict-resolution-models.py
```

### Migration Rollback

If migration fails or needs rollback:

```bash
# Rollback one step
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Re-apply migration
alembic upgrade head
```

### Manual Table Verification

```bash
# Connect to database
sqlite3 data/atom.db  # or psql for PostgreSQL

# Verify tables exist
.tables | grep -E "sync|skill_cache|rating|conflict"

# Expected output:
# conflict_log
# failed_rating_upload
# skill_cache
# category_cache
# sync_state
# websocket_state
# skill_rating
```

## Startup Verification

### 1. Check Environment Variables

```bash
# Verify ATOM_SAAS_API_TOKEN is set
echo $ATOM_SAAS_API_TOKEN

# Expected: at_saas_xxxxx (not empty)

# Check all Atom SaaS variables
env | grep ATOM_SAAS

# Expected output:
# ATOM_SAAS_API_URL=https://api.atomsaas.com
# ATOM_SAAS_API_TOKEN=at_saas_xxxxx
# ATOM_SAAS_SYNC_INTERVAL_MINUTES=15
# ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=30
# ATOM_SAAS_CONFLICT_STRATEGY=remote_wins
# ATOM_SAAS_WS_URL=wss://api.atomsaas.com/ws
```

### 2. Start Application

```bash
# Start Atom server
cd backend
python -m uvicorn main_api_app:app --reload --port 8000

# Or using Docker
docker-compose up -d
```

### 3. Verify Startup Logs

**Successful startup logs:**

```
INFO:ATOM_SERVER:Configuration loaded from /path/to/.env
INFO:ATOM_SERVER:ATOM Platform Starting (Hybrid Mode)
INFO:ATOM_SERVER:Server will start on 0.0.0.0:8000
INFO:ATOM_SERVER:Environment: production
INFO:core.database:Initializing database tables...
INFO:core.database:✓ Database tables created: [...]
INFO:core.admin_bootstrap:Bootstrapping admin user...
INFO:core.admin_bootstrap:✓ Admin user ready
INFO:core.scheduler:AgentScheduler started.
INFO:core.scheduler:Initialized skill sync with 15 minute interval
INFO:core.scheduler:Scheduled skill sync job skill-sync-atom-saas every 15 minutes
INFO:core.scheduler:Initialized rating sync with 30 minute interval
INFO:core.scheduler:Scheduled rating sync job rating-sync-atom-saas every 30 minutes
INFO:ATOM_SERVER:✓ Agent Scheduler running
INFO:ATOM_SERVER:✓ Rating Sync scheduled
INFO:ATOM_SERVER:✓ Skill Sync scheduled
INFO:ATOM_SERVER:✓ Server Ready
```

**Warning signs:**

```
# Missing API token
WARNING:core.scheduler:Failed to initialize skill sync: ATOM_SAAS_API_TOKEN not set

# Scheduler disabled
INFO:ATOM_SERVER:Skipping Scheduler startup (ENABLE_SCHEDULER=false)

# Invalid API URL
WARNING:core.scheduler:Failed to initialize skill sync: Invalid ATOM_SAAS_API_URL
```

### 4. Verify APScheduler Jobs

```bash
# Check admin API for scheduled jobs
curl http://localhost:8000/api/admin/sync/jobs

# Expected output:
{
  "success": true,
  "jobs": [
    {
      "id": "skill-sync-atom-saas",
      "name": "Skill Sync with Atom SaaS",
      "next_run_time": "2026-02-19T14:30:00Z",
      "trigger": "interval",
      "minutes": 15
    },
    {
      "id": "rating-sync-atom-saas",
      "name": "Rating Sync with Atom SaaS",
      "next_run_time": "2026-02-19T14:45:00Z",
      "trigger": "interval",
      "minutes": 30
    }
  ]
}
```

### 5. Check Sync Status

```bash
# Check current sync status
curl http://localhost:8000/api/admin/sync/status

# Expected output:
{
  "success": true,
  "sync": {
    "status": "idle",
    "last_sync_at": "2026-02-19T14:15:00Z",
    "last_successful_sync_at": "2026-02-19T14:15:00Z",
    "total_syncs": 42,
    "successful_syncs": 41,
    "failed_syncs": 1
  },
  "websocket": {
    "connected": true,
    "last_connected_at": "2026-02-19T14:10:00Z",
    "last_message_at": "2026-02-19T14:18:30Z",
    "fallback_to_polling": false,
    "reconnect_attempts": 0
  },
  "cache": {
    "skills_count": 1250,
    "categories_count": 24
  }
}
```

## Health Check Configuration

### Kubernetes Probes

### Liveness Probe

```yaml
# kubernetes/deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

**Endpoint behavior:**
- Returns 200 if server is running
- Returns 503 if server is unresponsive
- No database checks (fast response)

### Readiness Probe

```yaml
# kubernetes/deployment.yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

**Endpoint behavior:**
- Returns 200 if server is ready (database connected, jobs scheduled)
- Returns 503 if database is down or not migrated
- Checks disk space (1GB threshold)

### Sync-Specific Health Check

```yaml
# Optional: Custom probe for sync health
livenessProbe:
  httpGet:
    path: /health/sync
    port: 8000
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 5
```

**Endpoint behavior:**
- Returns 200 if sync is healthy (last sync < 30 min ago)
- Returns 503 if sync is stale or failed
- Checks WebSocket connection status

### Manual Health Checks

```bash
# Liveness check
curl http://localhost:8000/health/live

# Expected output:
{"status": "healthy", "timestamp": "2026-02-19T14:20:00Z"}

# Readiness check
curl http://localhost:8000/health/ready

# Expected output:
{
  "status": "ready",
  "database": "connected",
  "disk_space_gb": 45.2,
  "migrations_applied": true
}

# Sync health check
curl http://localhost:8000/health/sync

# Expected output:
{
  "status": "healthy",
  "sync": {
    "last_sync_at": "2026-02-19T14:15:00Z",
    "minutes_since_last_sync": 5
  },
  "websocket": {
    "connected": true,
    "last_message_at": "2026-02-19T14:18:30Z"
  }
}
```

## Prometheus Metrics

### Metrics Endpoint

```bash
# Scrape metrics
curl http://localhost:8000/metrics/sync

# Expected output:
# HELP atom_saas_sync_duration_seconds Sync duration in seconds
# TYPE atom_saas_sync_duration_seconds histogram
atom_saas_sync_duration_seconds_bucket{le="0.5"} 15
atom_saas_sync_duration_seconds_bucket{le="1.0"} 42
atom_saas_sync_duration_seconds_bucket{le="5.0"} 89
atom_saas_sync_duration_seconds_bucket{le="+Inf"} 90
atom_saas_sync_duration_seconds_sum 234.5
atom_saas_sync_duration_seconds_count 90

# HELP atom_saas_sync_success_total Total successful syncs
# TYPE atom_saas_sync_success_total counter
atom_saas_sync_success_total{type="skill"} 85
atom_saas_sync_success_total{type="rating"} 78

# HELP atom_saas_sync_errors_total Total sync errors
# TYPE atom_saas_sync_errors_total counter
atom_saas_sync_errors_total{type="skill",error="api_error"} 2
atom_saas_sync_errors_total{type="rating",error="timeout"} 1

# HELP atom_saas_cache_size Current cache size
# TYPE atom_saas_cache_size gauge
atom_saas_cache_size{type="skills"} 1250
atom_saas_cache_size{type="categories"} 24

# HELP atom_saas_websocket_connected WebSocket connection status
# TYPE atom_saas_websocket_connected gauge
atom_saas_websocket_connected 1

# HELP atom_saas_conflicts_detected_total Total conflicts detected
# TYPE atom_saas_conflicts_detected_total counter
atom_saas_conflicts_detected_total 15

# HELP atom_saas_conflicts_resolved_total Total conflicts auto-resolved
# TYPE atom_saas_conflicts_resolved_total counter
atom_saas_conflicts_resolved_total 12
```

### Prometheus Configuration

```yaml
# prometheus/prometheus.yml
scrape_configs:
  - job_name: 'atom-saas-sync'
    scrape_interval: 30s
    static_configs:
      - targets: ['atom-api:8000']
    metrics_path: '/metrics/sync'
```

### Key Metrics

| Metric Name | Type | Description | Alert Threshold |
|-------------|------|-------------|-----------------|
| `atom_saas_sync_duration_seconds` | Histogram | Sync duration | p95 > 60s |
| `atom_saas_sync_success_total` | Counter | Successful syncs | Rate < 0.9/hour |
| `atom_saas_sync_errors_total` | Counter | Sync errors | Rate > 0.1/hour |
| `atom_saas_cache_size` | Gauge | Cache entries | Skills < 1000 |
| `atom_saas_websocket_connected` | Gauge | WebSocket status | 0 for > 5min |
| `atom_saas_conflicts_detected_total` | Counter | Conflicts detected | Rate > 5/hour |

## Grafana Dashboard

### Dashboard Import

1. Navigate to Grafana → Dashboards → Import
2. Upload `monitoring/grafana/sync-dashboard.json`
3. Select Prometheus data source
4. Import dashboard

### Dashboard Panels

**Overview Row:**
- Sync Success Rate (last 24h)
- Average Sync Duration
- Cache Size (Skills, Categories)
- WebSocket Connection Status

**Sync Metrics Row:**
- Skill Sync Success Rate (gauge)
- Rating Sync Success Rate (gauge)
- Sync Duration Histogram (heatmap)
- Sync Errors by Type (bar chart)

**Cache Metrics Row:**
- Skills Cached Over Time (time series)
- Categories Cached Over Time (time series)
- Cache Hit Rate (gauge)

**WebSocket Row:**
- WebSocket Connection Status (state timeline)
- Reconnection Attempts (gauge)
- Messages Received (counter)
- Fallback Mode Duration (gauge)

**Conflict Resolution Row:**
- Conflicts Detected (counter)
- Conflicts Auto-Resolved (gauge)
- Conflicts Manual Review (gauge)
- Conflict Types (pie chart)

### Alerting

See `monitoring/alerts/prometheus-alerts.yml` for alert rules.

**Critical Alerts:**
- **SyncStale**: No successful sync in 60 minutes
- **WebSocketDisconnected**: WebSocket down for 10+ minutes
- **HighErrorRate**: Sync error rate > 10%

**Warning Alerts:**
- **SyncSlow**: Sync duration p95 > 60 seconds
- **CacheLow**: Skills cached < 1000
- **ConflictHigh**: Conflict detection rate > 5/hour

## Troubleshooting

### Sync Not Running

**Symptoms:**
- No sync jobs scheduled
- Startup logs missing "Initialized skill sync"
- Cache count is 0

**Diagnosis:**
```bash
# Check scheduler enabled
env | grep ENABLE_SCHEDULER
# Expected: ENABLE_SCHEDULER=true

# Check API token
env | grep ATOM_SAAS_API_TOKEN
# Expected: ATOM_SAAS_API_TOKEN=at_saas_xxxxx

# Check startup logs
docker-compose logs atom-api | grep -E "skill sync|scheduler"
# Expected: "✓ Skill Sync scheduled"
```

**Solutions:**
1. Set `ENABLE_SCHEDULER=true` in environment
2. Set `ATOM_SAAS_API_TOKEN` with valid token
3. Restart application
4. Check database migrations applied

### High Error Rate

**Symptoms:**
- Sync error rate > 10%
- Failed syncs increasing
- API errors in logs

**Diagnosis:**
```bash
# Check API URL accessibility
curl -I $ATOM_SAAS_API_URL/health
# Expected: HTTP 200

# Check API token validity
curl -H "Authorization: Bearer $ATOM_SAAS_API_TOKEN" $ATOM_SAAS_API_URL/skills
# Expected: HTTP 200 with skills array

# Check error logs
docker-compose logs atom-api | grep "sync.*error"
# Look for: timeout, connection refused, 401 unauthorized
```

**Solutions:**
1. Verify `ATOM_SAAS_API_URL` is correct (check for typos)
2. Verify `ATOM_SAAS_API_TOKEN` is valid (regenerate if needed)
3. Check firewall rules (allow outbound HTTPS)
4. Check network connectivity (DNS resolution)
5. Contact Atom SaaS support if API is down

### WebSocket Disconnects

**Symptoms:**
- WebSocket status shows "connected": false
- Reconnection attempts increasing
- Fallback to polling mode

**Diagnosis:**
```bash
# Check WebSocket URL
echo $ATOM_SAAS_WS_URL
# Expected: wss://api.atomsaas.com/ws

# Check WebSocket connection
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  $ATOM_SAAS_WS_URL
# Expected: HTTP 101 Switching Protocols

# Check firewall rules
sudo iptables -L | grep -E "websocket|9001"
# Ensure outbound TCP 9001 is allowed
```

**Solutions:**
1. Verify `ATOM_SAAS_WS_URL` is correct (wss:// for production)
2. Check firewall allows outbound connections to WebSocket port
3. Check proxy settings (WebSocket may not work through HTTP proxy)
4. Increase `ATOM_SAAS_WS_RECONNECT_ATTEMPTS` for unstable networks
5. System will fallback to polling automatically

### Conflicts: Review Strategy Setting

**Symptoms:**
- High conflict rate (> 5/hour)
- Many manual conflicts logged
- Data inconsistency

**Diagnosis:**
```bash
# Check conflict strategy
echo $ATOM_SAAS_CONFLICT_STRATEGY
# Expected: remote_wins (recommended)

# Check conflict logs
curl http://localhost:8000/api/admin/sync/conflicts
# Look for patterns in conflict types

# Check conflict metrics
curl http://localhost:8000/metrics/sync | grep conflict
# atom_saas_conflicts_detected_total
```

**Solutions:**
1. Change `ATOM_SAAS_CONFLICT_STRATEGY` to `remote_wins` (recommended)
2. Resolve manual conflicts via admin API: `POST /api/admin/sync/resolve`
3. Check for concurrent edits (multiple users modifying same skills)
4. Review conflict logs to identify root cause

### Cache Not Updating

**Symptoms:**
- Cache count not increasing
- Stale skill data
- Skills synced: 0

**Diagnosis:**
```bash
# Check cache table
sqlite3 data/atom.db "SELECT COUNT(*) FROM skill_cache;"
# Expected: > 0

# Check last sync time
curl http://localhost:8000/api/admin/sync/status | jq .sync.last_sync_at
# Expected: Recent timestamp (< 30 min ago)

# Check sync logs
docker-compose logs atom-api | grep "Sync completed"
# Look for: "Sync completed: X skills, Y categories"
```

**Solutions:**
1. Trigger manual sync: `POST /api/admin/sync/skills`
2. Check database permissions (write access to cache tables)
3. Check disk space (> 1GB required)
4. Restart application to clear any stuck sync state

### Database Migration Issues

**Symptoms:**
- "Table not found" errors
- Migration failed
- Application crash on startup

**Diagnosis:**
```bash
# Check current migration
alembic current
# Expected: Latest revision ID

# Check migration history
alembic history | tail -5
# Look for sync-related migrations

# Check database tables
sqlite3 data/atom.db ".tables" | grep -E "sync|skill_cache|rating|conflict"
# Expected: 6 tables (conflict_log, failed_rating_upload, skill_cache, category_cache, sync_state, websocket_state)
```

**Solutions:**
1. Apply pending migrations: `alembic upgrade head`
2. If migration failed, rollback: `alembic downgrade -1`
3. Check database user permissions (CREATE TABLE, ALTER TABLE)
4. For SQLite, ensure write permissions on .db file
5. For PostgreSQL, ensure schema exists and is accessible

## Production Checklist

### Pre-Deployment

- [ ] **Environment Variables**
  - [ ] `ATOM_SAAS_API_TOKEN` set with valid production token
  - [ ] `ATOM_SAAS_API_URL` points to production endpoint (https://api.atomsaas.com)
  - [ ] `ATOM_SAAS_SYNC_INTERVAL_MINUTES` configured (recommended: 15)
  - [ ] `ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES` configured (recommended: 30)
  - [ ] `ATOM_SAAS_CONFLICT_STRATEGY` set to `remote_wins`
  - [ ] `ATOM_SAAS_WS_URL` points to production WebSocket (wss://api.atomsaas.com/ws)
  - [ ] `ENABLE_SCHEDULER=true` (for single-instance deployments)

- [ ] **Database Migrations**
  - [ ] All migrations applied (`alembic upgrade head`)
  - [ ] Migration verification: 6 tables created
  - [ ] Database user has CREATE/ALTER permissions
  - [ ] Backup created before deployment

- [ ] **Monitoring Configuration**
  - [ ] Prometheus scraping configured for `/metrics/sync`
  - [ ] Grafana dashboard imported from `monitoring/grafana/sync-dashboard.json`
  - [ ] Alerting rules loaded from `monitoring/alerts/prometheus-alerts.yml`
  - [ ] Alert notifications configured (Slack, PagerDuty, etc.)

### Post-Deployment

- [ ] **Startup Verification**
  - [ ] Check logs for "Initialized skill sync with X minute interval"
  - [ ] Check logs for "Initialized rating sync with X minute interval"
  - [ ] Verify no startup errors or warnings related to sync
  - [ ] Check APScheduler jobs registered (2 jobs: skill-sync, rating-sync)

- [ ] **Health Checks**
  - [ ] Liveness probe: `GET /health/live` returns 200
  - [ ] Readiness probe: `GET /health/ready` returns 200
  - [ ] Sync health: `GET /health/sync` returns 200
  - [ ] Kubernetes/ECS health checks passing

- [ ] **Manual Sync Verification**
  - [ ] Trigger manual skill sync: `POST /api/admin/sync/skills`
  - [ ] Verify skills synced: Check `skills_synced` count > 0
  - [ ] Trigger manual rating sync: `POST /api/admin/sync/ratings`
  - [ ] Verify ratings uploaded: Check `uploaded` count > 0

- [ ] **WebSocket Verification**
  - [ ] Check WebSocket status: `GET /api/admin/sync/status` → `websocket.connected: true`
  - [ ] Verify reconnection attempts = 0 (no connection issues)
  - [ ] Check fallback_to_polling = false (WebSocket working)

- [ ] **Cache Verification**
  - [ ] Check cache status: `GET /api/admin/sync/status` → `cache.skills_count > 1000`
  - [ ] Check cache status: `GET /api/admin/sync/status` → `cache.categories_count > 20`
  - [ ] Verify cache TTL working (24-hour expiry)

- [ ] **Metrics Verification**
  - [ ] Prometheus metrics endpoint accessible: `GET /metrics/sync`
  - [ ] Grafana dashboard showing data
  - [ ] No critical alerts firing

### Ongoing Operations

- [ ] **Daily Monitoring**
  - [ ] Check sync success rate > 95%
  - [ ] Check sync duration p95 < 60s
  - [ ] Check WebSocket uptime > 99%
  - [ ] Review conflict logs for manual resolution

- [ ] **Weekly Maintenance**
  - [ ] Review and resolve manual conflicts
  - [ ] Check cache size and cleanup
  - [ ] Review error logs for patterns
  - [ ] Verify API token not expiring soon

- [ ] **Monthly Review**
  - [ ] Sync interval optimization (adjust based on traffic)
  - [ ] Conflict strategy review (manual vs auto)
  - [ ] Cache performance tuning
  - [ ] Documentation updates

## Security Considerations

### API Token Security

- Store `ATOM_SAAS_API_TOKEN` in secure vault (HashiCorp Vault, AWS Secrets Manager)
- Rotate tokens every 90 days
- Use separate tokens for staging/production
- Never commit tokens to git
- Use read-only tokens when possible (only skill sync, no rating upload)

### Network Security

- Use HTTPS for API URLs (TLS 1.2+)
- Use WSS for WebSocket URLs (secure WebSocket)
- Restrict outbound access to Atom SaaS IPs (if possible)
- Enable VPC endpoints for cloud deployments

### Data Privacy

- Synced skills may contain user-generated content
- Cache data encrypted at rest (database encryption)
- Cache data encrypted in transit (TLS)
- Implement data retention policies (24-hour cache TTL)

### Rate Limiting

- Atom SaaS API may enforce rate limits (1000 req/hour typical)
- Implement backoff logic (exponential backoff included)
- Monitor rate limit headers in API responses
- Alert on high rate limit usage

### Audit Trail

- All sync operations logged to database
- Conflict resolution logged with timestamps
- Failed uploads tracked with retry counts
- Admin operations require AUTONOMOUS governance

## Performance Tuning

### Sync Interval Optimization

**Low Traffic (< 1000 users):**
- Skill sync: 15 minutes (default)
- Rating sync: 30 minutes (default)

**Medium Traffic (1000-10000 users):**
- Skill sync: 10 minutes
- Rating sync: 20 minutes

**High Traffic (> 10000 users):**
- Skill sync: 5 minutes
- Rating sync: 15 minutes

### Cache Sizing

**Expected cache sizes:**
- Skills: 1000-5000 entries
- Categories: 20-50 entries
- Memory: ~50MB for 5000 skills

**Cache cleanup:**
- Automatic expiration after 24 hours
- Manual cleanup: `DELETE /api/admin/sync/cache/expired`
- Scheduled cleanup: Runs daily at midnight

### Concurrency Control

- Skill sync: Single-threaded (async await)
- Rating sync: Batch upload (max 10 concurrent)
- WebSocket: Single connection (async message handler)
- Database: Connection pooling (20 max connections)

### Database Indexing

```sql
-- Required indexes for performance
CREATE INDEX idx_skill_cache_skill_id ON skill_cache(skill_id);
CREATE INDEX idx_skill_cache_expires_at ON skill_cache(expires_at);
CREATE INDEX idx_category_cache_name ON category_cache(category_name);
CREATE INDEX idx_sync_state_device_id ON sync_state(device_id);
CREATE INDEX idx_conflict_log_skill_id ON conflict_log(skill_id);
CREATE INDEX idx_conflict_log_resolved ON conflict_log(resolved);
```

## Rollback Procedures

### Application Rollback

```bash
# Docker deployment
docker-compose down
docker-compose pull atom-api:previous-version
docker-compose up -d

# Kubernetes deployment
kubectl rollout undo deployment/atom-api

# Verify rollback
kubectl rollout status deployment/atom-api
```

### Database Rollback

```bash
# Rollback last migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Re-apply migration after fix
alembic upgrade head
```

### Emergency Stop

```bash
# Disable sync jobs (keep API running)
export ENABLE_SCHEDULER=false
docker-compose restart atom-api

# Or delete scheduled jobs via API
curl -X DELETE http://localhost:8000/api/admin/sync/jobs
```

## Support and Resources

### Documentation

- **Architecture**: `docs/ATOM_SAAS_SYNC_ARCHITECTURE.md`
- **API Reference**: `docs/API_DOCUMENTATION.md#sync-endpoints`
- **Monitoring**: `docs/MONITORING_SETUP.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

### Support Contacts

- **Atom SaaS Support**: support@atomsaas.com
- **Technical Issues**: tech-support@atomsaas.com
- **API Status**: https://status.atomsaas.com
- **Documentation**: https://docs.atomsaas.com

### Community Resources

- **GitHub Issues**: https://github.com/atom/atom/issues
- **Discord Community**: https://discord.gg/atom
- **Stack Overflow**: Tag questions with `atom-saas-sync`

---

**Document Version:** 1.0
**Last Updated:** 2026-02-19
**Maintained By:** Atom Platform Team
