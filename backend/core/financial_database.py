"""
Financial Database Operations
Real database implementation for financial transactions, budgets, and analytics
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timedelta
import uuid
import json
from core.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class FinancialDatabase:
    """Real database operations for financial data"""

    def __init__(self):
        self.db_manager = DatabaseManager()

    async def initialize(self):
        """Initialize database and create financial tables"""
        await self.db_manager.initialize()
        await self._create_financial_tables()

    async def _create_financial_tables(self):
        """Create financial-specific tables"""

        # Transactions table
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S'))
            )
        """)

        # Budgets table
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                allocated_amount REAL NOT NULL,
                spent_amount REAL DEFAULT 0.0,
                period TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S'))
            )
        """)

        # Net worth tracking table
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS net_worth (
                id TEXT PRIMARY KEY,
                total_assets REAL NOT NULL,
                total_liabilities REAL NOT NULL,
                net_worth REAL NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S'))
            )
        """)

        # Create indexes for better performance
        await self.db_manager.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)")
        await self.db_manager.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category)")
        await self.db_manager.execute("CREATE INDEX IF NOT EXISTS idx_budgets_category ON budgets(category)")
        await self.db_manager.execute("CREATE INDEX IF NOT EXISTS idx_budgets_period ON budgets(period)")

        logger.info("Financial database tables created successfully")

    # Transaction operations
    async def create_transaction(self, description: str, category: str, amount: float, status: str = "Pending", transaction_date: Optional[str] = None) -> str:
        """Create a new transaction"""
        transaction_id = f"TRX-{uuid.uuid4().hex[:8].upper()}"

        if not transaction_date:
            transaction_date = datetime.now().strftime("%Y-%m-%d")

        await self.db_manager.execute("""
            INSERT INTO transactions (id, date, description, category, amount, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (transaction_id, transaction_date, description, category, amount, status))

        logger.info(f"Created transaction: {transaction_id}")
        return transaction_id

    async def get_transactions(self, limit: int = 50, offset: int = 0, category: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Get transactions with optional filtering"""

        query = "SELECT * FROM transactions WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self.db_manager.fetch_all(query, params)
        return [dict(row) for row in rows]

    async def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get a specific transaction by ID"""
        row = await self.db_manager.fetch_one("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
        return dict(row) if row else None

    async def update_transaction(self, transaction_id: str, **kwargs) -> bool:
        """Update a transaction"""
        if not kwargs:
            return False

        # Build update query dynamically
        set_clauses = []
        params = []

        for field, value in kwargs.items():
            if field in ['description', 'category', 'amount', 'status', 'date']:
                set_clauses.append(f"{field} = ?")
                params.append(value)

        if not set_clauses:
            return False

        set_clauses.append("updated_at = strftime('%Y-%m-%d %H:%M:%S')")
        params.append(transaction_id)

        query = f"UPDATE transactions SET {', '.join(set_clauses)} WHERE id = ?"
        await self.db_manager.execute(query, params)

        logger.info(f"Updated transaction: {transaction_id}")
        return True

    async def delete_transaction(self, transaction_id: str) -> bool:
        """Delete a transaction"""
        result = await self.db_manager.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        success = result.rowcount > 0
        if success:
            logger.info(f"Deleted transaction: {transaction_id}")
        return success

    # Budget operations
    async def create_budget(self, category: str, allocated_amount: float, period: str) -> str:
        """Create a new budget"""
        budget_id = f"BUD-{uuid.uuid4().hex[:8].upper()}"

        await self.db_manager.execute("""
            INSERT INTO budgets (id, category, allocated_amount, period)
            VALUES (?, ?, ?, ?)
        """, (budget_id, category, allocated_amount, period))

        logger.info(f"Created budget: {budget_id}")
        return budget_id

    async def get_budgets(self, period: Optional[str] = None) -> List[Dict]:
        """Get budgets with optional period filtering"""
        query = "SELECT * FROM budgets"
        params = []

        if period:
            query += " WHERE period = ?"
            params.append(period)

        query += " ORDER BY category, period DESC"

        rows = await self.db_manager.fetch_all(query, params)
        return [dict(row) for row in rows]

    async def update_budget_spent(self, budget_id: str, spent_amount: float) -> bool:
        """Update the spent amount for a budget"""
        await self.db_manager.execute("""
            UPDATE budgets SET spent_amount = ?, updated_at = strftime('%Y-%m-%d %H:%M:%S')
            WHERE id = ?
        """, (spent_amount, budget_id))

        logger.info(f"Updated budget spent amount: {budget_id}")
        return True

    # Net worth operations
    async def record_net_worth(self, total_assets: float, total_liabilities: float) -> str:
        """Record net worth snapshot"""
        net_worth_id = f"NW-{uuid.uuid4().hex[:8].upper()}"
        net_worth_value = total_assets - total_liabilities

        await self.db_manager.execute("""
            INSERT INTO net_worth (id, total_assets, total_liabilities, net_worth)
            VALUES (?, ?, ?, ?)
        """, (net_worth_id, total_assets, total_liabilities, net_worth_value))

        logger.info(f"Recorded net worth: {net_worth_id}")
        return net_worth_id

    async def get_latest_net_worth(self) -> Optional[Dict]:
        """Get the most recent net worth record"""
        row = await self.db_manager.fetch_one("""
            SELECT * FROM net_worth
            ORDER BY recorded_at DESC
            LIMIT 1
        """)
        return dict(row) if row else None

    async def get_net_worth_history(self, limit: int = 30) -> List[Dict]:
        """Get net worth history"""
        rows = await self.db_manager.fetch_all("""
            SELECT * FROM net_worth
            ORDER BY recorded_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in rows]

    # Analytics operations
    async def get_financial_summary(self, period: str = None) -> Dict[str, Any]:
        """Get financial summary for a period"""

        # Default to current month if no period specified
        if not period:
            period = datetime.now().strftime("%Y-%m")

        # Get transactions for the period
        transactions = await self.get_transactions(limit=1000, start_date=f"{period}-01", end_date=f"{period}-31")

        # Calculate totals
        total_income = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_expenses = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)
        net_income = total_income - total_expenses
        savings_rate = (net_income / total_income * 100) if total_income > 0 else 0

        # Get budget information
        budgets = await self.get_budgets(period)

        return {
            "period": period,
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_income": round(net_income, 2),
            "savings_rate": round(savings_rate, 2),
            "transaction_count": len(transactions),
            "budget_count": len(budgets),
            "categories": list(set(t['category'] for t in transactions))
        }

    async def get_category_summary(self, period: str = None) -> List[Dict]:
        """Get spending/income summary by category"""
        if not period:
            period = datetime.now().strftime("%Y-%m")

        rows = await self.db_manager.fetch_all("""
            SELECT
                category,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as expenses,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE date >= ? AND date <= ?
            GROUP BY category
            ORDER BY expenses DESC, income DESC
        """, (f"{period}-01", f"{period}-31"))

        return [dict(row) for row in rows]

# Global instance
financial_db = FinancialDatabase()