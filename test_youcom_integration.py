#!/usr/bin/env python3
"""
Test script for You.com integration in ATOM
Tests the web search functionality with mock responses
"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_youcom_integration():
    """Test You.com web search integration"""
    print("Testing You.com integration...")
    
    # Mock the httpx client response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hits": [
            {
                "url": "https://example.com/test",
                "title": "Test Result",
                "description": "This is a test result from You.com",
                "relevance_score": 0.9
            }
        ],
        "answer": "This is a test answer from You.com"
    }
    
    # Mock environment variable
    with patch.dict(os.environ, {"YDC_API_KEY": "test_key_123"}):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            # Import and test after mocking
            from integrations.mcp_service import mcp_service
            
            result = await mcp_service.web_search("test query")
            
            # Verify result structure
            assert result["query"] == "test query"
            assert result["provider"] == "you.com"
            assert len(result["results"]) == 1
            assert result["results"][0]["url"] == "https://example.com/test"
            assert result["results"][0]["title"] == "Test Result"
            assert result["answer"] == "This is a test answer from You.com"
            
            print("✅ You.com integration test passed!")
            return True

async def test_tavily_fallback():
    """Test fallback to Tavily when You.com fails"""
    print("Testing Tavily fallback...")
    
    # Mock Tavily response
    mock_tavily_response = MagicMock()
    mock_tavily_response.status_code = 200
    mock_tavily_response.json.return_value = {
        "query": "test query",
        "results": [{"url": "https://tavily-example.com", "title": "Tavily Result"}],
        "answer": "Tavily answer"
    }
    
    # Mock You.com failure and Tavily success
    with patch.dict(os.environ, {"TAVILY_API_KEY": "test_tavily_key"}):
        with patch("httpx.AsyncClient") as mock_client:
            # First call (You.com) fails, second call (Tavily) succeeds
            async def mock_post(*args, **kwargs):
                if "api.you.com" in str(kwargs.get("url", args[0] if args else "")):
                    raise Exception("You.com API error")
                else:
                    return mock_tavily_response
            
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            from integrations.mcp_service import mcp_service
            
            result = await mcp_service.web_search("test query")
            
            # Verify fallback to Tavily
            assert result["provider"] == "tavily"
            assert result["query"] == "test query"
            
            print("✅ Tavily fallback test passed!")
            return True

async def test_no_api_keys():
    """Test behavior when no API keys are configured"""
    print("Testing no API keys scenario...")
    
    # Clear all search-related env vars
    env_patch = {k: None for k in ["YDC_API_KEY", "TAVILY_API_KEY"] if k in os.environ}
    
    with patch.dict(os.environ, env_patch, clear=False):
        from integrations.mcp_service import mcp_service
        
        result = await mcp_service.web_search("test query")
        
        # Verify error response
        assert result["query"] == "test query"
        assert result["results"] == []
        assert result["answer"] is None
        assert "error" in result
        assert "not configured" in result["error"]
        
        print("✅ No API keys test passed!")
        return True

def test_byok_provider_config():
    """Test that You.com is properly configured in BYOK providers"""
    print("Testing BYOK provider configuration...")
    
    from api.byok_routes import get_ai_providers
    
    providers = get_ai_providers()
    youcom_provider = None
    
    for provider in providers:
        if provider.id == "youcom":
            youcom_provider = provider
            break
    
    assert youcom_provider is not None, "You.com provider not found in BYOK configuration"
    assert youcom_provider.name == "You.com"
    assert youcom_provider.api_key_env_var == "YDC_API_KEY"
    assert "search" in youcom_provider.supported_tasks
    assert youcom_provider.base_url == "https://api.you.com"
    
    print("✅ BYOK provider configuration test passed!")
    return True

async def main():
    """Run all tests"""
    print("🔍 Running You.com integration tests...\n")
    
    try:
        # Test synchronous BYOK config first
        test_byok_provider_config()
        print()
        
        # Test async web search functionality
        await test_youcom_integration()
        print()
        
        await test_tavily_fallback()
        print()
        
        await test_no_api_keys()
        print()
        
        print("🎉 All tests passed! You.com integration is working correctly.")
        return 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)