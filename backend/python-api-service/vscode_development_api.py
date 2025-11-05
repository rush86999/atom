"""
VS Code Development API Endpoints
Complete VS Code development environment management with LanceDB integration
"""

import os
import logging
import json
import asyncio
import tempfile
import shutil
from datetime import datetime, timezone
from flask import request, jsonify, Blueprint, send_file
from typing import Dict, Any, Optional, List
from werkzeug.utils import secure_filename

# Import VS Code LanceDB service
try:
    from vscode_lancedb_ingestion_service import (
        vscode_lancedb_service,
        VSCodeMemorySettings
    )
    VSCODE_LANCEDB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"VS Code LanceDB service not available: {e}")
    VSCODE_LANCEDB_AVAILABLE = False
    vscode_lancedb_service = None

# Import VS Code enhanced service
try:
    from vscode_enhanced_service import vscode_enhanced_service
    VSCODE_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"VS Code service not available: {e}")
    VSCODE_SERVICE_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
vscode_development_bp = Blueprint("vscode_development_bp", __name__)

# Error handling decorator
def handle_vscode_development_errors(func):
    """Decorator to handle VS Code development API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"VS Code development API error: {e}")
            return jsonify({
                "ok": False,
                "error": str(e),
                "error_type": "api_error"
            }), 500
    return wrapper

# Authentication decorator
def require_user_auth(func):
    """Decorator to require user authentication"""
    def wrapper(*args, **kwargs):
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id') or request.headers.get('X-User-ID')
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "User ID is required"
            }), 400
        
        return func(*args, **kwargs)
    return wrapper

# File upload validation
ALLOWED_EXTENSIONS = {
    'txt', 'py', 'js', 'ts', 'jsx', 'tsx', 'json', 'yaml', 'yml',
    'html', 'htm', 'css', 'scss', 'sass', 'less', 'md', 'markdown',
    'sql', 'xml', 'csv', 'log', 'conf', 'cfg', 'ini', 'toml',
    'go', 'rs', 'java', 'cpp', 'c', 'cs', 'php', 'rb', 'swift',
    'kt', 'scala', 'r', 'm', 'dart', 'lua', 'sh', 'ps1',
    'bat', 'cmd', 'graphql', 'dockerfile', 'gitignore', 'editorconfig'
}

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@vscode_development_bp.route("/api/vscode/development/health", methods=["GET"])
@handle_vscode_development_errors
def health():
    """Health check for VS Code development service"""
    try:
        service_info = {
            "service": "vscode-development-api",
            "status": "healthy",
            "version": "1.0.0",
            "features": {
                "lancedb_available": VSCODE_LANCEDB_AVAILABLE,
                "vscode_service_available": VSCODE_SERVICE_AVAILABLE,
                "file_operations": True,
                "workspace_management": True,
                "extension_management": True,
                "git_integration": True,
                "ingestion_available": True,
                "search_available": True,
                "user_controls_available": True
            }
        }
        
        return jsonify({
            "ok": True,
            **service_info
        })
        
    except Exception as e:
        logger.error(f"VS Code development health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Workspace Management
@vscode_development_bp.route("/api/vscode/development/workspace/info", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_workspace_info():
    """Get VS Code workspace information"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        workspace_info = loop.run_until_complete(
            vscode_enhanced_service.get_workspace_info(workspace_path, user_id)
        )
        loop.close()
        
        if workspace_info:
            return jsonify({
                "ok": True,
                "workspace": workspace_info.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to get workspace information",
                "error_type": "workspace_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error getting VS Code workspace info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/workspace/search", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def search_workspace():
    """Search files in VS Code workspace"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        search_query = data.get('search_query', '')
        file_pattern = data.get('file_pattern')
        case_sensitive = data.get('case_sensitive', False)
        include_content = data.get('include_content', True)
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        search_results = loop.run_until_complete(
            vscode_enhanced_service.search_workspace_files(
                workspace_path=workspace_path,
                search_query=search_query,
                file_pattern=file_pattern,
                case_sensitive=case_sensitive,
                include_content=include_content
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "results": search_results,
            "count": len(search_results),
            "search_filters": {
                "query": search_query,
                "pattern": file_pattern,
                "case_sensitive": case_sensitive,
                "include_content": include_content
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching VS Code workspace: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# File Operations
@vscode_development_bp.route("/api/vscode/development/files/content", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_file_content():
    """Get file content from VS Code project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        file_path = data.get('file_path')
        encoding = data.get('encoding', 'utf-8')
        max_size = data.get('max_size', 1024 * 1024)
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file_content = loop.run_until_complete(
            vscode_enhanced_service.get_file_content(
                workspace_path=workspace_path,
                file_path=file_path,
                encoding=encoding,
                max_size=max_size
            )
        )
        loop.close()
        
        if file_content:
            return jsonify({
                "ok": True,
                "file": file_content.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "File not found or unreadable",
                "error_type": "file_error"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting VS Code file content: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/files/create", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def create_file():
    """Create file in VS Code project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        file_path = data.get('file_path')
        content = data.get('content', '')
        encoding = data.get('encoding', 'utf-8')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            vscode_enhanced_service.create_file(
                workspace_path=workspace_path,
                file_path=file_path,
                content=content,
                encoding=encoding
            )
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "File created successfully",
                "file_path": file_path
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create file",
                "error_type": "file_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating VS Code file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/files/update", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def update_file():
    """Update file in VS Code project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        file_path = data.get('file_path')
        content = data.get('content', '')
        encoding = data.get('encoding', 'utf-8')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            vscode_enhanced_service.update_file(
                workspace_path=workspace_path,
                file_path=file_path,
                content=content,
                encoding=encoding
            )
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "File updated successfully",
                "file_path": file_path
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to update file",
                "error_type": "file_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error updating VS Code file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/files/delete", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def delete_file():
    """Delete file from VS Code project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        file_path = data.get('file_path')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            vscode_enhanced_service.delete_file(
                workspace_path=workspace_path,
                file_path=file_path
            )
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "File deleted successfully",
                "file_path": file_path
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete file",
                "error_type": "file_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting VS Code file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/files/upload", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def upload_file():
    """Upload file to VS Code project"""
    try:
        user_id = request.form.get('user_id')
        workspace_path = request.form.get('workspace_path')
        upload_path = request.form.get('upload_path', '')
        
        if not user_id or not workspace_path:
            return jsonify({
                "ok": False,
                "error": "User ID and workspace path are required"
            }), 400
        
        if 'file' not in request.files:
            return jsonify({
                "ok": False,
                "error": "No file provided"
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                "ok": False,
                "error": "No file selected"
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "ok": False,
                "error": "File type not allowed"
            }), 400
        
        # Secure filename
        filename = secure_filename(file.filename)
        
        # Create target path
        if upload_path:
            target_path = os.path.join(workspace_path, upload_path, filename)
        else:
            target_path = os.path.join(workspace_path, filename)
        
        # Create directory if needed
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Save file
        file.save(target_path)
        
        # Log activity if LanceDB is available
        if VSCODE_LANCEDB_AVAILABLE:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                await vscode_lancedb_service.ingest_vscode_activity(
                    user_id=user_id,
                    activity_data={
                        'action_type': 'file_upload',
                        'file_path': os.path.relpath(target_path, workspace_path),
                        'content': f'Uploaded file: {filename}',
                        'metadata': {
                            'original_filename': file.filename,
                            'size': os.path.getsize(target_path),
                            'upload_path': upload_path
                        }
                    }
                )
                loop.close()
            except:
                pass
        
        return jsonify({
            "ok": True,
            "message": "File uploaded successfully",
            "filename": filename,
            "file_path": os.path.relpath(target_path, workspace_path),
            "size": os.path.getsize(target_path)
        })
        
    except Exception as e:
        logger.error(f"Error uploading VS Code file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/files/download", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def download_file():
    """Download file from VS Code project"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        file_path = data.get('file_path')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Get file content
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file_content = loop.run_until_complete(
            vscode_enhanced_service.get_file_content(workspace_path, file_path)
        )
        loop.close()
        
        if not file_content:
            return jsonify({
                "ok": False,
                "error": "File not found",
                "error_type": "file_error"
            }), 404
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_content.extension)
        try:
            temp_file.write(file_content.content.encode(file_content.encoding))
            temp_file.close()
            
            # Log activity if LanceDB is available
            if VSCODE_LANCEDB_AVAILABLE:
                try:
                    await vscode_lancedb_service.ingest_vscode_activity(
                        user_id=user_id,
                        activity_data={
                            'action_type': 'file_download',
                            'file_path': file_path,
                            'content': f'Downloaded file: {file_content.name}',
                            'metadata': {
                                'original_filename': file_content.name,
                                'size': file_content.size,
                                'encoding': file_content.encoding
                            }
                        }
                    )
                except:
                    pass
            
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=file_content.name,
                mimetype='application/octet-stream'
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        
    except Exception as e:
        logger.error(f"Error downloading VS Code file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Extension Management
@vscode_development_bp.route("/api/vscode/development/extensions/search", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def search_extensions():
    """Search VS Code extensions"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        category = data.get('category')
        page_size = data.get('page_size', 50)
        page_number = data.get('page_number', 1)
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        extensions = loop.run_until_complete(
            vscode_enhanced_service.search_extensions(
                query=query,
                category=category,
                page_size=page_size,
                page_number=page_number
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "extensions": extensions,
            "count": len(extensions),
            "search_filters": {
                "query": query,
                "category": category,
                "page_size": page_size,
                "page_number": page_number
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching VS Code extensions: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/extensions/info", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_extension_info():
    """Get VS Code extension information"""
    try:
        data = request.get_json()
        extension_id = data.get('extension_id')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        extension_info = loop.run_until_complete(
            vscode_enhanced_service.get_extension_info(extension_id)
        )
        loop.close()
        
        if extension_info:
            return jsonify({
                "ok": True,
                "extension": extension_info.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Extension not found",
                "error_type": "extension_error"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting VS Code extension info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/extensions/recommendations", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_recommended_extensions():
    """Get recommended extensions for project"""
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        language = data.get('language')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        recommendations = loop.run_until_complete(
            vscode_enhanced_service.get_recommended_extensions(
                project_path=project_path,
                language=language
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "recommendations": recommendations,
            "count": len(recommendations),
            "filters": {
                "project_path": project_path,
                "language": language
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting VS Code extension recommendations: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Memory Management
@vscode_development_bp.route("/api/vscode/development/memory/settings", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_memory_settings():
    """Get VS Code memory settings for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        settings = loop.run_until_complete(
            vscode_lancedb_service.get_user_settings(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "settings": {
                "user_id": settings.user_id,
                "ingestion_enabled": settings.ingestion_enabled,
                "sync_frequency": settings.sync_frequency,
                "data_retention_days": settings.data_retention_days,
                "include_projects": settings.include_projects or [],
                "exclude_projects": settings.exclude_projects or [],
                "include_file_types": settings.include_file_types or [],
                "exclude_file_types": settings.exclude_file_types or [],
                "max_file_size_mb": settings.max_file_size_mb,
                "max_files_per_project": settings.max_files_per_project,
                "include_hidden_files": settings.include_hidden_files,
                "include_binary_files": settings.include_binary_files,
                "code_search_enabled": settings.code_search_enabled,
                "semantic_search_enabled": settings.semantic_search_enabled,
                "metadata_extraction_enabled": settings.metadata_extraction_enabled,
                "activity_logging_enabled": settings.activity_logging_enabled,
                "last_sync_timestamp": settings.last_sync_timestamp,
                "next_sync_timestamp": settings.next_sync_timestamp,
                "sync_in_progress": settings.sync_in_progress,
                "error_message": settings.error_message,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting VS Code memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/memory/settings", methods=["PUT"])
@handle_vscode_development_errors
@require_user_auth
def save_memory_settings():
    """Save VS Code memory settings for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        # Validate settings
        valid_frequencies = ["real-time", "hourly", "daily", "weekly", "manual"]
        sync_frequency = data.get('sync_frequency', 'real-time')
        if sync_frequency not in valid_frequencies:
            return jsonify({
                "ok": False,
                "error": f"Invalid sync frequency. Must be one of: {valid_frequencies}",
                "error_type": "validation_error"
            }), 400
        
        # Create settings object
        settings = VSCodeMemorySettings(
            user_id=user_id,
            ingestion_enabled=data.get('ingestion_enabled', True),
            sync_frequency=sync_frequency,
            data_retention_days=data.get('data_retention_days', 365),
            include_projects=data.get('include_projects', []),
            exclude_projects=data.get('exclude_projects', []),
            include_file_types=data.get('include_file_types', []),
            exclude_file_types=data.get('exclude_file_types', []),
            max_file_size_mb=data.get('max_file_size_mb', 10),
            max_files_per_project=data.get('max_files_per_project', 10000),
            include_hidden_files=data.get('include_hidden_files', False),
            include_binary_files=data.get('include_binary_files', False),
            code_search_enabled=data.get('code_search_enabled', True),
            semantic_search_enabled=data.get('semantic_search_enabled', True),
            metadata_extraction_enabled=data.get('metadata_extraction_enabled', True),
            activity_logging_enabled=data.get('activity_logging_enabled', True)
        )
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            vscode_lancedb_service.save_user_settings(settings)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "VS Code memory settings saved successfully",
                "settings": {
                    "user_id": settings.user_id,
                    "ingestion_enabled": settings.ingestion_enabled,
                    "sync_frequency": settings.sync_frequency,
                    "updated_at": settings.updated_at
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to save VS Code memory settings",
                "error_type": "save_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error saving VS Code memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/memory/ingest", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def start_ingestion():
    """Start VS Code project ingestion"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        project_path = data.get('project_path')
        force_sync = data.get('force_sync', False)
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            vscode_lancedb_service.ingest_vscode_project(
                user_id=user_id,
                project_path=project_path,
                force_sync=force_sync
            )
        )
        loop.close()
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "ingestion_result": {
                    "project_ingested": result.get('project_ingested'),
                    "files_ingested": result.get('files_ingested', 0),
                    "total_size_mb": result.get('total_size_mb', 0),
                    "batch_id": result.get('batch_id'),
                    "next_sync": result.get('next_sync'),
                    "sync_frequency": result.get('sync_frequency')
                },
                "message": "VS Code project ingestion completed successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown ingestion error'),
                "error_type": result.get('error_type', 'ingestion_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting VS Code ingestion: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/memory/status", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_memory_status():
    """Get VS Code memory synchronization status"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        status = loop.run_until_complete(
            vscode_lancedb_service.get_sync_status(user_id)
        )
        loop.close()
        
        if status.get('error'):
            return jsonify({
                "ok": False,
                "error": status.get('error'),
                "error_type": status.get('error_type', 'status_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "memory_status": status
        })
        
    except Exception as e:
        logger.error(f"Error getting VS Code memory status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/memory/search", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def search_memory():
    """Search VS Code files in memory"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        project_id = data.get('project_id')
        language = data.get('language')
        limit = data.get('limit', 50)
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        files = loop.run_until_complete(
            vscode_lancedb_service.search_vscode_files(
                user_id=user_id,
                query=query,
                project_id=project_id,
                language=language,
                limit=limit,
                date_from=date_from,
                date_to=date_to
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "files": files,
            "count": len(files),
            "search_filters": {
                "query": query,
                "project_id": project_id,
                "language": language,
                "limit": limit,
                "date_from": date_from,
                "date_to": date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching VS Code memory: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/memory/ingestion-stats", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_ingestion_stats():
    """Get VS Code ingestion statistics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(
            vscode_lancedb_service.get_ingestion_stats(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "ingestion_stats": {
                "user_id": stats.user_id,
                "total_projects_ingested": stats.total_projects_ingested,
                "total_files_ingested": stats.total_files_ingested,
                "total_activities_ingested": stats.total_activities_ingested,
                "last_ingestion_timestamp": stats.last_ingestion_timestamp,
                "total_size_mb": stats.total_size_mb,
                "failed_ingestions": stats.failed_ingestions,
                "last_error_message": stats.last_error_message,
                "avg_files_per_project": stats.avg_files_per_project,
                "avg_processing_time_ms": stats.avg_processing_time_ms,
                "created_at": stats.created_at,
                "updated_at": stats.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting VS Code ingestion stats: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/memory/delete", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def delete_user_data():
    """Delete all VS Code data for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        confirm = data.get('confirm', False)
        
        if not VSCODE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code LanceDB service not available"
            }), 503
        
        if not confirm:
            return jsonify({
                "ok": False,
                "error": "Confirmation required to delete VS Code data",
                "error_type": "confirmation_required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            vscode_lancedb_service.delete_user_data(user_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "All VS Code data deleted successfully",
                "deleted_at": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete VS Code data",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting VS Code user data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility Endpoints
@vscode_development_bp.route("/api/vscode/development/workspace/languages", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def get_workspace_languages():
    """Get language statistics for workspace"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_path = data.get('workspace_path')
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        language_stats = loop.run_until_complete(
            vscode_enhanced_service.get_workspace_languages(workspace_path)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "language_stats": language_stats,
            "workspace_path": workspace_path
        })
        
    except Exception as e:
        logger.error(f"Error getting VS Code workspace languages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@vscode_development_bp.route("/api/vscode/development/activity/log", methods=["POST"])
@handle_vscode_development_errors
@require_user_auth
def log_development_activity():
    """Log development activity"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        activity_data = data.get('activity', {})
        
        if not VSCODE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "VS Code service not available"
            }), 503
        
        # Log activity
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            vscode_enhanced_service.log_development_activity(
                user_id=user_id,
                project_id=activity_data.get('project_id', ''),
                action_type=activity_data.get('action_type', ''),
                file_path=activity_data.get('file_path', ''),
                content=activity_data.get('content', ''),
                session_id=activity_data.get('session_id'),
                metadata=activity_data.get('metadata', {})
            )
        )
        loop.close()
        
        # Also store in memory if available
        if success and VSCODE_LANCEDB_AVAILABLE:
            try:
                await vscode_lancedb_service.ingest_vscode_activity(
                    user_id=user_id,
                    activity_data=activity_data
                )
            except:
                pass
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Development activity logged successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to log development activity",
                "error_type": "activity_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error logging development activity: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Export components
__all__ = [
    'vscode_development_bp'
]