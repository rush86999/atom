"""
Workflow Notifier - Phase 31
Sends Slack/Email notifications on workflow completion/failure.
Includes user-configurable notification settings.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    SLACK = "slack"
    EMAIL = "email"

@dataclass
class NotificationSettings:
    """User-configurable notification settings for a workflow"""
    enabled: bool = True
    notify_on_success: bool = True
    notify_on_failure: bool = True
    
    # Slack settings
    slack_enabled: bool = True
    slack_channel: str = ""  # Blank means use default from env
    slack_mention_users: List[str] = field(default_factory=list)  # e.g., ["U12345", "U67890"]
    
    # Email settings
    email_enabled: bool = False
    email_recipients: List[str] = field(default_factory=list)  # e.g., ["user@example.com"]
    
    # Message customization
    custom_success_message: Optional[str] = None
    custom_failure_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

# Global settings store (in production, use database)
_notification_settings_store: Dict[str, NotificationSettings] = {}

def get_notification_settings(workflow_id: str) -> NotificationSettings:
    """Get notification settings for a workflow, or default if not set"""
    return _notification_settings_store.get(workflow_id, NotificationSettings())

def set_notification_settings(workflow_id: str, settings: NotificationSettings):
    """Save notification settings for a workflow"""
    _notification_settings_store[workflow_id] = settings

class WorkflowNotifier:
    """
    Handles sending notifications when workflows complete or fail.
    Integrates with existing Slack and Email services.
    """
    
    def __init__(self):
        self.default_slack_channel = os.getenv("WORKFLOW_SLACK_CHANNEL", "#workflow-alerts")
        self.slack_token = os.getenv("WORKFLOW_SLACK_TOKEN") or os.getenv("SLACK_BOT_TOKEN")
        self.slack_service = None
        
        # Initialize Slack service if available
        try:
            from integrations.slack_service_unified import SlackUnifiedService
            self.slack_service = SlackUnifiedService()
            logger.info("WorkflowNotifier: Slack service initialized")
        except ImportError:
            logger.warning("WorkflowNotifier: Slack service not available")
    
    async def notify_completion(
        self,
        workflow_id: str,
        workflow_name: str,
        execution_id: str,
        results: Dict[str, Any],
        settings: Optional[NotificationSettings] = None
    ):
        """Send notification when a workflow completes successfully"""
        settings = settings or get_notification_settings(workflow_id)
        
        if not settings.enabled or not settings.notify_on_success:
            logger.info(f"Notifications disabled for workflow {workflow_id}")
            return
        
        # Build message
        message = settings.custom_success_message or (
            f"✅ *Workflow Completed*\n"
            f"• Name: `{workflow_name}`\n"
            f"• Execution ID: `{execution_id}`\n"
            f"• Steps Completed: {len(results)}"
        )
        
        # Add mentions
        if settings.slack_mention_users:
            mentions = " ".join([f"<@{uid}>" for uid in settings.slack_mention_users])
            message = f"{mentions}\n{message}"
        
        # Send Slack notification
        if settings.slack_enabled:
            await self._send_slack(settings.slack_channel or self.default_slack_channel, message)
        
        # Send Email notification
        if settings.email_enabled and settings.email_recipients:
            await self._send_email(
                recipients=settings.email_recipients,
                subject=f"✅ Workflow Complete: {workflow_name}",
                body=message.replace("*", "").replace("`", "")  # Strip markdown
            )
    
    async def notify_failure(
        self,
        workflow_id: str,
        workflow_name: str,
        execution_id: str,
        error: str,
        settings: Optional[NotificationSettings] = None
    ):
        """Send notification when a workflow fails"""
        settings = settings or get_notification_settings(workflow_id)
        
        if not settings.enabled or not settings.notify_on_failure:
            logger.info(f"Failure notifications disabled for workflow {workflow_id}")
            return
        
        # Build message
        message = settings.custom_failure_message or (
            f"❌ *Workflow Failed*\n"
            f"• Name: `{workflow_name}`\n"
            f"• Execution ID: `{execution_id}`\n"
            f"• Error: {error}"
        )
        
        # Add mentions (always mention on failure)
        if settings.slack_mention_users:
            mentions = " ".join([f"<@{uid}>" for uid in settings.slack_mention_users])
            message = f"{mentions}\n{message}"
        
        # Send Slack notification
        if settings.slack_enabled:
            await self._send_slack(settings.slack_channel or self.default_slack_channel, message)
        
        # Send Email notification
        if settings.email_enabled and settings.email_recipients:
            await self._send_email(
                recipients=settings.email_recipients,
                subject=f"❌ Workflow Failed: {workflow_name}",
                body=message.replace("*", "").replace("`", "")
            )
    
    async def _send_slack(self, channel: str, message: str):
        """Send Slack message using unified service"""
        if not self.slack_service or not self.slack_token:
            logger.warning("Slack not configured, skipping notification")
            return
        
        try:
            # Find channel ID if given a name
            channel_id = channel
            if channel.startswith("#"):
                # Would need to look up channel ID from name - simplified for now
                logger.info(f"Would send to Slack channel {channel}: {message[:100]}...")
                return
            
            result = await self.slack_service.post_message(
                token=self.slack_token,
                channel_id=channel_id,
                text=message
            )
            logger.info(f"Slack notification sent to {channel}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
    
    async def _send_email(self, recipients: List[str], subject: str, body: str):
        """Send email notification using SendGrid service"""
        try:
            from integrations.sendgrid_routes import sendgrid_service

            # Send to each recipient
            for recipient in recipients:
                result = await sendgrid_service.send_email(
                    to=recipient,
                    subject=subject,
                    content=body
                )
                logger.info(f"Email sent successfully to {recipient}: {result}")

        except ImportError:
            logger.warning("SendGrid service not available, using fallback")
            logger.info(f"EMAIL (not sent): To: {recipients}, Subject: {subject}, Body: {body[:100]}...")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            # Fallback: Log the email for debugging
            logger.info(f"EMAIL (not sent): To: {recipients}, Subject: {subject}, Body: {body[:100]}...")

# Global notifier instance
notifier = WorkflowNotifier()
