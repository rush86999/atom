
import sys
import os
import datetime

# Add current directory to path
sys.path.append(os.getcwd())

# Mock environment if needed
os.environ["SECRET_KEY"] = "atom_secure_secret_2025_fixed_key" 
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

try:
    from jose import jwt
    
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM")
    
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    to_encode = {"sub": "admin", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    print(f"TOKEN_START:{encoded_jwt}:TOKEN_END")
except ImportError:
    print("ERROR: python-jose not installed")
except Exception as e:
    print(f"ERROR: {e}")
