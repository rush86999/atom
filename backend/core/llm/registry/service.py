"""LLM Registry Service for Database Operations

This module provides the LLMRegistryService class for managing model metadata
in the database. It handles fetching, transforming, upserting, and querying
models with proper tenant isolation.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.llm.registry.models import LLMModel
from core.llm.registry.fetchers import ModelMetadataFetcher
from core.llm.registry.transformers import (
    transform_litellm_model,
    transform_openrouter_model,
    merge_duplicate_models
)
from core.llm.registry.cache import RegistryCacheService
from core.llm.registry.lmsys_client import LMSYSClient
from core.llm.registry.heuristic_scorer import HeuristicScorer

logger = logging.getLogger(__name__)


class LLMRegistryService:
    """
    Service for managing LLM model registry in the database.

    Handles fetching models from external sources, transforming data,
    upserting to database, and querying with tenant isolation.
    """

    def __init__(self, db: Session, use_cache: bool = True):
        """
        Initialize the registry service.

        Args:
            db: SQLAlchemy database session
            use_cache: Enable caching (default True)
        """
        self.db = db
        self.fetcher = ModelMetadataFetcher()
        self.cache = RegistryCacheService() if use_cache else None
        self.use_cache = use_cache

    async def fetch_and_store(self, tenant_id: str) -> Dict[str, int]:
        """
        Fetch models from all sources and store them in the database.

        This method:
        1. Fetches models from LiteLLM and OpenRouter
        2. Transforms the data to LLMModel schema
        3. Upserts each model to the database
        4. Returns statistics about the operation

        Args:
            tenant_id: Tenant identifier for multi-tenancy

        Returns:
            Dictionary with stats:
            {
                'created': int,
                'updated': int,
                'failed': int,
                'total': int
            }

        Example:
            >>> service = LLMRegistryService(db)
            >>> stats = await service.fetch_and_store('tenant-123')
            >>> print(f"Created {stats['created']} models")
        """
        logger.info(f"Fetching and storing models for tenant {tenant_id}")

        # Fetch from all sources
        fetch_result = await self.fetcher.fetch_all()

        litellm_models = fetch_result.get('litellm', {})
        openrouter_models = fetch_result.get('openrouter', {})

        logger.info(f"Fetched {len(litellm_models)} LiteLLM models, {len(openrouter_models)} OpenRouter models")

        # Transform models
        transformed_litellm = [
            transform_litellm_model(data, name)
            for name, data in litellm_models.items()
        ]
        transformed_litellm = [m for m in transformed_litellm if m]

        transformed_openrouter = [
            transform_openrouter_model(data)
            for data in openrouter_models.values()
        ]
        transformed_openrouter = [m for m in transformed_openrouter if m]

        # Merge and deduplicate
        all_transformed = transformed_litellm + transformed_openrouter
        unique_models = merge_duplicate_models(all_transformed, priority_source='litellm')

        logger.info(f"Transformed {len(unique_models)} unique models")

        # Upsert each model
        stats = {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'total': len(unique_models)
        }

        for model_data in unique_models:
            try:
                model = self.upsert_model(tenant_id, model_data)

                if model.created_at == model.updated_at:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

            except Exception as e:
                logger.error(f"Failed to upsert model {model_data.get('model_name')}: {e}")
                stats['failed'] += 1

        logger.info(f"Complete: {stats['created']} created, {stats['updated']} updated, {stats['failed']} failed")

        # Warm cache after successful upsert
        if self.use_cache and self.cache:
            try:
                stored_models = self.list_models(tenant_id, use_cache=False)
                model_dicts = [
                    {
                        'provider': m.provider,
                        'model_name': m.model_name,
                        'context_window': m.context_window,
                        'input_price_per_token': m.input_price_per_token,
                        'output_price_per_token': m.output_price_per_token,
                        'capabilities': m.capabilities,
                        'provider_metadata': m.provider_metadata
                    }
                    for m in stored_models
                ]
                await self.cache.warm_cache(tenant_id, model_dicts)
                logger.info(f"Warmed cache with {len(model_dicts)} models for tenant {tenant_id}")
            except Exception as e:
                logger.warning(f"Failed to warm cache for tenant {tenant_id}: {e}")

        return stats

    def upsert_model(self, tenant_id: str, model_data: Dict[str, Any]) -> LLMModel:
        """
        Create or update a model in the database.

        Checks if a model exists (by tenant_id, provider, model_name).
        If exists: updates fields and sets updated_at
        If not exists: creates new LLMModel

        Args:
            tenant_id: Tenant identifier
            model_data: Dictionary with model fields (from transformer)

        Returns:
            LLMModel instance (created or updated)

        Example:
            >>> model_data = {
            ...     'provider': 'openai',
            ...     'model_name': 'gpt-4',
            ...     'context_window': 8192,
            ...     'input_price_per_token': 0.00003,
            ...     'output_price_per_token': 0.00006,
            ...     'capabilities': ['tools', 'vision'],
            ...     'provider_metadata': {'source': 'litellm'}
            ... }
            >>> model = service.upsert_model('tenant-123', model_data)
        """
        provider = model_data.get('provider')
        model_name = model_data.get('model_name')

        if not provider or not model_name:
            raise ValueError("Both 'provider' and 'model_name' are required")

        # Try to find existing model
        existing = (
            self.db.query(LLMModel)
            .filter(
                and_(
                    LLMModel.tenant_id == tenant_id,
                    LLMModel.provider == provider,
                    LLMModel.model_name == model_name
                )
            )
            .first()
        )

        if existing:
            # Update existing model
            existing.context_window = model_data.get('context_window')
            existing.input_price_per_token = model_data.get('input_price_per_token')
            existing.output_price_per_token = model_data.get('output_price_per_token')
            existing.capabilities = model_data.get('capabilities', [])
            existing.provider_metadata = model_data.get('provider_metadata', {})
            existing.last_refreshed_at = datetime.utcnow()

            logger.debug(f"Updated model: {provider}/{model_name}")
            return existing
        else:
            # Create new model
            new_model = LLMModel(
                tenant_id=tenant_id,
                provider=provider,
                model_name=model_name,
                context_window=model_data.get('context_window'),
                input_price_per_token=model_data.get('input_price_per_token'),
                output_price_per_token=model_data.get('output_price_per_token'),
                capabilities=model_data.get('capabilities', []),
                provider_metadata=model_data.get('provider_metadata', {}),
                last_refreshed_at=datetime.utcnow()
            )

            self.db.add(new_model)
            self.db.flush()

            logger.debug(f"Created model: {provider}/{model_name}")
            return new_model

    async def get_model(
        self,
        tenant_id: str,
        provider: str,
        model_name: str,
        use_cache: bool = True,
        include_deprecated: bool = False
    ) -> Optional[LLMModel]:
        """
        Retrieve a specific model by tenant, provider, and name.

        Uses cache-aside pattern:
        1. Try cache first (if enabled)
        2. On cache miss, query database
        3. Warm cache with result

        Args:
            tenant_id: Tenant identifier
            provider: Provider name (e.g., 'openai')
            model_name: Model name (e.g., 'gpt-4')
            use_cache: Enable cache lookup (default True)
            include_deprecated: Include deprecated models (default False)

        Returns:
            LLMModel instance or None if not found

        Example:
            >>> model = await service.get_model('tenant-123', 'openai', 'gpt-4')
            >>> if model:
            ...     print(f"Found: {model.model_name}")
        """
        # Try cache first (only for non-deprecated queries)
        if self.use_cache and use_cache and self.cache and not include_deprecated:
            try:
                cached = await self.cache.get_model(tenant_id, provider, model_name)
                if cached:
                    # Convert cached dict to LLMModel
                    return LLMModel(
                        tenant_id=tenant_id,
                        provider=cached.get('provider', provider),
                        model_name=cached.get('model_name', model_name),
                        context_window=cached.get('context_window'),
                        input_price_per_token=cached.get('input_price_per_token'),
                        output_price_per_token=cached.get('output_price_per_token'),
                        capabilities=cached.get('capabilities', []),
                        provider_metadata=cached.get('provider_metadata', {})
                    )
            except Exception as e:
                logger.warning(f"Cache get failed for {provider}/{model_name}: {e}")

        # Cache miss or disabled - query database
        query = self.db.query(LLMModel).filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.provider == provider,
                LLMModel.model_name == model_name
            )
        )

        # Filter out deprecated models unless explicitly requested
        if not include_deprecated:
            query = query.filter(LLMModel.is_deprecated == False)

        model = query.first()

        # Warm cache on database hit
        if model and self.use_cache and use_cache and self.cache:
            try:
                await self.cache.set_model(
                    tenant_id,
                    provider,
                    model_name,
                    {
                        'provider': model.provider,
                        'model_name': model.model_name,
                        'context_window': model.context_window,
                        'input_price_per_token': model.input_price_per_token,
                        'output_price_per_token': model.output_price_per_token,
                        'capabilities': model.capabilities,
                        'provider_metadata': model.provider_metadata
                    }
                )
            except Exception as e:
                logger.warning(f"Cache set failed for {provider}/{model_name}: {e}")

        return model

    async def list_models(
        self,
        tenant_id: str,
        provider: Optional[str] = None,
        include_deprecated: bool = False,
        use_cache: bool = True
    ) -> List[LLMModel]:
        """
        List all models for a tenant, optionally filtered by provider.

        Uses cache-aside pattern for performance.

        Args:
            tenant_id: Tenant identifier
            provider: Optional provider filter
            include_deprecated: Include deprecated models (default False)
            use_cache: Enable cache lookup (default True)

        Returns:
            List of LLMModel instances

        Example:
            >>> # List all active models
            >>> all_models = await service.list_models('tenant-123')
            >>>
            >>> # List only OpenAI models
            >>> openai_models = await service.list_models('tenant-123', 'openai')
            >>>
            >>> # List all models including deprecated
            >>> all_models = await service.list_models('tenant-123', include_deprecated=True)
        """
        # Try cache first (only for non-deprecated queries)
        if self.use_cache and use_cache and self.cache and not include_deprecated:
            try:
                cached_list = await self.cache.get_models_list(tenant_id, provider)
                if cached_list:
                    # Convert cached dicts to LLMModel instances
                    return [
                        LLMModel(
                            tenant_id=tenant_id,
                            provider=m.get('provider'),
                            model_name=m.get('model_name'),
                            context_window=m.get('context_window'),
                            input_price_per_token=m.get('input_price_per_token'),
                            output_price_per_token=m.get('output_price_per_token'),
                            capabilities=m.get('capabilities', []),
                            provider_metadata=m.get('provider_metadata', {})
                        )
                        for m in cached_list
                    ]
            except Exception as e:
                logger.warning(f"Cache list get failed for tenant {tenant_id}: {e}")

        # Cache miss or disabled - query database
        query = self.db.query(LLMModel).filter(LLMModel.tenant_id == tenant_id)

        if provider:
            query = query.filter(LLMModel.provider == provider)

        # Filter out deprecated models unless explicitly requested
        if not include_deprecated:
            query = query.filter(LLMModel.is_deprecated == False)

        models = query.all()

        # Warm cache on database hit
        if models and self.use_cache and use_cache and self.cache:
            try:
                model_dicts = [
                    {
                        'provider': m.provider,
                        'model_name': m.model_name,
                        'context_window': m.context_window,
                        'input_price_per_token': m.input_price_per_token,
                        'output_price_per_token': m.output_price_per_token,
                        'capabilities': m.capabilities,
                        'provider_metadata': m.provider_metadata
                    }
                    for m in models
                ]
                await self.cache.set_models_list(tenant_id, model_dicts, provider)
            except Exception as e:
                logger.warning(f"Cache list set failed for tenant {tenant_id}: {e}")

        return models

    def get_models_by_capability(
        self,
        tenant_id: str,
        capability: str,
        use_cache: bool = False
    ) -> List[LLMModel]:
        """
        Get all models that have a specific capability.

        Uses PostgreSQL JSONB contains operator (@>) for efficient querying.
        Note: Cache not used by default for complex JSONB queries.

        Args:
            tenant_id: Tenant identifier
            capability: Capability to filter by (e.g., 'vision', 'tools')
            use_cache: Enable cache lookup (default False - uses database)

        Returns:
            List of LLMModel instances with the capability

        Example:
            >>> # Get all models with vision capability
            >>> vision_models = service.get_models_by_capability('tenant-123', 'vision')
            >>>
            >>> # Get all models with tools/function_calling
            >>> tool_models = service.get_models_by_capability('tenant-123', 'tools')
        """
        # Complex JSONB queries always use database (not cached)
        return (
            self.db.query(LLMModel)
            .filter(
                and_(
                    LLMModel.tenant_id == tenant_id,
                    LLMModel.capabilities.contains([capability])
                )
            )
            .all()
        )

    def get_models_by_capabilities(
        self,
        tenant_id: str,
        capabilities: List[str],
        match_all: bool = False,
        use_cache: bool = False
    ) -> List[LLMModel]:
        """
        Get models matching one or more capabilities.

        Args:
            tenant_id: Tenant identifier
            capabilities: List of capabilities to match
            match_all: If True, require ALL capabilities; if False, match ANY
            use_cache: Enable cache lookup (default False - uses database)

        Returns:
            List of LLMModel instances

        Example:
            >>> # Models with vision AND tools
            >>> models = service.get_models_by_capabilities(
            ...     'tenant-123',
            ...     ['vision', 'tools'],
            ...     match_all=True
            ... )
            >>>
            >>> # Models with vision OR tools
            >>> models = service.get_models_by_capabilities(
            ...     'tenant-123',
            ...     ['vision', 'tools'],
            ...     match_all=False
            ... )
        """
        # Complex JSONB queries always use database (not cached)
        query = self.db.query(LLMModel).filter(LLMModel.tenant_id == tenant_id)

        if match_all:
            # Require ALL capabilities
            for cap in capabilities:
                query = query.filter(LLMModel.capabilities.contains([cap]))
        else:
            # Match ANY capability (use overlap operator)
            query = query.filter(LLMModel.capabilities.overlap(capabilities))

        return query.all()

    def delete_model(
        self,
        tenant_id: str,
        provider: str,
        model_name: str
    ) -> bool:
        """
        Delete a specific model from the registry.

        Args:
            tenant_id: Tenant identifier
            provider: Provider name
            model_name: Model name

        Returns:
            True if deleted, False if not found

        Example:
            >>> deleted = service.delete_model('tenant-123', 'openai', 'gpt-4')
            >>> if deleted:
            ...     print("Model deleted")
        """
        model = self.get_model(tenant_id, provider, model_name)

        if model:
            self.db.delete(model)
            logger.debug(f"Deleted model: {provider}/{model_name}")
            return True

        return False

    async def refresh_cache(self, tenant_id: str) -> Dict[str, int]:
        """
        Refresh the model cache with fresh data from database.

        Performs atomic swap to prevent race conditions:
        1. Query all models from database
        2. Convert to dict format
        3. Call cache.atomic_swap_registry()

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary with stats:
            {
                'swapped': int,
                'failed': int
            }

        Example:
            >>> stats = await service.refresh_cache('tenant-123')
            >>> print(f"Swapped {stats['swapped']} models")
        """
        if not self.use_cache or not self.cache:
            logger.warning(f"Caching disabled for tenant {tenant_id}")
            return {'swapped': 0, 'failed': 0}

        try:
            # Query all models from database
            models = self.list_models(tenant_id, use_cache=False)

            # Convert to dict format
            model_dicts = [
                {
                    'provider': m.provider,
                    'model_name': m.model_name,
                    'context_window': m.context_window,
                    'input_price_per_token': m.input_price_per_token,
                    'output_price_per_token': m.output_price_per_token,
                    'capabilities': m.capabilities,
                    'provider_metadata': m.provider_metadata
                }
                for m in models
            ]

            # Perform atomic swap
            await self.cache.atomic_swap_registry(tenant_id, model_dicts)

            logger.info(f"Cache refresh complete for tenant {tenant_id}: {len(model_dicts)} models")

            return {'swapped': len(model_dicts), 'failed': 0}

        except Exception as e:
            logger.error(f"Cache refresh failed for tenant {tenant_id}: {e}")
            return {'swapped': 0, 'failed': 1}

    def register_lux_model(
        self,
        tenant_id: str,
        enabled: bool = True
    ) -> Optional[LLMModel]:
        """
        Register or update the LUX model in the registry.

        LUX is a special computer-use model based on claude-3-5-sonnet-20241022.
        It has the unique computer_use capability for desktop automation tasks.

        Args:
            tenant_id: Tenant identifier for multi-tenancy
            enabled: Whether LUX is enabled for this tenant (default True)

        Returns:
            LLMModel instance for LUX or None if registration failed

        Example:
            >>> service = LLMRegistryService(db)
            >>> lux = service.register_lux_model('tenant-123')
            >>> print(f"LUX registered: {lux.model_name}")
        """
        if not enabled:
            logger.debug(f"LUX disabled for tenant {tenant_id}")
            return None

        lux_model_data = {
            'provider': 'anthropic',
            'model_name': 'claude-3-5-sonnet-20241022',
            'context_window': 200000,
            'input_price_per_token': 0.000003,
            'output_price_per_token': 0.000015,
            'capabilities': ['vision', 'tools', 'computer_use', 'agentic'],
            'provider_metadata': {
                'source': 'lux',
                'specialization': 'computer_use',
                'description': 'LUX computer use model for desktop automation'
            }
        }

        try:
            model = self.upsert_model(tenant_id, lux_model_data)
            # Ensure computer_use capability is synced to hybrid column
            if 'computer_use' not in model.capabilities:
                model.capabilities.append('computer_use')
            model.sync_capabilities()
            self.db.flush()
            logger.info(f"LUX model registered for tenant {tenant_id}")
            return model
        except Exception as e:
            logger.error(f"Failed to register LUX model for tenant {tenant_id}: {e}")
            return None

    def get_computer_use_models(
        self,
        tenant_id: str,
        use_cache: bool = False
    ) -> List[LLMModel]:
        """
        Get all models with computer_use capability.

        Args:
            tenant_id: Tenant identifier
            use_cache: Enable cache lookup (default False - uses database)

        Returns:
            List of LLMModel instances with computer_use capability

        Example:
            >>> models = service.get_computer_use_models('tenant-123')
            >>> for model in models:
            ...     print(f"{model.model_name} supports computer use")
        """
        return (
            self.db.query(LLMModel)
            .filter(
                and_(
                    LLMModel.tenant_id == tenant_id,
                    LLMModel.supports_computer_use == True
                )
            )
            .all()
        )

    async def invalidate_cache(self, tenant_id: str) -> int:
        """
        Invalidate all cached data for a tenant.

        Useful after bulk updates or deletions.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Number of keys deleted

        Example:
            >>> count = await service.invalidate_cache('tenant-123')
            >>> print(f"Invalidated {count} cache keys")
        """
        if not self.use_cache or not self.cache:
            logger.warning(f"Caching disabled for tenant {tenant_id}")
            return 0

        try:
            count = await self.cache.invalidate_tenant(tenant_id)
            logger.info(f"Invalidated {count} cache keys for tenant {tenant_id}")
            return count
        except Exception as e:
            logger.error(f"Cache invalidation failed for tenant {tenant_id}: {e}")
            return 0

    async def detect_and_add_new_models(
        self,
        tenant_id: str,
        fetched_models: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect and add new models from fetched API data.

        Compares fetched models against existing registry entries and adds
        any models not already present. New models automatically have their
        capabilities inferred from model name patterns.

        Args:
            tenant_id: Tenant identifier
            fetched_models: List of model dicts from fetchers

        Returns:
            Dict with results:
            {
                'new_models': int,
                'existing_models': int,
                'added': List[str],  # model names that were added
                'skipped': List[str]  # model names that already existed
            }
        """
        # Get existing models for tenant
        existing = self.db.query(LLMModel).filter(
            LLMModel.tenant_id == tenant_id
        ).all()

        # Create set of (provider, model_name) tuples for O(1) lookup
        existing_keys = {(m.provider, m.model_name) for m in existing}

        # Filter to new models only
        new_models = [
            m for m in fetched_models
            if (m.get('provider'), m.get('model_name')) not in existing_keys
        ]

        # Upsert each new model
        added = []
        for model_data in new_models:
            try:
                model = self.upsert_model(tenant_id, model_data)
                added.append(f"{model.provider}/{model.model_name}")
            except Exception as e:
                logger.error(f"Failed to add new model {model_data.get('model_name')}: {e}")

        return {
            'new_models': len(new_models),
            'existing_models': len(existing_keys),
            'added': added,
            'skipped': list(existing_keys)
        }

    def get_new_models_since(
        self,
        tenant_id: str,
        since: datetime
    ) -> List[LLMModel]:
        """Get models discovered since a given timestamp.

        Useful for monitoring new model additions and debugging sync jobs.

        Args:
            tenant_id: Tenant identifier
            since: Timestamp to filter from

        Returns:
            List of LLMModel objects discovered since the timestamp
        """
        return self.db.query(LLMModel).filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.discovered_at >= since
            )
        ).order_by(LLMModel.discovered_at.desc()).all()

    async def detect_deprecated_models(
        self,
        tenant_id: str,
        fetched_models: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect models that have been removed from provider APIs.

        Compares existing registry entries against freshly fetched models
        and flags any models that no longer appear in API responses.

        Args:
            tenant_id: Tenant identifier
            fetched_models: List of model dicts from current API fetch

        Returns:
            Dict with results:
            {
                'deprecated': int,
                'still_active': int,
                'deprecated_models': List[str],  # provider/model names
                'reason': str  # 'removed_from_api'
            }
        """
        # Get existing non-deprecated models for tenant
        existing = self.db.query(LLMModel).filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.is_deprecated == False
            )
        ).all()

        # Create set of (provider, model_name) from fetched data
        fetched_keys = {(m.get('provider'), m.get('model_name')) for m in fetched_models}

        # Find models in registry but not in fetched data
        deprecated = []
        for model in existing:
            if (model.provider, model.model_name) not in fetched_keys:
                deprecated.append(model)

        # Mark each as deprecated
        deprecated_names = []
        for model in deprecated:
            self.mark_model_deprecated(
                tenant_id,
                model.provider,
                model.model_name,
                reason='removed_from_api'
            )
            deprecated_names.append(f"{model.provider}/{model.model_name}")

            # Invalidate cache for deprecated model
            if self.cache:
                await self.cache.delete_model(tenant_id, model.provider, model.model_name)

        return {
            'deprecated': len(deprecated),
            'still_active': len(existing) - len(deprecated),
            'deprecated_models': deprecated_names,
            'reason': 'removed_from_api'
        }

    def mark_model_deprecated(
        self,
        tenant_id: str,
        provider: str,
        model_name: str,
        reason: str = 'manually_flagged'
    ) -> Optional[LLMModel]:
        """Mark a model as deprecated.

        Args:
            tenant_id: Tenant identifier
            provider: Model provider
            model_name: Model name
            reason: Reason for deprecation (default: manually_flagged)

        Returns:
            Updated LLMModel or None if not found
        """
        model = self.get_model(tenant_id, provider, model_name, use_cache=False)
        if not model:
            return None

        model.is_deprecated = True
        model.deprecated_at = datetime.utcnow()
        model.deprecation_reason = reason
        self.db.commit()

        logger.info(f"Marked {provider}/{model_name} as deprecated: {reason}")
        return model

    def restore_deprecated_model(
        self,
        tenant_id: str,
        provider: str,
        model_name: str
    ) -> Optional[LLMModel]:
        """Restore a previously deprecated model.

        Useful when a model reappears in API responses after being
        temporarily unavailable.

        Args:
            tenant_id: Tenant identifier
            provider: Model provider
            model_name: Model name

        Returns:
            Updated LLMModel or None if not found
        """
        model = self.db.query(LLMModel).filter(
            and_(
                LLMModel.tenant_id == tenant_id,
                LLMModel.provider == provider,
                LLMModel.model_name == model_name
            )
        ).first()

        if not model:
            return None

        model.is_deprecated = False
        model.deprecated_at = None
        model.deprecation_reason = None
        model.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Restored {provider}/{model_name} from deprecated status")
        return model

    async def close(self):
        """Close the fetcher's HTTP client."""
        await self.fetcher.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def update_quality_scores_from_lmsys(
        self,
        tenant_id: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Update model quality scores from LMSYS Chatbot Arena.

        Fetches latest leaderboard data from LMSYS, maps model names,
        and updates quality_score for matching models in the registry.

        Args:
            tenant_id: Tenant identifier
            use_cache: Use cached LMSYS data (default True)

        Returns:
            Dict with results:
            {
                'updated': int,  # Number of models updated
                'not_found': int,  # LMSYS models not in registry
                'skipped': int,  # Registry models not in LMSYS
                'scores': Dict[str, float]  # Model -> score mapping
            }

        Example:
            >>> result = await service.update_quality_scores_from_lmsys('tenant-123')
            >>> print(f"Updated {result['updated']} models with quality scores")
        """
        logger.info(f"Updating quality scores for tenant {tenant_id} from LMSYS")

        # Get existing models for tenant
        existing_models = self.list_models(
            tenant_id,
            include_deprecated=False,
            use_cache=False
        )

        registry_model_names = [m.model_name for m in existing_models]

        # Fetch LMSYS scores
        lmsys_client = LMSYSClient(cache_service=self.cache.cache if self.cache else None)
        try:
            lmsys_scores = await lmsys_client.fetch_leaderboard(use_cache=use_cache)

            # Map LMSYS names to registry names
            mapped_scores = await lmsys_client.map_scores_to_registry(
                lmsys_scores,
                registry_model_names
            )

            # Convert ELO to quality score
            client = lmsys_client  # Alias for conversion method

            # Update models with scores
            updated = 0
            for model in existing_models:
                if model.model_name in mapped_scores:
                    elo = mapped_scores[model.model_name]
                    quality_score = client.elo_to_quality_score(elo)

                    model.quality_score = quality_score
                    updated += 1

                    logger.debug(
                        f"Updated {model.model_name}: "
                        f"ELO={elo}, quality_score={quality_score:.1f}"
                    )

            self.db.commit()

            # Invalidate cache for tenant
            if self.cache:
                await self.cache.invalidate_tenant(tenant_id)

            logger.info(f"Updated {updated} model quality scores from LMSYS")

            return {
                'updated': updated,
                'not_found': len(lmsys_scores) - len(mapped_scores),
                'skipped': len(existing_models) - updated,
                'scores': {m.model_name: m.quality_score for m in existing_models if m.quality_score}
            }

        finally:
            await lmsys_client.close()

    def assign_heuristic_quality_scores(
        self,
        tenant_id: str,
        overwrite_existing: bool = False
    ) -> Dict[str, Any]:
        """Assign heuristic quality scores to models without LMSYS data.

        Calculates quality scores using model name patterns, version numbers,
        and context windows. Only assigns to models with NULL quality_score
        unless overwrite_existing is True.

        Args:
            tenant_id: Tenant identifier
            overwrite_existing: Overwrite existing quality scores

        Returns:
            Dict with results:
            {
                'assigned': int,  # Number of models assigned
                'skipped': int,  # Models with existing scores
                'scores': Dict[str, float]  # Model -> score mapping
            }
        """
        logger.info(f"Assigning heuristic quality scores for tenant {tenant_id}")

        scorer = HeuristicScorer()

        # Get models needing scores
        query = self.db.query(LLMModel).filter(LLMModel.tenant_id == tenant_id)

        if not overwrite_existing:
            query = query.filter(LLMModel.quality_score.is_(None))

        models = query.all()

        assigned = 0
        scores = {}

        for model in models:
            # Calculate heuristic score
            score = scorer.calculate_score(
                model_name=model.model_name,
                context_window=model.context_window,
                provider=model.provider
            )

            model.quality_score = score
            scores[model.model_name] = score
            assigned += 1

            logger.debug(
                f"Assigned heuristic score {score:.1f} to {model.model_name}"
            )

        self.db.commit()

        # Get skip count
        if overwrite_existing:
            skipped = 0
        else:
            skipped = self.db.query(LLMModel).filter(
                and_(
                    LLMModel.tenant_id == tenant_id,
                    LLMModel.quality_score.isnot(None)
                )
            ).count()

        logger.info(f"Assigned {assigned} heuristic quality scores")

        return {
            'assigned': assigned,
            'skipped': skipped,
            'scores': scores
        }

    async def get_top_models_by_quality(
        self,
        tenant_id: str,
        limit: int = 10,
        min_quality: float = 80.0
    ) -> List[LLMModel]:
        """Get top models by quality score.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of models to return
            min_quality: Minimum quality score (0-100)

        Returns:
            List of LLMModel instances sorted by quality_score DESC
        """
        return (
            self.db.query(LLMModel)
            .filter(
                and_(
                    LLMModel.tenant_id == tenant_id,
                    LLMModel.quality_score >= min_quality,
                    LLMModel.is_deprecated == False
                )
            )
            .order_by(LLMModel.quality_score.desc())
            .limit(limit)
            .all()
        )


def get_registry_service(db: Session) -> LLMRegistryService:
    """
    Factory function for creating LLMRegistryService instances.

    Useful for dependency injection in FastAPI routes.

    Args:
        db: SQLAlchemy database session

    Returns:
        LLMRegistryService instance

    Example:
        >>> from fastapi import Depends
        >>> from core.database import get_db
        >>>
        >>> def route(db: Session = Depends(get_db)):
        ...     service = get_registry_service(db)
        ...     models = service.list_models('tenant-123')
        ...     return models
    """
    return LLMRegistryService(db)
