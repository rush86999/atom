
import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from core.lancedb_handler import LanceDBHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_lancedb():
    print("Checking LanceDB availability...")
    handler = LanceDBHandler()
    res = handler.test_connection()
    print(f"Connection Test Result: {res}")
    
    if res.get("status") == "success":
        print("✅ LanceDB is working.")
        # Try to search
        try:
            results = handler.search("documents", "test", limit=1)
            print(f"Search Test Result: {len(results)} results")
        except Exception as e:
            print(f"❌ Search Test Failed: {e}")
    else:
        print("❌ LanceDB is NOT working.")
        if "LanceDB not available" in res.get("message", ""):
            print("Tip: Check if lancedb and numpy are installed.")

if __name__ == "__main__":
    check_lancedb()
