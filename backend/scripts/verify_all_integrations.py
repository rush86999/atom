
import asyncio
import os
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

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

try:
    from integrations.bitbucket_service import BitbucketService
except ImportError:
    BitbucketService = None

try:
    from integrations.intercom_service import IntercomService
except ImportError:
    IntercomService = None

try:
    from integrations.mailchimp_service import MailchimpService
except ImportError:
    MailchimpService = None

try:
    from integrations.gitlab_service import GitLabService
except ImportError:
    GitLabService = None

try:
    from integrations.xero_service import XeroService
except ImportError:
    XeroService = None

try:
    from integrations.shopify_service import ShopifyService
except ImportError:
    ShopifyService = None

try:
    from integrations.calendly_service import CalendlyService
except ImportError:
    CalendlyService = None

try:
    from integrations.zendesk_service import ZendeskService
except ImportError:
    ZendeskService = None

try:
    from integrations.dropbox_service import DropboxService
except ImportError:
    DropboxService = None

try:
    from integrations.discord_service import DiscordService
except ImportError:
    DiscordService = None

async def verify_integrations():
    print("\n--- Comprehensive Integration Verification ---")
    
    results = {}

    # 1. Salesforce
    print("\n1. Salesforce:")
    sf_vars = [
        "SALESFORCE_CLIENT_ID", 
        "SALESFORCE_CLIENT_SECRET", 
        "SALESFORCE_USERNAME", 
        "SALESFORCE_PASSWORD", 
        "SALESFORCE_SECURITY_TOKEN"
    ]
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
        if IntercomService:
            try:
                service = IntercomService()
                print("   ✅ Service Instantiated")
                results["Intercom"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["Intercom"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["Intercom"] = "Partial (Env Only)"

    # 5. GitLab
    print("\n5. GitLab:")
    gl_vars = ["GITLAB_CLIENT_ID", "GITLAB_CLIENT_SECRET"]
    gl_missing = [v for v in gl_vars if not os.getenv(v)]
    if gl_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(gl_missing)}")
        results["GitLab"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if GitLabService:
            try:
                service = GitLabService()
                print("   ✅ Service Instantiated")
                results["GitLab"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["GitLab"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["GitLab"] = "Partial (Env Only)"

    # 6. Bitbucket
    print("\n6. Bitbucket:")
    bb_vars = ["BITBUCKET_CLIENT_ID", "BITBUCKET_CLIENT_SECRET"]
    bb_missing = [v for v in bb_vars if not os.getenv(v)]
    if bb_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(bb_missing)}")
        results["Bitbucket"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if BitbucketService:
            try:
                service = BitbucketService()
                print("   ✅ Service Instantiated")
                results["Bitbucket"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["Bitbucket"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["Bitbucket"] = "Partial (Env Only)"

    # 7. Mailchimp
    print("\n7. Mailchimp:")
    mc_vars = ["MAILCHIMP_CLIENT_ID", "MAILCHIMP_CLIENT_SECRET"]
    mc_missing = [v for v in mc_vars if not os.getenv(v)]
    if mc_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(mc_missing)}")
        results["Mailchimp"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if MailchimpService:
            try:
                service = MailchimpService()
                print("   ✅ Service Instantiated")
                results["Mailchimp"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["Mailchimp"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["Mailchimp"] = "Partial (Env Only)"

    # 8. Xero
    print("\n8. Xero:")
    xr_vars = ["XERO_CLIENT_ID", "XERO_CLIENT_SECRET"]
    xr_missing = [v for v in xr_vars if not os.getenv(v)]
    if xr_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(xr_missing)}")
        results["Xero"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if XeroService:
            try:
                service = XeroService()
                print("   ✅ Service Instantiated")
                results["Xero"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["Xero"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["Xero"] = "Partial (Env Only)"

    # 9. Shopify
    print("\n9. Shopify:")
    sh_vars = ["SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_SHOP_NAME"]
    sh_missing = [v for v in sh_vars if not os.getenv(v)]
    if sh_missing:
        print(f"   ❌ Missing Env Vars: {', '.join(sh_missing)}")
        results["Shopify"] = "Failed (Missing Env)"
    else:
        print("   ✅ Env Vars Present")
        if ShopifyService:
            try:
                service = ShopifyService()
                print("   ✅ Service Instantiated")
                results["Shopify"] = "Success"
            except Exception as e:
                print(f"   ❌ Service Error: {e}")
                results["Shopify"] = f"Failed ({e})"
        else:
            print("   ⚠️ Service Class Not Found")
            results["Shopify"] = "Partial (Env Only)"

    print("\n--- Summary ---")
    for service, status in results.items():
        print(f"{service}: {status}")

if __name__ == "__main__":
    asyncio.run(verify_integrations())
