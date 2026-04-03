import sys
import os
import logging
import requests
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import SessionLocal
from core.models import User
from core.auth import verify_password, get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_login():
    db = SessionLocal()
    email = "admin@example.com"
    password = "securePass123"
    
    print(f"\n--- Testing DB Credential for {email} ---")
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print("❌ User not found in DB!")
            return
            
        print(f"User Found: {user.id}")
        print(f"Stored Hash: {user.password_hash}")
        
        # Test Verify Password
        is_valid = verify_password(password, user.password_hash)
        print(f"Password Check ('{password}'): {'✅ VALID' if is_valid else '❌ INVALID'}")
        
        if not is_valid:
            print("Resetting password to ensure validity...")
            new_hash = get_password_hash(password)
            user.password_hash = new_hash
            db.commit()
            print("✓ Password reset. Re-verifying...")
            is_valid_recheck = verify_password(password, new_hash)
            print(f"Re-check: {'✅ VALID' if is_valid_recheck else '❌ INVALID'}")

    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        db.close()

    print(f"\n--- Testing API Login Endpoint ---")
    try:
        # Test JSON login (New way)
        payload = {"username": email, "password": password}
        print(f"Posting JSON to /api/auth/login: {payload}")
        res = requests.post("http://localhost:8000/api/auth/login", json=payload)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
        
        if res.status_code != 200:
             # Test Form Login (Old way fallback?)
             print("\nTrying Form Data...")
             res_form = requests.post("http://localhost:8000/api/auth/login", data=payload)
             print(f"Status: {res_form.status_code}")
             print(f"Response: {res_form.text}")

    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    test_login()
