import asyncio
from datetime import datetime
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid

try:
    from backend.core.lancedb_handler import LanceDBHandler
except ImportError:
    # Fallback for when imported from main API context
    from core.lancedb_handler import LanceDBHandler

# BYOK Integration
try:
    from backend.core.byok_endpoints import get_byok_manager

    BYOK_AVAILABLE = True
except ImportError:
    BYOK_AVAILABLE = False
    get_byok_manager = None

logger = logging.getLogger(__name__)


class PDFMemoryIntegration:
    """
    Integration service for storing processed PDF content in Atom's memory system.
    Handles vector storage, metadata management, and semantic search for PDF documents.
    """

    def __init__(
        self, lancedb_handler: Optional[LanceDBHandler] = None, use_byok: bool = True
    ):
        """
        Initialize PDF memory integration.

        Args:
            lancedb_handler: LanceDB handler for vector storage
            use_byok: Whether to use BYOK system for AI provider management
        """
        self.lancedb_handler = lancedb_handler
        self.table_name = "pdf_documents"
        self.use_byok = use_byok and BYOK_AVAILABLE

        # Initialize BYOK manager if available
        self.byok_manager = None
        if self.use_byok:
            try:
                self.byok_manager = get_byok_manager()
                logger.info("BYOK system initialized for PDF memory integration")
            except Exception as e:
                logger.warning(f"Failed to initialize BYOK system: {e}")
                self.use_byok = False

        # Initialize table if LanceDB is available
        if self.lancedb_handler:
            self._initialize_memory_tables()

        # Initialize SQLite fallback storage
        self._init_simple_db()

    def _initialize_memory_tables(self):
        """Initialize required tables in LanceDB for PDF storage."""
        try:
            if self.table_name not in self.lancedb_handler.list_tables():
                schema = {
                    "doc_id": "string",
                    "user_id": "string",
                    "filename": "string",
                    "file_size": "int64",
                    "page_count": "int64",
                    "total_chars": "int64",
                    "processing_method": "string",
                    "pdf_type": "string",  # searchable, scanned, mixed
                    "extracted_text": "string",
                    "embedding": "vector(768)",
                    "metadata": "string",  # JSON string
                    "created_at": "timestamp",
                    "updated_at": "timestamp",
                    "source_uri": "string",
                    "tags": "list<string>",
                }
                self.lancedb_handler.create_table(self.table_name, schema)
                logger.info(f"Created PDF memory table: {self.table_name}")
            else:
                logger.info(f"PDF memory table already exists: {self.table_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize PDF memory tables: {e}")

    def _init_simple_db(self):
        """Initialize SQLite database for fallback storage"""
        try:
            # Place database in backend/data directory
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._simple_db_path = os.path.join(backend_dir, "data", "pdf_simple.db")
            os.makedirs(os.path.dirname(self._simple_db_path), exist_ok=True)

            conn = sqlite3.connect(self._simple_db_path)
            cursor = conn.cursor()

            # Main table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pdf_documents (
                    doc_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT,
                    page_count INTEGER,
                    total_chars INTEGER,
                    pdf_type TEXT,
                    processing_method TEXT,
                    extracted_text TEXT,
                    created_at TEXT,
                    source_uri TEXT
                )
            """)

            # FTS5 virtual table for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS pdf_documents_fts
                USING fts5(doc_id, extracted_text, content='pdf_documents', content_rowid='rowid')
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS pdf_documents_ai
                AFTER INSERT ON pdf_documents BEGIN
                    INSERT INTO pdf_documents_fts(rowid, doc_id, extracted_text)
                    VALUES (new.rowid, new.doc_id, new.extracted_text);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS pdf_documents_ad
                AFTER DELETE ON pdf_documents BEGIN
                    INSERT INTO pdf_documents_fts(pdf_documents_fts, doc_id, extracted_text)
                    VALUES ('delete', old.doc_id, old.extracted_text);
                END
            """)

            conn.commit()
            conn.close()
            logger.info(f"SQLite fallback storage initialized at {self._simple_db_path}")
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite fallback storage: {e}")
            self._simple_db_path = None

    async def store_processed_pdf(
        self,
        user_id: str,
        processing_result: Dict[str, Any],
        source_uri: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store processed PDF content in memory system.

        Args:
            user_id: User identifier
            processing_result: Output from PDF processing service
            source_uri: Source URI of the PDF (file path, URL, etc.)
            tags: Optional tags for categorization
            metadata: Additional metadata

        Returns:
            Storage result with success status and document info
        """

        # Track BYOK usage if available
        if self.use_byok and self.byok_manager:
            try:
                # Extract processing method information
                processing_summary = processing_result.get("processing_summary", {})
                best_method = processing_summary.get("best_method", "")
                used_ocr = processing_summary.get("used_ocr", False)

                # Map processing method to BYOK provider
                provider_id = self._map_processing_method_to_provider(
                    best_method, used_ocr
                )

                if provider_id:
                    # Estimate tokens used for embedding generation
                    total_chars = processing_summary.get("total_characters", 0)
                    estimated_tokens = max(total_chars // 4, 100)  # Rough estimate

                    # Track usage for embedding generation
                    self.byok_manager.track_usage(
                        provider_id=provider_id,
                        success=True,
                        tokens_used=estimated_tokens,
                    )

                    logger.debug(
                        f"Tracked BYOK usage for embedding: {provider_id}, {estimated_tokens} tokens"
                    )
            except Exception as e:
                logger.warning(f"Failed to track BYOK usage during storage: {e}")
        try:
            doc_id = str(uuid.uuid4())
            now = datetime.now()

            # Extract data from processing result
            extracted_content = processing_result.get("extracted_content", {})
            processing_summary = processing_result.get("processing_summary", {})
            file_metadata = processing_result.get("file_metadata", {})

            # Prepare document data
            document_data = {
                "doc_id": doc_id,
                "user_id": user_id,
                "filename": file_metadata.get("filename", "unknown.pdf"),
                "file_size": file_metadata.get("size_bytes", 0),
                "page_count": processing_summary.get("total_pages", 0),
                "total_chars": processing_summary.get("total_characters", 0),
                "processing_method": processing_summary.get("best_method", "unknown"),
                "pdf_type": self._determine_pdf_type(processing_result),
                "extracted_text": extracted_content.get("text", ""),
                "metadata": self._serialize_metadata(metadata or {}),
                "created_at": now,
                "updated_at": now,
                "source_uri": source_uri or "",
                "tags": tags or [],
            }

            # Store in LanceDB if available
            if self.lancedb_handler:
                await self._store_in_lancedb(document_data)

            # Also store in simpler format for quick access
            simple_storage_result = await self._store_simple_format(document_data)

            logger.info(f"Stored PDF document {doc_id} for user {user_id}")

            return {
                "success": True,
                "doc_id": doc_id,
                "storage_methods": ["simple_format"]
                + (["lancedb"] if self.lancedb_handler else []),
                "document_info": {
                    "filename": document_data["filename"],
                    "pages": document_data["page_count"],
                    "characters": document_data["total_chars"],
                    "pdf_type": document_data["pdf_type"],
                },
            }

        except Exception as e:
            logger.error(f"Failed to store processed PDF: {e}")
            return {"success": False, "error": str(e), "doc_id": None}

    async def _store_in_lancedb(self, document_data: Dict[str, Any]):
        """Store document in LanceDB with embeddings."""
        try:
            # Generate embedding for the text content
            text_for_embedding = document_data["extracted_text"]
            if len(text_for_embedding) > 1000:
                text_for_embedding = text_for_embedding[:1000]  # Limit for embedding

            embedding = self.lancedb_handler.embed_text(text_for_embedding)

            # Prepare data for LanceDB
            lancedb_data = {
                "doc_id": document_data["doc_id"],
                "user_id": document_data["user_id"],
                "filename": document_data["filename"],
                "file_size": document_data["file_size"],
                "page_count": document_data["page_count"],
                "total_chars": document_data["total_chars"],
                "processing_method": document_data["processing_method"],
                "pdf_type": document_data["pdf_type"],
                "extracted_text": document_data["extracted_text"],
                "embedding": embedding,
                "metadata": document_data["metadata"],
                "created_at": document_data["created_at"],
                "updated_at": document_data["updated_at"],
                "source_uri": document_data["source_uri"],
                "tags": document_data["tags"],
            }

            # Add to LanceDB table
            table = self.lancedb_handler.get_table(self.table_name)
            table.add([lancedb_data])

            logger.debug(f"Stored document {document_data['doc_id']} in LanceDB")

        except Exception as e:
            logger.error(f"Failed to store in LanceDB: {e}")
            raise

    async def _store_simple_format(
        self, document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store document in SQLite fallback storage"""
        if not self._simple_db_path:
            logger.debug("SQLite fallback not available, skipping simple storage")
            return {"success": False, "error": "SQLite fallback not initialized"}

        try:
            conn = sqlite3.connect(self._simple_db_path)
            cursor = conn.cursor()

            # Get extracted text from document_data
            extracted_text = document_data.get("extracted_text", "")

            cursor.execute("""
                INSERT OR REPLACE INTO pdf_documents
                (doc_id, user_id, filename, page_count, total_chars, pdf_type,
                 processing_method, extracted_text, created_at, source_uri)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                document_data["doc_id"],
                document_data["user_id"],
                document_data.get("filename", ""),
                document_data.get("page_count", 0),
                document_data.get("total_chars", 0),
                document_data.get("pdf_type", "unknown"),
                document_data.get("processing_method", "unknown"),
                extracted_text[:10000],  # Limit for performance
                document_data.get("created_at", datetime.now()).isoformat(),
                document_data.get("source_uri", "")
            ))

            conn.commit()
            conn.close()

            logger.debug(f"Stored simple format for {document_data['doc_id']}")
            return {"success": True, "storage_type": "sqlite"}

        except Exception as e:
            logger.error(f"Failed to store in simple format: {e}")
            return {"success": False, "error": str(e)}

    def _determine_pdf_type(self, processing_result: Dict[str, Any]) -> str:
        """Determine PDF type based on processing results."""
        processing_summary = processing_result.get("processing_summary", {})

        if processing_summary.get("used_ocr", False):
            return "scanned"
        else:
            text_ratio = processing_result.get("extracted_content", {}).get(
                "text_ratio", 0
            )
            if text_ratio > 0.7:
                return "searchable"
            elif text_ratio > 0.3:
                return "mixed"
            else:
                return "scanned"

    def _serialize_metadata(self, metadata: Dict[str, Any]) -> str:
        """Serialize metadata to JSON string."""
        import json

        try:
            return json.dumps(metadata)
        except Exception as e:
            logger.warning(f"Failed to serialize metadata: {e}")
            return "{}"

    async def search_pdfs(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search PDF documents using semantic search.

        Args:
            user_id: User identifier
            query: Search query text
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0.0-1.0)
            filters: Optional filters for search

        Returns:
            List of search results with similarity scores
        """

        # Track BYOK usage for search if available
        if self.use_byok and self.byok_manager:
            try:
                # Estimate tokens for query embedding
                estimated_tokens = max(len(query) // 4, 50)  # Rough estimate

                # Use BYOK to get optimal provider for search
                try:
                    optimal_provider = self.byok_manager.get_optimal_provider(
                        "analysis"
                    )
                    if optimal_provider:
                        self.byok_manager.track_usage(
                            provider_id=optimal_provider,
                            success=True,
                            tokens_used=estimated_tokens,
                        )
                        logger.debug(
                            f"Tracked BYOK search usage: {optimal_provider}, {estimated_tokens} tokens"
                        )
                except Exception as e:
                    logger.debug(f"BYOK provider optimization for search failed: {e}")
            except Exception as e:
                logger.warning(f"Failed to track BYOK usage during search: {e}")
        try:
            results = []

            # Search in LanceDB if available
            if self.lancedb_handler:
                lancedb_results = await self._search_in_lancedb(
                    user_id, query, limit, similarity_threshold, filters
                )
                results.extend(lancedb_results)

            # Fallback to simple search if no LanceDB results
            if not results:
                simple_results = await self._simple_search(
                    user_id, query, limit, filters
                )
                results.extend(simple_results)

            return results

        except Exception as e:
            logger.error(f"PDF search failed: {e}")
            return []

    async def _search_in_lancedb(
        self,
        user_id: str,
        query: str,
        limit: int,
        similarity_threshold: float,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Search PDFs using LanceDB semantic search."""
        try:
            table = self.lancedb_handler.get_table(self.table_name)

            # Build filter expression
            filter_expr = f"user_id = '{user_id}'"
            if filters:
                if filters.get("pdf_type"):
                    filter_expr += f" AND pdf_type = '{filters['pdf_type']}'"
                if filters.get("tags"):
                    # This is simplified - in production would need proper array handling
                    tag_filter = " OR ".join(
                        [f"'{tag}' IN tags" for tag in filters["tags"]]
                    )
                    filter_expr += f" AND ({tag_filter})"

            # Perform semantic search
            search_results = self.lancedb_handler.search(
                table=table,
                query_text=query,
                limit=limit,
                filter_expr=filter_expr,
                similarity_threshold=similarity_threshold,
            )

            # Format results
            formatted_results = []
            for result in search_results:
                formatted_results.append(
                    {
                        "doc_id": result.get("doc_id"),
                        "filename": result.get("filename"),
                        "similarity_score": result.get("_distance", 0),
                        "page_count": result.get("page_count", 0),
                        "total_chars": result.get("total_chars", 0),
                        "pdf_type": result.get("pdf_type"),
                        "excerpt": self._get_text_excerpt(
                            result.get("extracted_text", ""), query
                        ),
                        "created_at": result.get("created_at"),
                        "source_uri": result.get("source_uri"),
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"LanceDB search failed: {e}")
            return []

    async def _simple_search(
        self, user_id: str, query: str, limit: int, filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Full-text search using SQLite FTS5"""
        if not self._simple_db_path:
            logger.debug("SQLite fallback not available, skipping simple search")
            return []

        try:
            conn = sqlite3.connect(self._simple_db_path)
            cursor = conn.cursor()

            # Build FTS5 search query - escape quotes
            fts_query = query.replace('"', '""')

            # Apply filters if provided
            filter_clause = ""
            filter_params = [user_id, fts_query]

            if filters:
                if "pdf_type" in filters:
                    filter_clause += " AND pdf_type = ?"
                    filter_params.append(filters["pdf_type"])
                if "processing_method" in filters:
                    filter_clause += " AND processing_method = ?"
                    filter_params.append(filters["processing_method"])

            filter_params.append(limit)

            sql = f"""
                SELECT d.doc_id, d.filename, d.page_count, d.total_chars,
                       d.pdf_type, d.extracted_text, d.created_at, d.source_uri,
                       bm25(pdf_documents_fts) as rank
                FROM pdf_documents d
                JOIN pdf_documents_fts f ON d.rowid = f.rowid
                WHERE d.user_id = ? AND pdf_documents_fts MATCH ?{filter_clause}
                ORDER BY rank
                LIMIT ?
            """

            cursor.execute(sql, filter_params)
            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                results.append({
                    "doc_id": row[0],
                    "filename": row[1],
                    "page_count": row[2],
                    "total_chars": row[3],
                    "pdf_type": row[4],
                    "excerpt": self._get_text_excerpt(row[5], query),
                    "similarity_score": row[8],  # BM25 rank (lower is better)
                    "created_at": row[6],
                    "source_uri": row[7]
                })

            logger.info(f"Simple search found {len(results)} results for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Simple search failed: {e}")
            return []

    def _get_text_excerpt(
        self, text: str, query: str, excerpt_length: int = 200
    ) -> str:
        """Get relevant excerpt from text containing query terms."""
        if not text or not query:
            return text[:excerpt_length] + "..." if len(text) > excerpt_length else text

        # Simple implementation - find first occurrence of any query word
        query_words = query.lower().split()
        text_lower = text.lower()

        for word in query_words:
            if len(word) > 3:  # Only consider words longer than 3 characters
                pos = text_lower.find(word)
                if pos != -1:
                    start = max(0, pos - 50)
                    end = min(len(text), start + excerpt_length)
                    excerpt = text[start:end]
                    if start > 0:
                        excerpt = "..." + excerpt
                    if end < len(text):
                        excerpt = excerpt + "..."
                    return excerpt

        # Fallback to beginning of text
        return text[:excerpt_length] + "..." if len(text) > excerpt_length else text

    async def get_document(self, user_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific PDF document.

        Args:
            user_id: User identifier
            doc_id: Document ID

        Returns:
            Document data or None if not found
        """
        try:
            # Try LanceDB first
            if self.lancedb_handler:
                table = self.lancedb_handler.get_table(self.table_name)
                result = (
                    table.search()
                    .where(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
                    .to_list()
                )
                if result:
                    return self._format_document_result(result[0])

            # Fallback to simple storage
            simple_result = await self._get_simple_document(user_id, doc_id)
            if simple_result:
                return simple_result

            return None

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def _get_simple_document(
        self, user_id: str, doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get document from SQLite storage"""
        if not self._simple_db_path:
            return None

        try:
            conn = sqlite3.connect(self._simple_db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT doc_id, user_id, filename, page_count, total_chars,
                       pdf_type, processing_method, extracted_text, created_at, source_uri
                FROM pdf_documents
                WHERE doc_id = ? AND user_id = ?
            """, (doc_id, user_id))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "doc_id": row[0],
                    "user_id": row[1],
                    "filename": row[2],
                    "page_count": row[3],
                    "total_chars": row[4],
                    "pdf_type": row[5],
                    "processing_method": row[6],
                    "extracted_text": row[7],
                    "created_at": row[8],
                    "source_uri": row[9]
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get simple document: {e}")
            return None

    def _format_document_result(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format document data for API response."""
        return {
            "doc_id": document_data.get("doc_id"),
            "filename": document_data.get("filename"),
            "page_count": document_data.get("page_count", 0),
            "total_chars": document_data.get("total_chars", 0),
            "pdf_type": document_data.get("pdf_type"),
            "processing_method": document_data.get("processing_method"),
            "extracted_text": document_data.get("extracted_text", ""),
            "source_uri": document_data.get("source_uri", ""),
            "tags": document_data.get("tags", []),
            "created_at": document_data.get("created_at"),
            "file_size": document_data.get("file_size", 0),
            "metadata": self._parse_metadata(document_data.get("metadata", "{}")),
        }

    def _parse_metadata(self, metadata_str: str) -> Dict[str, Any]:
        """Parse metadata from JSON string."""
        import json

        try:
            return json.loads(metadata_str)
        except Exception:
            return {}

    async def delete_document(self, user_id: str, doc_id: str) -> Dict[str, Any]:
        """
        Delete a PDF document from memory.

        Args:
            user_id: User identifier
            doc_id: Document ID

        Returns:
            Deletion result
        """
        try:
            deleted_from = []

            # Delete from LanceDB
            if self.lancedb_handler:
                try:
                    table = self.lancedb_handler.get_table(self.table_name)
                    table.delete(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
                    deleted_from.append("lancedb")
                except Exception as e:
                    logger.warning(f"Failed to delete from LanceDB: {e}")

            # Delete from simple storage
            simple_delete_result = await self._delete_simple_document(user_id, doc_id)
            if simple_delete_result.get("success"):
                deleted_from.append("simple_storage")

            return {
                "success": True,
                "doc_id": doc_id,
                "deleted_from": deleted_from,
                "message": f"Document {doc_id} deleted from {len(deleted_from)} storage systems",
            }

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return {"success": False, "error": str(e), "doc_id": doc_id}

    async def _delete_simple_document(
        self, user_id: str, doc_id: str
    ) -> Dict[str, Any]:
        """Delete document from SQLite storage"""
        if not self._simple_db_path:
            return {"success": False, "error": "SQLite fallback not initialized"}

        try:
            conn = sqlite3.connect(self._simple_db_path)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM pdf_documents
                WHERE doc_id = ? AND user_id = ?
            """, (doc_id, user_id))

            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if deleted:
                logger.info(f"Deleted document {doc_id} from SQLite storage")

            return {"success": True, "deleted": deleted}

        except Exception as e:
            logger.error(f"Failed to delete simple document: {e}")
            return {"success": False, "error": str(e)}

    async def get_user_document_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics for user's PDF documents.

        Args:
            user_id: User identifier

        Returns:
            Document statistics
        """
        try:
            stats = {
                "total_documents": 0,
                "total_pages": 0,
                "total_characters": 0,
                "pdf_types": {},
                "storage_size_bytes": 0,
                "by_month": {},
            }

            # Get stats from LanceDB if available
            if self.lancedb_handler:
                table = self.lancedb_handler.get_table(self.table_name)
                user_docs = table.search().where(f"user_id = '{user_id}'").to_list()

                stats["total_documents"] = len(user_docs)
                for doc in user_docs:
                    stats["total_pages"] += doc.get("page_count", 0)
                    stats["total_characters"] += doc.get("total_chars", 0)
                    stats["storage_size_bytes"] += doc.get("file_size", 0)

                    # Count by PDF type
                    pdf_type = doc.get("pdf_type", "unknown")
                    stats["pdf_types"][pdf_type] = (
                        stats["pdf_types"].get(pdf_type, 0) + 1
                    )

            return stats

        except Exception as e:
            logger.error(f"Failed to get user document stats: {e}")
            return {
                "total_documents": 0,
                "total_pages": 0,
                "total_characters": 0,
                "pdf_types": {},
                "storage_size_bytes": 0,
                "by_month": {},
                "error": str(e),
            }

    def _map_processing_method_to_provider(
        self, method: str, used_ocr: bool
    ) -> Optional[str]:
        """Map PDF processing method to BYOK provider ID."""
        if not method:
            return None

        method_to_provider = {
            "openai_vision": "openai",
            "tesseract": "openai",  # Tesseract doesn't have BYOK provider, map to default
            "easyocr": "openai",  # EasyOCR doesn't have BYOK provider, map to default
            "basic_pdf": "openai",  # Basic extraction uses embeddings
        }

        provider = method_to_provider.get(method)

        # If OCR was used but method is basic_pdf, still track usage
        if used_ocr and provider is None:
            provider = "openai"  # Default to OpenAI for OCR usage

        return provider

    def get_byok_status(self) -> Dict[str, Any]:
        """Get BYOK integration status."""
        return {
            "byok_integrated": self.use_byok,
            "byok_manager_available": self.byok_manager is not None,
            "tracking_enabled": self.use_byok and self.byok_manager is not None,
        }
