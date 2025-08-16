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

async def search_transactions(user_id: str, db_conn_pool, query: str = None, category: str = None, date_range: dict = None, amount_range: dict = None, limit: int = 50):
    """
    Searches for transactions based on various criteria.
    """
    sql_query = "SELECT t.id, t.amount, t.description, t.date, t.category FROM transactions t JOIN accounts a ON t.account_id = a.id WHERE a.user_id = $1"
    params = [user_id]
    param_index = 2

    if query:
        sql_query += f" AND t.description ILIKE ${param_index}"
        params.append(f"%{query}%")
        param_index += 1

    if category:
        sql_query += f" AND t.category = ${param_index}"
        params.append(category)
        param_index += 1

    if date_range and date_range.get('start') and date_range.get('end'):
        sql_query += f" AND t.date BETWEEN ${param_index} AND ${param_index + 1}"
        params.extend([date_range['start'], date_range['end']])
        param_index += 2

    if amount_range and amount_range.get('min') is not None and amount_range.get('max') is not None:
        sql_query += f" AND t.amount BETWEEN ${param_index} AND ${param_index + 1}"
        params.extend([amount_range['min'], amount_range['max']])
        param_index += 2

    sql_query += f" ORDER BY t.date DESC LIMIT ${param_index}"
    params.append(limit)

    async with db_conn_pool.acquire() as connection:
        rows = await connection.fetch(sql_query, *params)

    return [dict(row) for row in rows]
