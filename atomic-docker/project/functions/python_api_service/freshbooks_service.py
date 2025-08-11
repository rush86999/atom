import logging
import os
import requests
from . import db_oauth_freshbooks

logger = logging.getLogger(__name__)

FRESHBOOKS_CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
FRESHBOOKS_CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")

async def refresh_freshbooks_token(user_id, refresh_token, db_conn_pool):
    """
    Refreshes a FreshBooks OAuth token.
    """
    # Placeholder for FreshBooks token refresh logic
    pass

async def get_freshbooks_invoices(user_id, account_id, db_conn_pool):
    """
    Gets a list of FreshBooks invoices for a user.
    """
    access_token, _ = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("FreshBooks credentials not found for this user.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Api-Version": "alpha",
        "Content-Type": "application/json"
    }

    response = requests.get(
        f"https://api.freshbooks.com/accounting/account/{account_id}/invoices/invoices",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_freshbooks_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.get(
                f"https://api.freshbooks.com/accounting/account/{account_id}/invoices/invoices",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting FreshBooks invoices: {response.text}")
        raise Exception(f"Error getting FreshBooks invoices: {response.text}")

    return response.json()['response']['invoices']

async def create_freshbooks_invoice(user_id, account_id, invoice_data, db_conn_pool):
    """
    Creates a new FreshBooks invoice for a user.
    """
    access_token, _ = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("FreshBooks credentials not found for this user.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Api-Version": "alpha",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"https://api.freshbooks.com/accounting/account/{account_id}/invoices/invoices",
        headers=headers,
        json=invoice_data,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_freshbooks_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.post(
                f"https://api.freshbooks.com/accounting/account/{account_id}/invoices/invoices",
                headers=headers,
                json=invoice_data,
            )

    if response.status_code != 200:
        logger.error(f"Error creating FreshBooks invoice: {response.text}")
        raise Exception(f"Error creating FreshBooks invoice: {response.text}")

    return response.json()

async def get_freshbooks_clients(user_id, account_id, db_conn_pool):
    """
    Gets a list of FreshBooks clients for a user.
    """
    access_token, _ = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("FreshBooks credentials not found for this user.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Api-Version": "alpha",
        "Content-Type": "application/json"
    }

    response = requests.get(
        f"https://api.freshbooks.com/accounting/account/{account_id}/users/clients",
        headers=headers,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_freshbooks_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.get(
                f"https://api.freshbooks.com/accounting/account/{account_id}/users/clients",
                headers=headers,
            )

    if response.status_code != 200:
        logger.error(f"Error getting FreshBooks clients: {response.text}")
        raise Exception(f"Error getting FreshBooks clients: {response.text}")

    return response.json()['response']['clients']

async def create_freshbooks_client(user_id, account_id, client_data, db_conn_pool):
    """
    Creates a new FreshBooks client for a user.
    """
    access_token, _ = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
    if not access_token:
        raise Exception("FreshBooks credentials not found for this user.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Api-Version": "alpha",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"https://api.freshbooks.com/accounting/account/{account_id}/users/clients",
        headers=headers,
        json=client_data,
    )

    if response.status_code == 401:
        _, refresh_token = await db_oauth_freshbooks.get_freshbooks_tokens(user_id, db_conn_pool)
        if refresh_token:
            access_token = await refresh_freshbooks_token(user_id, refresh_token, db_conn_pool)
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.post(
                f"https://api.freshbooks.com/accounting/account/{account_id}/users/clients",
                headers=headers,
                json=client_data,
            )

    if response.status_code != 200:
        logger.error(f"Error creating FreshBooks client: {response.text}")
        raise Exception(f"Error creating FreshBooks client: {response.text}")

    return response.json()
