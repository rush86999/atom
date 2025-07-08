import os
import sys
import tempfile
import uuid
import logging
import shutil # For robust temp directory removal
from flask import Blueprint, request, jsonify

# Adjust path for imports
PYTHON_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PYTHON_API_DIR not in sys.path:
    sys.path.append(PYTHON_API_DIR)
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)

try:
    from . import gdrive_service
    from .auth_handler import _get_valid_gdrive_access_token # For internal token fetching
    from .db_oauth_gdrive import get_gdrive_oauth_details # For connection status
    from .auth_handler import get_db_connection_pool # To pass to get_gdrive_oauth_details

    # Changed import from process_pdf_and_store to process_document_and_store
    from ingestion_pipeline import document_processor
    INGESTION_SERVICES_AVAILABLE = True
    if not hasattr(document_processor, 'process_document_and_store'):
        logging.getLogger(__name__).error("CRITICAL: document_processor.process_document_and_store not found!")
        INGESTION_SERVICES_AVAILABLE = False
except ImportError as e:
    # Log detailed error for better debugging in case of import issues
    err_msg = f"Error importing dependencies for gdrive_handler: {e}. GDrive functionality might be impaired."
    if 'gdrive_service' not in locals(): err_msg += " (gdrive_service failed to import)"
    if '_get_valid_gdrive_access_token' not in locals(): err_msg += " (_get_valid_gdrive_access_token from auth_handler failed)"
    if 'get_gdrive_oauth_details' not in locals(): err_msg += " (get_gdrive_oauth_details from db_oauth_gdrive failed)"
    if 'document_processor' not in locals(): err_msg += " (document_processor from ingestion_pipeline failed)"
    print(err_msg, file=sys.stderr)
    logging.getLogger(__name__).critical(err_msg, exc_info=True)

    INGESTION_SERVICES_AVAILABLE = False
    # Define fallbacks if imports failed, so the module can still load for basic Flask operations
    if 'gdrive_service' not in locals():
        gdrive_service = type('obj', (object,), {
            'download_gdrive_file': lambda **kwargs: {"status": "error", "message": "gdrive_service not loaded"},
            'get_gdrive_file_metadata': lambda **kwargs: {"status": "error", "message": "gdrive_service not loaded"},
            'list_gdrive_files': lambda **kwargs: {"status": "error", "message": "gdrive_service not loaded"}
        })()
    if 'document_processor' not in locals():
        document_processor = type('obj', (object,), {'process_document_and_store': lambda **kwargs: {"status": "error", "message": "document_processor not loaded"}})()
    if '_get_valid_gdrive_access_token' not in locals():
        def _get_valid_gdrive_access_token(user_id: str): logger.error("auth_handler._get_valid_gdrive_access_token not loaded"); return None
    if 'get_gdrive_oauth_details' not in locals():
        def get_gdrive_oauth_details(pool, user_id: str): logger.error("db_oauth_gdrive.get_gdrive_oauth_details not loaded"); return None
    if 'get_db_connection_pool' not in locals():
        def get_db_connection_pool(): logger.error("auth_handler.get_db_connection_pool not loaded"); return None


logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

gdrive_bp = Blueprint('gdrive_api', __name__)

@gdrive_bp.errorhandler(Exception)
def handle_gdrive_exception(e): # pragma: no cover
    logger.error(f"Unhandled exception in gdrive_handler: {e}", exc_info=True)
    return jsonify({
        "ok": False,
        "error": {"code": "PYTHON_UNHANDLED_ERROR", "message": "An unexpected server error occurred in GDrive handler.", "details": str(e)}
    }), 500

@gdrive_bp.route('/api/gdrive/connection-status', methods=['GET'])
def gdrive_connection_status_route():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id query parameter is required."}}), 400

    # Placeholder: Verify user_id belongs to authenticated user if using session-based auth

    db_pool = get_db_connection_pool()
    token_details = get_gdrive_oauth_details(db_pool, user_id)

    if token_details and token_details.get("access_token_encrypted"): # Check if token exists
        # Optionally, could use _get_valid_gdrive_access_token to ensure it's not just present but also usable/refreshable
        # For a simple status, just checking existence might be enough.
        # If _get_valid_gdrive_access_token(user_id) returns a token, then it's truly connected.
        # Let's use the more robust check:
        access_token = _get_valid_gdrive_access_token(user_id) # This handles refresh check
        if access_token:
             # Re-fetch details if refresh happened, or use initial details if no refresh was needed.
            updated_token_details = get_gdrive_oauth_details(db_pool, user_id) if token_details["expiry_timestamp_ms"] < (datetime.now(timezone.utc).timestamp() * 1000) else token_details
            gdrive_email = updated_token_details.get("gdrive_user_email", "Email not available") if updated_token_details else "Email not available"
            return jsonify({"ok": True, "data": {"isConnected": True, "email": gdrive_email}}), 200
        else:
            # Token existed but could not be refreshed or was invalid
            return jsonify({"ok": True, "data": {"isConnected": False, "email": None, "reason": "Token refresh failed or token invalid."}}), 200
    else:
        return jsonify({"ok": True, "data": {"isConnected": False, "email": None}}), 200


@gdrive_bp.route('/api/gdrive/list-files', methods=['POST'])
def list_files_route():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    user_id = data.get('user_id')
    folder_id = data.get('folder_id')
    page_token = data.get('page_token')
    page_size = data.get('page_size', 50) # Default page size
    query = data.get('query') # For file name search, e.g., "name contains 'report'"

    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    access_token = _get_valid_gdrive_access_token(user_id)
    if not access_token:
        return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Failed to retrieve valid Google Drive access token. Please re-authenticate."}}), 401

    result = gdrive_service.list_gdrive_files(
        access_token=access_token,
        folder_id=folder_id,
        query=query,
        page_size=page_size,
        page_token=page_token
    )
    if result["status"] == "success":
        return jsonify({"ok": True, "data": result.get("data")}), 200
    else:
        return jsonify({"ok": False, "error": {"code": result.get("code", "GDRIVE_LIST_FAILED"), "message": result.get("message"), "details": result.get("details")}}), 500


@gdrive_bp.route('/api/ingest-gdrive-document', methods=['POST'])
async def ingest_gdrive_document_route():
    if not INGESTION_SERVICES_AVAILABLE or not document_processor or not gdrive_service:
        return jsonify({"ok": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "GDrive ingestion or document processing service is not available."}}), 503

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    user_id = data.get('user_id')
    gdrive_file_id = data.get('gdrive_file_id')
    # access_token = data.get('access_token') # Replaced by user_id lookup
    original_file_metadata = data.get('original_file_metadata', {})
    file_name_from_meta = original_file_metadata.get('name', f"GDrive_{gdrive_file_id}")
    original_gdrive_mime_type = original_file_metadata.get('mimeType', '')
    source_uri_from_meta = original_file_metadata.get('webViewLink', f"gdrive_id_{gdrive_file_id}")
    openai_api_key_param = data.get('openai_api_key')

    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400
    if not gdrive_file_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "gdrive_file_id is required."}}), 400
    if not original_file_metadata or 'name' not in original_file_metadata or 'mimeType' not in original_file_metadata:
         logger.warning(f"Original GDrive file metadata (name, mimeType) missing for file ID {gdrive_file_id}. This is crucial for ingestion.")
         return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "original_file_metadata with name and mimeType is required."}}), 400

    access_token = _get_valid_gdrive_access_token(user_id)
    if not access_token:
        return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Failed to retrieve valid Google Drive access token. Please re-authenticate."}}), 401

    logger.info(f"Request to ingest GDrive file: ID='{gdrive_file_id}', Name='{file_name_from_meta}', User='{user_id}', OriginalMIME='{original_gdrive_mime_type}'")

    # Determine target MIME type for download/export, preferring text-friendly formats
    target_mime_type_for_download = None
    if original_gdrive_mime_type == 'application/vnd.google-apps.document':
        target_mime_type_for_download = 'text/plain' # Prefer plain text for GDocs
        # Alt: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' (DOCX)
    elif original_gdrive_mime_type == 'application/vnd.google-apps.spreadsheet':
        target_mime_type_for_download = 'text/csv' # Prefer CSV for GSheets
        # Alt: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' (XLSX)
    elif original_gdrive_mime_type == 'application/vnd.google-apps.presentation':
        target_mime_type_for_download = 'application/pdf' # PDF is often best for text from slides
    elif original_gdrive_mime_type in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']:
        target_mime_type_for_download = None # Download as is
    else: # For other unknown or binary types, attempt PDF export if GSuite, else direct download
        if original_gdrive_mime_type.startswith('application/vnd.google-apps.'):
            target_mime_type_for_download = 'application/pdf'
            logger.info(f"Unknown GSuite type {original_gdrive_mime_type}, attempting PDF export for file {gdrive_file_id}")
        else: # Non-GSuite, non-directly processable type - direct download
            logger.info(f"Non-GSuite, non-directly processable type {original_gdrive_mime_type} for file {gdrive_file_id}. Will attempt direct download.")
            target_mime_type_for_download = None


    download_result = gdrive_service.download_gdrive_file(
        access_token=access_token,
        file_id=gdrive_file_id,
        target_mime_type=target_mime_type_for_download
    )

    if download_result["status"] != "success":
        logger.error(f"Failed to download GDrive file {gdrive_file_id}: {download_result.get('message')}")
        return jsonify({"ok": False, "error": {"code": download_result.get("code", "GDRIVE_DOWNLOAD_FAILED"), "message": download_result.get("message")}}), 500

    downloaded_data = download_result["data"]
    file_content_bytes = downloaded_data["content_bytes"]
    downloaded_file_name = downloaded_data["file_name"] # Name after potential export extension change
    processing_mime_type = downloaded_data["mime_type"] # Actual MIME type of downloaded/exported content

    temp_dir = None
    temp_file_path = None
    try:
        temp_dir = tempfile.mkdtemp()
        # Use the name determined by download_gdrive_file (which includes new extension if exported)
        temp_file_path = os.path.join(temp_dir, downloaded_file_name)
        with open(temp_file_path, 'wb') as f:
            f.write(file_content_bytes)

        logger.info(f"GDrive file {gdrive_file_id} downloaded to temp path: {temp_file_path} as MIME: {processing_mime_type}")

        document_id = str(uuid.uuid4())

        # Construct original_doc_type for storage metadata
        # Use a cleaned version of the original GDrive MIME type
        original_doc_type_for_storage = f"gdrive_{original_gdrive_mime_type.split('/')[-1].replace('.', '_').replace('-', '_')}"

        processing_result = await document_processor.process_document_and_store(
            user_id=user_id,
            file_path_or_bytes=temp_file_path,
            document_id=document_id,
            source_uri=source_uri_from_meta,
            original_doc_type=original_doc_type_for_storage,
            processing_mime_type=processing_mime_type,
            title=file_name_from_meta, # Use original GDrive name for title
            doc_metadata_json=None, # Can add GDrive specific metadata here if needed
            openai_api_key_param=openai_api_key
        )

        if processing_result["status"] == "success" or processing_result["status"] == "warning":
            return jsonify({"ok": True, "data": processing_result.get("data"), "message": processing_result.get("message")}), 201 if processing_result["status"] == "success" else 200
        else:
            status_code = 500
            if processing_result.get("code") == "UNSUPPORTED_PROCESSING_TYPE": status_code = 415
            return jsonify({"ok": False, "error": {"code": processing_result.get("code", "DOCUMENT_PROCESSING_FAILED"), "message": processing_result.get("message")}}), status_code

    except Exception as e:
        logger.error(f"Error during GDrive document ingestion pipeline for {gdrive_file_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GDRIVE_INGESTION_PIPELINE_ERROR", "message": str(e)}}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except OSError as e_rm:
                logger.error(f"Error removing temp directory {temp_dir}: {e_rm}", exc_info=True)

@gdrive_bp.route('/api/gdrive/get-file-metadata', methods=['POST'])
def get_file_metadata_route():
    # if not INGESTION_SERVICES_AVAILABLE: # gdrive_service might be available even if full ingestion isn't
    #     return jsonify({"ok": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "GDrive service or its dependencies are not available."}}), 503
    if not hasattr(gdrive_service, 'get_gdrive_file_metadata'): # Check if gdrive_service itself is loaded
        logger.critical("gdrive_service.get_gdrive_file_metadata is not available. Module may not have loaded correctly.")
        return jsonify({"ok": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "Core GDrive service component is not available."}}), 503

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    user_id = data.get('user_id') # Expect user_id instead of access_token
    file_id = data.get('file_id')
    fields = data.get('fields')

    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400
    if not file_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "file_id is required."}}), 400

    access_token = _get_valid_gdrive_access_token(user_id)
    if not access_token:
        return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Failed to retrieve valid Google Drive access token. Please re-authenticate."}}), 401

    logger.info(f"Route /api/gdrive/get-file-metadata called for user_id: {user_id}, file_id: {file_id}")

    result = gdrive_service.get_gdrive_file_metadata(
        access_token=access_token,
        file_id=file_id,
        fields=fields
    )

    if result["status"] == "success":
        return jsonify({"ok": True, "data": result.get("data")}), 200
    else:
        error_payload = {
            "code": result.get("code", "GDRIVE_METADATA_FETCH_FAILED"),
            "message": result.get("message"),
            "details": result.get("details")
        }
        status_code = 500
        if "GDRIVE_API_OBJECT_NOT_FOUND" in (result.get("code") or "") or \
           "GDRIVE_API_FILE_NOT_FOUND" in (result.get("code") or ""):
            status_code = 404
        elif "GDRIVE_API_UNAUTHORIZED" in (result.get("code") or "") or \
             "GDRIVE_API_FORBIDDEN" in (result.get("code") or ""):
            status_code = 401

        logger.warn(f"Failed to get metadata for GDrive file {file_id}. Status: {status_code}, Code: {result.get('code')}, Message: {result.get('message')}")
        return jsonify({"ok": False, "error": error_payload}), status_code

# Example of how this blueprint would be registered in the main Flask app
# (e.g., in python_api_service/note_handler.py or a main app.py)
# from .gdrive_handler import gdrive_bp
# app.register_blueprint(gdrive_bp)

if __name__ == '__main__':
    # This allows running this handler standalone for development/testing
    # A real setup would register gdrive_bp with the main python_api_service Flask app.
    # To test, ensure python-api/ingestion_pipeline and project/functions are in PYTHONPATH
    # and necessary environment variables (like OPENAI_API_KEY for embedding) are set.

    # Need to create a temporary app to register blueprint for standalone run
    # This is NOT how it would run in production.
    # In production, the main app (e.g. from note_handler.py or a central app.py)
    # would import and register gdrive_bp.

    # For standalone testing of gdrive_handler.py:
    # 1. Make sure Flask is installed.
    # 2. Run this file: python gdrive_handler.py
    # 3. It will start a Flask dev server on port 5060 (or $GDOC_HANDLER_PORT).
    # 4. You can then send POST requests to /api/ingest-gdrive-document etc.
    # Note: Dependencies like note_utils and lancedb_handler must be importable.

    _main_app = Flask(__name__)
    _main_app.register_blueprint(gdrive_bp)

    # A basic error handler for the temporary app
    @_main_app.errorhandler(Exception)
    def _temp_app_handle_exception(e):
        logger.error(f"Unhandled exception in gdrive_handler standalone app: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "PYTHON_STANDALONE_ERROR", "message": str(e)}}), 500

    logger.info("Starting gdrive_handler.py standalone for testing on port 5060 (or $GDOC_HANDLER_PORT)")
    flask_port = int(os.environ.get("GDOC_HANDLER_PORT", 5060))
    _main_app.run(host='0.0.0.0', port=flask_port, debug=True)

```
