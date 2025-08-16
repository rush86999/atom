import os
import logging
import json
from typing import Optional, Dict, Any
from google.ads.googleads.client import GoogleAdsClient
from .crypto import decrypt, encrypt

logger = logging.getLogger(__name__)

async def get_google_ads_client(user_id: str, db_conn_pool) -> Optional[GoogleAdsClient]:
    """
    Retrieves Google Ads credentials from the database and returns an initialized Google Ads client.
    """
    try:
        async with db_conn_pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT encrypted_secret FROM public.user_credentials WHERE user_id = $1 AND service_name = 'google_ads'",
                user_id
            )

        if not row:
            logger.error(f"No Google Ads credentials found for user {user_id}")
            return None

        encrypted_secret = row['encrypted_secret']

        encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("ENCRYPTION_KEY environment variable not set.")
            return None

        decrypted_secret = decrypt(encrypted_secret, encryption_key)
        credentials = json.loads(decrypted_secret)

        google_ads_client = GoogleAdsClient.load_from_dict(credentials)
        return google_ads_client
    except Exception as e:
        logger.error(f"Failed to create Google Ads client for user {user_id}: {e}", exc_info=True)
        return None

async def set_google_ads_credentials(user_id: str, credentials: Dict[str, Any], db_conn_pool):
    """
    Encrypts and stores Google Ads credentials in the database.
    """
    try:
        encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("ENCRYPTION_KEY environment variable not set.")
            raise ValueError("Server configuration error: Encryption key not set.")

        encrypted_secret = encrypt(json.dumps(credentials), encryption_key)

        async with db_conn_pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO public.user_credentials (user_id, service_name, encrypted_secret)
                VALUES ($1, 'google_ads', $2)
                ON CONFLICT (user_id, service_name) DO UPDATE
                SET encrypted_secret = EXCLUDED.encrypted_secret, updated_at = NOW()
                """,
                user_id,
                encrypted_secret
            )
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to set Google Ads credentials for user {user_id}: {e}", exc_info=True)
        raise

# Placeholder for other functions
async def create_campaign(client: GoogleAdsClient, customer_id: str, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder implementation
    return {"status": "created", "campaign_id": "12345"}

async def get_campaign(client: GoogleAdsClient, customer_id: str, campaign_id: str) -> Dict[str, Any]:
    # Placeholder implementation
    return {"status": "found", "campaign_id": campaign_id}
