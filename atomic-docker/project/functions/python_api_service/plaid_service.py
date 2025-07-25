import logging
import os
from plaid import Client

logger = logging.getLogger(__name__)

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")

client = Client(client_id=PLAID_CLIENT_ID, secret=PLAID_SECRET, environment=PLAID_ENV)

def create_link_token(user_id):
    """
    Creates a Plaid link token for a user.
    """
    try:
        response = client.LinkToken.create({
            'user': {
                'client_user_id': user_id,
            },
            'client_name': 'Atom Agent',
            'products': ['transactions'],
            'country_codes': ['US'],
            'language': 'en',
        })
        return response['link_token']
    except Exception as e:
        logger.error(f"Error creating Plaid link token for user {user_id}: {e}", exc_info=True)
        raise

def exchange_public_token(public_token):
    """
    Exchanges a Plaid public token for an access token.
    """
    try:
        response = client.Item.public_token.exchange(public_token)
        return response['access_token']
    except Exception as e:
        logger.error(f"Error exchanging Plaid public token: {e}", exc_info=True)
        raise

def get_accounts(access_token):
    """
    Gets a list of accounts for a Plaid item.
    """
    try:
        response = client.Accounts.get(access_token)
        return response['accounts']
    except Exception as e:
        logger.error(f"Error getting accounts for access token {access_token}: {e}", exc_info=True)
        raise

def get_transactions(access_token, start_date, end_date):
    """
    Gets a list of transactions for a Plaid item.
    """
    try:
        response = client.Transactions.get(access_token, start_date, end_date)
        return response['transactions']
    except Exception as e:
        logger.error(f"Error getting transactions for access token {access_token}: {e}", exc_info=True)
        raise

def get_investments(access_token):
    """
    Gets a list of investments for a Plaid item.
    """
    try:
        response = client.Investments.Holdings.get(access_token)
        return response['holdings']
    except Exception as e:
        logger.error(f"Error getting investments for access token {access_token}: {e}", exc_info=True)
        raise

def get_liabilities(access_token):
    """
    Gets a list of liabilities for a Plaid item.
    """
    try:
        response = client.Liabilities.get(access_token)
        return response['liabilities']
    except Exception as e:
        logger.error(f"Error getting liabilities for access token {access_token}: {e}", exc_info=True)
        raise
