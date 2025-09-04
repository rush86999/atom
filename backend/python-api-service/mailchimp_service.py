import os
import logging
import json
from typing import Optional, Dict, Any
from mailchimp_marketing import Client
from mailchimp_marketing.api_client import ApiClientError
from crypto import decrypt, encrypt

logger = logging.getLogger(__name__)

async def get_mailchimp_client(user_id: str, db_conn_pool) -> Optional[Client]:
    """
    Retrieves Mailchimp credentials from the database, decrypts the API key,
    and returns an initialized Mailchimp client.
    """
    try:
        async with db_conn_pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT encrypted_secret FROM public.user_credentials WHERE user_id = $1 AND service_name = 'mailchimp'",
                user_id
            )

        if not row:
            logger.error(f"No Mailchimp credentials found for user {user_id}")
            return None

        encrypted_secret = row['encrypted_secret']

        encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("ENCRYPTION_KEY environment variable not set.")
            return None

        decrypted_secret = decrypt(encrypted_secret, encryption_key)
        credentials = json.loads(decrypted_secret)
        api_key = credentials.get('api_key')
        server_prefix = credentials.get('server_prefix')

        if not api_key or not server_prefix:
            logger.error(f"Incomplete Mailchimp credentials for user {user_id}")
            return None

        client = Client()
        client.set_config({
            "api_key": api_key,
            "server": server_prefix,
        })
        return client
    except Exception as e:
        logger.error(f"Failed to create Mailchimp client for user {user_id}: {e}", exc_info=True)
        return None

async def set_mailchimp_credentials(user_id: str, api_key: str, server_prefix: str, db_conn_pool):
    """
    Encrypts and stores Mailchimp credentials in the database.
    """
    try:
        encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not encryption_key:
            logger.error("ENCRYPTION_KEY environment variable not set.")
            raise ValueError("Server configuration error: Encryption key not set.")

        credentials = {
            "api_key": api_key,
            "server_prefix": server_prefix
        }
        encrypted_secret = encrypt(json.dumps(credentials), encryption_key)

        async with db_conn_pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO public.user_credentials (user_id, service_name, encrypted_secret)
                VALUES ($1, 'mailchimp', $2)
                ON CONFLICT (user_id, service_name) DO UPDATE
                SET encrypted_secret = EXCLUDED.encrypted_secret, updated_at = NOW()
                """,
                user_id,
                encrypted_secret
            )
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to set Mailchimp credentials for user {user_id}: {e}", exc_info=True)
        raise

async def create_campaign(client: Client, list_id: str, subject_line: str, from_name: str, reply_to: str, template_id: Optional[int] = None) -> Dict[str, Any]:
    campaign_data = {
        "type": "regular",
        "recipients": {"list_id": list_id},
        "settings": {
            "subject_line": subject_line,
            "from_name": from_name,
            "reply_to": reply_to,
        }
    }
    if template_id:
        campaign_data["settings"]["template_id"] = template_id

    try:
        response = client.campaigns.create(campaign_data)
        return response
    except ApiClientError as error:
        logger.error(f"Error creating Mailchimp campaign: {error.text}")
        raise

async def get_campaign_report(client: Client, campaign_id: str) -> Dict[str, Any]:
    try:
        response = client.reports.get_campaign_report(campaign_id)
        return response
    except ApiClientError as error:
        logger.error(f"Error getting Mailchimp campaign report: {error.text}")
        raise

async def get_campaign(client: Client, campaign_id: str) -> Dict[str, Any]:
    try:
        response = client.campaigns.get(campaign_id)
        return response
    except ApiClientError as error:
        logger.error(f"Error getting Mailchimp campaign: {error.text}")
        raise

async def get_all_lists(client: Client) -> Dict[str, Any]:
    try:
        response = client.lists.get_all_lists()
        return response
    except ApiClientError as error:
        logger.error(f"Error getting all Mailchimp lists: {error.text}")
        raise

async def add_list_member(client: Client, list_id: str, member_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = client.lists.add_list_member(list_id, member_data)
        return response
    except ApiClientError as error:
        logger.error(f"Error adding member to Mailchimp list: {error.text}")
        raise

async def list_templates(client: Client) -> Dict[str, Any]:
    try:
        response = client.templates.list()
        return response
    except ApiClientError as error:
        logger.error(f"Error listing Mailchimp templates: {error.text}")
        raise
