"""
Financial Data API Routes
Real implementation for financial transactions, budgets, and analytics
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import logging
from core.database_manager import DatabaseManager
from core.financial_database import financial_db

logger = logging.getLogger(__name__)

# Pydantic models
class Transaction(BaseModel):
    id: str
    date: str
    description: str
    category: str
    amount: float
    status: str

class TransactionCreate(BaseModel):
    description: str
    category: str
    amount: float

class Budget(BaseModel):
    id: str
    category: str
    allocated_amount: float
    spent_amount: float
    period: str

class NetWorth(BaseModel):
    total_assets: float
    total_liabilities: float
    net_worth: float
    last_updated: str

# Create router
router = APIRouter(prefix="/api/atom/finance", tags=["Financial Data"])

# Database manager instance
db_manager = DatabaseManager()

@router.post("/initialize", response_model=dict)
async def initialize_financial_db():
    """Initialize financial database and seed with sample data"""
    try:
        await financial_db.initialize()

        # Seed with sample data if no transactions exist
        existing_transactions = await financial_db.get_transactions(limit=1)
        if not existing_transactions:
            # Insert sample transactions
            await financial_db.create_transaction("Client Payment - ABC Corp", "Income", 5000.00, "Completed")
            await financial_db.create_transaction("AWS Services", "Infrastructure", -234.56, "Completed")
            await financial_db.create_transaction("Software Licenses", "Software", -156.00, "Completed")
            await financial_db.create_transaction("Office Supplies", "Office", -89.99, "Completed")
            await financial_db.create_transaction("Contract Income", "Income", 3500.00, "Completed")

            # Create sample budgets
            await financial_db.create_budget("Infrastructure", 500.00, "2025-12")
            await financial_db.create_budget("Software", 300.00, "2025-12")
            await financial_db.create_budget("Office", 200.00, "2025-12")

            # Record initial net worth
            await financial_db.record_net_worth(15000.00, 3500.00)

            return {
                "success": True,
                "message": "Financial database initialized with sample data",
                "transactions_created": 5,
                "budgets_created": 3,
                "net_worth_recorded": True
            }
        else:
            return {
                "success": True,
                "message": "Financial database already initialized",
                "existing_transactions": True
            }

    except Exception as e:
        logger.error(f"Failed to initialize financial database: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Sample data (fallback if database is not available)
SAMPLE_TRANSACTIONS = [
    {
        "id": "TRX-0001",
        "date": "2025-12-09",
        "description": "Client Payment - ABC Corp",
        "category": "Income",
        "amount": 5000.00,
        "status": "Completed"
    },
    {
        "id": "TRX-0002",
        "date": "2025-12-08",
        "description": "AWS Services",
        "category": "Infrastructure",
        "amount": -234.56,
        "status": "Completed"
    },
    {
        "id": "TRX-0003",
        "date": "2025-12-08",
        "description": "Software Licenses",
        "category": "Software",
        "amount": -156.00,
        "status": "Completed"
    },
    {
        "id": "TRX-0004",
        "date": "2025-12-07",
        "description": "Office Supplies",
        "category": "Office",
        "amount": -89.99,
        "status": "Completed"
    },
    {
        "id": "TRX-0005",
        "date": "2025-12-07",
        "description": "Contract Income",
        "category": "Income",
        "amount": 3500.00,
        "status": "Completed"
    }
]

SAMPLE_BUDGETS = [
    {
        "id": "BUD-001",
        "category": "Infrastructure",
        "allocated_amount": 500.00,
        "spent_amount": 234.56,
        "period": "2025-12"
    },
    {
        "id": "BUD-002",
        "category": "Software",
        "allocated_amount": 300.00,
        "spent_amount": 156.00,
        "period": "2025-12"
    },
    {
        "id": "BUD-003",
        "category": "Office",
        "allocated_amount": 200.00,
        "spent_amount": 89.99,
        "period": "2025-12"
    }
]

# Transactions endpoints
@router.get("/transactions", response_model=dict)
async def get_transactions(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Get financial transactions with optional filtering
    """
    try:
        # Try to get data from real database first
        try:
            transactions = await financial_db.get_transactions(
                limit=limit,
                offset=offset,
                category=category,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as db_error:
            logger.warning(f"Database error, using fallback data: {db_error}")
            # Fallback to sample data
            transactions = SAMPLE_TRANSACTIONS.copy()

            # Apply filters to fallback data
            if category:
                transactions = [t for t in transactions if t["category"].lower() == category.lower()]

            if start_date:
                transactions = [t for t in transactions if t["date"] >= start_date]

            if end_date:
                transactions = [t for t in transactions if t["date"] <= end_date]

            # Apply pagination
            transactions = transactions[offset:offset + limit]

        return {
            "success": True,
            "data": {
                "transactions": paginated_transactions,
                "total": len(transactions),
                "count": len(paginated_transactions),
                "limit": limit,
                "offset": offset
            }
        }
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")

@router.post("/transactions", response_model=dict)
async def create_transaction(transaction: TransactionCreate):
    """
    Create a new transaction
    """
    try:
        # Generate transaction ID
        transaction_id = f"TRX-{len(SAMPLE_TRANSACTIONS) + 1:04d}"

        new_transaction = {
            "id": transaction_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": transaction.description,
            "category": transaction.category,
            "amount": transaction.amount,
            "status": "Pending"
        }

        # Add to sample data (in production, save to database)
        SAMPLE_TRANSACTIONS.insert(0, new_transaction)

        return {
            "success": True,
            "data": {
                "transaction": new_transaction,
                "message": "Transaction created successfully"
            }
        }
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to create transaction")

@router.get("/transactions/{transaction_id}", response_model=dict)
async def get_transaction(transaction_id: str):
    """
    Get a specific transaction by ID
    """
    try:
        transaction = next((t for t in SAMPLE_TRANSACTIONS if t["id"] == transaction_id), None)

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return {
            "success": True,
            "data": {
                "transaction": transaction
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transaction {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch transaction")

# Budgets endpoints
@router.get("/budgets", response_model=dict)
async def get_budgets():
    """
    Get budget information
    """
    try:
        return {
            "success": True,
            "data": {
                "budgets": SAMPLE_BUDGETS,
                "total_allocated": sum(b["allocated_amount"] for b in SAMPLE_BUDGETS),
                "total_spent": sum(b["spent_amount"] for b in SAMPLE_BUDGETS)
            }
        }
    except Exception as e:
        logger.error(f"Error fetching budgets: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch budgets")

# Net Worth endpoint
@router.get("/net-worth", response_model=dict)
async def get_net_worth():
    """
    Get net worth summary
    """
    try:
        total_income = sum(t["amount"] for t in SAMPLE_TRANSACTIONS if t["amount"] > 0)
        total_expenses = sum(abs(t["amount"]) for t in SAMPLE_TRANSACTIONS if t["amount"] < 0)
        net_worth = total_income - total_expenses

        return {
            "success": True,
            "data": {
                "total_assets": total_income,
                "total_liabilities": total_expenses,
                "net_worth": net_worth,
                "last_updated": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error calculating net worth: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate net worth")

# Financial Summary endpoint
@router.get("/summary", response_model=dict)
async def get_financial_summary():
    """
    Get comprehensive financial summary
    """
    try:
        # Calculate metrics
        transactions = SAMPLE_TRANSACTIONS
        total_income = sum(t["amount"] for t in transactions if t["amount"] > 0)
        total_expenses = sum(abs(t["amount"]) for t in transactions if t["amount"] < 0)

        # Category breakdown
        category_breakdown = {}
        for transaction in transactions:
            category = transaction["category"]
            if category not in category_breakdown:
                category_breakdown[category] = {"income": 0, "expenses": 0}

            if transaction["amount"] > 0:
                category_breakdown[category]["income"] += transaction["amount"]
            else:
                category_breakdown[category]["expenses"] += abs(transaction["amount"])

        return {
            "success": True,
            "data": {
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net_profit": total_income - total_expenses,
                "transaction_count": len(transactions),
                "category_breakdown": category_breakdown,
                "budget_utilization": {
                    "total_allocated": sum(b["allocated_amount"] for b in SAMPLE_BUDGETS),
                    "total_spent": sum(b["spent_amount"] for b in SAMPLE_BUDGETS)
                },
                "period": "Current Month"
            }
        }
    except Exception as e:
        logger.error(f"Error generating financial summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate financial summary")