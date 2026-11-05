"""
HITL Service - Centralized resolution logic for Human-in-the-Loop actions.
Handles approvals, rejections, 2FA enforcement, and workflow resumption.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import update

from core.database import get_db_session
from core.models import HITLAction, HITLActionStatus, User
from core.communication_service import communication_service

logger = logging.getLogger(__name__)

class HITLService:
    """
    Manages the lifecycle of HITL actions after they are created.
    """

    async def resolve_action(
        self,
        action_id: str,
        resolution: str,
        resolver_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolves a pending HITL action.
        
        Returns:
            Dict containing final status and any required next steps (e.g. 2FA).
        """
        with get_db_session() as db:
            # The conditional UPDATE below is the real claim. with_for_update
            # is kept for PostgreSQL; SQLite ignores it, so status alone is
            # never treated as an atomic guard.
            action = (
                db.query(HITLAction)
                .filter(HITLAction.id == action_id)
                .with_for_update()
                .first()
            )
            if not action:
                raise ValueError(f"HITL Action {action_id} not found")

            user = db.query(User).filter(User.id == resolver_id).first()
            if not user:
                raise ValueError(f"Resolver user {resolver_id} not found")

            def _current_status() -> str:
                current = (
                    db.query(HITLAction)
                    .filter(HITLAction.id == action_id)
                    .first()
                )
                return str(getattr(current, "status", "unknown") or "unknown")

            def _claim(values: Dict[str, Any], allowed_statuses) -> bool:
                result = db.execute(
                    update(HITLAction)
                    .where(
                        HITLAction.id == action_id,
                        HITLAction.status.in_(list(allowed_statuses)),
                    )
                    .values(**values)
                )
                return result.rowcount == 1

            now = datetime.now(timezone.utc)

            # 1. Handle Rejection
            if resolution == "rejected":
                if action.status in (
                        HITLActionStatus.APPROVED.value,
                        HITLActionStatus.REJECTED.value):
                    return {
                        "status": action.status,
                        "message": "Action already resolved",
                    }
                with db.no_autoflush:
                    claimed = _claim(
                        {
                            "status": HITLActionStatus.REJECTED.value,
                            "reviewed_by": resolver_id,
                            "reviewed_at": now,
                        },
                        (
                            HITLActionStatus.PENDING.value,
                            HITLActionStatus.PENDING_2FA.value,
                        ),
                    )
                    if not claimed:
                        db.rollback()
                        return {
                            "status": _current_status(),
                            "message": "Action already resolved",
                        }
                    db.expire(action)
                    action = (
                        db.query(HITLAction)
                        .filter(HITLAction.id == action_id)
                        .first()
                    )
                    # Callback compatibility only; reviewed_by/reviewed_at are
                    # the durable columns.
                    action.resolver_id = resolver_id
                    db.commit()
                logger.info(f"HITL Action {action_id} REJECTED by {user.email}")

                # Student agents learn from corrections: a human rejection is
                # the strongest "don't do this" signal in the workspace.
                import asyncio
                from core.student_learning_service import auto_observe
                asyncio.create_task(auto_observe(
                    workspace_id=action.workspace_id or "default",
                    observation_type="hitl_rejection",
                    summary=f"A human rejected '{action.action_type}'"
                            + (f": {action.reason}" if action.reason else ""),
                    details={"action_type": action.action_type},
                    action_type=action.action_type,
                ))
                return {"status": "rejected"}

            # 2. Check for 2FA Enforcement (Phase 5)
            # High-stakes actions (URGENT priority) require 2FA if enabled for user
            if action.priority == "URGENT" and user.two_factor_enabled:
                verified_2fa = metadata.get("verified_2fa", False) if metadata else False
                if not verified_2fa:
                    if action.status == HITLActionStatus.PENDING_2FA.value:
                        return {
                            "status": "pending_2fa",
                            "message": "2FA verification required",
                        }
                    with db.no_autoflush:
                        claimed = _claim(
                            {"status": HITLActionStatus.PENDING_2FA.value},
                            (HITLActionStatus.PENDING.value,),
                        )
                        if not claimed:
                            db.rollback()
                            return {
                                "status": _current_status(),
                                "message": "Action already resolved",
                            }
                        db.expire(action)
                        action = (
                            db.query(HITLAction)
                            .filter(HITLAction.id == action_id)
                            .first()
                        )
                        db.commit()
                    logger.info(
                        f"HITL Action {action_id} requires 2FA from {user.email}")
                    await self._prompt_for_2fa(action, user)
                    return {
                        "status": "pending_2fa",
                        "message": "2FA verification required",
                    }

            if action.status in (
                    HITLActionStatus.APPROVED.value,
                    HITLActionStatus.REJECTED.value):
                return {
                    "status": action.status,
                    "message": "Action already resolved",
                }

            # 3. Handle Approval
            with db.no_autoflush:
                claimed = _claim(
                    {
                        "status": HITLActionStatus.APPROVED.value,
                        "reviewed_by": resolver_id,
                        "reviewed_at": now,
                    },
                    (
                        HITLActionStatus.PENDING.value,
                        HITLActionStatus.PENDING_2FA.value,
                    ),
                )
                if not claimed:
                    db.rollback()
                    return {
                        "status": _current_status(),
                        "message": "Action already resolved",
                    }
                db.expire(action)
                action = (
                    db.query(HITLAction)
                    .filter(HITLAction.id == action_id)
                    .first()
                )
                action.resolver_id = resolver_id
                db.commit()

            logger.info(f"HITL Action {action_id} APPROVED by {user.email}")

            # Student agents learn from approvals: what humans keep
            # green-lighting defines trusted behavior patterns.
            import asyncio
            from core.student_learning_service import auto_observe
            asyncio.create_task(auto_observe(
                workspace_id=action.workspace_id or "default",
                observation_type="hitl_approval",
                summary=f"A human approved '{action.action_type}'"
                        + (f": {action.reason}" if action.reason else ""),
                details={"action_type": action.action_type},
                action_type=action.action_type,
            ))

            # 4. Resume Workflow (Phase 4)
            await self._resume_workflow(action)

            return {"status": "approved"}

    async def _prompt_for_2fa(self, action: HITLAction, user: User):
        """Send a 2FA verification prompt to the user"""
        source = "slack"
        channel_id = None
        
        if action.notified_channel_id and ":" in action.notified_channel_id:
            source, channel_id = action.notified_channel_id.split(":", 1)
        
        if not channel_id:
            return

        msg = (
            f"🔒 *2FA Required*: The action `{action.action_type}` is marked as high-stakes.\n"
            f"Please verify your identity to proceed. [Link to 2FA Dashboard]"
        )
        
        adapter = communication_service.get_adapter(source)
        await adapter.send_message(channel_id, msg)

    async def _resume_workflow(self, action: HITLAction):
        """Notify the system that the action is approved and can proceed"""
        # Logic to unblock the agent that called request_approval
        # In the current sync implementation, request_approval waits on an event or polling.
        # For async persistence, we would trigger the callback URL if provided.
        logger.info(f"Resuming workflow for action {action.id}")

        # Placeholder for actual resumption logic (e.g. QStash/Redis trigger)
        # If the action has a callback_url in params, we hit it.
        callback_url = (action.params or {}).get("callback_url")
        if callback_url:
            # SSRF FIX: Validate URL before making request
            if not self._validate_url(callback_url):
                logger.error(f"SSRF blocked: Invalid callback_url: {callback_url}")
                return

            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(callback_url, json={
                        "action_id": action.id,
                        "status": "approved",
                        "resolver_id": action.resolver_id
                    })
                except Exception as e:
                    logger.error(f"Failed to trigger HITL callback: {e}")

    def _validate_url(self, url: str) -> bool:
        """
        Validate URL to prevent SSRF attacks.

        Blocks:
        - Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
        - localhost and 127.0.0.1
        - Link-local addresses (169.254.0.0/16)
        - Internal hostnames (metadata.google.internal, etc.)

        Args:
            url: URL to validate

        Returns:
            True if URL is allowed, False otherwise
        """
        import re
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""

            # Block private IP ranges
            if hostname in ('localhost', '127.0.0.1', '::1'):
                logger.warning(f"SSRF blocked: localhost access denied: {hostname}")
                return False

            # Block private IPv4 ranges
            ipv4_pattern = r'^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|169\.254\.)'
            if re.match(ipv4_pattern, hostname):
                logger.warning(f"SSRF blocked: private IPv4 address: {hostname}")
                return False

            # Block internal hostnames
            internal_patterns = [
                'metadata.google.internal',
                '.compute.internal',
                '.cloudfunctions.internal',
                'localhost',
                'internal'
            ]
            if any(pattern in hostname.lower() for pattern in internal_patterns):
                logger.warning(f"SSRF blocked: internal hostname: {hostname}")
                return False

            # Only allow http and https schemes
            if parsed.scheme not in ('http', 'https'):
                logger.warning(f"SSRF blocked: invalid scheme: {parsed.scheme}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating URL: {e}")
            return False

# Singleton
hitl_service = HITLService()
