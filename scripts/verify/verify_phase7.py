import asyncio
import os
import sys
import httpx

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_phase7():
    print("--- Phase 7 Verification: Additional Platform Integration ---")
    
    from core.lazy_integration_registry import load_integration
    from enhanced_workflow_api import enhanced_workflow_api, IntelligenceAnalyzeRequest, ai_service
    
    # Mock AI Service to avoid BYOK provider errors during unit test
    if ai_service:
        async def mock_analyze(*args, **kwargs):
            return "Mock analysis result"
        ai_service.analyze_text = mock_analyze
    
    # 1. Test Route Loading & Health Endpoints
    platforms = ["telegram", "whatsapp", "zoom"]
    print("\n1. Testing Route Loading & Health Endpoints...")
    
    for platform in platforms:
        router = load_integration(platform)
        if router:
            print(f"✓ {platform.capitalize()} router loaded successfully")
            # We can't easily test the health endpoint without a running server, 
            # but we've verified the registration and imports.
            # Let's check some router attributes to be sure it's the right one.
            if hasattr(router, "prefix"):
                print(f"  Prefix: {router.prefix}")
        else:
            print(f"✗ Failed to load {platform} router")

    # 2. Test Intelligence Suggesions
    print("\n2. Testing Intelligence Suggestions...")
    test_cases = [
        ("Send a telegram message to the team", "telegram"),
        ("Message me on WhatsApp", "whatsapp"),
        ("Start a zoom meeting", "zoom")
    ]
    
    for text, expected_service in test_cases:
        request = IntelligenceAnalyzeRequest(text=text)
        result = await enhanced_workflow_api.analyze_workflow_intent(request)
        
        found = False
        for suggestion in result.get("routing_suggestions", []):
            if suggestion.get("primary") == expected_service:
                print(f"✓ Found correct suggestion for '{text}': {expected_service}")
                found = True
                break
        
        if not found:
            print(f"✗ Failed to find correct suggestion for '{text}'. Got: {[s.get('primary') for s in result.get('routing_suggestions', [])]}")

if __name__ == "__main__":
    asyncio.run(test_phase7())
