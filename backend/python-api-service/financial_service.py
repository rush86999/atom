import logging
from . import plaid_service
from . import db_utils # This will be a new file to handle db operations

logger = logging.getLogger(__name__)

async def create_plaid_integration(user_id, public_token, db_conn_pool):
    """
    Creates a new Plaid integration for a user.
    """
    access_token = plaid_service.exchange_public_token(public_token)
    await db_utils.create_plaid_item(user_id, access_token, db_conn_pool)
    return {"status": "success"}

async def get_financial_summary(user_id, db_conn_pool):
    """
    Gets a financial summary for a user.
    """
    access_token = await db_utils.get_plaid_access_token(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Plaid integration not found for this user.")

    accounts = plaid_service.get_accounts(access_token)
    # In a real application, we would do more here, like calculating net worth, etc.
    return {"accounts": accounts}

async def get_accounts(user_id, db_conn_pool):
    """
    Gets a list of accounts for a user.
    """
    access_token = await db_utils.get_plaid_access_token(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Plaid integration not found for this user.")

    return plaid_service.get_accounts(access_token)

async def get_transactions(user_id, start_date, end_date, db_conn_pool):
    """
    Gets a list of transactions for a user.
    """
    access_token = await db_utils.get_plaid_access_token(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Plaid integration not found for this user.")

    return plaid_service.get_transactions(access_token, start_date, end_date)

async def get_investments(user_id, db_conn_pool):
    """
    Gets a list of investments for a user.
    """
    access_token = await db_utils.get_plaid_access_token(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Plaid integration not found for this user.")

    return plaid_service.get_investments(access_token)

async def get_liabilities(user_id, db_conn_pool):
    """
    Gets a list of liabilities for a user.
    """
    access_token = await db_utils.get_plaid_access_token(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Plaid integration not found for this user.")

    return plaid_service.get_liabilities(access_token)
