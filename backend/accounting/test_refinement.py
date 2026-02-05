import asyncio
from datetime import datetime, timedelta
import logging
from accounting.categorizer import AICategorizer
from accounting.export_service import AccountExporter
from accounting.models import (
    Account,
    Budget,
    CategorizationProposal,
    EntryType,
    JournalEntry,
    Transaction,
)
from accounting.seeds import seed_default_accounts
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.cross_system_reasoning import CrossSystemReasoningEngine
from core.database import Base
import core.models

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_learning_and_reasoning():
    # 1. Setup DB
    db_url = "postgresql://atom:atom_password@127.0.0.1:5433/atom_db"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    workspace_id = "reasoning-test-ws"
    
    try:
        from core.models import User, Workspace
        if not db.query(Workspace).filter(Workspace.id == workspace_id).first():
            ws = Workspace(id=workspace_id, name="Reasoning Test")
            db.add(ws)
            db.commit()

        # Create user for reviewing
        test_user_id = "test-user-fpa"
        if not db.query(User).filter(User.id == test_user_id).first():
            user = User(id=test_user_id, email="test@example.com", first_name="Test", last_name="User", workspace_id=workspace_id)
            db.add(user)
            db.commit()

        # Clean old data if any (cascading cleanup)
        from accounting.models import (
            CategorizationProposal,
            CategorizationRule,
            JournalEntry,
            Transaction,
        )
        db.query(JournalEntry).filter(JournalEntry.account_id.in_(
            db.query(Account.id).filter(Account.workspace_id == workspace_id)
        )).delete(synchronize_session=False)
        db.query(CategorizationProposal).filter(CategorizationProposal.transaction_id.in_(
            db.query(Transaction.id).filter(Transaction.workspace_id == workspace_id)
        )).delete(synchronize_session=False)
        db.query(CategorizationRule).filter(CategorizationRule.workspace_id == workspace_id).delete()
        db.query(Transaction).filter(Transaction.workspace_id == workspace_id).delete()
        db.query(Account).filter(Account.workspace_id == workspace_id).delete()
        db.commit()

        seed_default_accounts(db, workspace_id)
        
        # Get accounts
        sw_acc = db.query(Account).filter(Account.workspace_id == workspace_id, Account.name == "Software & Subscriptions").first()
        cash_acc = db.query(Account).filter(Account.workspace_id == workspace_id, Account.name == "Cash and Cash Equivalents").first()

        # --- A. Test Learning Layer ---
        categorizer = AICategorizer(db)
        
        # 1. Create a transaction
        tx = Transaction(workspace_id=workspace_id, transaction_date=datetime.utcnow(), source="manual", description="AWS Cloud Services")
        db.add(tx)
        db.flush()
        
        # 2. Mock a proposal
        proposal = CategorizationProposal(transaction_id=tx.id, suggested_account_id=sw_acc.id, confidence=0.7, reasoning="Sounds like software")
        db.add(proposal)
        db.commit()
        
        # 3. Accept proposal (should create rule)
        print("Accepting proposal to trigger Learning Layer...")
        categorizer.accept_proposal(proposal.id, test_user_id)
        
        # 4. Check if rule exists
        from accounting.models import CategorizationRule
        rule = db.query(CategorizationRule).filter(CategorizationRule.workspace_id == workspace_id).first()
        print(f"✅ Rule created: {rule.merchant_pattern} -> {rule.target_account_id}")
        
        # 5. Propose again for a similar transaction (should use rule)
        tx2 = Transaction(workspace_id=workspace_id, transaction_date=datetime.utcnow(), source="manual", description="AWS Bill Dec")
        db.add(tx2)
        db.commit()
        
        print("Testing rule-based categorization...")
        prop2 = await categorizer.propose_categorization(tx2, workspace_id)
        print(f"✅ Categorized via rule: {prop2.reasoning}")

        # --- B. Test Financial Reasoning ---
        engine = CrossSystemReasoningEngine()
        
        # 1. Setup Budget ($500 for software)
        budget = Budget(
            workspace_id=workspace_id,
            category_id=sw_acc.id,
            amount=500.0,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        db.add(budget)
        
        # 2. Add Spend ($600)
        tx3 = Transaction(workspace_id=workspace_id, transaction_date=datetime.utcnow(), source="test", description="Expensive Software")
        db.add(tx3)
        db.flush()
        db.add(JournalEntry(transaction_id=tx3.id, account_id=sw_acc.id, type=EntryType.DEBIT, amount=600.0))
        db.add(JournalEntry(transaction_id=tx3.id, account_id=cash_acc.id, type=EntryType.CREDIT, amount=600.0))
        db.commit()
        
        print("Checking financial integrity (Reasoning Engine)...")
        alerts = await engine.check_financial_integrity(db, workspace_id)
        for alert in alerts:
            print(f"✅ ALERT FOUND: {alert['type']} - {alert['description']}")

        # --- C. Test Regulatory Compliance (Export) ---
        print("Testing Accountant Export (GL CSV)...")
        exporter = AccountExporter(db)
        
        # Add some GAAP mapping for testing
        sw_acc.standards_mapping = {"gaap": "5100-SaaS", "ifrs": "5100-S"}
        db.commit()
        
        csv_data = exporter.export_general_ledger_csv(workspace_id)
        if "5100-SaaS" in csv_data:
            print("✅ Export CSV contains GAAP mappings")
        else:
            print("❌ Export CSV missing GAAP mappings")
            
        tb = exporter.export_trial_balance_json(workspace_id)
        if len(tb["accounts"]) > 0:
             print(f"✅ Trial Balance generated with {len(tb['accounts'])} accounts")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_learning_and_reasoning())
