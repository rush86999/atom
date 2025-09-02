import logging
from . import financial_service

logger = logging.getLogger(__name__)

async def get_net_worth(user_id, db_conn_pool):
    """
    Calculates the net worth of a user.
    """
    accounts = await financial_service.get_accounts(user_id, db_conn_pool)
    investments = await financial_service.get_investments(user_id, db_conn_pool)

    total_assets = 0
    total_liabilities = 0

    for account in accounts:
        if account['type'] == 'depository' or account['type'] == 'brokerage':
            total_assets += account['balances']['current']
        elif account['type'] == 'loan' or account['type'] == 'credit':
            total_liabilities += account['balances']['current']

    for investment in investments:
        total_assets += investment['institution_value']

    return total_assets - total_liabilities
