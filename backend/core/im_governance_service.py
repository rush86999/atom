"""
IM Governance Service

Centralized security layer for all IM platform interactions.
Implements rate limiting, webhook signature verification, governance maturity checks,
and audit trail logging.

Purpose: Enterprise-grade security governance for IM interactions (prevent spam, spoofing, and ensure compliance)
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from core.communication.adapters.base import PlatformAdapter
from core.communication.adapters.telegram import TelegramAdapter
from core.communication.adapters.whatsapp import WhatsAppAdapter
from core.governance_cache import get_governance_cache
from core.models import IMAuditLog

logger = logging.getLogger(__name__)


class IMGovernanceService:
    """
    Centralized security and governance service for IM platform interactions.

    Three-stage security pipeline:
    1. verify_and_rate_limit() - Rate limit check + webhook signature verification
    2. check_permissions() - Governance maturity checks using GovernanceCache
    3. log_to_audit_trail() - Async fire-and-forget audit logging

    Rate limiting: 10 requests/minute per platform:sender_id
    Verification: Platform-specific HMAC signature validation
    Governance: STUDENT agents blocked from IM triggers
    Audit: All interactions logged to IMAuditLog for compliance
    """

    def __init__(self, db: Session):
        """
        Initialize IM governance service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

        # Initialize platform adapters
        self.adapters = {
            "telegram": TelegramAdapter(),
            "whatsapp": WhatsAppAdapter(),
        }

        # Rate limiting configuration
        self.rate_limit_requests = 10  # requests per minute per user
        self.rate_limit_window = 60  # seconds

        # In-memory rate limit tracking (production: use Redis)
        self._rate_limit_store: Dict[str, list] = {}

        logger.info("IMGovernanceService initialized with %d adapters", len(self.adapters))

    async def verify_and_rate_limit(
        self,
        request: Request,
        body_bytes: bytes,
        platform: str
    ) -> Dict[str, Any]:
        """
        Stage 1: Rate limit check and webhook signature verification.

        Rate limiting is checked FIRST (before expensive signature verification).
        Then platform-specific signature verification is performed.

        Args:
            request: FastAPI Request object
            body_bytes: Raw request body bytes for signature verification
            platform: Platform name (telegram, whatsapp)

        Returns:
            Dict with verified=True and platform/sender_id

        Raises:
            HTTPException: 429 if rate limited, 403 if signature invalid
        """
        # Extract sender_id from request for rate limiting
        sender_id = self._extract_sender_id(request, body_bytes, platform)
        if not sender_id:
            logger.warning(f"Could not extract sender_id from {platform} webhook")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request format"
            )

        # Rate limit check FIRST (cheap operation)
        rate_limit_key = f"{platform}:{sender_id}"
        if not self._check_rate_limit(rate_limit_key):
            logger.warning(f"Rate limit exceeded for {rate_limit_key}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "Retry-After": str(self.rate_limit_window),
                    "X-RateLimit-Limit": str(self.rate_limit_requests),
                    "X-RateLimit-Window": str(self.rate_limit_window)
                }
            )

        # Get platform adapter
        adapter = self.adapters.get(platform)
        if not adapter:
            logger.error(f"Unknown platform: {platform}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported platform: {platform}"
            )

        # Signature verification (expensive operation, done after rate limit)
        try:
            signature_valid = await adapter.verify_request(request, body_bytes)
            if not signature_valid:
                logger.warning(f"Invalid signature for {platform} webhook from {sender_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid webhook signature"
                )
        except Exception as e:
            logger.error(f"Error verifying {platform} webhook: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Webhook verification failed"
            )

        logger.info(f"Webhook verified for {platform} user {sender_id}")

        return {
            "verified": True,
            "platform": platform,
            "sender_id": sender_id
        }

    async def check_permissions(
        self,
        sender_id: str,
        platform: str,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stage 2: Governance maturity and permission checks.

        Checks:
        1. User is not blocked (from GovernanceCache)
        2. Agent maturity allows IM triggers (STUDENT blocked)

        Args:
            sender_id: Platform-specific user ID
            platform: Platform name
            agent_id: Optional specific agent being triggered

        Returns:
            Dict with allowed=True and governance metadata

        Raises:
            HTTPException: 403 if governance check fails
        """
        cache = get_governance_cache()

        # Check if user is blocked
        blocked_key = f"im_blocked:{platform}:{sender_id}"
        blocked = await cache.get(blocked_key)
        if blocked and blocked.get("blocked"):
            logger.warning(f"Blocked {platform} user {sender_id} attempted trigger")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is blocked from IM interactions"
            )

        # If specific agent specified, check maturity
        if agent_id:
            agent_maturity = await cache.get(agent_id, "im_trigger")
            if agent_maturity:
                maturity_level = agent_maturity.get("maturity_level", "STUDENT")
                if maturity_level == "STUDENT":
                    logger.warning(
                        f"STUDENT agent {agent_id} blocked from IM trigger "
                        f"by {platform} user {sender_id}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="STUDENT agents are not allowed to execute IM triggers"
                    )

                logger.info(
                    f"Agent {agent_id} ({maturity_level}) allowed for "
                    f"{platform} user {sender_id}"
                )

                return {
                    "allowed": True,
                    "agent_id": agent_id,
                    "maturity_level": maturity_level,
                    "platform": platform,
                    "sender_id": sender_id
                }

        # No specific agent - generic permission check
        logger.info(f"Generic permission granted for {platform} user {sender_id}")
        return {
            "allowed": True,
            "platform": platform,
            "sender_id": sender_id
        }

    async def log_to_audit_trail(
        self,
        platform: str,
        sender_id: str,
        payload: Dict[str, Any],
        action: str,
        success: bool,
        error_message: Optional[str] = None,
        rate_limited: bool = False,
        signature_valid: bool = True,
        governance_check_passed: Optional[bool] = None,
        agent_maturity_level: Optional[str] = None
    ) -> None:
        """
        Stage 3: Async fire-and-forget audit trail logging.

        Creates IMAuditLog record without blocking request processing.
        Errors are logged but don't raise exceptions (audit log failure
        shouldn't break webhook responses).

        Args:
            platform: Platform name
            sender_id: Platform-specific user ID
            payload: Original request payload (will be hashed for PII protection)
            action: Action performed (webhook_received, command_run, etc.)
            success: Whether the operation succeeded
            error_message: Error message if failed
            rate_limited: True if request was rate limited
            signature_valid: True if webhook signature was valid
            governance_check_passed: True if governance check passed
            agent_maturity_level: Agent maturity level if applicable
        """
        async def _do_log():
            try:
                # Hash payload for PII protection (SHA256)
                payload_json = json.dumps(payload, sort_keys=True)
                payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

                # Extract metadata (non-sensitive only)
                metadata_json = {
                    "action": action,
                    "has_media": any(k in payload for k in ["media_id", "media_type", "voice", "audio"]),
                }

                # Add agent maturity if present
                if agent_maturity_level:
                    metadata_json["agent_maturity"] = agent_maturity_level

                # Create audit log record
                audit_log = IMAuditLog(
                    platform=platform,
                    sender_id=sender_id,
                    action=action,
                    payload_hash=payload_hash,
                    metadata_json=metadata_json,
                    success=success,
                    error_message=error_message,
                    rate_limited=rate_limited,
                    signature_valid=signature_valid,
                    governance_check_passed=governance_check_passed,
                    agent_maturity_level=agent_maturity_level,
                    timestamp=datetime.utcnow()
                )

                self.db.add(audit_log)
                self.db.commit()

                logger.debug(
                    f"Audit log created for {platform} user {sender_id}: "
                    f"action={action}, success={success}"
                )

            except Exception as e:
                # Don't raise - audit log failure shouldn't break webhooks
                logger.error(f"Failed to create IM audit log: {e}")

        # Fire-and-forget async task
        asyncio.create_task(_do_log())

    def _extract_sender_id(self, request: Request, body_bytes: bytes, platform: str) -> Optional[str]:
        """
        Extract sender_id from request payload for rate limiting.

        Args:
            request: FastAPI Request object
            body_bytes: Raw request body bytes
            platform: Platform name

        Returns:
            sender_id string or None if not found
        """
        try:
            payload = json.loads(body_bytes)

            if platform == "telegram":
                # Telegram: message.from.id or callback_query.from.id
                message = payload.get("message", {})
                if not message or not isinstance(message, dict):
                    message = payload.get("callback_query", {})
                if not isinstance(message, dict):
                    return None
                from_info = message.get("from", {})
                if not isinstance(from_info, dict):
                    return None
                return str(from_info.get("id", ""))

            elif platform == "whatsapp":
                # WhatsApp: entry[0].changes[0].value.messages[0].from
                entry = payload.get("entry", [{}])
                if not isinstance(entry, list) or not entry:
                    return None
                entry_data = entry[0]
                if not isinstance(entry_data, dict):
                    return None
                changes = entry_data.get("changes", [{}])
                if not isinstance(changes, list) or not changes:
                    return None
                changes_data = changes[0]
                if not isinstance(changes_data, dict):
                    return None
                value = changes_data.get("value", {})
                if not isinstance(value, dict):
                    return None
                messages = value.get("messages", [])
                if not isinstance(messages, list) or not messages:
                    return None
                message_data = messages[0]
                if not isinstance(message_data, dict):
                    return None
                return str(message_data.get("from", ""))

            logger.warning(f"Could not extract sender_id for platform {platform}")
            return None

        except (json.JSONDecodeError, KeyError, IndexError, UnicodeDecodeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error extracting sender_id: {e}")
            return None

    def _check_rate_limit(self, key: str) -> bool:
        """
        Check if request is within rate limit using token bucket algorithm.

        Rate limit: 10 requests per minute per key (platform:sender_id)

        Args:
            key: Rate limit key (platform:sender_id)

        Returns:
            True if within rate limit, False if exceeded
        """
        now = datetime.utcnow().timestamp()

        # Get or initialize request history for this key
        if key not in self._rate_limit_store:
            self._rate_limit_store[key] = []

        # Get request history
        requests = self._rate_limit_store[key]

        # Remove old requests outside the time window
        requests[:] = [req_time for req_time in requests if now - req_time < self.rate_limit_window]

        # Check if limit exceeded
        if len(requests) >= self.rate_limit_requests:
            return False

        # Add current request
        requests.append(now)
        return True

    def get_rate_limit_status(self, platform: str, sender_id: str) -> Dict[str, Any]:
        """
        Get current rate limit status for a user.

        Args:
            platform: Platform name
            sender_id: Platform-specific user ID

        Returns:
            Dict with rate limit status
        """
        key = f"{platform}:{sender_id}"
        requests = self._rate_limit_store.get(key, [])

        now = datetime.utcnow().timestamp()
        # Remove old requests
        requests[:] = [req_time for req_time in requests if now - req_time < self.rate_limit_window]

        return {
            "limit": self.rate_limit_requests,
            "remaining": max(0, self.rate_limit_requests - len(requests)),
            "window": self.rate_limit_window,
            "reset_at": int(min(requests) + self.rate_limit_window) if requests else now
        }
