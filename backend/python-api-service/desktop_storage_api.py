"""
Desktop Storage API Endpoints
Local storage as primary with S3 as secondary backup
"""

import os
import json
import asyncio
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
from pathlib import Path
import logging

# Import desktop storage service
from desktop_storage_service import (
    create_desktop_storage_manager,
    LocalStorageConfig,
    S3StorageConfig,
    StorageQuota
)

logger = logging.getLogger(__name__)

# Create blueprint
desktop_storage_bp = Blueprint('desktop_storage_bp', __name__)

# Global storage manager instance
_storage_manager = None

def get_storage_manager():
    """Get or create global storage manager"""
    global _storage_manager
    
    if _storage_manager is None:
        # Get configuration from environment or use defaults
        local_path = os.getenv('ATOM_LOCAL_STORAGE_PATH')
        max_local_size_gb = float(os.getenv('ATOM_MAX_LOCAL_SIZE_GB', '50.0'))
        
        # S3 configuration (optional)
        s3_bucket = os.getenv('ATOM_S3_BUCKET')
        s3_region = os.getenv('ATOM_S3_REGION', 'us-west-2')
        auto_sync = os.getenv('ATOM_AUTO_SYNC', 'true').lower() == 'true'
        sync_interval_minutes = int(os.getenv('ATOM_SYNC_INTERVAL_MINUTES', '30'))
        
        # Create storage manager
        _storage_manager = create_desktop_storage_manager(
            local_path=local_path,
            max_local_size_gb=max_local_size_gb,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            auto_sync=auto_sync,
            sync_interval_minutes=sync_interval_minutes
        )
        
        # Start auto-sync if enabled
        if auto_sync:
            asyncio.create_task(_storage_manager.start_sync_service())
    
    return _storage_manager


# -------------------------------------------------------------------------
# Storage Management Endpoints
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/config", methods=["GET"])
def get_storage_config():
    """Get storage configuration"""
    try:
        storage_manager = get_storage_manager()
        
        config = {
            "local_storage": {
                "base_path": str(storage_manager.local_manager.config.base_path),
                "max_size_gb": storage_manager.local_manager.config.max_local_size_bytes / (1024 * 1024 * 1024),
                "compression_enabled": storage_manager.local_manager.config.compression_enabled,
                "encryption_enabled": storage_manager.local_manager.config.encryption_enabled
            },
            "cloud_storage": {
                "s3_configured": storage_manager.s3_manager is not None,
                "auto_sync_enabled": storage_manager.auto_sync,
                "sync_interval_minutes": storage_manager.sync_interval_seconds / 60
            }
        }
        
        # Add S3 details if configured
        if storage_manager.s3_manager:
            config["cloud_storage"]["s3_config"] = {
                "bucket_name": storage_manager.s3_manager.config.bucket_name,
                "region": storage_manager.s3_manager.config.region,
                "prefix": storage_manager.s3_manager.config.prefix,
                "storage_class": storage_manager.s3_manager.config.storage_class
            }
        
        return jsonify({
            "status": "success",
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Error getting storage config: {e}")
        return jsonify({
            "error": f"Failed to get storage config: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/config", methods=["PUT"])
def update_storage_config():
    """Update storage configuration"""
    try:
        data = request.get_json()
        storage_manager = get_storage_manager()
        
        # Note: For this implementation, config updates would require
        # recreation of the storage manager. In production, implement
        # dynamic configuration updates.
        
        return jsonify({
            "status": "success",
            "message": "Storage configuration update would require service restart",
            "data": {
                "current_config": "See GET /api/storage/config",
                "requested_changes": data
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating storage config: {e}")
        return jsonify({
            "error": f"Failed to update storage config: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/stats", methods=["GET"])
def get_storage_stats():
    """Get comprehensive storage statistics"""
    try:
        storage_manager = get_storage_manager()
        stats = storage_manager.get_comprehensive_stats()
        
        return jsonify({
            "status": "success",
            "data": stats
        })
        
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        return jsonify({
            "error": f"Failed to get storage stats: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/quota", methods=["GET"])
def get_storage_quota():
    """Get storage quota information"""
    try:
        storage_manager = get_storage_manager()
        quota_info = storage_manager.local_manager.quota._get_quota_info()
        
        return jsonify({
            "status": "success",
            "data": {
                "quota": quota_info,
                "is_exceeded": storage_manager.local_manager.quota.is_quota_exceeded(),
                "cleanup_candidates": len(storage_manager.local_manager.quota.get_cleanup_candidates())
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting storage quota: {e}")
        return jsonify({
            "error": f"Failed to get storage quota: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# File Management Endpoints
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/files", methods=["GET"])
def list_files():
    """List stored files with optional filtering"""
    try:
        storage_manager = get_storage_manager()
        
        # Parse query parameters
        sync_status = request.args.get('sync_status')
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        
        files = storage_manager.local_manager.list_files(
            sync_status=sync_status,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            "status": "success",
            "data": {
                "files": files,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "returned": len(files)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({
            "error": f"Failed to list files: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/files/<file_id>", methods=["GET"])
def get_file_info(file_id):
    """Get file information by ID"""
    try:
        storage_manager = get_storage_manager()
        file_data = storage_manager.local_manager.get_file(file_id)
        
        if not file_data:
            return jsonify({
                "error": "File not found",
                "success": False
            }), 404
        
        return jsonify({
            "status": "success",
            "data": file_data
        })
        
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return jsonify({
            "error": f"Failed to get file info: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/files/<file_id>", methods=["DELETE"])
def delete_file(file_id):
    """Delete file from storage"""
    try:
        storage_manager = get_storage_manager()
        
        # Get file info first
        file_data = storage_manager.local_manager.get_file(file_id)
        if not file_data:
            return jsonify({
                "error": "File not found",
                "success": False
            }), 404
        
        # Delete from local storage
        local_path = file_data.get('local_path')
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
        
        # Delete from S3 if synced
        if storage_manager.s3_manager and file_data.get('s3_key'):
            storage_manager.s3_manager.delete_file(file_data['s3_key'])
        
        # Remove from database (would need to implement)
        # storage_manager.local_manager.delete_file(file_id)
        
        return jsonify({
            "status": "success",
            "message": "File deleted successfully",
            "file_id": file_id
        })
        
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({
            "error": f"Failed to delete file: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# File Upload Endpoints
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/files/upload", methods=["POST"])
def upload_file():
    """Upload file to local storage"""
    try:
        storage_manager = get_storage_manager()
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                "error": "No file provided",
                "success": False
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "error": "No file selected",
                "success": False
            }), 400
        
        # Secure filename
        filename = secure_filename(file.filename)
        
        # Generate unique file ID
        file_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        
        # Create upload directory if needed
        upload_dir = storage_manager.local_manager.config.base_path / 'uploads'
        upload_dir.mkdir(exist_ok=True)
        
        # Save file to local storage
        local_path = upload_dir / filename
        file.save(str(local_path))
        
        # Get additional metadata
        metadata = {
            "original_filename": file.filename,
            "content_type": file.content_type,
            "uploaded_by": request.form.get('uploaded_by', 'desktop'),
            "source": request.form.get('source', 'upload'),
            "tags": request.form.getlist('tags'),
            "description": request.form.get('description', '')
        }
        
        # Store file metadata
        success = storage_manager.local_manager.store_file(
            file_id=file_id,
            local_path=str(local_path),
            metadata=metadata
        )
        
        if not success:
            # Clean up uploaded file if storage failed
            if os.path.exists(local_path):
                os.remove(local_path)
            return jsonify({
                "error": "Failed to store file metadata",
                "success": False
            }), 500
        
        return jsonify({
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "file_id": file_id,
                "filename": filename,
                "local_path": str(local_path),
                "file_size": os.path.getsize(local_path)
            }
        })
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({
            "error": f"Failed to upload file: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Sync Management Endpoints
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/sync/start", methods=["POST"])
def start_sync():
    """Start manual sync to cloud"""
    try:
        storage_manager = get_storage_manager()
        
        if not storage_manager.s3_manager:
            return jsonify({
                "error": "S3 storage not configured",
                "success": False
            }), 400
        
        # Start sync in background
        async def run_sync():
            return await storage_manager.sync_to_cloud()
        
        sync_task = asyncio.create_task(run_sync())
        sync_result = asyncio.run(sync_task)
        
        return jsonify({
            "status": "success",
            "message": "Sync completed",
            "data": sync_result
        })
        
    except Exception as e:
        logger.error(f"Error starting sync: {e}")
        return jsonify({
            "error": f"Failed to start sync: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/sync/status", methods=["GET"])
def get_sync_status():
    """Get current sync status"""
    try:
        storage_manager = get_storage_manager()
        
        sync_status = {
            "auto_sync_enabled": storage_manager.auto_sync,
            "is_syncing": storage_manager.is_syncing,
            "last_sync_time": storage_manager.last_sync_time.isoformat() if storage_manager.last_sync_time else None,
            "s3_configured": storage_manager.s3_manager is not None
        }
        
        # Add sync statistics
        if storage_manager.s3_manager:
            sync_status["cloud_stats"] = storage_manager.s3_manager.get_storage_usage()
        
        return jsonify({
            "status": "success",
            "data": sync_status
        })
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({
            "error": f"Failed to get sync status: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/sync/config", methods=["PUT"])
def update_sync_config():
    """Update sync configuration"""
    try:
        data = request.get_json()
        storage_manager = get_storage_manager()
        
        # Update auto-sync setting
        if 'auto_sync' in data:
            storage_manager.auto_sync = data['auto_sync']
            
            if storage_manager.auto_sync:
                # Start auto-sync service
                asyncio.create_task(storage_manager.start_sync_service())
            else:
                # Stop auto-sync service
                asyncio.create_task(storage_manager.stop_sync_service())
        
        # Update sync interval
        if 'sync_interval_minutes' in data:
            storage_manager.sync_interval_seconds = data['sync_interval_minutes'] * 60
        
        return jsonify({
            "status": "success",
            "message": "Sync configuration updated",
            "data": {
                "auto_sync": storage_manager.auto_sync,
                "sync_interval_minutes": storage_manager.sync_interval_seconds / 60
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating sync config: {e}")
        return jsonify({
            "error": f"Failed to update sync config: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# File Restore Endpoints
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/files/<file_id>/restore", methods=["POST"])
def restore_file(file_id):
    """Restore file from cloud storage"""
    try:
        storage_manager = get_storage_manager()
        data = request.get_json() or {}
        
        restore_path = data.get('restore_path')
        
        if not storage_manager.s3_manager:
            return jsonify({
                "error": "S3 storage not configured",
                "success": False
            }), 400
        
        # Restore file in background
        async def run_restore():
            return await storage_manager.restore_from_cloud(
                file_id=file_id,
                local_path=restore_path
            )
        
        restore_task = asyncio.create_task(run_restore())
        restore_success = asyncio.run(restore_task)
        
        if restore_success:
            return jsonify({
                "status": "success",
                "message": "File restored successfully",
                "file_id": file_id,
                "restore_path": restore_path
            })
        else:
            return jsonify({
                "error": "Failed to restore file",
                "success": False
            }), 500
        
    except Exception as e:
        logger.error(f"Error restoring file: {e}")
        return jsonify({
            "error": f"Failed to restore file: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Storage Cleanup Endpoints
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/cleanup", methods=["POST"])
def cleanup_storage():
    """Cleanup storage (cache, temp files, old backups)"""
    try:
        data = request.get_json() or {}
        cleanup_days = data.get('cleanup_days', 30)
        
        storage_manager = get_storage_manager()
        
        # Run cleanup in background
        async def run_cleanup():
            return await storage_manager.cleanup_storage(cleanup_days)
        
        cleanup_task = asyncio.create_task(run_cleanup())
        cleanup_result = asyncio.run(cleanup_task)
        
        return jsonify({
            "status": "success",
            "message": "Storage cleanup completed",
            "data": cleanup_result
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up storage: {e}")
        return jsonify({
            "error": f"Failed to cleanup storage: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/health", methods=["GET"])
def health_check():
    """Perform health check on storage system"""
    try:
        storage_manager = get_storage_manager()
        
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        # Check local storage
        local_quota = storage_manager.local_manager.quota
        local_usage = local_quota._get_quota_info()
        
        local_health = {
            "status": "healthy",
            "available_space": local_usage['available_bytes'],
            "usage_percentage": local_usage['usage_percentage'],
            "quota_exceeded": local_quota.is_quota_exceeded()
        }
        
        if local_quota.is_quota_exceeded():
            local_health["status"] = "degraded"
            health_status["overall_status"] = "degraded"
        
        health_status["components"]["local_storage"] = local_health
        
        # Check S3 storage
        if storage_manager.s3_manager:
            try:
                s3_usage = storage_manager.s3_manager.get_storage_usage()
                s3_health = {
                    "status": "healthy",
                    "bucket_accessible": True,
                    "s3_usage": s3_usage
                }
                
                # Test S3 connectivity with a simple HEAD request
                storage_manager.s3_manager.s3_client.head_bucket(
                    Bucket=storage_manager.s3_manager.config.bucket_name
                )
                
            except Exception as e:
                s3_health = {
                    "status": "unhealthy",
                    "bucket_accessible": False,
                    "error": str(e)
                }
                health_status["overall_status"] = "degraded"
            
            health_status["components"]["s3_storage"] = s3_health
        else:
            health_status["components"]["s3_storage"] = {
                "status": "not_configured"
            }
        
        # Check sync service
        sync_health = {
            "status": "healthy",
            "auto_sync_enabled": storage_manager.auto_sync,
            "is_syncing": storage_manager.is_syncing,
            "last_sync_time": storage_manager.last_sync_time.isoformat() if storage_manager.last_sync_time else None
        }
        
        health_status["components"]["sync_service"] = sync_health
        
        return jsonify({
            "status": "success",
            "data": health_status
        })
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({
            "error": f"Health check failed: {str(e)}",
            "success": False
        }), 500


# -------------------------------------------------------------------------
# Advanced Storage Operations
# -------------------------------------------------------------------------

@desktop_storage_bp.route("/api/storage/migrate", methods=["POST"])
def migrate_storage():
    """Migrate storage to new location"""
    try:
        data = request.get_json()
        new_path = data.get('new_path')
        
        if not new_path:
            return jsonify({
                "error": "new_path is required",
                "success": False
            }), 400
        
        storage_manager = get_storage_manager()
        
        # This is a placeholder for storage migration functionality
        # In a complete implementation, this would:
        # 1. Stop all sync operations
        # 2. Copy all data to new location
        # 3. Update configuration
        # 4. Restart services
        # 5. Verify integrity
        
        return jsonify({
            "status": "not_implemented",
            "message": "Storage migration requires implementation",
            "requested_path": new_path
        })
        
    except Exception as e:
        logger.error(f"Error in storage migration: {e}")
        return jsonify({
            "error": f"Storage migration failed: {str(e)}",
            "success": False
        }), 500


@desktop_storage_bp.route("/api/storage/export", methods=["GET"])
def export_storage_manifest():
    """Export storage manifest"""
    try:
        storage_manager = get_storage_manager()
        
        # Get all files with metadata
        files = storage_manager.local_manager.list_files(limit=10000)
        
        # Create manifest
        manifest = {
            "export_timestamp": datetime.now().isoformat(),
            "total_files": len(files),
            "storage_stats": storage_manager.get_comprehensive_stats(),
            "files": files
        }
        
        return jsonify({
            "status": "success",
            "data": manifest
        })
        
    except Exception as e:
        logger.error(f"Error exporting storage manifest: {e}")
        return jsonify({
            "error": f"Failed to export storage manifest: {str(e)}",
            "success": False
        }), 500


logger.info("Desktop storage API endpoints registered successfully")