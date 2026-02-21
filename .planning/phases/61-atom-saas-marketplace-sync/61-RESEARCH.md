# Phase 61: Atom SaaS Marketplace Sync - Research

**Purpose**: Research Atom SaaS sync requirements and architecture

**Date**: 2026-02-19

## Current State Analysis

### What's Already Built (Phase 60)

1. **AtomSaaSClient** (`backend/core/atom_saas_client.py` - 267 lines)
   - ✅ HTTP client with authentication (Bearer token)
   - ✅ Async methods: fetch_skills, get_skill_by_id, get_categories, rate_skill, install_skill
   - ✅ Synchronous wrapper methods
   - ❌ WebSocket connection: TODO (line 225-227)
   - ❌ No background sync jobs
   - ❌ No bidirectional sync logic

2. **Local Marketplace** (`backend/core/skill_marketplace_service.py`)
   - ✅ PostgreSQL-based skill storage
   - ✅ SkillRating model (local 1-5 star ratings)
   - ✅ SkillCache and CategoryCache models (for sync)
   - ✅ Search, categories, ratings, installation
   - ❌ No sync service to populate cache from Atom SaaS
   - ❌ No push of local data to Atom SaaS

3. **Cache Models** (`backend/core/models.py`)
   - ✅ SkillCache (skill_id, name, description, category, metadata, expires_at)
   - ✅ CategoryCache (category, count, expires_at)
   - ✅ Indexes on expires_at for cleanup
   - ✅ 5-minute TTL default

### What's Missing

1. **Background Sync Service**
   - Periodic jobs to pull skills/categories from Atom SaaS
   - Cache population and invalidation
   - Error handling and retry logic
   - Sync scheduling (cron-like or task queue)

2. **Bidirectional Sync**
   - Push local ratings to Atom SaaS
   - Push local skill installations to Atom SaaS
   - Conflict resolution (local vs remote data)

3. **WebSocket Integration**
   - Real-time skill updates from Atom SaaS
   - Connection management (reconnect, heartbeat)
   - Message handling and routing

4. **Conflict Resolution**
   - Skills exist both locally and remotely
   - Version conflicts
   - Rating aggregation (local + remote)

5. **Admin & Monitoring**
   - Sync status endpoints
   - Manual sync trigger
   - Sync health metrics
   - Error logging and alerting

## Atom SaaS API (Assumptions)

Based on AtomSaaSClient placeholder, Atom SaaS API likely provides:

### REST API Endpoints

```
GET  /api/marketplace/skills           - List/search skills (paginated)
GET  /api/marketplace/skills/{id}      - Get skill details
GET  /api/marketplace/categories       - List categories
POST /api/marketplace/skills/{id}/rate - Submit rating
POST /api/marketplace/skills/{id}/install - Install skill
```

### WebSocket Endpoint

```
ws://localhost:5058/api/ws/satellite/connect
```

Expected WebSocket messages:
- **skill_update**: New or updated skill
- **category_update**: New or updated category
- **rating_update**: New rating for skill
- **skill_delete**: Skill removed from marketplace

### Authentication

- Bearer token in Authorization header
- Token validation on connection
- Token refresh mechanism (if needed)

## Architecture Options

### Option 1: Polling-Based Sync (Simpler)

**How it works:**
- Background job runs every N minutes (e.g., 5, 15, 60)
- Calls AtomSaaSClient.fetch_skills() with incremental updates
- Compares with local cache, updates/deletes as needed
- Pushes local ratings to Atom SaaS

**Pros:**
- Simple to implement
- No WebSocket complexity
- Easy to schedule and monitor
- Works with existing AtomSaaSClient

**Cons:**
- Not real-time (5-15 minute delay)
- Higher API load (continuous polling)
- May hit rate limits

**Estimated effort:** 3-4 plans

### Option 2: WebSocket + Polling Hybrid (Recommended)

**How it works:**
- WebSocket connection for real-time updates
- Polling as fallback when WebSocket disconnected
- Initial full sync via polling, then incremental via WebSocket
- Bidirectional sync for ratings and installations

**Pros:**
- Near real-time updates
- Resilient (polling fallback)
- Lower API load after initial sync
- Better user experience

**Cons:**
- More complex (WebSocket reconnection, message ordering)
- Requires WebSocket implementation
- More testing edge cases

**Estimated effort:** 5-6 plans

### Option 3: Event-Driven with Message Queue (Most Complex)

**How it works:**
- Atom SaaS publishes events to message queue (Redis, RabbitMQ)
- Atom subscribes to queue, processes events
- No polling, pure event-driven

**Pros:**
- Most scalable
- Real-time updates
- Decoupled architecture

**Cons:**
- Requires Atom SaaS to support message queue
- Most complex infrastructure
- Overkill for current needs

**Estimated effort:** 7-8 plans

## Recommendation: Option 2 (WebSocket + Polling Hybrid)

This provides the best balance of real-time updates and resilience while fitting within the existing AtomSaaSClient architecture.

## Technical Requirements

### Libraries Needed

1. **WebSocket Client**
   - `websockets` (Python async WebSocket library)
   - OR `websocket-client` (synchronous wrapper)
   - Already likely installed if using satellite scripts

2. **Background Jobs**
   - `apscheduler` (lightweight scheduler)
   - OR `celery` (if already using Redis)
   - OR `asyncio.create_task()` with sleep loops

3. **Conflict Resolution**
   - Custom merge logic (no library needed)
   - Strategy pattern for different merge policies

### Database Schema Changes

No new models needed - SkillCache, CategoryCache, SkillRating already exist.

Potential additions:
- SyncState model (track last sync time, sync status)
- SyncLog model (audit log of sync operations)

### API Endpoints Needed

Admin endpoints:
- POST /api/admin/sync/trigger - Manual sync trigger
- GET /api/admin/sync/status - Sync status (last sync, next sync, errors)
- GET /api/admin/sync/logs - Sync operation logs
- PUT /api/admin/sync/config - Update sync configuration

### Configuration

New environment variables:
```bash
# Sync scheduling
ATOM_SAAS_SYNC_ENABLED=true
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15
ATOM_SAAS_SYNC_BATCH_SIZE=100

# WebSocket
ATOM_SAAS_WEBSOCKET_ENABLED=true
ATOM_SAAS_WEBSOCKET_RECONNECT_DELAY_SECONDS=5
ATOM_SAAS_WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS=30

# Conflict resolution
ATOM_SAAS_SYNC_CONFLICT_STRATEGY=remote_wins  # remote_wins, local_wins, merge
```

## Sync Flow Design

### Initial Full Sync

1. Clear existing SkillCache/CategoryCache
2. Fetch all skills from Atom SaaS (paginated)
3. Fetch all categories from Atom SaaS
4. Populate local cache
5. Update SyncState with last_sync_time
6. Log sync completion

### Incremental Sync (Polling)

1. Fetch skills modified since last_sync_time
2. Compare with local cache
3. Update/add/delete as needed
4. Push local ratings to Atom SaaS
5. Update last_sync_time

### Real-time Sync (WebSocket)

1. Connect to Atom SaaS WebSocket
2. Subscribe to skill updates
3. On skill_update message:
   - Check if skill exists locally
   - Update cache or fetch full skill details
4. On skill_delete message:
   - Remove from local cache
5. On disconnect:
   - Fall back to polling
   - Attempt reconnection with exponential backoff

### Bidirectional Rating Sync

1. Query local SkillRating for ratings not yet synced
2. Batch push to Atom SaaS API
3. Mark ratings as synced
4. Handle conflicts (same user rated multiple times)

## Conflict Resolution Strategies

### remote_wins (Default)
- Atom SaaS data always overwrites local
- Use case: Atom SaaS is source of truth

### local_wins
- Local data never overwritten
- Use case: Custom local skills

### merge
- Merge fields intelligently
- Use case: Collaborative editing
- Example: Keep local customizations, update remote metadata

### manual
- Flag conflicts, require admin resolution
- Use case: Critical data conflicts

## Testing Strategy

### Unit Tests
- SyncService methods (fetch, cache, update)
- Conflict resolution logic
- WebSocket message handling

### Integration Tests
- Mock Atom SaaS API responses
- Test full sync cycle
- Test error scenarios (timeout, 500 errors)

### E2E Tests
- Connect to test Atom SaaS instance
- Verify sync end-to-end
- Load testing (1000+ skills)

### Performance Tests
- Sync time vs skill count
- Memory usage during sync
- API rate limit handling

## Security Considerations

1. **API Token Storage**
   - Never log tokens
   - Use secrets management (Kubernetes secrets, AWS Secrets Manager)
   - Rotate tokens periodically

2. **WebSocket Authentication**
   - Token validation on connection
   - Disconnect on auth failure
   - Rate limit connection attempts

3. **Data Validation**
   - Validate all incoming data from Atom SaaS
   - Sanitize skill metadata
   - Check for malicious payloads

4. **Rate Limiting**
   - Respect Atom SaaS API rate limits
   - Implement backoff on 429 errors
   - Log rate limit hits

## Rollout Plan

### Phase 1: Polling-Based Sync (MVP)
- Implement background sync service
- No WebSocket yet
- 15-minute sync interval
- Manual sync trigger

### Phase 2: Add WebSocket
- Implement WebSocket connection
- Real-time skill updates
- Fallback to polling on disconnect

### Phase 3: Bidirectional Sync
- Push local ratings to Atom SaaS
- Push local skill installations
- Conflict resolution

### Phase 4: Enhanced Monitoring
- Sync metrics and dashboards
- Error alerting
- Performance optimization

## Dependencies

- ✅ Phase 14 (Community Skills) - Skill models, registry
- ✅ Phase 35 (Python Package Support) - Package governance
- ✅ Phase 36 (npm Package Support) - npm governance
- ✅ Phase 60 (Advanced Skill Execution) - Marketplace models, AtomSaaSClient

## Success Criteria

1. Background sync service runs every 15 minutes
2. Local cache populated with Atom SaaS skills
3. WebSocket receives real-time updates
4. Bidirectional rating sync working
5. Admin API endpoints functional
6. Comprehensive test coverage (80%+)
7. Documentation complete

## Open Questions

1. **Atom SaaS Availability**: Is Atom SaaS API deployed and accessible?
2. **API Rate Limits**: What are the rate limits for Atom SaaS API?
3. **WebSocket Protocol**: What's the exact WebSocket message format?
4. **Authentication**: How to obtain and refresh API tokens?
5. **Sync Scope**: Sync all skills or filtered subset?

## Next Steps

Create detailed implementation plans for:
- Plan 01: Background Sync Service
- Plan 02: Bidirectional Rating Sync
- Plan 03: WebSocket Real-time Updates
- Plan 04: Conflict Resolution & Merge Strategies
- Plan 05: Admin API & Health Monitoring

---

*Research completed: 2026-02-19*
*Recommendation: Proceed with Option 2 (WebSocket + Polling Hybrid)*
