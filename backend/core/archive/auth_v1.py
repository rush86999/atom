from datetime import datetime, timedelta
import os
import secrets
from typing import Any, Optional, Union
from jose import JWTError, jwt

# Make bcrypt optional for authentication
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

import logging
from fastapi import Depends, HTTPException, status
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
        SECRET_KEY = secrets.token_urlsafe(32)
        logger.warning("⚠️ Using auto-generated secret key for development. Set SECRET_KEY in production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password, hashed_password):
    """Verify password using bcrypt if available, otherwise fallback"""
    if not BCRYPT_AVAILABLE:
        logger.warning("bcrypt not available - using insecure password verification")
        # Fallback: Simple string comparison (INSECURE - for development only)
        return plain_password == hashed_password

    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password, hashed_password)

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

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
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
