import os
import sys
import tempfile
import uuid
import logging
from flask import Blueprint, request, jsonify

# Adjust path for imports - assumes this file is in python_api_service
# Path to 'python-api/' (parent of python_api_service)
PYTHON_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PYTHON_API_DIR not in sys.path:
    sys.path.append(PYTHON_API_DIR)

# Path to 'project/functions/' for note_utils (if used for embeddings by document_processor)
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)

try:
    from . import gdrive_service # Expects gdrive_service.py in the same directory (python_api_service)
    from ingestion_pipeline import document_processor # Expects document_processor in ingestion_pipeline subdir
    INGESTION_SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"Error importing gdrive_service or document_processor: {e}. GDrive ingestion will not be fully functional.", file=sys.stderr)
    INGESTION_SERVICES_AVAILABLE = False
    # Mock them if necessary for app loading, but calls will fail
    gdrive_service = type('obj', (object,), {'download_gdrive_file': lambda **kwargs: {"status": "error", "message": "gdrive_service not loaded"}})()
    document_processor = type('obj', (object,), {'process_pdf_and_store': lambda **kwargs: {"status": "error", "message": "document_processor not loaded"}})()


logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

gdrive_bp = Blueprint('gdrive_api', __name__)

@gdrive_bp.errorhandler(Exception)
def handle_gdrive_exception(e):
    logger.error(f"Unhandled exception in gdrive_handler: {e}", exc_info=True)
    return jsonify({
        "ok": False,
        "error": {"code": "PYTHON_UNHANDLED_ERROR", "message": "An unexpected server error occurred in GDrive handler.", "details": str(e)}
    }), 500

@gdrive_bp.route('/api/ingest-gdrive-document', methods=['POST'])
async def ingest_gdrive_document_route(): # Made async
    if not INGESTION_SERVICES_AVAILABLE:
        return jsonify({"ok": False, "error": {"code": "SERVICE_UNAVAILABLE", "message": "GDrive ingestion or document processing service is not available."}}), 503

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": {"code": "INVALID_PAYLOAD", "message": "Request must be JSON."}}), 400

    user_id = data.get('user_id')
    gdrive_file_id = data.get('gdrive_file_id')
    access_token = data.get('access_token') # Direct access token for simplicity in this example
    # In production, this might be an internal token_ref to look up the actual GDrive access_token

    original_file_metadata = data.get('original_file_metadata', {})
    file_name = original_file_metadata.get('name', 'Untitled Google Drive File')
    original_mime_type = original_file_metadata.get('mimeType', '')
    source_uri = original_file_metadata.get('webViewLink', f"gdrive_id_{gdrive_file_id}")

    openai_api_key_param = data.get('openai_api_key') # Optional key for embeddings

    if not all([user_id, gdrive_file_id, access_token]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Missing required fields: user_id, gdrive_file_id, access_token."}}), 400

    logger.info(f"Received request to ingest GDrive file: ID='{gdrive_file_id}', Name='{file_name}', User='{user_id}'")

    # Determine target MIME type for download/export
    target_mime_type_for_download = None
    doc_processor_input_type = "pdf" # Assume PDF for now, as that's what process_pdf_and_store handles

    if original_mime_type.startswith('application/vnd.google-apps'):
        if original_mime_type == 'application/vnd.google-apps.document':
            target_mime_type_for_download = 'application/pdf'
            # file_name_for_processor = f"{os.path.splitext(file_name)[0]}.pdf"
        elif original_mime_type == 'application/vnd.google-apps.spreadsheet':
            # TODO: process_pdf_and_store currently only handles PDFs.
            # Need text extraction for XLSX or export GSheet as CSV/TSV then process text.
            # For now, this path will likely fail or needs a different processor.
            # target_mime_type_for_download = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            # doc_processor_input_type = "xlsx"
            logger.warning(f"Processing Google Sheets (ID: {gdrive_file_id}) as text via PDF export is a TODO. Attempting PDF export.")
            target_mime_type_for_download = 'application/pdf' # Fallback to PDF for text
        elif original_mime_type == 'application/vnd.google-apps.presentation':
            target_mime_type_for_download = 'application/pdf'
            # file_name_for_processor = f"{os.path.splitext(file_name)[0]}.pdf"
        else: # Other GSuite types
            logger.warning(f"Unsupported Google Workspace MIME type for direct processing: {original_mime_type}. Attempting PDF export.")
            target_mime_type_for_download = 'application/pdf'
    elif original_mime_type == 'application/pdf':
        doc_processor_input_type = "pdf" # Already a PDF
    # TODO: Add handling for other direct download types like .docx, .txt if document_processor supports them.
    else:
        logger.warning(f"GDrive file {gdrive_file_id} has MIME type {original_mime_type}, which may not be directly processable by PDF pipeline. Attempting direct download.")
        # No target_mime_type means direct download. document_processor must handle it.
        # For now, we assume it must become a PDF to go through process_pdf_and_store.
        # This part needs more robust type handling based on what document_processor can take.
        # If we only support PDF processing, we should error here for non-convertible/non-PDF types.
        return jsonify({"ok": False, "error": {"code": "UNSUPPORTED_MIME_TYPE", "message": f"MIME type {original_mime_type} for GDrive file {gdrive_file_id} is not yet supported for ingestion via PDF pipeline."}}), 400


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
    # Use the (potentially extension-changed) name from download_result for the temp file
    temp_file_name_for_processing = downloaded_data["file_name"]

    temp_dir = None
    temp_file_path = None
    try:
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, temp_file_name_for_processing) # Use name from download
        with open(temp_file_path, 'wb') as f:
            f.write(file_content_bytes)

        logger.info(f"GDrive file {gdrive_file_id} downloaded to temp path: {temp_file_path}")

        document_id = str(uuid.uuid4()) # New UUID for this ingested document

        # Current document_processor.process_pdf_and_store is specific to PDFs.
        # If download_gdrive_file always converts to PDF, this is fine.
        # Otherwise, process_pdf_and_store needs to become more generic or we need type-specific processors.
        if doc_processor_input_type != "pdf": # Placeholder for future when it handles more types
             return jsonify({"ok": False, "error": {"code": "PROCESSOR_TYPE_MISMATCH", "message": f"Document processor currently set for PDF, but got type {doc_processor_input_type} from GDrive download."}}), 500


        processing_result = await document_processor.process_pdf_and_store(
            user_id=user_id,
            pdf_file_path=temp_file_path, # Path to the downloaded (and potentially converted) PDF
            document_id=document_id,
            source_uri=source_uri, # Original GDrive webViewLink
            title=file_name, # Original GDrive file name
            doc_source_type=f"gdrive_{original_mime_type.split('/')[-1].replace('.', '_')}", # e.g. gdrive_pdf, gdrive_document
            openai_api_key_param=openai_api_key
        )

        if processing_result["status"] == "success":
            return jsonify({"ok": True, "data": processing_result.get("data")}), 201
        else:
            return jsonify({"ok": False, "error": {"code": processing_result.get("code", "DOCUMENT_PROCESSING_FAILED"), "message": processing_result.get("message")}}), 500

    except Exception as e:
        logger.error(f"Error during GDrive document ingestion pipeline for {gdrive_file_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GDRIVE_INGESTION_PIPELINE_ERROR", "message": str(e)}}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if temp_dir and os.path.exists(temp_dir):
            # os.rmdir(temp_dir) # This fails if files were created then deleted, use shutil
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except OSError as e_rm:
                logger.error(f"Error removing temp directory {temp_dir}: {e_rm}", exc_info=True)

# Example of how this blueprint would be registered in the main Flask app
# (e.g., in python_api_service/note_handler.py or a main app.py)
# from .gdrive_handler import gdrive_bp
# app.register_blueprint(gdrive_bp)

if __name__ == '__main__':
    # This allows running this handler standalone for development/testing,
    # but it won't have other registered blueprints unless main app is structured differently.
    # For testing, one would typically run the main Flask app that includes this blueprint.
    app.run(host='0.0.0.0', port=5060, debug=True) # Use a different port for standalone run
```
