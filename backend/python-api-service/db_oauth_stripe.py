"""
Stripe OAuth Database Handler
Database operations for Stripe OAuth token management and user data storage
"""

import sqlite3
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

# Database configuration
DB_PATH = os.getenv("STRIPE_DB_PATH", "integrations.db")
STRIPE_TOKENS_TABLE = "stripe_oauth_tokens"
STRIPE_USER_DATA_TABLE = "stripe_user_data"


async def get_db_connection():
    """Get database connection"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def create_tables_if_not_exists():
    """Create Stripe tables if they don't exist"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()

        # Create Stripe OAuth tokens table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {STRIPE_TOKENS_TABLE} (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_type TEXT DEFAULT 'Bearer',
                account_id TEXT,
                scope TEXT,
                livemode INTEGER DEFAULT 0,
                expires_in INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # Create Stripe user data table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {STRIPE_USER_DATA_TABLE} (
                user_id TEXT PRIMARY KEY,
                account_id TEXT,
                email TEXT,
                business_name TEXT,
                display_name TEXT,
                country TEXT,
                currency TEXT,
                mcc TEXT,
                balance_available INTEGER DEFAULT 0,
                balance_pending INTEGER DEFAULT 0,
                created_utc INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES {STRIPE_TOKENS_TABLE}(user_id)
            )
        """)

        conn.commit()
        conn.close()
        logger.info("Stripe database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to create Stripe tables: {e}")
        raise


async def get_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Stripe OAuth tokens for user"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT * FROM {STRIPE_TOKENS_TABLE} WHERE user_id = ?
        """,
            (user_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Convert row to dict
        tokens = dict(row)

        # Parse metadata if exists
        if tokens.get("metadata"):
            try:
                tokens["metadata"] = json.loads(tokens["metadata"])
            except:
                tokens["metadata"] = {}

        # Get user data
        user_data = await get_user_stripe_data(user_id)
        if user_data:
            tokens["user_info"] = user_data

        return tokens

    except Exception as e:
        logger.error(f"Error getting Stripe tokens for user {user_id}: {e}")
        return None


async def save_tokens(user_id: str, tokens: Dict[str, Any]) -> bool:
    """Save Stripe OAuth tokens for user"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        # Prepare token data
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        token_type = tokens.get("token_type", "Bearer")
        account_id = tokens.get("account_id")
        scope = tokens.get("scope")
        livemode = 1 if tokens.get("livemode") else 0
        expires_in = tokens.get("expires_in")
        metadata = json.dumps(tokens.get("metadata", {}))

        # Insert or update tokens
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO {STRIPE_TOKENS_TABLE}
            (user_id, access_token, refresh_token, token_type, account_id, scope, livemode, expires_in, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                user_id,
                access_token,
                refresh_token,
                token_type,
                account_id,
                scope,
                livemode,
                expires_in,
                metadata,
            ),
        )

        # Save user data if available
        user_info = tokens.get("user_info")
        if user_info:
            await save_stripe_data(user_id, user_info)

        conn.commit()
        conn.close()
        logger.info(f"Stripe tokens saved successfully for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving Stripe tokens for user {user_id}: {e}")
        return False


async def delete_tokens(user_id: str) -> bool:
    """Delete Stripe OAuth tokens for user"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        # Delete tokens and user data
        cursor.execute(
            f"DELETE FROM {STRIPE_TOKENS_TABLE} WHERE user_id = ?", (user_id,)
        )
        cursor.execute(
            f"DELETE FROM {STRIPE_USER_DATA_TABLE} WHERE user_id = ?", (user_id,)
        )

        conn.commit()
        conn.close()
        logger.info(f"Stripe tokens deleted successfully for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error deleting Stripe tokens for user {user_id}: {e}")
        return False


async def get_user_stripe_data(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Stripe user data"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT * FROM {STRIPE_USER_DATA_TABLE} WHERE user_id = ?
        """,
            (user_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Convert row to dict
        user_data = dict(row)

        # Parse metadata if exists
        if user_data.get("metadata"):
            try:
                user_data["metadata"] = json.loads(user_data["metadata"])
            except:
                user_data["metadata"] = {}

        # Format balance data
        user_data["balance"] = {
            "available": [
                {
                    "amount": user_data.get("balance_available", 0),
                    "currency": user_data.get("currency", "usd"),
                }
            ],
            "pending": [
                {
                    "amount": user_data.get("balance_pending", 0),
                    "currency": user_data.get("currency", "usd"),
                }
            ],
        }

        return user_data

    except Exception as e:
        logger.error(f"Error getting Stripe user data for user {user_id}: {e}")
        return None


async def save_stripe_data(user_id: str, user_data: Dict[str, Any]) -> bool:
    """Save Stripe user data"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        # Prepare user data
        account_id = user_data.get("id")
        email = user_data.get("email")
        business_name = user_data.get("business_name")
        display_name = user_data.get("display_name")
        country = user_data.get("country")
        currency = user_data.get("currency")
        mcc = user_data.get("mcc")

        # Extract balance data
        balance_data = user_data.get("balance", {})
        balance_available = 0
        balance_pending = 0

        if balance_data.get("available"):
            for balance in balance_data["available"]:
                if balance.get("currency", "").lower() == currency:
                    balance_available = balance.get("amount", 0)
                    break

        if balance_data.get("pending"):
            for balance in balance_data["pending"]:
                if balance.get("currency", "").lower() == currency:
                    balance_pending = balance.get("amount", 0)
                    break

        created_utc = user_data.get("created_utc")
        metadata = json.dumps(user_data.get("metadata", {}))

        # Insert or update user data
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO {STRIPE_USER_DATA_TABLE}
            (user_id, account_id, email, business_name, display_name, country, currency, mcc,
             balance_available, balance_pending, created_utc, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                user_id,
                account_id,
                email,
                business_name,
                display_name,
                country,
                currency,
                mcc,
                balance_available,
                balance_pending,
                created_utc,
                metadata,
            ),
        )

        conn.commit()
        conn.close()
        logger.info(f"Stripe user data saved successfully for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving Stripe user data for user {user_id}: {e}")
        return False


async def list_users_with_stripe_access() -> List[Dict[str, Any]]:
    """List all users with Stripe access"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT t.user_id, t.account_id, t.scope, t.created_at,
                   d.email, d.business_name, d.country, d.currency
            FROM {STRIPE_TOKENS_TABLE} t
            LEFT JOIN {STRIPE_USER_DATA_TABLE} d ON t.user_id = d.user_id
            ORDER BY t.created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        users = []
        for row in rows:
            user_data = dict(row)
            users.append(user_data)

        return users

    except Exception as e:
        logger.error(f"Error listing users with Stripe access: {e}")
        return []


async def cleanup_expired_tokens() -> int:
    """Clean up expired Stripe tokens (placeholder for future implementation)"""
    # Stripe access tokens don't typically expire, but this can be used for refresh token cleanup
    # For now, return 0 as no cleanup is performed
    return 0


async def get_token_stats() -> Dict[str, Any]:
    """Get Stripe token statistics"""
    try:
        await create_tables_if_not_exists()
        conn = await get_db_connection()
        cursor = conn.cursor()

        # Get total users with Stripe access
        cursor.execute(f"SELECT COUNT(*) as total FROM {STRIPE_TOKENS_TABLE}")
        total_users = cursor.fetchone()["total"]

        # Get users by country
        cursor.execute(f"""
            SELECT country, COUNT(*) as count
            FROM {STRIPE_USER_DATA_TABLE}
            WHERE country IS NOT NULL
            GROUP BY country
        """)
        users_by_country = {row["country"]: row["count"] for row in cursor.fetchall()}

        # Get average balance
        cursor.execute(f"""
            SELECT AVG(balance_available) as avg_balance
            FROM {STRIPE_USER_DATA_TABLE}
            WHERE balance_available > 0
        """)
        avg_balance_row = cursor.fetchone()
        avg_balance = avg_balance_row["avg_balance"] if avg_balance_row else 0

        conn.close()

        return {
            "total_users": total_users,
            "users_by_country": users_by_country,
            "average_balance": round(avg_balance, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting Stripe token stats: {e}")
        return {
            "total_users": 0,
            "users_by_country": {},
            "average_balance": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
