"""
Enhanced Document Service with LanceDB Integration for Atom Personal Assistant

This service provides unified document management with full integration into the
LanceDB-based memory system for efficient recall and semantic search.
"""

import logging
import os
import tempfile
import uuid
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Document type enumeration"""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    PPTX = "pptx"
    XLSX = "xlsx"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    UNKNOWN = "unknown"


class DocumentStatus(Enum):
    """Document processing status enumeration"""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentChunkingStrategy(Enum):
    """Document chunking strategy enumeration"""

    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


class EnhancedDocumentService:
    """Enhanced service for document management with LanceDB integration"""

    def __init__(self, db_pool=None, lancedb_connection=None):
        self.db_pool = db_pool
        self.lancedb_conn = lancedb_connection
        self.processors = self._initialize_processors()
        self.chunk_size = 1000  # characters per chunk
        self.chunk_overlap = 200  # characters overlap between chunks

    async def process_and_store_document(
        self,
        user_id: str,
        file_data: bytes,
        filename: str,
        source_uri: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process document and store in LanceDB memory system

        Args:
            user_id: User identifier
            file_data: Document file bytes
            filename: Original filename
            source_uri: Source URI for tracking
            metadata: Additional metadata

        Returns:
            Processing results with LanceDB storage info
        """
        try:
            # Generate unique document ID
            doc_id = f"doc_{uuid.uuid4().hex}"

            # Determine document type
            doc_type = self._detect_document_type(filename)

            # Create document record
            document = {
                "doc_id": doc_id,
                "user_id": user_id,
                "filename": filename,
                "file_size": len(file_data),
                "doc_type": doc_type.value,
                "source_uri": source_uri or f"upload://{filename}",
                "status": DocumentStatus.UPLOADED.value,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # Store file temporarily for processing
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{filename}"
            ) as temp_file:
                temp_file.write(file_data)
                temp_path = temp_file.name

            try:
                # Extract text content
                (
                    extracted_text,
                    extraction_metadata,
                ) = await self._extract_document_content(temp_path, doc_type)

                document["extracted_text"] = extracted_text
                document["metadata"].update(extraction_metadata)
                document["status"] = DocumentStatus.PROCESSING.value

                # Chunk document for embedding
                chunks = await self._chunk_document(extracted_text, doc_id, user_id)
                document["total_chunks"] = len(chunks)

                # Generate embeddings and store in LanceDB
                if self.lancedb_conn:
                    storage_result = await self._store_in_lancedb(document, chunks)
                    document.update(storage_result)

                # Update status to processed
                document["status"] = DocumentStatus.PROCESSED.value
                document["updated_at"] = datetime.now().isoformat()

                # Save to database if available
                if self.db_pool:
                    await self._save_document_to_db(document)

                logger.info(
                    f"Successfully processed and stored document '{filename}' for user {user_id}"
                )
                return document

            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Failed to process and store document: {e}")
            # Update status to failed
            document["status"] = DocumentStatus.FAILED.value
            document["error_message"] = str(e)
            document["updated_at"] = datetime.now().isoformat()
            raise

    async def search_documents(
        self,
        user_id: str,
        query: str,
        doc_type: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search documents using semantic search in LanceDB

        Args:
            user_id: User identifier
            query: Search query
            doc_type: Filter by document type
            limit: Maximum results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching documents with relevance scores
        """
        try:
            if not self.lancedb_conn:
                logger.warning("LanceDB not available, falling back to text search")
                return await self._fallback_text_search(user_id, query, doc_type, limit)

            # Generate embedding for query
            query_embedding = await self._generate_embedding(query)
            if not query_embedding:
                return await self._fallback_text_search(user_id, query, doc_type, limit)

            # Search in LanceDB
            table = await self._get_lancedb_table("document_chunks")
            if not table:
                return await self._fallback_text_search(user_id, query, doc_type, limit)

            # Perform vector search
            results = table.search(query_embedding).where(f"user_id = '{user_id}'")

            if doc_type:
                results = results.where(f"doc_type = '{doc_type}'")

            # Execute search and get results
            search_results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: results.limit(
                    limit * 3
                ).to_list(),  # Get more for deduplication
            )

            # Group by document and calculate relevance
            document_scores = {}
            for result in search_results:
                doc_id = result.get("doc_id")
                score = result.get("_distance", 0)

                # Convert distance to similarity score (assuming cosine distance)
                similarity = (
                    1 - score if score <= 2 else 0
                )  # Cosine distance range: 0-2

                if similarity >= similarity_threshold:
                    if doc_id not in document_scores:
                        document_scores[doc_id] = {
                            "doc_id": doc_id,
                            "similarity_score": similarity,
                            "best_chunk": result,
                            "matching_chunks": 1,
                        }
                    else:
                        document_scores[doc_id]["similarity_score"] = max(
                            document_scores[doc_id]["similarity_score"], similarity
                        )
                        document_scores[doc_id]["matching_chunks"] += 1

            # Get full document details for top results
            results_list = sorted(
                document_scores.values(),
                key=lambda x: x["similarity_score"],
                reverse=True,
            )[:limit]

            # Enhance with document metadata
            enhanced_results = []
            for result in results_list:
                doc_details = await self._get_document_by_id(user_id, result["doc_id"])
                if doc_details:
                    result.update(doc_details)
                    enhanced_results.append(result)

            return enhanced_results

        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return await self._fallback_text_search(user_id, query, doc_type, limit)

    async def get_document_chunks(
        self, user_id: str, doc_id: str, chunk_indices: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve specific chunks from a document

        Args:
            user_id: User identifier
            doc_id: Document identifier
            chunk_indices: Specific chunk indices to retrieve (None for all)

        Returns:
            List of document chunks
        """
        try:
            if not self.lancedb_conn:
                return []

            table = await self._get_lancedb_table("document_chunks")
            if not table:
                return []

            query = f"doc_id = '{doc_id}' AND user_id = '{user_id}'"
            if chunk_indices:
                indices_str = ",".join(str(i) for i in chunk_indices)
                query += f" AND chunk_index IN ({indices_str})"

            chunks = await asyncio.get_event_loop().run_in_executor(
                None, lambda: table.search().where(query).to_list()
            )

            return chunks

        except Exception as e:
            logger.error(f"Failed to get document chunks: {e}")
            return []

    async def update_document_embeddings(
        self, user_id: str, doc_id: str
    ) -> Dict[str, Any]:
        """
        Update embeddings for a document (useful when embedding model changes)

        Args:
            user_id: User identifier
            doc_id: Document identifier

        Returns:
            Update results
        """
        try:
            document = await self._get_document_by_id(user_id, doc_id)
            if not document:
                raise ValueError(f"Document {doc_id} not found")

            # Get existing chunks
            chunks = await self.get_document_chunks(user_id, doc_id)
            if not chunks:
                raise ValueError(f"No chunks found for document {doc_id}")

            # Regenerate embeddings
            updated_chunks = []
            for chunk in chunks:
                new_embedding = await self._generate_embedding(
                    chunk.get("chunk_text", "")
                )
                if new_embedding:
                    chunk["vector_embedding"] = new_embedding
                    updated_chunks.append(chunk)

            # Update in LanceDB
            if updated_chunks and self.lancedb_conn:
                table = await self._get_lancedb_table("document_chunks")
                if table:
                    # Delete old chunks
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: table.delete(
                            f"doc_id = '{doc_id}' AND user_id = '{user_id}'"
                        ),
                    )

                    # Insert updated chunks
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: table.add(updated_chunks)
                    )

            return {
                "success": True,
                "doc_id": doc_id,
                "chunks_updated": len(updated_chunks),
                "updated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to update document embeddings: {e}")
            return {"success": False, "error": str(e), "doc_id": doc_id}

    async def get_document_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive document statistics including LanceDB metrics"""
        try:
            base_stats = await self._get_basic_document_stats(user_id)
            lancedb_stats = await self._get_lancedb_document_stats(user_id)

            return {**base_stats, **lancedb_stats}

        except Exception as e:
            logger.error(f"Failed to get document statistics: {e}")
            return {}

    # Internal implementation methods

    async def _extract_document_content(
        self, file_path: str, doc_type: DocumentType
    ) -> Tuple[str, Dict[str, Any]]:
        """Extract text content from document based on type"""
        try:
            # Import document processor functions
            from document_processor import (
                extract_text_from_pdf,
                extract_text_from_docx,
                extract_text_from_txt,
                extract_text_from_html,
            )

            extraction_functions = {
                DocumentType.PDF: extract_text_from_pdf,
                DocumentType.DOCX: extract_text_from_docx,
                DocumentType.TXT: extract_text_from_txt,
                DocumentType.HTML: extract_text_from_html,
            }

            extract_func = extraction_functions.get(doc_type)
            if not extract_func:
                raise ValueError(f"Unsupported document type: {doc_type}")

            # Execute extraction
            if doc_type == DocumentType.DOCX:
                text, metadata = extract_func(file_path)
            else:
                text = extract_func(file_path)
                metadata = {}

            return text, metadata

        except Exception as e:
            logger.error(f"Failed to extract document content: {e}")
            raise

    async def _chunk_document(
        self, text: str, doc_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Chunk document text for embedding"""
        chunks = []

        # Simple fixed-size chunking with overlap
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            # Try to end at sentence boundary
            sentence_endings = [".", "!", "?", "\n\n"]
            for ending in sentence_endings:
                pos = chunk_text.rfind(ending)
                if pos > self.chunk_size // 2:  # Only adjust if reasonable
                    chunk_text = chunk_text[: pos + 1]
                    end = start + len(chunk_text)
                    break

            chunk = {
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "doc_id": doc_id,
                "user_id": user_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text.strip(),
                "start_pos": start,
                "end_pos": end,
                "created_at": datetime.now().isoformat(),
            }

            chunks.append(chunk)
            chunk_index += 1
            start = end - self.chunk_overlap  # Apply overlap

        return chunks

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using available embedding service"""
        try:
            # Try to import embedding function
            from note_utils import get_text_embedding_openai

            if get_text_embedding_openai:
                embedding = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: get_text_embedding_openai(text)
                )
                return embedding
            else:
                logger.warning("Embedding function not available")
                return None

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def _store_in_lancedb(
        self, document: Dict[str, Any], chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Store document and chunks in LanceDB"""
        try:
            # Generate embedding for document metadata
            doc_embedding_text = f"{document.get('filename', '')} {document.get('metadata', {}).get('title', '')}"
            doc_embedding = await self._generate_embedding(doc_embedding_text)

            # Prepare document record for LanceDB
            doc_record = {
                "doc_id": document["doc_id"],
                "user_id": document["user_id"],
                "source_uri": document["source_uri"],
                "doc_type": document["doc_type"],
                "title": document.get("filename", ""),
                "metadata_json": json.dumps(document.get("metadata", {})),
                "ingested_at": document["created_at"],
                "processing_status": document["status"],
                "total_chunks": len(chunks),
                "vector_embedding": doc_embedding or [],
            }

            # Generate embeddings for chunks
            for chunk in chunks:
                chunk_embedding = await self._generate_embedding(chunk["chunk_text"])
                chunk["vector_embedding"] = chunk_embedding or []
                chunk["doc_type"] = document["doc_type"]

            # Store in LanceDB
            doc_table = await self._get_lancedb_table("processed_documents")
            chunk_table = await self._get_lancedb_table("document_chunks")

            if doc_table and chunk_table:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: doc_table.add([doc_record])
                )
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: chunk_table.add(chunks)
                )

            return {
                "lancedb_stored": True,
                "documents_table": "processed_documents",
                "chunks_table": "document_chunks",
                "embedding_dimension": len(doc_embedding) if doc_embedding else 0,
            }

        except Exception as e:
            logger.error(f"Failed to store in LanceDB: {e}")
            return {"lancedb_stored": False, "error": str(e)}

    async def _get_lancedb_table(self, table_name: str):
        """Get LanceDB table, creating if it doesn't exist"""
        if not self.lancedb_conn:
            return None

        try:
            if table_name in self.lancedb_conn.table_names():
                return self.lancedb_conn.open_table(table_name)
            else:
                # Table will be created automatically on first insert
                return self.lancedb_conn.create_table(table_name, data=[])
        except Exception as e:
            logger.error(f"Failed to get LanceDB table {table_name}: {e}")
            return None

    def _detect_document_type(self, filename: str) -> DocumentType:
        """Detect document type from filename"""
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        type_mapping = {
            "pdf": DocumentType.PDF,
            "docx": DocumentType.DOCX,
            "doc": DocumentType.DOCX,
            "txt": DocumentType.TXT,
            "md": DocumentType.MD,
            "html": DocumentType.HTML,
            "htm": DocumentType.HTML,
            "pptx": DocumentType.PPTX,
            "xlsx": DocumentType.XLSX,
            "jpg": DocumentType.IMAGE,
            "jpeg": DocumentType.IMAGE,
            "png": DocumentType.IMAGE,
            "gif": DocumentType.IMAGE,
            "mp3": DocumentType.AUDIO,
            "wav": DocumentType.AUDIO,
            "mp4": DocumentType.VIDEO,
            "avi": DocumentType.VIDEO,
        }

        return type_mapping.get(ext, DocumentType.UNKNOWN)

    async def _get_basic_document_stats(self, user_id: str) -> Dict[str, Any]:
        """Get basic document statistics from database"""
        try:
            documents = await self.get_documents(user_id, limit=1000)
            return {
                "total_documents": len(documents),
                "processed_documents": len(
                    [
                        d
                        for d in documents
                        if d.get("status") == DocumentStatus.PROCESSED.value
                    ]
                ),
                "processing_documents": len(
                    [
                        d
                        for d in documents
                        if d.get("status") == DocumentStatus.PROCESSING.value
                    ]
                ),
                "failed_documents": len(
                    [
                        d
                        for d in documents
                        if d.get("status") == DocumentStatus.FAILED.value
                    ]
                ),
                "total_file_size": sum(d.get("file_size", 0) for d in documents),
                "documents_by_type": self._count_documents_by_type(documents),
            }
        except Exception as e:
            logger.error(f"Failed to get basic document stats: {e}")
            return {}

    async def _get_lancedb_document_stats(self, user_id: str) -> Dict[str, Any]:
        """Get LanceDB-specific document statistics"""
        try:
            if not self.lancedb_conn:
                return {"lancedb_available": False}

            doc_table = await self._get_lancedb_table("processed_documents")
            chunk_table = await self._get_lancedb_table("document_chunks")

            if not doc_table or not chunk_table:
                return {"lancedb_tables_missing": True}

            # Get document count from LanceDB
            doc_count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: doc_table.search().where(f"user_id = '{user_id}'").count_rows(),
            )

            # Get chunk count from LanceDB
            chunk_count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: chunk_table.search()
                .where(f"user_id = '{user_id}'")
                .count_rows(),
            )

            return {
                "lancedb_available": True,
                "documents_in_lancedb": doc_count,
                "chunks_in_lancedb": chunk_count,
                "avg_chunks_per_doc": chunk_count / doc_count if doc_count > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get LanceDB document stats: {e}")
            return {"lancedb_error": str(e)}

    def _count_documents_by_type(
        self, documents: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Count documents by type"""
        counts = {}
        for doc in documents:
            doc_type = doc.get("doc_type", "unknown")
            counts[doc_type] = counts.get(doc_type, 0) + 1
        return counts

    async def _fallback_text_search(
        self, user_id: str, query: str, doc_type: Optional[str], limit: int
    ) -> List[Dict[str, Any]]:
        """Fallback text search when LanceDB is not available"""
        try:
            documents = await self.get_documents(user_id, limit=1000)
            query_lower = query.lower()

            results = []
            for doc in documents:
                if doc_type and doc.get("doc_type") != doc_type:
                    continue

                # Simple text matching
                text_to_search = f"{doc.get('filename', '')} {doc.get('extracted_text', '')} {doc.get('summary', '')}"
                if query_lower in text_to_search.lower():
                    results.append(
                        {
                            **doc,
                            "similarity_score": 0.5,  # Default score for text match
                            "search_method": "text_fallback",
                        }
                    )

            return sorted(
                results, key=lambda x: x.get("similarity_score", 0), reverse=True
            )[:limit]

        except Exception as e:
            logger.error(f"Fallback text search failed: {e}")
            return []

    async def _get_document_by_id(
        self, user_id: str, doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get document by ID from database"""
        # Implementation depends on database schema
        # This would query the database for the specific document
        return None

    async def get_documents(
        self,
        user_id: str,
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get documents with filtering options"""
        try:
            # This would query the database
            # For now, return empty list - actual implementation would query database
            return []
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []

    async def _save_document_to_db(self, document: Dict[str, Any]):
        """Save document to database"""
        # Implementation depends on database schema
        pass

    def _initialize_processors(self) -> Dict[str, Any]:
        """Initialize document processors for different file types"""
        # This would set up processors similar to the basic document service
        return {}
