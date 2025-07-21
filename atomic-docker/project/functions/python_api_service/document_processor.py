import io
import os
import logging
import json # Added for metadata serialization
from typing import List, Dict, Any, Optional
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from datetime import datetime, timezone # For ingested_at timestamp

# Attempt to import python-docx
try:
    import docx # from python-docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("python-docx library not found. DOCX processing will not be available.")
    PYTHON_DOCX_AVAILABLE = False
    docx = None # type: ignore

# Attempt to import BeautifulSoup
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("BeautifulSoup4 library not found. HTML processing will not be available.")
    BS4_AVAILABLE = False
    BeautifulSoup = None # type: ignore

# Embedding and LanceDB imports (adjust paths as necessary based on execution context)
try:
    import sys
    FUNCTIONS_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'project', 'functions'))
    if FUNCTIONS_DIR_PATH not in sys.path:
        sys.path.append(FUNCTIONS_DIR_PATH)
    from note_utils import get_text_embedding_openai
    EMBEDDING_FUNCTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import get_text_embedding_openai from note_utils: {e}. Embedding will not be available.")
    get_text_embedding_openai = None
    EMBEDDING_FUNCTION_AVAILABLE = False

from . import lancedb_handler


logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Text Extraction Utilities ---
def extract_text_from_pdf(pdf_file_path_or_bytes: Any) -> str:
    try:
        output_string = io.StringIO()
        laparams = LAParams()
        if isinstance(pdf_file_path_or_bytes, str):
            if not os.path.exists(pdf_file_path_or_bytes):
                raise FileNotFoundError(f"PDF file not found at path: {pdf_file_path_or_bytes}")
            with open(pdf_file_path_or_bytes, 'rb') as fin:
                extract_text_to_fp(fin, output_string, laparams=laparams, output_type='text', codec='utf-8')
        elif isinstance(pdf_file_path_or_bytes, bytes):
             with io.BytesIO(pdf_file_path_or_bytes) as fin:
                extract_text_to_fp(fin, output_string, laparams=laparams, output_type='text', codec='utf-8')
        else:
            raise ValueError("Input for PDF extraction must be a file path (str) or bytes.")
        return output_string.getvalue()
    except Exception as e:
        logger.error(f"Error extracting text from PDF input: {e}", exc_info=True)
        raise

def extract_text_from_docx(file_path_or_bytes: Any) -> str:
    if not PYTHON_DOCX_AVAILABLE or not docx:
        raise ImportError("python-docx library is required for DOCX processing but not found.")

    extracted_elements: List[str] = []
    doc_properties: Dict[str, Any] = {}

    try:
        if isinstance(file_path_or_bytes, str):
            if not os.path.exists(file_path_or_bytes):
                raise FileNotFoundError(f"DOCX file not found at path: {file_path_or_bytes}")
            document = docx.Document(file_path_or_bytes)
        elif isinstance(file_path_or_bytes, bytes):
            document = docx.Document(io.BytesIO(file_path_or_bytes))
        else:
            raise ValueError("Input for DOCX extraction must be a file path (str) or bytes.")

        # Extract core properties
        props = document.core_properties
        doc_properties['author'] = props.author
        doc_properties['category'] = props.category
        doc_properties['comments'] = props.comments
        doc_properties['content_status'] = props.content_status
        doc_properties['created'] = props.created.isoformat() if props.created else None
        doc_properties['identifier'] = props.identifier
        doc_properties['keywords'] = props.keywords
        doc_properties['language'] = props.language
        doc_properties['last_modified_by'] = props.last_modified_by
        doc_properties['last_printed'] = props.last_printed.isoformat() if props.last_printed else None
        doc_properties['modified'] = props.modified.isoformat() if props.modified else None
        doc_properties['revision'] = props.revision
        doc_properties['subject'] = props.subject
        doc_properties['title'] = props.title
        doc_properties['version'] = props.version

        # Filter out None values from properties
        doc_properties = {k: v for k, v in doc_properties.items() if v is not None and v != ''}


        # Iterate through document body elements (paragraphs and tables)
        for element in document.element.body:
            if isinstance(element, docx.oxml.text.paragraph.CT_P): # Paragraph
                para = docx.text.paragraph.Paragraph(element, document)
                if para.text.strip():
                    style_name = para.style.name.lower() if para.style else ''
                    text = para.text.strip()

                    # Basic heading detection (can be expanded)
                    if style_name.startswith('heading 1') or style_name.startswith('h1'):
                        extracted_elements.append(f"[H1] {text}")
                    elif style_name.startswith('heading 2') or style_name.startswith('h2'):
                        extracted_elements.append(f"[H2] {text}")
                    elif style_name.startswith('heading 3') or style_name.startswith('h3'):
                        extracted_elements.append(f"[H3] {text}")
                    elif style_name.startswith('heading 4') or style_name.startswith('h4'):
                        extracted_elements.append(f"[H4] {text}")
                    # Basic list item detection (very naive)
                    elif para.style.name.lower().startswith('list paragraph') or \
                         (len(para.runs) > 0 and para.runs[0].text.strip() in ['•', '*', '-', '1.', 'a.']) : # common list markers
                        extracted_elements.append(f"[LIST_ITEM] {text}")
                    else:
                        extracted_elements.append(text)

            elif isinstance(element, docx.oxml.table.CT_Tbl): # Table
                table = docx.table.Table(element, document)
                extracted_elements.append("[TABLE_START]")
                for row_idx, row in enumerate(table.rows):
                    row_texts: List[str] = []
                    for cell_idx, cell in enumerate(row.cells):
                        cell_text = cell.text.strip().replace("\n", " ").replace("\t", " ") # Normalize cell content
                        row_texts.append(f"[TABLE_CELL row={row_idx+1} col={cell_idx+1}] {cell_text}")
                    extracted_elements.append("[TABLE_ROW_START]\n" + "\n".join(row_texts) + "\n[TABLE_ROW_END]")
                extracted_elements.append("[TABLE_END]")

        return '\n\n'.join(extracted_elements), doc_properties

    except Exception as e:
        logger.error(f"Error extracting text from DOCX input: {e}", exc_info=True)
        # Return empty string and empty dict in case of error to allow partial processing if needed downstream
        # Or re-raise depending on desired strictness
        raise # For now, re-raise to signal failure clearly


def extract_text_from_txt(file_path_or_bytes: Any, encoding: str = 'utf-8') -> str:
    try:
        if isinstance(file_path_or_bytes, str):
            if not os.path.exists(file_path_or_bytes):
                raise FileNotFoundError(f"TXT file not found at path: {file_path_or_bytes}")
            with open(file_path_or_bytes, 'r', encoding=encoding) as f:
                return f.read()
        elif isinstance(file_path_or_bytes, bytes):
            return file_path_or_bytes.decode(encoding)
        else:
            raise ValueError("Input for TXT extraction must be a file path (str) or bytes.")
    except UnicodeDecodeError as ude:
        logger.error(f"Unicode error for TXT (encoding: {encoding}): {ude}", exc_info=True)
        raise ValueError(f"Encoding error: Could not decode TXT with {encoding}.") from ude
    except Exception as e:
        logger.error(f"Error extracting text from TXT input: {e}", exc_info=True)
        raise

def extract_text_from_html(file_path_or_bytes: Any, encoding: str = 'utf-8') -> str:
    if not BS4_AVAILABLE or not BeautifulSoup:
        raise ImportError("BeautifulSoup4 library is required for HTML processing but not found.")

    html_content = ""
    try:
        if isinstance(file_path_or_bytes, str):
            if not os.path.exists(file_path_or_bytes):
                raise FileNotFoundError(f"HTML file not found at path: {file_path_or_bytes}")
            with open(file_path_or_bytes, 'r', encoding=encoding) as f:
                html_content = f.read()
        elif isinstance(file_path_or_bytes, bytes):
            html_content = file_path_or_bytes.decode(encoding)
        else:
            raise ValueError("Input for HTML extraction must be a file path (str) or bytes.")

        soup = BeautifulSoup(html_content, 'lxml') # Using lxml parser

        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text, attempting to preserve some structure with newlines
        # Different strategies can be used here depending on desired output.
        # .get_text(separator='\n', strip=True) is a common approach.
        text = soup.get_text(separator='\n', strip=True)

        # Optional: Further clean-up, e.g., remove excessive blank lines
        lines = [line for line in text.splitlines() if line.strip()]
        return '\n'.join(lines)

    except UnicodeDecodeError as ude:
        logger.error(f"Unicode error for HTML (encoding: {encoding}): {ude}", exc_info=True)
        raise ValueError(f"Encoding error: Could not decode HTML with {encoding}.") from ude
    except Exception as e:
        logger.error(f"Error extracting text from HTML input: {e}", exc_info=True)
        # If lxml is not installed, BeautifulSoup might raise FeatureNotFound.
        if "FeatureNotFound" in str(type(e)): # Basic check for missing parser
             logger.error("lxml parser not found. Please install it (pip install lxml). Falling back to html.parser for this attempt.")
             try:
                 soup = BeautifulSoup(html_content, 'html.parser')
                 for script_or_style in soup(["script", "style"]):
                     script_or_style.decompose()
                 text = soup.get_text(separator='\n', strip=True)
                 lines = [line for line in text.splitlines() if line.strip()]
                 return '\n'.join(lines)
             except Exception as e_fallback:
                 logger.error(f"Error extracting text from HTML with html.parser fallback: {e_fallback}", exc_info=True)
                 raise e_fallback # Re-raise the error from fallback
        raise # Re-raise original error if not FeatureNotFound or if fallback also fails

# --- Text Chunking Utility ---
def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    if not text: return []
    chunks = []; start = 0; text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= text_len: break
        start += (chunk_size - chunk_overlap)
        if start >= text_len: break
    return chunks

# --- Main Orchestration Function ---
async def process_document_and_store(
    user_id: str,
    file_path_or_bytes: Any, # Can be path (str) or content (bytes)
    document_id: str,
    source_uri: str, # Original URI of the document
    original_doc_type: str, # Original type, e.g., "gdoc", "pdf_upload", "gdrive_docx"
    processing_mime_type: str, # MIME type of file_path_or_bytes (e.g., "application/pdf", "text/plain")
    title: Optional[str] = None,
    doc_metadata_json: Optional[str] = None,
    openai_api_key_param: Optional[str] = None
) -> Dict[str, Any]:
    """
    Orchestrates document processing: text extraction based on MIME type, chunking,
    embedding, and storage in LanceDB.
    """
    logger.info(f"Processing document: id={document_id}, user={user_id}, source_uri={source_uri}, original_type='{original_doc_type}', processing_mime='{processing_mime_type}'")

    if not EMBEDDING_FUNCTION_AVAILABLE or not get_text_embedding_openai:
        return {"status": "error", "message": "Embedding utility (note_utils/get_text_embedding_openai) not available.", "code": "EMBEDDING_SERVICE_UNAVAILABLE"}
    if not lancedb_handler:
         return {"status": "error", "message": "LanceDB handler not available.", "code": "LANCEDB_HANDLER_UNAVAILABLE"}

    extracted_text: str = ""
    additional_doc_props: Optional[Dict[str, Any]] = None
    try:
        if processing_mime_type == "application/pdf":
            extracted_text = extract_text_from_pdf(file_path_or_bytes)
        elif processing_mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or \
             original_doc_type.endswith("docx"): # Broader check for docx
            extracted_text, additional_doc_props = extract_text_from_docx(file_path_or_bytes)
        elif processing_mime_type == "text/plain" or original_doc_type.endswith("txt"):
            extracted_text = extract_text_from_txt(file_path_or_bytes)
        elif processing_mime_type == "text/html" or \
             original_doc_type.endswith("html") or \
             original_doc_type.endswith("htm") or \
             original_doc_type == "webpage": # Common identifiers for HTML
            extracted_text = extract_text_from_html(file_path_or_bytes)
            # Ensure original_doc_type for storage is consistent, e.g., 'html'
            if original_doc_type != "html": # If it was like 'gdrive_html' or 'webpage'
                logger.info(f"Normalizing original_doc_type from '{original_doc_type}' to 'html' for storage for doc_id {document_id}")
                original_doc_type = "html"
        else:
            logger.error(f"Unsupported processing_mime_type: {processing_mime_type} for document {document_id}")
            # Update document metadata in LanceDB to 'failed_unsupported_type'
            # This requires doc_meta to be created first, then updated.
            # For now, just return error. A more robust flow would pre-register the doc then update status.
            return {"status": "error", "message": f"Unsupported document type for processing: {processing_mime_type}", "code": "UNSUPPORTED_PROCESSING_TYPE"}
    except Exception as extraction_error:
        logger.error(f"Text extraction failed for document {document_id} (type: {processing_mime_type}): {extraction_error}", exc_info=True)
        # TODO: Update document status in LanceDB to "failed_extraction"
        return {"status": "error", "message": f"Text extraction failed: {str(extraction_error)}", "code": "TEXT_EXTRACTION_FAILED"}

    # Prepare combined metadata
    final_metadata_dict: Dict[str, Any] = {}
    if doc_metadata_json: # If input metadata_json string exists
        try:
            final_metadata_dict = json.loads(doc_metadata_json)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse input doc_metadata_json for doc_id {document_id}. Starting with empty metadata dict.")
            final_metadata_dict = {}

    if additional_doc_props: # If properties were extracted (e.g., from DOCX)
        final_metadata_dict.update(additional_doc_props) # Merge/overwrite with new props

    final_metadata_json_str: Optional[str] = None
    if final_metadata_dict:
        final_metadata_json_str = json.dumps(final_metadata_dict)


    if not extracted_text.strip():
        logger.warning(f"No text extracted from document: {source_uri} (ID: {document_id})")
        doc_meta_to_store = {
            "doc_id": document_id, "user_id": user_id, "source_uri": source_uri,
            "doc_type": original_doc_type, "title": title,
            "metadata_json": final_metadata_json_str, # Use combined and serialized metadata
            "ingested_at": datetime.now(timezone.utc).isoformat(), # Store as ISO string
            "processing_status": "failed_empty_content", "error_message": "No text content extracted."
        }
        db_conn = await lancedb_handler.get_lancedb_connection()
        if db_conn:
            await lancedb_handler.create_generic_document_tables_if_not_exist(db_conn)
            await lancedb_handler.add_processed_document(db_conn, doc_meta_to_store, []) # Store metadata even if no chunks
        return {"status": "warning", "message": "No text extracted from document, only metadata stored.", "code": "PDF_PROCESSING_EMPTY", "data": {"doc_id": document_id, "num_chunks_stored": 0}}

    text_chunks = chunk_text(extracted_text)
    logger.info(f"Extracted {len(extracted_text)} chars, split into {len(text_chunks)} chunks for doc_id: {document_id}")

    chunks_with_embeddings_data = []
    for i, chunk_text_content in enumerate(text_chunks):
        if not chunk_text_content.strip(): continue
        embedding_resp = get_text_embedding_openai(text_to_embed=chunk_text_content, openai_api_key_param=openai_api_key_param)
        if embedding_resp["status"] == "success":
            chunks_with_embeddings_data.append({
                "doc_id": document_id, # Ensure doc_id is part of the chunk data
                "user_id": user_id,   # Ensure user_id is part of the chunk data
                "parent_doc_type": original_doc_type, # Add parent_doc_type
                "chunk_sequence": i,
                "text_content": chunk_text_content,
                "embedding": embedding_resp["data"], # Ensure key is 'embedding'
                "metadata_json": None,
                "char_count": len(chunk_text_content)
            })
        else:
            logger.warning(f"Embedding failed for chunk {i} of doc_id {document_id}: {embedding_resp.get('message')}")

    if not chunks_with_embeddings_data:
        doc_meta_err_embed = {
            "doc_id": document_id, "user_id": user_id, "source_uri": source_uri,
            "doc_type": original_doc_type, "title": title,
            "metadata_json": final_metadata_json_str, # Use combined and serialized metadata
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "processing_status": "failed_embedding", "error_message": "No chunks could be embedded."
        }
        db_conn = await lancedb_handler.get_lancedb_connection()
        if db_conn:
            await lancedb_handler.create_generic_document_tables_if_not_exist(db_conn)
            await lancedb_handler.add_processed_document(db_conn, doc_meta_err_embed, [])
        return {"status": "error", "message": "No chunks could be embedded for the document.", "code": "EMBEDDING_FAILURE_ALL_CHUNKS"}

    doc_meta_to_store = {
        "doc_id": document_id, "user_id": user_id, "source_uri": source_uri,
        "doc_type": original_doc_type, "title": title,
        "metadata_json": final_metadata_json_str, # Use combined and serialized metadata
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "processing_status": "completed",
    }

    db_conn = await lancedb_handler.get_lancedb_connection()
    if not db_conn:
        return {"status": "error", "message": "Failed to connect to LanceDB.", "code": "LANCEDB_CONNECTION_ERROR"}

    await lancedb_handler.create_generic_document_tables_if_not_exist(db_conn)
    lancedb_storage_result = await lancedb_handler.add_processed_document(
        db_conn=db_conn, doc_meta=doc_meta_to_store, chunks_with_embeddings=chunks_with_embeddings_data
    )

    # Final return based on lancedb_storage_result and potential Meili failure
    if lancedb_storage_result["status"] == "success":
        logger.info(f"Successfully processed and stored document: {source_uri}, doc_id: {document_id} (LanceDB & Meilisearch)")
        return {"status": "success", "data": {"doc_id": document_id, "num_chunks_stored": len(chunks_with_embeddings_data)}}
    else: # LanceDB failed
        logger.error(f"Failed to store processed document {document_id} in LanceDB: {lancedb_storage_result.get('message')}")
        return {"status": "error", "message": f"LanceDB storage failed: {lancedb_storage_result.get('message')}", "code": lancedb_storage_result.get("code", "LANCEDB_STORAGE_ERROR")}
