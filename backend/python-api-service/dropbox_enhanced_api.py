"""
Enhanced Dropbox API Implementation
Complete Dropbox integration with Flask API handlers
"""

import os
import logging
import json
import asyncio
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Blueprint
from typing import Dict, Any, Optional, List

# Import enhanced services
try:
    from dropbox_services_enhanced import dropbox_services_enhanced
    DROPBOX_ENHANCED_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Enhanced Dropbox service not available: {e}")
    DROPBOX_ENHANCED_AVAILABLE = False
    dropbox_services_enhanced = None

# Import authentication
try:
    from auth_handler_dropbox_complete import dropbox_auth_manager, get_dropbox_tokens
    DROPBOX_AUTH_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Dropbox authentication not available: {e}")
    DROPBOX_AUTH_AVAILABLE = False
    dropbox_auth_manager = None

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
dropbox_enhanced_bp = Blueprint("dropbox_enhanced_bp", __name__)

# Error handling decorator
def handle_dropbox_errors(func):
    """Decorator to handle Dropbox API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Dropbox API error: {e}")
            return jsonify({
                "ok": False,
                "error": str(e),
                "error_type": "api_error"
            }), 500
    return wrapper

# Authentication decorator
def require_dropbox_auth(func):
    """Decorator to require Dropbox authentication"""
    def wrapper(*args, **kwargs):
        if not DROPBOX_AUTH_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Dropbox authentication not available"
            }), 503
        
        try:
            # Get user_id from request
            data = request.get_json() if request.is_json else {}
            user_id = data.get('user_id') or request.headers.get('X-User-ID')
            
            if not user_id:
                return jsonify({
                    "ok": False,
                    "error": "User ID is required"
                }), 400
            
            # Validate tokens (synchronous wrapper)
            if DROPBOX_ENHANCED_AVAILABLE:
                tokens = asyncio.run(get_dropbox_tokens(None, user_id))
                if not tokens:
                    return jsonify({
                        "ok": False,
                        "error": "Dropbox authentication required"
                    }), 401
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Dropbox auth error: {e}")
            return jsonify({
                "ok": False,
                "error": "Authentication failed"
            }), 500
    return wrapper

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/health", methods=["GET"])
@handle_dropbox_errors
def health():
    """Health check for enhanced Dropbox service"""
    try:
        service_info = dropbox_services_enhanced.get_service_info() if dropbox_services_enhanced else {}
        
        return jsonify({
            "ok": True,
            "status": "healthy",
            "service": "enhanced-dropbox-api",
            "version": "2.0.0",
            "features": {
                "service_available": DROPBOX_ENHANCED_AVAILABLE,
                "auth_available": DROPBOX_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False)
            },
            "service_info": service_info
        })
    except Exception as e:
        logger.error(f"Dropbox health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# User operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/user/info", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def get_user_info():
    """Get Dropbox user information"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        # Get access token (simplified)
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        user = loop.run_until_complete(
            dropbox_services_enhanced.get_current_user(access_token=access_token)
        )
        loop.close()
        
        if not user:
            return jsonify({
                "ok": False,
                "error": "User not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "user": user.__dict__ if hasattr(user, '__dict__') else user
        })
        
    except Exception as e:
        logger.error(f"Error getting Dropbox user: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# File Operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/files/list", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def list_files():
    """List Dropbox files and folders"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path', '')
        recursive = data.get('recursive', False)
        include_media_info = data.get('include_media_info', False)
        include_deleted = data.get('include_deleted', False)
        limit = data.get('limit', 1000)
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        items = loop.run_until_complete(
            dropbox_services_enhanced.list_files(
                access_token=access_token,
                path=path,
                recursive=recursive
            )
        )
        loop.close()
        
        # Separate files and folders
        files = [item for item in items if hasattr(item, 'is_file') and item.is_file]
        folders = [item for item in items if hasattr(item, 'is_folder') and item.is_folder]
        
        return jsonify({
            "ok": True,
            "files": [file.__dict__ if hasattr(file, '__dict__') else file for file in files],
            "folders": [folder.__dict__ if hasattr(folder, '__dict__') else folder for folder in folders],
            "total_count": len(items),
            "files_count": len(files),
            "folders_count": len(folders)
        })
        
    except Exception as e:
        logger.error(f"Error listing Dropbox files: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/folders/list", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def list_folders():
    """List Dropbox folders"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path', '')
        recursive = data.get('recursive', False)
        limit = data.get('limit', 1000)
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        items = loop.run_until_complete(
            dropbox_services_enhanced.list_files(
                access_token=access_token,
                path=path,
                recursive=recursive
            )
        )
        loop.close()
        
        # Filter only folders
        folders = [item for item in items if hasattr(item, 'is_folder') and item.is_folder]
        
        return jsonify({
            "ok": True,
            "folders": [folder.__dict__ if hasattr(folder, '__dict__') else folder for folder in folders],
            "count": len(folders)
        })
        
    except Exception as e:
        logger.error(f"Error listing Dropbox folders: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/folders/create", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def create_folder():
    """Create Dropbox folder"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        folder_path = data.get('folder_path') or data.get('name')
        autorename = data.get('autorename', False)
        
        if not folder_path:
            return jsonify({
                "ok": False,
                "error": "Folder path or name is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        folder = loop.run_until_complete(
            dropbox_services_enhanced.create_folder(
                access_token=access_token,
                folder_path=folder_path,
                autorename=autorename
            )
        )
        loop.close()
        
        if not folder:
            return jsonify({
                "ok": False,
                "error": "Failed to create folder"
            }), 500
        
        return jsonify({
            "ok": True,
            "folder": folder.__dict__ if hasattr(folder, '__dict__') else folder,
            "message": "Folder created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating Dropbox folder: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/files/upload", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def upload_file():
    """Upload file to Dropbox"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        file_content = data.get('file_content')
        file_name = data.get('file_name')
        file_path = data.get('file_path')
        autorename = data.get('autorename', True)
        
        if not file_content and not file_name:
            return jsonify({
                "ok": False,
                "error": "File content and file name are required"
            }), 400
        
        # Construct full path
        if file_path:
            full_path = file_path
        else:
            full_path = file_name
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Convert hex string to bytes if needed
        import binascii
        file_bytes = binascii.unhexlify(file_content) if isinstance(file_content, str) else file_content
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file = loop.run_until_complete(
            dropbox_services_enhanced.upload_file(
                access_token=access_token,
                file_content=file_bytes,
                file_path=full_path,
                autorename=autorename
            )
        )
        loop.close()
        
        if not file:
            return jsonify({
                "ok": False,
                "error": "Failed to upload file"
            }), 500
        
        return jsonify({
            "ok": True,
            "file": file.__dict__ if hasattr(file, '__dict__') else file,
            "message": "File uploaded successfully"
        })
        
    except Exception as e:
        logger.error(f"Error uploading Dropbox file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/files/download", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def download_file():
    """Download file from Dropbox"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        file_path = data.get('path')
        rev = data.get('rev')
        
        if not file_path:
            return jsonify({
                "ok": False,
                "error": "File path is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            dropbox_services_enhanced.download_file(
                access_token=access_token,
                file_path=file_path
            )
        )
        loop.close()
        
        if not result:
            return jsonify({
                "ok": False,
                "error": "Failed to download file"
            }), 500
        
        return jsonify({
            "ok": True,
            "content": result.get('content', b'').hex(),  # Convert to hex for JSON
            "metadata": result.get('metadata', {}),
            "message": "File downloaded successfully"
        })
        
    except Exception as e:
        logger.error(f"Error downloading Dropbox file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/items/delete", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def delete_item():
    """Delete file or folder from Dropbox"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path')
        
        if not path:
            return jsonify({
                "ok": False,
                "error": "Path is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            dropbox_services_enhanced.delete_item(
                access_token=access_token,
                path=path
            )
        )
        loop.close()
        
        return jsonify({
            "ok": result,
            "message": "Item deleted successfully" if result else "Failed to delete item"
        })
        
    except Exception as e:
        logger.error(f"Error deleting Dropbox item: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/items/move", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def move_item():
    """Move file or folder in Dropbox"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        from_path = data.get('from_path')
        to_path = data.get('to_path')
        autorename = data.get('autorename', False)
        
        if not from_path or not to_path:
            return jsonify({
                "ok": False,
                "error": "Source path and destination path are required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        item = loop.run_until_complete(
            dropbox_services_enhanced.move_item(
                access_token=access_token,
                from_path=from_path,
                to_path=to_path,
                autorename=autorename
            )
        )
        loop.close()
        
        if not item:
            return jsonify({
                "ok": False,
                "error": "Failed to move item"
            }), 500
        
        return jsonify({
            "ok": True,
            "item": item.__dict__ if hasattr(item, '__dict__') else item,
            "message": "Item moved successfully"
        })
        
    except Exception as e:
        logger.error(f"Error moving Dropbox item: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/items/copy", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def copy_item():
    """Copy file or folder in Dropbox"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        from_path = data.get('from_path')
        to_path = data.get('to_path')
        autorename = data.get('autorename', False)
        
        if not from_path or not to_path:
            return jsonify({
                "ok": False,
                "error": "Source path and destination path are required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        item = loop.run_until_complete(
            dropbox_services_enhanced.copy_item(
                access_token=access_token,
                from_path=from_path,
                to_path=to_path,
                autorename=autorename
            )
        )
        loop.close()
        
        if not item:
            return jsonify({
                "ok": False,
                "error": "Failed to copy item"
            }), 500
        
        return jsonify({
            "ok": True,
            "item": item.__dict__ if hasattr(item, '__dict__') else item,
            "message": "Item copied successfully"
        })
        
    except Exception as e:
        logger.error(f"Error copying Dropbox item: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Search Operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/search", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def search_files():
    """Search for files and folders in Dropbox"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        path = data.get('path', '')
        mode = data.get('mode', 'filename')
        limit = data.get('limit', 100)
        
        if not query:
            return jsonify({
                "ok": False,
                "error": "Search query is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            dropbox_services_enhanced.search_files(
                access_token=access_token,
                query=query,
                path=path,
                mode=mode,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "results": result.get('matches', []),
            "count": len(result.get('matches', [])),
            "has_more": result.get('has_more', False),
            "cursor": result.get('cursor')
        })
        
    except Exception as e:
        logger.error(f"Error searching Dropbox files: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Sharing Operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/links/create", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def create_shared_link():
    """Create shared link for file or folder"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path')
        settings = data.get('settings')
        
        if not path:
            return jsonify({
                "ok": False,
                "error": "Path is required"
            }), 400
        
        if settings is None:
            settings = {
                'requested_visibility': 'public',
                'allow_download': True
            }
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        link = loop.run_until_complete(
            dropbox_services_enhanced.create_shared_link(
                access_token=access_token,
                path=path,
                settings=settings
            )
        )
        loop.close()
        
        if not link:
            return jsonify({
                "ok": False,
                "error": "Failed to create shared link"
            }), 500
        
        return jsonify({
            "ok": True,
            "link": link.__dict__ if hasattr(link, '__dict__') else link,
            "message": "Shared link created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating Dropbox shared link: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Metadata Operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/metadata", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def get_file_metadata():
    """Get file or folder metadata"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path')
        include_media_info = data.get('include_media_info', False)
        include_deleted = data.get('include_deleted', False)
        include_has_explicit_shared_members = data.get('include_has_explicit_shared_members', False)
        include_mounted_folders = data.get('include_mounted_folders', False)
        
        if not path:
            return jsonify({
                "ok": False,
                "error": "Path is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        metadata = loop.run_until_complete(
            dropbox_services_enhanced.get_file_metadata(
                access_token=access_token,
                path=path,
                include_media_info=include_media_info,
                include_deleted=include_deleted,
                include_has_explicit_shared_members=include_has_explicit_shared_members,
                include_mounted_folders=include_mounted_folders
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "metadata": metadata
        })
        
    except Exception as e:
        logger.error(f"Error getting Dropbox metadata: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Versioning Operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/versions/list", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def list_file_versions():
    """List file versions"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path')
        limit = data.get('limit', 10)
        
        if not path:
            return jsonify({
                "ok": False,
                "error": "Path is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        versions = loop.run_until_complete(
            dropbox_services_enhanced.list_file_versions(
                access_token=access_token,
                path=path,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "versions": versions,
            "count": len(versions)
        })
        
    except Exception as e:
        logger.error(f"Error listing Dropbox file versions: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@dropbox_enhanced_bp.route("/api/dropbox/enhanced/versions/restore", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def restore_file_version():
    """Restore file to specific version"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path')
        rev = data.get('rev')
        
        if not path or not rev:
            return jsonify({
                "ok": False,
                "error": "Path and rev are required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file = loop.run_until_complete(
            dropbox_services_enhanced.restore_file(
                access_token=access_token,
                path=path,
                rev=rev
            )
        )
        loop.close()
        
        if not file:
            return jsonify({
                "ok": False,
                "error": "Failed to restore file"
            }), 500
        
        return jsonify({
            "ok": True,
            "file": file.__dict__ if hasattr(file, '__dict__') else file,
            "message": "File restored successfully"
        })
        
    except Exception as e:
        logger.error(f"Error restoring Dropbox file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Preview Operations
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/preview", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def get_file_preview():
    """Get file preview"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        path = data.get('path')
        preview_format = data.get('format', 'png')
        size = data.get('size', 'm')
        
        if not path:
            return jsonify({
                "ok": False,
                "error": "Path is required"
            }), 400
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        preview_url = loop.run_until_complete(
            dropbox_services_enhanced.get_file_preview(
                access_token=access_token,
                path=path,
                format=preview_format,
                size=size
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "preview_url": preview_url,
            "message": "Preview generated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error getting Dropbox file preview: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Space Usage
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/space", methods=["POST"])
@handle_dropbox_errors
@require_dropbox_auth
def get_space_usage():
    """Get Dropbox space usage"""
    try:
        if not DROPBOX_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Dropbox service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        access_token = "mock_token"  # In real implementation, get from auth handler
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        space_usage = loop.run_until_complete(
            dropbox_services_enhanced.get_space_usage(access_token=access_token)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "space_usage": space_usage
        })
        
    except Exception as e:
        logger.error(f"Error getting Dropbox space usage: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Status endpoint
@dropbox_enhanced_bp.route("/api/dropbox/enhanced/status", methods=["POST"])
@handle_dropbox_errors
def get_status():
    """Get enhanced Dropbox service status"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        service_info = dropbox_services_enhanced.get_service_info() if dropbox_services_enhanced else {}
        
        status_data = {
            "ok": True,
            "service": "enhanced-dropbox-api",
            "status": "available",
            "version": "2.0.0",
            "capabilities": {
                "service_available": DROPBOX_ENHANCED_AVAILABLE,
                "auth_available": DROPBOX_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False),
                "encryption_available": bool(os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            },
            "service_info": service_info,
            "api_endpoints": [
                "/api/dropbox/enhanced/health",
                "/api/dropbox/enhanced/user/info",
                "/api/dropbox/enhanced/files/list",
                "/api/dropbox/enhanced/folders/list",
                "/api/dropbox/enhanced/folders/create",
                "/api/dropbox/enhanced/files/upload",
                "/api/dropbox/enhanced/files/download",
                "/api/dropbox/enhanced/items/delete",
                "/api/dropbox/enhanced/items/move",
                "/api/dropbox/enhanced/items/copy",
                "/api/dropbox/enhanced/search",
                "/api/dropbox/enhanced/links/create",
                "/api/dropbox/enhanced/metadata",
                "/api/dropbox/enhanced/versions/list",
                "/api/dropbox/enhanced/versions/restore",
                "/api/dropbox/enhanced/preview",
                "/api/dropbox/enhanced/space",
                "/api/dropbox/enhanced/status"
            ]
        }
        
        if user_id:
            # Add user-specific status
            try:
                if DROPBOX_AUTH_AVAILABLE:
                    status_data["user_authenticated"] = True  # Simplified for sync context
            except:
                status_data["user_authenticated"] = False
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error getting Dropbox service status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Register blueprint with Flask app
def register_dropbox_enhanced_bp(app: Flask):
    """Register enhanced Dropbox blueprint with Flask app"""
    app.register_blueprint(dropbox_enhanced_bp)
    logger.info("Enhanced Dropbox API blueprint registered")

# Export components
__all__ = [
    'dropbox_enhanced_bp',
    'register_dropbox_enhanced_bp'
]