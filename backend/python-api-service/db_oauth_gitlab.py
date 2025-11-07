"""
GitLab OAuth Database Integration
Handles GitLab OAuth token storage and retrieval
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg

# Configure logging
logger = logging.getLogger(__name__)

# Database table name
GITLAB_OAUTH_TABLE = "gitlab_oauth_tokens"


async def init_gitlab_oauth_table(db_pool: asyncpg.Pool) -> bool:
    """
    Initialize GitLab OAuth table in database

    Args:
        db_pool: Database connection pool

    Returns:
        True if successful, False otherwise
    """
    try:
        async with db_pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = $1
                );
                """,
                GITLAB_OAUTH_TABLE,
            )

            if not table_exists:
                # Create table
                await conn.execute(
                    f"""
                    CREATE TABLE {GITLAB_OAUTH_TABLE} (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT,
                        token_type VARCHAR(50),
                        expires_at TIMESTAMP,
                        scope TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id)
                    );
                    """
                )

                # Create indexes
                await conn.execute(
                    f"CREATE INDEX idx_{GITLAB_OAUTH_TABLE}_user_id ON {GITLAB_OAUTH_TABLE}(user_id);"
                )
                await conn.execute(
                    f"CREATE INDEX idx_{GITLAB_OAUTH_TABLE}_expires_at ON {GITLAB_OAUTH_TABLE}(expires_at);"
                )

                logger.info(
                    f"GitLab OAuth table '{GITLAB_OAUTH_TABLE}' created successfully"
                )
            else:
                logger.info(f"GitLab OAuth table '{GITLAB_OAUTH_TABLE}' already exists")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize GitLab OAuth table: {str(e)}")
        return False


async def save_gitlab_tokens(
    db_pool: asyncpg.Pool, user_id: str, tokens: Dict[str, any]
) -> bool:
    """
    Save GitLab OAuth tokens for user

    Args:
        db_pool: Database connection pool
        user_id: User identifier
        tokens: Dictionary containing token data

    Returns:
        True if successful, False otherwise
    """
    try:
        async with db_pool.acquire() as conn:
            # Parse token data
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            token_type = tokens.get("token_type", "Bearer")
            scope = tokens.get("scope")

            # Calculate expiration time
            expires_in = tokens.get("expires_in", 7200)  # Default 2 hours
            expires_at = datetime.now().timestamp() + expires_in

            # Convert to datetime
            expires_at_dt = datetime.fromtimestamp(expires_at)

            # Check if user already has tokens
            existing_tokens = await conn.fetchval(
                f"SELECT user_id FROM {GITLAB_OAUTH_TABLE} WHERE user_id = $1", user_id
            )

            if existing_tokens:
                # Update existing tokens
                await conn.execute(
                    f"""
                    UPDATE {GITLAB_OAUTH_TABLE}
                    SET access_token = $1,
                        refresh_token = $2,
                        token_type = $3,
                        expires_at = $4,
                        scope = $5,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $6
                    """,
                    access_token,
                    refresh_token,
                    token_type,
                    expires_at_dt,
                    scope,
                    user_id,
                )
                logger.info(f"Updated GitLab tokens for user {user_id}")
            else:
                # Insert new tokens
                await conn.execute(
                    f"""
                    INSERT INTO {GITLAB_OAUTH_TABLE}
                    (user_id, access_token, refresh_token, token_type, expires_at, scope)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    user_id,
                    access_token,
                    refresh_token,
                    token_type,
                    expires_at_dt,
                    scope,
                )
                logger.info(f"Saved new GitLab tokens for user {user_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to save GitLab tokens for user {user_id}: {str(e)}")
        return False


async def get_gitlab_tokens(
    db_pool: asyncpg.Pool, user_id: str
) -> Optional[Dict[str, any]]:
    """
    Retrieve GitLab OAuth tokens for user

    Args:
        db_pool: Database connection pool
        user_id: User identifier

    Returns:
        Dictionary with token data or None if not found/expired
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                f"""
                SELECT access_token, refresh_token, token_type, expires_at, scope, created_at, updated_at
                FROM {GITLAB_OAUTH_TABLE}
                WHERE user_id = $1
                """,
                user_id,
            )

            if result:
                # Check if token is expired
                expires_at = result["expires_at"]
                if expires_at and expires_at < datetime.now():
                    logger.warning(f"GitLab tokens expired for user {user_id}")
                    return None

                tokens = {
                    "access_token": result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "token_type": result["token_type"],
                    "expires_at": result["expires_at"].isoformat()
                    if result["expires_at"]
                    else None,
                    "scope": result["scope"],
                    "created_at": result["created_at"].isoformat()
                    if result["created_at"]
                    else None,
                    "updated_at": result["updated_at"].isoformat()
                    if result["updated_at"]
                    else None,
                }

                logger.info(f"Retrieved GitLab tokens for user {user_id}")
                return tokens
            else:
                logger.info(f"No GitLab tokens found for user {user_id}")
                return None

    except Exception as e:
        logger.error(f"Failed to get GitLab tokens for user {user_id}: {str(e)}")
        return None


async def delete_gitlab_tokens(db_pool: asyncpg.Pool, user_id: str) -> bool:
    """
    Delete GitLab OAuth tokens for user

    Args:
        db_pool: Database connection pool
        user_id: User identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {GITLAB_OAUTH_TABLE} WHERE user_id = $1", user_id
            )

            if "DELETE 1" in result:
                logger.info(f"Deleted GitLab tokens for user {user_id}")
                return True
            else:
                logger.info(f"No GitLab tokens to delete for user {user_id}")
                return False

    except Exception as e:
        logger.error(f"Failed to delete GitLab tokens for user {user_id}: {str(e)}")
        return False


async def get_all_gitlab_users(db_pool: asyncpg.Pool) -> List[str]:
    """
    Get all users with GitLab OAuth tokens

    Args:
        db_pool: Database connection pool

    Returns:
        List of user IDs
    """
    try:
        async with db_pool.acquire() as conn:
            results = await conn.fetch(f"SELECT user_id FROM {GITLAB_OAUTH_TABLE}")

            user_ids = [row["user_id"] for row in results]
            logger.info(f"Found {len(user_ids)} users with GitLab tokens")
            return user_ids

    except Exception as e:
        logger.error(f"Failed to get GitLab users: {str(e)}")
        return []


async def cleanup_expired_gitlab_tokens(db_pool: asyncpg.Pool) -> int:
    """
    Clean up expired GitLab OAuth tokens

    Args:
        db_pool: Database connection pool

    Returns:
        Number of tokens deleted
    """
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {GITLAB_OAUTH_TABLE} WHERE expires_at < CURRENT_TIMESTAMP"
            )

            # Parse the result to get count
            if "DELETE" in result:
                count = int(result.split()[1])
                logger.info(f"Cleaned up {count} expired GitLab tokens")
                return count
            else:
                return 0

    except Exception as e:
        logger.error(f"Failed to cleanup expired GitLab tokens: {str(e)}")
        return 0


async def get_gitlab_token_stats(db_pool: asyncpg.Pool) -> Dict[str, any]:
    """
    Get statistics about GitLab OAuth tokens

    Args:
        db_pool: Database connection pool

    Returns:
        Dictionary with token statistics
    """
    try:
        async with db_pool.acquire() as conn:
            # Get total count
            total_count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {GITLAB_OAUTH_TABLE}"
            )

            # Get active count (not expired)
            active_count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {GITLAB_OAUTH_TABLE} WHERE expires_at > CURRENT_TIMESTAMP"
            )

            # Get expired count
            expired_count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {GITLAB_OAUTH_TABLE} WHERE expires_at <= CURRENT_TIMESTAMP"
            )

            # Get most recent update
            most_recent = await conn.fetchval(
                f"SELECT MAX(updated_at) FROM {GITLAB_OAUTH_TABLE}"
            )

            stats = {
                "total_tokens": total_count,
                "active_tokens": active_count,
                "expired_tokens": expired_count,
                "most_recent_update": most_recent.isoformat() if most_recent else None,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"GitLab token stats: {stats}")
            return stats

    except Exception as e:
        logger.error(f"Failed to get GitLab token stats: {str(e)}")
        return {
            "total_tokens": 0,
            "active_tokens": 0,
            "expired_tokens": 0,
            "most_recent_update": None,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


# Flask blueprint for GitLab OAuth routes
from flask import Blueprint, jsonify, request

gitlab_oauth_bp = Blueprint("gitlab_oauth_bp", __name__)


@gitlab_oauth_bp.route("/api/auth/gitlab/tokens/save", methods=["POST"])
async def save_gitlab_tokens_route():
    """
    Save GitLab OAuth tokens via API
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided", "success": False}), 400

        user_id = data.get("user_id")
        tokens = data.get("tokens")

        if not user_id or not tokens:
            return jsonify(
                {"error": "User ID and tokens are required", "success": False}
            ), 400

        # Get database pool from app context
        db_pool = request.app.config.get("DB_POOL")
        if not db_pool:
            return jsonify({"error": "Database not available", "success": False}), 500

        success = await save_gitlab_tokens(db_pool, user_id, tokens)

        if success:
            return jsonify({"success": True, "message": "Tokens saved successfully"})
        else:
            return jsonify({"error": "Failed to save tokens", "success": False}), 500

    except Exception as e:
        logger.error(f"Save GitLab tokens API error: {str(e)}")
        return jsonify(
            {"error": f"Internal server error: {str(e)}", "success": False}
        ), 500


@gitlab_oauth_bp.route("/api/auth/gitlab/tokens/get", methods=["GET"])
async def get_gitlab_tokens_route():
    """
    Get GitLab OAuth tokens via API
    """
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "User ID is required", "success": False}), 400

        # Get database pool from app context
        db_pool = request.app.config.get("DB_POOL")
        if not db_pool:
            return jsonify({"error": "Database not available", "success": False}), 500

        tokens = await get_gitlab_tokens(db_pool, user_id)

        if tokens:
            return jsonify({"success": True, "tokens": tokens})
        else:
            return jsonify({"error": "No tokens found", "success": False}), 404

    except Exception as e:
        logger.error(f"Get GitLab tokens API error: {str(e)}")
        return jsonify(
            {"error": f"Internal server error: {str(e)}", "success": False}
        ), 500


@gitlab_oauth_bp.route("/api/auth/gitlab/tokens/delete", methods=["DELETE"])
async def delete_gitlab_tokens_route():
    """
    Delete GitLab OAuth tokens via API
    """
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "User ID is required", "success": False}), 400

        # Get database pool from app context
        db_pool = request.app.config.get("DB_POOL")
        if not db_pool:
            return jsonify({"error": "Database not available", "success": False}), 500

        success = await delete_gitlab_tokens(db_pool, user_id)

        if success:
            return jsonify({"success": True, "message": "Tokens deleted successfully"})
        else:
            return jsonify({"error": "No tokens to delete", "success": False}), 404

    except Exception as e:
        logger.error(f"Delete GitLab tokens API error: {str(e)}")
        return jsonify(
            {"error": f"Internal server error: {str(e)}", "success": False}
        ), 500


@gitlab_oauth_bp.route("/api/auth/gitlab/tokens/stats", methods=["GET"])
async def get_gitlab_token_stats_route():
    """
    Get GitLab OAuth token statistics via API
    """
    try:
        # Get database pool from app context
        db_pool = request.app.config.get("DB_POOL")
        if not db_pool:
            return jsonify({"error": "Database not available", "success": False}), 500

        stats = await get_gitlab_token_stats(db_pool)

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        logger.error(f"Get GitLab token stats API error: {str(e)}")
        return jsonify(
            {"error": f"Internal server error: {str(e)}", "success": False}
        ), 500
