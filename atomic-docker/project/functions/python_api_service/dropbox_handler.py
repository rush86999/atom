import logging
from flask import Blueprint, request, jsonify, current_app

# Internal imports
try:
    from . import db_oauth_dropbox
    from . import dropbox_service
    from ingestion_pipeline import document_processor # Import the document processor
except ImportError:
    import db_oauth_dropbox
    import dropbox_service
    from ingestion_pipeline import document_processor

logger = logging.getLogger(__name__)
dropbox_bp = Blueprint('dropbox_bp', __name__)

@dropbox_bp.route('/api/dropbox/status', methods=['GET'])
async def get_status():
    """
    Checks the Dropbox connection status for a given user.
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        tokens = await db_oauth_dropbox.get_tokens(db_conn_pool, user_id)
        if not tokens:
            return jsonify({"ok": True, "data": {"isConnected": False, "reason": "No token found."}})

        # To be fully sure, try to get an authenticated client and make a test call
        client = await dropbox_service.get_dropbox_client(user_id, db_conn_pool)
        if not client:
             # get_dropbox_client would have logged the reason (e.g., expired refresh token)
            return jsonify({"ok": True, "data": {"isConnected": False, "reason": "Token validation failed."}})

        account_info = await dropbox_service.get_current_account(client)
        if account_info:
            return jsonify({"ok": True, "data": {"isConnected": True, "email": account_info.get("email")}})
        else:
            # This case can happen if the token is valid but the API call fails for other reasons
            return jsonify({"ok": True, "data": {"isConnected": False, "reason": "Failed to verify account with token."}})

    except Exception as e:
        logger.error(f"Error checking Dropbox status for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "STATUS_CHECK_FAILED", "message": str(e)}}), 500


@dropbox_bp.route('/api/dropbox/disconnect', methods=['POST'])
async def disconnect():
    """
    Disconnects a user's Dropbox account by deleting their tokens.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        await db_oauth_dropbox.delete_tokens(db_conn_pool, user_id)
        return jsonify({"ok": True, "data": {"message": "Dropbox connection successfully removed."}})
    except Exception as e:
        logger.error(f"Error disconnecting Dropbox for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "DISCONNECT_FAILED", "message": str(e)}}), 500


@dropbox_bp.route('/api/dropbox/list-files', methods=['POST'])
async def list_files():
    """
    Lists files and folders in a user's Dropbox at a given path.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    path = data.get('path', '') # Default to root folder
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        client = await dropbox_service.get_dropbox_client(user_id, db_conn_pool)
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Dropbox client. Please reconnect."}}), 401

        file_list = await dropbox_service.list_folder(client, path)
        if file_list is not None:
            return jsonify({"ok": True, "data": file_list})
        else:
            return jsonify({"ok": False, "error": {"code": "API_ERROR", "message": "Failed to list files from Dropbox API."}}), 500

    except Exception as e:
        logger.error(f"Error listing Dropbox files for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "LIST_FILES_FAILED", "message": str(e)}}), 500


@dropbox_bp.route('/api/dropbox/ingest-file', methods=['POST'])
async def ingest_file():
    """
    Triggers the ingestion of a specific Dropbox file.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    file_path = data.get('file_path') # The path_lower from Dropbox API

    if not user_id or not file_path:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and file_path are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        client = await dropbox_service.get_dropbox_client(user_id, db_conn_pool)
        if not client:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Dropbox client."}}), 401

        download_result = await dropbox_service.download_file(client, file_path)
        if not download_result:
            return jsonify({"ok": False, "error": {"code": "DOWNLOAD_FAILED", "message": f"Failed to download file from Dropbox path: {file_path}"}}), 500

        metadata, file_bytes = download_result

        # Determine MIME type from filename, similar to document_handler
        _, file_extension = os.path.splitext(metadata.name)
        mime_type = "application/octet-stream" # Default
        if file_extension.lower() == ".pdf": mime_type = "application/pdf"
        elif file_extension.lower() == ".docx": mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif file_extension.lower() == ".txt": mime_type = "text/plain"
        elif file_extension.lower() in [".html", ".htm"]: mime_type = "text/html"

        import uuid
        document_id = str(uuid.uuid4())
        source_uri = f"dropbox://{metadata.path_display}"

        logger.info(f"Submitting Dropbox file to document processor. Doc ID: {document_id}, Path: {file_path}")

        # Call the document processor with the file bytes
        result = await document_processor.process_document_and_store(
            user_id=user_id,
            file_path_or_bytes=file_bytes,
            document_id=document_id,
            source_uri=source_uri,
            original_doc_type=f"dropbox_{metadata.name.split('.')[-1].lower()}",
            processing_mime_type=mime_type,
            title=metadata.name
        )

        if result.get("status") in ["success", "warning"]:
            return jsonify({"ok": True, "data": result.get("data"), "message": result.get("message")}), 200
        else:
            return jsonify({"ok": False, "error": {"code": result.get("code", "INGESTION_FAILED"), "message": result.get("message")}}), 500

    except Exception as e:
        logger.error(f"Error ingesting Dropbox file for user {user_id}, path {file_path}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "INGESTION_UNHANDLED_ERROR", "message": str(e)}}), 500
