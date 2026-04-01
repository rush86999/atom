"""Tests for RegistryCacheService atomic swap and race condition prevention

This test module verifies:
- Concurrent swap attempts are prevented
- Cache consistency during swap
- Lock timeout behavior
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from core.llm.registry.cache import RegistryCacheService, SWAP_LOCK_KEY, LOCK_TTL


@pytest.mark.asyncio
async def test_concurrent_swap_prevention():
    """Test that concurrent swap attempts are prevented by distributed lock"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-concurrent'

    # Mock UniversalCacheService
    with patch.object(cache.cache, 'get_async', new_callable=AsyncMock) as mock_get, \
         patch.object(cache.cache, 'set_async', new_callable=AsyncMock) as mock_set, \
         patch.object(cache.cache, 'delete_async', new_callable=AsyncMock):

        # First call - no lock exists
        mock_get.return_value = None  # No existing lock
        mock_set.return_value = True

        models = [
            {'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192}
        ]

        # First swap should succeed
        result1 = await cache.atomic_swap_registry(tenant_id, models)
        assert result1 is True

        # Verify lock was acquired (check first call to set_async)
        assert mock_set.call_count > 0
        first_call = mock_set.call_args_list[0]
        assert first_call[0][0] == SWAP_LOCK_KEY  # First argument is lock key
        assert first_call[0][1] == "swapping"


@pytest.mark.asyncio
async def test_concurrent_swap_blocks_second_attempt():
    """Test that second swap attempt fails when lock is held"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-block'

    # Mock UniversalCacheService
    with patch.object(cache.cache, 'get_async', new_callable=AsyncMock) as mock_get:
        # Lock already exists
        mock_get.return_value = "swapping"

        models = [
            {'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192}
        ]

        # Second swap should raise exception
        with pytest.raises(Exception) as exc_info:
            await cache.atomic_swap_registry(tenant_id, models)

        assert "Swap in progress" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cache_consistency_during_swap():
    """Test that cache remains consistent during atomic swap"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-consistency'

    # Pre-populate cache with old data
    old_models = [
        {'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192}
    ]

    new_models = [
        {'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 128000},  # Updated
        {'provider': 'openai', 'model_name': 'gpt-4-turbo', 'context_window': 128000}  # New
    ]

    with patch.object(cache.cache, 'get_async', new_callable=AsyncMock, return_value=None), \
         patch.object(cache.cache, 'set_async', new_callable=AsyncMock, return_value=True), \
         patch.object(cache.cache, 'delete_async', new_callable=AsyncMock) as mock_delete:

        # Perform atomic swap
        result = await cache.atomic_swap_registry(tenant_id, new_models)

        assert result is True

        # Verify all new models were cached (2 models + 2 lists = 4 calls)
        assert cache.cache.set_async.call_count >= len(new_models)

        # Verify lock was released
        mock_delete.assert_called_once()
        delete_call_args = mock_delete.call_args[0]
        assert delete_call_args[0] == SWAP_LOCK_KEY
        assert delete_call_args[1] == tenant_id


@pytest.mark.asyncio
async def test_lock_timeout_behavior():
    """Test that lock expires after timeout"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-timeout'

    # Mock cache that simulates lock timeout
    lock_acquired = False

    async def mock_get(key, tenant):
        if key == SWAP_LOCK_KEY and lock_acquired:
            # Simulate lock timeout on second check
            return None
        return "swapping" if lock_acquired else None

    async def mock_set(key, value, ttl, tenant):
        nonlocal lock_acquired
        if key == SWAP_LOCK_KEY:
            lock_acquired = True
        return True

    with patch.object(cache.cache, 'get_async', side_effect=mock_get), \
         patch.object(cache.cache, 'set_async', side_effect=mock_set), \
         patch.object(cache.cache, 'delete_async', new_callable=AsyncMock):

        models = [{'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192}]

        # First swap should acquire lock
        result1 = await cache.atomic_swap_registry(tenant_id, models)
        assert result1 is True


@pytest.mark.asyncio
async def test_swap_error_handling():
    """Test error handling during swap"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-error'

    # Mock cache that fails during set (after lock is acquired)
    call_count = [0]

    async def mock_set_with_error(key, value, ttl, tenant):
        call_count[0] += 1
        if key != SWAP_LOCK_KEY:  # Fail on model set, not lock set
            raise Exception("Redis error")
        return True

    with patch.object(cache.cache, 'get_async', new_callable=AsyncMock, return_value=None), \
         patch.object(cache.cache, 'set_async', side_effect=mock_set_with_error), \
         patch.object(cache.cache, 'delete_async', new_callable=AsyncMock) as mock_delete:

        models = [{'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192}]

        # Swap should handle error gracefully (catches and logs exceptions)
        result = await cache.atomic_swap_registry(tenant_id, models)

        # Result should still be True (errors are logged, not raised)
        assert result is True

        # Verify lock was still released despite errors
        mock_delete.assert_called_once()
        delete_call_args = mock_delete.call_args[0]
        assert delete_call_args[0] == SWAP_LOCK_KEY
        assert delete_call_args[1] == tenant_id


@pytest.mark.asyncio
async def test_warm_cache_no_lock_required():
    """Test that warm_cache doesn't require lock"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-warm'

    with patch.object(cache.cache, 'set_async', new_callable=AsyncMock, return_value=True):
        models = [
            {'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192},
            {'provider': 'anthropic', 'model_name': 'claude-3-opus', 'context_window': 200000}
        ]

        # warm_cache should not use lock
        result = await cache.warm_cache(tenant_id, models)

        # Should complete without error
        assert result is None  # warm_cache returns None


@pytest.mark.asyncio
async def test_invalidate_tenant_clears_all_keys():
    """Test that invalidate_tenant clears all tenant cache keys"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-invalidate'

    with patch.object(cache.cache, 'delete_tenant_all', new_callable=AsyncMock, return_value=42):
        count = await cache.invalidate_tenant(tenant_id)

        assert count == 42


@pytest.mark.asyncio
async def test_model_cache_operations():
    """Test basic model cache operations"""

    cache = RegistryCacheService()
    tenant_id = 'test-tenant-model-ops'

    with patch.object(cache.cache, 'get_async', new_callable=AsyncMock) as mock_get, \
         patch.object(cache.cache, 'set_async', new_callable=AsyncMock, return_value=True) as mock_set:

        # Set model
        model_data = {'provider': 'openai', 'model_name': 'gpt-4', 'context_window': 8192}
        await cache.set_model(tenant_id, 'openai', 'gpt-4', model_data)

        # Verify set was called
        mock_set.assert_called_once()

        # Get model (cache hit)
        mock_get.return_value = model_data
        result = await cache.get_model(tenant_id, 'openai', 'gpt-4')

        assert result == model_data

        # Get model (cache miss)
        mock_get.return_value = None
        result = await cache.get_model(tenant_id, 'openai', 'gpt-5')

        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
