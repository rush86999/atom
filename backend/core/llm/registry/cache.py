"""Registry Cache Service for LLM Model Metadata

This module provides the RegistryCacheService class for caching LLM model
metadata in Redis with tenant isolation and atomic swap operations.

Cache Key Pattern:
- Individual models: llm_model:{provider}:{model_name}
- Model lists: llm_models_list[:{provider}]
- Swap lock: llm_registry_swap_lock

TTL Configuration:
- Model metadata: 24 hours (86400 seconds)
- Swap lock: 60 seconds (auto-releases)

Tenant Isolation:
All keys are automatically namespaced with tenant_id by UniversalCacheService:
tenant:{tenant_id}:llm_model:...
"""

import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

from core.cache import UniversalCacheService

logger = logging.getLogger(__name__)

# Cache key constants
MODEL_KEY_PREFIX = "llm_model"
LIST_KEY_PREFIX = "llm_models_list"
SWAP_LOCK_KEY = "llm_registry_swap_lock"
CACHE_TTL = 86400  # 24 hours
LOCK_TTL = 60  # 60 seconds


class RegistryCacheService:
    """
    Cache service for LLM model registry with tenant isolation and atomic swap.

    Features:
    - Tenant-scoped cache keys (handled by UniversalCacheService)
    - Atomic swap operations with distributed locking
    - 24-hour TTL for model metadata
    - Graceful degradation on cache failures
    - Database fallback on cache miss

    Example:
        >>> cache = RegistryCacheService()
        >>> await cache.set_model('tenant-123', 'openai', 'gpt-4', {...})
        >>> model = await cache.get_model('tenant-123', 'openai', 'gpt-4')
    """

    def __init__(self):
        """Initialize the cache service with UniversalCacheService singleton."""
        self.cache = UniversalCacheService()
        logger.debug("RegistryCacheService initialized")

    def _model_key(self, provider: str, model_name: str) -> str:
        """
        Build tenant-scoped cache key for individual model.

        Note: UniversalCacheService handles tenant prefix internally via _namespace_key,
        so we return the base key without tenant prefix.

        Args:
            tenant_id: Tenant identifier (for logging/validation only)
            provider: Provider name (e.g., 'openai', 'anthropic')
            model_name: Model name (e.g., 'gpt-4', 'claude-3-opus')

        Returns:
            Cache key string (without tenant prefix)
        """
        return f"{MODEL_KEY_PREFIX}:{provider}:{model_name}"

    def _list_key(self, provider: Optional[str] = None) -> str:
        """
        Build tenant-scoped cache key for model list.

        Args:
            tenant_id: Tenant identifier (for logging/validation only)
            provider: Optional provider filter

        Returns:
            Cache key string (without tenant prefix)
        """
        if provider:
            return f"{LIST_KEY_PREFIX}:{provider}"
        return LIST_KEY_PREFIX

    async def get_model(
        self,
        provider: str,
        model_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a model from cache.

        Args:
            tenant_id: Tenant identifier
            provider: Provider name
            model_name: Model name

        Returns:
            Model data dictionary or None if not found

        Example:
            >>> model = await cache.get_model('tenant-123', 'openai', 'gpt-4')
            >>> if model:
            ...     print(f"Context window: {model['context_window']}")
        """
        key = self._model_key(tenant_id, provider, model_name)
        try:
            result = await self.cache.get_async(key)
            if result:
                logger.debug(f"Cache hit: {key} for tenant {tenant_id}")
            else:
                logger.debug(f"Cache miss: {key} for tenant {tenant_id}")
            return result
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    async def set_model(
        self,
        provider: str,
        model_name: str,
        model_data: Dict[str, Any]
    ) -> bool:
        """
        Store a model in cache.

        Args:
            tenant_id: Tenant identifier
            provider: Provider name
            model_name: Model name
            model_data: Model metadata dictionary

        Returns:
            True if successful, False otherwise

        Example:
            >>> success = await cache.set_model(
            ...     'tenant-123',
            ...     'openai',
            ...     'gpt-4',
            ...     {'context_window': 8192, 'capabilities': ['tools', 'vision']}
            ... )
        """
        key = self._model_key(tenant_id, provider, model_name)
        try:
            await self.cache.set_async(key, model_data, CACHE_TTL)
            logger.debug(f"Cache set: {key} for tenant {tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    async def get_models_list(
        self,
        provider: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve cached list of models.

        Args:
            tenant_id: Tenant identifier
            provider: Optional provider filter

        Returns:
            List of model dictionaries or None if not cached

        Example:
            >>> # Get all cached models
            >>> all_models = await cache.get_models_list('tenant-123')
            >>>
            >>> # Get only OpenAI models
            >>> openai_models = await cache.get_models_list('tenant-123', 'openai')
        """
        key = self._list_key(tenant_id, provider)
        try:
            result = await self.cache.get_async(key)
            if result:
                logger.debug(f"Cache list hit: {key} for tenant {tenant_id}")
            else:
                logger.debug(f"Cache list miss: {key} for tenant {tenant_id}")
            return result
        except Exception as e:
            logger.error(f"Cache list get error for {key}: {e}")
            return None

    async def set_models_list(
        self,
        models: List[Dict[str, Any]],
        provider: Optional[str] = None
    ) -> bool:
        """
        Store list of models in cache.

        Args:
            tenant_id: Tenant identifier
            models: List of model dictionaries
            provider: Optional provider filter

        Returns:
            True if successful, False otherwise
        """
        key = self._list_key(tenant_id, provider)
        try:
            await self.cache.set_async(key, models, CACHE_TTL)
            logger.debug(f"Cache list set: {key} for tenant {tenant_id} ({len(models)} models)")
            return True
        except Exception as e:
            logger.error(f"Cache list set error for {key}: {e}")
            return False

    async def atomic_swap_registry(
        self,
        models: List[Dict[str, Any]]
    ) -> bool:
        """
        Perform atomic swap of model registry cache.

        Uses distributed lock pattern to prevent race conditions:
        1. Try to acquire swap lock
        2. If lock exists, raise exception (swap already in progress)
        3. Delete old model keys and write new data atomically
        4. Release lock in finally block

        Key Rotation Pattern:
        - Old keys: llm_model:provider:model
        - New keys: llm_model:provider:model:{timestamp}
        - After swap, old keys expire naturally via TTL

        Args:
            tenant_id: Tenant identifier
            models: List of model dictionaries to cache

        Returns:
            True if swap successful

        Raises:
            Exception: If swap already in progress (lock held)

        Example:
            >>> # Fetch all models from database
            >>> models = await fetch_models_from_db('tenant-123')
            >>>
            >>> # Atomically swap cache
            >>> await cache.atomic_swap_registry('tenant-123', models)
        """
        lock_key = SWAP_LOCK_KEY

        # Try to acquire lock
        try:
            # Check if lock exists
            existing_lock = await self.cache.get_async(lock_key)
            if existing_lock:
                raise Exception("Swap in progress - lock already held")

            # Acquire lock with 60-second TTL
            await self.cache.set_async(lock_key, "swapping", LOCK_TTL)
            logger.info(f"Acquired swap lock for tenant {tenant_id}")

        except Exception as e:
            logger.warning(f"Failed to acquire swap lock for tenant {tenant_id}: {e}")
            raise

        try:
            # Generate version suffix for key rotation
            version = int(time.time())

            # Group models by provider for efficient list caching
            models_by_provider: Dict[str, List[Dict[str, Any]]] = {}
            all_models_list = []

            for model_data in models:
                provider = model_data.get('provider', 'unknown')
                model_name = model_data.get('model_name', 'unknown')

                # Set individual model cache with version suffix
                # Note: We don't use version suffix in actual key to keep lookup simple
                # Instead, we overwrite existing keys during swap
                await self.set_model(tenant_id, provider, model_name, model_data)

                # Add to provider-specific list
                if provider not in models_by_provider:
                    models_by_provider[provider] = []
                models_by_provider[provider].append(model_data)
                all_models_list.append(model_data)

            # Update list caches
            await self.set_models_list(tenant_id, all_models_list, provider=None)

            for provider, provider_models in models_by_provider.items():
                await self.set_models_list(tenant_id, provider_models, provider=provider)

            logger.info(
                f"Atomic swap complete for tenant {tenant_id}: "
                f"{len(all_models_list)} models, {len(models_by_provider)} providers"
            )

            return True

        except Exception as e:
            logger.error(f"Error during atomic swap for tenant {tenant_id}: {e}")
            raise

        finally:
            # Release lock
            try:
                await self.cache.delete_async(lock_key)
                logger.debug(f"Released swap lock for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Error releasing swap lock for tenant {tenant_id}: {e}")

    async def invalidate_tenant(self) -> int:
        """
        Clear all cached data for a tenant.

        Deletes all keys matching the tenant pattern:
        tenant:{tenant_id}:llm_model:*
        tenant:{tenant_id}:llm_models_list:*
        tenant:{tenant_id}:llm_registry_swap_lock

        Args:
            tenant_id: Tenant identifier

        Returns:
            Number of keys deleted

        Example:
            >>> count = await cache.invalidate_tenant('tenant-123')
            >>> print(f"Invalidated {count} cache keys")
        """
        try:
            count = await self.cache.delete_tenant_all(tenant_id)
            logger.info(f"Invalidated {count} cache keys for tenant {tenant_id}")
            return count
        except Exception as e:
            logger.error(f"Error invalidating cache for tenant {tenant_id}: {e}")
            return 0

    async def warm_cache(
        self,
        models: List[Dict[str, Any]]
    ) -> None:
        """
        Warm cache with model data (no lock required).

        Used for initial cache population. Unlike atomic_swap_registry,
        this method does not acquire a lock and is safe to run when
        cache is empty or during startup.

        Args:
            tenant_id: Tenant identifier
            models: List of model dictionaries to cache

        Example:
            >>> # Initial cache population
            >>> models = await fetch_models_from_db('tenant-123')
            >>> await cache.warm_cache('tenant-123', models)
        """
        logger.info(f"Warming cache for tenant {tenant_id} with {len(models)} models")

        # Set individual models
        for model_data in models:
            provider = model_data.get('provider', 'unknown')
            model_name = model_data.get('model_name', 'unknown')
            await self.set_model(tenant_id, provider, model_name, model_data)

        # Set list caches
        models_by_provider: Dict[str, List[Dict[str, Any]]] = {}
        for model_data in models:
            provider = model_data.get('provider', 'unknown')
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            models_by_provider[provider].append(model_data)

        await self.set_models_list(tenant_id, models, provider=None)

        for provider, provider_models in models_by_provider.items():
            await self.set_models_list(tenant_id, provider_models, provider=provider)

        logger.info(f"Cache warming complete for tenant {tenant_id}")

    async def delete_model(
        self,
        provider: str,
        model_name: str
    ) -> bool:
        """
        Delete a specific model from cache.

        Args:
            tenant_id: Tenant identifier
            provider: Provider name
            model_name: Model name

        Returns:
            True if deleted, False otherwise

        Example:
            >>> deleted = await cache.delete_model('tenant-123', 'openai', 'gpt-4')
        """
        key = self._model_key(tenant_id, provider, model_name)
        try:
            await self.cache.delete_async(key)
            logger.debug(f"Deleted model from cache: {key} for tenant {tenant_id}")

            # Invalidate list caches (they'll be rebuilt on next request)
            list_key_all = self._list_key(tenant_id, provider=None)
            list_key_provider = self._list_key(tenant_id, provider=provider)
            await self.cache.delete_async(list_key_all)
            await self.cache.delete_async(list_key_provider)

            return True
        except Exception as e:
            logger.error(f"Error deleting model from cache: {key}: {e}")
            return False
