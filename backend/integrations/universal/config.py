
import os
from typing import Dict, Any

# Map of piece names to OAuth configuration
# In production, these should be stored in the database or a secure vault.
# For MVP, we use environment variables.
OAUTH_CONFIGS: Dict[str, Dict[str, Any]] = {
    "@activepieces/piece-slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "client_id": os.getenv("SLACK_CLIENT_ID", "default_slack_id"),
        "client_secret": os.getenv("SLACK_CLIENT_SECRET", "default_slack_secret"),
        "scopes": ["channels:read", "chat:write", "groups:read", "im:read", "mpim:read"]
    },
    "@activepieces/piece-google-drive": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "default_google_id"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "default_google_secret"),
        "scopes": ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.file"]
    },
    "@activepieces/piece-gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "default_google_id"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "default_google_secret"),
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
    },
    "@activepieces/piece-hubspot": {
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "client_id": os.getenv("HUBSPOT_CLIENT_ID", "default_hubspot_id"),
        "client_secret": os.getenv("HUBSPOT_CLIENT_SECRET", "default_hubspot_secret"),
        "scopes": ["crm.objects.contacts.read", "crm.objects.contacts.write"]
    }
}

def get_oauth_config(piece_name: str) -> Optional[Dict[str, Any]]:
    return OAUTH_CONFIGS.get(piece_name)
