"""
👥 Zoom Multi-Account Manager
Enterprise-grade multi-account management for Zoom integration
"""

import os
import json
import logging
import asyncio
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import asyncpg
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class AccountStatus(Enum):
    """Account status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    ERROR = "error"

class AccountType(Enum):
    """Account type enumeration"""
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    EDUCATION = "education"

@dataclass
class ZoomAccount:
    """Zoom account information"""
    account_id: str
    user_id: str
    account_name: str
    account_email: str
    account_type: AccountType
    account_status: AccountStatus
    zoom_account_id: str
    zoom_user_id: str
    zoom_user_type: int
    zoom_role_name: str
    is_primary: bool
    is_default: bool
    oauth_token_id: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]
    access_count: int
    permissions: List[str]
    metadata: Dict[str, Any]

@dataclass
class AccountSwitchRequest:
    """Account switch request"""
    user_id: str
    target_account_id: str
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class AccountSwitchResult:
    """Account switch result"""
    success: bool
    user_id: str
    previous_account_id: Optional[str]
    current_account_id: str
    switch_time: datetime
    reason: Optional[str]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ZoomMultiAccountManager:
    """Enterprise-grade Zoom multi-account manager"""
    
    def __init__(self, db_pool: asyncpg.Pool, encryption_key: Optional[str] = None):
        self.db_pool = db_pool
        
        # Initialize encryption for sensitive data
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            self.fernet = Fernet(os.getenv('ENCRYPTION_KEY', Fernet.generate_key()).encode())
        
        self.encryption_enabled = True
        
        # Initialize database
        asyncio.create_task(self._init_database())
    
    def _encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive account data"""
        if not self.encryption_enabled:
            return data
        return self.fernet.encrypt(data.encode()).decode()
    
    def _decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive account data"""
        if not self.encryption_enabled:
            return encrypted_data
        return self.fernet.decrypt(encrypted_data.encode()).decode()
    
    async def _init_database(self) -> None:
        """Initialize multi-account database tables"""
        if not self.db_pool:
            logger.warning("Database pool not available for multi-account management")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create accounts table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_accounts (
                        id SERIAL PRIMARY KEY,
                        account_id VARCHAR(255) UNIQUE NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        account_name VARCHAR(255) NOT NULL,
                        account_email VARCHAR(255) NOT NULL,
                        account_type VARCHAR(50) NOT NULL,
                        account_status VARCHAR(50) NOT NULL,
                        zoom_account_id VARCHAR(255) NOT NULL,
                        zoom_user_id VARCHAR(255) NOT NULL,
                        zoom_user_type INTEGER NOT NULL,
                        zoom_role_name VARCHAR(255) NOT NULL,
                        is_primary BOOLEAN DEFAULT false,
                        is_default BOOLEAN DEFAULT false,
                        oauth_token_id VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_used_at TIMESTAMP WITH TIME ZONE,
                        access_count INTEGER DEFAULT 0,
                        permissions TEXT[] DEFAULT ARRAY[]::TEXT[],
                        metadata JSONB DEFAULT '{}'::jsonb,
                        UNIQUE(user_id, zoom_user_id)
                    );
                """)
                
                # Create account switch history table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_account_switches (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        previous_account_id VARCHAR(255),
                        current_account_id VARCHAR(255) NOT NULL,
                        switch_reason TEXT,
                        switch_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        client_info JSONB DEFAULT '{}'::jsonb,
                        ip_address INET,
                        user_agent TEXT,
                        metadata JSONB DEFAULT '{}'::jsonb
                    );
                """)
                
                # Create account permissions table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_account_permissions (
                        id SERIAL PRIMARY KEY,
                        account_id VARCHAR(255) NOT NULL,
                        permission_name VARCHAR(255) NOT NULL,
                        permission_scope JSONB DEFAULT '{}'::jsonb,
                        granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        granted_by VARCHAR(255),
                        expires_at TIMESTAMP WITH TIME ZONE,
                        is_active BOOLEAN DEFAULT true,
                        UNIQUE(account_id, permission_name)
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_user_id ON zoom_accounts(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_zoom_account_id ON zoom_accounts(zoom_account_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_status ON zoom_accounts(account_status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_type ON zoom_accounts(account_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_primary ON zoom_accounts(is_primary);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_default ON zoom_accounts(is_default);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_accounts_last_used ON zoom_accounts(last_used_at);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_account_switches_user_id ON zoom_account_switches(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_account_switches_time ON zoom_account_switches(switch_time);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_account_permissions_account_id ON zoom_account_permissions(account_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_account_permissions_active ON zoom_account_permissions(is_active);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("Zoom multi-account database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize Zoom multi-account database: {e}")
    
    async def add_account(
        self, 
        user_id: str, 
        account_name: str,
        account_email: str,
        account_type: AccountType,
        zoom_account_id: str,
        zoom_user_id: str,
        zoom_user_type: int,
        zoom_role_name: str,
        oauth_token_id: str,
        is_primary: bool = False,
        permissions: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """Add a new Zoom account"""
        try:
            account_id = f"{user_id}_{zoom_user_id}_{datetime.now(timezone.utc).timestamp()}"
            
            # Check if this is the first account for user (make it primary)
            if not is_primary:
                async with self.db_pool.acquire() as conn:
                    existing_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM zoom_accounts WHERE user_id = $1",
                        user_id
                    )
                    is_primary = existing_count == 0
            
            # Set as default account if it's primary
            is_default = is_primary
            
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_accounts (
                        account_id, user_id, account_name, account_email, account_type,
                        account_status, zoom_account_id, zoom_user_id, zoom_user_type,
                        zoom_role_name, is_primary, is_default, oauth_token_id,
                        permissions, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """,
                account_id, user_id, account_name, account_email, account_type.value,
                AccountStatus.ACTIVE.value, zoom_account_id, zoom_user_id,
                zoom_user_type, zoom_role_name, is_primary, is_default, oauth_token_id,
                permissions or [], json.dumps(metadata or {})
                )
                
                # If this is the primary account, update other accounts
                if is_primary:
                    await conn.execute("""
                        UPDATE zoom_accounts 
                        SET is_primary = false, is_default = false 
                        WHERE user_id = $1 AND account_id != $2
                    """, user_id, account_id)
            
            logger.info(f"Added Zoom account {account_id} for user {user_id}")
            return account_id
            
        except Exception as e:
            logger.error(f"Failed to add Zoom account: {e}")
            return None
    
    async def get_accounts(
        self, 
        user_id: str,
        include_inactive: bool = False
    ) -> List[ZoomAccount]:
        """Get all accounts for a user"""
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT account_id, user_id, account_name, account_email, account_type,
                           account_status, zoom_account_id, zoom_user_id, zoom_user_type,
                           zoom_role_name, is_primary, is_default, oauth_token_id,
                           created_at, last_used_at, access_count, permissions, metadata
                    FROM zoom_accounts 
                    WHERE user_id = $1
                """
                
                params = [user_id]
                
                if not include_inactive:
                    query += " AND account_status = $2"
                    params.append(AccountStatus.ACTIVE.value)
                
                query += " ORDER BY is_primary DESC, is_default DESC, created_at DESC"
                
                rows = await conn.fetch(query, *params)
                
                accounts = []
                for row in rows:
                    account = ZoomAccount(
                        account_id=row['account_id'],
                        user_id=row['user_id'],
                        account_name=row['account_name'],
                        account_email=row['account_email'],
                        account_type=AccountType(row['account_type']),
                        account_status=AccountStatus(row['account_status']),
                        zoom_account_id=row['zoom_account_id'],
                        zoom_user_id=row['zoom_user_id'],
                        zoom_user_type=row['zoom_user_type'],
                        zoom_role_name=row['zoom_role_name'],
                        is_primary=row['is_primary'],
                        is_default=row['is_default'],
                        oauth_token_id=row['oauth_token_id'],
                        created_at=row['created_at'],
                        last_used_at=row['last_used_at'],
                        access_count=row['access_count'],
                        permissions=row['permissions'] or [],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    accounts.append(account)
                
                return accounts
                
        except Exception as e:
            logger.error(f"Failed to get accounts for user {user_id}: {e}")
            return []
    
    async def get_default_account(self, user_id: str) -> Optional[ZoomAccount]:
        """Get default account for user"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT account_id, user_id, account_name, account_email, account_type,
                           account_status, zoom_account_id, zoom_user_id, zoom_user_type,
                           zoom_role_name, is_primary, is_default, oauth_token_id,
                           created_at, last_used_at, access_count, permissions, metadata
                    FROM zoom_accounts 
                    WHERE user_id = $1 AND is_default = true AND account_status = $2
                    ORDER BY is_primary DESC, created_at DESC
                    LIMIT 1
                """, user_id, AccountStatus.ACTIVE.value)
                
                if row:
                    return ZoomAccount(
                        account_id=row['account_id'],
                        user_id=row['user_id'],
                        account_name=row['account_name'],
                        account_email=row['account_email'],
                        account_type=AccountType(row['account_type']),
                        account_status=AccountStatus(row['account_status']),
                        zoom_account_id=row['zoom_account_id'],
                        zoom_user_id=row['zoom_user_id'],
                        zoom_user_type=row['zoom_user_type'],
                        zoom_role_name=row['zoom_role_name'],
                        is_primary=row['is_primary'],
                        is_default=row['is_default'],
                        oauth_token_id=row['oauth_token_id'],
                        created_at=row['created_at'],
                        last_used_at=row['last_used_at'],
                        access_count=row['access_count'],
                        permissions=row['permissions'] or [],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get default account for user {user_id}: {e}")
            return None
    
    async def get_account(self, account_id: str) -> Optional[ZoomAccount]:
        """Get specific account by ID"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT account_id, user_id, account_name, account_email, account_type,
                           account_status, zoom_account_id, zoom_user_id, zoom_user_type,
                           zoom_role_name, is_primary, is_default, oauth_token_id,
                           created_at, last_used_at, access_count, permissions, metadata
                    FROM zoom_accounts 
                    WHERE account_id = $1
                """, account_id)
                
                if row:
                    return ZoomAccount(
                        account_id=row['account_id'],
                        user_id=row['user_id'],
                        account_name=row['account_name'],
                        account_email=row['account_email'],
                        account_type=AccountType(row['account_type']),
                        account_status=AccountStatus(row['account_status']),
                        zoom_account_id=row['zoom_account_id'],
                        zoom_user_id=row['zoom_user_id'],
                        zoom_user_type=row['zoom_user_type'],
                        zoom_role_name=row['zoom_role_name'],
                        is_primary=row['is_primary'],
                        is_default=row['is_default'],
                        oauth_token_id=row['oauth_token_id'],
                        created_at=row['created_at'],
                        last_used_at=row['last_used_at'],
                        access_count=row['access_count'],
                        permissions=row['permissions'] or [],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get account {account_id}: {e}")
            return None
    
    async def switch_account(
        self, 
        switch_request: AccountSwitchRequest,
        client_info: Dict[str, str] = None
    ) -> AccountSwitchResult:
        """Switch to a different account"""
        try:
            user_id = switch_request.user_id
            target_account_id = switch_request.target_account_id
            
            # Get current default account
            current_default = await self.get_default_account(user_id)
            previous_account_id = current_default.account_id if current_default else None
            
            # Get target account
            target_account = await self.get_account(target_account_id)
            if not target_account:
                return AccountSwitchResult(
                    success=False,
                    user_id=user_id,
                    previous_account_id=previous_account_id,
                    current_account_id=target_account_id,
                    switch_time=datetime.now(timezone.utc),
                    reason=switch_request.reason,
                    error="Target account not found"
                )
            
            if target_account.account_status != AccountStatus.ACTIVE:
                return AccountSwitchResult(
                    success=False,
                    user_id=user_id,
                    previous_account_id=previous_account_id,
                    current_account_id=target_account_id,
                    switch_time=datetime.now(timezone.utc),
                    reason=switch_request.reason,
                    error=f"Account status is {target_account.account_status.value}"
                )
            
            # Update default account
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_accounts 
                    SET is_default = false 
                    WHERE user_id = $1
                """, user_id)
                
                await conn.execute("""
                    UPDATE zoom_accounts 
                    SET is_default = true, last_used_at = NOW(), access_count = access_count + 1
                    WHERE account_id = $1 AND user_id = $2
                """, target_account_id, user_id)
                
                # Record account switch
                await conn.execute("""
                    INSERT INTO zoom_account_switches (
                        user_id, previous_account_id, current_account_id, switch_reason,
                        client_info, ip_address, user_agent, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id, previous_account_id, target_account_id, switch_request.reason,
                json.dumps(client_info or {}), client_info.get('ip_address') if client_info else None,
                client_info.get('user_agent') if client_info else None,
                json.dumps(switch_request.metadata or {})
                )
            
            logger.info(f"User {user_id} switched from account {previous_account_id} to {target_account_id}")
            
            return AccountSwitchResult(
                success=True,
                user_id=user_id,
                previous_account_id=previous_account_id,
                current_account_id=target_account_id,
                switch_time=datetime.now(timezone.utc),
                reason=switch_request.reason,
                metadata=switch_request.metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to switch account for user {switch_request.user_id}: {e}")
            return AccountSwitchResult(
                success=False,
                user_id=switch_request.user_id,
                previous_account_id=None,
                current_account_id=switch_request.target_account_id,
                switch_time=datetime.now(timezone.utc),
                reason=switch_request.reason,
                error=f"Account switch failed: {e}"
            )
    
    async def update_account(
        self, 
        account_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update account information"""
        try:
            # Prepare update data
            update_fields = []
            update_values = []
            param_index = 1
            
            for field, value in updates.items():
                if field in ['account_name', 'account_email', 'account_type', 'account_status', 'permissions', 'metadata']:
                    update_fields.append(f"{field} = ${param_index}")
                    update_values.append(value)
                    param_index += 1
            
            if not update_fields:
                return False
            
            # Add updated_at timestamp
            update_fields.append(f"updated_at = ${param_index}")
            update_values.append(datetime.now(timezone.utc))
            update_values.append(account_id)
            
            async with self.db_pool.acquire() as conn:
                await conn.execute(f"""
                    UPDATE zoom_accounts 
                    SET {', '.join(update_fields)}
                    WHERE account_id = ${param_index + 1}
                """, *update_values)
            
            logger.info(f"Updated Zoom account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update account {account_id}: {e}")
            return False
    
    async def remove_account(
        self, 
        account_id: str,
        user_id: str
    ) -> bool:
        """Remove an account"""
        try:
            async with self.db_pool.acquire() as conn:
                # Check if account is primary
                is_primary = await conn.fetchval(
                    "SELECT is_primary FROM zoom_accounts WHERE account_id = $1 AND user_id = $2",
                    account_id, user_id
                )
                
                if is_primary:
                    return False  # Cannot remove primary account
                
                # Remove account
                result = await conn.execute("""
                    DELETE FROM zoom_accounts 
                    WHERE account_id = $1 AND user_id = $2
                """, account_id, user_id)
                
                deleted = int(result.split(' ')[-1]) > 0
                
                if deleted:
                    # Update default account if needed
                    remaining_accounts = await conn.fetchval(
                        "SELECT COUNT(*) FROM zoom_accounts WHERE user_id = $1 AND is_default = true",
                        user_id
                    )
                    
                    if remaining_accounts == 0:
                        # Set first remaining account as default
                        await conn.execute("""
                            UPDATE zoom_accounts 
                            SET is_default = true 
                            WHERE user_id = $1 AND is_primary = true
                        """, user_id)
                
                logger.info(f"Removed Zoom account {account_id} for user {user_id}")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to remove account {account_id}: {e}")
            return False
    
    async def get_account_switch_history(
        self, 
        user_id: str,
        limit: int = 50,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get account switch history"""
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT user_id, previous_account_id, current_account_id, switch_reason,
                           switch_time, client_info, ip_address, user_agent, metadata
                    FROM zoom_account_switches 
                    WHERE user_id = $1
                """
                params = [user_id]
                
                if from_date:
                    query += " AND switch_time >= $2"
                    params.append(from_date)
                
                if to_date:
                    query += f" AND switch_time <= ${len(params) + 1}"
                    params.append(to_date)
                
                query += " ORDER BY switch_time DESC LIMIT $" + str(len(params) + 1)
                params.append(limit)
                
                rows = await conn.fetch(query, *params)
                
                history = []
                for row in rows:
                    history.append({
                        'user_id': row['user_id'],
                        'previous_account_id': row['previous_account_id'],
                        'current_account_id': row['current_account_id'],
                        'switch_reason': row['switch_reason'],
                        'switch_time': row['switch_time'].isoformat(),
                        'client_info': json.loads(row['client_info']) if row['client_info'] else {},
                        'ip_address': str(row['ip_address']) if row['ip_address'] else None,
                        'user_agent': row['user_agent'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"Failed to get account switch history for user {user_id}: {e}")
            return []
    
    async def set_account_permissions(
        self, 
        account_id: str,
        permissions: List[str]
    ) -> bool:
        """Set account permissions"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_accounts 
                    SET permissions = $1
                    WHERE account_id = $2
                """, permissions, account_id)
            
            logger.info(f"Updated permissions for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set permissions for account {account_id}: {e}")
            return False
    
    async def check_account_permission(
        self, 
        account_id: str,
        permission: str
    ) -> bool:
        """Check if account has specific permission"""
        try:
            async with self.db_pool.acquire() as conn:
                user_permission = await conn.fetchval("""
                    SELECT 1 FROM zoom_accounts 
                    WHERE account_id = $1 AND $2 = ANY(permissions) AND account_status = $3
                    LIMIT 1
                """, account_id, permission, AccountStatus.ACTIVE.value)
                
                return user_permission == 1
                
        except Exception as e:
            logger.error(f"Failed to check permission for account {account_id}: {e}")
            return False
    
    async def get_account_statistics(
        self, 
        user_id: str
    ) -> Dict[str, Any]:
        """Get account statistics for user"""
        try:
            async with self.db_pool.acquire() as conn:
                # Basic counts
                total_accounts = await conn.fetchval(
                    "SELECT COUNT(*) FROM zoom_accounts WHERE user_id = $1",
                    user_id
                )
                
                active_accounts = await conn.fetchval(
                    "SELECT COUNT(*) FROM zoom_accounts WHERE user_id = $1 AND account_status = $2",
                    user_id, AccountStatus.ACTIVE.value
                )
                
                # Switch history count
                total_switches = await conn.fetchval(
                    "SELECT COUNT(*) FROM zoom_account_switches WHERE user_id = $1",
                    user_id
                )
                
                # Last switch time
                last_switch = await conn.fetchval("""
                    SELECT switch_time FROM zoom_account_switches 
                    WHERE user_id = $1 
                    ORDER BY switch_time DESC 
                    LIMIT 1
                """, user_id)
                
                # Most used account
                most_used = await conn.fetchrow("""
                    SELECT current_account_id, COUNT(*) as switch_count
                    FROM zoom_account_switches 
                    WHERE user_id = $1 
                    GROUP BY current_account_id 
                    ORDER BY switch_count DESC 
                    LIMIT 1
                """, user_id)
                
                # Account types distribution
                type_distribution = await conn.fetch("""
                    SELECT account_type, COUNT(*) as count
                    FROM zoom_accounts 
                    WHERE user_id = $1 
                    GROUP BY account_type
                """, user_id)
                
                return {
                    'user_id': user_id,
                    'total_accounts': total_accounts,
                    'active_accounts': active_accounts,
                    'inactive_accounts': total_accounts - active_accounts,
                    'total_switches': total_switches,
                    'last_switch_time': last_switch.isoformat() if last_switch else None,
                    'most_used_account': most_used['current_account_id'] if most_used else None,
                    'most_used_switch_count': most_used['switch_count'] if most_used else 0,
                    'account_type_distribution': {
                        row['account_type']: row['count'] for row in type_distribution
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get account statistics for user {user_id}: {e}")
            return {}
    
    async def cleanup_inactive_accounts(self, days: int = 90) -> int:
        """Clean up inactive accounts"""
        try:
            async with self.db_pool.acquire() as conn:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                
                result = await conn.execute("""
                    DELETE FROM zoom_accounts 
                    WHERE account_status = $1 
                    AND last_used_at < $2 
                    AND is_primary = false
                """, AccountStatus.INACTIVE.value, cutoff_date)
                
                # Extract count from result
                count = 0
                if result:
                    count_str = result.split(' ')[-1]
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 0
                
                logger.info(f"Cleaned up {count} inactive Zoom accounts")
                return count
                
        except Exception as e:
            logger.error(f"Failed to cleanup inactive Zoom accounts: {e}")
            return 0