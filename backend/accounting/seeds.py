import uuid
from accounting.models import Account, AccountType
from sqlalchemy.orm import Session


def seed_default_accounts(db: Session, workspace_id: str):
    """Seed a basic Chart of Accounts for a workspace"""
    
    # 1. Assets
    cash = Account(
        workspace_id=workspace_id,
        name="Cash and Cash Equivalents",
        code="1000",
        type=AccountType.ASSET,
        description="General cash account"
    )
    receivables = Account(
        workspace_id=workspace_id,
        name="Accounts Receivable",
        code="1100",
        type=AccountType.ASSET,
        description="Money owed by customers"
    )
    
    payables = Account(
        workspace_id=workspace_id,
        name="Accounts Payable",
        code="2000",
        type=AccountType.LIABILITY,
        description="Money owed to vendors"
    )
    deferred_revenue = Account(
        workspace_id=workspace_id,
        name="Deferred Revenue",
        code="2100",
        type=AccountType.LIABILITY,
        description="Revenue received but not yet earned"
    )
    
    # 3. Revenue
    sales = Account(
        workspace_id=workspace_id,
        name="Sales Revenue",
        code="4000",
        type=AccountType.REVENUE,
        description="Income from sales"
    )
    
    # 4. Expenses
    marketing = Account(
        workspace_id=workspace_id,
        name="Marketing Expense",
        code="5000",
        type=AccountType.EXPENSE,
        description="Advertising and marketing costs"
    )
    software = Account(
        workspace_id=workspace_id,
        name="Software & Subscriptions",
        code="5100",
        type=AccountType.EXPENSE,
        description="SaaS and software licenses"
    )
    rent = Account(
        workspace_id=workspace_id,
        name="Rent & Utilities",
        code="5200",
        type=AccountType.EXPENSE,
        description="Office rent and utilities"
    )

    db.add_all([cash, receivables, payables, deferred_revenue, sales, marketing, software, rent])
    db.commit()
    return {
        "cash": cash.id,
        "receivables": receivables.id,
        "payables": payables.id,
        "sales": sales.id,
        "marketing": marketing.id,
        "software": software.id,
        "rent": rent.id
    }
