
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from core.unified_search_endpoints import hybrid_search, SearchRequest

async def test_fallback():
    print("Testing search fallback...")
    
    # Mock handler to return None for db
    with patch('core.unified_search_endpoints.get_lancedb_handler') as mock_get:
        mock_handler = MagicMock()
        mock_handler.db = None
        mock_get.return_value = mock_handler
        
        req = SearchRequest(query="test", user_id="user1")
        
        try:
            response = await hybrid_search(req)
            print(f"Response success: {response.success}")
            print(f"Results count: {len(response.results)}")
            
            if response.success and len(response.results) == 0:
                print("✅ Fallback worked: Returned empty results instead of crashing.")
            else:
                print("❌ Fallback failed: Unexpected response format.")
                
        except Exception as e:
            print(f"❌ Fallback failed: Exception raised: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_fallback())
