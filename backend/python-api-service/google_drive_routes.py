"""
Google Drive API Routes
Core API endpoints for Google Drive integration, authentication, and file operations
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from functools import wraps
from contextlib import asynccontextmanager

# Google Drive imports
try:
    from google_drive_service import get_google_drive_service, GoogleDriveFile
    from google_drive_auth import get_google_drive_auth
    from google_drive_memory import get_google_drive_memory_service
    from google_drive_search_integration import get_google_drive_search_provider
    from ingestion_pipeline.content_extractor import get_content_extractor, ExtractedContent
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logging.warning("Google Drive services not available")

# Local imports
from loguru import logger
from config import get_config_instance
from extensions import redis_client

# Create Blueprint
google_drive_bp = Blueprint('google_drive', __name__, url_prefix='/api/google-drive')

# ==================== DECORATORS ====================

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.headers.get('X-Session-ID') or request.json.get('session_id') if request.json else None
        
        if not session_id:
            return jsonify({
                "success": False,
                "error": "Session ID required"
            }), 401
        
        # Validate session
        async def validate():
            auth_service = await get_google_drive_auth()
            if not auth_service:
                return None
            
            return await auth_service.validate_session(session_id)
        
        # Run validation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(validate())
        finally:
            loop.close()
        
        if not result or not result.get("valid"):
            return jsonify({
                "success": False,
                "error": result.get("error", "Invalid session")
            }), 401
        
        # Store session in request context
        request.google_drive_session = result
        
        return f(*args, **kwargs)
    
    return decorated_function

def async_route(f):
    """Decorator for async routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(f(*args, **kwargs))
            return result
        finally:
            loop.close()
    
    return decorated_function

# ==================== AUTHENTICATION ROUTES ====================

@google_drive_bp.route('/auth/start', methods=['POST'])
@async_route
async def start_auth():
    """Start Google Drive authentication flow"""
    
    try:
        data = request.json or {}
        redirect_uri = data.get('redirect_uri')
        
        # Start authentication
        auth_service = await get_google_drive_auth()
        if not auth_service:
            return jsonify({
                "success": False,
                "error": "Google Drive authentication service not available"
            }), 500
        
        auth_result = await auth_service.start_auth_flow(redirect_uri=redirect_uri)
        
        if not auth_result["success"]:
            return jsonify(auth_result), 400
        
        return jsonify(auth_result)
    
    except Exception as e:
        logger.error(f"Failed to start auth flow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/auth/complete', methods=['POST'])
@async_route
async def complete_auth():
    """Complete Google Drive authentication flow"""
    
    try:
        data = request.json or {}
        code = data.get('code')
        state = data.get('state')
        session_id = data.get('session_id')
        
        if not code or not state or not session_id:
            return jsonify({
                "success": False,
                "error": "code, state, and session_id are required"
            }), 400
        
        # Complete authentication
        auth_service = await get_google_drive_auth()
        if not auth_service:
            return jsonify({
                "success": False,
                "error": "Google Drive authentication service not available"
            }), 500
        
        auth_result = await auth_service.complete_auth_flow(code, state, session_id)
        
        if not auth_result["success"]:
            return jsonify(auth_result), 400
        
        return jsonify(auth_result)
    
    except Exception as e:
        logger.error(f"Failed to complete auth flow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/auth/validate', methods=['POST'])
@async_route
async def validate_auth():
    """Validate authentication session"""
    
    try:
        data = request.json or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                "success": False,
                "error": "session_id is required"
            }), 400
        
        # Validate session
        auth_service = await get_google_drive_auth()
        if not auth_service:
            return jsonify({
                "success": False,
                "error": "Google Drive authentication service not available"
            }), 500
        
        validation_result = await auth_service.validate_session(session_id)
        
        if not validation_result.get("valid"):
            return jsonify({
                "success": False,
                "error": validation_result.get("error", "Invalid session")
            }), 401
        
        return jsonify({
            "success": True,
            "valid": True,
            "session": validation_result.get("session"),
            "expires_at": validation_result.get("expires_at")
        })
    
    except Exception as e:
        logger.error(f"Failed to validate auth: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/auth/invalidate', methods=['POST'])
@async_route
async def invalidate_auth():
    """Invalidate authentication session"""
    
    try:
        data = request.json or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                "success": False,
                "error": "session_id is required"
            }), 400
        
        # Invalidate session
        auth_service = await get_google_drive_auth()
        if not auth_service:
            return jsonify({
                "success": False,
                "error": "Google Drive authentication service not available"
            }), 500
        
        invalidate_result = await auth_service.invalidate_session(session_id)
        
        return jsonify(invalidate_result)
    
    except Exception as e:
        logger.error(f"Failed to invalidate auth: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== USER ROUTES ====================

@google_drive_bp.route('/user/info', methods=['GET'])
@require_auth
@async_route
async def get_user_info():
    """Get current user information"""
    
    try:
        session_data = request.google_drive_session
        session = session_data["session"]
        
        return jsonify({
            "success": True,
            "user": {
                "id": session["user_id"],
                "email": session["email"],
                "name": session["name"],
                "metadata": session.get("metadata", {})
            }
        })
    
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/user/tokens', methods=['GET'])
@require_auth
@async_route
async def get_user_tokens():
    """Get user tokens"""
    
    try:
        session_data = request.google_drive_session
        session = session_data["session"]
        
        if not session.get("tokens"):
            return jsonify({
                "success": False,
                "error": "No tokens available"
            }), 404
        
        tokens = session["tokens"]
        
        return jsonify({
            "success": True,
            "tokens": {
                "access_token": tokens["access_token"],
                "token_type": tokens["token_type"],
                "expires_at": tokens["expires_at"],
                "scope": tokens["scope"]
            }
        })
    
    except Exception as e:
        logger.error(f"Failed to get user tokens: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== FILE OPERATIONS ROUTES ====================

@google_drive_bp.route('/files', methods=['GET'])
@require_auth
@async_route
async def list_files():
    """List Google Drive files"""
    
    try:
        # Get query parameters
        query = request.args.get('query')
        page_size = int(request.args.get('page_size', 100))
        page_token = request.args.get('page_token')
        order_by = request.args.get('order_by', 'modifiedTime desc')
        
        # Get user tokens
        session_data = request.google_drive_session
        tokens = session_data["session"]["tokens"]
        
        # Initialize drive service with tokens
        drive_service = await get_google_drive_service()
        if not drive_service:
            return jsonify({
                "success": False,
                "error": "Google Drive service not available"
            }), 500
        
        # Create credentials from tokens
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_app.config['GOOGLE_DRIVE_CLIENT_ID'],
            client_secret=current_app.config['GOOGLE_DRIVE_CLIENT_SECRET'],
            scopes=tokens["scope"]
        )
        
        # Refresh token if needed
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        
        # Initialize service
        await drive_service._initialize_service(credentials)
        
        # List files
        files_result = await drive_service.list_files(
            query=query,
            page_size=min(page_size, 1000),  # Max 1000
            page_token=page_token,
            order_by=order_by
        )
        
        return jsonify(files_result)
    
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/files/<file_id>', methods=['GET'])
@require_auth
@async_route
async def get_file(file_id: str):
    """Get file information"""
    
    try:
        # Get user tokens
        session_data = request.google_drive_session
        tokens = session_data["session"]["tokens"]
        
        # Initialize drive service
        drive_service = await get_google_drive_service()
        if not drive_service:
            return jsonify({
                "success": False,
                "error": "Google Drive service not available"
            }), 500
        
        # Create credentials
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_app.config['GOOGLE_DRIVE_CLIENT_ID'],
            client_secret=current_app.config['GOOGLE_DRIVE_CLIENT_SECRET'],
            scopes=tokens["scope"]
        )
        
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        
        await drive_service._initialize_service(credentials)
        
        # Get file
        file_result = await drive_service.get_file(file_id)
        
        if not file_result["success"]:
            if file_result.get("not_found"):
                return jsonify(file_result), 404
            return jsonify(file_result), 400
        
        return jsonify(file_result)
    
    except Exception as e:
        logger.error(f"Failed to get file: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/files/<file_id>/download', methods=['GET'])
@require_auth
@async_route
async def download_file(file_id: str):
    """Download file from Google Drive"""
    
    try:
        # Get download path
        download_path = request.args.get('path')
        if not download_path:
            return jsonify({
                "success": False,
                "error": "Download path is required"
            }), 400
        
        # Get user tokens
        session_data = request.google_drive_session
        tokens = session_data["session"]["tokens"]
        
        # Initialize drive service
        drive_service = await get_google_drive_service()
        if not drive_service:
            return jsonify({
                "success": False,
                "error": "Google Drive service not available"
            }), 500
        
        # Create credentials
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_app.config['GOOGLE_DRIVE_CLIENT_ID'],
            client_secret=current_app.config['GOOGLE_DRIVE_CLIENT_SECRET'],
            scopes=tokens["scope"]
        )
        
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        
        await drive_service._initialize_service(credentials)
        
        # Download file
        download_result = await drive_service.download_file(file_id, download_path)
        
        if not download_result["success"]:
            return jsonify(download_result), 400
        
        # Send file
        return send_file(
            download_result["file_path"],
            as_attachment=True,
            download_name=download_result["file_name"]
        )
    
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/files/upload', methods=['POST'])
@require_auth
@async_route
async def upload_file():
    """Upload file to Google Drive"""
    
    try:
        # Get file from request
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        # Get upload parameters
        file_name = request.form.get('name', file.filename)
        parent_id = request.form.get('parent_id')
        
        # Save file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Get user tokens
            session_data = request.google_drive_session
            tokens = session_data["session"]["tokens"]
            
            # Initialize drive service
            drive_service = await get_google_drive_service()
            if not drive_service:
                return jsonify({
                    "success": False,
                    "error": "Google Drive service not available"
                }), 500
            
            # Create credentials
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            
            credentials = Credentials(
                token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=current_app.config['GOOGLE_DRIVE_CLIENT_ID'],
                client_secret=current_app.config['GOOGLE_DRIVE_CLIENT_SECRET'],
                scopes=tokens["scope"]
            )
            
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            
            await drive_service._initialize_service(credentials)
            
            # Upload file
            upload_result = await drive_service.upload_file(
                file_path=temp_path,
                file_name=file_name,
                parent_id=parent_id
            )
            
            if not upload_result["success"]:
                return jsonify(upload_result), 400
            
            return jsonify(upload_result)
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/files/<file_id>', methods=['DELETE'])
@require_auth
@async_route
async def delete_file(file_id: str):
    """Delete file from Google Drive"""
    
    try:
        # Get user tokens
        session_data = request.google_drive_session
        tokens = session_data["session"]["tokens"]
        
        # Initialize drive service
        drive_service = await get_google_drive_service()
        if not drive_service:
            return jsonify({
                "success": False,
                "error": "Google Drive service not available"
            }), 500
        
        # Create credentials
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_app.config['GOOGLE_DRIVE_CLIENT_ID'],
            client_secret=current_app.config['GOOGLE_DRIVE_CLIENT_SECRET'],
            scopes=tokens["scope"]
        )
        
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        
        await drive_service._initialize_service(credentials)
        
        # Delete file
        delete_result = await drive_service.delete_file(file_id)
        
        if not delete_result["success"]:
            if delete_result.get("not_found"):
                return jsonify(delete_result), 404
            return jsonify(delete_result), 400
        
        return jsonify(delete_result)
    
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== SEARCH ROUTES ====================

@google_drive_bp.route('/search', methods=['GET'])
@require_auth
@async_route
async def search_files():
    """Search Google Drive files"""
    
    try:
        # Get search parameters
        query = request.args.get('query', '')
        search_type = request.args.get('search_type', 'semantic')
        limit = int(request.args.get('limit', 50))
        min_score = float(request.args.get('min_score', 0.1))
        offset = int(request.args.get('offset', 0))
        
        # Get search options
        options = {
            "limit": limit,
            "offset": offset,
            "search_type": search_type,
            "min_score": min_score,
            "file_types": request.args.getlist('file_types'),
            "mime_types": request.args.getlist('mime_types'),
            "size_min": request.args.get('size_min'),
            "size_max": request.args.get('size_max'),
            "date_from": request.args.get('date_from'),
            "date_to": request.args.get('date_to'),
            "folder_id": request.args.get('folder_id')
        }
        
        # Initialize search provider
        search_provider = await get_google_drive_search_provider()
        if not search_provider:
            return jsonify({
                "success": False,
                "error": "Search provider not available"
            }), 500
        
        # Perform search
        search_result = await search_provider.search(query, options)
        
        return jsonify(search_result)
    
    except Exception as e:
        logger.error(f"Failed to search files: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/search/facets', methods=['GET'])
@require_auth
@async_route
async def get_search_facets():
    """Get search facets"""
    
    try:
        query = request.args.get('query')
        
        # Initialize search provider
        search_provider = await get_google_drive_search_provider()
        if not search_provider:
            return jsonify({
                "success": False,
                "error": "Search provider not available"
            }), 500
        
        # Get facets
        facets_result = await search_provider.get_facets(query)
        
        return jsonify(facets_result)
    
    except Exception as e:
        logger.error(f"Failed to get search facets: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/search/suggestions', methods=['GET'])
@require_auth
@async_route
async def get_search_suggestions():
    """Get search suggestions"""
    
    try:
        query = request.args.get('query', '')
        limit = int(request.args.get('limit', 10))
        
        # Initialize search provider
        search_provider = await get_google_drive_search_provider()
        if not search_provider:
            return jsonify({
                "success": False,
                "error": "Search provider not available"
            }), 500
        
        # Get suggestions
        suggestions_result = await search_provider.get_suggestions(query, limit)
        
        return jsonify(suggestions_result)
    
    except Exception as e:
        logger.error(f"Failed to get search suggestions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== MEMORY/EMBEDDING ROUTES ====================

@google_drive_bp.route('/memory/embeddings/<file_id>', methods=['POST'])
@require_auth
@async_route
async def store_embedding(file_id: str):
    """Store embedding for file"""
    
    try:
        data = request.json or {}
        text = data.get('text')
        metadata = data.get('metadata', {})
        
        if not text:
            return jsonify({
                "success": False,
                "error": "Text content is required"
            }), 400
        
        # Initialize memory service
        memory_service = await get_google_drive_memory_service()
        if not memory_service:
            return jsonify({
                "success": False,
                "error": "Memory service not available"
            }), 500
        
        # Store embedding
        store_result = await memory_service.store_embedding(
            file_id=file_id,
            text=text,
            metadata=metadata
        )
        
        return jsonify(store_result)
    
    except Exception as e:
        logger.error(f"Failed to store embedding: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@google_drive_bp.route('/memory/embeddings/<file_id>', methods=['GET'])
@require_auth
@async_route
async def get_embedding(file_id: str):
    """Get embedding for file"""
    
    try:
        # Initialize memory service
        memory_service = await get_google_drive_memory_service()
        if not memory_service:
            return jsonify({
                "success": False,
                "error": "Memory service not available"
            }), 500
        
        # Get embedding
        embedding_result = await memory_service.get_embedding(file_id)
        
        return jsonify(embedding_result)
    
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== CONTENT EXTRACTION ROUTES ====================

@google_drive_bp.route('/content/extract', methods=['POST'])
@require_auth
@async_route
async def extract_content():
    """Extract content from uploaded file"""
    
    try:
        # Get file from request
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        # Get file metadata
        file_id = request.form.get('file_id')
        if not file_id:
            return jsonify({
                "success": False,
                "error": "File ID is required"
            }), 400
        
        # Save file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Initialize content extractor
            content_extractor = await get_content_extractor()
            if not content_extractor:
                return jsonify({
                    "success": False,
                    "error": "Content extractor not available"
                }), 500
            
            # Extract content
            extracted_content = await content_extractor.extract_content(
                file_id=file_id,
                file_path=temp_path,
                file_name=file.filename
            )
            
            # Return extracted content
            return jsonify({
                "success": True,
                "content": extracted_content.to_dict()
            })
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except Exception as e:
        logger.error(f"Failed to extract content: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== UTILITY ROUTES ====================

@google_drive_bp.route('/health', methods=['GET'])
@async_route
async def health_check():
    """Health check for Google Drive services"""
    
    try:
        health_status = {
            "status": "healthy",
            "services": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check authentication service
        try:
            auth_service = await get_google_drive_auth()
            if auth_service:
                auth_health = await auth_service.health_check()
                health_status["services"]["authentication"] = auth_health
            else:
                health_status["services"]["authentication"] = {"status": "unavailable"}
        except Exception as e:
            health_status["services"]["authentication"] = {"status": "error", "error": str(e)}
        
        # Check search provider
        try:
            search_provider = await get_google_drive_search_provider()
            if search_provider:
                search_health = await search_provider.get_provider_info()
                health_status["services"]["search"] = {"status": search_health["status"]}
            else:
                health_status["services"]["search"] = {"status": "unavailable"}
        except Exception as e:
            health_status["services"]["search"] = {"status": "error", "error": str(e)}
        
        # Check memory service
        try:
            memory_service = await get_google_drive_memory_service()
            if memory_service:
                memory_health = await memory_service.health_check()
                health_status["services"]["memory"] = memory_health
            else:
                health_status["services"]["memory"] = {"status": "unavailable"}
        except Exception as e:
            health_status["services"]["memory"] = {"status": "error", "error": str(e)}
        
        # Check content extractor
        try:
            content_extractor = await get_content_extractor()
            if content_extractor:
                health_status["services"]["content_extractor"] = {"status": "available"}
            else:
                health_status["services"]["content_extractor"] = {"status": "unavailable"}
        except Exception as e:
            health_status["services"]["content_extractor"] = {"status": "error", "error": str(e)}
        
        # Check overall status
        service_statuses = [service.get("status", "unavailable") for service in health_status["services"].values()]
        
        if "error" in service_statuses:
            health_status["status"] = "unhealthy"
        elif "unavailable" in service_statuses:
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "healthy"
        
        return jsonify(health_status)
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@google_drive_bp.route('/info', methods=['GET'])
def get_info():
    """Get Google Drive integration information"""
    
    try:
        info = {
            "name": "Google Drive Integration",
            "version": "1.0.0",
            "description": "Advanced Google Drive integration with semantic search and automation",
            "features": [
                "OAuth 2.0 Authentication",
                "File Operations (CRUD)",
                "Semantic Search with LanceDB",
                "Content Extraction and Processing",
                "Real-time Synchronization",
                "Workflow Automation",
                "Search UI Integration"
            ],
            "supported_formats": [
                "PDF", "DOC", "DOCX", "TXT", "RTF", "ODT",
                "PPT", "PPTX", "XLS", "XLSX", "CSV",
                "JPG", "JPEG", "PNG", "GIF", "BMP", "SVG",
                "MP4", "AVI", "MOV", "WMV", "FLV", "WEBM",
                "MP3", "WAV", "FLAC", "AAC", "OGG",
                "ZIP", "RAR", "7Z", "TAR", "GZ"
            ],
            "endpoints": {
                "authentication": "/api/google-drive/auth/*",
                "files": "/api/google-drive/files/*",
                "search": "/api/google-drive/search/*",
                "memory": "/api/google-drive/memory/*",
                "content": "/api/google-drive/content/*",
                "health": "/api/google-drive/health",
                "info": "/api/google-drive/info"
            },
            "available": GOOGLE_DRIVE_AVAILABLE,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify(info)
    
    except Exception as e:
        logger.error(f"Failed to get info: {e}")
        return jsonify({
            "error": str(e),
            "available": GOOGLE_DRIVE_AVAILABLE,
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Register routes with app
def register_google_drive_routes(app):
    """Register Google Drive routes with Flask app"""
    
    if GOOGLE_DRIVE_AVAILABLE:
        app.register_blueprint(google_drive_bp)
        logger.info("Google Drive routes registered")
    else:
        logger.warning("Google Drive routes not registered - services not available")

# Export blueprint and registration function
__all__ = [
    'google_drive_bp',
    'register_google_drive_routes'
]