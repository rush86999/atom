import sys
import os
from datetime import datetime, timedelta
import secrets
import hashlib

# Add backend to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_path not in sys.path:
    sys.path.append(backend_path)

# Mock environment variables for testing if they don't exist
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/atom.test.db")

from core.database import SessionLocal, Base, engine
from core.models import User, PasswordResetToken, UserStatus
from core.auth import get_password_hash, verify_password

def setup_test_db():
    # Make sure data dir exists
    os.makedirs("./data", exist_ok=True)
    Base.metadata.create_all(bind=engine)

def test_password_reset_flow():
    print("Starting Password Reset Flow Test...")
    setup_test_db()
    db = SessionLocal()
    try:
        # 1. Create a test user
        test_email = f"test_{secrets.token_hex(4)}@example.com"
        password = "testpassword123"
        user = User(
            email=test_email,
            password_hash=get_password_hash(password),
            first_name="Test",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"  [✓] Created test user: {test_email}")

        # 2. Simulate forgot password (generate token)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(reset_token)
        db.commit()
        print(f"  [✓] Generated reset token: {token}")

        # 3. Verify token
        db_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        assert db_token is not None, "Token not found in DB"
        assert db_token.user_id == user.id, "Token user_id mismatch"
        print("  [✓] Token verification in DB successful")

        # 4. Reset password
        new_password = "newpassword456"
        user.password_hash = get_password_hash(new_password)
        db_token.is_used = True
        db.commit()
        print("  [✓] Password reset in DB successful")

        # 5. Verify new password
        db.refresh(user)
        assert verify_password(new_password, user.password_hash), "New password verification failed"
        assert not verify_password(password, user.password_hash), "Old password still works"
        print("  [✓] Final password verification successful")

        # 6. Cleanup
        db.delete(db_token)
        db.delete(user)
        db.commit()
        print("  [✓] Cleanup completed")
        print("\nAll password reset tests PASSED!")

    except Exception as e:
        print(f"  [✗] Test failed: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    test_password_reset_flow()
