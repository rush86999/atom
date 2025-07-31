import logging
import os
import requests
from . import db_oauth_zoho

logger = logging.getLogger(__name__)

ZOHO_ORG_ID = os.getenv("ZOHO_ORG_ID")

async def send_to_zoho(user_id, data, db_conn_pool):
    """
    Sends data to Zoho Books.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json;charset=UTF-8",
    }

    # In a real application, we would format the data to match Zoho's API
    # and handle the response properly.
    response = requests.post(
        f"https://books.zoho.com/api/v3/invoices?organization_id={ZOHO_ORG_ID}",
        headers=headers,
        json=data,
    )

    if response.status_code != 201:
        raise Exception(f"Error sending data to Zoho: {response.text}")

    return response.json()
