"""
OneDrive Document Processor for ATOM Agent Memory System

This module processes OneDrive documents, extracts content, generates embeddings,
and feeds them into LanceDB ingestion pipeline for agent memory.
"""

import os
import logging
import asyncio
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass

# Import Microsoft Graph client
try:
    from msal import PublicClientApplication
    from requests import Session
    from requests.adapters import HTTPAdapter
    import ssl
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False
    logging.warning("MSAL libraries not available")

# Import ATOM services
try:
    from sync.incremental_sync_service import IncrementalSyncService
    from sync.source_change_detector import SourceChange, ChangeType, SourceType
    from db_oauth_outlook import get_user_outlook_tokens
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
class OneDriveDocument:
    """Represents a processed OneDrive document"""
    
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
class OneDriveProcessorConfig:
    """Configuration for OneDrive document processor"""
    
    user_id: str
    sync_interval: int = 300  # 5 minutes
    max_files: int = 100
    chunk_size: int = 500  # characters
    chunk_overlap: int = 50
    include_shared: bool = True
    include_folders: bool = False
    exclude_recycle_bin: bool = True
    supported_mime_types: List[str] = None

    def __post_init__(self):
        if self.supported_mime_types is None:
            self.supported_mime_types = [
                'text/plain',
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            ]


class OneDriveDocumentProcessor:
    """
    Processes OneDrive documents and feeds them into ATOM agent memory system
    """
    
    def __init__(self, config: OneDriveProcessorConfig):
        self.config = config
        self.graph_client: Optional[Session] = None
        self.sync_service: Optional[IncrementalSyncService] = None
        self.processed_docs: Set[str] = set()
        self.running = False
        self.sync_task: Optional[asyncio.Task] = None
        
        # Verify dependencies
        self._verify_dependencies()
        
        logger.info(f"Initialized OneDriveDocumentProcessor for user: {config.user_id}")
    
    def _verify_dependencies(self):
        """Verify all required dependencies are available"""
        if not MSAL_AVAILABLE:
            raise ImportError("MSAL libraries not available")
        if not SYNC_AVAILABLE:
            raise ImportError("Sync services not available")
        if not TEXT_PROCESSING_AVAILABLE:
            logger.warning("Text processing service not available - using fallback")
    
    async def initialize(self) -> bool:
        """
        Initialize OneDrive processor
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Get Microsoft Graph client
            self.graph_client = await self._get_graph_client()
            if not self.graph_client:
                logger.error("Failed to get Microsoft Graph client")
                return False
            
            # Initialize sync service
            self.sync_service = await self._get_sync_service()
            if not self.sync_service:
                logger.error("Failed to get sync service")
                return False
            
            logger.info("OneDriveDocumentProcessor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OneDriveDocumentProcessor: {e}")
            return False
    
    async def start_processing(self) -> None:
        """Start continuous document processing"""
        if self.running:
            logger.warning("OneDriveDocumentProcessor already running")
            return
        
        self.running = True
        
        # Start continuous sync
        self.sync_task = asyncio.create_task(self._processing_loop())
        logger.info("Started OneDrive document processing")
    
    async def stop_processing(self) -> None:
        """Stop continuous document processing"""
        self.running = False
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped OneDrive document processing")
    
    async def _processing_loop(self) -> None:
        """Main processing loop"""
        while self.running:
            try:
                logger.info("Starting OneDrive document sync cycle")
                
                # Process all supported file types
                await self._process_onedrive_files()
                
                # Wait for next sync cycle
                await asyncio.sleep(self.config.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _process_onedrive_files(self) -> None:
        """Process all supported files from OneDrive"""
        try:
            # Get all files
            files = await self._get_all_files()
            
            supported_files = [
                file for file in files
                if file.get('file', {}).get('mimeType') in self.config.supported_mime_types
            ]
            
            for file in supported_files:
                try:
                    # Skip deleted files if configured
                    if self.config.exclude_recycle_bin and file.get('deleted', {}).get('state') == 'restorable':
                        continue
                    
                    # Process individual file
                    await self._process_file(file)
                    
                except Exception as e:
                    logger.error(f"Error processing file {file.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Processed {len(supported_files)} OneDrive files")
            
        except Exception as e:
            logger.error(f"Error processing OneDrive files: {e}")
    
    async def _process_file(self, file: Dict[str, Any]) -> None:
        """Process an individual OneDrive file"""
        try:
            file_id = file.get("id")
            name = file.get("name", "")
            file_metadata = file.get("file", {})
            mime_type = file_metadata.get("mimeType", "")
            url = file.get("webUrl", f"https://onedrive.live.com/?id={file_id}")
            last_modified = file.get("lastModifiedDateTime", datetime.now(timezone.utc).isoformat())
            
            # Download and extract content
            content = await self._extract_file_content(file, mime_type)
            
            # Create document metadata
            document_data = {
                "doc_id": f"onedrive_{file_id}",
                "title": name,
                "source_type": "onedrive",
                "source_uri": url,
                "last_modified": last_modified,
                "user_id": self.config.user_id,
                "metadata": {
                    "file_id": file_id,
                    "mime_type": mime_type,
                    "size": file_metadata.get("size", 0),
                    "created_time": file.get("createdDateTime"),
                    "parent_reference": file.get("parentReference"),
                    "shared": file.get("shared", {}).get("scope", "private") != "private",
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
                    logger.debug(f"Successfully processed file: {name}")
                else:
                    logger.error(f"Failed to process file {name}: {result}")
            
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
    
    async def _get_graph_client(self) -> Optional[Session]:
        """Get authenticated Microsoft Graph client"""
        try:
            # Get user's Outlook/OneDrive tokens (they're the same)
            tokens = await get_user_outlook_tokens(self.config.user_id)
            if not tokens or "access_token" not in tokens:
                logger.error("No OneDrive tokens found for user")
                return None
            
            access_token = tokens["access_token"]
            
            # Create Graph API client session
            session = Session()
            session.headers.update({
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'ATOM-Agent-Memory/1.0'
            })
            
            # Test connection
            response = session.get('https://graph.microsoft.com/v1.0/me')
            if response.status_code == 200:
                return session
            else:
                logger.error(f"Graph API connection failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting Graph client: {e}")
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
        """Get all files from OneDrive"""
        try:
            if not self.graph_client:
                return []
            
            files = []
            endpoint = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
            
            while endpoint:
                response = self.graph_client.get(endpoint)
                if response.status_code != 200:
                    break
                
                data = response.json()
                files.extend(data.get('value', []))
                
                # Check for next link
                next_link = data.get('@odata.nextLink')
                if next_link:
                    endpoint = next_link
                else:
                    break
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting OneDrive files: {e}")
            return []
    
    async def _extract_file_content(
        self, file: Dict[str, Any], mime_type: str
    ) -> str:
        """Extract text content from OneDrive file"""
        try:
            file_id = file.get("id")
            name = file.get("name", "")
            
            # Determine download URL based on MIME type
            if mime_type.startswith('text/'):
                # Direct download for text files
                download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
                return await self._download_file_content(download_url)
            
            elif mime_type == 'application/pdf':
                # Download PDF and extract text
                download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
                return await self._extract_pdf_content(download_url)
            
            elif mime_type in [
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ]:
                # Download Word doc and extract text
                download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
                return await self._extract_word_content(download_url)
            
            elif mime_type in [
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ]:
                # Download Excel and extract text
                download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
                return await self._extract_excel_content(download_url)
            
            else:
                # Fallback to filename
                logger.warning(f"Unsupported MIME type for extraction: {mime_type}")
                return f"OneDrive file: {name}"
                
        except Exception as e:
            logger.error(f"Error extracting file content: {e}")
            return f"OneDrive file: {file.get('name', 'Unknown')}"
    
    async def _download_file_content(self, download_url: str) -> str:
        """Download file content from OneDrive"""
        try:
            response = self.graph_client.get(download_url)
            if response.status_code == 200:
                return response.text.decode('utf-8')
            else:
                logger.error(f"Failed to download file: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"Error downloading file content: {e}")
            return ""
    
    async def _extract_pdf_content(self, download_url: str) -> str:
        """Extract text content from PDF"""
        try:
            response = self.graph_client.get(download_url)
            if response.status_code != 200:
                return f"PDF document ({len(response.content)} bytes)"
            
            pdf_bytes = response.content
            
            # Try to import PyPDF2
            import PyPDF2
            import io
            
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text_content = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"
            
            return text_content
            
        except ImportError:
            logger.warning("PyPDF2 not available - using fallback")
            return f"PDF document ({len(response.content)} bytes)"
        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            return f"PDF document ({len(response.content)} bytes)"
    
    async def _extract_word_content(self, download_url: str) -> str:
        """Extract text content from Word document"""
        try:
            response = self.graph_client.get(download_url)
            if response.status_code != 200:
                return f"Word document ({len(response.content)} bytes)"
            
            doc_bytes = response.content
            
            # Try to import python-docx
            import docx
            import io
            
            doc = docx.Document(io.BytesIO(doc_bytes))
            text_content = ""
            
            for paragraph in doc.paragraphs:
                text_content += paragraph.text + "\n"
            
            return text_content
            
        except ImportError:
            logger.warning("python-docx not available - using fallback")
            return f"Word document ({len(response.content)} bytes)"
        except Exception as e:
            logger.error(f"Error extracting Word content: {e}")
            return f"Word document ({len(response.content)} bytes)"
    
    async def _extract_excel_content(self, download_url: str) -> str:
        """Extract text content from Excel spreadsheet"""
        try:
            response = self.graph_client.get(download_url)
            if response.status_code != 200:
                return f"Excel spreadsheet ({len(response.content)} bytes)"
            
            excel_bytes = response.content
            
            # Try to import pandas and openpyxl
            import pandas as pd
            import io
            
            # Read Excel file
            df = pd.read_excel(io.BytesIO(excel_bytes))
            
            # Convert to text
            text_content = f"Excel spreadsheet: {df.shape[0]} rows, {df.shape[1]} columns\n\n"
            
            # Add first few rows
            for i, row in df.head(10).iterrows():
                row_text = " | ".join([str(cell) for cell in row.values])
                text_content += f"Row {i+1}: {row_text}\n"
            
            return text_content
            
        except ImportError:
            logger.warning("pandas/openpyxl not available - using fallback")
            return f"Excel spreadsheet ({len(response.content)} bytes)"
        except Exception as e:
            logger.error(f"Error extracting Excel content: {e}")
            return f"Excel spreadsheet ({len(response.content)} bytes)"
    
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
def create_onedrive_processor(
    user_id: str, 
    config_overrides: Dict[str, Any] = None
) -> OneDriveDocumentProcessor:
    """
    Create a OneDrive document processor with configuration
    
    Args:
        user_id: User identifier
        config_overrides: Configuration overrides
    
    Returns:
        OneDriveDocumentProcessor instance
    """
    config = OneDriveProcessorConfig(
        user_id=user_id,
        **(config_overrides or {})
    )
    
    return OneDriveDocumentProcessor(config)


async def initialize_onedrive_processor_for_user(
    user_id: str, 
    config_overrides: Dict[str, Any] = None
) -> Optional[OneDriveDocumentProcessor]:
    """
    Initialize and start OneDrive processor for a user
    
    Args:
        user_id: User identifier
        config_overrides: Configuration overrides
    
    Returns:
        Initialized OneDriveDocumentProcessor or None if failed
    """
    try:
        # Create processor
        processor = create_onedrive_processor(user_id, config_overrides)
        
        # Initialize
        if await processor.initialize():
            # Start processing
            await processor.start_processing()
            return processor
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to initialize OneDrive processor for user {user_id}: {e}")
        return None