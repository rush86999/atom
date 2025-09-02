import logging
from . import account_service
from . import investment_service
import yfinance as yf

logger = logging.getLogger(__name__)

async def get_net_worth(user_id: str, db_conn_pool):
    """
    Calculates the net worth of a user.
    """
    accounts = await account_service.get_accounts(user_id, db_conn_pool)
    net_worth = 0

    for account in accounts:
        net_worth += account['balance']
        investments = await investment_service.get_investments(account['id'], db_conn_pool)
        for investment in investments:
            holdings = await investment_service.get_holdings(investment['id'], db_conn_pool)
            for holding in holdings:
                ticker = yf.Ticker(holding['ticker'])
                current_price = ticker.history(period="1d")['Close'][0]
                net_worth += holding['shares'] * current_price

    return {"net_worth": net_worth}
