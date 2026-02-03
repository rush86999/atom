import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import Request
from sqlalchemy.orm import Session

from core.models import AuditEventType, AuditLog, SecurityLevel, ThreatLevel

logger = logging.getLogger(__name__)

class AuditService:
    """Service for logging security and audit events to the database"""

    def log_event(
        self,
        db: Session,
        event_type: str,
        action: str,
        description: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        workspace_id: Optional[str] = None,
        security_level: str = SecurityLevel.LOW.value,
        threat_level: str = ThreatLevel.NONE.value,
        resource: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        request: Optional[Request] = None
    ) -> str:
        """
        Log an audit event to the database
        """
        try:
            ip_address = None
            user_agent = None
            
            if request:
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

            metadata_json = None
            if metadata:
                try:
                    metadata_json = json.dumps(metadata)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Failed to serialize audit metadata: {e}")
                    metadata_json = str(metadata)

            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                event_type=event_type,
                security_level=security_level,
                threat_level=threat_level,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                user_email=user_email,
                workspace_id=workspace_id,
                ip_address=ip_address,
                user_agent=user_agent,
                resource=resource,
                action=action,
                description=description,
                metadata_json=metadata_json,
                success=success,
                error_message=error_message
            )

            db.add(audit_log)
            db.commit()
            return audit_log.id
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            # Don't raise - audit logging should not break the main flow
            return ""

# Global instance
audit_service = AuditService()
