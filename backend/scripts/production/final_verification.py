
import sys
import os
import asyncio
import httpx
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from integrations.salesforce_routes import get_salesforce_client_from_env
from integrations.slack_routes import get_slack_client

async def verify_system():
    print("\n--- Final System Verification ---")
    
    # 1. Check Environment Variables
    print("\n1. Checking Critical Environment Variables:")
    critical_vars = ["SECRET_KEY", "ENVIRONMENT"]
    for var in critical_vars:
        val = os.getenv(var)
        status = "✅ Present" if val else "❌ Missing"
        print(f"   - {var}: {status}")

    # 2. Check Integration Clients (Graceful Failure)
    print("\n2. Checking Integration Clients:")
    try:
        sf_client = get_salesforce_client_from_env()
        print(f"   - Salesforce: {'✅ Connected' if sf_client else 'ℹ️ Not Configured (Expected)'}")
    except Exception as e:
        print(f"   - Salesforce: ❌ Error ({e})")

    try:
        slack_client = get_slack_client()
        print(f"   - Slack: {'✅ Connected' if slack_client else 'ℹ️ Not Configured (Expected)'}")
    except Exception as e:
        print(f"   - Slack: ❌ Error ({e})")

    # 3. Check Backend Importability
    print("\n3. Checking Backend Importability:")
    try:
        from main_api_app import app
        print("   - main_api_app: ✅ Imported successfully")
    except ImportError as e:
        print(f"   - main_api_app: ❌ Import Failed ({e})")
    except Exception as e:
        print(f"   - main_api_app: ❌ Error ({e})")

async def main():
    await verify_system()

if __name__ == "__main__":
    asyncio.run(main())
