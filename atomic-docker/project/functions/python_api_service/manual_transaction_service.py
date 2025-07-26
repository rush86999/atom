import logging

logger = logging.getLogger(__name__)

async def get_manual_transactions(user_id, account_id, db_conn_pool):
    """
    Gets a list of manual transactions for a user's account.
    """
    # In a real application, we would retrieve the manual transactions from the database.
    # For this example, we will just return a dummy value.
    logger.info(f"Getting manual transactions for user {user_id} and account {account_id}")
    return [{"id": "1", "description": "Coffee", "amount": 5}]

async def create_manual_transaction(user_id, account_id, description, amount, db_conn_pool):
    """
    Creates a new manual transaction for a user's account.
    """
    # In a real application, we would store the manual transaction in the database.
    # For this example, we will just log it.
    logger.info(f"Creating manual transaction for user {user_id} and account {account_id} with description {description} and amount {amount}")
    pass
