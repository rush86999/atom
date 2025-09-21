import logging
from flask import Blueprint, request, jsonify, current_app
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

box_bp = Blueprint('box_bp', __name__)

# Mock implementations
class MockOAuth2:
    """Mock OAuth2 class for Box authentication"""
    def __init__(self, access_token: str = "mock_access_token"):
        self.access_token = access_token

class MockBoxService:
    """Mock Box Service implementation"""
    def __init__(self, oauth: MockOAuth2):
        self.oauth = oauth
        logger.warning("Using mock Box service - real Box integration disabled")

    def list_files(
        self,
        folder_id: str = '0',
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Mock list files implementation"""
        # Return mock file data
        files = [
            {
                "id": "file_001",
                "name": "Project Documentation.pdf",
                "size": 2048,
                "modified_at": "2025-09-15T10:30:00Z",
                "type": "file"
            },
            {
                "id": "file_002",
                "name": "Financial Report.xlsx",
                "size": 4096,
                "modified_at": "2025-09-14T14:45:00Z",
                "type": "file"
            },
            {
                "id": "file_003",
                "name": "Meeting Notes.docx",
                "size": 1024,
                "modified_at": "2025-09-13T11:30:00Z",
                "type": "file"
            }
        ]

        # Filter by query if provided
        if query:
            files = [f for f in files if query.lower() in f["name"].lower()]

        # Apply pagination
        start_idx = int(page_token or 0)
        end_idx = start_idx + page_size
        paginated_files = files[start_idx:end_idx]

        return {
            "entries": paginated_files,
            "total_count": len(files),
            "limit": page_size,
            "offset": start_idx,
            "next_page_token": str(end_idx) if end_idx < len(files) else None
        }

    def get_service_status(self) -> Dict[str, Any]:
        """Get mock service status"""
        return {
            "status": "mock_mode",
            "message": "Box service running in mock mode for development",
            "available": False,
            "mock_data": True
        }

# Create mock service instance
mock_service = MockBoxService(MockOAuth2())

@box_bp.route('/files', methods=['GET'])
def list_files():
    """List files from Box"""
    try:
        folder_id = request.args.get('folder_id', '0')
        query = request.args.get('query')
        page_size = int(request.args.get('page_size', 100))
        page_token = request.args.get('page_token')

        result = mock_service.list_files(
            folder_id=folder_id,
            query=query,
            page_size=page_size,
            page_token=page_token
        )

        return jsonify({
            "success": True,
            "data": result,
            "is_mock": True
        })

    except Exception as e:
        logger.error(f"Error listing Box files: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@box_bp.route('/status', methods=['GET'])
def get_status():
    """Get Box service status"""
    try:
        status = mock_service.get_service_status()
        return jsonify({
            "success": True,
            "status": status,
            "is_mock": True
        })

    except Exception as e:
        logger.error(f"Error getting Box status: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@box_bp.route('/health', methods=['GET'])
def health_check():
    """Box service health check"""
    return jsonify({
        "status": "healthy",
        "service": "box",
        "mode": "mock",
        "available": True
    })

# Mock OAuth endpoints for development
@box_bp.route('/auth/url', methods=['GET'])
def get_auth_url():
    """Get mock OAuth URL"""
    return jsonify({
        "auth_url": "https://mock-box.com/oauth/authorize?client_id=mock_client_id&response_type=code",
        "is_mock": True
    })

@box_bp.route('/auth/callback', methods=['GET'])
def oauth_callback():
    """Mock OAuth callback"""
    return jsonify({
        "success": True,
        "access_token": "mock_access_token_123",
        "refresh_token": "mock_refresh_token_456",
        "expires_in": 3600,
        "is_mock": True
    })

logger.info("Box mock handler initialized successfully")
