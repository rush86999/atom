"""
Google Drive API Routes
Flask routes for Google Drive integration with real-time sync, memory, and analytics
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import asyncio
import json
import io
import os
from pathlib import Path
from loguru import logger

# Import Google Drive services
from google_drive_service import GoogleDriveService, GoogleDriveConfig, get_google_drive_service
from google_drive_memory import GoogleDriveMemoryService, get_google_drive_memory_service
from google_drive_realtime_sync import GoogleDriveRealtimeSyncService, get_google_drive_realtime_sync_service, RealtimeSyncEventType

# Import ATOM core services
from memory.lancedb_manager import LanceDBManager
from ingestion.data_processor import DataProcessor
from ingestion.embeddings_manager import EmbeddingsManager
from ingestion.content_extractor import ContentExtractor

# Create Flask blueprints
google_drive_bp = Blueprint("google_drive_bp", __name__)
google_drive_files_bp = Blueprint("google_drive_files_bp", __name__)
google_drive_sync_bp = Blueprint("google_drive_sync_bp", __name__)
google_drive_memory_bp = Blueprint("google_drive_memory_bp", __name__)
google_drive_analytics_bp = Blueprint("google_drive_analytics_bp", __name__)

# Database pool (will be set from main app)
db_pool = None

# Service instances
drive_service: Optional[GoogleDriveService] = None
memory_service: Optional[GoogleDriveMemoryService] = None
sync_service: Optional[GoogleDriveRealtimeSyncService] = None

def set_database_pool(pool):
    """Set database connection pool"""
    global db_pool
    db_pool = pool

def initialize_services(db_conn_pool=None):
    """Initialize Google Drive services"""
    global drive_service, memory_service, sync_service, db_pool
    
    db_pool = db_conn_pool
    
    try:
        # Initialize core services
        drive_service = get_google_drive_service()
        
        # Initialize memory service (requires LanceDB)
        if os.environ.get('LANCE_DB_PATH'):
            db_manager = LanceDBManager()
            embeddings_manager = EmbeddingsManager()
            data_processor = DataProcessor()
            content_extractor = ContentExtractor()
            
            memory_service = get_google_drive_memory_service(
                db_manager, embeddings_manager, data_processor, content_extractor, drive_service
            )
        
        # Initialize real-time sync service
        if memory_service:
            sync_service = get_google_drive_realtime_sync_service(
                drive_service, memory_service, db_pool
            )
        
        logger.info("Google Drive services initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Google Drive services: {e}")
        return False

# =============================================================================
# Core Google Drive Routes
# =============================================================================

@google_drive_bp.route('/api/google-drive/health', methods=['GET'])
async def google_drive_health():
    """Check Google Drive integration health"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "drive_service": drive_service is not None,
                "memory_service": memory_service is not None,
                "sync_service": sync_service is not None,
                "database": db_pool is not None
            },
            "features": {
                "file_operations": True,
                "real_time_sync": sync_service is not None,
                "memory_search": memory_service is not None,
                "analytics": True,
                "content_extraction": memory_service is not None
            }
        }
        
        # Add memory statistics if available
        if memory_service:
            memory_stats = memory_service.get_memory_statistics()
            health_status["memory"] = {
                "indexed_files": memory_stats["indexed_files"],
                "processed_content": memory_stats["processed_content"],
                "success_rate": memory_stats["success_rate"]
            }
        
        # Add sync statistics if available
        if sync_service:
            sync_stats = sync_service.get_sync_statistics()
            health_status["sync"] = {
                "total_subscriptions": sync_stats["total_subscriptions"],
                "active_subscriptions": sync_stats["active_subscriptions"],
                "events_processed": sync_stats["events_processed"]
            }
        
        return jsonify({"ok": True, "health": health_status})
        
    except Exception as e:
        logger.error(f"Google Drive health check error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_bp.route('/api/google-drive/connect', methods=['POST'])
async def google_drive_connect():
    """Connect to Google Drive"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        redirect_uri = data.get('redirect_uri')
        refresh_token = data.get('refresh_token')
        
        if not all([user_id, client_id, client_secret]):
            return jsonify({
                "ok": False,
                "error": "user_id, client_id, and client_secret are required"
            }), 400
        
        # Create Google Drive configuration
        config = GoogleDriveConfig(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri or "http://localhost:8000/auth/google/callback"
        )
        
        # Initialize service with new config
        global drive_service
        drive_service = GoogleDriveService(config)
        
        # Test connection by getting user's drive info
        about_response = await drive_service._make_request(
            user_id=user_id,
            method="GET",
            endpoint="about",
            params={
                "fields": "user,storageQuota,driveType"
            },
            db_conn_pool=db_pool
        )
        
        if about_response and "user" in about_response:
            user_info = about_response["user"]
            storage_quota = about_response.get("storageQuota", {})
            
            return jsonify({
                "ok": True,
                "connected": True,
                "user": {
                    "display_name": user_info.get("displayName"),
                    "email_address": user_info.get("emailAddress"),
                    "photo_link": user_info.get("photoLink")
                },
                "storage": {
                    "limit": int(storage_quota.get("limit", 0)),
                    "usage": int(storage_quota.get("usage", 0)),
                    "usage_in_drive": int(storage_quota.get("usageInDrive", 0)),
                    "usage_in_drive_trash": int(storage_quota.get("usageInDriveTrash", 0))
                },
                "drive_type": about_response.get("driveType"),
                "message": "Successfully connected to Google Drive"
            })
        else:
            return jsonify({
                "ok": False,
                "connected": False,
                "error": "Failed to connect to Google Drive"
            }), 400
            
    except Exception as e:
        logger.error(f"Google Drive connection error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# File Operations Routes
# =============================================================================

@google_drive_files_bp.route('/api/google-drive/files', methods=['GET'])
async def get_files():
    """Get files from Google Drive"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Get filters
        query = request.args.get('q')
        parent_id = request.args.get('parent_id')
        mime_type = request.args.get('mime_type')
        page_size = int(request.args.get('page_size', 10))
        page_token = request.args.get('page_token')
        order_by = request.args.get('order_by')
        
        # Get files
        files = await drive_service.get_files(
            user_id=user_id,
            query=query,
            parent_id=parent_id,
            mime_type=mime_type,
            page_size=min(page_size, 1000),  # Max 1000
            page_token=page_token,
            order_by=order_by,
            db_conn_pool=db_pool
        )
        
        # Convert to JSON-friendly format
        files_json = []
        for file in files:
            file_dict = {
                "id": file.id,
                "name": file.name,
                "mime_type": file.mime_type,
                "size": file.size,
                "created_time": file.created_time.isoformat() if file.created_time else None,
                "modified_time": file.modified_time.isoformat() if file.modified_time else None,
                "viewed_by_me_time": file.viewed_by_me_time.isoformat() if file.viewed_by_me_time else None,
                "parents": file.parents,
                "web_view_link": file.web_view_link,
                "web_content_link": file.web_content_link,
                "thumbnail_link": file.thumbnail_link,
                "shared": file.shared,
                "owners": file.owners,
                "version": file.version,
                "md5_checksum": file.md5_checksum,
                "file_extension": file.file_extension,
                "full_file_extension": file.full_file_extension,
                "trashed": file.trashed,
                "starred": file.starred
            }
            files_json.append(file_dict)
        
        return jsonify({
            "ok": True,
            "files": files_json,
            "total": len(files_json),
            "filters": {
                "query": query,
                "parent_id": parent_id,
                "mime_type": mime_type,
                "page_size": page_size,
                "page_token": page_token,
                "order_by": order_by
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/<file_id>', methods=['GET'])
async def get_file(file_id: str):
    """Get specific file"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Get file
        file = await drive_service.get_file(
            file_id=file_id,
            user_id=user_id,
            db_conn_pool=db_pool
        )
        
        if not file:
            return jsonify({"ok": False, "error": "File not found"}), 404
        
        # Convert to JSON-friendly format
        file_dict = {
            "id": file.id,
            "name": file.name,
            "mime_type": file.mime_type,
            "size": file.size,
            "created_time": file.created_time.isoformat() if file.created_time else None,
            "modified_time": file.modified_time.isoformat() if file.modified_time else None,
            "viewed_by_me_time": file.viewed_by_me_time.isoformat() if file.viewed_by_me_time else None,
            "parents": file.parents,
            "web_view_link": file.web_view_link,
            "web_content_link": file.web_content_link,
            "thumbnail_link": file.thumbnail_link,
            "shared": file.shared,
            "owners": file.owners,
            "version": file.version,
            "md5_checksum": file.md5_checksum,
            "file_extension": file.file_extension,
            "full_file_extension": file.full_file_extension,
            "trashed": file.trashed,
            "starred": file.starred
        }
        
        return jsonify({
            "ok": True,
            "file": file_dict
        })
        
    except Exception as e:
        logger.error(f"Error getting file {file_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files', methods=['POST'])
async def create_file():
    """Create new file"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('name')
        mime_type = data.get('mime_type')
        content = data.get('content')
        parents = data.get('parents', [])
        
        if not all([user_id, name, mime_type]):
            return jsonify({
                "ok": False,
                "error": "user_id, name, and mime_type are required"
            }), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Create file
        file = await drive_service.create_file(
            user_id=user_id,
            name=name,
            mime_type=mime_type,
            content=content,
            parents=parents,
            db_conn_pool=db_pool
        )
        
        if not file:
            return jsonify({
                "ok": False,
                "error": "Failed to create file"
            }), 500
        
        # Convert to JSON-friendly format
        file_dict = {
            "id": file.id,
            "name": file.name,
            "mime_type": file.mime_type,
            "size": file.size,
            "created_time": file.created_time.isoformat() if file.created_time else None,
            "modified_time": file.modified_time.isoformat() if file.modified_time else None,
            "parents": file.parents,
            "web_view_link": file.web_view_link,
            "web_content_link": file.web_content_link,
            "shared": file.shared,
            "owners": file.owners
        }
        
        return jsonify({
            "ok": True,
            "file": file_dict,
            "message": f"File '{name}' created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating file: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/<file_id>', methods=['PUT'])
async def update_file(file_id: str):
    """Update file"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('name')
        content = data.get('content')
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Update file
        file = await drive_service.update_file(
            user_id=user_id,
            file_id=file_id,
            name=name,
            content=content,
            db_conn_pool=db_pool
        )
        
        if not file:
            return jsonify({
                "ok": False,
                "error": "Failed to update file"
            }), 500
        
        # Convert to JSON-friendly format
        file_dict = {
            "id": file.id,
            "name": file.name,
            "mime_type": file.mime_type,
            "size": file.size,
            "modified_time": file.modified_time.isoformat() if file.modified_time else None,
            "parents": file.parents,
            "web_view_link": file.web_view_link,
            "web_content_link": file.web_content_link
        }
        
        return jsonify({
            "ok": True,
            "file": file_dict,
            "message": f"File '{name or file_id}' updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error updating file {file_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/<file_id>', methods=['DELETE'])
async def delete_file(file_id: str):
    """Delete file"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Delete file
        success = await drive_service.delete_file(
            user_id=user_id,
            file_id=file_id,
            db_conn_pool=db_pool
        )
        
        if success:
            return jsonify({
                "ok": True,
                "message": f"File '{file_id}' deleted successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete file"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/upload', methods=['POST'])
async def upload_file():
    """Upload file to Google Drive"""
    try:
        user_id = request.form.get('user_id')
        file = request.files.get('file')
        name = request.form.get('name')
        parents = json.loads(request.form.get('parents', '[]')) if request.form.get('parents') else []
        
        if not all([user_id, file]):
            return jsonify({
                "ok": False,
                "error": "user_id and file are required"
            }), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Save uploaded file temporarily
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        file_name = name or file.filename
        temp_path = temp_dir / f"{user_id}_{file_name}"
        file.save(temp_path)
        
        try:
            # Upload to Google Drive
            uploaded_file = await drive_service.upload_file(
                user_id=user_id,
                file_path=str(temp_path),
                name=file_name,
                parents=parents,
                db_conn_pool=db_pool
            )
            
            if not uploaded_file:
                return jsonify({
                    "ok": False,
                    "error": "Failed to upload file"
                }), 500
            
            # Convert to JSON-friendly format
            file_dict = {
                "id": uploaded_file.id,
                "name": uploaded_file.name,
                "mime_type": uploaded_file.mime_type,
                "size": uploaded_file.size,
                "created_time": uploaded_file.created_time.isoformat() if uploaded_file.created_time else None,
                "modified_time": uploaded_file.modified_time.isoformat() if uploaded_file.modified_time else None,
                "parents": uploaded_file.parents,
                "web_view_link": uploaded_file.web_view_link,
                "web_content_link": uploaded_file.web_content_link,
                "shared": uploaded_file.shared,
                "owners": uploaded_file.owners
            }
            
            return jsonify({
                "ok": True,
                "file": file_dict,
                "message": f"File '{file_name}' uploaded successfully"
            })
        
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/<file_id>/download', methods=['GET'])
async def download_file(file_id: str):
    """Download file from Google Drive"""
    try:
        user_id = request.args.get('user_id')
        inline = request.args.get('inline', 'false').lower() == 'true'
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Get file info first
        file = await drive_service.get_file(
            file_id=file_id,
            user_id=user_id,
            db_conn_pool=db_pool
        )
        
        if not file:
            return jsonify({"ok": False, "error": "File not found"}), 404
        
        # Download file content
        content = await drive_service.download_file(
            user_id=user_id,
            file_id=file_id,
            db_conn_pool=db_pool
        )
        
        if not content:
            return jsonify({"ok": False, "error": "Failed to download file"}), 500
        
        # Create file-like object
        file_stream = io.BytesIO(content)
        
        # Set appropriate headers
        headers = {
            'Content-Type': file.mime_type,
            'Content-Length': str(len(content))
        }
        
        if inline:
            headers['Content-Disposition'] = f'inline; filename="{file.name}"'
        else:
            headers['Content-Disposition'] = f'attachment; filename="{file.name}"'
        
        return send_file(
            file_stream,
            as_attachment=not inline,
            download_name=file.name,
            mimetype=file.mime_type
        )
        
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/<file_id>/copy', methods=['POST'])
async def copy_file(file_id: str):
    """Copy file"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('name')
        parents = data.get('parents')
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Copy file
        copied_file = await drive_service.copy_file(
            user_id=user_id,
            file_id=file_id,
            name=name,
            parents=parents,
            db_conn_pool=db_pool
        )
        
        if not copied_file:
            return jsonify({
                "ok": False,
                "error": "Failed to copy file"
            }), 500
        
        # Convert to JSON-friendly format
        file_dict = {
            "id": copied_file.id,
            "name": copied_file.name,
            "mime_type": copied_file.mime_type,
            "size": copied_file.size,
            "created_time": copied_file.created_time.isoformat() if copied_file.created_time else None,
            "modified_time": copied_file.modified_time.isoformat() if copied_file.modified_time else None,
            "parents": copied_file.parents,
            "web_view_link": copied_file.web_view_link,
            "web_content_link": copied_file.web_content_link,
            "shared": copied_file.shared,
            "owners": copied_file.owners
        }
        
        return jsonify({
            "ok": True,
            "file": file_dict,
            "message": f"File copied successfully as '{copied_file.name}'"
        })
        
    except Exception as e:
        logger.error(f"Error copying file {file_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_files_bp.route('/api/google-drive/files/<file_id>/move', methods=['PUT'])
async def move_file(file_id: str):
    """Move file to different folder"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        add_parents = data.get('add_parents', [])
        remove_parents = data.get('remove_parents', [])
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not drive_service:
            return jsonify({"ok": False, "error": "Google Drive service not initialized"}), 500
        
        # Move file
        moved_file = await drive_service.move_file(
            user_id=user_id,
            file_id=file_id,
            add_parents=add_parents,
            remove_parents=remove_parents,
            db_conn_pool=db_pool
        )
        
        if not moved_file:
            return jsonify({
                "ok": False,
                "error": "Failed to move file"
            }), 500
        
        # Convert to JSON-friendly format
        file_dict = {
            "id": moved_file.id,
            "name": moved_file.name,
            "mime_type": moved_file.mime_type,
            "size": moved_file.size,
            "modified_time": moved_file.modified_time.isoformat() if moved_file.modified_time else None,
            "parents": moved_file.parents,
            "web_view_link": moved_file.web_view_link
        }
        
        return jsonify({
            "ok": True,
            "file": file_dict,
            "message": f"File moved successfully"
        })
        
    except Exception as e:
        logger.error(f"Error moving file {file_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Real-time Sync Routes
# =============================================================================

@google_drive_sync_bp.route('/api/google-drive/sync/subscriptions', methods=['POST'])
async def create_sync_subscription():
    """Create real-time sync subscription"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        folder_id = data.get('folder_id')
        include_subfolders = data.get('include_subfolders', True)
        file_types = data.get('file_types', [])
        event_types_str = data.get('event_types', [])
        webhook_url = data.get('webhook_url')
        memory_sync = data.get('memory_sync', True)
        realtime_notifications = data.get('realtime_notifications', True)
        sync_interval = data.get('sync_interval', 30)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        # Convert event types
        event_types = []
        for event_type_str in event_types_str:
            try:
                event_type = RealtimeSyncEventType(event_type_str)
                event_types.append(event_type)
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid event type: {event_type_str}"
                }), 400
        
        # Create subscription
        subscription = await sync_service.create_subscription(
            user_id=user_id,
            folder_id=folder_id,
            include_subfolders=include_subfolders,
            file_types=file_types,
            event_types=event_types,
            webhook_url=webhook_url,
            memory_sync=memory_sync,
            realtime_notifications=realtime_notifications,
            sync_interval=sync_interval,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": True,
            "subscription": {
                "id": subscription.id,
                "user_id": subscription.user_id,
                "folder_id": subscription.folder_id,
                "include_subfolders": subscription.include_subfolders,
                "file_types": subscription.file_types,
                "event_types": [et.value for et in subscription.event_types],
                "webhook_url": subscription.webhook_url,
                "memory_sync": subscription.memory_sync,
                "realtime_notifications": subscription.realtime_notifications,
                "sync_interval": subscription.sync_interval,
                "active": subscription.active,
                "created_at": subscription.created_at.isoformat(),
                "total_synced": subscription.total_synced,
                "total_errors": subscription.total_errors
            },
            "message": "Sync subscription created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating sync subscription: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_sync_bp.route('/api/google-drive/sync/subscriptions', methods=['GET'])
async def get_sync_subscriptions():
    """Get sync subscriptions"""
    try:
        user_id = request.args.get('user_id')
        subscription_id = request.args.get('subscription_id')
        
        if not user_id and not subscription_id:
            return jsonify({
                "ok": False,
                "error": "user_id or subscription_id is required"
            }), 400
        
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        subscriptions = []
        
        if subscription_id:
            # Get specific subscription
            subscription = sync_service.get_subscription(subscription_id)
            if subscription:
                subscriptions.append(subscription)
        elif user_id:
            # Get all user subscriptions
            subscriptions = sync_service.get_user_subscriptions(user_id)
        
        # Convert to JSON-friendly format
        subscriptions_json = []
        for sub in subscriptions:
            sub_dict = {
                "id": sub.id,
                "user_id": sub.user_id,
                "folder_id": sub.folder_id,
                "include_subfolders": sub.include_subfolders,
                "file_types": sub.file_types,
                "event_types": [et.value for et in sub.event_types],
                "webhook_url": sub.webhook_url,
                "memory_sync": sub.memory_sync,
                "realtime_notifications": sub.realtime_notifications,
                "change_webhook_active": sub.change_webhook_active,
                "last_sync_token": sub.last_sync_token,
                "sync_interval": sub.sync_interval,
                "max_file_size": sub.max_file_size,
                "active": sub.active,
                "created_at": sub.created_at.isoformat(),
                "updated_at": sub.updated_at.isoformat(),
                "total_synced": sub.total_synced,
                "total_errors": sub.total_errors,
                "last_sync_time": sub.last_sync_time.isoformat() if sub.last_sync_time else None
            }
            subscriptions_json.append(sub_dict)
        
        return jsonify({
            "ok": True,
            "subscriptions": subscriptions_json,
            "total": len(subscriptions_json)
        })
        
    except Exception as e:
        logger.error(f"Error getting sync subscriptions: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_sync_bp.route('/api/google-drive/sync/subscriptions/<subscription_id>', methods=['DELETE'])
async def delete_sync_subscription(subscription_id: str):
    """Delete sync subscription"""
    try:
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        success = await sync_service.delete_subscription(
            subscription_id=subscription_id,
            db_conn_pool=db_pool
        )
        
        if success:
            return jsonify({
                "ok": True,
                "message": f"Sync subscription {subscription_id} deleted successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Sync subscription not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error deleting sync subscription {subscription_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_sync_bp.route('/api/google-drive/sync/trigger', methods=['POST'])
async def trigger_sync():
    """Trigger manual sync"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        subscription_id = data.get('subscription_id')
        full_sync = data.get('full_sync', False)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        # Trigger sync
        result = await sync_service.sync_now(
            user_id=user_id,
            subscription_id=subscription_id,
            full_sync=full_sync,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": result.get("success", False),
            "result": result,
            "message": "Sync triggered successfully" if result.get("success") else "Sync failed"
        })
        
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_sync_bp.route('/api/google-drive/sync/events', methods=['GET'])
async def get_sync_events():
    """Get sync event history"""
    try:
        user_id = request.args.get('user_id')
        event_type_str = request.args.get('event_type')
        limit = int(request.args.get('limit', 100))
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        # Convert event type
        event_type = None
        if event_type_str:
            try:
                event_type = RealtimeSyncEventType(event_type_str)
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid event type: {event_type_str}"
                }), 400
        
        # Get events
        events = sync_service.get_event_history(
            user_id=user_id,
            event_type=event_type,
            limit=limit
        )
        
        # Convert to JSON-friendly format
        events_json = []
        for event in events:
            event_dict = {
                "id": event.id,
                "event_type": event.event_type.value,
                "file_id": event.file_id,
                "file_name": event.file_name,
                "mime_type": event.mime_type,
                "user_id": event.user_id,
                "timestamp": event.timestamp.isoformat(),
                "old_parent_ids": event.old_parent_ids,
                "new_parent_ids": event.new_parent_ids,
                "old_name": event.old_name,
                "new_name": event.new_name,
                "old_shared": event.old_shared,
                "new_shared": event.new_shared,
                "content_hash": event.content_hash,
                "change_id": event.change_id,
                "processing_status": event.processing_status,
                "processing_time": event.processing_time.isoformat() if event.processing_time else None,
                "error_message": event.error_message,
                "memory_updated": event.memory_updated,
                "webhook_sent": event.webhook_sent
            }
            events_json.append(event_dict)
        
        return jsonify({
            "ok": True,
            "events": events_json,
            "total": len(events_json)
        })
        
    except Exception as e:
        logger.error(f"Error getting sync events: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_sync_bp.route('/api/google-drive/sync/webhook', methods=['POST'])
async def handle_webhook_notification():
    """Handle webhook notification from Google Drive"""
    try:
        subscription_id = request.headers.get('X-Goog-Channel-ID')
        
        if not subscription_id:
            return jsonify({
                "ok": False,
                "error": "Missing X-Goog-Channel-ID header"
            }), 400
        
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        # Get webhook data
        webhook_data = {
            "headers": dict(request.headers),
            "data": request.get_json() or request.form.to_dict()
        }
        
        # Process webhook notification
        result = await sync_service.process_webhook_notification(
            subscription_id=subscription_id,
            notification_data=webhook_data,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": result.get("success", False),
            "result": result
        })
        
    except Exception as e:
        logger.error(f"Error handling webhook notification: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_sync_bp.route('/api/google-drive/sync/statistics', methods=['GET'])
async def get_sync_statistics():
    """Get sync service statistics"""
    try:
        if not sync_service:
            return jsonify({
                "ok": False,
                "error": "Real-time sync service not initialized"
            }), 500
        
        statistics = sync_service.get_sync_statistics()
        
        return jsonify({
            "ok": True,
            "statistics": statistics
        })
        
    except Exception as e:
        logger.error(f"Error getting sync statistics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Memory and Search Routes
# =============================================================================

@google_drive_memory_bp.route('/api/google-drive/memory/index', methods=['POST'])
async def index_file_in_memory():
    """Index file in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        file_id = data.get('file_id')
        download_content = data.get('download_content', True)
        process_content = data.get('process_content', True)
        
        if not all([user_id, file_id]):
            return jsonify({
                "ok": False,
                "error": "user_id and file_id are required"
            }), 400
        
        if not memory_service:
            return jsonify({
                "ok": False,
                "error": "Memory service not initialized"
            }), 500
        
        if not drive_service:
            return jsonify({
                "ok": False,
                "error": "Google Drive service not initialized"
            }), 500
        
        # Get file
        file = await drive_service.get_file(
            file_id=file_id,
            user_id=user_id,
            db_conn_pool=db_pool
        )
        
        if not file:
            return jsonify({
                "ok": False,
                "error": "File not found"
            }), 404
        
        # Index in memory
        memory_record = await memory_service.index_file(
            file=file,
            user_id=user_id,
            download_content=download_content,
            process_content=process_content
        )
        
        return jsonify({
            "ok": True,
            "record": {
                "id": memory_record.id,
                "file_id": memory_record.file_id,
                "name": memory_record.name,
                "mime_type": memory_record.mime_type,
                "size": memory_record.size,
                "content_status": memory_record.content_status.value,
                "has_extracted_content": bool(memory_record.extracted_content),
                "has_embeddings": bool(memory_record.embeddings),
                "indexed_at": datetime.now(timezone.utc).isoformat()
            },
            "message": f"File '{memory_record.name}' indexed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error indexing file in memory: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_memory_bp.route('/api/google-drive/memory/batch-index', methods=['POST'])
async def batch_index_files():
    """Batch index files in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        folder_id = data.get('folder_id')
        include_subfolders = data.get('include_subfolders', True)
        download_content = data.get('download_content', True)
        process_content = data.get('process_content', True)
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not memory_service:
            return jsonify({
                "ok": False,
                "error": "Memory service not initialized"
            }), 500
        
        if not drive_service:
            return jsonify({
                "ok": False,
                "error": "Google Drive service not initialized"
            }), 500
        
        # Perform batch indexing
        results = await memory_service.batch_index(
            user_id=user_id,
            folder_id=folder_id,
            include_subfolders=include_subfolders,
            download_content=download_content
        )
        
        return jsonify({
            "ok": True,
            "results": results,
            "message": "Batch indexing completed"
        })
        
    except Exception as e:
        logger.error(f"Error in batch indexing: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_memory_bp.route('/api/google-drive/memory/search', methods=['POST'])
async def search_in_memory():
    """Search files in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('search_type', 'semantic')  # semantic, text, metadata
        filters = data.get('filters', {})
        limit = data.get('limit', 50)
        
        if not all([user_id, query]):
            return jsonify({
                "ok": False,
                "error": "user_id and query are required"
            }), 400
        
        if not memory_service:
            return jsonify({
                "ok": False,
                "error": "Memory service not initialized"
            }), 500
        
        # Search in memory
        records = await memory_service.search_files(
            user_id=user_id,
            query=query,
            search_type=search_type,
            filters=filters,
            limit=limit
        )
        
        # Convert to JSON-friendly format
        records_json = []
        for record in records:
            record_dict = {
                "id": record.id,
                "file_id": record.file_id,
                "name": record.name,
                "mime_type": record.mime_type,
                "size": record.size,
                "content_status": record.content_status.value,
                "created_time": record.created_time.isoformat() if record.created_time else None,
                "modified_time": record.modified_time.isoformat() if record.modified_time else None,
                "parents": record.parents,
                "web_view_link": record.web_view_link,
                "web_content_link": record.web_content_link,
                "shared": record.shared,
                "tags": record.tags,
                "metadata": record.metadata,
                "has_extracted_content": bool(record.extracted_content),
                "has_embeddings": bool(record.embeddings),
                "last_indexed": record.last_indexed.isoformat() if record.last_indexed else None,
                "access_count": record.access_count,
                "last_accessed": record.last_accessed.isoformat() if record.last_accessed else None
            }
            records_json.append(record_dict)
        
        return jsonify({
            "ok": True,
            "records": records_json,
            "total": len(records_json),
            "search_params": {
                "query": query,
                "search_type": search_type,
                "filters": filters,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching in memory: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_memory_bp.route('/api/google-drive/memory/content/<file_id>', methods=['GET'])
async def get_file_content_from_memory():
    """Get file content from memory"""
    try:
        user_id = request.args.get('user_id')
        file_id = file_id
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not memory_service:
            return jsonify({
                "ok": False,
                "error": "Memory service not initialized"
            }), 500
        
        # Get file content
        content = await memory_service.get_file_content(
            file_id=file_id,
            user_id=user_id
        )
        
        if content:
            return jsonify({
                "ok": True,
                "file_id": file_id,
                "content": content,
                "content_length": len(content)
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Content not found in memory"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting file content from memory: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_memory_bp.route('/api/google-drive/memory/statistics', methods=['GET'])
async def get_memory_statistics():
    """Get memory service statistics"""
    try:
        if not memory_service:
            return jsonify({
                "ok": False,
                "error": "Memory service not initialized"
            }), 500
        
        statistics = memory_service.get_memory_statistics()
        
        return jsonify({
            "ok": True,
            "statistics": statistics
        })
        
    except Exception as e:
        logger.error(f"Error getting memory statistics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Analytics Routes
# =============================================================================

@google_drive_analytics_bp.route('/api/google-drive/analytics/storage', methods=['GET'])
async def get_storage_analytics():
    """Get storage analytics"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not drive_service:
            return jsonify({
                "ok": False,
                "error": "Google Drive service not initialized"
            }), 500
        
        # Get storage info
        about_response = await drive_service._make_request(
            user_id=user_id,
            method="GET",
            endpoint="about",
            params={
                "fields": "storageQuota"
            },
            db_conn_pool=db_pool
        )
        
        if about_response and "storageQuota" in about_response:
            storage_quota = about_response["storageQuota"]
            
            # Get file type distribution
            files = await drive_service.get_files(
                user_id=user_id,
                page_size=1000,
                db_conn_pool=db_pool
            )
            
            file_type_stats = {}
            total_files = len(files)
            
            for file in files:
                mime_type = file.mime_type
                if mime_type not in file_type_stats:
                    file_type_stats[mime_type] = {
                        "count": 0,
                        "total_size": 0
                    }
                
                file_type_stats[mime_type]["count"] += 1
                file_type_stats[mime_type]["total_size"] += file.size
            
            # Calculate storage usage
            total_limit = int(storage_quota.get("limit", 0))
            total_usage = int(storage_quota.get("usage", 0))
            usage_in_drive = int(storage_quota.get("usageInDrive", 0))
            usage_in_drive_trash = int(storage_quota.get("usageInDriveTrash", 0))
            
            return jsonify({
                "ok": True,
                "storage": {
                    "total_limit": total_limit,
                    "total_usage": total_usage,
                    "usage_in_drive": usage_in_drive,
                    "usage_in_drive_trash": usage_in_drive_trash,
                    "usage_percentage": (total_usage / total_limit * 100) if total_limit > 0 else 0,
                    "available_space": total_limit - total_usage
                },
                "file_stats": {
                    "total_files": total_files,
                    "file_types": file_type_stats,
                    "largest_files": [
                        {
                            "id": file.id,
                            "name": file.name,
                            "size": file.size,
                            "mime_type": file.mime_type
                        }
                        for file in sorted(files, key=lambda f: f.size, reverse=True)[:10]
                    ]
                },
                "analytics_generated_at": datetime.now(timezone.utc).isoformat()
            })
        
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to get storage information"
            }), 500
        
    except Exception as e:
        logger.error(f"Error getting storage analytics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_analytics_bp.route('/api/google-drive/analytics/activity', methods=['GET'])
async def get_activity_analytics():
    """Get file activity analytics"""
    try:
        user_id = request.args.get('user_id')
        days = int(request.args.get('days', 30))
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "user_id is required"
            }), 400
        
        if not drive_service:
            return jsonify({
                "ok": False,
                "error": "Google Drive service not initialized"
            }), 500
        
        # Get recent files
        files = await drive_service.get_files(
            user_id=user_id,
            page_size=1000,
            db_conn_pool=db_pool
        )
        
        # Calculate activity metrics
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        recent_files = [
            file for file in files
            if file.modified_time and file.modified_time > cutoff_date
        ]
        
        # Activity by day
        activity_by_day = {}
        for file in recent_files:
            day_key = file.modified_time.date().isoformat()
            if day_key not in activity_by_day:
                activity_by_day[day_key] = {
                    "created": 0,
                    "modified": 0,
                    "total_size": 0
                }
            
            if file.created_time and file.created_time > cutoff_date:
                activity_by_day[day_key]["created"] += 1
            
            activity_by_day[day_key]["modified"] += 1
            activity_by_day[day_key]["total_size"] += file.size
        
        # Most active file types
        file_type_activity = {}
        for file in recent_files:
            mime_type = file.mime_type
            if mime_type not in file_type_activity:
                file_type_activity[mime_type] = 0
            file_type_activity[mime_type] += 1
        
        return jsonify({
            "ok": True,
            "activity": {
                "period_days": days,
                "total_recent_files": len(recent_files),
                "activity_by_day": activity_by_day,
                "most_active_file_types": sorted(
                    file_type_activity.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10],
                "recently_created": len([
                    f for f in recent_files
                    if f.created_time and f.created_time > cutoff_date
                ]),
                "recently_modified": len(recent_files)
            },
            "analytics_generated_at": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting activity analytics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Registration Function
# =============================================================================

def register_google_drive_blueprints(app):
    """Register all Google Drive blueprints with Flask app"""
    app.register_blueprint(google_drive_bp, url_prefix='/api/google-drive')
    app.register_blueprint(google_drive_files_bp, url_prefix='/api/google-drive')
    app.register_blueprint(google_drive_sync_bp, url_prefix='/api/google-drive')
    app.register_blueprint(google_drive_memory_bp, url_prefix='/api/google-drive')
    app.register_blueprint(google_drive_analytics_bp, url_prefix='/api/google-drive')
    
    logger.info("Google Drive blueprints registered successfully")
    return True

# Export blueprints for direct registration
__all__ = [
    "register_google_drive_blueprints",
    "google_drive_bp",
    "google_drive_files_bp", 
    "google_drive_sync_bp",
    "google_drive_memory_bp",
    "google_drive_analytics_bp",
    "set_database_pool",
    "initialize_services"
]