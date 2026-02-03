
import json
import logging
import os
from typing import Any, Optional, Union

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from datetime import timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self):
        from core.config import get_config
        self.config = get_config()
        self.redis_client = None
        self.memory_cache = {}
        
        if self.config.redis.enabled and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(self.config.redis.url, decode_responses=True)
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
        else:
            if not REDIS_AVAILABLE:
                logger.info("Redis module not available. Using in-memory cache.")
            else:
                logger.info("Redis not enabled or no configuration found. Using in-memory cache.")

    @property
    def enabled(self):
        return self.config.redis.enabled and REDIS_AVAILABLE

    @property
    def client(self):
        return self.redis_client

class RedisCacheService(CacheManager):
    pass

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
                # Note: In-memory cache doesn't implement expiration in this simple version
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def delete(self, key: str):
        """Delete value from cache"""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            elif key in self.memory_cache:
                del self.memory_cache[key]
        except Exception as e:
            logger.error(f"Cache delete error: {e}")

    async def clear_pattern(self, pattern: str):
        """Clear keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            else:
                # Simple prefix matching for in-memory
                keys_to_delete = [k for k in self.memory_cache.keys() if k.startswith(pattern.replace('*', ''))]
                for k in keys_to_delete:
                    del self.memory_cache[k]
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

# Global cache instance
cache = CacheManager()
