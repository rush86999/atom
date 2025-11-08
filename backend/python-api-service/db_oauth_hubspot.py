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

class HubSpotTokenManager:
    """HubSpot OAuth Token Management Database Functions"""
    
    def __init__(self):
        self.fernet = Fernet(os.getenv("ATOM_OAUTH_ENCRYPTION_KEY"))
    
    async def init_hubspot_oauth_table(self, db_pool: Pool) -> bool:
        """Initialize HubSpot OAuth table"""
        try:
            # Run the schema if it doesn't exist
            schema_file = "migrations/hubspot_schema.sql"
            if os.path.exists(schema_file):
                async with db_pool.acquire() as conn:
                    with open(schema_file, 'r') as f:
                        schema_sql = f.read()
                    await conn.execute(schema_sql)
                logger.info("HubSpot OAuth tables initialized")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize HubSpot OAuth tables: {e}")
            return False
    
    async def store_hubspot_tokens(self, db_pool: Pool, user_id: str, 
                                email: str, hub_id: str, tokens: Dict[str, Any]) -> bool:
        """Store HubSpot OAuth tokens in database"""
        try:
            # Encrypt tokens
            encrypted_tokens = self.fernet.encrypt(json.dumps(tokens).encode())
            
            # Calculate expiration
            expires_at = None
            if tokens.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timezone.timedelta(seconds=tokens["expires_in"])
            
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_oauth_tokens 
                    (user_id, email, hub_id, access_token, refresh_token, 
                     expires_at, scope, encrypted_tokens)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET
                        email = EXCLUDED.email,
                        hub_id = EXCLUDED.hub_id,
                        access_token = EXCLUDED.access_token,
                        refresh_token = EXCLUDED.refresh_token,
                        expires_at = EXCLUDED.expires_at,
                        scope = EXCLUDED.scope,
                        encrypted_tokens = EXCLUDED.encrypted_tokens,
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                """, user_id, email, hub_id, tokens.get("access_token"), 
                     tokens.get("refresh_token"), expires_at,
                     tokens.get("scope", ""),
                     encrypted_tokens.decode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store HubSpot tokens: {e}")
            return False
    
    async def get_user_hubspot_tokens(self, db_pool: Pool, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's HubSpot tokens from database"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT user_id, email, hub_id, access_token, refresh_token, 
                           expires_at, scope, encrypted_tokens, is_active, updated_at
                    FROM hubspot_oauth_tokens
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
                    "hub_id": row["hub_id"],
                    "access_token": row["access_token"],
                    "refresh_token": row["refresh_token"],
                    "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                    "scope": row["scope"],
                    "token_data": token_data,
                    "is_active": row["is_active"],
                    "updated_at": row["updated_at"].isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot tokens: {e}")
            return None
    
    async def refresh_hubspot_tokens(self, db_pool: Pool, user_id: str, 
                                  new_tokens: Dict[str, Any]) -> bool:
        """Update user's HubSpot tokens"""
        try:
            # Encrypt new tokens
            encrypted_tokens = self.fernet.encrypt(json.dumps(new_tokens).encode())
            
            # Calculate new expiration
            expires_at = None
            if new_tokens.get("expires_in"):
                expires_at = datetime.now(timezone.utc) + timezone.timedelta(seconds=new_tokens["expires_in"])
            
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE hubspot_oauth_tokens
                    SET access_token = $2,
                        refresh_token = COALESCE($3, refresh_token),
                        expires_at = $4,
                        scope = COALESCE($5, scope),
                        encrypted_tokens = $6,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, new_tokens.get("access_token"),
                     new_tokens.get("refresh_token"), expires_at,
                     new_tokens.get("scope"), encrypted_tokens.decode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh HubSpot tokens: {e}")
            return False
    
    async def delete_hubspot_tokens(self, db_pool: Pool, user_id: str) -> bool:
        """Delete user's HubSpot tokens (logout)"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE hubspot_oauth_tokens
                    SET is_active = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete HubSpot tokens: {e}")
            return False
    
    async def is_token_expired(self, db_pool: Pool, user_id: str) -> bool:
        """Check if user's HubSpot token is expired"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT expires_at FROM hubspot_oauth_tokens
                    WHERE user_id = $1 AND is_active = TRUE
                """, user_id)
                
                if not row or not row["expires_at"]:
                    return True
                
                # Add 5-minute buffer
                return row["expires_at"] < datetime.now(timezone.utc) - timezone.timedelta(minutes=5)
                
        except Exception as e:
            logger.error(f"Failed to check token expiration: {e}")
            return True
    
    async def cache_contact_data(self, db_pool: Pool, user_id: str, 
                              contact: Dict[str, Any]) -> bool:
        """Cache contact data"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_contacts_cache 
                    (user_id, contact_id, contact_data, first_name, last_name,
                     email, phone, company, job_title, lifecycle_stage,
                     created_at, updated_at, is_customer, has_email, has_phone)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15)
                    ON CONFLICT (user_id, contact_id)
                    DO UPDATE SET
                        contact_data = EXCLUDED.contact_data,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        company = EXCLUDED.company,
                        job_title = EXCLUDED.job_title,
                        lifecycle_stage = EXCLUDED.lifecycle_stage,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        is_customer = EXCLUDED.is_customer,
                        has_email = EXCLUDED.has_email,
                        has_phone = EXCLUDED.has_phone
                """, user_id, contact["id"], json.dumps(contact),
                     contact.get("firstName", ""), contact.get("lastName", ""),
                     contact.get("email", ""), contact.get("phone", ""),
                     contact.get("company", ""), contact.get("jobTitle", ""),
                     contact.get("lifecycleStage", ""),
                     contact.get("createdAt"), contact.get("updatedAt"),
                     contact.get("isCustomer", False), contact.get("hasEmail", False),
                     contact.get("hasPhone", False))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache contact data: {e}")
            return False
    
    async def cache_company_data(self, db_pool: Pool, user_id: str, 
                               company: Dict[str, Any]) -> bool:
        """Cache company data"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_companies_cache 
                    (user_id, company_id, company_data, name, domain, industry,
                     description, size, revenue, phone, website, city, state, country,
                     created_at, updated_at, has_website, has_phone, employee_count)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                            $15, $16, $17, $18, $19, $20, $21)
                    ON CONFLICT (user_id, company_id)
                    DO UPDATE SET
                        company_data = EXCLUDED.company_data,
                        name = EXCLUDED.name,
                        domain = EXCLUDED.domain,
                        industry = EXCLUDED.industry,
                        description = EXCLUDED.description,
                        size = EXCLUDED.size,
                        revenue = EXCLUDED.revenue,
                        phone = EXCLUDED.phone,
                        website = EXCLUDED.website,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        country = EXCLUDED.country,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        has_website = EXCLUDED.has_website,
                        has_phone = EXCLUDED.has_phone,
                        employee_count = EXCLUDED.employee_count
                """, user_id, company["id"], json.dumps(company),
                     company.get("name", ""), company.get("domain", ""),
                     company.get("industry", ""), company.get("description", ""),
                     company.get("size", ""), company.get("revenue", ""),
                     company.get("phone", ""), company.get("website", ""),
                     company.get("city", ""), company.get("state", ""),
                     company.get("country", ""),
                     company.get("createdAt"), company.get("updatedAt"),
                     company.get("hasWebsite", False), company.get("hasPhone", False),
                     company.get("employeeCount", 0))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache company data: {e}")
            return False
    
    async def cache_deal_data(self, db_pool: Pool, user_id: str, 
                            deal: Dict[str, Any]) -> bool:
        """Cache deal data"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_deals_cache 
                    (user_id, deal_id, deal_data, deal_name, pipeline, deal_stage,
                     amount, forecast_amount, probability, deal_type, close_date,
                     created_at, updated_at, is_closed, is_won, has_amount)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                            $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (user_id, deal_id)
                    DO UPDATE SET
                        deal_data = EXCLUDED.deal_data,
                        deal_name = EXCLUDED.deal_name,
                        pipeline = EXCLUDED.pipeline,
                        deal_stage = EXCLUDED.deal_stage,
                        amount = EXCLUDED.amount,
                        forecast_amount = EXCLUDED.forecast_amount,
                        probability = EXCLUDED.probability,
                        deal_type = EXCLUDED.deal_type,
                        close_date = EXCLUDED.close_date,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        is_closed = EXCLUDED.is_closed,
                        is_won = EXCLUDED.is_won,
                        has_amount = EXCLUDED.has_amount
                """, user_id, deal["id"], json.dumps(deal),
                     deal.get("dealName", ""), deal.get("pipeline", ""),
                     deal.get("dealStage", ""), deal.get("amount", 0),
                     deal.get("forecastAmount", 0), deal.get("probability", 0),
                     deal.get("dealType", ""), deal.get("closeDate", ""),
                     deal.get("createdAt"), deal.get("updatedAt"),
                     deal.get("isClosed", False), deal.get("isWon", False),
                     deal.get("hasAmount", False))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache deal data: {e}")
            return False
    
    async def log_hubspot_activity(self, db_pool: Pool, user_id: str, 
                                 action: str, details: Dict[str, Any] = None,
                                 status: str = "success", error_message: str = None,
                                 contact_id: str = None, company_id: str = None,
                                 deal_id: str = None, ticket_id: str = None) -> bool:
        """Log HubSpot activity"""
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_activity_logs 
                    (user_id, action, action_details, status, error_message,
                     contact_id, company_id, deal_id, ticket_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, user_id, action, json.dumps(details or {}), status,
                     error_message, contact_id, company_id, deal_id, ticket_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log HubSpot activity: {e}")
            return False
    
    async def get_hubspot_stats(self, db_pool: Pool, user_id: str) -> Dict[str, Any]:
        """Get HubSpot usage statistics"""
        try:
            async with db_pool.acquire() as conn:
                # Execute the stats function
                row = await conn.fetchrow("""
                    SELECT get_hubspot_stats($1) as stats
                """, user_id)
                
                return row["stats"] if row else {}
                
        except Exception as e:
            logger.error(f"Failed to get HubSpot stats: {e}")
            return {}
    
    async def cleanup_hubspot_cache(self, db_pool: Pool, user_id: str, 
                                 days_old: int = 30) -> int:
        """Clean up old HubSpot cache data"""
        try:
            async with db_pool.acquire() as conn:
                # Use the cleanup function
                result = await conn.execute("""
                    SELECT cleanup_hubspot_cache($1, $2)
                """, user_id, days_old)
                
                # Return deleted count
                if "CLEANUP" in result:
                    return int(result.split()[0])
                
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup HubSpot cache: {e}")
            return 0

# Global token manager instance
hubspot_token_manager = None

def get_hubspot_token_manager() -> HubSpotTokenManager:
    """Get global HubSpot token manager instance"""
    global hubspot_token_manager
    if hubspot_token_manager is None:
        hubspot_token_manager = HubSpotTokenManager()
    return hubspot_token_manager

# Convenience functions
async def init_hubspot_oauth_table(db_pool: Pool) -> bool:
    """Initialize HubSpot OAuth tables"""
    manager = get_hubspot_token_manager()
    return await manager.init_hubspot_oauth_table(db_pool)

async def get_user_hubspot_tokens(db_pool: Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's HubSpot tokens"""
    manager = get_hubspot_token_manager()
    return await manager.get_user_hubspot_tokens(db_pool, user_id)

async def store_hubspot_tokens(db_pool: Pool, user_id: str, email: str,
                             hub_id: str, tokens: Dict[str, Any]) -> bool:
    """Store HubSpot tokens"""
    manager = get_hubspot_token_manager()
    return await manager.store_hubspot_tokens(db_pool, user_id, email, hub_id, tokens)

async def refresh_hubspot_tokens(db_pool: Pool, user_id: str, new_tokens: Dict[str, Any]) -> bool:
    """Refresh HubSpot tokens"""
    manager = get_hubspot_token_manager()
    return await manager.refresh_hubspot_tokens(db_pool, user_id, new_tokens)

async def delete_hubspot_tokens(db_pool: Pool, user_id: str) -> bool:
    """Delete HubSpot tokens"""
    manager = get_hubspot_token_manager()
    return await manager.delete_hubspot_tokens(db_pool, user_id)

async def is_hubspot_token_expired(db_pool: Pool, user_id: str) -> bool:
    """Check if HubSpot token is expired"""
    manager = get_hubspot_token_manager()
    return await manager.is_token_expired(db_pool, user_id)