
import sys
import os
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from integrations.salesforce_routes import get_salesforce_client_from_env, format_salesforce_error_response
from integrations.slack_routes import get_slack_client, SLACK_SDK_AVAILABLE

async def verify_salesforce():
    print("\n--- Verifying Salesforce ---")
    client = get_salesforce_client_from_env()
    if client:
        print("✅ Salesforce client created from env")
    else:
        print("ℹ️ Salesforce client not created (expected if no env vars)")
    
    error_response = format_salesforce_error_response("Test Error")
    if error_response["error"]["message"] == "Test Error":
        print("✅ Salesforce error formatting works")
    else:
        print("❌ Salesforce error formatting failed")

async def verify_slack():
    print("\n--- Verifying Slack ---")
    print(f"Slack SDK Available: {SLACK_SDK_AVAILABLE}")
    
    client = get_slack_client()
    if client:
        print("✅ Slack client created from env")
    else:
        print("ℹ️ Slack client not created (expected if no env vars)")

async def main():
    await verify_salesforce()
    await verify_slack()

if __name__ == "__main__":
    asyncio.run(main())
