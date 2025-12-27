
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock env vars
os.environ["APP_DOMAIN"] = "localhost:3000"
os.environ["URL_SCHEME"] = "http"

from backend.integrations.universal.auth_handler import universal_auth, OAuthState

async def test_universal_auth():
    print("Testing Universal Auth Handler...")
    
    # 1. Test URL Generation
    state = OAuthState(
        integration_type="native",
        service_id="mock_service",
        user_id="user_123",
        extra_data={"foo": "bar"}
    )
    
    auth_url = universal_auth.generate_oauth_url(
        auth_url="https://provider.com/oauth/authorize",
        client_id="mock_client_id",
        scopes=["read", "write"],
        state_payload=state
    )
    
    print(f"\n[OK] Generated Auth URL: {auth_url}")
    assert "provider.com" in auth_url
    assert "client_id=mock_client_id" in auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fapi%2Fv1%2Fintegrations%2Funiversal%2Fcallback" in auth_url
    assert "state=" in auth_url
    
    # Extract state param from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(auth_url)
    params = urllib.parse.parse_qs(parsed.query)
    encrypted_state = params['state'][0]
    
    # 2. Test Callback Processing
    print(f"\nSimulating Callback with state: {encrypted_state[:20]}...")
    
    result = await universal_auth.handle_callback(
        code="mock_auth_code",
        state=encrypted_state
    )
    
    print("\n[OK] Callback Result:", result)
    assert result["code"] == "mock_auth_code"
    assert result["state"].service_id == "mock_service"
    assert result["state"].user_id == "user_123"
    assert result["state"].extra_data["foo"] == "bar"
    
    print("\n✅ Universal OAuth Handler Verified Successfully")

if __name__ == "__main__":
    asyncio.run(test_universal_auth())
