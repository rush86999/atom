import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def check_env_vars():
    # Load .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        print(f"Loading .env from {env_path}")
        load_dotenv(env_path)
    else:
        print(f"Warning: .env file not found at {env_path}")

    # Define required variables by integration
    integrations = {
        "Slack": [
            "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_SIGNING_SECRET", "SLACK_BOT_TOKEN"
        ],
        "HubSpot": [
            "HUBSPOT_ACCESS_TOKEN"
        ],
        "Google Calendar": [
            "GOOGLE_CALENDAR_CREDENTIALS"
        ],
        "Zoom": [
            "ZOOM_API_KEY", "ZOOM_API_SECRET", "ZOOM_WEBHOOK_SECRET", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"
        ],
        "Dropbox": [
            "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REDIRECT_URI"
        ],
        "QuickBooks": [
            "QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET", "QUICKBOOKS_REDIRECT_URI", "QUICKBOOKS_COMPANY_ID"
        ],
        "Zendesk": [
            "ZENDESK_SUBDOMAIN", "ZENDESK_API_TOKEN", "ZENDESK_USERNAME", "ZENDESK_CLIENT_ID", "ZENDESK_CLIENT_SECRET"
        ],
        "Discord": [
            "DISCORD_BOT_TOKEN", "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET"
        ],
        "Microsoft Teams": [
            "TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET", "TEAMS_TENANT_ID"
        ],
        "WhatsApp": [
            "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"
        ],
        "Telegram": [
            "TELEGRAM_BOT_TOKEN"
        ]
    }

    missing_count = 0
    print("\nChecking Environment Variables...")
    print("-" * 50)

    for service, vars in integrations.items():
        print(f"\nChecking {service}...")
        service_missing = []
        for var in vars:
            if not os.getenv(var):
                service_missing.append(var)
        
        if service_missing:
            print(f"  ❌ Missing: {', '.join(service_missing)}")
            missing_count += len(service_missing)
        else:
            print(f"  ✅ All variables present")

    print("-" * 50)
    if missing_count > 0:
        print(f"\nFound {missing_count} missing environment variables.")
        print("Please update your .env file with the missing credentials.")
    else:
        print("\nAll checked environment variables are present! 🎉")

if __name__ == "__main__":
    check_env_vars()
