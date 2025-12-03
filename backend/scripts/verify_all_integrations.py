
import sys
import os
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Import integration services/clients where available
try:
    from integrations.salesforce_routes import get_salesforce_client_from_env
except ImportError:
    get_salesforce_client_from_env = None

try:
    from integrations.hubspot_routes import HubSpotService
except ImportError:
    HubSpotService = None

async def verify_integrations():
    print("\n--- Comprehensive Integration Verification ---")
    
    results = {}

    # 1. Salesforce
    print("\n1. Salesforce:")
    sf_vars = ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET"]
    sf_missing = [v for v in sf_vars if not os.getenv(v)]
    if sf_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(sf_missing)}")
        results["Salesforce"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if get_salesforce_client_from_env:
            try:
                client = get_salesforce_client_from_env()
                if client:
                    print("   ✅ Client Instantiated")
                    results["Salesforce"] = "Success"
                else:
                    print("   ❌ Client Instantiation Failed")
                    results["Salesforce"] = "Failed (Client)"
            except Exception as e:
                print(f"   ❌ Client Error: {e}")
                results["Salesforce"] = f"Failed ({e})"
        else:
            print("   ⚠️ Client Factory Not Found")
            results["Salesforce"] = "Partial (Env Only)"

    # 2. HubSpot
    print("\n2. HubSpot:")
    hs_vars = ["HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET"]
    hs_missing = [v for v in hs_vars if not os.getenv(v)]
    if hs_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(hs_missing)}")
        results["HubSpot"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if HubSpotService:
            try:
                service = HubSpotService()
                print("   ✅ Service Instantiated")
                results["HubSpot"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["HubSpot"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["HubSpot"] = "Partial (Env Only)"

    # 3. Zendesk
    print("\n3. Zendesk:")
    zd_vars = ["ZENDESK_CLIENT_ID", "ZENDESK_CLIENT_SECRET", "ZENDESK_SUBDOMAIN"]
    zd_missing = [v for v in zd_vars if not os.getenv(v)]
    if zd_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(zd_missing)}")
        results["Zendesk"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["Zendesk"] = "Success (Env Only)"

    # 4. Intercom
    print("\n4. Intercom:")
    ic_vars = ["INTERCOM_CLIENT_ID", "INTERCOM_CLIENT_SECRET"]
    ic_missing = [v for v in ic_vars if not os.getenv(v)]
    if ic_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(ic_missing)}")
        results["Intercom"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["Intercom"] = "Success (Env Only)"

    # 5. GitLab
    print("\n5. GitLab:")
    gl_vars = ["GITLAB_CLIENT_ID", "GITLAB_CLIENT_SECRET"]
    gl_missing = [v for v in gl_vars if not os.getenv(v)]
    if gl_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(gl_missing)}")
        results["GitLab"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["GitLab"] = "Success (Env Only)"

    # 6. Bitbucket
    print("\n6. Bitbucket:")
    bb_vars = ["BITBUCKET_CLIENT_ID", "BITBUCKET_CLIENT_SECRET"]
    bb_missing = [v for v in bb_vars if not os.getenv(v)]
    if bb_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(bb_missing)}")
        results["Bitbucket"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["Bitbucket"] = "Success (Env Only)"

    # 7. Mailchimp
    print("\n7. Mailchimp:")
    mc_vars = ["MAILCHIMP_CLIENT_ID", "MAILCHIMP_CLIENT_SECRET"]
    mc_missing = [v for v in mc_vars if not os.getenv(v)]
    if mc_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(mc_missing)}")
        results["Mailchimp"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["Mailchimp"] = "Success (Env Only)"

    # 8. Xero
    print("\n8. Xero:")
    xr_vars = ["XERO_CLIENT_ID", "XERO_CLIENT_SECRET"]
    xr_missing = [v for v in xr_vars if not os.getenv(v)]
    if xr_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(xr_missing)}")
        results["Xero"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["Xero"] = "Success (Env Only)"

    # 9. Shopify
    print("\n9. Shopify:")
    sh_vars = ["SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_SHOP_NAME"]
    sh_missing = [v for v in sh_vars if not os.getenv(v)]
    if sh_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(sh_missing)}")
        results["Shopify"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        results["Shopify"] = "Success (Env Only)"

    print("\n--- Summary ---")
    for service, status in results.items():
        print(f"{service}: {status}")

if __name__ == "__main__":
    asyncio.run(verify_integrations())
