
import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from core.config import get_config
from core.database import get_db_session
from core.models import UserConnection

logger = logging.getLogger(__name__)

class ConnectionService:
    """
    Manages user connections for both native and remote (ActivePieces) integrations.
    """
    def __init__(self):
        self.security_config = get_config().security
        self._fernet = None
        
    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            key = self.security_config.encryption_key or self.security_config.secret_key
            # Fernet key must be 32 url-safe base64-encoded bytes
            key_bytes = key.encode()
            key_hash = hashlib.sha256(key_bytes).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            self._fernet = Fernet(fernet_key)
        return self._fernet

    def _encrypt(self, data: Dict[str, Any]) -> str:
        f = self._get_fernet()
        return f.encrypt(json.dumps(data).encode()).decode()

    def _decrypt(self, encrypted_data: Any) -> Dict[str, Any]:
        if not encrypted_data:
            return {}
        
        # If it's already a dict (SQLAlchemy JSON column might return it as dict if it was stored as JSON)
        # However, we intend to store it as an encrypted string.
        if isinstance(encrypted_data, dict):
            return encrypted_data
            
        # Support for transitional plain-text (if it starts with { look like JSON)
        if isinstance(encrypted_data, str) and encrypted_data.startswith('{'):
            try:
                return json.loads(encrypted_data)
            except Exception as e:
                logger.warning(f"Failed to parse plain-text credentials: {e}")
        
        try:
            f = self._get_fernet()
            decrypted = f.decrypt(encrypted_data.encode()).decode()
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            return {}
    
    def get_connections(self, user_id: str, integration_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List connections for a user, optionally filtered by integration.
        """
        with get_db_session() as db:
        try:
            query = db.query(UserConnection).filter(UserConnection.user_id == user_id)
            if integration_id:
                query = query.filter(UserConnection.integration_id == integration_id)
            
            connections = query.all()
            return [
                {
                    "id": c.id,
                    "name": c.connection_name,
                    "integration_id": c.integration_id,
                    "status": c.status,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "last_used": c.last_used.isoformat() if c.last_used else None
                }
                for c in connections
            ]
        finally:
            db.close()

    def save_connection(self, user_id: str, integration_id: str, name: str, credentials: Dict[str, Any], workspace_id: Optional[str] = None) -> UserConnection:
        """
        Saves or updates a user connection.
        Calculates expires_at if possible and encrypts credentials.
        """
        with get_db_session() as db:
        try:
            # Check for existing connection for this user and integration
            conn = db.query(UserConnection).filter(
                UserConnection.user_id == user_id,
                UserConnection.integration_id == integration_id
            ).first()
            
            # Calculate expires_at
            expires_at = None
            expires_in = credentials.get("expires_in")
            if expires_in:
                try:
                    expires_at = datetime.now() + timedelta(seconds=int(expires_in))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse expires_in: {e}")

            encrypted_creds = self._encrypt(credentials)

            if conn:
                conn.connection_name = name
                conn.credentials = encrypted_creds
                conn.updated_at = datetime.now()
                if expires_at:
                    conn.expires_at = expires_at
                db.commit()
                db.refresh(conn)
                return conn
            else:
                new_conn = UserConnection(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    workspace_id=workspace_id,
                    integration_id=integration_id,
                    connection_name=name,
                    credentials=encrypted_creds,
                    expires_at=expires_at,
                    status="active"
                )
                db.add(new_conn)
                db.commit()
                db.refresh(new_conn)
                return new_conn
        finally:
            db.close()

    async def get_connection_credentials(self, connection_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the credentials for a connection.
        Ensures user owns the connection and refreshes token if needed.
        """
        with get_db_session() as db:
        try:
            conn = db.query(UserConnection).filter(
                UserConnection.id == connection_id,
                UserConnection.user_id == user_id
            ).first()
            
            if conn:
                # Decrypt credentials for use
                creds = self._decrypt(conn.credentials)
                
                # Automatic refresh logic
                updated_creds = await self._refresh_token_if_needed(conn, creds)
                if updated_creds:
                    conn.credentials = self._encrypt(updated_creds)
                    # Recalculate expires_at from new data
                    expires_in = updated_creds.get("expires_in")
                    if expires_in:
                        conn.expires_at = datetime.now() + timedelta(seconds=int(expires_in))
                    conn.updated_at = datetime.now()
                    conn.status = "active" # Mark as active if refresh succeeds
                    db.commit()
                    creds = updated_creds
                
                # Update last used
                conn.last_used = datetime.now()
                db.commit()
                return creds
            return None
        finally:
            db.close()

    async def _refresh_token_if_needed(self, conn: UserConnection, creds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Checks if the token is expired and refreshes it using refresh_token if available.
        """
        if not creds:
            return None

        # Check if we have a refresh token
        refresh_token = creds.get("refresh_token")
        if not refresh_token:
            return None

        # Check if token is expired or near expiry (within 5 minutes)
        should_refresh = False
        if conn.expires_at:
            if datetime.now() + timedelta(minutes=5) >= conn.expires_at:
                should_refresh = True
        else:
            # Heuristic: if last updated > 55 mins ago and we have a refresh token, maybe just refresh?
            # For now, stay with explicit expiry or manually triggered.
            pass
            
        if not should_refresh:
            return None

        from integrations.universal.config import get_oauth_config
        config = get_oauth_config(conn.integration_id)
        if not config:
            return None

        import httpx
        try:
            logger.info(f"Attempting to refresh token for {conn.integration_id} (Connection: {conn.id})")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    config["token_url"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"]
                    }
                )
                if resp.status_code == 200:
                    new_token_data = resp.json()
                    # Merge new data into old
                    updated_creds = {**creds, **new_token_data}
                    return updated_creds
                else:
                    logger.error(f"Refresh failed for {conn.integration_id}: {resp.text}")
                    # Update status to error/expired
                    with get_db_session() as db:
                    conn_to_update = db.query(UserConnection).get(conn.id)
                    if conn_to_update:
                        conn_to_update.status = "error"
                        db.commit()
                    db.close()
        except Exception as e:
            logger.error(f"Error during token refresh: {e}")
            
        return None

    def update_connection_name(self, connection_id: str, user_id: str, new_name: str) -> bool:
        with get_db_session() as db:
        try:
            conn = db.query(UserConnection).filter(
                UserConnection.id == connection_id,
                UserConnection.user_id == user_id
            ).first()
            if conn:
                conn.connection_name = new_name
                conn.updated_at = datetime.now()
                db.commit()
                return True
            return False
        finally:
            db.close()

    def delete_connection(self, connection_id: str, user_id: str) -> bool:
        with get_db_session() as db:
        try:
            conn = db.query(UserConnection).filter(
                UserConnection.id == connection_id,
                UserConnection.user_id == user_id
            ).first()
            if conn:
                db.delete(conn)
                db.commit()
                return True
            return False
        finally:
            db.close()

# Singleton
connection_service = ConnectionService()
