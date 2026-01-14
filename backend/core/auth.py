import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt, JWTError

# Make bcrypt optional for authentication
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User
import logging

# Configuration
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production" or os.getenv("NODE_ENV") == "production":
        raise ValueError("SECRET_KEY environment variable is required in production")
    else:
        # Match NextAuth default secret for development
        SECRET_KEY = "atom_secure_secret_2025_fixed_key"
        logger.warning("⚠️ Using hardcoded secret key (matching NextAuth) for development.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password, hashed_password):
    """Verify password using bcrypt if available, otherwise fallback"""
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available - using insecure password verification")
        # Fallback: Simple string comparison (INSECURE - for development only)
        # Fallback: Check if hashed_password looks like hex
        try:
             # Try to match the get_password_hash fallback (hex)
             if isinstance(plain_password, str):
                 plain_bytes = plain_password.encode('utf-8')
             else:
                 plain_bytes = plain_password
             
             return plain_bytes.hex() == hashed_password
        except:
             return plain_password == hashed_password

    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(plain_password, hashed_password)
    except ValueError as e:
        logger.warning(f"bcrypt check failed (possibly invalid hash format): {e}")
        # Fallback for legacy/dev hashes: try plain comparison if hash doesn't look like bcrypt
        if plain_password.decode('utf-8') == hashed_password.decode('utf-8'):
             logger.warning("⚠️  Auth successful using INSECURE fallback (legacy hash). Please reset password.")
             return True
        return False
    except Exception as e:
        logger.error(f"Unexpected error in verify_password: {e}")
        return False

def get_password_hash(password):
    """Hash password using bcrypt if available, otherwise fallback"""
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available - using insecure password hashing")
        # Fallback: Simple encoding (INSECURE - for development only)
        if isinstance(password, str):
            password = password.encode('utf-8')
        return password.hex()

    # Bcrypt has a 72 byte limit
    if isinstance(password, str):
        # Encode to bytes, truncate to 71 bytes (safe margin)
        password = password.encode('utf-8')[:71]

    # Generate salt and hash
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt




async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current user from Bearer token OR NextAuth session cookie
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check Cookie if Header is missing
    if not token:
        token = request.cookies.get("next-auth.session-token")
        # Also check for secure cookie name if in production
        if not token:
            token = request.cookies.get("__Secure-next-auth.session-token")
            
    if not token:
        logger.warning("AUTH DEBUG: No token found in header or cookie")
        raise credentials_exception

    try:
        # logger.info(f"AUTH DEBUG: Attempting to decode token: {token[:15]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            # Try "id" field if "sub" is missing (NextAuth sometimes differs)
            user_id = payload.get("id")
            if user_id is None:
                logger.warning("AUTH DEBUG: Token payload missing 'sub' and 'id'")
                raise credentials_exception
    except JWTError as e:
        logger.warning(f"AUTH DEBUG: JWT Decode Error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"AUTH DEBUG: Unexpected Auth Error: {e}")
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"AUTH DEBUG: User {user_id} not found in DB")
        raise credentials_exception
    return user

async def get_current_user_ws(token: str, db: Session):
    """Get user from token for WebSocket connections"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except JWTError:
        return None
