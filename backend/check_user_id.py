
from core.database import SessionLocal
from core.models import User

def check_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "user123@example.com").first()
        if user:
            print(f"✅ User found: {user.email}")
            print(f"🆔 ID: {user.id}")
            print(f"Status: {user.status}")
            print(f"Workspace: {user.workspace_id}")
        else:
            print("❌ User 'user123@example.com' not found!")
            
        # Also check if there is a user with id 'user-123' (literal)
        user_literal = db.query(User).filter(User.id == "user-123").first()
        if user_literal:
             print(f"✅ User with literal ID 'user-123' found: {user_literal.email}")
        else:
             print(f"ℹ️ No user with literal ID 'user-123' exists.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_user()
