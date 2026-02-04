import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from fastapi import Request
from sqlalchemy.orm import Session

from core.models import AuditEventType, AuditLog, CanvasAudit, BrowserAudit, DeviceAudit, SecurityLevel, ThreatLevel

logger = logging.getLogger(__name__)


class AuditType(str, Enum):
    """Audit types for different system components"""
    CANVAS = "canvas"
    BROWSER = "browser"
    DEVICE = "device"
    AGENT = "agent"
    GENERIC = "generic"


class AuditService:
    """
    Unified audit service for all system components.

    Provides centralized audit logging with:
    - Automatic retry on failure
    - Type-specific audit records (Canvas, Browser, Device, Agent)
    - Enriched metadata with request context
    - Graceful degradation (never breaks main flow)

    Feature Flags:
        None - core service, always enabled
    """

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

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
        Log a generic audit event to the database.

        Returns:
            Audit log ID or empty string on failure
        """
        return self._log_with_retry(
            db=db,
            audit_type=AuditType.GENERIC,
            event_data={
                "event_type": event_type,
                "action": action,
                "description": description,
                "user_id": user_id,
                "user_email": user_email,
                "workspace_id": workspace_id,
                "security_level": security_level,
                "threat_level": threat_level,
                "resource": resource,
                "metadata": metadata,
                "success": success,
                "error_message": error_message,
                "request": request
            }
        )

    def create_canvas_audit(
        self,
        db: Session,
        agent_id: Optional[str],
        agent_execution_id: Optional[str],
        user_id: str,
        canvas_id: Optional[str],
        session_id: Optional[str],
        canvas_type: str = "generic",
        component_type: str = "component",
        component_name: Optional[str] = None,
        action: str = "present",
        governance_check_passed: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> Optional[str]:
        """
        Create a canvas audit entry for tracking.

        Replaces _create_canvas_audit() in canvas_tool.py

        Returns:
            Canvas audit ID or None on failure
        """
        return self._log_with_retry(
            db=db,
            audit_type=AuditType.CANVAS,
            event_data={
                "agent_id": agent_id,
                "agent_execution_id": agent_execution_id,
                "user_id": user_id,
                "canvas_id": canvas_id,
                "session_id": session_id,
                "canvas_type": canvas_type,
                "component_type": component_type,
                "component_name": component_name,
                "action": action,
                "governance_check_passed": governance_check_passed,
                "metadata": metadata,
                "request": request
            }
        )

    def create_browser_audit(
        self,
        db: Session,
        agent_id: Optional[str],
        agent_execution_id: Optional[str],
        user_id: str,
        session_id: str,
        action: str,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> Optional[str]:
        """
        Create a browser audit entry for tracking.

        Replaces _create_browser_audit() in browser_tool.py

        Returns:
            Browser audit ID or None on failure
        """
        return self._log_with_retry(
            db=db,
            audit_type=AuditType.BROWSER,
            event_data={
                "agent_id": agent_id,
                "agent_execution_id": agent_execution_id,
                "user_id": user_id,
                "session_id": session_id,
                "action": action,
                "url": url,
                "metadata": metadata,
                "request": request
            }
        )

    def create_device_audit(
        self,
        db: Session,
        agent_id: Optional[str],
        agent_execution_id: Optional[str],
        user_id: str,
        action: str,
        device_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> Optional[str]:
        """
        Create a device audit entry for tracking.

        Replaces _create_device_audit() in device_tool.py

        Returns:
            Device audit ID or None on failure
        """
        return self._log_with_retry(
            db=db,
            audit_type=AuditType.DEVICE,
            event_data={
                "agent_id": agent_id,
                "agent_execution_id": agent_execution_id,
                "user_id": user_id,
                "action": action,
                "device_type": device_type,
                "metadata": metadata,
                "request": request
            }
        )

    def create_agent_audit(
        self,
        db: Session,
        agent_id: str,
        agent_execution_id: str,
        user_id: str,
        action: str,
        workspace_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> Optional[str]:
        """
        Create an agent audit entry for tracking.

        Returns:
            Agent audit ID or None on failure
        """
        return self._log_with_retry(
            db=db,
            audit_type=AuditType.AGENT,
            event_data={
                "agent_id": agent_id,
                "agent_execution_id": agent_execution_id,
                "user_id": user_id,
                "action": action,
                "workspace_id": workspace_id,
                "metadata": metadata,
                "request": request
            }
        )

    def _log_with_retry(
        self,
        db: Session,
        audit_type: AuditType,
        event_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Internal method to log audit event with automatic retry.

        Args:
            db: Database session
            audit_type: Type of audit (canvas, browser, device, agent, generic)
            event_data: Event data dictionary

        Returns:
            Audit record ID or None on failure
        """
        for attempt in range(self.max_retries + 1):
            try:
                if audit_type == AuditType.CANVAS:
                    return self._create_canvas_audit_record(db, event_data)
                elif audit_type == AuditType.BROWSER:
                    return self._create_browser_audit_record(db, event_data)
                elif audit_type == AuditType.DEVICE:
                    return self._create_device_audit_record(db, event_data)
                elif audit_type == AuditType.AGENT:
                    return self._create_generic_audit_record(db, event_data, "agent")
                else:
                    return self._create_generic_audit_record(db, event_data, "generic")

            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Audit log attempt {attempt + 1} failed for {audit_type}, retrying: {e}")
                    continue
                else:
                    logger.error(f"Failed to log audit event after {self.max_retries + 1} attempts: {e}")
                    return None

    def _create_canvas_audit_record(self, db: Session, data: Dict[str, Any]) -> str:
        """Create CanvasAudit record"""
        request = data.get("request")
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        audit = CanvasAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=data.get("agent_id"),
            agent_execution_id=data.get("agent_execution_id"),
            user_id=data["user_id"],
            canvas_id=data.get("canvas_id"),
            session_id=data.get("session_id"),
            canvas_type=data.get("canvas_type", "generic"),
            component_type=data.get("component_type", "component"),
            component_name=data.get("component_name"),
            action=data.get("action", "present"),
            audit_metadata=data.get("metadata") or {},
            governance_check_passed=data.get("governance_check_passed"),
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )

        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit.id

    def _create_browser_audit_record(self, db: Session, data: Dict[str, Any]) -> str:
        """Create BrowserAudit record"""
        request = data.get("request")
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        audit = BrowserAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=data.get("agent_id"),
            agent_execution_id=data.get("agent_execution_id"),
            user_id=data["user_id"],
            session_id=data["session_id"],
            action=data.get("action"),
            url=data.get("url"),
            audit_metadata=data.get("metadata") or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )

        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit.id

    def _create_device_audit_record(self, db: Session, data: Dict[str, Any]) -> str:
        """Create DeviceAudit record"""
        request = data.get("request")
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        audit = DeviceAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=data.get("agent_id"),
            agent_execution_id=data.get("agent_execution_id"),
            user_id=data["user_id"],
            device_type=data.get("device_type"),
            action=data.get("action"),
            audit_metadata=data.get("metadata") or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )

        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit.id

    def _create_generic_audit_record(self, db: Session, data: Dict[str, Any], audit_subtype: str) -> str:
        """Create generic AuditLog record"""
        request = data.get("request")
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent") if request else None

        metadata = data.get("metadata") or {}
        if audit_subtype:
            metadata["audit_subtype"] = audit_subtype

        metadata_json = None
        if metadata:
            try:
                metadata_json = json.dumps(metadata)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize audit metadata: {e}")
                metadata_json = str(metadata)

        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            event_type=data.get("event_type", audit_subtype),
            security_level=data.get("security_level", SecurityLevel.LOW.value),
            threat_level=data.get("threat_level", ThreatLevel.NONE.value),
            timestamp=datetime.utcnow(),
            user_id=data.get("user_id"),
            user_email=data.get("user_email"),
            workspace_id=data.get("workspace_id", "default"),
            ip_address=ip_address,
            user_agent=user_agent,
            resource=data.get("resource"),
            action=data.get("action"),
            description=data.get("description"),
            metadata_json=metadata_json,
            success=data.get("success", True),
            error_message=data.get("error_message")
        )

        db.add(audit_log)
        db.commit()
        return audit_log.id


# Global instance
audit_service = AuditService()
