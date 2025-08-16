import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def create_budget(user_id: str, name: str, category: str, amount: float, period_type: str, start_date: str, db_conn_pool):
    """
    Creates a new budget for a user.
    """
    async with db_conn_pool.acquire() as connection:
        async with connection.transaction():
            # Using the comprehensive schema from 0014-create-budgets-and-goals-tables.sql
            await connection.execute(
                """
                INSERT INTO budgets (user_id, name, category, amount, period_type, start_date)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id, name, category, amount, period_type, start_date
            )
    return {"user_id": user_id, "name": name, "category": category, "amount": amount}


async def get_budgets(user_id: str, db_conn_pool):
    """
    Gets a list of all budgets for a user.
    """
    async with db_conn_pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id, name, category, amount, period_type, start_date, end_date FROM budgets WHERE user_id = $1 AND is_active = TRUE",
            user_id
        )
    return [dict(row) for row in rows]


async def get_budget_summary(user_id: str, db_conn_pool, period_start: str = None, period_end: str = None):
    """
    Calculates the budget summary for a user for a given period.
    """
    if not period_start or not period_end:
        # Default to the current month if no period is provided
        today = datetime.today()
        period_start = today.replace(day=1).strftime('%Y-%m-%d')
        # To get the end of the month, we can go to the first day of the next month and subtract one day.
        # This is a bit complex with just strftime, so for simplicity, we'll estimate 30 days.
        # A more robust solution would use dateutil or calendar library.
        next_month = today.replace(day=28) + datetime.timedelta(days=4)
        period_end = (next_month - datetime.timedelta(days=next_month.day)).strftime('%Y-%m-%d')


    budgets = await get_budgets(user_id, db_conn_pool)
    summary = {
        "totalBudget": 0,
        "totalSpent": 0,
        "totalRemaining": 0,
        "categories": []
    }

    async with db_conn_pool.acquire() as connection:
        for budget in budgets:
            # For each budget, get the sum of transactions in its category for the period
            spent_row = await connection.fetchrow(
                """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE a.user_id = $1 AND t.category = $2 AND t.date BETWEEN $3 AND $4 AND t.amount < 0
                """,
                user_id, budget['category'], period_start, period_end
            )

            spent = abs(spent_row['total']) if spent_row else 0
            budgeted = budget['amount']
            remaining = budgeted - spent
            utilization = (spent / budgeted) * 100 if budgeted > 0 else 0

            summary['categories'].append({
                "category": budget['category'],
                "budgeted": budgeted,
                "spent": spent,
                "remaining": remaining,
                "utilization": round(utilization, 2)
            })

    summary['totalBudget'] = sum(c['budgeted'] for c in summary['categories'])
    summary['totalSpent'] = sum(c['spent'] for c in summary['categories'])
    summary['totalRemaining'] = sum(c['remaining'] for c in summary['categories'])

    return summary
