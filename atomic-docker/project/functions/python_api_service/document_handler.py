import os
import sys
import tempfile
import uuid
import logging
from flask import Flask, request, jsonify # Ensure Blueprint is imported if switching from local app
# from flask import Blueprint # If this becomes a blueprint registered elsewhere

# Adjust path for imports
PYTHON_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PYTHON_API_DIR not in sys.path:
    sys.path.append(PYTHON_API_DIR)
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)

try:
    # Changed import from process_pdf_and_store to process_document_and_store
    from ingestion_pipeline import document_processor
    INGESTION_SERVICES_AVAILABLE = True
    if not hasattr(document_processor, 'process_document_and_store'):
        # This can happen if the overwrite of document_processor.py failed or was partial
        logging.getLogger(__name__).error("CRITICAL: document_processor.process_document_and_store not found after import!")
        INGESTION_SERVICES_AVAILABLE = False
except ImportError as e1:
    print(f"Error importing document_processor: {e1}", file=sys.stderr)
    INGESTION_SERVICES_AVAILABLE = False
    document_processor = None

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# document_bp = Blueprint('document_api', __name__) # If using blueprints
app = Flask(__name__) # Assuming standalone app for now, or this is the main app file

@app.errorhandler(Exception)
def handle_generic_exception(e):
    logger.error(f"Unhandled exception in document_handler: {e}", exc_info=True)
    return jsonify({
        "ok": False,
        "error": {"code": "PYTHON_UNHANDLED_ERROR", "message": "An unexpected server error occurred.", "details": str(e)}
    }), 500

@app.route('/api/ingest-document', methods=['POST'])
async def ingest_document_route():
    if not INGESTION_SERVICES_AVAILABLE or not document_processor:
        return jsonify({"ok": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "Document processing service is not available."}}), 503

    if 'file' not in request.files:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Missing 'file' in request."}}), 400

    file_storage_object = request.files['file'] # This is a FileStorage object
    if not file_storage_object.filename: # Check if a file was actually selected
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "No file selected."}}), 400

    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id form field is required."}}), 400

    original_filename = file_storage_object.filename
    processing_mime_type = file_storage_object.mimetype # Get MIME type from Flask's FileStorage

    # Determine original_doc_type based on filename extension for storage metadata
    # This helps categorize the original upload type in the DB.
    _, file_extension = os.path.splitext(original_filename)
    file_ext_lower = file_extension.lower()

    original_doc_type_for_storage = "upload_unknown" # Default
    if file_ext_lower == ".pdf":
        original_doc_type_for_storage = "upload_pdf"
        if not processing_mime_type: processing_mime_type = "application/pdf" # Fallback if mimetype not sent
    elif file_ext_lower == ".docx":
        original_doc_type_for_storage = "upload_docx"
        if not processing_mime_type: processing_mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif file_ext_lower == ".txt":
        original_doc_type_for_storage = "upload_txt"
        if not processing_mime_type: processing_mime_type = "text/plain"
    # Add more types as document_processor supports them

    if not processing_mime_type: # If still no MIME type after checks
        logger.warning(f"Could not determine MIME type for uploaded file {original_filename}. Ingestion may fail or be incorrect.")
        # Allow to proceed, document_processor will handle unsupported types if it can't process based on this.

    source_uri = request.form.get('source_uri', original_filename)
    title = request.form.get('title', os.path.splitext(original_filename)[0])
    openai_api_key = request.form.get('openai_api_key')

    temp_dir = None
    temp_file_path = None
    try:
        temp_dir = tempfile.mkdtemp()
        # Use a generic name for temp file to avoid issues with special chars in user filenames
        temp_file_path = os.path.join(temp_dir, "uploaded_file" + file_extension)
        file_storage_object.save(temp_file_path)

        document_id = str(uuid.uuid4())

        logger.info(f"Processing uploaded document: id={document_id}, user={user_id}, original_filename='{original_filename}', processing_mime='{processing_mime_type}', original_doc_type_for_storage='{original_doc_type_for_storage}'")

        result = await document_processor.process_document_and_store(
            user_id=user_id,
            file_path_or_bytes=temp_file_path, # Pass path to saved temp file
            document_id=document_id,
            source_uri=source_uri,
            original_doc_type=original_doc_type_for_storage,
            processing_mime_type=processing_mime_type,
            title=title,
            doc_metadata_json=None,
            openai_api_key_param=openai_api_key
        )

        if result["status"] == "success" or result["status"] == "warning": # Treat warning (e.g. empty content) as partial success from endpoint view
            return jsonify({"ok": True, "data": result.get("data"), "message": result.get("message")}), 201 if result["status"] == "success" else 200
        else:
            status_code = 500
            if result.get("code") == "UNSUPPORTED_PROCESSING_TYPE": status_code = 415 # Unsupported Media Type
            elif result.get("code") == "TEXT_EXTRACTION_FAILED": status_code = 500
            # Add more specific mappings if needed
            return jsonify({"ok": False, "error": {"code": result.get("code"), "message": result.get("message")}}), status_code

    except Exception as e:
        logger.error(f"Error during document ingestion for user {user_id}, file {original_filename}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "DOCUMENT_INGESTION_FAILED", "message": str(e)}}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if temp_dir and os.path.exists(temp_dir):
            # Use shutil.rmtree for directories that might not be empty if file save failed mid-way
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except OSError as e_rm:
                logger.error(f"Error removing temp directory {temp_dir}: {e_rm}", exc_info=True)

if __name__ == '__main__':
    flask_port = int(os.environ.get("DOCUMENT_HANDLER_PORT", 5059))
    app.run(host='0.0.0.0', port=flask_port, debug=True)
```
