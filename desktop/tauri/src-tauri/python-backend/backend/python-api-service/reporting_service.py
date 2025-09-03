import logging
from . import financial_service

logger = logging.getLogger(__name__)

async def get_spending_report(user_id, db_conn_pool):
    """
    Generates a spending report for a user.
    """
    transactions = await financial_service.get_transactions(user_id, "2023-01-01", "2023-12-31", db_conn_pool)

    spending_by_category = {}
    for transaction in transactions:
        category = transaction['category'][0]
        if category not in spending_by_category:
            spending_by_category[category] = 0
        spending_by_category[category] += transaction['amount']

    return spending_by_category
