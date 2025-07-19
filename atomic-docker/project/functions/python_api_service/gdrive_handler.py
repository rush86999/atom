import logging
from flask import Blueprint, request, jsonify, current_app

from . import gdrive_service
from . import db_oauth_gdrive
from . import document_processor

logger = logging.getLogger(__name__)

gdrive_bp = Blueprint('gdrive_bp', __name__)

@gdrive_bp.route('/api/gdrive/search', methods=['POST'])
async def search_gdrive_route():
    """
    Searches Google Drive for the given query.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    query = data.get('query')
    if not user_id or not query:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and query are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
        if not creds:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Google Drive client. Please reconnect."}}), 401

        search_results = await gdrive_service.search_files(creds, query)
        if search_results is not None:
            return jsonify({"ok": True, "data": search_results})
        else:
            return jsonify({"ok": False, "error": {"code": "API_ERROR", "message": "Failed to search files from Google Drive API."}}), 500

    except Exception as e:
        logger.error(f"Error searching Google Drive files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "SEARCH_FILES_FAILED", "message": str(e)}}), 500

@gdrive_bp.route('/api/gdrive/connection-status', methods=['GET'])
async def get_status():
    """
    Checks if a user has a valid Google Drive connection.
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        is_connected = await gdrive_service.is_user_connected(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": {"isConnected": is_connected}})
    except Exception as e:
        logger.error(f"Error checking Google Drive status for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "STATUS_CHECK_FAILED", "message": str(e)}}), 500

@gdrive_bp.route('/api/auth/gdrive/disconnect', methods=['POST'])
async def disconnect():
    """
    Disconnects a user's Google Drive account.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        await db_oauth_gdrive.delete_token(db_conn_pool, user_id)
        return jsonify({"ok": True, "message": "Google Drive account disconnected successfully."})
    except Exception as e:
        logger.error(f"Error disconnecting Google Drive for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "DISCONNECT_UNHANDLED_ERROR", "message": str(e)}}), 500

@gdrive_bp.route('/api/gdrive/list-files', methods=['POST'])
async def list_files():
    """
    Lists files and folders in a user's Google Drive.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    folder_id = data.get('folder_id')
    query = data.get('query')
    page_size = data.get('page_size')
    page_token = data.get('page_token')

    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
        if not creds:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Google Drive client. Please reconnect."}}), 401

        list_results = await gdrive_service.list_files(creds, folder_id=folder_id, query=query, page_size=page_size, page_token=page_token)

        if list_results is not None:
            return jsonify({"ok": True, "data": list_results})
        else:
            return jsonify({"ok": False, "error": {"code": "API_ERROR", "message": "Failed to list files from Google Drive API."}}), 500

    except Exception as e:
        logger.error(f"Error listing Google Drive files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_FILES_FAILED", "message": str(e)}}), 500

@gdrive_bp.route('/api/gdrive/get-file-metadata', methods=['POST'])
async def get_file_metadata_route():
    data = request.get_json()
    user_id = data.get('user_id')
    file_id = data.get('file_id')
    fields = data.get('fields')

    if not user_id or not file_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and file_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
        if not creds:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Google Drive client. Please reconnect."}}), 401

        metadata = await gdrive_service.get_file_metadata(creds, file_id, fields)
        if metadata:
            return jsonify({"ok": True, "data": metadata})
        else:
            return jsonify({"ok": False, "error": {"code": "METADATA_FETCH_FAILED", "message": "Failed to fetch file metadata."}}), 404
    except Exception as e:
        logger.error(f"Error getting file metadata for user {user_id}, file {file_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "METADATA_UNHANDLED_ERROR", "message": str(e)}}), 500

@gdrive_bp.route('/api/ingest-gdrive-document', methods=['POST'])
async def ingest_gdrive_document_route():
    data = request.get_json()
    user_id = data.get('user_id')
    gdrive_file_id = data.get('gdrive_file_id')
    original_file_metadata = data.get('original_file_metadata')

    if not all([user_id, gdrive_file_id, original_file_metadata]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, gdrive_file_id, and original_file_metadata are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        creds = await gdrive_service.get_gdrive_credentials(user_id, db_conn_pool)
        if not creds:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Google Drive client."}}), 401

        file_content, downloaded_metadata = await gdrive_service.download_file(creds, gdrive_file_id)
        if not file_content:
            return jsonify({"ok": False, "error": {"code": "DOWNLOAD_FAILED", "message": "Failed to download file from Google Drive."}}), 500

        import uuid
        document_id = str(uuid.uuid4())
        source_uri = f"gdrive://{gdrive_file_id}"

        result = await document_processor.process_document_and_store(
            user_id=user_id,
            file_path_or_bytes=file_content,
            document_id=document_id,
            source_uri=source_uri,
            original_doc_type=f"gdrive_{original_file_metadata.get('name', 'file').split('.')[-1].lower()}",
            processing_mime_type=downloaded_metadata.get('mimeType'),
            title=original_file_metadata.get('name')
        )

        if result.get("status") in ["success", "warning"]:
            return jsonify({"ok": True, "data": result.get("data"), "message": result.get("message")}), 200
        else:
            return jsonify({"ok": False, "error": {"code": result.get("code", "INGESTION_FAILED"), "message": result.get("message")}}), 500

    except Exception as e:
        logger.error(f"Error ingesting Google Drive file for user {user_id}, file {gdrive_file_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "INGESTION_UNHANDLED_ERROR", "message": str(e)}}), 500
