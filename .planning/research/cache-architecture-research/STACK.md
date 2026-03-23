# Technology Stack

**Project:** Atom - Verification Result Caching
**Researched:** March 22, 2026

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | Matches existing codebase (`backend/core/` all use Python 3.11+ type hints) |
| FastAPI | Latest (existing) | Web framework | Already in use, async/await support for lifespan events |
| SQLAlchemy | 2.0 (existing) | ORM | Existing database layer, supports async operations |

### Database
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 14+ (existing) | Cache storage (cold) | Production database, ACID compliance for cache reliability |
| SQLite | File-based (dev) | Cache storage (dev) | Development fallback, matches existing `DATABASE_URL` pattern |
| In-memory | Python dict | Cache storage (hot) | <1ms lookup, follows `GovernanceCache` pattern (LRU with TTL) |
| Redis (optional) | 6+ | Distributed cache | Existing `RedisCacheService` in `cache.py` but not required |

### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| boto3 | Latest (existing) | S3/R2 client | Already in `storage.py`, no new dependencies |
| LanceDB | Latest (existing) | Vector storage | Business facts stored here, read-only access for cache |
| asyncio | Built-in | Async worker | Background cache warming via FastAPI lifespan |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| functools | Built-in | `@lru_cache` decorator | Simple caching for single-process deployments |
| pydantic | Existing | Validation | Schema models match existing `FactResponse` patterns |
| structlog | Existing | Logging | Matches existing `core/monitoring.py` logging |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Cache Storage | Hybrid (memory + PostgreSQL) | Redis-only | Redis optional in existing stack, not all deployments have it |
| Cache Pattern | Decorator wrapper | Direct integration | Decorator allows graceful fallback, less invasive |
| TTL Strategy | 15-minute TTL | No expiration | Risk of stale data from deleted documents |
| Background Worker | FastAPI lifespan | Celery task | Celery not in existing stack, adds complexity |

## Installation

```bash
# Core (all existing)
# No new dependencies required - uses existing stack

# Optional: Redis (if using distributed cache)
# Already in backend/core/cache.py - no new installation needed
```

## Existing Stack References

**File: `backend/core/governance_cache.py`** (lines 25-150)
- LRU cache pattern with OrderedDict
- Thread-safe operations with threading.Lock()
- TTL expiration with background cleanup task
- Cache statistics tracking (hits, misses, evictions)

**File: `backend/core/cache.py`** (lines 1-95)
- RedisCacheService with fallback to in-memory
- JSON serialization for complex objects
- Pattern matching for cache invalidation

**File: `backend/main_api_app.py`** (lines 88-180)
- FastAPI lifespan context manager
- Startup event sequence (database, scheduler, integrations)
- Graceful degradation patterns (try/except with logging)

**File: `backend/core/storage.py`** (lines 56-63)
```python
def check_exists(self, key: str) -> bool:
    """Check if a file exists in S3/R2"""
    try:
        self.s3.head_object(Bucket=self.bucket, Key=key)
        return True
    except Exception as e:
        logger.debug(f"File check failed for {key}: {e}")
        return False
```
- This is the bottleneck we're caching (200-500ms per call)

## Sources

- HIGH confidence: Direct codebase analysis (all references verified)
- backend/core/governance_cache.py
- backend/core/cache.py
- backend/core/storage.py
- backend/core/agent_world_model.py
- backend/api/admin/business_facts_routes.py
- backend/main_api_app.py
- backend/core/models.py (CitationVerificationBatch model)
