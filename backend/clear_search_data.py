import logging
import shutil
import os
from core.lancedb_handler import get_lancedb_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_data():
    handler = get_lancedb_handler()
    if not handler.db:
        print("LanceDB not available.")
        return

    table_name = "documents"
    if table_name in handler.db.table_names():
        print(f"Dropping table '{table_name}'...")
        handler.db.drop_table(table_name)
        print("Table dropped successfully.")
    else:
        print(f"Table '{table_name}' does not exist.")
        
    # Also verify directory cleanup if necessary
    # (LanceDB drop_table usually handles this, but we can check)
    
if __name__ == "__main__":
    confirm = input("This will DELETE ALL SEARCH DATA. Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        clear_data()
    else:
        print("Operation cancelled.")
