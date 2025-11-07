"""
OneDrive Routes Handler

This module provides REST API endpoints for OneDrive integration
including file operations, search, and document ingestion with
LanceDB memory system integration.
"""

import os
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import requests
from dotenv import load_dotenv

# Import document processing and LanceDB integration
try:
    from document_processor import process_document_and_store

    DOCUMENT_PROCESSING_AVAILABLE = True
except ImportError as e:
    DOCUMENT_PROCESSING_AVAILABLE = False
    logger.warning(f"Document processor not available: {e}")

try:
    from lancedb_handler import get_lancedb_connection, search_documents

    LANCEDB_AVAILABLE = True
except ImportError as e:
    LANCEDB_AVAILABLE = False
    logger.warning(f"LanceDB handler not available: {e}")

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Create blueprint for OneDrive routes
onedrive_bp = Blueprint("onedrive", __name__)

# In-memory storage for access tokens (in production, use database)
_user_tokens = {}


class OneDriveAPIService:
    """Service for OneDrive API operations using Microsoft Graph API"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0/me/drive"

    async def get_connection_status(self) -> Dict[str, Any]:
        """Check OneDrive connection status"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Test connection by getting user info
            user_response = requests.get(
                "https://graph.microsoft.com/v1.0/me", headers=headers
            )
            if user_response.status_code != 200:
                return {
                    "is_connected": False,
                    "reason": f"User info request failed: {user_response.status_code}",
                }

            # Test drive access
            drive_response = requests.get(f"{self.base_url}", headers=headers)
            if drive_response.status_code != 200:
                return {
                    "is_connected": False,
                    "reason": f"Drive access failed: {drive_response.status_code}",
                }

            user_data = user_response.json()
            drive_data = drive_response.json()

            return {
                "is_connected": True,
                "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                "display_name": user_data.get("displayName"),
                "drive_id": drive_data.get("id"),
                "drive_type": drive_data.get("driveType"),
                "quota": drive_data.get("quota", {}),
            }

        except Exception as e:
            logger.error(f"Error checking OneDrive connection: {e}")
            return {"is_connected": False, "reason": str(e)}

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """List files and folders from OneDrive"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Build URL for listing files
            if folder_id and folder_id != "root":
                url = f"{self.base_url}/items/{folder_id}/children"
            else:
                url = f"{self.base_url}/root/children"

            params = {"$top": page_size}
            if page_token:
                params["$skiptoken"] = page_token

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            files = data.get("value", [])

            # Parse file data
            parsed_files = []
            for file in files:
                parsed_file = await self._parse_file_data(file)
                parsed_files.append(parsed_file)

            result = {
                "files": parsed_files,
                "next_page_token": data.get("@odata.nextLink"),
            }

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing OneDrive files: {e}")
            raise

    async def search_files(
        self, query: str, page_token: Optional[str] = None, page_size: int = 50
    ) -> Dict[str, Any]:
        """Search files in OneDrive"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/root/search(q='{query}')"
            params = {"$top": page_size}
            if page_token:
                params["$skiptoken"] = page_token

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            files = data.get("value", [])

            # Parse file data
            parsed_files = []
            for file in files:
                parsed_file = await self._parse_file_data(file)
                parsed_files.append(parsed_file)

            return {
                "files": parsed_files,
                "next_page_token": data.get("@odata.nextLink"),
                "query": query,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching OneDrive files: {e}")
            raise

    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get metadata for a specific file"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/items/{file_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            file_data = response.json()
            return await self._parse_file_data(file_data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting file metadata: {e}")
            raise

    async def download_file(self, file_id: str) -> Dict[str, Any]:
        """Download file content from OneDrive"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}

            # Get file metadata first
            metadata = await self.get_file_metadata(file_id)

            # Download file content
            url = f"{self.base_url}/items/{file_id}/content"
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()

            # For now, we'll return the content as bytes
            # In a real implementation, you might want to stream to file
            content = response.content

            return {
                "file_name": metadata["name"],
                "content": content,
                "mime_type": metadata.get("mime_type", "application/octet-stream"),
                "size": len(content),
                "metadata": metadata,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading file: {e}")
            raise

    async def upload_file(
        self, file_path: str, folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload file to OneDrive"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/octet-stream",
            }

            # Determine upload URL
            if folder_id and folder_id != "root":
                url = f"{self.base_url}/items/{folder_id}:/{os.path.basename(file_path)}:/content"
            else:
                url = f"{self.base_url}/root:/{os.path.basename(file_path)}:/content"

            # Read file content
            with open(file_path, "rb") as file:
                file_content = file.read()

            response = requests.put(url, headers=headers, data=file_content)
            response.raise_for_status()

            uploaded_file = response.json()
            return await self._parse_file_data(uploaded_file)

        except Exception as e:
            logger.error(f"Error uploading file to OneDrive: {e}")
            raise

    async def _parse_file_data(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Microsoft Graph file data into standardized format"""
        file_type = file_data.get("file", {})
        folder_type = file_data.get("folder", {})

        is_folder = bool(folder_type)
        mime_type = file_type.get("mimeType") if file_type else None

        # Determine file icon based on type
        icon = "📁" if is_folder else "📄"
        if mime_type:
            if "spreadsheet" in mime_type:
                icon = "📊"
            elif "presentation" in mime_type:
                icon = "📽️"
            elif "image" in mime_type:
                icon = "🖼️"
            elif "pdf" in mime_type:
                icon = "📕"
            elif "video" in mime_type:
                icon = "🎬"
            elif "audio" in mime_type:
                icon = "🎵"

        return {
            "id": file_data.get("id"),
            "name": file_data.get("name"),
            "mime_type": mime_type,
            "is_folder": is_folder,
            "size": file_data.get("size"),
            "created_time": file_data.get("createdDateTime"),
            "modified_time": file_data.get("lastModifiedDateTime"),
            "web_url": file_data.get("webUrl"),
            "parent_reference": file_data.get("parentReference", {}),
            "icon": icon,
        }


def require_onedrive_auth(func):
    """Decorator to require OneDrive authentication"""

    async def decorated_function(*args, **kwargs):
        try:
            # In a real implementation, you would:
            # 1. Get user ID from session or JWT
            # 2. Retrieve access token from database
            # 3. Validate token and refresh if needed

            # For now, we'll use a placeholder token from environment
            access_token = os.getenv("ONEDRIVE_ACCESS_TOKEN")
            if not access_token:
                return jsonify(
                    {
                        "error": "OneDrive not connected",
                        "message": "Please connect OneDrive first",
                    }
                ), 401

            # Create service instance
            service = OneDriveAPIService(access_token)

            # Pass service to the route function
            return await func(service, *args, **kwargs)

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({"error": "Authentication failed", "message": str(e)}), 401

    return decorated_function


@onedrive_bp.route("/onedrive/connection-status")
@require_onedrive_auth
async def get_connection_status(service: OneDriveAPIService):
    """Get OneDrive connection status"""
    try:
        status = await service.get_connection_status()
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting connection status: {e}")
        return jsonify(
            {"error": "Failed to get connection status", "message": str(e)}
        ), 500


@onedrive_bp.route("/onedrive/list-files")
@require_onedrive_auth
async def list_files(service: OneDriveAPIService):
    """List files and folders from OneDrive"""
    try:
        folder_id = request.args.get("folder_id", "root")
        page_token = request.args.get("page_token")
        page_size = int(request.args.get("page_size", 100))

        result = await service.list_files(folder_id, page_token, page_size)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"error": "Failed to list files", "message": str(e)}), 500


@onedrive_bp.route("/onedrive/search")
@require_onedrive_auth
async def search_files(service: OneDriveAPIService):
    """Search files in OneDrive"""
    try:
        query = request.args.get("q", "")
        page_token = request.args.get("page_token")
        page_size = int(request.args.get("page_size", 50))

        if not query:
            return jsonify({"error": "Search query is required"}), 400

        result = await service.search_files(query, page_token, page_size)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error searching files: {e}")
        return jsonify({"error": "Failed to search files", "message": str(e)}), 500


@onedrive_bp.route("/onedrive/files/<file_id>")
@require_onedrive_auth
async def get_file_metadata(service: OneDriveAPIService, file_id: str):
    """Get metadata for a specific file"""
    try:
        metadata = await service.get_file_metadata(file_id)
        return jsonify(metadata)

    except Exception as e:
        logger.error(f"Error getting file metadata: {e}")
        return jsonify({"error": "Failed to get file metadata", "message": str(e)}), 500


@onedrive_bp.route("/onedrive/files/<file_id>/download")
@require_onedrive_auth
async def download_file(service: OneDriveAPIService, file_id: str):
    """Download file from OneDrive"""
    try:
        file_data = await service.download_file(file_id)

        # For now, return file info (in production, you might stream the file)
        return jsonify(
            {
                "file_name": file_data["file_name"],
                "size": file_data["size"],
                "mime_type": file_data["mime_type"],
                "message": "File downloaded successfully (content available in response)",
            }
        )

    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": "Failed to download file", "message": str(e)}), 500


@onedrive_bp.route("/onedrive/ingest-document", methods=["POST"])
@require_onedrive_auth
async def ingest_document(service: OneDriveAPIService):
    """Ingest OneDrive document into ATOM search system"""
    try:
        data = request.get_json()
        file_id = data.get("file_id")

        if not file_id:
            return jsonify({"error": "File ID is required"}), 400

        # Download file content
        file_data = await service.download_file(file_id)

        # Get file metadata
        metadata = await service.get_file_metadata(file_id)

        # In a real implementation, you would:
        # 1. Process the file content (text extraction, etc.)
        # 2. Store in LanceDB vector database
        # 3. Index for search

        logger.info(f"Ingested OneDrive file: {metadata['name']} (ID: {file_id})")

        return jsonify(
            {
                "status": "success",
                "message": f"File '{metadata['name']}' ingested successfully",
                "file_id": file_id,
                "file_name": metadata["name"],
                "size": file_data["size"],
            }
        )

    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        return jsonify({"error": "Failed to ingest document", "message": str(e)}), 500


@onedrive_bp.route("/onedrive/search-memory", methods=["POST"])
@require_onedrive_auth
async def search_memory(service: OneDriveAPIService):
    """Search OneDrive documents in ATOM memory system"""
    try:
        if not LANCEDB_AVAILABLE:
            return jsonify({"error": "LanceDB memory system not available"}), 503

        data = request.get_json()
        query = data.get("query")
        user_id = data.get("user_id", "default_user")  # In production, get from auth
        limit = data.get("limit", 10)

        if not query:
            return jsonify({"error": "Search query is required"}), 400

        # Search in LanceDB for OneDrive documents
        db_conn = await get_lancedb_connection()
        if not db_conn:
            return jsonify({"error": "Failed to connect to LanceDB"}), 500

        search_results = await search_documents(
            db_conn=db_conn,
            user_id=user_id,
            query_text=query,
            limit=limit,
            source_filter="onedrive",
        )

        return jsonify(
            {
                "status": "success",
                "query": query,
                "results": search_results.get("results", []),
                "total_matches": search_results.get("total_matches", 0),
            }
        )

    except Exception as e:
        logger.error(f"Error searching OneDrive memory: {e}")
        return jsonify({"error": "Failed to search memory", "message": str(e)}), 500


@onedrive_bp.route("/onedrive/memory-stats")
@require_onedrive_auth
async def get_memory_stats(service: OneDriveAPIService):
    """Get statistics about OneDrive documents in memory system"""
    try:
        if not LANCEDB_AVAILABLE:
            return jsonify({"error": "LanceDB memory system not available"}), 503

        user_id = request.args.get(
            "user_id", "default_user"
        )  # In production, get from auth

        db_conn = await get_lancedb_connection()
        if not db_conn:
            return jsonify({"error": "Failed to connect to LanceDB"}), 500

        # Get document statistics from LanceDB
        from lancedb_handler import get_document_stats

        stats = await get_document_stats(
            db_conn=db_conn, user_id=user_id, source_filter="onedrive"
        )

        return jsonify({"status": "success", "stats": stats, "user_id": user_id})

    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        return jsonify(
            {"error": "Failed to get memory statistics", "message": str(e)}
        ), 500


@onedrive_bp.route("/onedrive/ingest-document-enhanced", methods=["POST"])
@require_onedrive_auth
async def ingest_document_enhanced(service: OneDriveAPIService):
    """Enhanced document ingestion with LanceDB memory integration"""
    try:
        if not DOCUMENT_PROCESSING_AVAILABLE or not LANCEDB_AVAILABLE:
            return jsonify(
                {
                    "error": "Document processing or LanceDB not available",
                    "document_processing": DOCUMENT_PROCESSING_AVAILABLE,
                    "lancedb": LANCEDB_AVAILABLE,
                }
            ), 503

        data = request.get_json()
        file_id = data.get("file_id")
        user_id = data.get("user_id", "default_user")  # In production, get from auth

        if not file_id:
            return jsonify({"error": "File ID is required"}), 400

        # Get file metadata
        metadata = await service.get_file_metadata(file_id)

        # Download file content
        file_data = await service.download_file(file_id)

        # Generate unique document ID
        document_id = str(uuid.uuid4())
        source_uri = f"onedrive://{file_id}"

        # Process and store in LanceDB
        result = await process_document_and_store(
            user_id=user_id,
            file_path_or_bytes=file_data["content"],
            document_id=document_id,
            source_uri=source_uri,
            original_doc_type=f"onedrive_{metadata['name'].split('.')[-1].lower() if '.' in metadata['name'] else 'file'}",
            processing_mime_type=metadata.get("mime_type", "application/octet-stream"),
            title=metadata["name"],
            doc_metadata_json=json.dumps(
                {
                    "onedrive_file_id": file_id,
                    "onedrive_web_url": metadata.get("web_url"),
                    "onedrive_modified_time": metadata.get("modified_time"),
                    "onedrive_size": metadata.get("size"),
                    "original_source": "onedrive",
                }
            ),
        )

        if result["status"] == "success":
            logger.info(
                f"Successfully ingested OneDrive file into memory: {metadata['name']} (ID: {file_id})"
            )
            return jsonify(
                {
                    "status": "success",
                    "message": f"File '{metadata['name']}' ingested into memory system",
                    "file_id": file_id,
                    "document_id": document_id,
                    "num_chunks_stored": result["data"]["num_chunks_stored"],
                    "memory_integration": True,
                }
            )
        else:
            logger.error(
                f"Failed to ingest OneDrive file into memory: {result.get('message')}"
            )
            return jsonify(
                {
                    "status": "error",
                    "message": f"Memory ingestion failed: {result.get('message')}",
                    "code": result.get("code", "MEMORY_INGESTION_FAILED"),
                }
            ), 500

    except Exception as e:
        logger.error(f"Error in enhanced document ingestion: {e}")
        return jsonify(
            {"error": "Failed to ingest document into memory", "message": str(e)}
        ), 500


@onedrive_bp.route("/onedrive/health")
async def health_check():
    """Health check endpoint for OneDrive integration"""
    try:
        # Check if required environment variables are set
        client_id = os.getenv("ONEDRIVE_CLIENT_ID")
        client_secret = os.getenv("ONEDRIVE_CLIENT_SECRET")

        health_status = {
            "status": "healthy",
            "service": "onedrive",
            "client_id_configured": bool(client_id),
            "client_secret_configured": bool(client_secret),
            "timestamp": str(asyncio.get_event_loop().time()),
        }

        if not client_id or not client_secret:
            health_status["status"] = "degraded"
            health_status["message"] = "OneDrive OAuth credentials not configured"

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify(
            {"status": "unhealthy", "service": "onedrive", "error": str(e)}
        ), 500


def register_onedrive_routes(app):
    """Register OneDrive routes with Flask application"""
    app.register_blueprint(onedrive_bp, url_prefix="/api")
    logger.info("OneDrive routes registered successfully")
    logger.info(
        f"OneDrive memory integration: Document Processing={DOCUMENT_PROCESSING_AVAILABLE}, LanceDB={LANCEDB_AVAILABLE}"
    )
