"""
OAuth Configuration Verification Script
Tests that OAuth credentials are properly configured for high-value integrations
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def verify_oauth_config():
    """Verify OAuth credentials are configured correctly"""
    
    integrations = {
        "Salesforce": {
            "client_id": os.getenv("SALESFORCE_CLIENT_ID"),
            "client_secret": os.getenv("SALESFORCE_CLIENT_SECRET"),
            "redirect_uri": os.getenv("SALESFORCE_REDIRECT_URI"),
            "value": "$100K/year"
        },
        "HubSpot": {
            "client_id": os.getenv("HUBSPOT_CLIENT_ID"),
            "client_secret": os.getenv("HUBSPOT_CLIENT_SECRET"),
            "value": "$88K/year"
        },
        "Zoom": {
            "client_id": os.getenv("ZOOM_CLIENT_ID"),
            "client_secret": os.getenv("ZOOM_CLIENT_SECRET"),
            "redirect_uri": os.getenv("ZOOM_REDIRECT_URI"),
            "value": "$32K/year"
        },
        "QuickBooks": {
            "client_id": os.getenv("QUICKBOOKS_CLIENT_ID"),
            "client_secret": os.getenv("QUICKBOOKS_CLIENT_SECRET"),
            "redirect_uri": os.getenv("QUICKBOOKS_REDIRECT_URI"),
            "value": "$35K/year"
        }
    }
    
    print("="*70)
    print("OAuth Credentials Verification Report")
    print("="*70)
    print()
    
    total_configured = 0
    total_value = 0
    
    for name, creds in integrations.items():
        client_id_ok = creds["client_id"] and not creds["client_id"].startswith("your-")
        client_secret_ok = creds["client_secret"] and not creds["client_secret"].startswith("your-")
        
        all_ok = client_id_ok and client_secret_ok
        
        status = "✅ CONFIGURED" if all_ok else "❌ MISSING"
        
        print(f"{name} ({creds['value']}): {status}")
        
        if all_ok:
            total_configured += 1
            # Parse value (remove $, K/year, convert to number)
            value_str = creds['value'].replace('$', '').replace('K/year', '').strip()
            total_value += int(value_str)
            
            print(f"  └─ Client ID: {creds['client_id'][:20]}...")
            if creds.get("redirect_uri"):
                print(f"  └─ Redirect URI: {creds['redirect_uri']}")
        else:
            if not client_id_ok:
                print(f"  └─ ❌ Client ID missing or placeholder")
            if not client_secret_ok:
                print(f"  └─ ❌ Client Secret missing or placeholder")
        
        print()
    
    print("="*70)
    print(f"Summary: {total_configured}/4 integrations configured")
    print(f"Business Value Unlocked: ${total_value}K/year")
    print("="*70)
    print()
    
    if total_configured == 4:
        print("🎉 All high-value OAuth integrations are configured!")
        print()
        print("Next Steps:")
        print("1. Test OAuth flow: http://localhost:3000/auth/salesforce/callback")
        print("2. Verify token storage and refresh")
        print("3. Test API endpoints with authenticated requests")
        return True
    else:
        print("⚠️  Some integrations still need configuration")
        print("   Check .env file and update placeholder values")
        return False

if __name__ == "__main__":
    verify_oauth_config()
