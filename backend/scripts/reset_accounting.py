import logging
import sys
import os
from sqlalchemy import text

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from core.database import engine, Base
import core.models # Crucial for workspace table
import accounting.models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_accounting():
    tables = [
        "accounting_journal_entries",
        "accounting_transactions",
        "accounting_categorization_proposals",
        "accounting_rules",
        "accounting_budgets",
        "accounting_accounts",
        "accounting_tax_nexus",
        "financial_close_checklists"
    ]
    
    with engine.connect() as conn:
        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        conn.commit()
        logger.info("Dropped existing accounting tables")
        
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Recreated accounting tables with new schema")

if __name__ == "__main__":
    reset_accounting()
