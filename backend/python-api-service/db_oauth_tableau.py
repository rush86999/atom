import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from asyncpg import Pool
from urllib.parse import parse_qs
import base64
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class TableauTokenManager:
    """Tableau OAuth Token Management Database Functions"""
    
    def __init__(self):
        self.fernet = Fernet(os.getenv("ATOM_OAUTH_ENCRYPTION_KEY"))
    
    async def init_tableau_oauth_table(self, db_pool: Pool) -> bool:
        """Initialize Tableau OAuth table"""
        try:
            # Run the schema if it doesn't exist
            schema_file = "migrations/tableau_schema.sql"
            if os.path.exists(schema_file):
                async with db_pool.acquire() as conn:
                    with open(schema_file, 'r') as f:
                        schema_sql = f.read()
                    await conn.execute(schema_sql)
                logger.info("Tableau OAuth tables initialized")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Tableau OAuth tables: {e}")
            return False
    
    async def store_tableau_tokens(self, db_pool: Pool, user_id: str, 
                                 email: str, tokens: Dict[str, Any], 
                                 site_info: Dict[str, Any] = None) -> bool:
        """Store Tableau OAuth tokens in database"""
        try:
            # Encrypt tokens
            encrypted_tokens = self.fernet.encrypt(json.dumps(tokens).encode())
            
            # Calculate expiration
            expires_at = None
            if tokens.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timezone.timedelta(seconds=tokens["expires_in"])
            
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO tableau_oauth_tokens 
                    (user_id, email, access_token, refresh_token, expires_at, 
                     site_id, site_name, site_content_url, encrypted_tokens)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET
                        email = EXCLUDED.email,
                        access_token = EXCLUDED.access_token,
                        refresh_token = EXCLUDED.refresh_token,
                        expires_at = EXCLUDED.expires_at,
                        site_id = EXCLUDED.site_id,
                        site_name = EXCLUDED.site_name,
                        site_content_url = EXCLUDED.site_content_url,
                        encrypted_tokens = EXCLUDED.encrypted_tokens,
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                """, user_id, email, tokens.get("access_token"), 
                     tokens.get("refresh_token"), expires_at,
                     site_info.get("id") if site_info else None,
                     site_info.get("name") if site_info else None,
                     site_info.get("contentUrl") if site_info else None,
                     encrypted_tokens.decode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store Tableau tokens: {e}")
            return False
    
    async def get_user_tableau_tokens(self, db_pool: Pool, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's Tableau tokens from database"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT user_id, email, access_token, refresh_token, 
                           expires_at, site_id, site_name, site_content_url,
                           encrypted_tokens, is_active, updated_at
                    FROM tableau_oauth_tokens
                    WHERE user_id = $1 AND is_active = TRUE
                """, user_id)
                
                if not row:
                    return None
                
                # Decrypt tokens
                decrypted_tokens = self.fernet.decrypt(row["encrypted_tokens"].encode())
                token_data = json.loads(decrypted_tokens.decode())
                
                # Combine with database info
                return {
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "access_token": row["access_token"],
                    "refresh_token": row["refresh_token"],
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                    "site_id": row["site_id"],
                    "site_name": row["site_name"],
                    "site_content_url": row["site_content_url"],
                    "user_content_url": f"https://online.tableau.com/t/{row['site_name']}" if row["site_name"] else None,
                    "token_data": token_data,
                    "is_active": row["is_active"],
                    "updated_at": row["updated_at"].isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau tokens: {e}")
            return None
    
    async def refresh_tableau_tokens(self, db_pool: Pool, user_id: str, 
                                  new_tokens: Dict[str, Any]) -> bool:
        """Update user's Tableau tokens"""
        try:
            # Encrypt new tokens
            encrypted_tokens = self.fernet.encrypt(json.dumps(new_tokens).encode())
            
            # Calculate new expiration
            expires_at = None
            if new_tokens.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timezone.timedelta(seconds=new_tokens["expires_in"])
            
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tableau_oauth_tokens
                    SET access_token = $2,
                        refresh_token = COALESCE($3, refresh_token),
                        expires_at = $4,
                        encrypted_tokens = $5,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, new_tokens.get("access_token"),
                     new_tokens.get("refresh_token"), expires_at,
                     encrypted_tokens.decode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh Tableau tokens: {e}")
            return False
    
    async def delete_tableau_tokens(self, db_pool: Pool, user_id: str) -> bool:
        """Delete user's Tableau tokens (logout)"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tableau_oauth_tokens
                    SET is_active = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete Tableau tokens: {e}")
            return False
    
    async def is_token_expired(self, db_pool: Pool, user_id: str) -> bool:
        """Check if user's Tableau token is expired"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT expires_at FROM tableau_oauth_tokens
                    WHERE user_id = $1 AND is_active = TRUE
                """, user_id)
                
                if not row or not row["expires_at"]:
                    return True
                
                # Add 5-minute buffer
                return row["expires_at"] < datetime.now(timezone.utc) - timezone.timedelta(minutes=5)
                
        except Exception as e:
            logger.error(f"Failed to check token expiration: {e}")
            return True
    
    async def cache_workbook_data(self, db_pool: Pool, user_id: str, 
                                workbook: Dict[str, Any]) -> bool:
        """Cache workbook data"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO tableau_workbooks_cache 
                    (user_id, workbook_id, workbook_data, workbook_name,
                     project_id, project_name, owner_id, owner_name,
                     view_count, size_bytes, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (user_id, workbook_id)
                    DO UPDATE SET
                        workbook_data = EXCLUDED.workbook_data,
                        workbook_name = EXCLUDED.workbook_name,
                        project_id = EXCLUDED.project_id,
                        project_name = EXCLUDED.project_name,
                        owner_id = EXCLUDED.owner_id,
                        owner_name = EXCLUDED.owner_name,
                        view_count = EXCLUDED.view_count,
                        size_bytes = EXCLUDED.size_bytes,
                        tags = EXCLUDED.tags,
                        updated_at = CURRENT_TIMESTAMP
                """, user_id, workbook["id"], json.dumps(workbook),
                     workbook.get("name"), workbook.get("projectId"),
                     workbook.get("project"), workbook.get("ownerId"),
                     workbook.get("owner"), workbook.get("viewCount", 0),
                     workbook.get("size", 0), workbook.get("tag", ""))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache workbook data: {e}")
            return False
    
    async def get_cached_workbooks(self, db_pool: Pool, user_id: str) -> list:
        """Get cached workbooks"""
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT workbook_data FROM tableau_workbooks_cache
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                """, user_id)
                
                workbooks = []
                for row in rows:
                    workbooks.append(json.loads(row["workbook_data"]))
                
                return workbooks
                
        except Exception as e:
            logger.error(f"Failed to get cached workbooks: {e}")
            return []
    
    async def log_tableau_activity(self, db_pool: Pool, user_id: str, 
                                 action: str, details: Dict[str, Any] = None,
                                 status: str = "success", error_message: str = None,
                                 workbook_id: str = None, view_id: str = None) -> bool:
        """Log Tableau activity"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO tableau_activity_logs 
                    (user_id, action, action_details, status, error_message,
                     workbook_id, view_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, user_id, action, json.dumps(details or {}), status,
                     error_message, workbook_id, view_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Tableau activity: {e}")
            return False
    
    async def get_tableau_stats(self, db_pool: Pool, user_id: str) -> Dict[str, Any]:
        """Get Tableau usage statistics"""
        try:
            async with db_pool.acquire() as conn:
                # Workbook counts
                workbook_row = await conn.fetchrow("""
                    SELECT COUNT(*) as total_workbooks,
                           SUM(view_count) as total_views
                    FROM tableau_workbooks_cache
                    WHERE user_id = $1
                """, user_id)
                
                # Project counts
                project_row = await conn.fetchrow("""
                    SELECT COUNT(*) as total_projects
                    FROM tableau_projects_cache
                    WHERE user_id = $1
                """, user_id)
                
                # Data source counts
                datasource_row = await conn.fetchrow("""
                    SELECT COUNT(*) as total_datasources,
                           COUNT(CASE WHEN is_extract = TRUE THEN 1 END) as extract_count
                    FROM tableau_datasources_cache
                    WHERE user_id = $1
                """, user_id)
                
                # Activity counts (last 30 days)
                activity_row = await conn.fetchrow("""
                    SELECT COUNT(*) as recent_activities
                    FROM tableau_activity_logs
                    WHERE user_id = $1
                    AND created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
                """, user_id)
                
                return {
                    "total_workbooks": workbook_row["total_workbooks"] or 0,
                    "total_views": workbook_row["total_views"] or 0,
                    "total_projects": project_row["total_projects"] or 0,
                    "total_datasources": datasource_row["total_datasources"] or 0,
                    "total_extracts": datasource_row["extract_count"] or 0,
                    "recent_activities": activity_row["recent_activities"] or 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau stats: {e}")
            return {}
    
    async def cleanup_tableau_cache(self, db_pool: Pool, user_id: str, 
                                  days_old: int = 30) -> int:
        """Clean up old Tableau cache data"""
        try:
            async with db_pool.acquire() as conn:
                # Clean up old activity logs
                result = await conn.execute("""
                    DELETE FROM tableau_activity_logs
                    WHERE user_id = $1
                    AND created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
                """, user_id)
                
                # Clean up old usage metrics
                await conn.execute("""
                    DELETE FROM tableau_usage_metrics
                    WHERE user_id = $1
                    AND metric_date < CURRENT_TIMESTAMP - INTERVAL '90 days'
                """, user_id)
                
                # Return deleted count
                if "DELETE" in result:
                    return int(result.split()[0])
                
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup Tableau cache: {e}")
            return 0

# Global token manager instance
tableau_token_manager = None

def get_tableau_token_manager() -> TableauTokenManager:
    """Get global Tableau token manager instance"""
    global tableau_token_manager
    if tableau_token_manager is None:
        tableau_token_manager = TableauTokenManager()
    return tableau_token_manager

# Convenience functions
async def init_tableau_oauth_table(db_pool: Pool) -> bool:
    """Initialize Tableau OAuth tables"""
    manager = get_tableau_token_manager()
    return await manager.init_tableau_oauth_table(db_pool)

async def get_user_tableau_tokens(db_pool: Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's Tableau tokens"""
    manager = get_tableau_token_manager()
    return await manager.get_user_tableau_tokens(db_pool, user_id)

async def store_tableau_tokens(db_pool: Pool, user_id: str, email: str,
                              tokens: Dict[str, Any], site_info: Dict[str, Any] = None) -> bool:
    """Store Tableau tokens"""
    manager = get_tableau_token_manager()
    return await manager.store_tableau_tokens(db_pool, user_id, email, tokens, site_info)

async def refresh_tableau_tokens(db_pool: Pool, user_id: str, new_tokens: Dict[str, Any]) -> bool:
    """Refresh Tableau tokens"""
    manager = get_tableau_token_manager()
    return await manager.refresh_tableau_tokens(db_pool, user_id, new_tokens)

async def delete_tableau_tokens(db_pool: Pool, user_id: str) -> bool:
    """Delete Tableau tokens"""
    manager = get_tableau_token_manager()
    return await manager.delete_tableau_tokens(db_pool, user_id)

async def is_tableau_token_expired(db_pool: Pool, user_id: str) -> bool:
    """Check if Tableau token is expired"""
    manager = get_tableau_token_manager()
    return await manager.is_token_expired(db_pool, user_id)