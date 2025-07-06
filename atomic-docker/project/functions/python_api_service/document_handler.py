import os
import sys
import tempfile
import uuid
import logging
from flask import Flask, request, jsonify

# Adjust path to import from sibling 'ingestion_pipeline' and 'project/functions'
# This assumes 'python_api_service' is the root for this Flask app or blueprint.
# Path to 'python-api/'
PYTHON_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PYTHON_API_DIR not in sys.path:
    sys.path.append(PYTHON_API_DIR)

# Path to 'project/functions/'
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)

try:
    from ingestion_pipeline import document_processor
except ImportError as e1:
    print(f"Error importing document_processor: {e1}", file=sys.stderr)
    document_processor = None

# Configure logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# This could be a Blueprint
# For simplicity in this example, creating a new Flask app.
# In a real scenario, this would be a Blueprint registered with the main app in python_api_service.
# from flask import Blueprint
# document_bp = Blueprint('document_api', __name__)
# @document_bp.route('/api/ingest-document', methods=['POST'])

app = Flask(__name__) # In real app, use existing app or blueprint from main service file

@app.errorhandler(Exception)
def handle_generic_exception(e):
    logger.error(f"Unhandled exception in document_handler: {e}", exc_info=True)
    return jsonify({
        "ok": False,
        "error": {"code": "PYTHON_UNHANDLED_ERROR", "message": "An unexpected server error occurred.", "details": str(e)}
    }), 500

@app.route('/api/ingest-document', methods=['POST'])
async def ingest_document_route(): # Made async as process_pdf_and_store is async
    if not document_processor:
        return jsonify({"ok": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "Document processing service is not available."}}), 503

    if 'file' not in request.files:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Missing 'file' in request."}}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "No file selected."}}), 400

    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id form field is required."}}), 400

    source_uri = request.form.get('source_uri', file.filename) # Use filename if source_uri not provided
    title = request.form.get('title', os.path.splitext(file.filename)[0] if file.filename else "Uploaded Document")
    doc_type = request.form.get('doc_type', "pdf") # Default to pdf, could infer from filename
    openai_api_key = request.form.get('openai_api_key') # Optional, if user-specific key for embedding

    temp_dir = None
    temp_file_path = None
    try:
        temp_dir = tempfile.mkdtemp()
        # Consider security implications of filename, though it's temporary.
        # For production, use a secured/randomized filename.
        temp_file_path = os.path.join(temp_dir, file.filename if file.filename else "upload.tmp")
        file.save(temp_file_path)

        document_id = str(uuid.uuid4()) # Generate a unique ID for this document

        logger.info(f"Processing document: id={document_id}, user={user_id}, source={source_uri}, title={title}")

        result = await document_processor.process_pdf_and_store(
            user_id=user_id,
            pdf_file_path=temp_file_path,
            document_id=document_id,
            source_uri=source_uri,
            title=title,
            doc_source_type=doc_type,
            openai_api_key_param=openai_api_key # Pass to use specific key for embedding
        )

        if result["status"] == "success":
            return jsonify({"ok": True, "data": result.get("data")}), 201 # 201 Created
        else:
            # Determine appropriate HTTP status code based on error
            status_code = 500
            if result.get("code") == "PDF_PROCESSING_EMPTY": status_code = 400
            elif result.get("code") == "EMBEDDING_FAILURE_ALL_CHUNKS": status_code = 500
            # Add more mappings as needed
            return jsonify({"ok": False, "error": {"code": result.get("code"), "message": result.get("message")}}), status_code

    except Exception as e:
        logger.error(f"Error during document ingestion for user {user_id}, file {source_uri}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "DOCUMENT_INGESTION_FAILED", "message": str(e)}}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if temp_dir and os.path.exists(temp_dir):
            os.rmdir(temp_dir)

# This is for standalone running. In a real setup, this 'app' or a blueprint from it
# would be imported and registered by the main python_api_service Flask app.
if __name__ == '__main__':
    # Example: python -m ingestion_pipeline.document_handler (if in PYTHONPATH)
    # Or python document_handler.py (if run directly from its dir, path adjustments are key)
    flask_port = int(os.environ.get("DOCUMENT_HANDLER_PORT", 5059)) # Different port
    # Note: Running multiple Flask apps directly like this is for dev only.
    # A production setup would use a proper WSGI server (gunicorn) and one main app.
    app.run(host='0.0.0.0', port=flask_port, debug=True)

```
