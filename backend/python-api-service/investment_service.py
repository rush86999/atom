import logging
import yfinance as yf

logger = logging.getLogger(__name__)

async def create_investment(account_id: int, investment_name: str, investment_type: str, db_conn_pool):
    """
    Creates a new investment for an account.
    """
    async with db_conn_pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                INSERT INTO investments (account_id, investment_name, investment_type)
                VALUES ($1, $2, $3)
                """,
                account_id,
                investment_name,
                investment_type
            )
    return {"account_id": account_id, "investment_name": investment_name, "investment_type": investment_type}

async def get_investments(account_id: int, db_conn_pool):
    """
    Retrieves all investments for an account.
    """
    async with db_conn_pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id, investment_name, investment_type FROM investments WHERE account_id = $1",
            account_id
        )
    return [dict(row) for row in rows]

async def create_holding(investment_id: int, ticker: str, shares: float, purchase_price: float, db_conn_pool):
    """
    Creates a new holding for an investment.
    """
    async with db_conn_pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                INSERT INTO holdings (investment_id, ticker, shares, purchase_price)
                VALUES ($1, $2, $3, $4)
                """,
                investment_id,
                ticker,
                shares,
                purchase_price
            )
    return {"investment_id": investment_id, "ticker": ticker, "shares": shares, "purchase_price": purchase_price}

async def get_holdings(investment_id: int, db_conn_pool):
    """
    Retrieves all holdings for an investment.
    """
    async with db_conn_pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id, ticker, shares, purchase_price FROM holdings WHERE investment_id = $1",
            investment_id
        )

    holdings = []
    for row in rows:
        holding = dict(row)
        ticker = yf.Ticker(holding['ticker'])
        current_price = ticker.history(period="1d")['Close'][0]
        holding['current_price'] = current_price
        holdings.append(holding)

    return holdings
