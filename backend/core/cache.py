
import os
import json
import logging
import time
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional, Any, Union, Dict
from enum import Enum
from collections import OrderedDict

try:
    import redis
except ImportError:
    redis = None

# Configure Logging
logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class RedisCircuitBreaker:
    """Circuit breaker for Redis connections with automatic recovery"""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,  # seconds
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED

    def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker"""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                logger.info("🔄 Circuit breaker transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Last failure: {self._last_failure_time}"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call"""
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            logger.info("✅ Circuit breaker recovered to CLOSED state")

    def _on_failure(self):
        """Handle failed call"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"⚠️ Circuit breaker opened after {self._failure_count} failures"
            )

    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state

    def reset(self):
        """Manually reset circuit breaker (for testing)"""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = None

class SyncLocalCache:
    """Synchronous LRU-like cache for simple in-memory storage"""
    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._expire_times: Dict[str, float] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            self.misses += 1
            return None
        
        if time.time() > self._expire_times.get(key, 0):
            self.delete(key)
            self.misses += 1
            return None
        
        self.hits += 1
        return self._cache[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if len(self._cache) >= self.max_size and key not in self._cache:
            # Simple eviction: clear random key or just clear all if it gets too big
            if len(self._cache) > self.max_size * 1.1:
                self._cache.clear()
                self._expire_times.clear()
        
        ttl = ttl or self.default_ttl
        self._cache[key] = value
        self._expire_times[key] = time.time() + ttl

    def delete(self, key: str):
        self._cache.pop(key, None)
        self._expire_times.pop(key, None)

    def clear(self):
        self._cache.clear()
        self._expire_times.clear()
        self.hits = 0
        self.misses = 0

class UniversalCacheService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UniversalCacheService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Priority: Dragonfly -> Specific Cache Redis -> Legacy Redis -> Upstash
        self.redis_url = (
            os.getenv("DRAGONFLY_URL") or 
            os.getenv("CACHE_REDIS_URL") or 
            os.getenv("REDIS_URL") or 
            ""
        )
        self.enabled = os.getenv("ENABLE_CACHE", "true").lower() == "true"
        self.client = None
        self.use_rest_api = False
        self.rest_api_url = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
        self.rest_api_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

        # Initialize circuit breaker
        self.circuit_breaker = RedisCircuitBreaker(
            failure_threshold=int(os.getenv("REDIS_CIRCUIT_THRESHOLD", "3")),
            recovery_timeout=int(os.getenv("REDIS_CIRCUIT_TIMEOUT", "60"))
        )

        # Initialize local cache fallbacks
        from middleware.performance import LocalCacheFallback
        self.async_local_cache = LocalCacheFallback(
            max_size=int(os.getenv("LOCAL_CACHE_SIZE", "1000")),
            default_ttl=int(os.getenv("LOCAL_CACHE_TTL", "60"))
        )
        self.sync_local_cache = SyncLocalCache(
            max_size=int(os.getenv("LOCAL_CACHE_SIZE", "1000")),
            default_ttl=int(os.getenv("LOCAL_CACHE_TTL", "60"))
        )

        if self.enabled:
            # 1. Try direct Redis (TCP) - HIGHEST PERFORMANCE ("Better")
            if self.redis_url and redis:
                try:
                    self.client = redis.from_url(
                        self.redis_url,
                        decode_responses=True,
                        socket_connect_timeout=2,
                        socket_timeout=2
                    )
                    self.client.ping()
                    logger.info(f"✅ Redis Cache connected (TCP/Better) at {self.redis_url}")
                except Exception as e:
                    logger.warning(f"⚠️ Direct Redis connection failed: {e}")
                    self.client = None

            # 2. Fallback to Upstash REST API if TCP is unavailable but REST is configured
            if not self.client and self.rest_api_url and self.rest_api_token:
                self.use_rest_api = True
                logger.info(f"✅ Falling back to Upstash REST API at {self.rest_api_url}")
            
            # 3. Final fallback is local memory
            if not self.client and not self.use_rest_api:
                logger.info("ℹ️ No distributed cache configured. Using Local Memory Cache only.")
        else:
            logger.info("ℹ️ Cache explicitly disabled via env.")

    def _rest_get(self, key: str) -> Optional[str]:
        """Get value via Upstash REST API"""
        if not self.use_rest_api: return None
        try:
            response = httpx.get(
                f"{self.rest_api_url}/get/{key}",
                headers={"Authorization": f"Bearer {self.rest_api_token}"},
                timeout=2.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("result")
        except Exception as e:
            logger.error(f"Upstash REST GET error: {e}")
        return None

    def _rest_set(self, key: str, value: str, ttl: int) -> bool:
        """Set value via Upstash REST API"""
        if not self.use_rest_api: return False
        try:
            # Upstash REST SET expects arguments in the path or as a list
            # Format: SET key value EX seconds
            response = httpx.post(
                f"{self.rest_api_url}/set/{key}",
                headers={"Authorization": f"Bearer {self.rest_api_token}"},
                params={"ex": ttl},
                content=str(value),
                timeout=2.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Upstash REST SET error: {e}")
        return False

    def _rest_delete(self, key: str) -> bool:
        """Delete value via Upstash REST API"""
        if not self.use_rest_api: return False
        try:
            response = httpx.get(
                f"{self.rest_api_url}/del/{key}",
                headers={"Authorization": f"Bearer {self.rest_api_token}"},
                timeout=2.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Upstash REST DEL error: {e}")
        return False

    def _rest_incr(self, key: str) -> Optional[int]:
        """Increment value via Upstash REST API"""
        if not self.use_rest_api: return None
        try:
            response = httpx.get(
                f"{self.rest_api_url}/incr/{key}",
                headers={"Authorization": f"Bearer {self.rest_api_token}"},
                timeout=2.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("result")
        except Exception as e:
            logger.error(f"Upstash REST INCR error: {e}")
        return None

    def _namespace_key(self, key: str, tenant_id: Optional[str] = None) -> str:
        """
        Namespace key with tenant_id for multi-tenant isolation.
        """
        if tenant_id:
            return f"tenant:{tenant_id}:{key}"
        return key

    async def get_async(self, key: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        """[ASYNC] Retrieve a value from cache."""
        namespaced_key = self._namespace_key(key, tenant_id)

        if not self.enabled: return None

        # 1. Try Direct Redis
        if self.client:
            try:
                val = self.circuit_breaker.call(self.client.get, namespaced_key)
                if val: return self._decode(val)
            except Exception: pass

        # 2. Try Upstash REST
        if self.use_rest_api:
            val = self._rest_get(namespaced_key)
            if val: return self._decode(val)

        # 3. Local fallback
        return await self.async_local_cache.get(namespaced_key)

    def get(self, key: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        """[SYNC] Retrieve a value from cache."""
        namespaced_key = self._namespace_key(key, tenant_id)

        if not self.enabled: return None

        if self.client:
            try:
                val = self.circuit_breaker.call(self.client.get, namespaced_key)
                if val: return self._decode(val)
            except Exception: pass

        if self.use_rest_api:
            val = self._rest_get(namespaced_key)
            if val: return self._decode(val)

        return self.sync_local_cache.get(namespaced_key)

    async def set_async(self, key: str, value: Any, ttl: int = 300, tenant_id: Optional[str] = None) -> bool:
        """[ASYNC] Set a value in cache"""
        namespaced_key = self._namespace_key(key, tenant_id)
        if not self.enabled: return False
        
        await self.async_local_cache.set(namespaced_key, value, ttl)
        self.sync_local_cache.set(namespaced_key, value, ttl)

        val_to_set = self._encode(value)
        if self.client:
            try: self.circuit_breaker.call(self.client.setex, namespaced_key, ttl, val_to_set)
            except Exception: pass
        
        if self.use_rest_api:
            self._rest_set(namespaced_key, val_to_set, ttl)
        
        return True

    def set(self, key: str, value: Any, ttl: int = 300, tenant_id: Optional[str] = None) -> bool:
        """[SYNC] Set a value in cache"""
        namespaced_key = self._namespace_key(key, tenant_id)
        if not self.enabled: return False

        self.sync_local_cache.set(namespaced_key, value, ttl)

        val_to_set = self._encode(value)
        if self.client:
            try: self.circuit_breaker.call(self.client.setex, namespaced_key, ttl, val_to_set)
            except Exception: pass
        
        if self.use_rest_api:
            self._rest_set(namespaced_key, val_to_set, ttl)

        return True

    def _encode(self, value: Any) -> str:
        if isinstance(value, (dict, list)): return json.dumps(value)
        return str(value)

    def _decode(self, value: str) -> Any:
        try: return json.loads(value)
        except (json.JSONDecodeError, TypeError): return value

    async def delete_async(self, key: str, tenant_id: Optional[str] = None):
        """[ASYNC] Delete a key from cache"""
        namespaced_key = self._namespace_key(key, tenant_id)
        await self.async_local_cache.delete(namespaced_key)
        self.sync_local_cache.delete(namespaced_key)

        if self.client:
            try: self.client.delete(namespaced_key)
            except Exception: pass

        if self.use_rest_api:
            self._rest_delete(namespaced_key)

    def delete(self, key: str, tenant_id: Optional[str] = None):
        """[SYNC] Delete a key from cache"""
        namespaced_key = self._namespace_key(key, tenant_id)
        self.sync_local_cache.delete(namespaced_key)
        if self.client:
            try: self.client.delete(namespaced_key)
            except Exception: pass
        if self.use_rest_api:
            self._rest_delete(namespaced_key)

    async def incr_async(self, key: str, ttl: int = 60, tenant_id: Optional[str] = None) -> int:
        """
        [ASYNC] Atomic increment of a key in cache.
        Used primarily for rate limiting.
        """
        namespaced_key = self._namespace_key(key, tenant_id)
        if not self.enabled: return 1

        # 1. Try Direct Redis
        if self.client:
            try:
                # Use a pipeline to ensure atomic INCR + EXPIRE
                pipe = self.client.pipeline()
                pipe.incr(namespaced_key)
                pipe.expire(namespaced_key, ttl)
                results = self.circuit_breaker.call(pipe.execute)
                return int(results[0])
            except Exception as e:
                logger.debug(f"Direct Redis INCR failed: {e}")

        # 2. Try Upstash REST
        if self.use_rest_api:
            val = self._rest_incr(namespaced_key)
            if val is not None:
                # Ensure TTL is set if new
                if val == 1:
                    try:
                        httpx.get(f"{self.rest_api_url}/expire/{namespaced_key}/{ttl}", 
                                 headers={"Authorization": f"Bearer {self.rest_api_token}"})
                    except Exception: pass
                return int(val)

        # 3. Local fallback (Simple non-atomic fallback)
        curr = await self.async_local_cache.get(namespaced_key) or 0
        new_val = int(curr) + 1
        await self.async_local_cache.set(namespaced_key, new_val, ttl)
        return new_val

    async def delete_tenant_all(self, pattern_or_tenant_id: str) -> int:
        """[ASYNC] Delete keys by pattern or tenant ID."""
        self.async_local_cache.clear()
        self.sync_local_cache.clear()

        if not self.enabled: return 0

        if self.client:
            try:
                pattern = pattern_or_tenant_id if ":" in pattern_or_tenant_id else f"tenant:{pattern_or_tenant_id}:*"
                keys = [k for k in self.client.scan_iter(match=pattern)]
                if keys: return self.client.delete(*keys)
            except Exception: pass

        return 0

    def get_circuit_state(self) -> str:
        return self.circuit_breaker.get_state().value

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the cache service for health checks"""
        status = "disabled"
        if self.enabled:
            status = "operational"
            if self.client:
                try:
                    self.client.ping()
                except Exception:
                    status = "degraded"
            elif self.use_rest_api:
                # Basic check for REST API
                if not self.rest_api_url or not self.rest_api_token:
                    status = "degraded"
            else:
                # Local memory always works if enabled
                status = "operational"
        
        return {
            "status": status,
            "mode": "redis" if self.client else ("upstash_rest" if self.use_rest_api else "local_memory"),
            "circuit_breaker": self.get_circuit_state(),
            "enabled": self.enabled
        }

# Legacy alias for backward compatibility
RedisCacheService = UniversalCacheService
redis_cache = UniversalCacheService()

# Export cache singleton for system_health_routes.py
cache = redis_cache  # Alias for backward compatibility
