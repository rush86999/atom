"""
Google Drive Document Processor for ATOM Agent Memory System

This module processes Google Drive documents, extracts content, generates embeddings,
and feeds them into the LanceDB ingestion pipeline for agent memory.
"""

import os
import logging
import asyncio
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass

# Import Google Drive client
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.http import MediaIoBaseDownload
    import io
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logging.warning("Google Drive libraries not available")

# Import ATOM services
try:
    from sync.incremental_sync_service import IncrementalSyncService
    from sync.source_change_detector import SourceChange, ChangeType, SourceType
    from db_oauth_google_drive import get_user_google_drive_tokens
    SYNC_AVAILABLE = True
except ImportError as e:
    SYNC_AVAILABLE = False
    logging.warning(f"Sync services not available: {e}")

# Import text processing
try:
    from text_processing_service import process_text_for_embeddings, generate_embeddings
    TEXT_PROCESSING_AVAILABLE = True
except ImportError:
    TEXT_PROCESSING_AVAILABLE = False
    logging.warning("Text processing service not available")

logger = logging.getLogger(__name__)


@dataclass
class GoogleDriveDocument:
    """Represents a processed Google Drive document"""
    
    doc_id: str
    title: str
    content: str
    url: str
    mime_type: str
    last_modified: str
    metadata: Dict[str, Any]
    chunks: List[str]
    embeddings: List[List[float]]
    checksum: str


@dataclass
class GoogleDriveProcessorConfig:
    """Configuration for Google Drive document processor"""
    
    user_id: str
    sync_interval: int = 300  # 5 minutes
    max_files: int = 100
    chunk_size: int = 500  # characters
    chunk_overlap: int = 50
    include_shared: bool = True
    include_folders: bool = False
    exclude_trashed: bool = True
    supported_mime_types: List[str] = None

    def __post_init__(self):
        if self.supported_mime_types is None:
            self.supported_mime_types = [
                'text/plain',
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.google-apps.document',
                'application/vnd.google-apps.spreadsheet',
                'application/vnd.google-apps.presentation',
            ]


class GoogleDriveDocumentProcessor:
    """
    Processes Google Drive documents and feeds them into ATOM agent memory system
    """
    
    def __init__(self, config: GoogleDriveProcessorConfig):
        self.config = config
        self.drive_service = None
        self.sync_service: Optional[IncrementalSyncService] = None
        self.processed_docs: Set[str] = set()
        self.running = False
        self.sync_task: Optional[asyncio.Task] = None
        
        # Verify dependencies
        self._verify_dependencies()
        
        logger.info(f"Initialized GoogleDriveDocumentProcessor for user: {config.user_id}")
    
    def _verify_dependencies(self):
        """Verify all required dependencies are available"""
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError("Google Drive libraries not available")
        if not SYNC_AVAILABLE:
            raise ImportError("Sync services not available")
        if not TEXT_PROCESSING_AVAILABLE:
            logger.warning("Text processing service not available - using fallback")
    
    async def initialize(self) -> bool:
        """
        Initialize Google Drive processor
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Get Google Drive service
            self.drive_service = await self._get_drive_service()
            if not self.drive_service:
                logger.error("Failed to get Google Drive service")
                return False
            
            # Initialize sync service
            self.sync_service = await self._get_sync_service()
            if not self.sync_service:
                logger.error("Failed to get sync service")
                return False
            
            logger.info("GoogleDriveDocumentProcessor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GoogleDriveDocumentProcessor: {e}")
            return False
    
    async def start_processing(self) -> None:
        """Start continuous document processing"""
        if self.running:
            logger.warning("GoogleDriveDocumentProcessor already running")
            return
        
        self.running = True
        
        # Start continuous sync
        self.sync_task = asyncio.create_task(self._processing_loop())
        logger.info("Started Google Drive document processing")
    
    async def stop_processing(self) -> None:
        """Stop continuous document processing"""
        self.running = False
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped Google Drive document processing")
    
    async def _processing_loop(self) -> None:
        """Main processing loop"""
        while self.running:
            try:
                logger.info("Starting Google Drive document sync cycle")
                
                # Process all supported file types
                await self._process_drive_files()
                
                # Wait for next sync cycle
                await asyncio.sleep(self.config.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _process_drive_files(self) -> None:
        """Process all supported files from Google Drive"""
        try:
            # Get all files
            files = await self._get_all_files()
            
            supported_files = [
                file for file in files
                if file.get('mimeType') in self.config.supported_mime_types
            ]
            
            for file in supported_files:
                try:
                    # Skip trashed files if configured
                    if self.config.exclude_trashed and file.get('trashed', False):
                        continue
                    
                    # Process individual file
                    await self._process_file(file)
                    
                except Exception as e:
                    logger.error(f"Error processing file {file.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Processed {len(supported_files)} Google Drive files")
            
        except Exception as e:
            logger.error(f"Error processing Google Drive files: {e}")
    
    async def _process_file(self, file: Dict[str, Any]) -> None:
        """Process an individual Google Drive file"""
        try:
            file_id = file.get("id")
            title = file.get("name", "")
            mime_type = file.get("mimeType", "")
            url = file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}")
            last_modified = file.get("modifiedTime", datetime.now(timezone.utc).isoformat())
            
            # Download and extract content
            content = await self._extract_file_content(file, mime_type)
            
            # Create document metadata
            document_data = {
                "doc_id": f"gdrive_{file_id}",
                "title": title,
                "source_type": "google_drive",
                "source_uri": url,
                "last_modified": last_modified,
                "user_id": self.config.user_id,
                "metadata": {
                    "file_id": file_id,
                    "mime_type": mime_type,
                    "size": file.get("size", 0),
                    "created_time": file.get("createdTime"),
                    "shared": file.get("shared", False),
                    "parents": file.get("parents", []),
                    "permissions": file.get("permissions", []),
                }
            }
            
            # Process content for embeddings
            chunks_with_embeddings = await self._process_content_for_embeddings(
                content, document_data
            )
            
            # Store in LanceDB through sync service
            if self.sync_service:
                result = await self.sync_service.process_document_incrementally(
                    user_id=self.config.user_id,
                    source_uri=url,
                    document_data=document_data,
                    chunks_with_embeddings=chunks_with_embeddings
                )
                
                if result["status"] == "success":
                    self.processed_docs.add(file_id)
                    logger.debug(f"Successfully processed file: {title}")
                else:
                    logger.error(f"Failed to process file {title}: {result}")
            
        except Exception as e:
            logger.error(f"Error processing file: {e}")
    
    async def _process_content_for_embeddings(
        self, content: str, document_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process content for embedding generation"""
        try:
            if TEXT_PROCESSING_AVAILABLE:
                # Use text processing service
                chunks = process_text_for_embeddings(
                    content,
                    chunk_size=self.config.chunk_size,
                    chunk_overlap=self.config.chunk_overlap
                )
                embeddings = await generate_embeddings(chunks)
                
                return [
                    {
                        "chunk_text": chunk,
                        "embedding": embedding,
                        "chunk_metadata": {
                            "doc_id": document_data["doc_id"],
                            "source_type": document_data["source_type"],
                            "chunk_index": i,
                            "char_count": len(chunk),
                        }
                    }
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
                ]
            else:
                # Fallback processing
                chunks = self._fallback_chunking(content)
                return [
                    {
                        "chunk_text": chunk,
                        "embedding": [0.0] * 384,  # Dummy embedding
                        "chunk_metadata": {
                            "doc_id": document_data["doc_id"],
                            "source_type": document_data["source_type"],
                            "chunk_index": i,
                            "char_count": len(chunk),
                        }
                    }
                    for i, chunk in enumerate(chunks)
                ]
                
        except Exception as e:
            logger.error(f"Error processing content for embeddings: {e}")
            return []
    
    async def _get_drive_service(self) -> Optional[Any]:
        """Get authenticated Google Drive service"""
        try:
            # Get user's Google Drive tokens
            tokens = await get_user_google_drive_tokens(self.config.user_id)
            if not tokens or "access_token" not in tokens:
                logger.error("No Google Drive tokens found for user")
                return None
            
            # Create credentials from tokens
            credentials = Credentials(
                token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                token_uri=tokens.get("token_uri"),
                client_id=tokens.get("client_id"),
                client_secret=tokens.get("client_secret"),
                scopes=tokens.get("scopes", [
                    'https://www.googleapis.com/auth/drive.readonly'
                ])
            )
            
            # Build service
            service = build('drive', 'v3', credentials=credentials)
            return service
            
        except Exception as e:
            logger.error(f"Error getting Google Drive service: {e}")
            return None
    
    async def _get_sync_service(self) -> Optional[IncrementalSyncService]:
        """Get sync service for document storage"""
        try:
            # Import sync configuration
            from sync.orchestration_service import get_default_sync_config
            
            sync_config = get_default_sync_config()
            
            # Create and return sync service
            from sync.incremental_sync_service import create_incremental_sync_service
            
            return create_incremental_sync_service(
                local_db_path=sync_config.local_db_path,
                s3_bucket=sync_config.s3_bucket,
                s3_prefix=sync_config.s3_prefix,
            )
            
        except Exception as e:
            logger.error(f"Error getting sync service: {e}")
            return None
    
    async def _get_all_files(self) -> List[Dict[str, Any]]:
        """Get all files from Google Drive"""
        try:
            if not self.drive_service:
                return []
            
            files = []
            page_token = None
            
            while True:
                # List files
                query = self.drive_service.files().list(
                    pageSize=self.config.max_files,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, webViewLink, size, shared, trashed, parents, permissions)",
                    pageToken=page_token
                )
                
                result = query.execute()
                files.extend(result.get('files', []))
                
                page_token = result.get('nextPageToken')
                if not page_token:
                    break
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting Google Drive files: {e}")
            return []
    
    async def _extract_file_content(
        self, file: Dict[str, Any], mime_type: str
    ) -> str:
        """Extract text content from Google Drive file"""
        try:
            file_id = file.get("id")
            file_name = file.get("name", "")
            
            # Google Workspace files
            if mime_type.startswith('application/vnd.google-apps'):
                return await self._extract_google_workspace_content(file, mime_type)
            
            # Regular files (PDF, Word, etc.)
            return await self._extract_regular_file_content(file, mime_type)
            
        except Exception as e:
            logger.error(f"Error extracting file content: {e}")
            return ""
    
    async def _extract_google_workspace_content(
        self, file: Dict[str, Any], mime_type: str
    ) -> str:
        """Extract content from Google Workspace files"""
        try:
            file_id = file.get("id")
            
            if mime_type == 'application/vnd.google-apps.document':
                # Export Google Doc as text
                request = self.drive_service.files().export(
                    fileId=file_id,
                    mimeType='text/plain'
                )
                
                media = request.execute()
                return media.decode('utf-8')
            
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Export Google Sheet as CSV
                request = self.drive_service.files().export(
                    fileId=file_id,
                    mimeType='text/csv'
                )
                
                media = request.execute()
                return media.decode('utf-8')
            
            elif mime_type == 'application/vnd.google-apps.presentation':
                # Export Google Slides as text
                request = self.drive_service.files().export(
                    fileId=file_id,
                    mimeType='text/plain'
                )
                
                media = request.execute()
                return media.decode('utf-8')
            
            else:
                logger.warning(f"Unsupported Google Workspace MIME type: {mime_type}")
                return f"Google Workspace file: {file.get('name', 'Unknown')}"
                
        except Exception as e:
            logger.error(f"Error extracting Google Workspace content: {e}")
            return f"Google Workspace file: {file.get('name', 'Unknown')}"
    
    async def _extract_regular_file_content(
        self, file: Dict[str, Any], mime_type: str
    ) -> str:
        """Extract content from regular files (PDF, Word, etc.)"""
        try:
            file_id = file.get("id")
            file_name = file.get("name", "")
            
            # Download file content
            request = self.drive_service.files().get_media(fileId=file_id)
            
            # Use in-memory download
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, chunksize=1024*1024)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            content = file_io.getvalue()
            
            # Process based on MIME type
            if mime_type == 'text/plain':
                return content.decode('utf-8')
            
            elif mime_type == 'application/pdf':
                return self._extract_pdf_content(content)
            
            elif mime_type in [
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ]:
                return self._extract_word_content(content)
            
            else:
                logger.warning(f"Unsupported MIME type for extraction: {mime_type}")
                return f"File: {file_name} ({mime_type})"
                
        except Exception as e:
            logger.error(f"Error extracting regular file content: {e}")
            return f"File: {file.get('name', 'Unknown')}"
    
    def _extract_pdf_content(self, pdf_bytes: bytes) -> str:
        """Extract text content from PDF bytes"""
        try:
            # Try to import PyPDF2
            import PyPDF2
            
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text_content = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
            
            return text_content
            
        except ImportError:
            logger.warning("PyPDF2 not available - using fallback")
            return f"PDF document ({len(pdf_bytes)} bytes)"
        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            return f"PDF document ({len(pdf_bytes)} bytes)"
    
    def _extract_word_content(self, doc_bytes: bytes) -> str:
        """Extract text content from Word document bytes"""
        try:
            # Try to import python-docx
            import docx
            
            doc = docx.Document(io.BytesIO(doc_bytes))
            text_content = ""
            
            for paragraph in doc.paragraphs:
                text_content += paragraph.text + "\n"
            
            return text_content
            
        except ImportError:
            logger.warning("python-docx not available - using fallback")
            return f"Word document ({len(doc_bytes)} bytes)"
        except Exception as e:
            logger.error(f"Error extracting Word content: {e}")
            return f"Word document ({len(doc_bytes)} bytes)"
    
    def _fallback_chunking(self, content: str) -> List[str]:
        """Fallback chunking method when text processing service is unavailable"""
        try:
            if not content:
                return []
            
            chunks = []
            for i in range(0, len(content), self.config.chunk_size):
                chunk = content[i:i + self.config.chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error in fallback chunking: {e}")
            return [content] if content else []


# Factory functions
def create_google_drive_processor(
    user_id: str, 
    config_overrides: Dict[str, Any] = None
) -> GoogleDriveDocumentProcessor:
    """
    Create a Google Drive document processor with configuration
    
    Args:
        user_id: User identifier
        config_overrides: Configuration overrides
    
    Returns:
        GoogleDriveDocumentProcessor instance
    """
    config = GoogleDriveProcessorConfig(
        user_id=user_id,
        **(config_overrides or {})
    )
    
    return GoogleDriveDocumentProcessor(config)


async def initialize_google_drive_processor_for_user(
    user_id: str, 
    config_overrides: Dict[str, Any] = None
) -> Optional[GoogleDriveDocumentProcessor]:
    """
    Initialize and start Google Drive processor for a user
    
    Args:
        user_id: User identifier
        config_overrides: Configuration overrides
    
    Returns:
        Initialized GoogleDriveDocumentProcessor or None if failed
    """
    try:
        # Create processor
        processor = create_google_drive_processor(user_id, config_overrides)
        
        # Initialize
        if await processor.initialize():
            # Start processing
            await processor.start_processing()
            return processor
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive processor for user {user_id}: {e}")
        return None