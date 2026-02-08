from datetime import datetime
import json

from core.token_storage import token_storage

print("Checking Token Storage for 'google'...")
token = token_storage.get_token("google")

if token:
    print("\n✅ Google Token FOUND!")
    print(f"Scopes: {token.get('scopes')}")
    print(f"Expires At: {token.get('expires_at')}")
    print(f"Last Updated: {token.get('updated_at')}")
    
    # Check if expired
    if token_storage.is_token_expired("google"):
        print("⚠️ Token is EXPIRED (Refresh required)")
    else:
        print("✅ Token is VALID")
else:
    print("\n❌ No Google Token found.")
    print("Please complete the auth flow via the frontend.")
