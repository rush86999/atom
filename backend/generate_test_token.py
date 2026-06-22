"""
DEV-ONLY script: generate a short-lived admin JWT for local testing.

SECURITY: this script does NOT set SECRET_KEY itself. It reads from
the existing environment (loaded via dotenv at app startup). Running
this script in production has no effect — it requires SECRET_KEY to
already be set the same way the app sets it.

Usage:
    cd backend
    python generate_test_token.py
"""
import sys
import os
import datetime
from dotenv import load_dotenv

# Load env the same way the app does
load_dotenv()

# Add current directory to path
sys.path.append(os.getcwd())

# Use defaults that match a dev environment; never overwrite SECRET_KEY
# if it's already set (avoids leaking the dev key into production envs).
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

try:
    from jose import jwt

    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        print("ERROR: SECRET_KEY not set in environment")
        sys.exit(1)
    ALGORITHM = os.getenv("ALGORITHM", "HS256")

    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    to_encode = {"sub": "admin", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    print(f"TOKEN_START:{encoded_jwt}:TOKEN_END")
except ImportError:
    print("ERROR: python-jose not installed")
except Exception as e:
    print(f"ERROR: {e}")
