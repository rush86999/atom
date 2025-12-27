
import logging
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.core.database import SessionLocal
from backend.core.models import UserConnection

logger = logging.getLogger(__name__)

class ConnectionService:
    """
    Manages user connections for both native and remote (ActivePieces) integrations.
    """
    
    def get_connections(self, user_id: str, integration_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List connections for a user, optionally filtered by integration.
        """
        db = SessionLocal()
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

    def save_connection(self, 
                        user_id: str, 
                        integration_id: str, 
                        name: str, 
                        credentials: Dict[str, Any],
                        workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Saves or updates a connection.
        """
        db = SessionLocal()
        try:
            # For simplicity, if a connection with same name and integration exists, update it.
            # Usually we'd want more granular control.
            existing = db.query(UserConnection).filter(
                UserConnection.user_id == user_id,
                UserConnection.integration_id == integration_id,
                UserConnection.connection_name == name
            ).first()

            if existing:
                existing.credentials = credentials
                existing.updated_at = datetime.now()
                conn = existing
            else:
                conn = UserConnection(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    workspace_id=workspace_id,
                    integration_id=integration_id,
                    connection_name=name,
                    credentials=credentials
                )
                db.add(conn)
            
            db.commit()
            db.refresh(conn)
            
            return {
                "id": conn.id,
                "name": conn.connection_name,
                "integration_id": conn.integration_id,
                "status": conn.status
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save connection: {e}")
            raise
        finally:
            db.close()

    def get_connection_credentials(self, connection_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the credentials for a connection.
        Ensures user owns the connection.
        """
        db = SessionLocal()
        try:
            conn = db.query(UserConnection).filter(
                UserConnection.id == connection_id,
                UserConnection.user_id == user_id
            ).first()
            
            if conn:
                # Update last used
                conn.last_used = datetime.now()
                db.commit()
                return conn.credentials
            return None
        finally:
            db.close()

    def delete_connection(self, connection_id: str, user_id: str) -> bool:
        db = SessionLocal()
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
