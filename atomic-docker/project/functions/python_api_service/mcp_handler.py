from flask import Blueprint, request, jsonify
from .mcp_service import list_mcp_files, get_mcp_file_metadata, download_mcp_file
from .auth_handler import get_mcp_credentials
import logging

logger = logging.getLogger(__name__)

mcp_bp = Blueprint('mcp_bp', __name__)

@mcp_bp.route('/mcp/files', methods=['GET'])
def list_files_route():
    user_id = request.headers.get('X-Hasura-User-Id')
    if not user_id:
        return jsonify({"status": "error", "message": "User ID is required"}), 401

    creds = get_mcp_credentials(user_id)
    if not creds:
        return jsonify({"status": "error", "message": "MCP credentials not found or expired"}), 401

    folder_id = request.args.get('folder_id')
    query = request.args.get('query')
    page_size = request.args.get('page_size', type=int)
    page_token = request.args.get('page_token')

    result = list_mcp_files(creds, folder_id, query, page_size, page_token)
    return jsonify(result)

@mcp_bp.route('/mcp/files/<file_id>', methods=['GET'])
def get_file_metadata_route(file_id):
    user_id = request.headers.get('X-Hasura-User-Id')
    if not user_id:
        return jsonify({"status": "error", "message": "User ID is required"}), 401

    creds = get_mcp_credentials(user_id)
    if not creds:
        return jsonify({"status": "error", "message": "MCP credentials not found or expired"}), 401

    result = get_mcp_file_metadata(creds, file_id)
    return jsonify(result)

@mcp_bp.route('/mcp/files/<file_id>/download', methods=['GET'])
def download_file_route(file_id):
    user_id = request.headers.get('X-Hasura-User-Id')
    if not user_id:
        return jsonify({"status": "error", "message": "User ID is required"}), 401

    creds = get_mcp_credentials(user_id)
    if not creds:
        return jsonify({"status": "error", "message": "MCP credentials not found or expired"}), 401

    target_mime_type = request.args.get('target_mime_type')
    result = download_mcp_file(creds, file_id, target_mime_type)
    return jsonify(result)
