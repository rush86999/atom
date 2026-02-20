
import sys
from core.database import SessionLocal
from core.models import User, Workspace

print("--- Checking User Workspaces ---")
db = SessionLocal()
try:
    user = db.query(User).filter(User.id == "user-123").first()
    if not user:
        print("User user-123 not found!")
    else:
        print(f"User found: {user.email}")
        print("Accessing workspaces...")
        workspaces = user.workspaces
        print(f"Workspaces count: {len(workspaces)}")
        for ws in workspaces:
            print(f" - {ws.name} ({ws.id})")
            
except Exception as e:
    print("\nXXX EXCEPTION CAUGHT XXX")
    print(f"Type: {type(e)}")
    print(f"String: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
