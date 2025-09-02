import logging

logger = logging.getLogger(__name__)

async def get_manual_accounts(user_id, db_conn_pool):
    """
    Gets a list of manual accounts for a user.
    """
    # In a real application, we would retrieve the manual accounts from the database.
    # For this example, we will just return a dummy value.
    logger.info(f"Getting manual accounts for user {user_id}")
    return [{"id": "1", "name": "Cash", "balance": 1000}]

async def create_manual_account(user_id, name, balance, db_conn_pool):
    """
    Creates a new manual account for a user.
    """
    # In a real application, we would store the manual account in the database.
    # For this example, we will just log it.
    logger.info(f"Creating manual account for user {user_id} with name {name} and balance {balance}")
    pass
