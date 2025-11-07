"""
Google Drive Trigger System
Handles webhook triggers, file change notifications, and scheduled triggers
"""

import os
import json
import asyncio
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
from contextlib import asynccontextmanager
from enum import Enum
from urllib.parse import parse_qs

# Flask imports
from flask import Flask, request, jsonify

# Local imports
from loguru import logger
from config import get_config_instance
from extensions import redis_client
from google_drive_automation_engine import get_automation_engine, TriggerType

# Try to import required services
try:
    from google_drive_service import get_google_drive_service
    from google_drive_auth import get_google_drive_auth
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive services not available")

class TriggerEventType(Enum):
    """Trigger event types"""
    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    FILE_SHARED = "file_shared"
    FILE_UNSHARED = "file_unshared"
    FILE_MOVED = "file_moved"
    FILE_RENAMED = "file_renamed"
    FOLDER_CREATED = "folder_created"
    FOLDER_DELETED = "folder_deleted"
    PERMISSION_CHANGED = "permission_changed"
    METADATA_CHANGED = "metadata_changed"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    SYNC_ERROR = "sync_error"

@dataclass
class TriggerEvent:
    """Trigger event data model"""
    event_id: str
    event_type: TriggerEventType
    resource_id: str
    resource_type: str
    user_id: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    processing_attempts: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "processed": self.processed,
            "processing_attempts": self.processing_attempts,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TriggerEvent':
        """Create from dictionary"""
        return cls(
            event_id=data["event_id"],
            event_type=TriggerEventType(data["event_type"]),
            resource_id=data["resource_id"],
            resource_type=data["resource_type"],
            user_id=data["user_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data.get("data", {}),
            processed=data.get("processed", False),
            processing_attempts=data.get("processing_attempts", 0),
            error_message=data.get("error_message")
        )

@dataclass
class WebhookSubscription:
    """Webhook subscription data model"""
    subscription_id: str
    channel_id: str
    channel_type: str  # "web_address", "push"
    address: str  # webhook URL
    resource_id: str  # file ID, folder ID, or "root"
    resource_type: str  # "file", "folder"
    expiration: Optional[datetime] = None
    state: str = "active"  # "active", "expired", "suspended"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "subscription_id": self.subscription_id,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "address": self.address,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class GoogleDriveTriggerSystem:
    """Google Drive Trigger System"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.sync_config = self.config.sync
        
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError("Google Drive services not available")
        
        # Trigger storage
        self.pending_events: Dict[str, TriggerEvent] = {}
        self.processed_events: Dict[str, TriggerEvent] = {}
        self.webhook_subscriptions: Dict[str, WebhookSubscription] = {}
        
        # Event processing
        self.event_processors: Dict[TriggerEventType, Callable] = {}
        self._register_event_processors()
        
        # Webhook security
        self.webhook_secret = self.config.google_drive.webhook_secret
        
        # Event retention
        self.event_retention_days = self.sync_config.sync_event_retention_days
        
        # Background processing
        self._background_tasks: List[asyncio.Task] = []
        self._processing_enabled = True
        
        logger.info("Google Drive Trigger System initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.load_subscriptions()
        await self.start_background_processing()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()
    
    async def stop(self):
        """Stop trigger system and cleanup resources"""
        
        try:
            # Stop background processing
            self._processing_enabled = False
            
            # Cancel background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            self._background_tasks.clear()
            
            # Save subscriptions
            await self.save_subscriptions()
            
            # Save pending events
            await self.save_pending_events()
            
            logger.info("Trigger System stopped")
        
        except Exception as e:
            logger.error(f"Error stopping Trigger System: {e}")
    
    # ==================== WEBHOOK HANDLING ====================
    
    def handle_webhook(self, request_data: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook from Google Drive"""
        
        try:
            # Verify webhook signature if secret is configured
            if self.webhook_secret and not self._verify_webhook_signature(request_data, headers):
                return {
                    "success": False,
                    "error": "Invalid webhook signature"
                }, 401
            
            # Parse webhook data
            webhook_data = self._parse_webhook_data(request_data)
            
            if not webhook_data:
                return {
                    "success": False,
                    "error": "Invalid webhook data"
                }, 400
            
            # Create trigger events
            events = self._create_events_from_webhook(webhook_data)
            
            # Add events to pending queue
            for event in events:
                self.pending_events[event.event_id] = event
                logger.debug(f"Added pending event: {event.event_id} ({event.event_type.value})")
            
            # Start background processing
            asyncio.create_task(self._process_pending_events())
            
            return {
                "success": True,
                "message": f"Processed {len(events)} events",
                "events": [event.event_id for event in events]
            }
        
        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }, 500
    
    def _verify_webhook_signature(self, request_data: Any, headers: Dict[str, Any]) -> bool:
        """Verify webhook HMAC signature"""
        
        try:
            # Get signature from headers
            signature = headers.get('X-Goog-Signature') or headers.get('X-Hub-Signature')
            if not signature:
                return True  # Skip verification if no signature
            
            # Extract signature hash
            if signature.startswith('sha256='):
                signature_hash = signature[7:]
            else:
                signature_hash = signature
            
            # Calculate expected signature
            if isinstance(request_data, str):
                payload = request_data.encode('utf-8')
            else:
                payload = json.dumps(request_data, sort_keys=True).encode('utf-8')
            
            expected_hash = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature_hash, expected_hash)
        
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False
    
    def _parse_webhook_data(self, request_data: Any) -> Optional[Dict[str, Any]]:
        """Parse webhook data"""
        
        try:
            # Handle different webhook formats
            if isinstance(request_data, dict):
                return request_data
            
            # Parse JSON string
            if isinstance(request_data, str):
                return json.loads(request_data)
            
            # Handle Flask request
            if hasattr(request_data, 'get_json'):
                return request_data.get_json()
            
            logger.error(f"Unsupported webhook data format: {type(request_data)}")
            return None
        
        except Exception as e:
            logger.error(f"Failed to parse webhook data: {e}")
            return None
    
    def _create_events_from_webhook(self, webhook_data: Dict[str, Any]) -> List[TriggerEvent]:
        """Create trigger events from webhook data"""
        
        try:
            events = []
            
            # Handle different webhook types
            if webhook_data.get('kind') == 'drive#change':
                # Google Drive changes webhook
                changes = webhook_data.get('changes', [])
                
                for change in changes:
                    event = self._create_event_from_change(change)
                    if event:
                        events.append(event)
            
            elif webhook_data.get('type') == 'webhook':
                # Generic webhook
                event = self._create_event_from_generic_webhook(webhook_data)
                if event:
                    events.append(event)
            
            return events
        
        except Exception as e:
            logger.error(f"Failed to create events from webhook: {e}")
            return []
    
    def _create_event_from_change(self, change: Dict[str, Any]) -> Optional[TriggerEvent]:
        """Create event from Google Drive change"""
        
        try:
            file_id = change.get('fileId')
            if not file_id:
                return None
            
            # Determine event type
            removed = change.get('removed', False)
            file_data = change.get('file', {})
            
            if removed:
                event_type = TriggerEventType.FILE_DELETED
            elif file_data.get('trashed'):
                event_type = TriggerEventType.FILE_DELETED
            else:
                event_type = TriggerEventType.FILE_UPDATED
            
            # Determine if it's a folder
            mime_type = file_data.get('mimeType', '')
            resource_type = 'folder' if mime_type == 'application/vnd.google-apps.folder' else 'file'
            
            # Create event
            event_id = str(uuid.uuid4())
            event = TriggerEvent(
                event_id=event_id,
                event_type=event_type,
                resource_id=file_id,
                resource_type=resource_type,
                user_id=change.get('kind', ''),  # Would need to get user from service
                timestamp=datetime.utcnow(),
                data={
                    'change': change,
                    'file': file_data,
                    'removed': removed,
                    'source': 'webhook'
                }
            )
            
            return event
        
        except Exception as e:
            logger.error(f"Failed to create event from change: {e}")
            return None
    
    def _create_event_from_generic_webhook(self, webhook_data: Dict[str, Any]) -> Optional[TriggerEvent]:
        """Create event from generic webhook"""
        
        try:
            # Extract event type
            event_type_str = webhook_data.get('event', 'file_created')
            event_type = TriggerEventType(event_type_str)
            
            # Extract resource info
            resource_id = webhook_data.get('resource_id') or webhook_data.get('file_id')
            resource_type = webhook_data.get('resource_type', 'file')
            user_id = webhook_data.get('user_id', '')
            
            if not resource_id:
                return None
            
            # Create event
            event_id = str(uuid.uuid4())
            event = TriggerEvent(
                event_id=event_id,
                event_type=event_type,
                resource_id=resource_id,
                resource_type=resource_type,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                data=webhook_data
            )
            
            return event
        
        except Exception as e:
            logger.error(f"Failed to create event from generic webhook: {e}")
            return None
    
    # ==================== EVENT PROCESSING ====================
    
    async def _process_pending_events(self):
        """Process pending trigger events"""
        
        try:
            if not self._processing_enabled:
                return
            
            # Get events to process
            events_to_process = [
                event for event in self.pending_events.values()
                if not event.processed and event.processing_attempts < 5
            ]
            
            if not events_to_process:
                return
            
            logger.info(f"Processing {len(events_to_process)} pending events")
            
            # Process events
            for event in events_to_process:
                try:
                    # Get event processor
                    processor = self.event_processors.get(event.event_type)
                    if not processor:
                        logger.warning(f"No processor for event type: {event.event_type.value}")
                        event.processed = True
                        event.error_message = "No processor available"
                        continue
                    
                    # Process event
                    processing_result = await processor(event)
                    
                    if processing_result.get("success", False):
                        event.processed = True
                        logger.debug(f"Processed event: {event.event_id}")
                    else:
                        event.processing_attempts += 1
                        event.error_message = processing_result.get("error", "Unknown error")
                        logger.warning(f"Failed to process event {event.event_id}: {event.error_message}")
                    
                    # Add to processed events (whether successful or not after max attempts)
                    if event.processed or event.processing_attempts >= 5:
                        self.processed_events[event.event_id] = event
                        
                        # Remove from pending
                        if event.event_id in self.pending_events:
                            del self.pending_events[event.event_id]
                
                except Exception as e:
                    event.processing_attempts += 1
                    event.error_message = str(e)
                    logger.error(f"Error processing event {event.event_id}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to process pending events: {e}")
    
    # ==================== EVENT PROCESSORS ====================
    
    def _register_event_processors(self):
        """Register event processors"""
        
        self.event_processors = {
            TriggerEventType.FILE_CREATED: self._process_file_created,
            TriggerEventType.FILE_UPDATED: self._process_file_updated,
            TriggerEventType.FILE_DELETED: self._process_file_deleted,
            TriggerEventType.FILE_SHARED: self._process_file_shared,
            TriggerEventType.FILE_MOVED: self._process_file_moved,
            TriggerEventType.FOLDER_CREATED: self._process_folder_created,
        }
    
    async def _process_file_created(self, event: TriggerEvent) -> Dict[str, Any]:
        """Process file created event"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {"success": False, "error": "Automation engine not available"}
            
            # Prepare trigger data
            trigger_data = {
                "file_id": event.resource_id,
                "resource_type": event.resource_type,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "data": event.data
            }
            
            # Get file information
            drive_service = await get_google_drive_service()
            if drive_service:
                file_result = await drive_service.get_file(event.resource_id)
                if file_result["success"]:
                    trigger_data["file"] = file_result["file"]
            
            # Process trigger
            results = await automation_engine.process_trigger(
                trigger_type=TriggerType.FILE_CREATED.value,
                trigger_data=trigger_data
            )
            
            return {
                "success": True,
                "message": f"Processed file created trigger, executed {len(results)} workflows",
                "workflow_results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process file created event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_file_updated(self, event: TriggerEvent) -> Dict[str, Any]:
        """Process file updated event"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {"success": False, "error": "Automation engine not available"}
            
            # Prepare trigger data
            trigger_data = {
                "file_id": event.resource_id,
                "resource_type": event.resource_type,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "data": event.data
            }
            
            # Get file information
            drive_service = await get_google_drive_service()
            if drive_service:
                file_result = await drive_service.get_file(event.resource_id)
                if file_result["success"]:
                    trigger_data["file"] = file_result["file"]
            
            # Process trigger
            results = await automation_engine.process_trigger(
                trigger_type=TriggerType.FILE_UPDATED.value,
                trigger_data=trigger_data
            )
            
            return {
                "success": True,
                "message": f"Processed file updated trigger, executed {len(results)} workflows",
                "workflow_results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process file updated event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_file_deleted(self, event: TriggerEvent) -> Dict[str, Any]:
        """Process file deleted event"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {"success": False, "error": "Automation engine not available"}
            
            # Prepare trigger data
            trigger_data = {
                "file_id": event.resource_id,
                "resource_type": event.resource_type,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "data": event.data
            }
            
            # Process trigger
            results = await automation_engine.process_trigger(
                trigger_type=TriggerType.FILE_DELETED.value,
                trigger_data=trigger_data
            )
            
            return {
                "success": True,
                "message": f"Processed file deleted trigger, executed {len(results)} workflows",
                "workflow_results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process file deleted event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_file_shared(self, event: TriggerEvent) -> Dict[str, Any]:
        """Process file shared event"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {"success": False, "error": "Automation engine not available"}
            
            # Prepare trigger data
            trigger_data = {
                "file_id": event.resource_id,
                "resource_type": event.resource_type,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "data": event.data
            }
            
            # Process trigger
            results = await automation_engine.process_trigger(
                trigger_type=TriggerType.FILE_SHARED.value,
                trigger_data=trigger_data
            )
            
            return {
                "success": True,
                "message": f"Processed file shared trigger, executed {len(results)} workflows",
                "workflow_results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process file shared event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_file_moved(self, event: TriggerEvent) -> Dict[str, Any]:
        """Process file moved event"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {"success": False, "error": "Automation engine not available"}
            
            # Prepare trigger data
            trigger_data = {
                "file_id": event.resource_id,
                "resource_type": event.resource_type,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "data": event.data
            }
            
            # Process trigger
            results = await automation_engine.process_trigger(
                trigger_type=TriggerType.FILE_MOVED.value,
                trigger_data=trigger_data
            )
            
            return {
                "success": True,
                "message": f"Processed file moved trigger, executed {len(results)} workflows",
                "workflow_results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process file moved event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_folder_created(self, event: TriggerEvent) -> Dict[str, Any]:
        """Process folder created event"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {"success": False, "error": "Automation engine not available"}
            
            # Prepare trigger data
            trigger_data = {
                "file_id": event.resource_id,
                "resource_type": event.resource_type,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "data": event.data
            }
            
            # Process trigger
            results = await automation_engine.process_trigger(
                trigger_type=TriggerType.FOLDER_CREATED.value,
                trigger_data=trigger_data
            )
            
            return {
                "success": True,
                "message": f"Processed folder created trigger, executed {len(results)} workflows",
                "workflow_results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to process folder created event: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== WEBHOOK SUBSCRIPTIONS ====================
    
    async def create_webhook_subscription(self, 
                                       webhook_url: str,
                                       resource_id: str = "root",
                                       resource_type: str = "folder") -> Dict[str, Any]:
        """Create webhook subscription"""
        
        try:
            # Get Google Drive service
            drive_service = await get_google_drive_service()
            if not drive_service:
                return {
                    "success": False,
                    "error": "Google Drive service not available"
                }
            
            # Create subscription
            subscription_data = {
                "kind": "api#channel",
                "type": "web_hook",
                "address": webhook_url,
                "id": str(uuid.uuid4()),
                "expiration": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
            }
            
            # Make subscription request to Google Drive
            # This would involve the actual Google Drive API call
            # For now, simulate successful subscription
            subscription_id = str(uuid.uuid4())
            channel_id = str(uuid.uuid4())
            
            # Create subscription object
            subscription = WebhookSubscription(
                subscription_id=subscription_id,
                channel_id=channel_id,
                channel_type="web_address",
                address=webhook_url,
                resource_id=resource_id,
                resource_type=resource_type,
                expiration=datetime.utcnow() + timedelta(hours=24)
            )
            
            # Store subscription
            self.webhook_subscriptions[subscription_id] = subscription
            await self.save_subscriptions()
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "channel_id": channel_id,
                "webhook_url": webhook_url,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "expiration": subscription.expiration.isoformat(),
                "message": "Webhook subscription created successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to create webhook subscription: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def renew_webhook_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Renew webhook subscription"""
        
        try:
            subscription = self.webhook_subscriptions.get(subscription_id)
            if not subscription:
                return {
                    "success": False,
                    "error": "Subscription not found"
                }
            
            # Update expiration
            subscription.updated_at = datetime.utcnow()
            subscription.expiration = datetime.utcnow() + timedelta(hours=24)
            subscription.state = "active"
            
            # Save subscription
            await self.save_subscriptions()
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "expiration": subscription.expiration.isoformat(),
                "message": "Webhook subscription renewed successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to renew webhook subscription: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_webhook_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Delete webhook subscription"""
        
        try:
            subscription = self.webhook_subscriptions.get(subscription_id)
            if not subscription:
                return {
                    "success": False,
                    "error": "Subscription not found"
                }
            
            # Delete from Google Drive (API call would go here)
            
            # Remove from storage
            del self.webhook_subscriptions[subscription_id]
            await self.save_subscriptions()
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "message": "Webhook subscription deleted successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to delete webhook subscription: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== MANUAL TRIGGERS ====================
    
    async def trigger_manual_workflow(self, 
                                     workflow_id: str,
                                     trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manually trigger workflow"""
        
        try:
            # Get automation engine
            automation_engine = await get_automation_engine()
            if not automation_engine:
                return {
                    "success": False,
                    "error": "Automation engine not available"
                }
            
            # Create manual trigger event
            event_id = str(uuid.uuid4())
            manual_event = TriggerEvent(
                event_id=event_id,
                event_type=TriggerEventType.SYNC_STARTED,  # Use a generic event type
                resource_id="manual",
                resource_type="manual",
                user_id=trigger_data.get("user_id", ""),
                timestamp=datetime.utcnow(),
                data=trigger_data
            )
            
            # Execute workflow
            execution_result = await automation_engine.execute_workflow(
                workflow_id=workflow_id,
                trigger_data=trigger_data,
                manual_trigger=True
            )
            
            return execution_result
        
        except Exception as e:
            logger.error(f"Failed to trigger manual workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== BACKGROUND PROCESSING ====================
    
    async def start_background_processing(self):
        """Start background event processing"""
        
        try:
            # Start event processing task
            event_processing_task = asyncio.create_task(self._background_event_processor())
            self._background_tasks.append(event_processing_task)
            
            # Start subscription renewal task
            subscription_renewal_task = asyncio.create_task(self._background_subscription_renewer())
            self._background_tasks.append(subscription_renewal_task)
            
            # Start cleanup task
            cleanup_task = asyncio.create_task(self._background_cleanup())
            self._background_tasks.append(cleanup_task)
            
            logger.info("Background processing started")
        
        except Exception as e:
            logger.error(f"Failed to start background processing: {e}")
    
    async def _background_event_processor(self):
        """Background task to process events"""
        
        while self._processing_enabled:
            try:
                await self._process_pending_events()
                await asyncio.sleep(5)  # Process every 5 seconds
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background event processor error: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def _background_subscription_renewer(self):
        """Background task to renew subscriptions"""
        
        while self._processing_enabled:
            try:
                # Check for expiring subscriptions
                now = datetime.utcnow()
                renewal_threshold = now + timedelta(hours=2)
                
                for subscription in self.webhook_subscriptions.values():
                    if (subscription.expiration and 
                        subscription.expiration <= renewal_threshold and
                        subscription.state == "active"):
                        
                        logger.info(f"Renewing subscription: {subscription.subscription_id}")
                        await self.renew_webhook_subscription(subscription.subscription_id)
                
                await asyncio.sleep(3600)  # Check every hour
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background subscription renewer error: {e}")
                await asyncio.sleep(3600)
    
    async def _background_cleanup(self):
        """Background task to clean up old events"""
        
        while self._processing_enabled:
            try:
                # Clean up old processed events
                cutoff_date = datetime.utcnow() - timedelta(days=self.event_retention_days)
                
                events_to_remove = [
                    event_id for event_id, event in self.processed_events.items()
                    if event.timestamp < cutoff_date
                ]
                
                for event_id in events_to_remove:
                    del self.processed_events[event_id]
                
                if events_to_remove:
                    logger.debug(f"Cleaned up {len(events_to_remove)} old events")
                
                await asyncio.sleep(86400)  # Clean up daily
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background cleanup error: {e}")
                await asyncio.sleep(86400)
    
    # ==================== STORAGE ====================
    
    async def save_subscriptions(self):
        """Save webhook subscriptions to storage"""
        
        try:
            # This would integrate with your database
            # For now, save to Redis
            if redis_client:
                subscriptions_data = {
                    sub_id: sub.to_dict() 
                    for sub_id, sub in self.webhook_subscriptions.items()
                }
                
                await redis_client.setex(
                    f"atom:google_drive:subscriptions",
                    86400 * 7,  # 7 days
                    json.dumps(subscriptions_data, default=str)
                )
            
            logger.debug(f"Saved {len(self.webhook_subscriptions)} webhook subscriptions")
        
        except Exception as e:
            logger.error(f"Failed to save subscriptions: {e}")
    
    async def load_subscriptions(self):
        """Load webhook subscriptions from storage"""
        
        try:
            # This would integrate with your database
            # For now, load from Redis
            if redis_client:
                subscriptions_data = await redis_client.get(f"atom:google_drive:subscriptions")
                
                if subscriptions_data:
                    subscriptions_dict = json.loads(subscriptions_data)
                    
                    for sub_id, sub_data in subscriptions_dict.items():
                        subscription = WebhookSubscription(
                            subscription_id=sub_data["subscription_id"],
                            channel_id=sub_data["channel_id"],
                            channel_type=sub_data["channel_type"],
                            address=sub_data["address"],
                            resource_id=sub_data["resource_id"],
                            resource_type=sub_data["resource_type"],
                            expiration=datetime.fromisoformat(sub_data["expiration"]) if sub_data.get("expiration") else None,
                            state=sub_data["state"],
                            created_at=datetime.fromisoformat(sub_data["created_at"]),
                            updated_at=datetime.fromisoformat(sub_data["updated_at"])
                        )
                        
                        self.webhook_subscriptions[sub_id] = subscription
            
            logger.info(f"Loaded {len(self.webhook_subscriptions)} webhook subscriptions")
        
        except Exception as e:
            logger.error(f"Failed to load subscriptions: {e}")
    
    async def save_pending_events(self):
        """Save pending events to storage"""
        
        try:
            # This would integrate with your database
            # For now, save to Redis
            if redis_client:
                events_data = {
                    event_id: event.to_dict() 
                    for event_id, event in self.pending_events.items()
                }
                
                await redis_client.setex(
                    f"atom:google_drive:pending_events",
                    86400,  # 1 day
                    json.dumps(events_data, default=str)
                )
            
            logger.debug(f"Saved {len(self.pending_events)} pending events")
        
        except Exception as e:
            logger.error(f"Failed to save pending events: {e}")
    
    # ==================== UTILITY METHODS ====================
    
    async def get_trigger_stats(self) -> Dict[str, Any]:
        """Get trigger system statistics"""
        
        try:
            return {
                "pending_events": len(self.pending_events),
                "processed_events": len(self.processed_events),
                "webhook_subscriptions": len(self.webhook_subscriptions),
                "active_subscriptions": len([
                    sub for sub in self.webhook_subscriptions.values()
                    if sub.state == "active"
                ]),
                "background_tasks": len(self._background_tasks),
                "processing_enabled": self._processing_enabled,
                "supported_event_types": [event_type.value for event_type in TriggerEventType],
                "webhook_secret_configured": bool(self.webhook_secret),
                "event_retention_days": self.event_retention_days
            }
        
        except Exception as e:
            logger.error(f"Failed to get trigger stats: {e}")
            return {}
    
    async def get_webhook_subscriptions(self, 
                                      active_only: bool = True) -> List[Dict[str, Any]]:
        """Get webhook subscriptions"""
        
        try:
            subscriptions = list(self.webhook_subscriptions.values())
            
            if active_only:
                subscriptions = [sub for sub in subscriptions if sub.state == "active"]
            
            return [sub.to_dict() for sub in subscriptions]
        
        except Exception as e:
            logger.error(f"Failed to get webhook subscriptions: {e}")
            return []
    
    async def get_pending_events(self, 
                                 limit: int = 50,
                                 unprocessed_only: bool = True) -> List[Dict[str, Any]]:
        """Get pending events"""
        
        try:
            events = list(self.pending_events.values())
            
            if unprocessed_only:
                events = [event for event in events if not event.processed]
            
            # Sort by timestamp (oldest first)
            events.sort(key=lambda e: e.timestamp)
            
            # Apply limit
            events = events[:limit]
            
            return [event.to_dict() for event in events]
        
        except Exception as e:
            logger.error(f"Failed to get pending events: {e}")
            return []

# Global trigger system instance
_trigger_system: Optional[GoogleDriveTriggerSystem] = None

async def get_google_drive_trigger_system() -> Optional[GoogleDriveTriggerSystem]:
    """Get global Google Drive trigger system instance"""
    
    global _trigger_system
    
    if _trigger_system is None:
        try:
            config = get_config_instance()
            _trigger_system = GoogleDriveTriggerSystem(config)
            await _trigger_system.load_subscriptions()
            logger.info("Google Drive Trigger System created")
        except Exception as e:
            logger.error(f"Failed to create Google Drive Trigger System: {e}")
            _trigger_system = None
    
    return _trigger_system

def clear_google_drive_trigger_system():
    """Clear global trigger system instance"""
    
    global _trigger_system
    _trigger_system = None
    logger.info("Google Drive Trigger System cleared")

# Export classes and functions
__all__ = [
    'GoogleDriveTriggerSystem',
    'TriggerEvent',
    'TriggerEventType',
    'WebhookSubscription',
    'get_google_drive_trigger_system',
    'clear_google_drive_trigger_system'
]