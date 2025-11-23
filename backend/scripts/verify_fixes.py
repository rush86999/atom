import sys
import os
import asyncio
import jwt
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def verify_asana_token_storage():
    print("\nTesting Asana Token Storage...")
    from integrations.asana_routes import set_access_token, get_access_token, _token_store
    
    user_id = "test_user_123"
    token = "test_token_abc"
    
    # Test setting token
    await set_access_token(token=token, user_id=user_id)
    print(f"  ✅ Set token for {user_id}")
    
    # Test getting token
    retrieved_token = await get_access_token(user_id=user_id)
    if retrieved_token == token:
        print(f"  ✅ Retrieved correct token: {retrieved_token}")
    else:
        print(f"  ❌ Failed to retrieve token. Got: {retrieved_token}")

    # Test default
    default_token = await get_access_token(user_id="unknown_user")
    if default_token == "mock_access_token_placeholder":
        print(f"  ✅ Retrieved default placeholder for unknown user")
    else:
        print(f"  ❌ Failed default behavior. Got: {default_token}")

async def verify_jwt_auth():
    print("\nTesting JWT Verification...")
    from integrations.atom_communication_memory_production_api import atom_memory_production_api
    
    secret = "your-secret-key-here-change-in-production"
    os.environ["SECRET_KEY"] = secret
    
    # Create valid token
    payload = {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)}
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    credentials = MagicMock()
    credentials.credentials = token
    
    try:
        result = atom_memory_production_api.verify_token(credentials)
        if result == token:
            print(f"  ✅ Valid token verified successfully")
    except Exception as e:
        print(f"  ❌ Valid token failed verification: {e}")
        
    # Create expired token
    payload_expired = {"sub": "user123", "exp": datetime.utcnow() - timedelta(hours=1)}
    token_expired = jwt.encode(payload_expired, secret, algorithm="HS256")
    credentials.credentials = token_expired
    
    try:
        atom_memory_production_api.verify_token(credentials)
        print(f"  ❌ Expired token should have failed")
    except Exception as e:
        if "Token has expired" in str(e.detail):
             print(f"  ✅ Expired token correctly rejected")
        else:
             print(f"  ❌ Unexpected error for expired token: {e}")

async def main():
    await verify_asana_token_storage()
    await verify_jwt_auth()

if __name__ == "__main__":
    asyncio.run(main())
