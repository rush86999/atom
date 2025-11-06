"""
Google Drive Real-time Sync and Webhooks
Real-time file synchronization and change notifications for Google Drive
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

class SyncEventType(Enum):
    """Sync event types"""
    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    PERMISSION_CHANGED = "permission_changed"
    FOLDER_CREATED = "folder_created"
    FOLDER_UPDATED = "folder_updated"
    FOLDER_DELETED = "folder_deleted"

@dataclass
class GoogleDriveSyncEvent:
    """Google Drive sync event model"""
    id: str
    event_type: SyncEventType
    file_id: str
    file_name: str
    mime_type: str
    user_id: str
    timestamp: datetime
    old_parent_ids: Optional[List[str]] = None
    new_parent_ids: Optional[List[str]] = None
    old_name: Optional[str] = None
    new_name: Optional[str] = None
    file_content_hash: Optional[str] = None
    change_id: Optional[str] = None
    processed: bool = False
    error_message: Optional[str] = None

@dataclass
class SyncSubscription:
    """Sync subscription model"""
    id: str
    user_id: str
    folder_id: Optional[str] = None
    include_subfolders: bool = True
    file_types: List[str] = field(default_factory=list)
    event_types: List[SyncEventType] = field(default_factory=lambda: list(SyncEventType))
    webhook_url: Optional[str] = None
    last_sync_token: Optional[str] = None
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class SyncState:
    """Sync state model"""
    user_id: str
    page_token: Optional[str] = None
    next_page_token: Optional[str] = None
    start_page_token: Optional[str] = None
    largest_change_id: Optional[str] = None
    last_sync_time: Optional[datetime] = None
    files_hash: Dict[str, str] = field(default_factory=dict)
    folders_hash: Dict[str, str] = field(default_factory=dict)

class GoogleDriveSyncService:
    """Google Drive real-time synchronization service"""
    
    def __init__(self, drive_service: GoogleDriveService, db_pool=None):
        self.drive_service = drive_service
        self.db_pool = db_pool
        self.subscriptions: Dict[str, SyncSubscription] = {}
        self.sync_states: Dict[str, SyncState] = {}
        self.event_handlers: Dict[SyncEventType, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
        self.change_webhook_handlers: Dict[str, Callable] = {}
        self.sync_interval = timedelta(minutes=5)
        self.max_sync_retries = 3
        self.max_events_history = 10000
        self.events_history: List[GoogleDriveSyncEvent] = []
        self.active_syncs: Set[str] = set()
        self.cleanup_interval = timedelta(hours=1)
    
    def register_event_handler(
        self, 
        event_type: SyncEventType, 
        handler: Callable
    ):
        """Register handler for specific sync event type"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered sync handler for event: {event_type.value}")
    
    def register_global_handler(self, handler: Callable):
        """Register global handler for all sync events"""
        self.global_handlers.append(handler)
        logger.info("Registered global sync handler")
    
    def register_change_webhook_handler(self, subscription_id: str, handler: Callable):
        """Register webhook handler for change notifications"""
        self.change_webhook_handlers[subscription_id] = handler
        logger.info(f"Registered change webhook handler for subscription: {subscription_id}")
    
    async def create_subscription(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        include_subfolders: bool = True,
        file_types: Optional[List[str]] = None,
        event_types: Optional[List[SyncEventType]] = None,
        webhook_url: Optional[str] = None,
        db_conn_pool=None
    ) -> SyncSubscription:
        """Create new sync subscription"""
        
        try:
            subscription_id = self._generate_subscription_id()
            
            subscription = SyncSubscription(
                id=subscription_id,
                user_id=user_id,
                folder_id=folder_id,
                include_subfolders=include_subfolders,
                file_types=file_types or [],
                event_types=event_types or list(SyncEventType),
                webhook_url=webhook_url
            )
            
            # Store subscription
            self.subscriptions[subscription_id] = subscription
            
            # Initialize sync state
            sync_state = SyncState(user_id=user_id)
            self.sync_states[user_id] = sync_state
            
            # Store in database
            if self.db_pool:
                await self._store_subscription_in_db(subscription, db_conn_pool)
            
            # Get initial page token
            await self._initialize_sync_state(user_id, db_conn_pool)
            
            logger.info(f"Created sync subscription: {subscription_id} for user {user_id}")
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating sync subscription: {e}")
            raise
    
    async def delete_subscription(
        self,
        subscription_id: str,
        db_conn_pool=None
    ) -> bool:
        """Delete sync subscription"""
        
        try:
            if subscription_id not in self.subscriptions:
                return False
            
            subscription = self.subscriptions[subscription_id]
            
            # Stop channel if active
            await self.stop_channel(subscription_id, db_conn_pool)
            
            # Remove from memory
            del self.subscriptions[subscription_id]
            del self.sync_states[subscription.user_id]
            
            # Remove webhook handler
            if subscription_id in self.change_webhook_handlers:
                del self.change_webhook_handlers[subscription_id]
            
            # Remove from database
            if self.db_pool:
                await self._delete_subscription_from_db(subscription_id, db_conn_pool)
            
            logger.info(f"Deleted sync subscription: {subscription_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting sync subscription: {e}")
            return False
    
    async def start_channel(
        self,
        subscription_id: str,
        db_conn_pool=None
    ) -> Dict[str, Any]:
        """Start Google Drive change channel"""
        
        try:
            if subscription_id not in self.subscriptions:
                return {"success": False, "error": "Subscription not found"}
            
            subscription = self.subscriptions[subscription_id]
            
            # Create channel using Google Drive API
            channel_data = {
                "id": subscription_id,
                "type": "web_hook",
                "address": subscription.webhook_url,
                "token": f"channel_token_{subscription_id}",
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
                # Update subscription with channel info
                subscription.last_sync_token = response.get("resourceId")
                subscription.updated_at = datetime.now(timezone.utc)
                
                # Store in database
                if self.db_pool:
                    await self._update_subscription_in_db(subscription, db_conn_pool)
                
                logger.info(f"Started change channel for subscription: {subscription_id}")
                
                return {
                    "success": True,
                    "channel_id": response["id"],
                    "resource_id": response["resourceId"],
                    "expiration": response.get("expiration"),
                    "token": response.get("token")
                }
            
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Unknown error")
                }
        
        except Exception as e:
            logger.error(f"Error starting change channel: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def stop_channel(
        self,
        subscription_id: str,
        db_conn_pool=None
    ) -> bool:
        """Stop Google Drive change channel"""
        
        try:
            if subscription_id not in self.subscriptions:
                return False
            
            subscription = self.subscriptions[subscription_id]
            
            if not subscription.last_sync_token:
                return True  # No channel to stop
            
            # Stop channel using Google Drive API
            response = await self.drive_service._make_request(
                user_id=subscription.user_id,
                method="POST",
                endpoint=f"changes/stop",
                data={
                    "id": subscription_id,
                    "resourceId": subscription.last_sync_token
                },
                db_conn_pool=db_conn_pool
            )
            
            # Clear sync token
            subscription.last_sync_token = None
            subscription.updated_at = datetime.now(timezone.utc)
            
            # Store in database
            if self.db_pool:
                await self._update_subscription_in_db(subscription, db_conn_pool)
            
            logger.info(f"Stopped change channel for subscription: {subscription_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error stopping change channel: {e}")
            return False
    
    async def sync_files(
        self,
        user_id: str,
        subscription_id: Optional[str] = None,
        db_conn_pool=None
    ) -> Dict[str, Any]:
        """Perform manual file sync"""
        
        try:
            if user_id in self.active_syncs:
                return {
                    "success": False,
                    "error": "Sync already in progress"
                }
            
            self.active_syncs.add(user_id)
            
            try:
                # Get subscription or sync all files
                subscription = None
                if subscription_id and subscription_id in self.subscriptions:
                    subscription = self.subscriptions[subscription_id]
                
                # Get current sync state
                sync_state = self.sync_states.get(user_id, SyncState(user_id=user_id))
                
                # Get changes from Google Drive
                if sync_state.page_token:
                    # Get changes since last sync
                    changes = await self._get_changes(user_id, sync_state.page_token, db_conn_pool)
                else:
                    # Get all files and create change events
                    files = await self.drive_service.get_files(
                        user_id=user_id,
                        parent_id=subscription.folder_id if subscription else None,
                        page_size=1000,
                        db_conn_pool=db_conn_pool
                    )
                    
                    changes = self._create_change_events_from_files(user_id, files, sync_state)
                
                # Process changes
                processed_changes = []
                for change in changes:
                    try:
                        # Determine event type
                        if change.removed:
                            event_type = SyncEventType.FILE_DELETED
                            sync_event = await self._create_sync_event(
                                user_id=user_id,
                                change=change,
                                event_type=event_type
                            )
                        else:
                            event_type = await self._determine_event_type(change, sync_state)
                            sync_event = await self._create_sync_event(
                                user_id=user_id,
                                change=change,
                                event_type=event_type
                            )
                        
                        if sync_event:
                            # Filter by subscription
                            if subscription and not self._should_include_event(sync_event, subscription):
                                continue
                            
                            # Process event
                            await self._process_sync_event(sync_event, db_conn_pool)
                            processed_changes.append(sync_event)
                    
                    except Exception as e:
                        logger.error(f"Error processing change {change.id}: {e}")
                        continue
                
                # Update sync state
                if changes and not sync_state.page_token:
                    # First sync - set start page token
                    response = await self.drive_service._make_request(
                        user_id=user_id,
                        method="GET",
                        endpoint="changes/startPageToken",
                        db_conn_pool=db_conn_pool
                    )
                    
                    if response.get("startPageToken"):
                        sync_state.start_page_token = response["startPageToken"]
                        sync_state.page_token = response["startPageToken"]
                
                elif changes:
                    # Get next page token from changes response
                    next_page_token = self._extract_next_page_token(changes)
                    if next_page_token:
                        sync_state.page_token = next_page_token
                
                sync_state.last_sync_time = datetime.now(timezone.utc)
                
                # Update file hashes
                await self._update_file_hashes(user_id, db_conn_pool)
                
                # Store sync state
                self.sync_states[user_id] = sync_state
                
                # Store in database
                if self.db_pool:
                    await self._store_sync_state_in_db(sync_state, db_conn_pool)
                
                result = {
                    "success": True,
                    "processed_changes": len(processed_changes),
                    "sync_time": sync_state.last_sync_time.isoformat(),
                    "next_page_token": sync_state.page_token
                }
                
                logger.info(f"Sync completed for user {user_id}: {len(processed_changes)} changes processed")
                
                return result
            
            finally:
                self.active_syncs.discard(user_id)
        
        except Exception as e:
            logger.error(f"Error during sync for user {user_id}: {e}")
            self.active_syncs.discard(user_id)
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_changes(
        self,
        user_id: str,
        page_token: str,
        db_conn_pool=None
    ) -> List[GoogleDriveChange]:
        """Get changes from Google Drive"""
        
        try:
            params = {
                "pageToken": page_token,
                "pageSize": 1000,
                "fields": "changes(id,fileId,removed,file(fileId,name,mimeType,createdTime,modifiedTime,parents)),nextPageToken,newStartPageToken"
            }
            
            all_changes = []
            
            while True:
                response = await self.drive_service._make_request(
                    user_id=user_id,
                    method="GET",
                    endpoint="changes",
                    params=params,
                    db_conn_pool=db_conn_pool
                )
                
                if "changes" in response:
                    # Convert to GoogleDriveChange objects
                    changes = []
                    for change_data in response["changes"]:
                        change = GoogleDriveChange(
                            id=change_data.get("id", ""),
                            file_id=change_data.get("fileId"),
                            removed=change_data.get("removed", False)
                        )
                        
                        if "file" in change_data and change_data["file"]:
                            file_data = change_data["file"]
                            change.file = self.drive_service._dict_to_file(file_data)
                        
                        changes.append(change)
                    
                    all_changes.extend(changes)
                
                # Check for next page
                if "nextPageToken" in response:
                    params["pageToken"] = response["nextPageToken"]
                else:
                    break
            
            return all_changes
        
        except Exception as e:
            logger.error(f"Error getting changes: {e}")
            return []
    
    async def _create_change_events_from_files(
        self,
        user_id: str,
        files: List[GoogleDriveFile],
        sync_state: SyncState
    ) -> List[GoogleDriveChange]:
        """Create change events from files list"""
        
        try:
            current_files_hash = {file.id: self._calculate_file_hash(file) for file in files}
            
            # Compare with stored hashes
            changes = []
            
            # New or modified files
            for file_id, current_hash in current_files_hash.items():
                stored_hash = sync_state.files_hash.get(file_id)
                
                if not stored_hash:
                    # New file
                    change = GoogleDriveChange(
                        id=f"new_{file_id}_{datetime.now().timestamp()}",
                        file_id=file_id,
                        removed=False
                    )
                    change.file = next(f for f in files if f.id == file_id)
                    changes.append(change)
                
                elif stored_hash != current_hash:
                    # Modified file
                    change = GoogleDriveChange(
                        id=f"modified_{file_id}_{datetime.now().timestamp()}",
                        file_id=file_id,
                        removed=False
                    )
                    change.file = next(f for f in files if f.id == file_id)
                    changes.append(change)
            
            # Deleted files
            for file_id in sync_state.files_hash:
                if file_id not in current_files_hash:
                    change = GoogleDriveChange(
                        id=f"deleted_{file_id}_{datetime.now().timestamp()}",
                        file_id=file_id,
                        removed=True
                    )
                    changes.append(change)
            
            return changes
        
        except Exception as e:
            logger.error(f"Error creating change events from files: {e}")
            return []
    
    async def _determine_event_type(
        self,
        change: GoogleDriveChange,
        sync_state: SyncState
    ) -> SyncEventType:
        """Determine event type from change"""
        
        try:
            if not change.file:
                return SyncEventType.FILE_DELETED
            
            # Check if file or folder
            if change.file.mime_type == "application/vnd.google-apps.folder":
                # Folder event
                stored_hash = sync_state.folders_hash.get(change.file_id)
                current_hash = self._calculate_file_hash(change.file)
                
                if not stored_hash:
                    return SyncEventType.FOLDER_CREATED
                else:
                    return SyncEventType.FOLDER_UPDATED
            else:
                # File event
                stored_hash = sync_state.files_hash.get(change.file_id)
                current_hash = self._calculate_file_hash(change.file)
                
                if not stored_hash:
                    return SyncEventType.FILE_CREATED
                else:
                    return SyncEventType.FILE_UPDATED
        
        except Exception as e:
            logger.error(f"Error determining event type: {e}")
            return SyncEventType.FILE_UPDATED
    
    async def _create_sync_event(
        self,
        user_id: str,
        change: GoogleDriveChange,
        event_type: SyncEventType
    ) -> Optional[GoogleDriveSyncEvent]:
        """Create sync event from change"""
        
        try:
            if change.file_id:
                file_name = change.file.name if change.file else ""
                mime_type = change.file.mime_type if change.file else ""
                change_id = change.id
            else:
                return None
            
            event = GoogleDriveSyncEvent(
                id=self._generate_event_id(),
                event_type=event_type,
                file_id=change.file_id,
                file_name=file_name,
                mime_type=mime_type,
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
                change_id=change_id
            )
            
            # Calculate file content hash
            if change.file:
                event.file_content_hash = self._calculate_file_hash(change.file)
            
            return event
        
        except Exception as e:
            logger.error(f"Error creating sync event: {e}")
            return None
    
    def _calculate_file_hash(self, file: GoogleDriveFile) -> str:
        """Calculate hash for file"""
        try:
            # Create hash from file metadata
            hash_string = (
                f"{file.id}|{file.name}|{file.mime_type}|"
                f"{file.modified_time.isoformat() if file.modified_time else ''}|"
                f"{file.size}|{json.dumps(file.parents, sort_keys=True)}"
            )
            
            return hashlib.md5(hash_string.encode()).hexdigest()
        
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ""
    
    def _should_include_event(self, event: GoogleDriveSyncEvent, subscription: SyncSubscription) -> bool:
        """Check if event should be included for subscription"""
        
        # Check file types
        if subscription.file_types:
            if not any(event.mime_type.startswith(ft.replace("*", "")) for ft in subscription.file_types):
                return False
        
        # Check event types
        if event.event_type not in subscription.event_types:
            return False
        
        return True
    
    async def _process_sync_event(
        self,
        event: GoogleDriveSyncEvent,
        db_conn_pool=None
    ) -> bool:
        """Process sync event"""
        
        try:
            # Add to history
            self.events_history.append(event)
            if len(self.events_history) > self.max_events_history:
                self.events_history.pop(0)
            
            # Store in database
            if self.db_pool:
                await self._store_event_in_db(event, db_conn_pool)
            
            # Call global handlers
            for handler in self.global_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Global sync handler error: {e}")
            
            # Call event-specific handlers
            event_handlers = self.event_handlers.get(event.event_type, [])
            for handler in event_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Event-specific sync handler error: {e}")
            
            event.processed = True
            logger.info(f"Processed sync event: {event.event_type.value} - {event.file_name}")
            
            return True
        
        except Exception as e:
            event.processed = False
            event.error_message = str(e)
            logger.error(f"Error processing sync event: {e}")
            return False
    
    async def _initialize_sync_state(self, user_id: str, db_conn_pool=None):
        """Initialize sync state for user"""
        
        try:
            sync_state = self.sync_states.get(user_id, SyncState(user_id=user_id))
            
            # Get start page token
            response = await self.drive_service._make_request(
                user_id=user_id,
                method="GET",
                endpoint="changes/startPageToken",
                db_conn_pool=db_conn_pool
            )
            
            if response.get("startPageToken"):
                sync_state.start_page_token = response["startPageToken"]
                sync_state.page_token = response["startPageToken"]
            
            # Store sync state
            self.sync_states[user_id] = sync_state
            
            logger.info(f"Initialized sync state for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error initializing sync state: {e}")
    
    async def _update_file_hashes(self, user_id: str, db_conn_pool=None):
        """Update file hashes in sync state"""
        
        try:
            sync_state = self.sync_states.get(user_id)
            if not sync_state:
                return
            
            # Get all files
            files = await self.drive_service.get_files(
                user_id=user_id,
                page_size=1000,
                db_conn_pool=db_conn_pool
            )
            
            # Update hashes
            new_files_hash = {}
            new_folders_hash = {}
            
            for file in files:
                file_hash = self._calculate_file_hash(file)
                
                if file.mime_type == "application/vnd.google-apps.folder":
                    new_folders_hash[file.id] = file_hash
                else:
                    new_files_hash[file.id] = file_hash
            
            sync_state.files_hash = new_files_hash
            sync_state.folders_hash = new_folders_hash
        
        except Exception as e:
            logger.error(f"Error updating file hashes: {e}")
    
    def _extract_next_page_token(self, changes: List[GoogleDriveChange]) -> Optional[str]:
        """Extract next page token from changes"""
        # This would be extracted from the API response in real implementation
        # For now, return a mock token
        return f"next_page_token_{datetime.now().timestamp()}"
    
    def _generate_subscription_id(self) -> str:
        """Generate subscription ID"""
        return f"sync_sub_{datetime.now().timestamp()}"
    
    def _generate_event_id(self) -> str:
        """Generate event ID"""
        return f"sync_event_{datetime.now().timestamp()}"
    
    async def _store_subscription_in_db(self, subscription: SyncSubscription, db_conn_pool=None):
        """Store subscription in database"""
        if not db_conn_pool:
            return
        
        try:
            query = """
            INSERT INTO google_drive_sync_subscriptions (
                id, user_id, folder_id, include_subfolders, file_types,
                event_types, webhook_url, last_sync_token, active,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                folder_id = EXCLUDED.folder_id,
                include_subfolders = EXCLUDED.include_subfolders,
                file_types = EXCLUDED.file_types,
                event_types = EXCLUDED.event_types,
                webhook_url = EXCLUDED.webhook_url,
                last_sync_token = EXCLUDED.last_sync_token,
                active = EXCLUDED.active,
                updated_at = EXCLUDED.updated_at
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
                subscription.last_sync_token,
                subscription.active,
                subscription.created_at,
                subscription.updated_at
            )
        
        except Exception as e:
            logger.error(f"Error storing subscription in database: {e}")
    
    async def _update_subscription_in_db(self, subscription: SyncSubscription, db_conn_pool=None):
        """Update subscription in database"""
        if not db_conn_pool:
            return
        
        try:
            query = """
            UPDATE google_drive_sync_subscriptions SET
                last_sync_token = $2,
                updated_at = $3
            WHERE id = $1
            """
            
            await db_conn_pool.execute(
                query,
                subscription.id,
                subscription.last_sync_token,
                subscription.updated_at
            )
        
        except Exception as e:
            logger.error(f"Error updating subscription in database: {e}")
    
    async def _delete_subscription_from_db(self, subscription_id: str, db_conn_pool=None):
        """Delete subscription from database"""
        if not db_conn_pool:
            return
        
        try:
            query = "DELETE FROM google_drive_sync_subscriptions WHERE id = $1"
            await db_conn_pool.execute(query, subscription_id)
        
        except Exception as e:
            logger.error(f"Error deleting subscription from database: {e}")
    
    async def _store_sync_state_in_db(self, sync_state: SyncState, db_conn_pool=None):
        """Store sync state in database"""
        if not db_conn_pool:
            return
        
        try:
            query = """
            INSERT INTO google_drive_sync_states (
                user_id, page_token, next_page_token, start_page_token,
                largest_change_id, last_sync_time, files_hash, folders_hash
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id) DO UPDATE SET
                page_token = EXCLUDED.page_token,
                next_page_token = EXCLUDED.next_page_token,
                start_page_token = EXCLUDED.start_page_token,
                largest_change_id = EXCLUDED.largest_change_id,
                last_sync_time = EXCLUDED.last_sync_time,
                files_hash = EXCLUDED.files_hash,
                folders_hash = EXCLUDED.folders_hash
            """
            
            await db_conn_pool.execute(
                query,
                sync_state.user_id,
                sync_state.page_token,
                sync_state.next_page_token,
                sync_state.start_page_token,
                sync_state.largest_change_id,
                sync_state.last_sync_time,
                json.dumps(sync_state.files_hash),
                json.dumps(sync_state.folders_hash)
            )
        
        except Exception as e:
            logger.error(f"Error storing sync state in database: {e}")
    
    async def _store_event_in_db(self, event: GoogleDriveSyncEvent, db_conn_pool=None):
        """Store event in database"""
        if not db_conn_pool:
            return
        
        try:
            query = """
            INSERT INTO google_drive_sync_events (
                id, event_type, file_id, file_name, mime_type,
                user_id, timestamp, old_parent_ids, new_parent_ids,
                old_name, new_name, file_content_hash, change_id,
                processed, error_message
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            """
            
            await db_conn_pool.execute(
                query,
                event.id,
                event.event_type.value,
                event.file_id,
                event.file_name,
                event.mime_type,
                event.user_id,
                event.timestamp,
                json.dumps(event.old_parent_ids) if event.old_parent_ids else None,
                json.dumps(event.new_parent_ids) if event.new_parent_ids else None,
                event.old_name,
                event.new_name,
                event.file_content_hash,
                event.change_id,
                event.processed,
                event.error_message
            )
        
        except Exception as e:
            logger.error(f"Error storing event in database: {e}")
    
    def get_subscription(self, subscription_id: str) -> Optional[SyncSubscription]:
        """Get subscription by ID"""
        return self.subscriptions.get(subscription_id)
    
    def get_user_subscriptions(self, user_id: str) -> List[SyncSubscription]:
        """Get all subscriptions for user"""
        return [sub for sub in self.subscriptions.values() if sub.user_id == user_id]
    
    def get_event_history(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[SyncEventType] = None,
        limit: int = 100
    ) -> List[GoogleDriveSyncEvent]:
        """Get event history"""
        
        events = self.events_history
        
        # Filter by user
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        # Filter by event type
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get sync statistics"""
        total_subscriptions = len(self.subscriptions)
        active_subscriptions = len([s for s in self.subscriptions.values() if s.active])
        total_events = len(self.events_history)
        processed_events = len([e for e in self.events_history if e.processed])
        failed_events = total_events - processed_events
        
        # Events by type
        event_type_counts = {}
        for event in self.events_history:
            event_type = event.event_type.value
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Active syncs
        active_sync_count = len(self.active_syncs)
        
        # Recent events (last hour)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_events = [e for e in self.events_history if e.timestamp > one_hour_ago]
        
        return {
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "total_events": total_events,
            "processed_events": processed_events,
            "failed_events": failed_events,
            "success_rate": (processed_events / total_events * 100) if total_events > 0 else 0,
            "events_by_type": event_type_counts,
            "active_syncs": active_sync_count,
            "recent_events_1h": len(recent_events),
            "event_handlers": {
                "global": len(self.global_handlers),
                "type_specific": sum(len(handlers) for handlers in self.event_handlers.values())
            },
            "change_webhook_handlers": len(self.change_webhook_handlers)
        }
    
    async def cleanup_old_data(self, db_conn_pool=None):
        """Clean up old sync data"""
        
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Clean old events from memory
            self.events_history = [
                e for e in self.events_history 
                if e.timestamp > cutoff_time
            ]
            
            # Clean old events from database
            if self.db_pool:
                query = "DELETE FROM google_drive_sync_events WHERE timestamp < $1"
                await db_conn_pool.execute(query, cutoff_time)
            
            logger.info("Cleaned up old sync data")
        
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    async def start_background_tasks(self):
        """Start background sync tasks"""
        
        async def sync_loop():
            while True:
                try:
                    # Sync all active subscriptions
                    for subscription in self.subscriptions.values():
                        if subscription.active and not subscription.webhook_url:
                            # Only sync subscriptions without webhooks
                            await self.sync_files(
                                subscription.user_id,
                                subscription.id,
                                self.db_pool
                            )
                    
                    # Cleanup old data
                    await self.cleanup_old_data(self.db_pool)
                    
                    # Wait for next sync
                    await asyncio.sleep(self.sync_interval.total_seconds())
                
                except Exception as e:
                    logger.error(f"Error in sync loop: {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
        
        # Start background task
        asyncio.create_task(sync_loop())
        logger.info("Started background sync tasks")

# Global sync service instance
_google_drive_sync_service: Optional[GoogleDriveSyncService] = None

def get_google_drive_sync_service(drive_service: GoogleDriveService, db_pool=None) -> GoogleDriveSyncService:
    """Get global Google Drive sync service instance"""
    global _google_drive_sync_service
    
    if _google_drive_sync_service is None:
        _google_drive_sync_service = GoogleDriveSyncService(drive_service, db_pool)
    
    return _google_drive_sync_service

# Export service and classes
__all__ = [
    "GoogleDriveSyncService",
    "GoogleDriveSyncEvent",
    "SyncSubscription",
    "SyncState",
    "SyncEventType",
    "get_google_drive_sync_service"
]