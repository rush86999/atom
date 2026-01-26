import sys
import os
import json

sys.path.append(os.getcwd())

from backend.core.chat_session_manager import get_chat_session_manager

def test_persistence():
    print("Testing ChatSessionManager persistence...")
    mgr = get_chat_session_manager()
    print(f"Target File: {mgr.sessions_file}")
    
    # 1. Create a session
    sid = mgr.create_session("unit_test_user")
    print(f"Created Session: {sid}")
    
    # 2. Verify file content
    with open(mgr.sessions_file, 'r') as f:
        data = json.load(f)
    print(f"File content length: {len(data)}")
    
    found = any(s["session_id"] == sid for s in data)
    if found:
        print("SUCCESS: Session found in file.")
    else:
        print("FAILURE: Session NOT found in file.")

if __name__ == "__main__":
    test_persistence()
