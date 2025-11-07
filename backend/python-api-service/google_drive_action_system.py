"""
Google Drive Action System
Provides standardized action execution, notifications, and integrations
"""

import os
import json
import asyncio
import logging
import smtplib
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Local imports
from loguru import logger
from config import get_config_instance
from extensions import redis_client

# Try to import required services
try:
    from google_drive_service import get_google_drive_service
    from google_drive_memory import get_google_drive_memory_service
    from ingestion_pipeline.content_extractor import get_content_extractor
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive services not available")

class ActionStatus(Enum):
    """Action execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"

class NotificationType(Enum):
    """Notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    ACTION_SUCCESS = "action_success"
    ACTION_FAILED = "action_failed"

@dataclass
class NotificationMessage:
    """Notification message data model"""
    notification_id: str
    type: NotificationType
    title: str
    message: str
    recipients: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"  # low, normal, high, urgent
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "google_drive_automation"
    delivery_method: str = "webhook"  # webhook, email, slack, teams, etc.
    delivered: bool = False
    delivery_attempts: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "notification_id": self.notification_id,
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "recipients": self.recipients,
            "data": self.data,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "delivery_method": self.delivery_method,
            "delivered": self.delivered,
            "delivery_attempts": self.delivery_attempts,
            "error_message": self.error_message
        }

@dataclass
class ActionContext:
    """Action execution context"""
    execution_id: str
    workflow_id: str
    action_type: str
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    previous_results: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    user_context: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "action_type": self.action_type,
            "trigger_data": self.trigger_data,
            "previous_results": self.previous_results,
            "environment": self.environment,
            "user_context": self.user_context,
            "start_time": self.start_time.isoformat()
        }

@dataclass
class ActionResult:
    """Action execution result"""
    action_id: str
    status: ActionStatus
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "action_id": self.action_id,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat()
        }

class GoogleDriveActionSystem:
    """Google Drive Action System"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.automation_config = self.config.automation
        
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError("Google Drive services not available")
        
        # Action storage
        self.action_history: List[ActionResult] = []
        self.pending_notifications: Dict[str, NotificationMessage] = {}
        
        # Configuration
        self.max_action_history = self.automation_config.max_action_history
        self.notification_timeout = self.automation_config.notification_timeout
        self.script_timeout = self.automation_config.script_timeout
        
        # Email configuration
        self.smtp_config = self.config.smtp if hasattr(self.config, 'smtp') else None
        
        # Webhook configuration
        self.webhook_config = self.automation_config.webhook_config
        
        # Integration configurations
        self.slack_config = self.automation_config.slack_config
        self.teams_config = self.automation_config.teams_config
        
        logger.info("Google Drive Action System initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.load_notifications()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.save_notifications()
    
    # ==================== FILE OPERATIONS ====================
    
    async def copy_file_to_multiple_locations(self,
                                           context: ActionContext,
                                           file_id: str,
                                           target_locations: List[Dict[str, Any]],
                                           new_name_pattern: Optional[str] = None) -> ActionResult:
        """Copy file to multiple locations"""
        
        try:
            start_time = datetime.utcnow()
            
            # Get Google Drive service
            drive_service = await get_google_drive_service()
            if not drive_service:
                return ActionResult(
                    action_id=f"copy_file_{context.execution_id}",
                    status=ActionStatus.FAILED,
                    success=False,
                    message="Google Drive service not available",
                    error="Service unavailable"
                )
            
            # Get file info
            file_result = await drive_service.get_file(file_id)
            if not file_result["success"]:
                return ActionResult(
                    action_id=f"copy_file_{context.execution_id}",
                    status=ActionStatus.FAILED,
                    success=False,
                    message=f"Failed to get file info: {file_result.get('error')}",
                    error=file_result.get('error')
                )
            
            file_data = file_result["file"]
            original_name = file_data["name"]
            
            # Copy to each location
            copy_results = []
            for i, location in enumerate(target_locations):
                try:
                    # Generate new name if pattern provided
                    new_name = original_name
                    if new_name_pattern:
                        new_name = self._substitute_name_pattern(
                            new_name_pattern, 
                            file_data, 
                            context, 
                            location
                        )
                    
                    # Download file temporarily
                    import tempfile
                    temp_path = None
                    
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{original_name}") as temp_file:
                            temp_path = temp_file.name
                        
                        # Download file
                        download_result = await drive_service.download_file(file_id, temp_path)
                        if not download_result["success"]:
                            copy_results.append({
                                "location": location,
                                "success": False,
                                "error": download_result.get('error')
                            })
                            continue
                        
                        # Upload to target location
                        upload_result = await drive_service.upload_file(
                            file_path=temp_path,
                            file_name=new_name,
                            parent_id=location.get("folder_id")
                        )
                        
                        copy_results.append({
                            "location": location,
                            "success": upload_result["success"],
                            "file_id": upload_result.get("file", {}).get("id") if upload_result["success"] else None,
                            "file_name": new_name,
                            "error": upload_result.get('error') if not upload_result["success"] else None
                        })
                    
                    finally:
                        # Clean up temp file
                        if temp_path and os.path.exists(temp_path):
                            os.unlink(temp_path)
                
                except Exception as e:
                    logger.error(f"Failed to copy to location {i}: {e}")
                    copy_results.append({
                        "location": location,
                        "success": False,
                        "error": str(e)
                    })
            
            # Calculate results
            successful_copies = [r for r in copy_results if r["success"]]
            failed_copies = [r for r in copy_results if not r["success"]]
            
            success = len(successful_copies) > 0
            message = f"Copied file to {len(successful_copies)} locations"
            
            if failed_copies:
                message += f", failed to copy to {len(failed_copies)} locations"
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ActionResult(
                action_id=f"copy_file_{context.execution_id}",
                status=ActionStatus.COMPLETED if success else ActionStatus.FAILED,
                success=success,
                message=message,
                data={
                    "original_file_id": file_id,
                    "original_file_name": original_name,
                    "target_locations": target_locations,
                    "copy_results": copy_results,
                    "successful_count": len(successful_copies),
                    "failed_count": len(failed_copies)
                },
                output=json.dumps(copy_results, indent=2),
                error=None if success else f"Failed to copy to {len(failed_copies)} locations",
                execution_time=execution_time
            )
        
        except Exception as e:
            logger.error(f"Copy file action failed: {e}")
            return ActionResult(
                action_id=f"copy_file_{context.execution_id}",
                status=ActionStatus.FAILED,
                success=False,
                message=f"Copy file action failed: {str(e)}",
                error=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    # ==================== NOTIFICATIONS ====================
    
    async def send_notification(self,
                             context: ActionContext,
                             notification_type: NotificationType,
                             title: str,
                             message: str,
                             recipients: List[str],
                             delivery_methods: List[str] = None,
                             priority: str = "normal") -> ActionResult:
        """Send notification via multiple delivery methods"""
        
        try:
            start_time = datetime.utcnow()
            
            if delivery_methods is None:
                delivery_methods = ["webhook", "email"]
            
            # Create notification message
            notification_id = str(uuid.uuid4())
            notification = NotificationMessage(
                notification_id=notification_id,
                type=notification_type,
                title=title,
                message=message,
                recipients=recipients,
                priority=priority,
                delivery_method=",".join(delivery_methods),
                data={
                    "context": context.to_dict(),
                    "workflow_id": context.workflow_id,
                    "execution_id": context.execution_id
                }
            )
            
            # Send via each delivery method
            delivery_results = []
            
            for method in delivery_methods:
                try:
                    if method == "email":
                        result = await self._send_email_notification(notification)
                    elif method == "slack":
                        result = await self._send_slack_notification(notification)
                    elif method == "teams":
                        result = await self._send_teams_notification(notification)
                    elif method == "webhook":
                        result = await self._send_webhook_notification(notification)
                    else:
                        result = {
                            "success": False,
                            "error": f"Unsupported delivery method: {method}"
                        }
                    
                    delivery_results.append({
                        "method": method,
                        "result": result
                    })
                
                except Exception as e:
                    logger.error(f"Failed to send notification via {method}: {e}")
                    delivery_results.append({
                        "method": method,
                        "success": False,
                        "error": str(e)
                    })
            
            # Calculate overall success
            successful_deliveries = [r for r in delivery_results if r["result"].get("success", False)]
            success = len(successful_deliveries) > 0
            
            notification.delivered = success
            notification.delivery_attempts = len(delivery_results)
            
            # Store notification
            self.pending_notifications[notification_id] = notification
            await self.save_notifications()
            
            message = f"Notification sent via {len(successful_deliveries)}/{len(delivery_results)} methods"
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ActionResult(
                action_id=f"send_notification_{context.execution_id}",
                status=ActionStatus.COMPLETED if success else ActionStatus.FAILED,
                success=success,
                message=message,
                data={
                    "notification_id": notification_id,
                    "notification_type": notification_type.value,
                    "title": title,
                    "recipients": recipients,
                    "delivery_methods": delivery_methods,
                    "delivery_results": delivery_results,
                    "successful_deliveries": len(successful_deliveries),
                    "priority": priority
                },
                output=json.dumps(delivery_results, indent=2),
                error=None if success else "Failed to deliver notification",
                execution_time=execution_time
            )
        
        except Exception as e:
            logger.error(f"Send notification action failed: {e}")
            return ActionResult(
                action_id=f"send_notification_{context.execution_id}",
                status=ActionStatus.FAILED,
                success=False,
                message=f"Send notification action failed: {str(e)}",
                error=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def _send_email_notification(self, notification: NotificationMessage) -> Dict[str, Any]:
        """Send email notification"""
        
        try:
            if not self.smtp_config:
                return {
                    "success": False,
                    "error": "SMTP configuration not available"
                }
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config.from_address
            msg['To'] = ", ".join(notification.recipients)
            msg['Subject'] = f"[{notification.type.value.upper()}] {notification.title}"
            
            # Create email body
            html_body = f"""
            <html>
            <body>
                <h2 style="color: {self._get_notification_color(notification.type)}">{notification.title}</h2>
                <p>{notification.message}</p>
                
                <h3>Details:</h3>
                <ul>
                    <li><strong>Type:</strong> {notification.type.value}</li>
                    <li><strong>Priority:</strong> {notification.priority}</li>
                    <li><strong>Source:</strong> {notification.source}</li>
                    <li><strong>Timestamp:</strong> {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>
                
                {self._format_notification_data(notification.data)}
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_config.host, self.smtp_config.port) as server:
                if self.smtp_config.use_tls:
                    server.starttls()
                
                if self.smtp_config.username and self.smtp_config.password:
                    server.login(self.smtp_config.username, self.smtp_config.password)
                
                text = msg.as_string()
                server.sendmail(self.smtp_config.from_address, notification.recipients, text)
            
            logger.info(f"Email notification sent to {len(notification.recipients)} recipients")
            
            return {
                "success": True,
                "recipients": notification.recipients,
                "subject": msg['Subject']
            }
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_slack_notification(self, notification: NotificationMessage) -> Dict[str, Any]:
        """Send Slack notification"""
        
        try:
            if not self.slack_config or not self.slack_config.webhook_url:
                return {
                    "success": False,
                    "error": "Slack configuration not available"
                }
            
            # Create Slack message
            color = self._get_slack_color(notification.type)
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": notification.title,
                        "text": notification.message,
                        "fields": [
                            {
                                "title": "Type",
                                "value": notification.type.value,
                                "short": True
                            },
                            {
                                "title": "Priority",
                                "value": notification.priority,
                                "short": True
                            },
                            {
                                "title": "Source",
                                "value": notification.source,
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": notification.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                "short": True
                            }
                        ],
                        "footer": "ATOM Google Drive Automation",
                        "ts": int(notification.timestamp.timestamp())
                    }
                ]
            }
            
            # Add context data if available
            if notification.data.get("context"):
                context_data = notification.data["context"]
                payload["attachments"][0]["fields"].append({
                    "title": "Context",
                    "value": f"Workflow: {context_data.get('workflow_id')}\nExecution: {context_data.get('execution_id')}",
                    "short": False
                })
            
            # Send to Slack
            response = requests.post(
                self.slack_config.webhook_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Slack notification sent successfully")
                return {
                    "success": True,
                    "response": response.text
                }
            else:
                logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_teams_notification(self, notification: NotificationMessage) -> Dict[str, Any]:
        """Send Microsoft Teams notification"""
        
        try:
            if not self.teams_config or not self.teams_config.webhook_url:
                return {
                    "success": False,
                    "error": "Teams configuration not available"
                }
            
            # Create Teams message
            theme_color = self._get_teams_color(notification.type)
            
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": theme_color,
                "summary": notification.title,
                "sections": [
                    {
                        "activityTitle": notification.title,
                        "activitySubtitle": notification.message,
                        "facts": [
                            {
                                "name": "Type",
                                "value": notification.type.value
                            },
                            {
                                "name": "Priority",
                                "value": notification.priority
                            },
                            {
                                "name": "Source",
                                "value": notification.source
                            },
                            {
                                "name": "Timestamp",
                                "value": notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                            }
                        ],
                        "markdown": True
                    }
                ],
                "potentialAction": [
                    {
                        "@type": "OpenUri",
                        "name": "View in Google Drive",
                        "targets": [
                            {
                                "os": "default",
                                "uri": "https://drive.google.com"
                            }
                        ]
                    }
                ]
            }
            
            # Send to Teams
            response = requests.post(
                self.teams_config.webhook_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Teams notification sent successfully")
                return {
                    "success": True,
                    "response": response.text
                }
            else:
                logger.error(f"Teams notification failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_webhook_notification(self, notification: NotificationMessage) -> Dict[str, Any]:
        """Send generic webhook notification"""
        
        try:
            if not self.webhook_config or not self.webhook_config.url:
                return {
                    "success": False,
                    "error": "Webhook configuration not available"
                }
            
            # Create webhook payload
            payload = {
                "notification_id": notification.notification_id,
                "type": notification.type.value,
                "title": notification.title,
                "message": notification.message,
                "recipients": notification.recipients,
                "priority": notification.priority,
                "source": notification.source,
                "timestamp": notification.timestamp.isoformat(),
                "data": notification.data
            }
            
            # Add headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ATOM-GoogleDrive-Automation/1.0"
            }
            
            # Add custom headers
            if self.webhook_config.headers:
                headers.update(self.webhook_config.headers)
            
            # Add authentication
            auth = None
            if self.webhook_config.auth_type == "bearer":
                headers["Authorization"] = f"Bearer {self.webhook_config.auth_token}"
            elif self.webhook_config.auth_type == "basic":
                auth = (self.webhook_config.auth_username, self.webhook_config.auth_password)
            
            # Send webhook
            response = requests.post(
                self.webhook_config.url,
                json=payload,
                headers=headers,
                auth=auth,
                timeout=30
            )
            
            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook notification sent successfully")
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": response.text
                }
            else:
                logger.error(f"Webhook notification failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== CONTENT PROCESSING ====================
    
    async def process_content_batch(self,
                                   context: ActionContext,
                                   file_ids: List[str],
                                   processing_options: Dict[str, Any]) -> ActionResult:
        """Process content for multiple files in batch"""
        
        try:
            start_time = datetime.utcnow()
            
            # Get services
            content_extractor = await get_content_extractor()
            memory_service = await get_google_drive_memory_service()
            drive_service = await get_google_drive_service()
            
            if not content_extractor or not memory_service:
                return ActionResult(
                    action_id=f"process_content_batch_{context.execution_id}",
                    status=ActionStatus.FAILED,
                    success=False,
                    message="Required services not available",
                    error="Services unavailable"
                )
            
            # Process each file
            processing_results = []
            
            for file_id in file_ids:
                try:
                    # Get file info
                    file_result = await drive_service.get_file(file_id) if drive_service else None
                    file_data = file_result["file"] if file_result else {"name": "Unknown", "id": file_id}
                    
                    # Download file
                    if drive_service:
                        import tempfile
                        temp_path = None
                        
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_data['name']}") as temp_file:
                                temp_path = temp_file.name
                            
                            download_result = await drive_service.download_file(file_id, temp_path)
                            if not download_result["success"]:
                                processing_results.append({
                                    "file_id": file_id,
                                    "file_name": file_data["name"],
                                    "success": False,
                                    "error": f"Failed to download: {download_result.get('error')}"
                                })
                                continue
                            
                            # Extract content
                            extracted_content = await content_extractor.extract_content(
                                file_id=file_id,
                                file_path=temp_path,
                                file_name=file_data["name"]
                            )
                            
                            if not extracted_content.success:
                                processing_results.append({
                                    "file_id": file_id,
                                    "file_name": file_data["name"],
                                    "success": False,
                                    "error": f"Content extraction failed: {extracted_content.error_message}"
                                })
                                continue
                            
                            # Generate embeddings if requested
                            embedding_result = None
                            if processing_options.get("generate_embeddings", True):
                                embedding_result = await memory_service.store_embedding(
                                    file_id=file_id,
                                    text=extracted_content.text_content,
                                    metadata={
                                        "file_name": file_data["name"],
                                        "file_size": file_data.get("size", 0),
                                        "mime_type": file_data.get("mime_type", ""),
                                        "extraction_method": extracted_content.extraction_method,
                                        "word_count": extracted_content.word_count,
                                        "processing_options": processing_options
                                    }
                                )
                            
                            processing_results.append({
                                "file_id": file_id,
                                "file_name": file_data["name"],
                                "success": True,
                                "extraction_result": extracted_content.to_dict(),
                                "embedding_result": embedding_result,
                                "processing_time": extracted_content.processing_time
                            })
                        
                        finally:
                            # Clean up temp file
                            if temp_path and os.path.exists(temp_path):
                                os.unlink(temp_path)
                    
                    else:
                        # Skip download, process file_id only
                        text_content = f"Processing file: {file_id}"
                        if processing_options.get("generate_embeddings", True):
                            embedding_result = await memory_service.store_embedding(
                                file_id=file_id,
                                text=text_content,
                                metadata={"processing_method": "batch_processing"}
                            )
                        
                        processing_results.append({
                            "file_id": file_id,
                            "success": True,
                            "text_content": text_content,
                            "embedding_result": embedding_result
                        })
                
                except Exception as e:
                    logger.error(f"Failed to process file {file_id}: {e}")
                    processing_results.append({
                        "file_id": file_id,
                        "success": False,
                        "error": str(e)
                    })
            
            # Calculate results
            successful_processing = [r for r in processing_results if r["success"]]
            failed_processing = [r for r in processing_results if not r["success"]]
            
            success = len(successful_processing) > 0
            message = f"Processed {len(successful_processing)} files successfully"
            
            if failed_processing:
                message += f", failed to process {len(failed_processing)} files"
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ActionResult(
                action_id=f"process_content_batch_{context.execution_id}",
                status=ActionStatus.COMPLETED if success else ActionStatus.FAILED,
                success=success,
                message=message,
                data={
                    "total_files": len(file_ids),
                    "successful_count": len(successful_processing),
                    "failed_count": len(failed_processing),
                    "processing_results": processing_results,
                    "processing_options": processing_options
                },
                output=json.dumps(processing_results, indent=2),
                error=None if success else f"Failed to process {len(failed_processing)} files",
                execution_time=execution_time
            )
        
        except Exception as e:
            logger.error(f"Content batch processing failed: {e}")
            return ActionResult(
                action_id=f"process_content_batch_{context.execution_id}",
                status=ActionStatus.FAILED,
                success=False,
                message=f"Content batch processing failed: {str(e)}",
                error=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    # ==================== CUSTOM SCRIPTS ====================
    
    async def execute_custom_script(self,
                                   context: ActionContext,
                                   script_path: str,
                                   script_args: Dict[str, Any] = None,
                                   working_directory: Optional[str] = None) -> ActionResult:
        """Execute custom script"""
        
        try:
            start_time = datetime.utcnow()
            
            if script_args is None:
                script_args = {}
            
            # Check if script exists
            script_file = Path(script_path)
            if not script_file.exists():
                return ActionResult(
                    action_id=f"execute_script_{context.execution_id}",
                    status=ActionStatus.FAILED,
                    success=False,
                    message=f"Script not found: {script_path}",
                    error="Script not found"
                )
            
            # Prepare script environment
            env = os.environ.copy()
            env.update({
                "ATOM_EXECUTION_ID": context.execution_id,
                "ATOM_WORKFLOW_ID": context.workflow_id,
                "ATOM_ACTION_TYPE": context.action_type,
                "ATOM_TRIGGER_DATA": json.dumps(context.trigger_data),
                "ATOM_PREVIOUS_RESULTS": json.dumps(context.previous_results),
                "ATOM_USER_CONTEXT": json.dumps(context.user_context),
                "ATOM_TIMESTAMP": context.start_time.isoformat()
            })
            
            # Add script args to environment
            for key, value in script_args.items():
                env[f"ATOM_ARG_{key.upper()}"] = str(value)
            
            # Determine working directory
            work_dir = working_directory or script_file.parent
            
            # Execute script
            try:
                process = subprocess.run(
                    [str(script_file)],
                    env=env,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.script_timeout
                )
                
                # Parse results
                success = process.returncode == 0
                output = process.stdout
                error = process.stderr if process.stderr else None
                
                # Try to parse JSON output
                try:
                    output_data = json.loads(output) if output and output.strip().startswith('{') else output
                except json.JSONDecodeError:
                    output_data = output
                
                message = "Script executed successfully" if success else "Script execution failed"
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                return ActionResult(
                    action_id=f"execute_script_{context.execution_id}",
                    status=ActionStatus.COMPLETED if success else ActionStatus.FAILED,
                    success=success,
                    message=message,
                    data={
                        "script_path": script_path,
                        "working_directory": work_dir,
                        "script_args": script_args,
                        "return_code": process.returncode,
                        "output": output_data,
                        "error": error
                    },
                    output=output,
                    error=error,
                    execution_time=execution_time
                )
            
            except subprocess.TimeoutExpired:
                return ActionResult(
                    action_id=f"execute_script_{context.execution_id}",
                    status=ActionStatus.TIMEOUT,
                    success=False,
                    message=f"Script execution timed out after {self.script_timeout} seconds",
                    error="Script timeout",
                    execution_time=(datetime.utcnow() - start_time).total_seconds()
                )
        
        except Exception as e:
            logger.error(f"Custom script execution failed: {e}")
            return ActionResult(
                action_id=f"execute_script_{context.execution_id}",
                status=ActionStatus.FAILED,
                success=False,
                message=f"Custom script execution failed: {str(e)}",
                error=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    # ==================== UTILITY METHODS ====================
    
    def _substitute_name_pattern(self,
                                 pattern: str,
                                 file_data: Dict[str, Any],
                                 context: ActionContext,
                                 location: Dict[str, Any]) -> str:
        """Substitute variables in name pattern"""
        
        try:
            # Basic substitutions
            substitutions = {
                "{original_name}": file_data.get("name", ""),
                "{file_id}": file_data.get("id", ""),
                "{file_extension}": file_data.get("file_extension", ""),
                "{mime_type}": file_data.get("mime_type", ""),
                "{workflow_id}": context.workflow_id,
                "{execution_id}": context.execution_id,
                "{timestamp}": context.start_time.strftime("%Y%m%d_%H%M%S"),
                "{date}": context.start_time.strftime("%Y-%m-%d"),
                "{time}": context.start_time.strftime("%H-%M-%S"),
                "{location_name}": location.get("name", ""),
                "{location_id}": location.get("id", "")
            }
            
            # Apply substitutions
            result = pattern
            for placeholder, value in substitutions.items():
                result = result.replace(placeholder, str(value))
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to substitute name pattern: {e}")
            return pattern
    
    def _get_notification_color(self, notification_type: NotificationType) -> str:
        """Get color for notification type"""
        
        colors = {
            NotificationType.INFO: "#3498db",
            NotificationType.SUCCESS: "#2ecc71",
            NotificationType.WARNING: "#f39c12",
            NotificationType.ERROR: "#e74c3c",
            NotificationType.WORKFLOW_STARTED: "#3498db",
            NotificationType.WORKFLOW_COMPLETED: "#2ecc71",
            NotificationType.WORKFLOW_FAILED: "#e74c3c",
            NotificationType.ACTION_SUCCESS: "#2ecc71",
            NotificationType.ACTION_FAILED: "#e74c3c"
        }
        
        return colors.get(notification_type, "#3498db")
    
    def _get_slack_color(self, notification_type: NotificationType) -> str:
        """Get Slack color for notification type"""
        
        colors = {
            NotificationType.INFO: "good",
            NotificationType.SUCCESS: "good",
            NotificationType.WARNING: "warning",
            NotificationType.ERROR: "danger",
            NotificationType.WORKFLOW_STARTED: "good",
            NotificationType.WORKFLOW_COMPLETED: "good",
            NotificationType.WORKFLOW_FAILED: "danger",
            NotificationType.ACTION_SUCCESS: "good",
            NotificationType.ACTION_FAILED: "danger"
        }
        
        return colors.get(notification_type, "good")
    
    def _get_teams_color(self, notification_type: NotificationType) -> str:
        """Get Teams color for notification type"""
        
        colors = {
            NotificationType.INFO: "0080FF",
            NotificationType.SUCCESS: "00FF00",
            NotificationType.WARNING: "FFFF00",
            NotificationType.ERROR: "FF0000",
            NotificationType.WORKFLOW_STARTED: "0080FF",
            NotificationType.WORKFLOW_COMPLETED: "00FF00",
            NotificationType.WORKFLOW_FAILED: "FF0000",
            NotificationType.ACTION_SUCCESS: "00FF00",
            NotificationType.ACTION_FAILED: "FF0000"
        }
        
        return colors.get(notification_type, "0080FF")
    
    def _format_notification_data(self, data: Dict[str, Any]) -> str:
        """Format notification data for HTML"""
        
        try:
            if not data:
                return ""
            
            html_parts = ["<h3>Additional Data:</h3><ul>"]
            
            for key, value in data.items():
                if isinstance(value, dict):
                    html_parts.append(f"<li><strong>{key}:</strong> <pre>{json.dumps(value, indent=2)}</pre></li>")
                else:
                    html_parts.append(f"<li><strong>{key}:</strong> {str(value)}</li>")
            
            html_parts.append("</ul>")
            
            return "".join(html_parts)
        
        except Exception as e:
            logger.error(f"Failed to format notification data: {e}")
            return ""
    
    # ==================== STORAGE ====================
    
    async def save_notifications(self):
        """Save pending notifications to storage"""
        
        try:
            # This would integrate with your database
            # For now, save to Redis
            if redis_client:
                notifications_data = {
                    notification_id: notification.to_dict() 
                    for notification_id, notification in self.pending_notifications.items()
                }
                
                await redis_client.setex(
                    f"atom:google_drive:notifications",
                    86400 * 7,  # 7 days
                    json.dumps(notifications_data, default=str)
                )
            
            logger.debug(f"Saved {len(self.pending_notifications)} notifications")
        
        except Exception as e:
            logger.error(f"Failed to save notifications: {e}")
    
    async def load_notifications(self):
        """Load pending notifications from storage"""
        
        try:
            # This would integrate with your database
            # For now, load from Redis
            if redis_client:
                notifications_data = await redis_client.get(f"atom:google_drive:notifications")
                
                if notifications_data:
                    notifications_dict = json.loads(notifications_data)
                    
                    for notification_id, notification_data in notifications_dict.items():
                        notification = NotificationMessage(
                            notification_id=notification_data["notification_id"],
                            type=NotificationType(notification_data["type"]),
                            title=notification_data["title"],
                            message=notification_data["message"],
                            recipients=notification_data["recipients"],
                            priority=notification_data["priority"],
                            delivery_method=notification_data["delivery_method"],
                            delivered=notification_data["delivered"],
                            delivery_attempts=notification_data["delivery_attempts"],
                            error_message=notification_data["error_message"],
                            timestamp=datetime.fromisoformat(notification_data["timestamp"]),
                            source=notification_data["source"],
                            data=notification_data["data"]
                        )
                        
                        self.pending_notifications[notification_id] = notification
            
            logger.info(f"Loaded {len(self.pending_notifications)} notifications")
        
        except Exception as e:
            logger.error(f"Failed to load notifications: {e}")
    
    # ==================== STATISTICS ====================
    
    def get_action_stats(self) -> Dict[str, Any]:
        """Get action execution statistics"""
        
        try:
            if not self.action_history:
                return {
                    "total_actions": 0,
                    "successful_actions": 0,
                    "failed_actions": 0,
                    "success_rate": 0.0,
                    "average_execution_time": 0.0
                }
            
            total = len(self.action_history)
            successful = len([action for action in self.action_history if action.success])
            failed = len([action for action in self.action_history if not action.success])
            
            success_rate = (successful / total) * 100 if total > 0 else 0
            
            execution_times = [action.execution_time for action in self.action_history if action.execution_time]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            return {
                "total_actions": total,
                "successful_actions": successful,
                "failed_actions": failed,
                "success_rate": success_rate,
                "average_execution_time": avg_execution_time,
                "pending_notifications": len(self.pending_notifications),
                "max_history": self.max_action_history,
                "current_history": len(self.action_history)
            }
        
        except Exception as e:
            logger.error(f"Failed to get action stats: {e}")
            return {}
    
    def get_recent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent actions"""
        
        try:
            # Sort by created_at (most recent first)
            recent_actions = sorted(
                self.action_history,
                key=lambda action: action.created_at,
                reverse=True
            )
            
            return [action.to_dict() for action in recent_actions[:limit]]
        
        except Exception as e:
            logger.error(f"Failed to get recent actions: {e}")
            return []

# Global action system instance
_action_system: Optional[GoogleDriveActionSystem] = None

async def get_google_drive_action_system() -> Optional[GoogleDriveActionSystem]:
    """Get global Google Drive action system instance"""
    
    global _action_system
    
    if _action_system is None:
        try:
            config = get_config_instance()
            _action_system = GoogleDriveActionSystem(config)
            await _action_system.load_notifications()
            logger.info("Google Drive Action System created")
        except Exception as e:
            logger.error(f"Failed to create Google Drive Action System: {e}")
            _action_system = None
    
    return _action_system

def clear_google_drive_action_system():
    """Clear global action system instance"""
    
    global _action_system
    _action_system = None
    logger.info("Google Drive Action System cleared")

# Export classes and functions
__all__ = [
    'GoogleDriveActionSystem',
    'NotificationMessage',
    'NotificationType',
    'ActionContext',
    'ActionResult',
    'ActionStatus',
    'get_google_drive_action_system',
    'clear_google_drive_action_system'
]