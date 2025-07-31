import logging
import os
import requests

logger = logging.getLogger(__name__)

ZOHO_API_KEY = os.getenv("ZOHO_API_KEY")
ZOHO_ORG_ID = os.getenv("ZOHO_ORG_ID")

def send_to_zoho(data):
    """
    Sends data to Zoho Books.
    """
    if not all([ZOHO_API_KEY, ZOHO_ORG_ID]):
        raise Exception("Zoho API key and organization ID are not configured.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_API_KEY}",
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
