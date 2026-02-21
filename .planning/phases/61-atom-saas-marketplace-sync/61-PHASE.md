# Phase 61: Atom SaaS Marketplace Sync

**Purpose**: Implement bidirectional sync between local Atom marketplace and Atom SaaS cloud platform

**Status**: PLANNING

**Last Updated**: 2026-02-19

---

## Overview

This phase implements the missing piece from Phase 60's Skill Marketplace: **bidirectional synchronization with Atom SaaS**. Phase 60 built a local PostgreSQL-based marketplace with Atom SaaS sync architecture as TODOs. Phase 61 completes that vision.

### What This Phase Builds

1. **Background Sync Service** (Plan 01) - Periodic polling to pull skills/categories from Atom SaaS
2. **Bidirectional Rating Sync** (Plan 02) - Push local ratings to Atom SaaS
3. **WebSocket Real-time Updates** (Plan 03) - Instant updates via WebSocket connection
4. **Conflict Resolution** (Plan 04) - Merge strategies when skills exist locally and remotely
5. **Admin API & Monitoring** (Plan 05) - Health checks, metrics, dashboards, alerting

### Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Local Atom                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ SkillCache   │  │ CategoryCache│  │ SkillRating  │         │
│  │ (PostgreSQL) │  │ (PostgreSQL) │  │ (PostgreSQL) │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                  │                  │
│         └─────────────────┴──────────────────┘                  │
│                           ▼                                      │
│                  ┌─────────────┐                                 │
│                  │ SyncService │ ◄─────── Scheduler (15min)     │
│                  └──────┬──────┘                                 │
│                         │                                        │
│            ┌────────────┴────────────┐                          │
│            ▼                         ▼                          │
│    ┌───────────────┐        ┌──────────────┐                    │
│    │ Polling Sync  │        │  WebSocket   │                    │
│    │  (HTTP API)   │        │ (Real-time)  │                    │
│    └───────┬───────┘        └──────┬───────┘                    │
└────────────┼───────────────────────┼────────────────────────────┘
             │                       │
             └───────────┬───────────┘
                         ▼
            ┌─────────────────────────┐
            │     Atom SaaS API        │
            │  (Cloud Marketplace)     │
            └─────────────────────────┘
```

---

## Goals

### Primary Goal
Implement production-ready bidirectional sync between local Atom marketplace and Atom SaaS cloud platform with <15-minute data freshness and 99.9% uptime.

### Success Criteria

1. **Background Sync** (Plan 01)
   - [x] SyncService fetches skills/categories from Atom SaaS every 15 minutes
   - [x] SkillCache and CategoryCache populated automatically
   - [x] SyncState model tracks sync status
   - [x] Error handling with exponential backoff
   - [x] Admin endpoint for manual sync trigger

2. **Bidirectional Rating Sync** (Plan 02)
   - [x] Local ratings pushed to Atom SaaS every 30 minutes
   - [x] Conflict resolution based on timestamp (newest wins)
   - [x] Batch upload for efficiency (100 ratings per request)
   - [x] Dead letter queue for failed uploads
   - [x] Admin endpoint for manual rating sync

3. **WebSocket Real-time Updates** (Plan 03)
   - [x] WebSocket connection to Atom SaaS for instant updates
   - [x] Message handlers for skill_update, category_update, rating_update, skill_delete
   - [x] Automatic reconnection with exponential backoff
   - [x] Heartbeat every 30 seconds to detect stale connections
   - [x] Fallback to polling when WebSocket unavailable

4. **Conflict Resolution** (Plan 04)
   - [x] Four merge strategies: remote_wins, local_wins, merge, manual
   - [x] Automatic conflict detection during sync
   - [x] ConflictLog model tracks all conflicts
   - [x] Admin workflow for manual conflict resolution
   - [x] Integration with skill and rating sync

5. **Admin API & Monitoring** (Plan 05)
   - [x] 15+ admin endpoints for sync management
   - [x] Health check endpoint for Kubernetes probes
   - [x] Prometheus metrics for sync operations
   - [x] Grafana dashboard for visualization
   - [x] Alerting rules for critical failures
   - [x] Comprehensive troubleshooting documentation

---

## Wave Structure

### Wave 1: Core Sync Infrastructure (Plans 01-02)
**Duration**: ~2 hours
**Plans**: Background Sync Service, Bidirectional Rating Sync
**Dependencies**: Phase 60 (AtomSaaSClient, marketplace models)

### Wave 2: Real-time & Conflict Resolution (Plans 03-04)
**Duration**: ~2.5 hours
**Plans**: WebSocket Updates, Conflict Resolution
**Dependencies**: Wave 1 (SyncService, RatingSyncService)

### Wave 3: Operations & Monitoring (Plan 05)
**Duration**: ~1.5 hours
**Plans**: Admin API, Health Checks, Metrics, Dashboards
**Dependencies**: Wave 1 + Wave 2 (all sync services)

**Total Estimated Duration**: ~6 hours (5 plans, 30 tasks)

---

## Dependencies

### Required Phases
- ✅ Phase 14: Community Skills Integration (Skill models, registry)
- ✅ Phase 35: Python Package Support (Package governance)
- ✅ Phase 36: npm Package Support (npm governance)
- ✅ Phase 60: Advanced Skill Execution (Marketplace, AtomSaaSClient, cache models)

### External Dependencies
- Atom SaaS API must be accessible (http://localhost:5058/api or production URL)
- Atom SaaS WebSocket endpoint must be available
- API token for authentication (ATOM_SAAS_API_TOKEN)

### Libraries to Install
- `apscheduler` - Background job scheduling
- `websockets` - WebSocket client
- `prometheus-client` - Metrics exposure (if not already installed)

---

## Key Decisions

### Architecture
- **Hybrid approach**: Polling + WebSocket (not WebSocket-only)
- **Rationale**: Resilient fallback if WebSocket fails, simpler implementation

### Sync Intervals
- **Skills**: 15 minutes (balance freshness vs API load)
- **Ratings**: 30 minutes (ratings change less frequently)
- **WebSocket heartbeat**: 30 seconds (detect stale connections quickly)

### Conflict Resolution
- **Default strategy**: remote_wins (Atom SaaS is source of truth)
- **Configurable**: Via ATOM_SAAS_CONFLICT_STRATEGY environment variable

### Batch Sizes
- **Skill sync**: 100 skills per API call
- **Rating sync**: 100 ratings per API call
- **Rationale**: Optimal for API performance vs memory

---

## Technical Stack

### Backend Services
- `SyncService` - Background sync orchestration
- `RatingSyncService` - Bidirectional rating sync
- `AtomSaaSWebSocketClient` - WebSocket connection manager
- `ConflictResolutionService` - Merge strategies and conflict tracking
- `SyncHealthMonitor` - Health checks and metrics

### Database Models
- `SyncState` - Track sync status (single-row table)
- `SkillCache` - Cached skills from Atom SaaS (from Phase 60)
- `CategoryCache` - Cached categories from Atom SaaS (from Phase 60)
- `SkillRating` - Extended with sync tracking fields (synced_at, synced_to_saas)
- `FailedRatingUpload` - Dead letter queue for failed uploads
- `ConflictLog` - Track conflicts and resolutions

### API Endpoints
- **Background Sync**: 3 endpoints (trigger, status, config)
- **Rating Sync**: 4 endpoints (trigger, status, failed-uploads, retry)
- **WebSocket**: 4 endpoints (status, reconnect, disable, enable)
- **Conflicts**: 4 endpoints (list, details, resolve, bulk-resolve)
- **Health Check**: 1 endpoint (/health/sync)
- **Metrics**: 1 endpoint (/metrics/sync)

### Monitoring
- **Health Check**: HTTP 200/503 based on sync status
- **Prometheus Metrics**: 12 metrics (duration, success rate, error rate, cache size, etc.)
- **Grafana Dashboard**: 12 panels (sync status, duration, errors, WebSocket, conflicts)
- **Alerting**: 6 rules (SyncStale, SyncUnhealthy, WebSocketDisconnected, etc.)

---

## Testing Strategy

### Unit Tests
- SyncService methods (batch fetching, caching, pagination)
- RatingSyncService methods (batch upload, conflict resolution)
- WebSocket connection management (connect, disconnect, heartbeat, reconnect)
- Conflict resolution strategies (remote_wins, local_wins, merge, manual)

### Integration Tests
- End-to-end sync flow (fetch → cache → update SyncState)
- WebSocket message handling (skill_update, category_update, skill_delete)
- Admin API endpoints (trigger sync, get status, resolve conflicts)
- Health check endpoint (healthy, degraded, unhealthy states)

### Performance Tests
- Sync time vs skill count (100, 1000, 10000 skills)
- WebSocket message throughput (messages per second)
- Admin endpoint latency (P50, P95, P99)
- Health check response time (<50ms target)

### Test Coverage Target
- **Overall**: 85%+ coverage
- **Critical paths**: 95%+ coverage (sync flow, WebSocket, conflict resolution)

---

## Security Considerations

### Authentication
- Admin endpoints: AUTONOMOUS maturity required
- Health check: No authentication (public for Kubernetes)
- Metrics endpoint: No authentication (public for Prometheus)
- Atom SaaS API: Bearer token authentication

### Governance
- All admin operations require AUTONOMOUS maturity
- Audit trail logging for all manual actions
- Input validation on all parameters

### Rate Limiting
- Admin endpoints: 100 requests/minute per user
- WebSocket messages: 100 messages/second
- API calls to Atom SaaS: Respect rate limits, backoff on 429

### Data Privacy
- API tokens never logged
- User data validated before syncing
- Skill code scanned for security issues before caching

---

## Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Sync duration (1000 skills) | <2 minutes | Acceptable wait time for manual sync |
| Sync duration (10000 skills) | <15 minutes | Must complete within sync interval |
| WebSocket message processing | <100ms | Near-instant updates |
| Health check response time | <50ms P95 | Fast Kubernetes probes |
| Admin endpoint response time | <200ms P95 | Good UX for admins |
| WebSocket reconnection time | <16 seconds | Max backoff delay |
| Rating sync duration (1000 ratings) | <30 seconds | Complete within rating interval |
| Cache hit rate | >90% | Reduce API load |
| WebSocket uptime | >99% | Minimize polling fallback |

---

## Rollout Plan

### Phase 1: Background Sync (Plans 01-02)
- Deploy polling-based sync first
- Verify skills/categories syncing correctly
- Monitor for 1 week before adding WebSocket

### Phase 2: Add WebSocket (Plan 03)
- Enable WebSocket connection
- Verify real-time updates working
- Test fallback to polling

### Phase 3: Conflict Resolution (Plan 04)
- Enable automatic conflict resolution
- Monitor ConflictLog for manual resolution needs
- Fine-tune merge strategies

### Phase 4: Monitoring & Alerting (Plan 05)
- Deploy admin API and health checks
- Configure Prometheus scraping
- Import Grafana dashboard
- Enable alerting rules

### Phase 5: Production Verification
- Monitor for 2 weeks
- Tune sync intervals based on load
- Adjust alert thresholds
- Document any issues

---

## Documentation

### User Documentation
- `ATOM_SAAS_SYNC_GUIDE.md` - How sync works, how to use it
- `ADMIN_API.md` - All admin endpoints with examples
- `TROUBLEUBLESHOOTING.md` - Common issues and resolutions

### Technical Documentation
- `SYNC_ARCHITECTURE.md` - Detailed architecture diagrams
- `WEBSOCKET_PROTOCOL.md` - WebSocket message format
- `CONFLICT_RESOLUTION.md` - Merge strategies and workflows

### Operational Documentation
- `HEALTH_CHECKS.md` - Health check logic and thresholds
- `METRICS_REFERENCE.md` - All Prometheus metrics
- `GRAFANA_SETUP.md` - Dashboard import instructions
- `ALERTING_GUIDE.md` - Alert rules and escalation

---

## Success Metrics

### Functional Metrics
- ✅ Background sync runs every 15 minutes
- ✅ WebSocket receives real-time updates
- ✅ Bidirectional rating sync working
- ✅ Conflicts detected and resolved automatically
- ✅ Admin API functional with 15+ endpoints
- ✅ Health checks passing
- ✅ Metrics exposed to Prometheus

### Operational Metrics
- ✅ 99.9% sync uptime (max 43 minutes downtime/month)
- ✅ <1% sync error rate
- ✅ <5 second reconnection time for WebSocket
- ✅ 100% audit trail coverage
- ✅ 0 security vulnerabilities
- ✅ 85%+ test coverage

### Business Metrics
- ✅ Marketplace always fresh (<15 minutes stale)
- ✅ Ratings synchronized across all instances
- ✅ Zero data loss during sync
- ✅ Admin productivity increased (self-service sync management)

---

## Risks & Mitigations

### Risk 1: Atom SaaS API Unavailable
**Impact**: High - Sync fails, marketplace becomes stale
**Mitigation**: Fallback to local-only mode, alert ops team

### Risk 2: WebSocket Connection Unstable
**Impact**: Medium - Frequent reconnections, increased polling
**Mitigation**: Exponential backoff, polling fallback, alert on disconnect

### Risk 3: Rate Limiting by Atom SaaS
**Impact**: Medium - Sync throttled, delayed updates
**Mitigation**: Respect Retry-After headers, increase sync intervals

### Risk 4: Conflicts Require Manual Resolution
**Impact**: Low - Most conflicts auto-resolved
**Mitigation**: Alert on >100 unresolved conflicts, escalation path

### Risk 5: Performance Degradation
**Impact**: Medium - Slow sync, high memory usage
**Mitigation**: Batch processing, pagination, monitoring

---

## Next Steps

1. ✅ Research complete (61-RESEARCH.md)
2. ✅ Plans created (61-01 through 61-05)
3. ⏳ Execute Plan 01: Background Sync Service
4. ⏳ Execute Plan 02: Bidirectional Rating Sync
5. ⏳ Execute Plan 03: WebSocket Real-time Updates
6. ⏳ Execute Plan 04: Conflict Resolution
7. ⏳ Execute Plan 05: Admin API & Monitoring
8. ⏳ Phase verification (61-VERIFICATION.md)
9. ⏳ Update ROADMAP.md

---

**Phase Status**: READY TO EXECUTE

**Estimated Duration**: 6 hours (5 plans, 30 tasks)

**Confidence**: High (clear dependencies, proven architecture from Phase 60)
