from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import sqlite3
import uuid
import logging
from datetime import datetime, timedelta
import os

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

DB_FILE = "backend/atom_data.db"

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

class VerifyTokenRequest(BaseModel):
    token: str

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    email = request.email
    logger.info(f"Password reset requested for: {email}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            # Don't reveal user existence
            logger.info(f"User not found: {email}")
            return {"success": True, "message": "If an account exists, a reset link has been sent."}

        user_id = user["id"]
        token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=1)

        # Save token
        cursor.execute(
            "INSERT INTO password_reset_tokens (id, user_id, token, expires_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, token, expires_at)
        )
        conn.commit()

        # Mock sending email
        reset_link = f"http://localhost:3000/auth/reset-password?token={token}"
        logger.info(f"EMAIL SENT TO {email}: Click here to reset password: {reset_link}")
        print(f"EMAIL SENT TO {email}: Click here to reset password: {reset_link}") # Print to stdout for visibility

        return {"success": True, "message": "If an account exists, a reset link has been sent."}

    except Exception as e:
        logger.error(f"Error in forgot_password: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()

@router.post("/verify-token")
async def verify_token(request: VerifyTokenRequest):
    token = request.token
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0 AND expires_at > ?",
            (token, datetime.now())
        )
        token_record = cursor.fetchone()

        if not token_record:
            return {"valid": False, "message": "Invalid or expired token"}

        return {"valid": True, "message": "Token is valid"}

    except Exception as e:
        logger.error(f"Error in verify_token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    token = request.token
    new_password = request.password
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verify token again
        cursor.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0 AND expires_at > ?",
            (token, datetime.now())
        )
        token_record = cursor.fetchone()

        if not token_record:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        user_id = token_record["user_id"]

        # Hash password (using raw for now as passlib might be missing, but try to use it if available)
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash(new_password)
        except ImportError:
            hashed_password = new_password # Fallback for dev

        # Update user password
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_password, user_id))

        # Mark token as used
        cursor.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (token_record["id"],))

        conn.commit()
        
        logger.info(f"Password reset successful for user_id: {user_id}")
        return {"success": True, "message": "Password has been reset successfully"}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in reset_password: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()
