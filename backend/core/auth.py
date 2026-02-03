import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
import bcrypt
from jose import JWTError, jwt

BCRYPT_AVAILABLE = True

import logging
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User

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
    """Verify password using bcrypt"""
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    
    # Truncate to 71 bytes as bcrypt has a 72-byte limit and includes a null terminator
    plain_password = plain_password[:71]
    
    try:
        return bcrypt.checkpw(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error in verify_password: {e}")
        return False

def get_password_hash(password):
    """Hash password using bcrypt"""
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

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify JWT token.

    Returns the token payload if valid, None otherwise.
    This is a synchronous version for use in non-async contexts.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Failed to decode token: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        return None

def generate_satellite_key() -> str:
    """Generate a secure Satellite API Key (sk-...)"""
    return f"sk-{secrets.token_hex(24)}"
