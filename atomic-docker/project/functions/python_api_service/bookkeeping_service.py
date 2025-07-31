import logging
from . import plaid_service
from . import db_utils

logger = logging.getLogger(__name__)

async def get_bookkeeping_data(user_id, db_conn_pool):
    """
    Gets bookkeeping data for a user.
    """
    access_token = await db_utils.get_plaid_access_token(user_id, db_conn_pool)
    if not access_token:
        raise Exception("Plaid integration not found for this user.")

    accounts = plaid_service.get_accounts(access_token)
    transactions = plaid_service.get_transactions(access_token, "2023-01-01", "2023-12-31")

    # In a real application, we would do more here, like categorizing transactions, etc.
    return {"accounts": accounts, "transactions": transactions}
