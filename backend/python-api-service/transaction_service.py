import logging

logger = logging.getLogger(__name__)

async def create_transaction(account_id: int, amount: float, description: str, date: str, category: str, db_conn_pool):
    """
    Creates a new transaction for an account.
    """
    async with db_conn_pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                INSERT INTO transactions (account_id, amount, description, date, category)
                VALUES ($1, $2, $3, $4, $5)
                """,
                account_id,
                amount,
                description,
                date,
                category
            )
    return {"account_id": account_id, "amount": amount, "description": description, "date": date, "category": category}

async def get_transactions(account_id: int, db_conn_pool):
    """
    Retrieves all transactions for an account.
    """
    async with db_conn_pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id, amount, description, date, category FROM transactions WHERE account_id = $1",
            account_id
        )
    return [dict(row) for row in rows]
