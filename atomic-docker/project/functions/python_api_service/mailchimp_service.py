import os
import logging
from typing import Optional, Dict, Any
from mailchimp_marketing import Client
from mailchimp_marketing.api_client import ApiClientError

logger = logging.getLogger(__name__)

async def get_mailchimp_client(user_id: str, db_conn_pool) -> Optional[Client]:
    # This is a placeholder. In a real application, you would fetch the user's Mailchimp credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    api_key = os.environ.get("MAILCHIMP_API_KEY")
    server_prefix = os.environ.get("MAILCHIMP_SERVER_PREFIX")

    if not all([api_key, server_prefix]):
        logger.error("Mailchimp credentials are not configured in environment variables.")
        return None

    try:
        client = Client()
        client.set_config({
            "api_key": api_key,
            "server": server_prefix,
        })
        return client
    except Exception as e:
        logger.error(f"Failed to create Mailchimp client: {e}", exc_info=True)
        return None

async def create_campaign(client: Client, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
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
