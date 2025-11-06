"""
Google Drive Real-time Sync Service
Real-time file synchronization with memory integration and change detection
"""

import json
import logging
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from google_drive_service import GoogleDriveService, GoogleDriveFile, GoogleDriveChange
from google_drive_memory import GoogleDriveMemoryService, GoogleDriveMemoryRecord, GoogleDriveFolderRecord

class RealtimeSyncEventType(Enum):
    """Real-time sync event types"""
    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    FILE_SHARED = "file_shared"
    FOLDER_CREATED = "folder_created"
    FOLDER_UPDATED = "folder_updated"
    FOLDER_DELETED = "folder_deleted"
    FOLDER_MOVED = "folder_moved"
    PERMISSION_CHANGED = "permission_changed"
    CONTENT_CHANGED = "content_changed"

@dataclass
class RealtimeSyncEvent:
    """Real-time sync event model"""
    id: str
    event_type: RealtimeSyncEventType
    file_id: str
    file_name: str
    mime_type: str
    user_id: str
    timestamp: datetime
    old_parent_ids: Optional[List[str]] = None
    new_parent_ids: Optional[List[str]] = None
    old_name: Optional[str] = None
    new_name: Optional[str] = None
    old_shared: Optional[bool] = None
    new_shared: Optional[bool] = None
    content_hash: Optional[str] = None
    change_id: Optional[str] = None
    processing_status: str = "pending"  # pending, processing, completed, failed
    processing_time: Optional[datetime] = None
    error_message: Optional[str] = None
    memory_updated: bool = False
    webhook_sent: bool = False

@dataclass
class SyncSubscription:
    """Real-time sync subscription model"""
    id: str
    user_id: str
    folder_id: Optional[str] = None  # Root folder if None
    include_subfolders: bool = True
    file_types: List[str] = field(default_factory=list)
    event_types: List[RealtimeSyncEventType] = field(default_factory=lambda: list(RealtimeSyncEventType))
    webhook_url: Optional[str] = None
    webhook_events: List[RealtimeSyncEventType] = field(default_factory=list)
    memory_sync: bool = True  # Sync to memory
    realtime_notifications: bool = True  # Send real-time notifications
    change_webhook_active: bool = False
    last_sync_token: Optional[str] = None
    last_change_id: Optional[str] = None
    sync_interval: int = 30  # seconds
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_synced: int = 0
    total_errors: int = 0
    last_sync_time: Optional[datetime] = None

@dataclass
class SyncState:
    """Real-time sync state model"""
    user_id: str
    page_token: Optional[str] = None
    next_page_token: Optional[str] = None
    start_page_token: Optional[str] = None
    largest_change_id: Optional[str] = None
    last_full_sync: Optional[datetime] = None
    last_incremental_sync: Optional[datetime] = None
    files_hash: Dict[str, str] = field(default_factory=dict)
    folders_hash: Dict[str, str] = field(default_factory=dict)
    sync_history: List[str] = field(default_factory=list)
    processing_changes: Set[str] = field(default_factory=set)
    error_count: int = 0
    consecutive_errors: int = 0

class GoogleDriveRealtimeSyncService:
    """Google Drive real-time synchronization service"""
    
    def __init__(
        self,
        drive_service: GoogleDriveService,
        memory_service: GoogleDriveMemoryService,
        db_pool=None
    ):
        self.drive_service = drive_service
        self.memory_service = memory_service
        self.db_pool = db_pool
        
        # Subscriptions and sync state
        self.subscriptions: Dict[str, SyncSubscription] = {}
        self.sync_states: Dict[str, SyncState] = {}
        
        # Event handlers
        self.event_handlers: Dict[RealtimeSyncEventType, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
        self.webhook_handlers: Dict[str, Callable] = {}
        
        # Sync configuration
        self.default_sync_interval = 30  # seconds
        self.max_concurrent_syncs = 5
        self.sync_timeout = 300  # seconds
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # Processing queues
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.processing_tasks: List[asyncio.Task] = []
        self.max_processing_workers = 4
        
        # Statistics
        self.total_events_processed = 0
        self.total_errors = 0
        self.active_syncs: Set[str] = set()
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.running = False
        
        # Event history
        self.events_history: List[RealtimeSyncEvent] = []
        self.max_events_history = 10000
        
        logger.info("Google Drive Real-time Sync Service initialized")
    
    def start(self):
        """Start real-time sync service"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting Google Drive Real-time Sync Service")
        
        # Start background tasks
        self.background_tasks = [
            asyncio.create_task(self._sync_worker()),
            asyncio.create_task(self._event_processor()),
            asyncio.create_task(self._periodic_sync()),
            asyncio.create_task(self._cleanup_worker())
        ]
        
        logger.info(f"Started {len(self.background_tasks)} background tasks")
    
    def stop(self):
        """Stop real-time sync service"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping Google Drive Real-time Sync Service")
        
        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.background_tasks:
            asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        logger.info("Google Drive Real-time Sync Service stopped")
    
    def register_event_handler(
        self,
        event_type: RealtimeSyncEventType,
        handler: Callable
    ):
        """Register handler for specific event type"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for event: {event_type.value}")
    
    def register_global_handler(self, handler: Callable):
        """Register global handler for all events"""
        self.global_handlers.append(handler)
        logger.info("Registered global sync handler")
    
    def register_webhook_handler(self, subscription_id: str, handler: Callable):
        """Register webhook handler for subscription"""
        self.webhook_handlers[subscription_id] = handler
        logger.info(f"Registered webhook handler for subscription: {subscription_id}")
    
    async def create_subscription(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        include_subfolders: bool = True,
        file_types: Optional[List[str]] = None,
        event_types: Optional[List[RealtimeSyncEventType]] = None,
        webhook_url: Optional[str] = None,
        webhook_events: Optional[List[RealtimeSyncEventType]] = None,
        memory_sync: bool = True,
        realtime_notifications: bool = True,
        sync_interval: int = None,
        max_file_size: int = None,
        db_conn_pool=None
    ) -> SyncSubscription:
        """Create new real-time sync subscription"""
        
        try:
            subscription_id = self._generate_subscription_id()
            
            subscription = SyncSubscription(
                id=subscription_id,
                user_id=user_id,
                folder_id=folder_id,
                include_subfolders=include_subfolders,
                file_types=file_types or [],
                event_types=event_types or list(RealtimeSyncEventType),
                webhook_url=webhook_url,
                webhook_events=webhook_events or [],
                memory_sync=memory_sync,
                realtime_notifications=realtime_notifications,
                sync_interval=sync_interval or self.default_sync_interval,
                max_file_size=max_file_size or (100 * 1024 * 1024)  # 100MB
            )
            
            # Store subscription
            self.subscriptions[subscription_id] = subscription
            
            # Initialize sync state
            sync_state = SyncState(user_id=user_id)
            self.sync_states[user_id] = sync_state
            
            # Store in database
            if self.db_pool:
                await self._store_subscription_in_db(subscription, db_conn_pool)
            
            # Perform initial sync
            await self._perform_initial_sync(subscription, db_conn_pool)
            
            # Start change notification if webhook URL provided
            if webhook_url:
                await self._start_change_notifications(subscription, db_conn_pool)
            
            logger.info(f"Created real-time sync subscription: {subscription_id}")
            
            return subscription
        
        except Exception as e:
            logger.error(f"Error creating sync subscription: {e}")
            raise
    
    async def delete_subscription(
        self,
        subscription_id: str,
        db_conn_pool=None
    ) -> bool:
        """Delete real-time sync subscription"""
        
        try:
            if subscription_id not in self.subscriptions:
                return False
            
            subscription = self.subscriptions[subscription_id]
            
            # Stop change notifications
            if subscription.change_webhook_active:
                await self._stop_change_notifications(subscription, db_conn_pool)
            
            # Remove from memory
            del self.subscriptions[subscription_id]
            del self.sync_states[subscription.user_id]
            
            # Remove webhook handler
            if subscription_id in self.webhook_handlers:
                del self.webhook_handlers[subscription_id]
            
            # Remove from database
            if self.db_pool:
                await self._delete_subscription_from_db(subscription_id, db_conn_pool)
            
            logger.info(f"Deleted sync subscription: {subscription_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error deleting sync subscription: {e}")
            return False
    
    async def sync_now(
        self,
        user_id: str,
        subscription_id: Optional[str] = None,
        full_sync: bool = False,
        db_conn_pool=None
    ) -> Dict[str, Any]:
        """Trigger immediate sync for user"""
        
        try:
            if user_id in self.active_syncs:
                return {
                    "success": False,
                    "error": "Sync already in progress"
                }
            
            # Get subscription
            subscription = None
            if subscription_id and subscription_id in self.subscriptions:
                subscription = self.subscriptions[subscription_id]
            
            # Get user subscriptions if no specific subscription
            if not subscription:
                user_subscriptions = [
                    sub for sub in self.subscriptions.values()
                    if sub.user_id == user_id and sub.active
                ]
                if not user_subscriptions:
                    return {
                        "success": False,
                        "error": "No active subscriptions found"
                    }
                subscription = user_subscriptions[0]  # Use first active subscription
            
            self.active_syncs.add(user_id)
            
            try:
                # Perform sync
                if full_sync:
                    result = await self._perform_full_sync(subscription, db_conn_pool)
                else:
                    result = await self._perform_incremental_sync(subscription, db_conn_pool)
                
                result["success"] = True
                return result
            
            finally:
                self.active_syncs.discard(user_id)
        
        except Exception as e:
            self.active_syncs.discard(user_id)
            logger.error(f"Error in sync_now: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_webhook_notification(
        self,
        subscription_id: str,
        notification_data: Dict[str, Any],
        db_conn_pool=None
    ) -> Dict[str, Any]:
        """Process webhook notification from Google Drive"""
        
        try:
            if subscription_id not in self.subscriptions:
                return {
                    "success": False,
                    "error": "Subscription not found"
                }
            
            subscription = self.subscriptions[subscription_id]
            
            # Validate notification
            headers = notification_data.get("headers", {})
            channel_id = headers.get("X-Goog-Channel-ID")
            
            if channel_id != subscription_id:
                return {
                    "success": False,
                    "error": "Invalid channel ID"
                }
            
            # Process changes
            changes = notification_data.get("changes", [])
            processed_changes = 0
            
            for change_data in changes:
                try:
                    # Create sync event
                    sync_event = await self._create_sync_event_from_webhook(
                        change_data, subscription, db_conn_pool
                    )
                    
                    if sync_event:
                        # Add to processing queue
                        await self.event_queue.put(sync_event)
                        processed_changes += 1
                
                except Exception as e:
                    logger.error(f"Error processing webhook change: {e}")
                    continue
            
            # Update subscription
            subscription.last_change_id = notification_data.get("changeId")
            subscription.updated_at = datetime.now(timezone.utc)
            
            if self.db_pool:
                await self._update_subscription_in_db(subscription, db_conn_pool)
            
            return {
                "success": True,
                "processed_changes": processed_changes,
                "subscription_id": subscription_id
            }
        
        except Exception as e:
            logger.error(f"Error processing webhook notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _sync_worker(self):
        """Background sync worker"""
        while self.running:
            try:
                # Process each active subscription
                for subscription in self.subscriptions.values():
                    if not subscription.active:
                        continue
                    
                    try:
                        # Check if sync is needed
                        if self._should_sync_now(subscription):
                            await self._perform_incremental_sync(subscription, self.db_pool)
                    
                    except Exception as e:
                        logger.error(f"Error in sync worker for subscription {subscription.id}: {e}")
                
                # Wait before next sync cycle
                await asyncio.sleep(self.default_sync_interval)
            
            except Exception as e:
                logger.error(f"Error in sync worker: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def _event_processor(self):
        """Background event processor"""
        processing_tasks = []
        
        while self.running:
            try:
                # Get event from queue (with timeout)
                try:
                    event = await asyncio.wait_for(
                        self.event_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Limit concurrent processing
                if len(processing_tasks) >= self.max_processing_workers:
                    # Wait for some tasks to complete
                    done, processing_tasks = await asyncio.wait(
                        processing_tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                
                # Create processing task
                task = asyncio.create_task(
                    self._process_sync_event(event, self.db_pool)
                )
                processing_tasks.append(task)
                
                # Clean up completed tasks
                done_tasks = [t for t in processing_tasks if t.done()]
                for task in done_tasks:
                    processing_tasks.remove(task)
                    try:
                        await task
                    except Exception as e:
                        logger.error(f"Error in event processing task: {e}")
            
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
                await asyncio.sleep(5)
    
    async def _periodic_sync(self):
        """Background periodic sync"""
        while self.running:
            try:
                # Perform full sync for subscriptions that need it
                for subscription in self.subscriptions.values():
                    if not subscription.active:
                        continue
                    
                    sync_state = self.sync_states.get(subscription.user_id)
                    
                    # Perform full sync if needed (once per day)
                    if (sync_state and 
                        sync_state.last_full_sync and
                        datetime.now(timezone.utc) - sync_state.last_full_sync > timedelta(days=1)):
                        
                        await self._perform_full_sync(subscription, self.db_pool)
                
                # Wait before next periodic sync
                await asyncio.sleep(3600)  # 1 hour
            
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
                await asyncio.sleep(300)  # 5 minutes
    
    async def _cleanup_worker(self):
        """Background cleanup worker"""
        while self.running:
            try:
                # Clean old events from history
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
                
                old_events = [
                    event for event in self.events_history
                    if event.timestamp < cutoff_time
                ]
                
                for event in old_events:
                    self.events_history.remove(event)
                
                # Clean old sync states
                for user_id, sync_state in self.sync_states.items():
                    if len(sync_state.sync_history) > 1000:
                        # Keep only last 1000 sync IDs
                        sync_state.sync_history = sync_state.sync_history[-1000:]
                
                # Log cleanup stats
                if old_events:
                    logger.info(f"Cleaned up {len(old_events)} old sync events")
                
                # Wait before next cleanup
                await asyncio.sleep(3600)  # 1 hour
            
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
                await asyncio.sleep(300)  # 5 minutes
    
    async def _perform_initial_sync(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ):
        """Perform initial sync for subscription"""
        
        try:
            logger.info(f"Performing initial sync for subscription: {subscription.id}")
            
            # Get sync state
            sync_state = self.sync_states.get(subscription.user_id)
            if not sync_state:
                sync_state = SyncState(user_id=subscription.user_id)
                self.sync_states[subscription.user_id] = sync_state
            
            # Get all files and folders
            files = await self.drive_service.get_files(
                user_id=subscription.user_id,
                parent_id=subscription.folder_id,
                page_size=1000,
                db_conn_pool=db_conn_pool
            )
            
            # Filter by file types and size
            filtered_files = self._filter_files(files, subscription)
            
            # Process files
            processed_count = 0
            for file in filtered_files:
                try:
                    # Index file in memory
                    memory_record = await self.memory_service.index_file(
                        file, subscription.user_id, True, True
                    )
                    
                    # Create sync event
                    sync_event = RealtimeSyncEvent(
                        id=self._generate_event_id(),
                        event_type=RealtimeSyncEventType.FILE_CREATED,
                        file_id=file.id,
                        file_name=file.name,
                        mime_type=file.mime_type,
                        user_id=subscription.user_id,
                        timestamp=datetime.now(timezone.utc),
                        processing_status="completed",
                        memory_updated=True
                    )
                    
                    await self._process_sync_event(sync_event, db_conn_pool)
                    processed_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing file {file.id}: {e}")
                    continue
            
            # Update sync state
            sync_state.last_full_sync = datetime.now(timezone.utc)
            sync_state.last_incremental_sync = datetime.now(timezone.utc)
            
            # Update file hashes
            await self._update_file_hashes(filtered_files, sync_state, db_conn_pool)
            
            # Update subscription
            subscription.total_synced = processed_count
            subscription.last_sync_time = datetime.now(timezone.utc)
            subscription.updated_at = datetime.now(timezone.utc)
            
            if self.db_pool:
                await self._update_subscription_in_db(subscription, db_conn_pool)
                await self._store_sync_state_in_db(sync_state, db_conn_pool)
            
            logger.info(f"Initial sync completed: {processed_count} files processed")
        
        except Exception as e:
            logger.error(f"Error in initial sync: {e}")
            subscription.total_errors += 1
            raise
    
    async def _perform_incremental_sync(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ) -> Dict[str, Any]:
        """Perform incremental sync for subscription"""
        
        try:
            logger.debug(f"Performing incremental sync for subscription: {subscription.id}")
            
            # Get sync state
            sync_state = self.sync_states.get(subscription.user_id)
            if not sync_state:
                sync_state = SyncState(user_id=subscription.user_id)
                self.sync_states[subscription.user_id] = sync_state
            
            # Get changes from Google Drive
            changes = []
            
            if sync_state.page_token:
                # Get changes since last sync
                drive_changes = await self.drive_service._make_request(
                    user_id=subscription.user_id,
                    method="GET",
                    endpoint="changes",
                    params={
                        "pageToken": sync_state.page_token,
                        "pageSize": 1000,
                        "fields": "changes(id,fileId,removed,file(id,name,mimeType,createdTime,modifiedTime,parents,webViewLink,webContentLink,thumbnailLink,shared,owners,version,md5Checksum)),nextPageToken,newStartPageToken"
                    },
                    db_conn_pool=db_conn_pool
                )
                
                if "changes" in drive_changes:
                    # Convert to GoogleDriveChange objects
                    for change_data in drive_changes["changes"]:
                        change = GoogleDriveChange(
                            id=change_data.get("id", ""),
                            file_id=change_data.get("fileId"),
                            removed=change_data.get("removed", False)
                        )
                        
                        if "file" in change_data and change_data["file"]:
                            change.file = self.drive_service._dict_to_file(change_data["file"])
                        
                        changes.append(change)
            
            else:
                # First sync - get all files and determine changes
                current_files = await self.drive_service.get_files(
                    user_id=subscription.user_id,
                    parent_id=subscription.folder_id,
                    page_size=1000,
                    db_conn_pool=db_conn_pool
                )
                
                changes = await self._determine_changes(current_files, sync_state)
            
            # Process changes
            processed_changes = []
            error_count = 0
            
            for change in changes:
                try:
                    # Create sync event
                    sync_event = await self._create_sync_event_from_change(
                        change, subscription, db_conn_pool
                    )
                    
                    if sync_event:
                        # Add to processing queue
                        await self.event_queue.put(sync_event)
                        processed_changes.append(sync_event)
                
                except Exception as e:
                    logger.error(f"Error processing change {change.id}: {e}")
                    error_count += 1
                    continue
            
            # Update sync state
            if changes:
                # Get next page token from response
                # For mock implementation, generate a new token
                sync_state.page_token = f"page_token_{datetime.now().timestamp()}"
            
            sync_state.last_incremental_sync = datetime.now(timezone.utc)
            sync_state.consecutive_errors = 0  # Reset on success
            
            # Update subscription
            subscription.total_synced += len(processed_changes)
            subscription.total_errors += error_count
            subscription.last_sync_time = datetime.now(timezone.utc)
            subscription.updated_at = datetime.now(timezone.utc)
            
            if self.db_pool:
                await self._update_subscription_in_db(subscription, db_conn_pool)
                await self._store_sync_state_in_db(sync_state, db_conn_pool)
            
            logger.info(f"Incremental sync completed: {len(processed_changes)} changes processed")
            
            return {
                "processed_changes": len(processed_changes),
                "error_count": error_count,
                "sync_time": sync_state.last_incremental_sync.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error in incremental sync: {e}")
            
            # Update error counts
            sync_state = self.sync_states.get(subscription.user_id)
            if sync_state:
                sync_state.error_count += 1
                sync_state.consecutive_errors += 1
            
            subscription.total_errors += 1
            
            raise
    
    async def _perform_full_sync(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ) -> Dict[str, Any]:
        """Perform full sync for subscription"""
        
        try:
            logger.info(f"Performing full sync for subscription: {subscription.id}")
            
            # Delete existing memory records for this scope
            await self._cleanup_memory_for_subscription(subscription, db_conn_pool)
            
            # Perform initial sync
            await self._perform_initial_sync(subscription, db_conn_pool)
            
            return {
                "processed_changes": subscription.total_synced,
                "sync_type": "full",
                "sync_time": subscription.last_sync_time.isoformat() if subscription.last_sync_time else None
            }
        
        except Exception as e:
            logger.error(f"Error in full sync: {e}")
            raise
    
    async def _create_sync_event_from_change(
        self,
        change: GoogleDriveChange,
        subscription: SyncSubscription,
        db_conn_pool=None
    ) -> Optional[RealtimeSyncEvent]:
        """Create sync event from Google Drive change"""
        
        try:
            if change.removed:
                # File deleted
                event_type = RealtimeSyncEventType.FILE_DELETED
                
                # Get file info from memory before deletion
                memory_record = await self.memory_service.get_file_record(
                    change.file_id, subscription.user_id
                )
                
                if memory_record:
                    sync_event = RealtimeSyncEvent(
                        id=self._generate_event_id(),
                        event_type=event_type,
                        file_id=change.file_id,
                        file_name=memory_record.name,
                        mime_type=memory_record.mime_type,
                        user_id=subscription.user_id,
                        timestamp=datetime.now(timezone.utc),
                        old_name=memory_record.name,
                        old_parent_ids=memory_record.parents,
                        change_id=change.id
                    )
                    
                    # Delete from memory
                    await self.memory_service.delete_file_record(
                        change.file_id, subscription.user_id
                    )
                    
                    return sync_event
            
            elif change.file:
                file = change.file
                
                # Get old record from memory
                old_record = await self.memory_service.get_file_record(
                    file.id, subscription.user_id
                )
                
                # Determine event type
                if old_record:
                    # File updated
                    event_type = RealtimeSyncEventType.FILE_UPDATED
                    
                    # Check for move/rename
                    name_changed = old_record.name != file.name
                    parents_changed = set(old_record.parents) != set(file.parents)
                    shared_changed = old_record.shared != file.shared
                    
                    if name_changed:
                        if parents_changed:
                            event_type = RealtimeSyncEventType.FILE_MOVED
                        else:
                            event_type = RealtimeSyncEventType.FILE_UPDATED
                    
                    if shared_changed:
                        event_type = RealtimeSyncEventType.FILE_SHARED
                else:
                    # New file
                    event_type = RealtimeSyncEventType.FILE_CREATED
                
                # Update memory
                memory_record = await self.memory_service.index_file(
                    file, subscription.user_id, True, True
                )
                
                # Create sync event
                sync_event = RealtimeSyncEvent(
                    id=self._generate_event_id(),
                    event_type=event_type,
                    file_id=file.id,
                    file_name=file.name,
                    mime_type=file.mime_type,
                    user_id=subscription.user_id,
                    timestamp=datetime.now(timezone.utc),
                    old_name=old_record.name if old_record else None,
                    new_name=file.name,
                    old_parent_ids=old_record.parents if old_record else None,
                    new_parent_ids=file.parents,
                    old_shared=old_record.shared if old_record else None,
                    new_shared=file.shared,
                    content_hash=self._calculate_file_hash(file),
                    change_id=change.id,
                    processing_status="completed",
                    memory_updated=True
                )
                
                return sync_event
            
            return None
        
        except Exception as e:
            logger.error(f"Error creating sync event from change: {e}")
            return None
    
    async def _create_sync_event_from_webhook(
        self,
        change_data: Dict[str, Any],
        subscription: SyncSubscription,
        db_conn_pool=None
    ) -> Optional[RealtimeSyncEvent]:
        """Create sync event from webhook notification"""
        
        try:
            # Extract change information from webhook data
            file_id = change_data.get("fileId")
            change_type = change_data.get("type", "change")
            
            if not file_id:
                return None
            
            # Get current file information
            file = await self.drive_service.get_file(
                subscription.user_id, file_id, db_conn_pool
            )
            
            if not file:
                return None
            
            # Determine event type from webhook change type
            event_type_map = {
                "create": RealtimeSyncEventType.FILE_CREATED,
                "update": RealtimeSyncEventType.FILE_UPDATED,
                "delete": RealtimeSyncEventType.FILE_DELETED,
                "move": RealtimeSyncEventType.FILE_MOVED,
                "share": RealtimeSyncEventType.FILE_SHARED
            }
            
            event_type = event_type_map.get(
                change_type, RealtimeSyncEventType.FILE_UPDATED
            )
            
            # Create sync event
            sync_event = RealtimeSyncEvent(
                id=self._generate_event_id(),
                event_type=event_type,
                file_id=file_id,
                file_name=file.name,
                mime_type=file.mime_type,
                user_id=subscription.user_id,
                timestamp=datetime.now(timezone.utc),
                change_id=change_data.get("changeId")
            )
            
            return sync_event
        
        except Exception as e:
            logger.error(f"Error creating sync event from webhook: {e}")
            return None
    
    async def _process_sync_event(
        self,
        event: RealtimeSyncEvent,
        db_conn_pool=None
    ) -> bool:
        """Process sync event"""
        
        try:
            event.processing_status = "processing"
            event.processing_time = datetime.now(timezone.utc)
            
            # Add to history
            self.events_history.append(event)
            if len(self.events_history) > self.max_events_history:
                self.events_history.pop(0)
            
            # Call global handlers
            for handler in self.global_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Global handler error: {e}")
            
            # Call event-specific handlers
            event_handlers = self.event_handlers.get(event.event_type, [])
            for handler in event_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
            
            # Send webhook if configured
            subscription = self._get_subscription_for_event(event)
            if subscription and subscription.webhook_url:
                await self._send_webhook_notification(event, subscription)
            
            # Update statistics
            self.total_events_processed += 1
            
            event.processing_status = "completed"
            event.memory_updated = True
            
            logger.debug(f"Processed sync event: {event.event_type.value} - {event.file_name}")
            
            return True
        
        except Exception as e:
            event.processing_status = "failed"
            event.error_message = str(e)
            self.total_errors += 1
            
            logger.error(f"Error processing sync event: {e}")
            return False
    
    def _filter_files(
        self,
        files: List[GoogleDriveFile],
        subscription: SyncSubscription
    ) -> List[GoogleDriveFile]:
        """Filter files based on subscription criteria"""
        
        filtered = []
        
        for file in files:
            # Skip trashed files
            if file.trashed:
                continue
            
            # Filter by file types
            if subscription.file_types:
                if not any(
                    file.mime_type.startswith(ft.replace("*", ""))
                    for ft in subscription.file_types
                ):
                    continue
            
            # Filter by size
            if file.size > subscription.max_file_size:
                continue
            
            filtered.append(file)
        
        return filtered
    
    def _should_sync_now(self, subscription: SyncSubscription) -> bool:
        """Check if subscription should sync now"""
        
        # Check if already syncing
        if subscription.user_id in self.active_syncs:
            return False
        
        # Check sync interval
        if (subscription.last_sync_time and
            datetime.now(timezone.utc) - subscription.last_sync_time < 
            timedelta(seconds=subscription.sync_interval)):
            return False
        
        return True
    
    async def _start_change_notifications(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ):
        """Start real-time change notifications"""
        
        try:
            channel_data = {
                "id": subscription.id,
                "type": "web_hook",
                "address": subscription.webhook_url,
                "token": f"channel_token_{subscription.id}",
                "expiration": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000)
            }
            
            response = await self.drive_service._make_request(
                user_id=subscription.user_id,
                method="POST",
                endpoint="changes/watch",
                data=channel_data,
                db_conn_pool=db_conn_pool
            )
            
            if response.get("id") and response.get("resourceId"):
                subscription.change_webhook_active = True
                subscription.last_sync_token = response.get("resourceId")
                subscription.updated_at = datetime.now(timezone.utc)
                
                if self.db_pool:
                    await self._update_subscription_in_db(subscription, db_conn_pool)
                
                logger.info(f"Started change notifications for subscription: {subscription.id}")
        
        except Exception as e:
            logger.error(f"Error starting change notifications: {e}")
            subscription.change_webhook_active = False
    
    async def _stop_change_notifications(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ):
        """Stop real-time change notifications"""
        
        try:
            if not subscription.change_webhook_active or not subscription.last_sync_token:
                return
            
            response = await self.drive_service._make_request(
                user_id=subscription.user_id,
                method="POST",
                endpoint="changes/stop",
                data={
                    "id": subscription.id,
                    "resourceId": subscription.last_sync_token
                },
                db_conn_pool=db_conn_pool
            )
            
            subscription.change_webhook_active = False
            subscription.last_sync_token = None
            subscription.updated_at = datetime.now(timezone.utc)
            
            if self.db_pool:
                await self._update_subscription_in_db(subscription, db_conn_pool)
            
            logger.info(f"Stopped change notifications for subscription: {subscription.id}")
        
        except Exception as e:
            logger.error(f"Error stopping change notifications: {e}")
    
    async def _send_webhook_notification(
        self,
        event: RealtimeSyncEvent,
        subscription: SyncSubscription
    ):
        """Send webhook notification for event"""
        
        try:
            if not subscription.webhook_url:
                return
            
            # Check if event type is in webhook events
            if subscription.webhook_events and event.event_type not in subscription.webhook_events:
                return
            
            # Prepare webhook payload
            payload = {
                "event": {
                    "id": event.id,
                    "type": event.event_type.value,
                    "file_id": event.file_id,
                    "file_name": event.file_name,
                    "mime_type": event.mime_type,
                    "timestamp": event.timestamp.isoformat(),
                    "old_name": event.old_name,
                    "new_name": event.new_name,
                    "old_parent_ids": event.old_parent_ids,
                    "new_parent_ids": event.new_parent_ids,
                    "old_shared": event.old_shared,
                    "new_shared": event.new_shared
                },
                "subscription": {
                    "id": subscription.id,
                    "user_id": subscription.user_id,
                    "folder_id": subscription.folder_id
                },
                "atom": {
                    "service": "google_drive",
                    "version": "1.0.0",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    subscription.webhook_url,
                    json=payload,
                    timeout=30,
                    headers={
                        "User-Agent": "ATOM-GoogleDrive/1.0",
                        "X-ATOM-Event": "google_drive_sync",
                        "X-ATOM-Signature": self._calculate_webhook_signature(payload)
                    }
                ) as response:
                    if response.status == 200:
                        event.webhook_sent = True
                        logger.debug(f"Webhook sent for event: {event.id}")
                    else:
                        logger.warning(f"Webhook failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
    
    async def _cleanup_memory_for_subscription(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ):
        """Clean up memory records for subscription scope"""
        
        try:
            # Get all files in subscription scope
            files = await self.drive_service.get_files(
                user_id=subscription.user_id,
                parent_id=subscription.folder_id,
                page_size=1000,
                db_conn_pool=db_conn_pool
            )
            
            # Delete from memory
            for file in files:
                await self.memory_service.delete_file_record(
                    file.id, subscription.user_id
                )
            
            logger.info(f"Cleaned up memory for subscription: {subscription.id}")
        
        except Exception as e:
            logger.error(f"Error cleaning up memory: {e}")
    
    def _get_subscription_for_event(self, event: RealtimeSyncEvent) -> Optional[SyncSubscription]:
        """Get subscription for sync event"""
        
        for subscription in self.subscriptions.values():
            if subscription.user_id == event.user_id and subscription.active:
                # Check if event is in subscription's event types
                if event.event_type in subscription.event_types:
                    return subscription
        
        return None
    
    def _calculate_file_hash(self, file: GoogleDriveFile) -> str:
        """Calculate hash for file"""
        hash_string = (
            f"{file.id}|{file.name}|{file.mime_type}|"
            f"{file.modified_time.isoformat() if file.modified_time else ''}|"
            f"{file.size}|{json.dumps(file.parents, sort_keys=True)}"
        )
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def _calculate_webhook_signature(self, payload: Dict[str, Any]) -> str:
        """Calculate webhook signature"""
        import hmac
        import hashlib
        
        # Use subscription secret (mock for now)
        secret = "webhook_secret"
        
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def _generate_subscription_id(self) -> str:
        """Generate subscription ID"""
        return f"sync_sub_{datetime.now().timestamp()}"
    
    def _generate_event_id(self) -> str:
        """Generate event ID"""
        return f"sync_event_{datetime.now().timestamp()}"
    
    async def _determine_changes(
        self,
        current_files: List[GoogleDriveFile],
        sync_state: SyncState
    ) -> List[GoogleDriveChange]:
        """Determine changes by comparing with stored hashes"""
        
        try:
            changes = []
            current_file_hashes = {
                file.id: self._calculate_file_hash(file)
                for file in current_files
            }
            
            # New or modified files
            for file_id, current_hash in current_file_hashes.items():
                stored_hash = sync_state.files_hash.get(file_id)
                
                if not stored_hash:
                    # New file
                    change = GoogleDriveChange(
                        id=f"new_{file_id}_{datetime.now().timestamp()}",
                        file_id=file_id,
                        removed=False
                    )
                    change.file = next(f for f in current_files if f.id == file_id)
                    changes.append(change)
                
                elif stored_hash != current_hash:
                    # Modified file
                    change = GoogleDriveChange(
                        id=f"modified_{file_id}_{datetime.now().timestamp()}",
                        file_id=file_id,
                        removed=False
                    )
                    change.file = next(f for f in current_files if f.id == file_id)
                    changes.append(change)
            
            # Deleted files
            for file_id in sync_state.files_hash:
                if file_id not in current_file_hashes:
                    change = GoogleDriveChange(
                        id=f"deleted_{file_id}_{datetime.now().timestamp()}",
                        file_id=file_id,
                        removed=True
                    )
                    changes.append(change)
            
            return changes
        
        except Exception as e:
            logger.error(f"Error determining changes: {e}")
            return []
    
    async def _update_file_hashes(
        self,
        files: List[GoogleDriveFile],
        sync_state: SyncState,
        db_conn_pool=None
    ):
        """Update file hashes in sync state"""
        
        try:
            new_file_hashes = {
                file.id: self._calculate_file_hash(file)
                for file in files
            }
            
            sync_state.files_hash = new_file_hashes
        
        except Exception as e:
            logger.error(f"Error updating file hashes: {e}")
    
    # Database operations
    async def _store_subscription_in_db(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ):
        """Store subscription in database"""
        if not db_conn_pool:
            return
        
        try:
            query = """
            INSERT INTO google_drive_realtime_sync_subscriptions (
                id, user_id, folder_id, include_subfolders, file_types,
                event_types, webhook_url, webhook_events, memory_sync,
                realtime_notifications, change_webhook_active,
                last_sync_token, last_change_id, sync_interval,
                max_file_size, active, created_at, updated_at,
                total_synced, total_errors, last_sync_time
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18,
                        $19, $20, $21, $22, $23)
            ON CONFLICT (id) DO UPDATE SET
                folder_id = EXCLUDED.folder_id,
                include_subfolders = EXCLUDED.include_subfolders,
                file_types = EXCLUDED.file_types,
                event_types = EXCLUDED.event_types,
                webhook_url = EXCLUDED.webhook_url,
                webhook_events = EXCLUDED.webhook_events,
                memory_sync = EXCLUDED.memory_sync,
                realtime_notifications = EXCLUDED.realtime_notifications,
                change_webhook_active = EXCLUDED.change_webhook_active,
                last_sync_token = EXCLUDED.last_sync_token,
                last_change_id = EXCLUDED.last_change_id,
                sync_interval = EXCLUDED.sync_interval,
                max_file_size = EXCLUDED.max_file_size,
                active = EXCLUDED.active,
                updated_at = EXCLUDED.updated_at,
                total_synced = EXCLUDED.total_synced,
                total_errors = EXCLUDED.total_errors,
                last_sync_time = EXCLUDED.last_sync_time
            """
            
            await db_conn_pool.execute(
                query,
                subscription.id,
                subscription.user_id,
                subscription.folder_id,
                subscription.include_subfolders,
                json.dumps(subscription.file_types),
                json.dumps([et.value for et in subscription.event_types]),
                subscription.webhook_url,
                json.dumps([et.value for et in subscription.webhook_events]),
                subscription.memory_sync,
                subscription.realtime_notifications,
                subscription.change_webhook_active,
                subscription.last_sync_token,
                subscription.last_change_id,
                subscription.sync_interval,
                subscription.max_file_size,
                subscription.active,
                subscription.created_at,
                subscription.updated_at,
                subscription.total_synced,
                subscription.total_errors,
                subscription.last_sync_time
            )
        
        except Exception as e:
            logger.error(f"Error storing subscription in database: {e}")
    
    async def _update_subscription_in_db(
        self,
        subscription: SyncSubscription,
        db_conn_pool=None
    ):
        """Update subscription in database"""
        await self._store_subscription_in_db(subscription, db_conn_pool)
    
    async def _delete_subscription_from_db(
        self,
        subscription_id: str,
        db_conn_pool=None
    ):
        """Delete subscription from database"""
        if not db_conn_pool:
            return
        
        try:
            query = "DELETE FROM google_drive_realtime_sync_subscriptions WHERE id = $1"
            await db_conn_pool.execute(query, subscription_id)
        
        except Exception as e:
            logger.error(f"Error deleting subscription from database: {e}")
    
    async def _store_sync_state_in_db(
        self,
        sync_state: SyncState,
        db_conn_pool=None
    ):
        """Store sync state in database"""
        if not db_conn_pool:
            return
        
        try:
            query = """
            INSERT INTO google_drive_realtime_sync_states (
                user_id, page_token, next_page_token, start_page_token,
                largest_change_id, last_full_sync, last_incremental_sync,
                files_hash, folders_hash, sync_history, processing_changes,
                error_count, consecutive_errors
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13)
            ON CONFLICT (user_id) DO UPDATE SET
                page_token = EXCLUDED.page_token,
                next_page_token = EXCLUDED.next_page_token,
                start_page_token = EXCLUDED.start_page_token,
                largest_change_id = EXCLUDED.largest_change_id,
                last_full_sync = EXCLUDED.last_full_sync,
                last_incremental_sync = EXCLUDED.last_incremental_sync,
                files_hash = EXCLUDED.files_hash,
                folders_hash = EXCLUDED.folders_hash,
                sync_history = EXCLUDED.sync_history,
                processing_changes = EXCLUDED.processing_changes,
                error_count = EXCLUDED.error_count,
                consecutive_errors = EXCLUDED.consecutive_errors
            """
            
            await db_conn_pool.execute(
                query,
                sync_state.user_id,
                sync_state.page_token,
                sync_state.next_page_token,
                sync_state.start_page_token,
                sync_state.largest_change_id,
                sync_state.last_full_sync,
                sync_state.last_incremental_sync,
                json.dumps(sync_state.files_hash),
                json.dumps(sync_state.folders_hash),
                json.dumps(list(sync_state.sync_history)),
                json.dumps(list(sync_state.processing_changes)),
                sync_state.error_count,
                sync_state.consecutive_errors
            )
        
        except Exception as e:
            logger.error(f"Error storing sync state in database: {e}")
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get sync service statistics"""
        
        total_subscriptions = len(self.subscriptions)
        active_subscriptions = len([
            s for s in self.subscriptions.values() if s.active
        ])
        
        event_type_counts = {}
        for event in self.events_history:
            event_type = event.event_type.value
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        return {
            "service_running": self.running,
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "total_events_processed": self.total_events_processed,
            "total_errors": self.total_errors,
            "events_in_queue": self.event_queue.qsize(),
            "active_syncs": len(self.active_syncs),
            "event_types": event_type_counts,
            "background_tasks": len(self.background_tasks),
            "processing_workers": len([t for t in self.processing_tasks if not t.done()]),
            "event_handlers": {
                "global": len(self.global_handlers),
                "type_specific": sum(len(handlers) for handlers in self.event_handlers.values())
            },
            "webhook_handlers": len(self.webhook_handlers),
            "events_history_size": len(self.events_history)
        }
    
    def get_subscription_statistics(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for specific subscription"""
        
        if subscription_id not in self.subscriptions:
            return None
        
        subscription = self.subscriptions[subscription_id]
        sync_state = self.sync_states.get(subscription.user_id)
        
        return {
            "subscription": {
                "id": subscription.id,
                "user_id": subscription.user_id,
                "folder_id": subscription.folder_id,
                "active": subscription.active,
                "change_webhook_active": subscription.change_webhook_active,
                "total_synced": subscription.total_synced,
                "total_errors": subscription.total_errors,
                "last_sync_time": subscription.last_sync_time.isoformat() if subscription.last_sync_time else None,
                "created_at": subscription.created_at.isoformat()
            },
            "sync_state": {
                "last_full_sync": sync_state.last_full_sync.isoformat() if sync_state and sync_state.last_full_sync else None,
                "last_incremental_sync": sync_state.last_incremental_sync.isoformat() if sync_state and sync_state.last_incremental_sync else None,
                "error_count": sync_state.error_count if sync_state else 0,
                "consecutive_errors": sync_state.consecutive_errors if sync_state else 0,
                "files_tracked": len(sync_state.files_hash) if sync_state else 0
            }
        }

# Global service instance
_google_drive_realtime_sync_service: Optional[GoogleDriveRealtimeSyncService] = None

def get_google_drive_realtime_sync_service(
    drive_service: GoogleDriveService,
    memory_service: GoogleDriveMemoryService,
    db_pool=None
) -> GoogleDriveRealtimeSyncService:
    """Get global Google Drive real-time sync service instance"""
    global _google_drive_realtime_sync_service
    
    if _google_drive_realtime_sync_service is None:
        _google_drive_realtime_sync_service = GoogleDriveRealtimeSyncService(
            drive_service, memory_service, db_pool
        )
        
        # Start the service
        _google_drive_realtime_sync_service.start()
    
    return _google_drive_realtime_sync_service

# Export classes
__all__ = [
    "GoogleDriveRealtimeSyncService",
    "RealtimeSyncEvent",
    "SyncSubscription",
    "SyncState",
    "RealtimeSyncEventType",
    "get_google_drive_realtime_sync_service"
]