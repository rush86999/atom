import logging

logger = logging.getLogger(__name__)

async def create_account(user_id: str, account_name: str, account_type: str, balance: float, db_conn_pool):
    """
    Creates a new financial account for a user.
    """
    async with db_conn_pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                INSERT INTO accounts (user_id, account_name, account_type, balance)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                account_name,
                account_type,
                balance
            )
    return {"user_id": user_id, "account_name": account_name, "account_type": account_type, "balance": balance}

async def get_accounts(user_id: str, db_conn_pool):
    """
    Retrieves all financial accounts for a user.
    """
    async with db_conn_pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id, account_name, account_type, balance FROM accounts WHERE user_id = $1",
            user_id
        )
    return [dict(row) for row in rows]
