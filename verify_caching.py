
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Mock models module BEFORE importing workflow_engine to avoid SQLAlchemy table definition errors
mock_models = MagicMock()
mock_catalog = MagicMock()
mock_models.IntegrationCatalog = mock_catalog
sys.modules['backend.core.models'] = mock_models
sys.modules['core.models'] = mock_models

# Mock cache module slightly to ensure we can control it easily, 
# although we will patch the instance in the test function
mock_cache_module = MagicMock()
sys.modules['core.cache'] = mock_cache_module

from backend.core.workflow_engine import WorkflowEngine, token_storage

async def verify_caching():
    print("Verifying Backend Caching (Phase 22)...")
    
    # 1. Mock DB Session and Catalog Item
    mock_db_session = MagicMock()
    mock_catalog_item = MagicMock()
    mock_catalog_item.id = "mock_service"
    mock_catalog_item.actions = [
        {
            "name": "mock_action",
            "method": "POST",
            "url": "https://api.mock_service.com/data",
            "description": "Mock action"
        }
    ]
    
    # Mock query chain
    mock_query = mock_db_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.return_value = mock_catalog_item
    
    # Update the query to return our mock item when queried with the mock class
    mock_db_session.query(mock_catalog).filter.return_value.first.return_value = mock_catalog_item
    
    # 2. Mock Cache Instance
    mock_cache_instance = AsyncMock()
    
    # 3. Mock HTTPX
    mock_httpx = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = MagicMock()
    async_client_mock = AsyncMock()
    async_client_mock.request.return_value = mock_response
    async_client_mock.__aenter__.return_value = async_client_mock
    async_client_mock.__aexit__.return_value = None
    mock_httpx.AsyncClient.return_value = async_client_mock

    # Patch modules
    with patch('backend.core.workflow_engine.SessionLocal', return_value=mock_db_session), \
         patch('backend.core.workflow_engine.httpx', mock_httpx), \
         patch('core.cache.cache', mock_cache_instance):
         
        engine = WorkflowEngine()
        
        # Test 1: Cache Miss
        print("\n--- Test 1: Cache Miss (Should hit DB) ---")
        mock_cache_instance.get.return_value = None # Cache miss
        
        await engine._execute_generic_action("mock_service", "mock_action", {})
        
        # Verify DB was queried
        # Note: SessionLocal() is called, then db.query...
        assert mock_db_session.query.called, "DB should be queried on cache miss"
        # Verify Cache Set was called
        assert mock_cache_instance.set.called, "Cache should be set after DB fetch"
        print("PASS: DB queried and Cache set.")

        # Test 2: Cache Hit
        print("\n--- Test 2: Cache Hit (Should skip DB) ---")
        mock_db_session.reset_mock()
        mock_cache_instance.set.reset_mock()
        
        # Setup cache hit return value
        mock_cache_instance.get.return_value = {
            "id": "mock_service",
            "actions": [
                {
                    "name": "mock_action",
                    "method": "POST",
                    "url": "https://api.mock_service.com/data"
                }
            ]
        }
        
        await engine._execute_generic_action("mock_service", "mock_action", {})
        
        # Verify DB was NOT queried
        assert not mock_db_session.query.called, "DB should NOT be queried on cache hit"
        print("PASS: DB skipped on cache hit.")
        
    print("\nCaching Verification: PASSED")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_caching())
