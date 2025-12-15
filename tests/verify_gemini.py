
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

async def verify_google_integration():
    """Verify Google Gemini integration by mocking the API call"""
    print("🧪 Verifying Google Gemini Integration...")
    
    # Mock environment variable
    os.environ["GOOGLE_API_KEY"] = "mock_google_key"
    
    try:
        from enhanced_ai_workflow_endpoints import RealAIWorkflowService
        
        # Initialize service
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        # Mock the aiohttp session and response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = asyncio.Future()
        mock_response.json.return_value.set_result({
            "candidates": [{
                "content": {
                    "parts": [{"text": "{\"intent\": \"CREATE_WORKFLOW\", \"confidence\": 0.9}"}]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "totalTokenCount": 30
            }
        })
        
        # Mock context manager for response
        mock_context = MagicMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        
        # Patch the post method on the session
        service.http_sessions['google'].post = MagicMock(return_value=mock_context)
        
        # Test call_google_api
        print("   Testing call_google_api...")
        result = await service.call_google_api("Create a workflow")
        
        if result['provider'] == 'google' and result['confidence'] == 0.88:
            print("   ✅ call_google_api successful")
            print(f"   Output: {result['content']}")
        else:
            print(f"   ❌ call_google_api failed: {result}")
            
        # Test process_with_nlu with google provider
        print("   Testing process_with_nlu(provider='google')...")
        nlu_result = await service.process_with_nlu("Create a workflow", provider="google")
        
        if nlu_result['ai_provider_used'] == 'google':
             print("   ✅ process_with_nlu successful")
        else:
             print(f"   ❌ process_with_nlu failed. Provider used: {nlu_result.get('ai_provider_used')}")

        await service.cleanup_sessions()
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_google_integration())
