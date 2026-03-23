# Existing System Analysis

**Project:** Atom - Verification Result Caching Research
**Date:** March 22, 2026

## Current Verification Flow Analysis

### Entry Point: `verify_citation()` API Endpoint
**File:** `backend/api/admin/business_facts_routes.py:336-407`

**Current Implementation:**
```python
@router.post("/{fact_id}/verify-citation")
async def verify_citation(
    fact_id: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Re-verify that a fact's citation sources still exist in R2/S3.
    """
    workspace_id = getattr(current_user, 'workspace_id', None) or "default"
    wm = WorldModelService(workspace_id)

    fact = await wm.get_fact_by_id(fact_id)
    if not fact:
        raise router.not_found_error("Business fact", fact_id)

    from core.storage import get_storage_service
    storage = get_storage_service()  # ← Singleton S3/R2 client

    verification_results = []
    all_valid = True

    for citation in fact.citations:
        exists = False

        # Check S3/R2
        if citation.startswith("s3://"):
            try:
                bucket_name = storage.bucket
                if f"s3://{bucket_name}/" in citation:
                    key = citation.replace(f"s3://{bucket_name}/", "")
                    exists = storage.check_exists(key)  # ← BOTTLENECK: 200-500ms
                else:
                    parts = citation.replace("s3://", "").split("/", 1)
                    if len(parts) == 2 and parts[0] == bucket_name:
                        exists = storage.check_exists(parts[1])
            except Exception as e:
                logger.warning(f"Failed to check S3 citation {citation}: {e}")

        # Fallback: Check Local (Legacy)
        else:
            filename = citation.split(":")[0]
            for base_path in ["/app/uploads", "/tmp", os.getcwd()]:
                full_path = os.path.join(base_path, filename)
                if os.path.exists(full_path):
                    exists = True
                    break

        verification_results.append({
            "citation": citation,
            "exists": exists,
            "source": "R2" if citation.startswith("s3://") else "Local"
        })

        if not exists:
            all_valid = False
            logger.warning(f"Verification failed for citation: {citation}")

    # Update verification status
    new_status = "verified" if all_valid else "outdated"
    await wm.update_fact_verification(fact_id, new_status)

    return {
        "fact_id": fact_id,
        "new_status": new_status,
        "citations": verification_results
    }
```

**Key Observations:**
1. **No caching**: Every citation triggers `storage.check_exists()` → 200-500ms network call
2. **Sequential processing**: Citations checked one-by-one (could be parallel)
3. **No result storage**: Verification results returned but not persisted for next call
4. **Manual S3 key parsing**: Brittle string manipulation, could be centralized

### Bottleneck: `storage.check_exists()`
**File:** `backend/core/storage.py:56-63`

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

**Performance Characteristics:**
- **S3/R2 API call**: 200-500ms latency (network round-trip)
- **No retries**: Single attempt, fails fast on network issues
- **No rate limiting**: Could hit API rate limits under load

### World Model Storage: `update_fact_verification()`
**File:** `backend/core/agent_world_model.py:385-414`

```python
async def update_fact_verification(self, fact_id: str, status: str) -> bool:
    """Update the verification status of a business fact"""
    try:
        results = self.db.search(
            table_name=self.facts_table_name,
            query="",
            limit=100
        )

        for res in results:
            if res.get("metadata", {}).get("id") == fact_id:
                meta = res.get("metadata", {})
                meta["verification_status"] = status
                meta["last_verified"] = datetime.now().isoformat()

                # Re-add with updated metadata (LanceDB append-only)
                self.db.add_document(
                    table_name=self.facts_table_name,
                    text=new_text,
                    source=res.get("source"),
                    metadata=meta,
                    user_id="fact_system"
                )
                logger.info(f"Updated fact {fact_id} status to {status}")
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to update fact verification: {e}")
        return False
```

**Key Observations:**
1. **LanceDB append-only**: Updates create new records, old records stale
2. **Full table scan**: Searches all records to find fact_id (inefficient)
3. **No caching**: Verification status not cached between lookups

## Existing Cache Patterns to Follow

### Pattern 1: `GovernanceCache` (In-Memory LRU)
**File:** `backend/core/governance_cache.py:25-358`

**Key Features:**
```python
class GovernanceCache:
    """
    Thread-safe LRU cache for governance decisions with TTL.
    Cache key format: "{agent_id}:{action_type}"
    Cache value: {"allowed": bool, "data": dict, "cached_at": timestamp}
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

        # OrderedDict for LRU eviction (thread-safe operations)
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, agent_id: str, action_type: str) -> Optional[Dict[str, Any]]:
        key = self._make_key(agent_id, action_type)

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            cached_at = entry.get("cached_at", 0)
            age_seconds = time.time() - cached_at

            # Check if expired
            if age_seconds > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._hits += 1

            return entry["data"]
```

**Reusability for Verification Cache:**
- **LRU eviction**: Can copy OrderedDict pattern directly
- **TTL expiration**: Reuse time-based expiration logic
- **Thread safety**: Reuse threading.Lock() pattern
- **Statistics**: Reuse hits/misses/evictions tracking

### Pattern 2: `RedisCacheService` (Hybrid Storage)
**File:** `backend/core/cache.py:43-95`

**Key Features:**
```python
class RedisCacheService(CacheManager):
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, expire: int = 300):
        """Set value in cache with expiration (seconds)"""
        try:
            serialized = json.dumps(value)
            if self.redis_client:
                self.redis_client.setex(key, expire, serialized)
            else:
                self.memory_cache[key] = serialized
        except Exception as e:
            logger.error(f"Cache set error: {e}")
```

**Reusability for Verification Cache:**
- **Redis fallback**: Can use existing Redis infrastructure
- **JSON serialization**: Reuse for complex objects (citation results)
- **Error handling**: Reuse graceful degradation pattern

### Pattern 3: FastAPI Lifespan Events
**File:** `backend/main_api_app.py:88-180`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("ATOM Platform Starting (Hybrid Mode)")

    # 1. Initialize Database
    from core.database import engine
    Base.metadata.create_all(bind=engine)

    # 2. Load Essential Integrations
    if ESSENTIAL_INTEGRATIONS:
        for name in ESSENTIAL_INTEGRATIONS:
            router = load_integration(name)
            app.include_router(router, tags=[name])

    # 3. Start Workflow Scheduler (non-blocking)
    if enable_scheduler:
        from ai.workflow_scheduler import workflow_scheduler
        try:
            workflow_scheduler.start()
        except Exception as e:
            logger.error(f"!!! Workflow Scheduler Crashed: {e}")

    yield

    # --- SHUTDOWN ---
    logger.info("ATOM Platform Shutting Down")
```

**Integration Point for Cache Warming:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("Starting verification cache warming...")

    # Non-blocking background task
    cache_warming_task = asyncio.create_task(warm_verification_cache())

    # Continue with other startup tasks
    yield

    # --- SHUTDOWN ---
    cache_warming_task.cancel()
```

## Existing Database Models

### Model: `CitationVerificationBatch`
**File:** `backend/core/models.py:5616-5659`

```python
class CitationVerificationBatch(Base):
    """
    Citation Verification Batch model for bulk verification operations.

    Tracks bulk verification jobs triggered by admin (by document, domain, or all pending).
    """
    __tablename__ = "citation_verification_batches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)

    # Batch details
    batch_type = Column(String(50), nullable=False)  # 'document', 'domain', 'all_pending'
    source_identifier = Column(Text, nullable=True)

    # Status tracking
    status = Column(String(50), default="pending", nullable=False)  # pending, in_progress, completed, failed

    # Results tracking
    total_facts = Column(Integer, default=0, nullable=False)
    verified_facts = Column(Integer, default=0, nullable=False)
    failed_facts = Column(Integer, default=0, nullable=False)

    # Trigger details
    triggered_by = Column(String(255), nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Detailed results
    results_json = Column(JSON, nullable=True)
```

**Observations:**
1. **Batch operations**: Model exists for bulk verification (not yet utilized for caching)
2. **Status tracking**: Has status, progress tracking fields
3. **Unused for caching**: Currently only tracks manual batch jobs, not automated caching

## Recommended Integration Points

### Point 1: Decorator on `verify_citation()`
**Location:** `backend/api/admin/business_facts_routes.py:336`

**Approach:** Add `@cached_verification` decorator
- Non-invasive (doesn't change function signature)
- Graceful fallback (decorator failure doesn't break verification)
- Easy to disable via feature flag

### Point 2: Background Worker in Lifespan
**Location:** `backend/main_api_app.py:88`

**Approach:** Add cache warming to startup sequence
- Non-blocking (asyncio.create_task)
- Graceful degradation (startup continues if warming fails)
- One-time cost (cache populated once per deployment)

### Point 3: Invalidation on Document Operations
**Locations:**
- `backend/api/admin/business_facts_routes.py:231` (upload)
- `backend/api/admin/business_facts_routes.py:212` (delete)

**Approach:** Invalidate cache entries when documents change
- Prevents stale data
- Targeted invalidation (only affected citations)
- Optional (can fall back to TTL expiration)

### Point 4: New Database Table
**Location:** `backend/core/models.py` (new model)

**Approach:** Create `FactVerificationCache` model
- PostgreSQL table for cold cache
- Indexed on (workspace_id, citation_key, expires_at)
- Managed by VerificationCacheService

## Performance Optimization Opportunities

### Opportunity 1: Parallel Verification
**Current:** Sequential citation checks
**Proposed:** `asyncio.gather()` for parallel S3/R2 calls

```python
# Current (sequential)
for citation in fact.citations:
    exists = storage.check_exists(key)

# Proposed (parallel)
tasks = [storage.check_exists(key) for key in citation_keys]
results = await asyncio.gather(*tasks)
```

**Expected Speedup:** 3-5x for facts with multiple citations

### Opportunity 2: Batch Verification
**Current:** One fact per API call
**Proposed:** Batch API endpoint (verify multiple facts)

```python
@router.post("/verify-batch")
async def verify_citation_batch(fact_ids: List[str]):
    """Verify multiple facts in one request"""
    # Reuse CitationVerificationBatch model for tracking
```

**Expected Speedup:** 5-10x for bulk operations

### Opportunity 3: Pre-Warming on Deployment
**Current:** Cold cache on startup
**Proposed:** Pre-warm with "verified" facts

```python
async def warm_verification_cache():
    facts = await wm.list_all_facts(status="verified", limit=1000)
    for fact in facts:
        for citation in fact.citations:
            await cache.set(citation, {"exists": True, "source": "R2"})
```

**Expected Speedup:** Eliminates cold start latency (~5-10s for first 100 requests)

## Migration Complexity Assessment

| Component | Complexity | Risk | Time Estimate |
|-----------|------------|------|---------------|
| Database schema | Low | Low | 2-4 hours |
| VerificationCacheService | Medium | Low | 4-6 hours |
| Decorator integration | Low | Low | 2-3 hours |
| Background worker | Medium | Medium | 4-8 hours |
| Monitoring/metrics | Low | Low | 2-3 hours |
| Testing/validation | Medium | Medium | 6-8 hours |
| **Total** | **Medium** | **Low-Medium** | **20-32 hours** |

**Risk Mitigation:**
- Feature flags for all new features (easy rollback)
- Gradual rollout (staging → canary → production)
- Comprehensive monitoring (detect issues early)
- Graceful degradation (cache failure doesn't break verification)

## Sources

- HIGH confidence: Direct codebase analysis (all references verified with line numbers)
- MEDIUM confidence: Performance estimates (based on documented S3/R2 latency)
- LOW confidence: Migration time estimates (no actual implementation experience)
