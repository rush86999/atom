import logging
import os
import requests
from . import db_oauth_zoho

logger = logging.getLogger(__name__)

ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_ORG_ID = os.getenv("ZOHO_ORG_ID")

async def refresh_zoho_token(user_id, refresh_token, db_conn_pool):
    """
    Refreshes a Zoho OAuth token.
    """
    token_url = "https://accounts.zoho.com/oauth/v2/token"
    token_data = {
        "grant_type": "refresh_token",
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    response = requests.post(token_url, data=token_data)
    if response.status_code != 200:
        logger.error(f"Error refreshing Zoho token: {response.text}")
        raise Exception(f"Error refreshing Zoho token: {response.text}")
    token_info = response.json()
    await db_oauth_zoho.store_zoho_tokens(user_id, token_info['access_token'], refresh_token, db_conn_pool)
    return token_info['access_token']

async def get_zoho_organizations(user_id, db_conn_pool):
    """
    Gets a list of Zoho organizations for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    response = requests.get(
        "https://books.zoho.com/api/v3/organizations",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.get(
                "https://books.zoho.com/api/v3/organizations",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting Zoho organizations: {response.text}")
        raise Exception(f"Error getting Zoho organizations: {response.text}")

    return response.json()['organizations']

async def send_to_zoho(user_id, org_id, data, db_conn_pool):
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
        f"https://books.zoho.com/api/v3/invoices?organization_id={org_id}",
        headers=headers,
        json=data,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.post(
                f"https://books.zoho.com/api/v3/invoices?organization_id={org_id}",
                headers=headers,
                json=data,
            )

    if response.status_code != 201:
        logger.error(f"Error sending data to Zoho: {response.text}")
        raise Exception(f"Error sending data to Zoho: {response.text}")

    return response.json()

async def get_zoho_invoices(user_id, org_id, db_conn_pool):
    """
    Gets a list of Zoho invoices for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    response = requests.get(
        f"https://books.zoho.com/api/v3/invoices?organization_id={org_id}",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.get(
                f"https://books.zoho.com/api/v3/invoices?organization_id={org_id}",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting Zoho invoices: {response.text}")
        raise Exception(f"Error getting Zoho invoices: {response.text}")

    return response.json()['invoices']

async def create_zoho_invoice(user_id, org_id, invoice_data, db_conn_pool):
    """
    Creates a new Zoho invoice for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json;charset=UTF-8",
    }

    response = requests.post(
        f"https://books.zoho.com/api/v3/invoices?organization_id={org_id}",
        headers=headers,
        json=invoice_data,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.post(
                f"https://books.zoho.com/api/v3/invoices?organization_id={org_id}",
                headers=headers,
                json=invoice_data,
            )

    if response.status_code != 201:
        logger.error(f"Error creating Zoho invoice: {response.text}")
        raise Exception(f"Error creating Zoho invoice: {response.text}")

    return response.json()

async def get_zoho_customers(user_id, org_id, db_conn_pool):
    """
    Gets a list of Zoho customers for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    response = requests.get(
        f"https://books.zoho.com/api/v3/contacts?organization_id={org_id}",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.get(
                f"https://books.zoho.com/api/v3/contacts?organization_id={org_id}",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting Zoho customers: {response.text}")
        raise Exception(f"Error getting Zoho customers: {response.text}")

    return response.json()['contacts']

async def create_zoho_customer(user_id, org_id, customer_data, db_conn_pool):
    """
    Creates a new Zoho customer for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json;charset=UTF-8",
    }

    response = requests.post(
        f"https://books.zoho.com/api/v3/contacts?organization_id={org_id}",
        headers=headers,
        json=customer_data,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.post(
                f"https://books.zoho.com/api/v3/contacts?organization_id={org_id}",
                headers=headers,
                json=customer_data,
            )

    if response.status_code != 201:
        logger.error(f"Error creating Zoho customer: {response.text}")
        raise Exception(f"Error creating Zoho customer: {response.text}")

    return response.json()

async def get_zoho_items(user_id, org_id, db_conn_pool):
    """
    Gets a list of Zoho items for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    response = requests.get(
        f"https://books.zoho.com/api/v3/items?organization_id={org_id}",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.get(
                f"https://books.zoho.com/api/v3/items?organization_id={org_id}",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting Zoho items: {response.text}")
        raise Exception(f"Error getting Zoho items: {response.text}")

    return response.json()['items']

async def create_zoho_item(user_id, org_id, item_data, db_conn_pool):
    """
    Creates a new Zoho item for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json;charset=UTF-8",
    }

    response = requests.post(
        f"https://books.zoho.com/api/v3/items?organization_id={org_id}",
        headers=headers,
        json=item_data,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.post(
                f"https://books.zoho.com/api/v3/items?organization_id={org_id}",
                headers=headers,
                json=item_data,
            )

    if response.status_code != 201:
        logger.error(f"Error creating Zoho item: {response.text}")
        raise Exception(f"Error creating Zoho item: {response.text}")

    return response.json()

async def get_zoho_bills(user_id, org_id, db_conn_pool):
    """
    Gets a list of Zoho bills for a user.
    """
    access_token, _ = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Zoho credentials not found for this user.")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    response = requests.get(
        f"https://books.zoho.com/api/v3/bills?organization_id={org_id}",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_zoho.get_zoho_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_zoho_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
            response = requests.get(
                f"https://books.zoho.com/api/v3/bills?organization_id={org_id}",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting Zoho bills: {response.text}")
        raise Exception(f"Error getting Zoho bills: {response.text}")

    return response.json()['bills']
