import logging
import sys
import os
from sqlalchemy import text

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from core.database import engine, Base
import core.models
import accounting.models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recreate_accounting_tables():
    logger.info("Dropping and recreating accounting tables...")
    tables = [
        "accounting_journal_entries",
        "accounting_transactions",
        "accounting_categorization_proposals",
        "accounting_rules",
        "accounting_budgets",
        "accounting_accounts"
    ]
    
    with engine.connect() as conn:
        for table in tables:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                logger.info(f"Dropped {table}")
            except Exception as e:
                logger.warning(f"Could not drop {table}: {e}")
        conn.commit()
        
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Accounting tables recreated successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to recreate tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    recreate_accounting_tables()
