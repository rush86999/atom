"""
Audit Logger for Device, Media, and Smart Home Actions

This module provides comprehensive audit logging for all sensitive operations
in Personal Edition. Tracks media control (Spotify, Sonos), smart home
(Hue, Home Assistant), and creative (FFmpeg) actions with structured JSON logs.

Features:
- Structured JSON logging with timestamp, user_id, agent_id, action, service
- Separate audit log file: logs/audit.log (rotates daily)
- Action categories: media, smarthome, creative, local_only_block
- Query methods for retrieving audit logs by user or service
- Log rotation and retention (90 days default, gzip compressed)
- Async logging to avoid blocking operations
- IP address tracking for network security

Log Format:
{
  "timestamp": "2026-02-20T10:30:00Z",
  "user_id": "user_123",
  "agent_id": "agent_456",
  "action": "pause_playback",
  "category": "media",
  "service": "spotify",
  "details": {"device_id": "device_abc"},
  "result": "success",
  "ip_address": "192.168.1.100"
}

Configuration:
- Environment: AUDIT_LOG_PATH (default: logs/audit.log)
- Environment: AUDIT_LOG_RETENTION_DAYS (default: 90)

Usage:
    from core.privsec.audit_logger import AuditLogger

    audit = AuditLogger()
    audit.log_media_action(
        user_id="user_123",
        agent_id="agent_456",
        action="pause_playback",
        service="spotify",
        details={"device_id": "device_abc"},
        result="success"
    )
"""

import asyncio
import gzip
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.structured_logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Configuration
# ============================================================================

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "logs/audit.log")
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "90"))


# ============================================================================
# Audit Logger Service
# ============================================================================

class AuditLogger:
    """
    Singleton service for structured audit logging.

    Provides methods for logging media, smart home, and creative actions.
    Writes to separate audit log file with JSON formatting.
    Implements log rotation and retention policies.

    Thread-safe: Uses module-level singleton instance
    """

    _instance: Optional['AuditLogger'] = None

    def __new__(cls) -> 'AuditLogger':
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize audit logger (only runs once due to singleton)."""
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self._log_path = Path(AUDIT_LOG_PATH)
        self._retention_days = AUDIT_LOG_RETENTION_DAYS

        # Create logs directory if it doesn't exist
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup file handler for audit logs
        self._setup_file_handler()

        logger.info(
            "AuditLogger initialized",
            extra={
                "log_path": str(self._log_path),
                "retention_days": self._retention_days
            }
        )

    def _setup_file_handler(self):
        """Setup separate file handler for audit logs."""
        self._audit_handler = logging.FileHandler(self._log_path)
        self._audit_handler.setFormatter(
            logging.Formatter('%(message)s')  # JSON only, no prefix
        )

        # Create audit-specific logger
        self._audit_logger = logging.getLogger('atom.audit')
        self._audit_logger.addHandler(self._audit_handler)
        self._audit_logger.setLevel(logging.INFO)
        self._audit_logger.propagate = False  # Don't propagate to root logger

    def _write_audit_log(
        self,
        user_id: str,
        agent_id: Optional[str],
        action: str,
        category: str,
        service: str,
        details: Dict[str, Any],
        result: str,
        ip_address: Optional[str] = None
    ):
        """
        Write audit log entry (internal method).

        Args:
            user_id: User ID performing action
            agent_id: Agent ID (None if human action)
            action: Action performed (e.g., "pause_playback")
            category: Action category (media, smarthome, creative, local_only_block)
            service: Service name (spotify, sonos, hue, etc.)
            details: Additional details (device_id, track_uri, etc.)
            result: Result (success, failed, blocked, error)
            ip_address: Client IP address (optional)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "agent_id": agent_id,
            "action": action,
            "category": category,
            "service": service,
            "details": details,
            "result": result,
            "ip_address": ip_address
        }

        # Write as JSON (single line)
        self._audit_logger.info(json.dumps(log_entry))

    # ========================================================================
    # Media Action Logging
    # ========================================================================

    def log_media_action(
        self,
        user_id: str,
        agent_id: Optional[str],
        action: str,
        service: str,
        details: Dict[str, Any],
        result: str
    ):
        """
        Log media control action (Spotify, Sonos).

        Args:
            user_id: User ID
            agent_id: Agent ID (None if human)
            action: Action (play, pause, skip, volume, etc.)
            service: Service name (spotify, sonos)
            details: Additional details (track_uri, device_id, speaker_ip)
            result: Result (success, failed, blocked)
        """
        self._write_audit_log(
            user_id=user_id,
            agent_id=agent_id,
            action=action,
            category="media",
            service=service,
            details=details,
            result=result
        )

    # ========================================================================
    # Smart Home Action Logging
    # ========================================================================

    def log_smarthome_action(
        self,
        user_id: str,
        agent_id: Optional[str],
        action: str,
        service: str,
        details: Dict[str, Any],
        result: str
    ):
        """
        Log smart home action (Hue, Home Assistant).

        Args:
            user_id: User ID
            agent_id: Agent ID (None if human)
            action: Action (turn_on, turn_off, set_color, etc.)
            service: Service name (hue, home_assistant)
            details: Additional details (light_id, entity_id, bridge_ip)
            result: Result (success, failed, blocked)
        """
        self._write_audit_log(
            user_id=user_id,
            agent_id=agent_id,
            action=action,
            category="smarthome",
            service=service,
            details=details,
            result=result
        )

    # ========================================================================
    # Creative Action Logging
    # ========================================================================

    def log_creative_action(
        self,
        user_id: str,
        agent_id: Optional[str],
        action: str,
        operation: str,
        details: Dict[str, Any],
        result: str
    ):
        """
        Log creative tool action (FFmpeg).

        Args:
            user_id: User ID
            agent_id: Agent ID (None if human)
            action: Action (trim_video, extract_audio, etc.)
            operation: FFmpeg operation
            details: Additional details (input_path, output_path, job_id)
            result: Result (success, failed, blocked)
        """
        self._write_audit_log(
            user_id=user_id,
            agent_id=agent_id,
            action=action,
            category="creative",
            service="ffmpeg",
            details={**details, "operation": operation},
            result=result
        )

    # ========================================================================
    # Local-Only Mode Logging
    # ========================================================================

    def log_local_only_block(
        self,
        user_id: str,
        agent_id: Optional[str],
        service: str,
        attempted_action: str,
        reason: Optional[str] = None
    ):
        """
        Log when local-only mode blocks external service request.

        Args:
            user_id: User ID
            agent_id: Agent ID (None if human)
            service: Service being accessed (spotify, notion, etc.)
            attempted_action: Action being attempted
            reason: Reason for blocking (optional)
        """
        details = {
            "attempted_action": attempted_action
        }
        if reason:
            details["reason"] = reason

        self._write_audit_log(
            user_id=user_id,
            agent_id=agent_id,
            action=f"blocked_{attempted_action}",
            category="local_only_block",
            service=service,
            details=details,
            result="blocked"
        )

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_user_audit_log(self, user_id: str, limit: int = 100) -> List[Dict]:
        """
        Retrieve audit entries for specific user.

        Args:
            user_id: User ID to query
            limit: Maximum number of entries (default: 100)

        Returns:
            List of audit log entries (most recent first)
        """
        entries = []

        try:
            with open(self._log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get('user_id') == user_id:
                            entries.append(entry)
                            if len(entries) >= limit:
                                break
                    except json.JSONDecodeError:
                        continue

        except FileNotFoundError:
            logger.warning(f"Audit log file not found: {self._log_path}")
            return []

        # Return most recent first
        return list(reversed(entries))

    def get_service_audit_log(self, service: str, limit: int = 100) -> List[Dict]:
        """
        Retrieve audit entries for specific service.

        Args:
            service: Service name to query (spotify, sonos, hue, etc.)
            limit: Maximum number of entries (default: 100)

        Returns:
            List of audit log entries (most recent first)
        """
        entries = []

        try:
            with open(self._log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get('service') == service:
                            entries.append(entry)
                            if len(entries) >= limit:
                                break
                    except json.JSONDecodeError:
                        continue

        except FileNotFoundError:
            logger.warning(f"Audit log file not found: {self._log_path}")
            return []

        # Return most recent first
        return list(reversed(entries))

    # ========================================================================
    # Log Rotation and Retention
    # ========================================================================

    def rotate_audit_logs(self):
        """
        Rotate audit logs (compress old logs).

        Compresses logs older than today with gzip.
        Should be called daily (e.g., via cron or scheduler).
        """
        today = datetime.utcnow().date()

        # Check if current log file exists
        if not self._log_path.exists():
            return

        # Get current log file modification time
        mtime = datetime.fromtimestamp(self._log_path.stat().st_mtime)

        # If log is from yesterday, rotate it
        if mtime.date() < today:
            yesterday = mtime.date()
            rotated_path = self._log_path.with_suffix(
                f'.{yesterday.strftime("%Y-%m-%d")}.log'
            )

            # Rename with date suffix
            self._log_path.rename(rotated_path)

            # Compress with gzip
            compressed_path = rotated_path.with_suffix('.log.gz')
            with open(rotated_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    f_out.writelines(f_in)

            # Remove uncompressed file
            rotated_path.unlink()

            logger.info(
                "Audit log rotated and compressed",
                extra={
                    "rotated_path": str(rotated_path),
                    "compressed_path": str(compressed_path)
                }
            )

            # Re-create file handler for new log
            self._audit_handler.close()
            self._setup_file_handler()

    def cleanup_old_audit_logs(self):
        """
        Remove audit logs older than retention period.

        Should be called daily (e.g., via cron or scheduler).
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self._retention_days)
        removed_count = 0

        # Find all audit log files (including rotated)
        log_pattern = self._log_path.stem + ".*.log*"
        for log_file in self._log_path.parent.glob(log_pattern):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                if mtime < cutoff_date:
                    log_file.unlink()
                    removed_count += 1
                    logger.info(
                        "Old audit log removed",
                        extra={
                            "file": str(log_file),
                            "age_days": (datetime.utcnow() - mtime).days
                        }
                    )

            except Exception as e:
                logger.error(
                    "Failed to remove old audit log",
                    extra={
                        "file": str(log_file),
                        "error": str(e)
                    }
                )

        if removed_count > 0:
            logger.info(
                "Audit log cleanup complete",
                extra={"removed_count": removed_count}
            )


# ============================================================================
# Async Logging Helpers
# ============================================================================

async def log_media_action_async(
    user_id: str,
    agent_id: Optional[str],
    action: str,
    service: str,
    details: Dict[str, Any],
    result: str
):
    """
    Async wrapper for media action logging.

    Runs logging in background thread to avoid blocking.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: AuditLogger().log_media_action(
            user_id=user_id,
            agent_id=agent_id,
            action=action,
            service=service,
            details=details,
            result=result
        )
    )


async def log_smarthome_action_async(
    user_id: str,
    agent_id: Optional[str],
    action: str,
    service: str,
    details: Dict[str, Any],
    result: str
):
    """
    Async wrapper for smart home action logging.

    Runs logging in background thread to avoid blocking.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: AuditLogger().log_smarthome_action(
            user_id=user_id,
            agent_id=agent_id,
            action=action,
            service=service,
            details=details,
            result=result
        )
    )


# ============================================================================
# Module-Level Singleton Instance
# ============================================================================

_audit_logger_instance: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get singleton AuditLogger instance.

    Returns:
        AuditLogger singleton instance
    """
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance
