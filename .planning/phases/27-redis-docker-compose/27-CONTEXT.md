# Phase 27: Redis-Compatible Database in Docker Compose - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

## Phase Boundary

Add Valkey (Redis-compatible open source database) to Docker Compose deployment stack for local development and production. Remove external Redis dependency by providing Valkey as part of the standard Docker Compose setup.

## Implementation Decisions

### Database Selection
- **Valkey** (Linux Foundation) - 100% Redis protocol compatible, LGPL-3.0 licensed
- Not official Redis
- Not DragonflyDB (GPL copyleft concerns)
- Not KeyDB (uncertain maintenance after Snapchat acquisition)

### Persistence Strategy
- **Personal Edition (docker-compose-personal.yml)**: In-memory only (no persistence)
  - Fastest performance for development
  - Clean restarts, no stale data issues
  - Data lost on container restart (acceptable for local development)
- **Production (docker-compose.yml)**: Would add persistence (AOF or RDB)
  - Durability for production deployments
  - Out of scope for Phase 27

### Docker Compose Configuration
- **Service name**: `valkey` (not `redis`)
- **Port**: 6379 (default Redis port, no code changes needed)
- **Image**: `valkey/valkey:latest` (or specific version pin)
- **Environment variable**: `REDIS_URL` already exists in codebase, will point to Valkey
- **Networking**: Bridge network, accessible from other services (backend, worker)

### Environment Differences
- **docker-compose-personal.yml**: Simpler configuration, in-memory only
- **docker-compose.yml**: More robust configuration with persistence (future enhancement)

### Claude's Discretion
- Exact Valkey version pinning strategy (latest vs specific version)
- Health check configuration details
- Resource limits (memory, CPU) for Valkey container
- Volume mount strategy for production persistence

## Specific Ideas

- "We want the same developer experience as Redis - just `docker-compose up` and everything works"
- "Personal Edition should be simple - in-memory is fine, we don't need durability"
- "Code changes should be minimal - hopefully just updating docker-compose.yml"

## Deferred Ideas

- Production persistence configuration (AOF, RDB, or hybrid) - separate phase or future enhancement
- Redis Sentinel clustering for high availability - not needed for Personal Edition
- Valkey monitoring and metrics - nice to have but out of scope
- Migration strategy from existing Redis deployments - not applicable for new setups

---

*Phase: 27-redis-docker-compose*
*Context gathered: 2026-02-18*
