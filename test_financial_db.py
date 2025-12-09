#!/usr/bin/env python3
"""
Test script for the financial database implementation
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.financial_database import financial_db

async def test_financial_database():
    """Test the financial database operations"""
    print("🔥 Testing Financial Database Implementation")
    print("=" * 50)

    try:
        # Initialize database
        print("\n1. Initializing financial database...")
        await financial_db.initialize()
        print("✅ Database initialized successfully")

        # Test creating a transaction
        print("\n2. Creating a test transaction...")
        transaction_id = await financial_db.create_transaction(
            description="Test Transaction - Coffee Shop",
            category="Meals",
            amount=-12.50,
            status="Completed"
        )
        print(f"✅ Created transaction: {transaction_id}")

        # Test getting transactions
        print("\n3. Fetching transactions...")
        transactions = await financial_db.get_transactions(limit=5)
        print(f"✅ Found {len(transactions)} transactions:")
        for tx in transactions:
            print(f"   - {tx['id']}: {tx['description']} (${tx['amount']:.2f})")

        # Test creating a budget
        print("\n4. Creating a test budget...")
        budget_id = await financial_db.create_budget(
            category="Meals",
            allocated_amount=200.00,
            period="2025-12"
        )
        print(f"✅ Created budget: {budget_id}")

        # Test getting budgets
        print("\n5. Fetching budgets...")
        budgets = await financial_db.get_budgets()
        print(f"✅ Found {len(budgets)} budgets:")
        for budget in budgets:
            print(f"   - {budget['category']}: ${budget['allocated_amount']:.2f} (period: {budget['period']})")

        # Test recording net worth
        print("\n6. Recording net worth...")
        net_worth_id = await financial_db.record_net_worth(
            total_assets=15000.00,
            total_liabilities=3500.00
        )
        print(f"✅ Recorded net worth: {net_worth_id}")

        # Test getting financial summary
        print("\n7. Generating financial summary...")
        summary = await financial_db.get_financial_summary()
        print(f"✅ Financial Summary for {summary['period']}:")
        print(f"   - Total Income: ${summary['total_income']:.2f}")
        print(f"   - Total Expenses: ${summary['total_expenses']:.2f}")
        print(f"   - Net Income: ${summary['net_income']:.2f}")
        print(f"   - Transaction Count: {summary['transaction_count']}")
        print(f"   - Categories: {', '.join(summary['categories'])}")

        print("\n🎉 All financial database tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_financial_database())