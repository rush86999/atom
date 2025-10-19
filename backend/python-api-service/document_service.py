"""
Document Service for Atom Personal Assistant

This service provides unified document management across multiple platforms:
- Document processing and ingestion
- Text extraction and analysis
- Document storage and retrieval
- Integration with cloud storage providers
"""

import logging
import os
import tempfile
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

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


class DocumentService:
    """Service for document management operations"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.processors = self._initialize_processors()

    async def upload_document(
        self,
        user_id: str,
        file_data: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload and process a document"""
        try:
            # Generate unique document ID
            doc_id = f"doc_{uuid.uuid4().hex}"

            # Determine document type
            doc_type = self._detect_document_type(filename)

            # Create document record
            document = {
                "id": doc_id,
                "user_id": user_id,
                "filename": filename,
                "file_size": len(file_data),
                "document_type": doc_type.value,
                "status": DocumentStatus.UPLOADED.value,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # Store file data
            storage_path = await self._store_document_file(doc_id, file_data)
            document["storage_path"] = storage_path

            # Save document record
            if self.db_pool:
                await self._save_document_to_db(document)

            # Start processing
            await self._process_document(document)

            logger.info(f"Uploaded document '{filename}' for user {user_id}")
            return document

        except Exception as e:
            logger.error(f"Failed to upload document: {e}")
            raise

    async def process_document(self, user_id: str, document_id: str) -> Dict[str, Any]:
        """Process a previously uploaded document"""
        try:
            document = await self._get_document_by_id(user_id, document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            # Update status to processing
            document["status"] = DocumentStatus.PROCESSING.value
            document["updated_at"] = datetime.now().isoformat()

            if self.db_pool:
                await self._update_document_in_db(document)

            # Process the document
            await self._process_document(document)

            return document

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}")
            # Update status to failed
            document["status"] = DocumentStatus.FAILED.value
            document["error"] = str(e)
            document["updated_at"] = datetime.now().isoformat()

            if self.db_pool:
                await self._update_document_in_db(document)

            raise

    async def get_documents(
        self,
        user_id: str,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get documents with filtering options"""
        try:
            documents = []

            # Get documents from database
            if self.db_pool:
                documents = await self._get_documents_from_db(
                    user_id, document_type, status, search_query, limit, offset
                )
            else:
                # Mock data for demonstration
                documents = self._generate_mock_documents(user_id)

            # Apply filters
            filtered_documents = self._apply_document_filters(
                documents, document_type, status, search_query
            )

            return filtered_documents[:limit]

        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []

    async def get_document_content(
        self, user_id: str, document_id: str
    ) -> Dict[str, Any]:
        """Get processed document content and metadata"""
        try:
            document = await self._get_document_by_id(user_id, document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            # Get processed content
            content = await self._get_document_content(document)

            return {
                "document": document,
                "content": content,
                "extracted_text": content.get("text", ""),
                "metadata": content.get("metadata", {}),
                "entities": content.get("entities", []),
                "summary": content.get("summary", ""),
            }

        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            raise

    async def delete_document(self, user_id: str, document_id: str) -> bool:
        """Delete a document and its associated files"""
        try:
            document = await self._get_document_by_id(user_id, document_id)
            if not document:
                return False

            # Delete file from storage
            await self._delete_document_file(document)

            # Delete from database
            if self.db_pool:
                await self._delete_document_from_db(user_id, document_id)

            logger.info(f"Deleted document {document_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def search_documents(
        self,
        user_id: str,
        query: str,
        document_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search documents by content"""
        try:
            results = []

            # Search in database
            if self.db_pool:
                db_results = await self._search_documents_in_db(
                    user_id, query, document_type, limit
                )
                results.extend(db_results)

            # Search in processed content
            content_results = await self._search_document_content(
                user_id, query, document_type, limit
            )
            results.extend(content_results)

            # Remove duplicates and sort by relevance
            unique_results = self._deduplicate_documents(results)
            unique_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

            return unique_results[:limit]

        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []

    async def get_document_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get document statistics for a user"""
        try:
            documents = await self.get_documents(user_id, limit=1000)

            stats = {
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
                "recent_uploads": len(
                    [
                        d
                        for d in documents
                        if self._is_recent(d.get("created_at"), days=7)
                    ]
                ),
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get document statistics: {e}")
            return {}

    def _initialize_processors(self) -> Dict[str, Any]:
        """Initialize document processors for different file types"""
        processors = {}

        # PDF processor
        try:
            # This would import actual PDF processing libraries
            processors[DocumentType.PDF.value] = {
                "extract_text": self._extract_pdf_text,
                "extract_metadata": self._extract_pdf_metadata,
                "supported": True,
            }
        except ImportError:
            processors[DocumentType.PDF.value] = {"supported": False}

        # DOCX processor
        try:
            processors[DocumentType.DOCX.value] = {
                "extract_text": self._extract_docx_text,
                "extract_metadata": self._extract_docx_metadata,
                "supported": True,
            }
        except ImportError:
            processors[DocumentType.DOCX.value] = {"supported": False}

        # TXT processor
        processors[DocumentType.TXT.value] = {
            "extract_text": self._extract_txt_text,
            "extract_metadata": self._extract_txt_metadata,
            "supported": True,
        }

        return processors

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

    async def _process_document(self, document: Dict[str, Any]):
        """Process document based on its type"""
        try:
            doc_type = document.get("document_type")
            processor = self.processors.get(doc_type)

            if not processor or not processor.get("supported"):
                logger.warning(f"No processor available for document type: {doc_type}")
                document["status"] = DocumentStatus.FAILED.value
                document["error"] = f"Unsupported document type: {doc_type}"
                return

            # Extract text content
            file_data = await self._load_document_file(document)
            if processor.get("extract_text"):
                text_content = await processor["extract_text"](file_data)
                document["extracted_text"] = text_content

            # Extract metadata
            if processor.get("extract_metadata"):
                metadata = await processor["extract_metadata"](file_data)
                document["metadata"].update(metadata)

            # Generate summary and entities
            await self._analyze_document_content(document)

            # Update status to processed
            document["status"] = DocumentStatus.PROCESSED.value
            document["updated_at"] = datetime.now().isoformat()

            if self.db_pool:
                await self._update_document_in_db(document)

            logger.info(f"Processed document {document['id']}")

        except Exception as e:
            logger.error(f"Failed to process document {document['id']}: {e}")
            document["status"] = DocumentStatus.FAILED.value
            document["error"] = str(e)
            document["updated_at"] = datetime.now().isoformat()

            if self.db_pool:
                await self._update_document_in_db(document)

    async def _extract_pdf_text(self, file_data: bytes) -> str:
        """Extract text from PDF file"""
        # This would use PyPDF2, pdfplumber, or similar library
        try:
            # Placeholder implementation
            return "PDF text extraction would be implemented here"
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            return ""

    async def _extract_pdf_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """Extract metadata from PDF file"""
        try:
            # Placeholder implementation
            return {
                "page_count": 0,
                "author": "",
                "title": "",
                "subject": "",
                "creation_date": "",
            }
        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {e}")
            return {}

    async def _extract_docx_text(self, file_data: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            # This would use python-docx library
            return "DOCX text extraction would be implemented here"
        except Exception as e:
            logger.error(f"Failed to extract DOCX text: {e}")
            return ""

    async def _extract_docx_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """Extract metadata from DOCX file"""
        try:
            return {
                "word_count": 0,
                "author": "",
                "title": "",
                "subject": "",
                "creation_date": "",
            }
        except Exception as e:
            logger.error(f"Failed to extract DOCX metadata: {e}")
            return {}

    async def _extract_txt_text(self, file_data: bytes) -> str:
        """Extract text from TXT file"""
        try:
            return file_data.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to extract TXT text: {e}")
            return ""

    async def _extract_txt_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """Extract metadata from TXT file"""
        try:
            text = file_data.decode("utf-8", errors="ignore")
            return {
                "character_count": len(text),
                "line_count": len(text.splitlines()),
                "word_count": len(text.split()),
            }
        except Exception as e:
            logger.error(f"Failed to extract TXT metadata: {e}")
            return {}

    async def _analyze_document_content(self, document: Dict[str, Any]):
        """Analyze document content for entities, summary, etc."""
        try:
            text = document.get("extracted_text", "")
            if not text:
                return

            # Basic analysis (would be enhanced with NLP libraries)
            document["analysis"] = {
                "word_count": len(text.split()),
                "character_count": len(text),
                "sentence_count": len(text.split(". ")),
                "reading_time_minutes": max(1, len(text.split()) // 200),  # 200 wpm
            }

            # Generate simple summary (first 200 characters)
            if len(text) > 200:
                document["summary"] = text[:200] + "..."
            else:
                document["summary"] = text

        except Exception as e:
            logger.error(f"Failed to analyze document content: {e}")

    def _apply_document_filters(
        self,
        documents: List[Dict[str, Any]],
        document_type: Optional[str],
        status: Optional[str],
        search_query: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Apply filters to document list"""
        filtered_documents = documents

        if document_type:
            filtered_documents = [
                d for d in filtered_documents if d.get("document_type") == document_type
            ]

        if status:
            filtered_documents = [
                d for d in filtered_documents if d.get("status") == status
            ]

        if search_query:
            query = search_query.lower()
            filtered_documents = [
                d
                for d in filtered_documents
                if query in d.get("filename", "").lower()
                or query in d.get("extracted_text", "").lower()
                or query in d.get("summary", "").lower()
            ]

        return filtered_documents

    def _count_documents_by_type(
        self, documents: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Count documents by type"""
        counts = {}
        for doc in documents:
            doc_type = doc.get("document_type", "unknown")
            counts[doc_type] = counts.get(doc_type, 0) + 1
        return counts

    def _is_recent(self, date_str: Optional[str], days: int = 7) -> bool:
        """Check if date is within recent days"""
        if not date_str:
            return False

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return (datetime.now() - date).days <= days
        except Exception:
            return False

    def _deduplicate_documents(
        self, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate documents"""
        seen_ids = set()
        unique_documents = []

        for doc in documents:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_documents.append(doc)

        return unique_documents

    def _generate_mock_documents(self, user_id: str) -> List[Dict[str, Any]]:
        """Generate mock documents for testing"""
        sample_filenames = [
            "project_proposal.pdf",
            "meeting_notes.docx",
            "requirements.txt",
            "design_spec.md",
            "budget_spreadsheet.xlsx",
            "presentation.pptx",
        ]

        documents = []
        for i, filename in enumerate(sample_filenames):
            doc_type = self._detect_document_type(filename)
            documents.append(
                {
                    "id": f"doc_{i}",
                    "user_id": user_id,
                    "filename": filename,
                    "file_size": 1024 * (i + 1),
                    "document_type": doc_type.value,
                    "status": DocumentStatus.PROCESSED.value,
                    "extracted_text": f"This is sample content for {filename}",
                    "summary": f"Summary of {filename}",
                    "metadata": {"pages": i + 1, "words": (i + 1) * 100},
                    "created_at": (datetime.now()).isoformat(),
                    "updated_at": (datetime.now()).isoformat(),
                }
            )
        return documents
