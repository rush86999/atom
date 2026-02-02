"""
Push Notification Service

Integrates with Firebase Cloud Messaging (FCM) and Apple Push Notification Service (APNs)
to send push notifications to mobile devices for agent events, alerts, and system updates.
"""

import logging
import uuid
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Feature flags
import os
PUSH_NOTIFICATIONS_ENABLED = os.getenv("PUSH_NOTIFICATIONS_ENABLED", "true").lower() == "true"
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY")  # Firebase service account key
APNS_KEY_ID = os.getenv("APNS_KEY_ID")  # Apple Push Notification key ID
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID")
APNS_BUNDLE_ID = os.getenv("APNS_BUNDLE_ID")

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class PushNotificationService:
    """
    Push notification service for mobile devices.

    Supports:
    - Firebase Cloud Messaging (FCM) for Android
    - Apple Push Notification Service (APNs) for iOS
    - Device token management
    - Notification queue and retry
    - Rich notifications with actions
    """

    def __init__(self, db: Session):
        self.db = db
        self._fcm_enabled = bool(FCM_SERVER_KEY) and PUSH_NOTIFICATIONS_ENABLED
        self._apns_enabled = all([APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID]) and PUSH_NOTIFICATIONS_ENABLED

    async def register_device(
        self,
        user_id: str,
        device_token: str,
        platform: str,  # "ios" | "android" | "web"
        device_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register a device for push notifications.

        Args:
            user_id: User ID
            device_token: Push notification token
            platform: Platform type (ios, android, web)
            device_info: Optional device info (model, OS version, etc.)

        Returns:
            Registration result with device_id
        """
        try:
            # Check if device already exists
            from core.models import MobileDevice

            existing_device = self.db.query(MobileDevice).filter(
                MobileDevice.device_token == device_token
            ).first()

            if existing_device:
                # Update existing device
                existing_device.platform = platform
                existing_device.device_info = device_info or {}
                existing_device.last_active = datetime.utcnow()
                existing_device.status = "active"
                self.db.commit()

                logger.info(f"Updated device {existing_device.id} for user {user_id}")

                return {
                    "device_id": existing_device.id,
                    "status": "updated",
                    "platform": platform
                }
            else:
                # Create new device
                device = MobileDevice(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    device_token=device_token,
                    platform=platform,
                    status="active",
                    device_info=device_info or {},
                    created_at=datetime.utcnow(),
                    last_active=datetime.utcnow()
                )

                self.db.add(device)
                self.db.commit()

                logger.info(f"Registered new device {device.id} for user {user_id}")

                return {
                    "device_id": device.id,
                    "status": "registered",
                    "platform": platform
                }

        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def send_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal",  # "normal" | "high"
    ) -> bool:
        """
        Send push notification to all user's active devices.

        Args:
            user_id: User to notify
            notification_type: Type of notification (agent_alert, system_alert, etc.)
            title: Notification title
            body: Notification body
            data: Optional additional data
            priority: Notification priority

        Returns:
            True if notification sent successfully
        """
        if not PUSH_NOTIFICATIONS_ENABLED:
            logger.debug("Push notifications disabled")
            return False

        try:
            # Get user's active devices
            from core.models import MobileDevice

            devices = self.db.query(MobileDevice).filter(
                MobileDevice.user_id == user_id,
                MobileDevice.status == "active"
            ).all()

            if not devices:
                logger.info(f"No active devices found for user {user_id}")
                return False

            success_count = 0

            for device in devices:
                try:
                    if device.platform == "android":
                        success = await self._send_fcm_notification(device, title, body, data, priority)
                    elif device.platform == "ios":
                        success = await self._send_apns_notification(device, title, body, data, priority)
                    else:
                        logger.warning(f"Unsupported platform: {device.platform}")
                        continue

                    if success:
                        success_count += 1

                except Exception as e:
                    logger.error(f"Failed to send to device {device.id}: {e}")
                    # Mark device as potentially inactive
                    if "token expired" in str(e).lower() or "unregistered" in str(e).lower():
                        device.status = "inactive"
                        self.db.commit()

            logger.info(f"Sent notification to {success_count}/{len(devices)} devices for user {user_id}")
            return success_count > 0

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def _send_fcm_notification(
        self,
        device,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]],
        priority: str
    ) -> bool:
        """Send notification via Firebase Cloud Messaging."""
        try:
            import httpx

            url = "https://fcm.googleapis.com/fcm/send"
            headers = {
                "Authorization": f"key={FCM_SERVER_KEY}",
                "Content-Type": "application/json"
            }

            # Build FCM payload
            notification = {
                "title": title,
                "body": body,
                "sound": "default" if priority == "high" else None
            }

            payload = {
                "to": device.device_token,
                "notification": notification,
                "data": data or {}
            }

            if priority == "high":
                payload["android"] = {
                    "priority": "high"
                }
                payload["apns"] = {
                    "payload": {
                        "aps": {
                            "alert": title,
                            "badge": 1,
                            "sound": "default"
                        }
                    }
                }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=10.0)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", 0) > 0:
                        logger.info(f"FCM notification sent to device {device.id}")
                        return True
                    else:
                        logger.warning(f"FCM notification failed: {result.get('results', [{}])[0].get('error')}")
                        return False
                else:
                    logger.error(f"FCM request failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"FCM notification error: {e}")
            return False

    async def _send_apns_notification(
        self,
        device,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]],
        priority: str
    ) -> bool:
        """Send notification via Apple Push Notification Service."""
        try:
            import httpx

            # APNs endpoint (production vs sandbox)
            is_sandbox = "sandbox" in os.getenv("APNS_KEY_ID", "")
            apns_url = f"https://{'' if is_sandbox else 'api'}.push.apple.com/3/device/{device.device_token}"

            headers = {
                "apns-topic": APNS_BUNDLE_ID,
                "Content-Type": "application/json"
            }

            # Build APNs payload
            payload = {
                "aps": {
                    "alert": {
                        "title": title,
                        "body": body
                    },
                    "badge": 1,
                    "sound": "default" if priority == "high" else None
                }
            }

            # Add custom data
            if data:
                payload["custom_data"] = data

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    apns_url,
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )

                if response.status_code == 200:
                    logger.info(f"APNs notification sent to device {device.id}")
                    return True
                elif response.status_code == 410:
                    logger.warning(f"Device token expired for device {device.id}")
                    return False
                else:
                    logger.error(f"APNs request failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"APNs notification error: {e}")
            return False

    async def send_agent_operation_notification(
        self,
        user_id: str,
        agent_name: str,
        operation_type: str,
        status: str,
        context: Optional[str] = None
    ) -> bool:
        """
        Send notification about agent operation status.

        Use cases:
        - Agent operation completes
        - Agent operation fails
        - Agent requires user approval
        """
        if status == "completed":
            title = f"✅ {agent_name} Completed"
            body = f"Successfully completed {operation_type}"
        elif status == "failed":
            title = f"❌ {agent_name} Failed"
            body = f"Failed during {operation_type}"
        elif status == "awaiting_approval":
            title = f"⏸️ Awaiting Approval"
            body = f"{agent_name} needs your approval for {operation_type}"
        else:
            title = f"ℹ️ {agent_name} Update"
            body = f"{agent_name}: {context or operation_type}"

        return await self.send_notification(
            user_id=user_id,
            notification_type="agent_operation",
            title=title,
            body=body,
            data={
                "agent_name": agent_name,
                "operation_type": operation_type,
                "status": status,
                "context": context
            },
            priority="normal"
        )

    async def send_error_alert(
        self,
        user_id: str,
        error_type: str,
        error_message: str,
        severity: str = "warning"
    ) -> bool:
        """
        Send notification about error.

        Use cases:
        - Integration connection fails
        - Agent operation error
        - System threshold breached
        """
        title = f"⚠️ Error: {error_type}" if severity == "warning" else f"🚨 Critical: {error_type}"
        body = error_message

        return await self.send_notification(
            user_id=user_id,
            notification_type="error_alert",
            title=title,
            body=body,
            data={
                "error_type": error_type,
                "error_message": error_message,
                "severity": severity
            },
            priority=severity
        )

    async def send_approval_request(
        self,
        user_id: str,
        agent_id: str,
        agent_name: str,
        action_description: str,
        options: List[Dict[str, Any]],
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Send notification requesting user approval.

        Use case: Agent needs permission for sensitive action.
        """
        title = "🔔 Approval Required"
        body = f"{agent_name} needs your permission: {action_description}"

        return await self.send_notification(
            user_id=user_id,
            notification_type="approval_request",
            title=title,
            body=body,
            data={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "action_description": action_description,
                "options": options,
                "expires_at": expires_at.isoformat() if expires_at else None
            },
            priority="high"
        )

    async def send_system_alert(
        self,
        user_id: str,
        alert_type: str,
        message: str,
        severity: str = "info"
    ) -> bool:
        """
        Send system alert notification.

        Use cases:
        - CPU/memory thresholds breached
        - Queue depth too high
        - Integration health degraded
        """
        if severity == "critical":
            title = "🚨 Critical Alert"
        elif severity == "warning":
            title = "⚠️ Warning"
        else:
            title = "ℹ️ Info"

        body = message

        return await self.send_notification(
            user_id=user_id,
            notification_type="system_alert",
            title=title,
            body=body,
            data={
                "alert_type": alert_type,
                "severity": severity
            },
            priority=severity
        )


# Singleton helper
def get_push_notification_service(db: Session) -> PushNotificationService:
    """Get or create push notification service instance."""
    return PushNotificationService(db)
