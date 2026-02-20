
import sys
import os
import shutil
import logging
import traceback

# Add current directory to path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

try:
    from core.lancedb_handler import get_lancedb_handler
    
    # List of workspaces to check
    # In a real scenario, we would iterate over all subdirectories in ./data/atom_memory
    base_uri = os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
    
    workspaces = []
    if os.path.exists(base_uri):
        workspaces = [d for d in os.listdir(base_uri) if os.path.isdir(os.path.join(base_uri, d))]
    
    # Also add default workspaces if not present
    if "default_shared" not in workspaces:
        workspaces.append("default_shared")
    if "ws-123" not in workspaces:
        workspaces.append("ws-123")
        
    print(f"Checking workspaces: {workspaces}")
    
    for ws_id in workspaces:
        try:
            print(f"--- Processing workspace: {ws_id} ---")
            handler = get_lancedb_handler(ws_id)
            table_name = "documents"
            
            if table_name in handler.db.table_names():
                table = handler.get_table(table_name)
                schema = table.schema
                metadata_field = schema.field("metadata")
                print(f"  Current metadata type: {metadata_field.type}")
                
                # Check if it is a Struct
                is_struct = "struct" in str(metadata_field.type).lower()
                
                if is_struct:
                    print(f"  DETECTED STRUCT SCHEMA. Dropping table '{table_name}' to force migration to string...")
                    handler.db.drop_table(table_name)
                    print(f"  Table '{table_name}' dropped.")
                else:
                    print(f"  Schema looks correct (String). Skipping.")
            else:
                print(f"  Table '{table_name}' not found.")
                
        except Exception as e:
            print(f"  Error processing {ws_id}: {e}")
            traceback.print_exc()

    print("\n--- Schema Fix Complete ---")

except Exception as e:
    print(f"Global Error: {e}")
    traceback.print_exc()
