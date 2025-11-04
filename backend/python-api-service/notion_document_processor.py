"""
Notion Document Processor for ATOM Agent Memory System

This module processes Notion documents, extracts content, generates embeddings,
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

# Import Notion client
try:
    from notion_client import Client
    from notion_client.helpers import collect_paginated_api
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    logging.warning("Notion client not available")

# Import ATOM services
try:
    from sync.incremental_sync_service import IncrementalSyncService, ChangeRecord
    from sync.source_change_detector import SourceChange, ChangeType, SourceType
    from db_oauth_notion import get_user_notion_tokens
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
class NotionDocument:
    """Represents a processed Notion document"""
    
    doc_id: str
    title: str
    content: str
    url: str
    source_type: str
    last_modified: str
    metadata: Dict[str, Any]
    chunks: List[str]
    embeddings: List[List[float]]
    checksum: str


@dataclass
class NotionProcessorConfig:
    """Configuration for Notion document processor"""
    
    user_id: str
    sync_interval: int = 300  # 5 minutes
    max_page_size: int = 100
    chunk_size: int = 500  # characters
    chunk_overlap: int = 50
    include_databases: bool = True
    include_pages: bool = True
    exclude_archived: bool = True
    exclude_private: bool = False


class NotionDocumentProcessor:
    """
    Processes Notion documents and feeds them into ATOM agent memory system
    """
    
    def __init__(self, config: NotionProcessorConfig):
        self.config = config
        self.notion_client: Optional[Client] = None
        self.sync_service: Optional[IncrementalSyncService] = None
        self.processed_docs: Set[str] = set()
        self.running = False
        self.sync_task: Optional[asyncio.Task] = None
        
        # Verify dependencies
        self._verify_dependencies()
        
        logger.info(f"Initialized NotionDocumentProcessor for user: {config.user_id}")
    
    def _verify_dependencies(self):
        """Verify all required dependencies are available"""
        if not NOTION_AVAILABLE:
            raise ImportError("Notion client not available")
        if not SYNC_AVAILABLE:
            raise ImportError("Sync services not available")
        if not TEXT_PROCESSING_AVAILABLE:
            logger.warning("Text processing service not available - using fallback")
    
    async def initialize(self) -> bool:
        """
        Initialize the Notion processor
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Get Notion client
            self.notion_client = await self._get_notion_client()
            if not self.notion_client:
                logger.error("Failed to get Notion client")
                return False
            
            # Initialize sync service
            self.sync_service = await self._get_sync_service()
            if not self.sync_service:
                logger.error("Failed to get sync service")
                return False
            
            logger.info("NotionDocumentProcessor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize NotionDocumentProcessor: {e}")
            return False
    
    async def start_processing(self) -> None:
        """Start continuous document processing"""
        if self.running:
            logger.warning("NotionDocumentProcessor already running")
            return
        
        self.running = True
        
        # Start continuous sync
        self.sync_task = asyncio.create_task(self._processing_loop())
        logger.info("Started Notion document processing")
    
    async def stop_processing(self) -> None:
        """Stop continuous document processing"""
        self.running = False
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped Notion document processing")
    
    async def _processing_loop(self) -> None:
        """Main processing loop"""
        while self.running:
            try:
                logger.info("Starting Notion document sync cycle")
                
                # Process all document types
                await self._process_notion_documents()
                
                # Wait for next sync cycle
                await asyncio.sleep(self.config.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _process_notion_documents(self) -> None:
        """Process all types of Notion documents"""
        try:
            # Process pages
            if self.config.include_pages:
                await self._process_pages()
            
            # Process database records
            if self.config.include_databases:
                await self._process_databases()
            
            logger.info("Completed Notion document sync cycle")
            
        except Exception as e:
            logger.error(f"Error processing Notion documents: {e}")
    
    async def _process_pages(self) -> None:
        """Process Notion pages"""
        try:
            # Search for all pages
            pages = await self._get_all_pages()
            
            for page in pages:
                try:
                    # Skip archived pages if configured
                    if self.config.exclude_archived and page.get("archived", False):
                        continue
                    
                    # Process individual page
                    await self._process_page(page)
                    
                except Exception as e:
                    logger.error(f"Error processing page {page.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Processed {len(pages)} Notion pages")
            
        except Exception as e:
            logger.error(f"Error in _process_pages: {e}")
    
    async def _process_databases(self) -> None:
        """Process Notion database records"""
        try:
            # Get all databases
            databases = await self._get_all_databases()
            
            for database in databases:
                try:
                    # Process database records
                    await self._process_database(database)
                    
                except Exception as e:
                    logger.error(f"Error processing database {database.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Processed {len(databases)} Notion databases")
            
        except Exception as e:
            logger.error(f"Error in _process_databases: {e}")
    
    async def _process_page(self, page: Dict[str, Any]) -> None:
        """Process an individual Notion page"""
        try:
            page_id = page.get("id")
            title = self._extract_page_title(page)
            content = await self._extract_page_content(page)
            url = page.get("url", "")
            last_modified = page.get("last_edited_time", datetime.now(timezone.utc).isoformat())
            
            # Create document metadata
            document_data = {
                "doc_id": f"notion_page_{page_id}",
                "title": title,
                "source_type": "notion_page",
                "source_uri": url,
                "last_modified": last_modified,
                "user_id": self.config.user_id,
                "metadata": {
                    "page_id": page_id,
                    "archived": page.get("archived", False),
                    "created_time": page.get("created_time"),
                    "created_by": page.get("created_by"),
                    "last_edited_by": page.get("last_edited_by"),
                    "parent_id": page.get("parent"),
                    "properties": page.get("properties", {}),
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
                    self.processed_docs.add(page_id)
                    logger.debug(f"Successfully processed page: {title}")
                else:
                    logger.error(f"Failed to process page {title}: {result}")
            
        except Exception as e:
            logger.error(f"Error processing page: {e}")
    
    async def _process_database(self, database: Dict[str, Any]) -> None:
        """Process a Notion database and its records"""
        try:
            database_id = database.get("id")
            database_title = self._extract_database_title(database)
            
            # Get all records from database
            records = await self._get_database_records(database_id)
            
            for record in records:
                try:
                    await self._process_database_record(record, database)
                    
                except Exception as e:
                    logger.error(f"Error processing record {record.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Processed {len(records)} records from database: {database_title}")
            
        except Exception as e:
            logger.error(f"Error processing database: {e}")
    
    async def _process_database_record(
        self, record: Dict[str, Any], database: Dict[str, Any]
    ) -> None:
        """Process an individual database record"""
        try:
            record_id = record.get("id")
            database_id = database.get("id")
            database_title = self._extract_database_title(database)
            
            # Extract record content
            content = self._extract_record_content(record, database)
            title = self._extract_record_title(record, database)
            url = record.get("url", f"https://notion.so/{record_id}")
            last_modified = record.get("last_edited_time", datetime.now(timezone.utc).isoformat())
            
            # Create document metadata
            document_data = {
                "doc_id": f"notion_record_{record_id}",
                "title": title,
                "source_type": "notion_record",
                "source_uri": url,
                "last_modified": last_modified,
                "user_id": self.config.user_id,
                "metadata": {
                    "record_id": record_id,
                    "database_id": database_id,
                    "database_title": database_title,
                    "database_properties": database.get("properties", {}),
                    "record_properties": record.get("properties", {}),
                    "created_time": record.get("created_time"),
                    "created_by": record.get("created_by"),
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
                    logger.debug(f"Successfully processed database record: {title}")
                else:
                    logger.error(f"Failed to process record {title}: {result}")
            
        except Exception as e:
            logger.error(f"Error processing database record: {e}")
    
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
    
    async def _get_notion_client(self) -> Optional[Client]:
        """Get authenticated Notion client"""
        try:
            # Get user's Notion tokens
            tokens = await get_user_notion_tokens(self.config.user_id)
            if not tokens or "access_token" not in tokens:
                logger.error("No Notion tokens found for user")
                return None
            
            access_token = tokens["access_token"]
            
            # Create and return Notion client
            return Client(auth=access_token)
            
        except Exception as e:
            logger.error(f"Error getting Notion client: {e}")
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
    
    async def _get_all_pages(self) -> List[Dict[str, Any]]:
        """Get all pages from Notion"""
        try:
            if not self.notion_client:
                return []
            
            # Search for all pages
            response = self.notion_client.search(
                filter={"property": "object", "value": "page"},
                page_size=self.config.max_page_size
            )
            
            # Collect all pages using pagination
            pages = []
            async for page in collect_paginated_api(self.notion_client, response):
                pages.append(page)
                if len(pages) >= self.config.max_page_size:
                    break
            
            return pages
            
        except Exception as e:
            logger.error(f"Error getting pages: {e}")
            return []
    
    async def _get_all_databases(self) -> List[Dict[str, Any]]:
        """Get all databases from Notion"""
        try:
            if not self.notion_client:
                return []
            
            # Search for all databases
            response = self.notion_client.search(
                filter={"property": "object", "value": "database"},
                page_size=self.config.max_page_size
            )
            
            # Collect all databases using pagination
            databases = []
            async for database in collect_paginated_api(self.notion_client, response):
                databases.append(database)
                if len(databases) >= self.config.max_page_size:
                    break
            
            return databases
            
        except Exception as e:
            logger.error(f"Error getting databases: {e}")
            return []
    
    async def _get_database_records(self, database_id: str) -> List[Dict[str, Any]]:
        """Get all records from a database"""
        try:
            if not self.notion_client:
                return []
            
            # Query database for all records
            response = self.notion_client.databases.query(
                database_id=database_id,
                page_size=self.config.max_page_size
            )
            
            # Collect all records using pagination
            records = []
            async for record in collect_paginated_api(self.notion_client, response):
                records.append(record)
                if len(records) >= self.config.max_page_size:
                    break
            
            return records
            
        except Exception as e:
            logger.error(f"Error getting database records: {e}")
            return []
    
    def _extract_page_title(self, page: Dict[str, Any]) -> str:
        """Extract title from Notion page"""
        try:
            properties = page.get("properties", {})
            
            # Try different title property names
            for title_prop in ["title", "Name", "name", "Title"]:
                if title_prop in properties:
                    title_data = properties[title_prop]
                    if title_data and "title" in title_data:
                        title_list = title_data["title"]
                        if title_list:
                            return title_list[0].get("text", {}).get("content", "")
            
            # Fallback to page ID
            return f"Page {page.get('id', 'Unknown')}"
            
        except Exception as e:
            logger.error(f"Error extracting page title: {e}")
            return f"Page {page.get('id', 'Unknown')}"
    
    def _extract_database_title(self, database: Dict[str, Any]) -> str:
        """Extract title from Notion database"""
        try:
            title_data = database.get("title", [])
            if title_data:
                return title_data[0].get("text", {}).get("content", "")
            return f"Database {database.get('id', 'Unknown')}"
            
        except Exception as e:
            logger.error(f"Error extracting database title: {e}")
            return f"Database {database.get('id', 'Unknown')}"
    
    def _extract_record_title(self, record: Dict[str, Any], database: Dict[str, Any]) -> str:
        """Extract title from database record"""
        try:
            properties = record.get("properties", {})
            database_properties = database.get("properties", {})
            
            # Find title property in database
            title_prop_id = None
            for prop_id, prop_data in database_properties.items():
                if prop_data.get("type") == "title":
                    title_prop_id = prop_id
                    break
            
            if title_prop_id and title_prop_id in properties:
                title_data = properties[title_prop_id]
                if title_data and "title" in title_data:
                    title_list = title_data["title"]
                    if title_list:
                        return title_list[0].get("text", {}).get("content", "")
            
            # Fallback to record ID
            return f"Record {record.get('id', 'Unknown')}"
            
        except Exception as e:
            logger.error(f"Error extracting record title: {e}")
            return f"Record {record.get('id', 'Unknown')}"
    
    def _extract_record_content(
        self, record: Dict[str, Any], database: Dict[str, Any]
    ) -> str:
        """Extract content from database record"""
        try:
            properties = record.get("properties", {})
            content_parts = []
            
            # Extract text from all text properties
            for prop_id, prop_value in properties.items():
                if isinstance(prop_value, dict):
                    if "title" in prop_value:
                        # Title property
                        title_parts = prop_value["title"]
                        for part in title_parts:
                            content_parts.append(part.get("text", {}).get("content", ""))
                    elif "rich_text" in prop_value:
                        # Rich text property
                        text_parts = prop_value["rich_text"]
                        for part in text_parts:
                            content_parts.append(part.get("text", {}).get("content", ""))
                    elif "plain_text" in prop_value:
                        # Plain text property
                        content_parts.append(str(prop_value["plain_text"]))
                    elif "select" in prop_value:
                        # Select property
                        select_data = prop_value["select"]
                        if select_data:
                            content_parts.append(select_data.get("name", ""))
                    elif "multi_select" in prop_value:
                        # Multi-select property
                        multi_select_data = prop_value["multi_select"]
                        for item in multi_select_data:
                            content_parts.append(item.get("name", ""))
                    elif "date" in prop_value:
                        # Date property
                        date_data = prop_value["date"]
                        if date_data:
                            content_parts.append(date_data.get("start", ""))
                    elif "checkbox" in prop_value:
                        # Checkbox property
                        checkbox_value = prop_value["checkbox"]
                        content_parts.append(str(checkbox_value))
            
            return " | ".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error extracting record content: {e}")
            return ""
    
    async def _extract_page_content(self, page: Dict[str, Any]) -> str:
        """Extract full content from Notion page"""
        try:
            if not self.notion_client:
                return ""
            
            page_id = page.get("id")
            if not page_id:
                return ""
            
            # Get page blocks
            blocks_response = self.notion_client.blocks.children.list(
                block_id=page_id,
                page_size=100
            )
            
            # Collect all content blocks
            content_parts = []
            async for block in collect_paginated_api(self.notion_client, blocks_response):
                block_content = self._extract_block_content(block)
                if block_content:
                    content_parts.append(block_content)
            
            # Combine with page properties
            properties_content = self._extract_page_properties_content(page)
            if properties_content:
                content_parts.insert(0, properties_content)  # Properties first
            
            return "\n\n".join(filter(None, content_parts))
            
        except Exception as e:
            logger.error(f"Error extracting page content: {e}")
            return ""
    
    def _extract_block_content(self, block: Dict[str, Any]) -> str:
        """Extract text content from a Notion block"""
        try:
            block_type = block.get("type", "")
            block_data = block.get(block_type, {})
            
            if block_type == "paragraph":
                text_parts = block_data.get("rich_text", [])
                return self._extract_rich_text(text_parts)
            
            elif block_type == "heading_1":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"# {text}" if text else ""
            
            elif block_type == "heading_2":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"## {text}" if text else ""
            
            elif block_type == "heading_3":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"### {text}" if text else ""
            
            elif block_type == "bulleted_list_item":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"• {text}" if text else ""
            
            elif block_type == "numbered_list_item":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"1. {text}" if text else ""
            
            elif block_type == "to_do":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                checked = block_data.get("checked", False)
                checkbox = "☑" if checked else "☐"
                return f"{checkbox} {text}" if text else f"{checkbox}"
            
            elif block_type == "toggle":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"📝 {text}" if text else ""
            
            elif block_type == "code":
                text_parts = block_data.get("rich_text", [])
                code = self._extract_rich_text(text_parts)
                language = block_data.get("language", "")
                return f"```{language}\n{code}\n```" if code else ""
            
            elif block_type == "quote":
                text_parts = block_data.get("rich_text", [])
                text = self._extract_rich_text(text_parts)
                return f"> {text}" if text else ""
            
            elif block_type == "divider":
                return "---"
            
            else:
                # Handle other block types
                text_parts = block_data.get("rich_text", [])
                return self._extract_rich_text(text_parts)
                
        except Exception as e:
            logger.error(f"Error extracting block content: {e}")
            return ""
    
    def _extract_rich_text(self, rich_text_data: List[Dict[str, Any]]) -> str:
        """Extract text content from rich text data"""
        try:
            text_parts = []
            for text_part in rich_text_data:
                text = text_part.get("text", "")
                text_parts.append(text)
            return "".join(text_parts)
            
        except Exception as e:
            logger.error(f"Error extracting rich text: {e}")
            return ""
    
    def _extract_page_properties_content(self, page: Dict[str, Any]) -> str:
        """Extract text content from page properties"""
        try:
            properties = page.get("properties", {})
            content_parts = []
            
            for prop_name, prop_value in properties.items():
                if isinstance(prop_value, dict):
                    if "title" in prop_value:
                        title_parts = prop_value["title"]
                        title_text = self._extract_rich_text(title_parts)
                        if title_text:
                            content_parts.append(f"**{prop_name}**: {title_text}")
                    
                    elif "rich_text" in prop_value:
                        text_parts = prop_value["rich_text"]
                        text_content = self._extract_rich_text(text_parts)
                        if text_content:
                            content_parts.append(f"**{prop_name}**: {text_content}")
                    
                    elif "select" in prop_value:
                        select_data = prop_value["select"]
                        if select_data:
                            content_parts.append(f"**{prop_name}**: {select_data.get('name', '')}")
                    
                    elif "date" in prop_value:
                        date_data = prop_value["date"]
                        if date_data:
                            date_text = date_data.get("start", "")
                            if date_text:
                                content_parts.append(f"**{prop_name}**: {date_text}")
                    
                    elif "checkbox" in prop_value:
                        checkbox_value = prop_value["checkbox"]
                        content_parts.append(f"**{prop_name}**: {checkbox_value}")
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error extracting page properties: {e}")
            return ""
    
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
def create_notion_processor(user_id: str, config_overrides: Dict[str, Any] = None) -> NotionDocumentProcessor:
    """
    Create a Notion document processor with configuration
    
    Args:
        user_id: User identifier
        config_overrides: Configuration overrides
    
    Returns:
        NotionDocumentProcessor instance
    """
    config = NotionProcessorConfig(
        user_id=user_id,
        **(config_overrides or {})
    )
    
    return NotionDocumentProcessor(config)


async def initialize_notion_processor_for_user(
    user_id: str, 
    config_overrides: Dict[str, Any] = None
) -> Optional[NotionDocumentProcessor]:
    """
    Initialize and start Notion processor for a user
    
    Args:
        user_id: User identifier
        config_overrides: Configuration overrides
    
    Returns:
        Initialized NotionDocumentProcessor or None if failed
    """
    try:
        # Create processor
        processor = create_notion_processor(user_id, config_overrides)
        
        # Initialize
        if await processor.initialize():
            # Start processing
            await processor.start_processing()
            return processor
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to initialize Notion processor for user {user_id}: {e}")
        return None