import io
import os
import logging
from typing import List, Dict, Any, Optional
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams

# Assuming note_utils.py is accessible for embedding.
# This path might need adjustment based on actual execution environment or by making embedding a service call.
# For now, direct import if they are part of the same broader Python package/environment.
try:
    # Adjust path if note_utils is not directly importable like this
    # This assumes that the 'functions' directory is in PYTHONPATH or they are installed as a package
    from project.functions import note_utils # Example: if 'functions' is a top-level package for the python_api_service
except ImportError:
    # Fallback if the above isn't right - this is tricky without seeing full PYTHONPATH setup for python-api
    # This is a common way to handle sibling directory imports if script is run from python-api/ingestion_pipeline
    import sys
    FUNCTIONS_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
    if FUNCTIONS_DIR_PATH not in sys.path:
        sys.path.append(FUNCTIONS_DIR_PATH)
    try:
        import note_utils # Now try importing from the adjusted path
    except ImportError as e:
        print(f"Critical Error: Could not import note_utils for embeddings: {e}. Ensure FUNCTIONS_DIR_PATH is correct.", file=sys.stderr)
        note_utils = None # Will cause errors later if embedding is attempted

# Import lancedb_handler for DB operations
try:
    from . import lancedb_handler # If lancedb_handler is in the same directory
except ImportError:
    import lancedb_handler # Fallback if run standalone or path issues

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def extract_text_from_pdf(pdf_file_path: str) -> str:
    """Extracts text content from a PDF file."""
    try:
        output_string = io.StringIO()
        with open(pdf_file_path, 'rb') as fin:
            laparams = LAParams() # Use default LAParams
            extract_text_to_fp(fin, output_string, laparams=laparams, output_type='text', codec='utf-8')
        return output_string.getvalue()
    except Exception as e:
        logger.error(f"Error extracting text from PDF {pdf_file_path}: {e}", exc_info=True)
        raise  # Re-raise to be handled by caller


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """
    Splits text into overlapping chunks.
    A simple implementation based on character count. More sophisticated methods exist (e.g., by sentences, tokens).
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= text_len:
            break
        start += (chunk_size - chunk_overlap)
        if start >= text_len: # Ensure we don't create an empty chunk if overlap pushes start to end
            break

    return chunks


async def process_pdf_and_store(
    user_id: str,
    pdf_file_path: str,
    document_id: str, # Pre-generated UUID for the document
    source_uri: str,
    title: Optional[str] = None,
    doc_source_type: str = "pdf_upload", # Default source type
    doc_metadata_json: Optional[str] = None, # Additional metadata for the document table
    openai_api_key_param: Optional[str] = None # Pass if not relying on global OPENAI_API_KEY_GLOBAL in note_utils
) -> Dict[str, Any]:
    """
    Orchestrates PDF processing: text extraction, chunking, embedding, and storage in LanceDB.
    """
    logger.info(f"Starting processing for PDF: {source_uri}, doc_id: {document_id}, user_id: {user_id}")

    if not note_utils: # Check if import failed
        return {"status": "error", "message": "Embedding utility (note_utils) not available.", "code": "INTERNAL_SETUP_ERROR"}

    try:
        extracted_text = extract_text_from_pdf(pdf_file_path)
        if not extracted_text.strip():
            logger.warning(f"No text extracted from PDF: {source_uri}")
            # Store document metadata with status 'processing_failed' or 'empty'
            # For now, returning error, but could also store an entry indicating empty content.
            doc_meta_to_store = {
                "id": document_id, "user_id": user_id, "source_uri": source_uri,
                "doc_type": doc_source_type, "title": title, "metadata_json": doc_metadata_json,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "processing_status": "failed_empty_content",
                "error_message": "No text content extracted from PDF."
            }
            db_conn = await lancedb_handler.get_lancedb_connection()
            if db_conn:
                await lancedb_handler.create_generic_document_tables_if_not_exist(db_conn) # Ensure tables exist
                # This function needs to be added to lancedb_handler.py
                await lancedb_handler.add_document_metadata_only(db_conn, doc_meta_to_store)
            return {"status": "error", "message": "No text extracted from PDF.", "code": "PDF_PROCESSING_EMPTY"}

        text_chunks = chunk_text(extracted_text) # Uses default chunk_size and overlap
        logger.info(f"Extracted {len(extracted_text)} chars, split into {len(text_chunks)} chunks for doc_id: {document_id}")

        chunks_with_embeddings_data = []
        for i, chunk_text_content in enumerate(text_chunks):
            if not chunk_text_content.strip():
                logger.info(f"Skipping empty chunk {i} for doc_id: {document_id}")
                continue

            # Generate embedding for the chunk
            # note_utils.get_text_embedding_openai needs to be callable, ensure it's correctly imported/configured
            embedding_resp = note_utils.get_text_embedding_openai(
                text_to_embed=chunk_text_content,
                openai_api_key_param=openai_api_key_param # Pass key if provided, else note_utils uses global
            )
            if embedding_resp["status"] == "success":
                vector = embedding_resp["data"]
                chunks_with_embeddings_data.append({
                    # "id" for chunk can be auto-generated by lancedb_handler or passed (e.g., f"{document_id}_chunk_{i}")
                    "chunk_sequence": i,
                    "text_content": chunk_text_content,
                    "vector": vector,
                    "metadata_json": None, # Placeholder for now
                    "char_count": len(chunk_text_content)
                })
            else:
                logger.warning(f"Failed to generate embedding for chunk {i} of doc_id {document_id}: {embedding_resp.get('message')}")
                # Decide: skip chunk or fail entire document processing? For now, skip chunk.

        if not chunks_with_embeddings_data:
            logger.warning(f"No chunks were successfully embedded for doc_id: {document_id}")
            # Similar to empty PDF, could store metadata with error, or return error.
            # For now, treat as error if no chunks could be stored.
            return {"status": "error", "message": "No chunks could be embedded for the document.", "code": "EMBEDDING_FAILURE_ALL_CHUNKS"}

        # Prepare document metadata for storage
        doc_meta_to_store = {
            "id": document_id, "user_id": user_id, "source_uri": source_uri,
            "doc_type": doc_source_type, "title": title, "metadata_json": doc_metadata_json,
            "ingested_at": datetime.now(timezone.utc).isoformat(), # Use timezone aware
            "processing_status": "completed",
        }

        # Store in LanceDB
        db_conn = await lancedb_handler.get_lancedb_connection()
        if not db_conn:
            return {"status": "error", "message": "Failed to connect to LanceDB.", "code": "LANCEDB_CONNECTION_ERROR"}

        # These table creation functions will be added to lancedb_handler.py
        await lancedb_handler.create_generic_document_tables_if_not_exist(db_conn)

        # This function will be added to lancedb_handler.py
        # It should add to 'documents' table and 'document_chunks' table
        storage_result = await lancedb_handler.add_processed_document(
            db_conn=db_conn,
            doc_meta=doc_meta_to_store,
            chunks_with_embeddings=chunks_with_embeddings_data # Pass the list of chunk dicts
        )

        if storage_result["status"] == "success":
            logger.info(f"Successfully processed and stored PDF: {source_uri}, doc_id: {document_id}")
            return {"status": "success", "data": {"doc_id": document_id, "num_chunks_stored": len(chunks_with_embeddings_data)}}
        else:
            logger.error(f"Failed to store processed document {document_id} in LanceDB: {storage_result.get('message')}")
            # Update document processing_status to 'failed_storage' if possible
            return {"status": "error", "message": f"LanceDB storage failed: {storage_result.get('message')}", "code": storage_result.get("code", "LANCEDB_STORAGE_ERROR")}

    except Exception as e:
        logger.error(f"Unhandled error in process_pdf_and_store for {source_uri}, doc_id {document_id}: {e}", exc_info=True)
        # Potentially update document status to 'failed' in DB here if doc_id was already created
        return {"status": "error", "message": f"Unexpected error processing PDF: {str(e)}", "code": "PYTHON_INTERNAL_ERROR_PDF_PROCESSING"}

```
