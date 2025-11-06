"""
Google Drive Memory Integration
Integration with ATOM's LanceDB memory and ingestion pipeline
"""

import json
import logging
import asyncio
import hashlib
import base64
import mimetypes
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, BinaryIO
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import io

# LanceDB and vector embeddings
import lancedb
import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np

# ATOM core imports
from memory.lancedb_manager import LanceDBManager
from ingestion.data_processor import DataProcessor
from ingestion.embeddings_manager import EmbeddingsManager
from ingestion.content_extractor import ContentExtractor

from google_drive_service import GoogleDriveService, GoogleDriveFile, GoogleDriveFolder

logger = logging.getLogger(__name__)

class MemoryType(Enum):
    """Memory storage types"""
    FILE_METADATA = "file_metadata"
    FILE_CONTENT = "file_content"
    FOLDER_STRUCTURE = "folder_structure"
    DOCUMENT_VECTORS = "document_vectors"
    RELATIONSHIPS = "relationships"

class ContentStatus(Enum):
    """Content processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    INDEXED = "indexed"

@dataclass
class GoogleDriveMemoryRecord:
    """Google Drive memory record model"""
    id: str
    file_id: str
    user_id: str
    name: str
    mime_type: str
    size: int = 0
    content_hash: str = ""
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    parents: List[str] = field(default_factory=list)
    web_view_link: str = ""
    web_content_link: str = ""
    thumbnail_link: str = ""
    shared: bool = False
    content_status: ContentStatus = ContentStatus.PENDING
    extracted_content: Optional[str] = None
    file_path: Optional[str] = None
    embeddings: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    vector_id: Optional[str] = None
    last_indexed: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None

@dataclass
class GoogleDriveFolderRecord:
    """Google Drive folder memory record"""
    id: str
    folder_id: str
    user_id: str
    name: str
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    parents: List[str] = field(default_factory=list)
    web_view_link: str = ""
    shared: bool = False
    child_count: int = 0
    path: str = ""
    depth: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class GoogleDriveMemoryService:
    """Google Drive memory integration service"""
    
    def __init__(
        self,
        db_manager: LanceDBManager,
        embeddings_manager: EmbeddingsManager,
        data_processor: DataProcessor,
        content_extractor: ContentExtractor,
        drive_service: GoogleDriveService
    ):
        self.db_manager = db_manager
        self.embeddings_manager = embeddings_manager
        self.data_processor = data_processor
        self.content_extractor = content_extractor
        self.drive_service = drive_service
        
        # Initialize collections
        self.collections = {
            MemoryType.FILE_METADATA: "google_drive_files",
            MemoryType.FOLDER_STRUCTURE: "google_drive_folders",
            MemoryType.DOCUMENT_VECTORS: "google_drive_documents",
            MemoryType.RELATIONSHIPS: "google_drive_relationships"
        }
        
        # Ensure collections exist
        self._initialize_collections()
        
        # Embedding model for semantic search
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dimension = 384
        
        # Processing queue
        self.processing_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.processing_workers: List[asyncio.Task] = []
        self.max_workers = 4
        
        # Statistics
        self.indexed_files = 0
        self.processed_content = 0
        self.failed_processing = 0
    
    def _initialize_collections(self):
        """Initialize LanceDB collections"""
        try:
            # Initialize file metadata collection
            self.db_manager.create_collection(
                self.collections[MemoryType.FILE_METADATA],
                schema={
                    "id": str,
                    "file_id": str,
                    "user_id": str,
                    "name": str,
                    "mime_type": str,
                    "size": int,
                    "content_hash": str,
                    "created_time": str,
                    "modified_time": str,
                    "parents": str,  # JSON string
                    "web_view_link": str,
                    "web_content_link": str,
                    "thumbnail_link": str,
                    "shared": bool,
                    "content_status": str,
                    "extracted_content": str,
                    "file_path": str,
                    "embeddings": str,  # JSON string
                    "metadata": str,  # JSON string
                    "tags": str,  # JSON string
                    "relationships": str,  # JSON string
                    "vector_id": str,
                    "last_indexed": str,
                    "access_count": int,
                    "last_accessed": str
                }
            )
            
            # Initialize folder structure collection
            self.db_manager.create_collection(
                self.collections[MemoryType.FOLDER_STRUCTURE],
                schema={
                    "id": str,
                    "folder_id": str,
                    "user_id": str,
                    "name": str,
                    "created_time": str,
                    "modified_time": str,
                    "parents": str,  # JSON string
                    "web_view_link": str,
                    "shared": bool,
                    "child_count": int,
                    "path": str,
                    "depth": int,
                    "metadata": str,  # JSON string
                    "last_updated": str
                }
            )
            
            # Initialize document vectors collection for semantic search
            self.db_manager.create_collection(
                self.collections[MemoryType.DOCUMENT_VECTORS],
                schema={
                    "id": str,
                    "file_id": str,
                    "user_id": str,
                    "content": str,
                    "content_type": str,
                    "title": str,
                    "embedding": list,  # Vector embeddings
                    "tokens": int,
                    "metadata": str  # JSON string
                }
            )
            
            # Initialize relationships collection
            self.db_manager.create_collection(
                self.collections[MemoryType.RELATIONSHIPS],
                schema={
                    "id": str,
                    "source_id": str,
                    "target_id": str,
                    "relationship_type": str,
                    "user_id": str,
                    "strength": float,
                    "metadata": str,  # JSON string
                    "created_at": str
                }
            )
            
            logger.info("Google Drive memory collections initialized")
            
        except Exception as e:
            logger.error(f"Error initializing Google Drive memory collections: {e}")
            raise
    
    async def index_file(
        self,
        file: GoogleDriveFile,
        user_id: str,
        download_content: bool = True,
        process_content: bool = True
    ) -> GoogleDriveMemoryRecord:
        """Index file in memory"""
        
        try:
            # Check if file already exists
            existing_record = await self.get_file_record(file.id, user_id)
            
            # Create memory record
            record = GoogleDriveMemoryRecord(
                id=self._generate_memory_id(file.id, user_id),
                file_id=file.id,
                user_id=user_id,
                name=file.name,
                mime_type=file.mime_type,
                size=file.size,
                content_hash=self._calculate_content_hash(file),
                created_time=file.created_time,
                modified_time=file.modified_time,
                parents=file.parents,
                web_view_link=file.web_view_link or "",
                web_content_link=file.web_content_link or "",
                thumbnail_link=file.thumbnail_link or "",
                shared=file.shared,
                content_status=ContentStatus.PENDING,
                metadata={
                    "version": file.version,
                    "md5_checksum": file.md5_checksum,
                    "file_extension": file.file_extension,
                    "full_file_extension": file.full_file_extension,
                    "trashed": file.trashed,
                    "starred": file.starred,
                    "owners": file.owners,
                    "permissions": file.permissions
                }
            )
            
            # Download content if requested and file is text/document
            if download_content and self._should_download_content(file.mime_type):
                try:
                    content = await self.drive_service.download_file(
                        user_id=user_id,
                        file_id=file.id
                    )
                    
                    if content:
                        record.extracted_content = self._extract_content_from_bytes(
                            content, file.name, file.mime_type
                        )
                        record.file_path = await self._store_file_locally(
                            file.id, content, file.name
                        )
                    
                    record.content_status = ContentStatus.COMPLETED if record.extracted_content else ContentStatus.FAILED
                    
                except Exception as e:
                    logger.error(f"Error downloading file {file.id}: {e}")
                    record.content_status = ContentStatus.FAILED
                    record.extracted_content = f"Error downloading content: {str(e)}"
            
            # Process content for embeddings and search
            if process_content and record.extracted_content:
                await self._process_file_content(record)
            
            # Store in memory
            await self._store_file_record(record)
            
            # Update relationships
            if record.parents:
                await self._update_parent_child_relationships(
                    record.user_id, record.id, record.parents
                )
            
            # Update statistics
            self.indexed_files += 1
            
            logger.info(f"Indexed file: {file.name} ({record.content_status.value})")
            
            return record
        
        except Exception as e:
            logger.error(f"Error indexing file {file.id}: {e}")
            raise
    
    async def index_folder(
        self,
        folder: GoogleDriveFolder,
        user_id: str
    ) -> GoogleDriveFolderRecord:
        """Index folder in memory"""
        
        try:
            # Build folder path
            path = await self._build_folder_path(folder.id, user_id)
            
            # Get child count
            child_files = await self.drive_service.get_files(
                user_id=user_id,
                parent_id=folder.id,
                page_size=1
            )
            child_folders = await self._get_child_folders(folder.id, user_id)
            child_count = len(child_files) + len(child_folders)
            
            # Create folder record
            record = GoogleDriveFolderRecord(
                id=self._generate_memory_id(folder.id, user_id),
                folder_id=folder.id,
                user_id=user_id,
                name=folder.name,
                created_time=folder.created_time,
                modified_time=folder.modified_time,
                parents=folder.parents,
                web_view_link=folder.web_view_link or "",
                shared=folder.shared,
                child_count=child_count,
                path=path,
                depth=path.count("/"),
                metadata={
                    "owners": folder.owners,
                    "permissions": folder.permissions,
                    "trashed": folder.trashed,
                    "starred": folder.starred
                }
            )
            
            # Store in memory
            await self._store_folder_record(record)
            
            logger.info(f"Indexed folder: {folder.name} (Path: {path})")
            
            return record
        
        except Exception as e:
            logger.error(f"Error indexing folder {folder.id}: {e}")
            raise
    
    async def batch_index(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        include_subfolders: bool = True,
        download_content: bool = True
    ) -> Dict[str, Any]:
        """Batch index files and folders"""
        
        try:
            results = {
                "files_indexed": 0,
                "folders_indexed": 0,
                "content_processed": 0,
                "errors": []
            }
            
            # Get all files and folders
            files = await self.drive_service.get_files(
                user_id=user_id,
                parent_id=folder_id,
                page_size=1000
            )
            
            # Index folders first
            folders_to_process = set()
            for file in files:
                if file.mime_type == "application/vnd.google-apps.folder":
                    try:
                        folder = GoogleDriveFolder(
                            id=file.id,
                            name=file.name,
                            created_time=file.created_time,
                            modified_time=file.modified_time,
                            parents=file.parents,
                            web_view_link=file.web_view_link,
                            shared=file.shared,
                            owners=file.owners,
                            trashed=file.trashed,
                            starred=file.starred
                        )
                        
                        await self.index_folder(folder, user_id)
                        results["folders_indexed"] += 1
                        folders_to_process.add(file.id)
                        
                    except Exception as e:
                        results["errors"].append(f"Folder {file.id}: {str(e)}")
            
            # Index files
            for file in files:
                if file.mime_type != "application/vnd.google-apps.folder":
                    try:
                        record = await self.index_file(
                            file, user_id, download_content, True
                        )
                        results["files_indexed"] += 1
                        
                        if record.content_status == ContentStatus.COMPLETED:
                            results["content_processed"] += 1
                        
                    except Exception as e:
                        results["errors"].append(f"File {file.id}: {str(e)}")
            
            # Process subfolders if requested
            if include_subfolders and folders_to_process:
                for folder_id in folders_to_process:
                    try:
                        sub_results = await self.batch_index(
                            user_id=user_id,
                            folder_id=folder_id,
                            include_subfolders=True,
                            download_content=download_content
                        )
                        
                        results["files_indexed"] += sub_results["files_indexed"]
                        results["folders_indexed"] += sub_results["folders_indexed"]
                        results["content_processed"] += sub_results["content_processed"]
                        results["errors"].extend(sub_results["errors"])
                        
                    except Exception as e:
                        results["errors"].append(f"Subfolder {folder_id}: {str(e)}")
            
            logger.info(f"Batch indexing completed: {results}")
            
            return results
        
        except Exception as e:
            logger.error(f"Error in batch indexing: {e}")
            raise
    
    async def search_files(
        self,
        user_id: str,
        query: str,
        search_type: str = "semantic",  # "semantic", "text", "metadata"
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> List[GoogleDriveMemoryRecord]:
        """Search files in memory"""
        
        try:
            if search_type == "semantic":
                return await self._semantic_search(user_id, query, filters, limit)
            elif search_type == "text":
                return await self._text_search(user_id, query, filters, limit)
            elif search_type == "metadata":
                return await self._metadata_search(user_id, query, filters, limit)
            else:
                raise ValueError(f"Invalid search type: {search_type}")
        
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return []
    
    async def get_file_record(
        self,
        file_id: str,
        user_id: str
    ) -> Optional[GoogleDriveMemoryRecord]:
        """Get file record from memory"""
        
        try:
            memory_id = self._generate_memory_id(file_id, user_id)
            
            record_data = self.db_manager.get_record(
                collection_name=self.collections[MemoryType.FILE_METADATA],
                record_id=memory_id
            )
            
            if record_data:
                return self._dict_to_file_record(record_data)
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting file record: {e}")
            return None
    
    async def get_folder_record(
        self,
        folder_id: str,
        user_id: str
    ) -> Optional[GoogleDriveFolderRecord]:
        """Get folder record from memory"""
        
        try:
            memory_id = self._generate_memory_id(folder_id, user_id)
            
            record_data = self.db_manager.get_record(
                collection_name=self.collections[MemoryType.FOLDER_STRUCTURE],
                record_id=memory_id
            )
            
            if record_data:
                return self._dict_to_folder_record(record_data)
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting folder record: {e}")
            return None
    
    async def get_file_content(
        self,
        file_id: str,
        user_id: str
    ) -> Optional[str]:
        """Get file content from memory"""
        
        try:
            record = await self.get_file_record(file_id, user_id)
            
            if record and record.extracted_content:
                # Update access statistics
                await self._update_access_stats(record)
                
                return record.extracted_content
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None
    
    async def update_file_record(
        self,
        file_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update file record in memory"""
        
        try:
            memory_id = self._generate_memory_id(file_id, user_id)
            
            # Get existing record
            record = await self.get_file_record(file_id, user_id)
            if not record:
                return False
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            
            # Update in database
            await self._store_file_record(record)
            
            logger.info(f"Updated file record: {file_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error updating file record: {e}")
            return False
    
    async def delete_file_record(
        self,
        file_id: str,
        user_id: str
    ) -> bool:
        """Delete file record from memory"""
        
        try:
            memory_id = self._generate_memory_id(file_id, user_id)
            
            # Delete from file metadata collection
            self.db_manager.delete_record(
                collection_name=self.collections[MemoryType.FILE_METADATA],
                record_id=memory_id
            )
            
            # Delete from document vectors collection
            self.db_manager.delete_records(
                collection_name=self.collections[MemoryType.DOCUMENT_VECTORS],
                filter={"file_id": file_id, "user_id": user_id}
            )
            
            # Delete relationships
            self.db_manager.delete_records(
                collection_name=self.collections[MemoryType.RELATIONSHIPS],
                filter={"source_id": file_id, "user_id": user_id}
            )
            
            self.db_manager.delete_records(
                collection_name=self.collections[MemoryType.RELATIONSHIPS],
                filter={"target_id": file_id, "user_id": user_id}
            )
            
            logger.info(f"Deleted file record: {file_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error deleting file record: {e}")
            return False
    
    async def get_folder_tree(
        self,
        user_id: str,
        root_folder_id: Optional[str] = None,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """Get folder tree structure"""
        
        try:
            # Get all folder records
            folders = self.db_manager.get_records(
                collection_name=self.collections[MemoryType.FOLDER_STRUCTURE],
                filter={"user_id": user_id}
            )
            
            folder_records = [self._dict_to_folder_record(f) for f in folders]
            
            # Build tree structure
            tree = {}
            root_folders = []
            
            if root_folder_id:
                # Build tree from specific root
                root_record = next(
                    (f for f in folder_records if f.folder_id == root_folder_id), 
                    None
                )
                if root_record:
                    root_folders = [root_record]
            else:
                # Find root folders (no parents or "root" in parents)
                root_folders = [
                    f for f in folder_records 
                    if not f.parents or "root" in f.parents
                ]
            
            # Recursively build tree
            for root_folder in root_folders:
                tree[root_folder.folder_id] = {
                    "record": root_folder,
                    "children": await self._build_folder_children(
                        root_folder.folder_id, folder_records, 1, max_depth
                    )
                }
            
            return tree
        
        except Exception as e:
            logger.error(f"Error getting folder tree: {e}")
            return {}
    
    async def get_file_relationships(
        self,
        file_id: str,
        user_id: str,
        relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get file relationships"""
        
        try:
            filter_dict = {"user_id": user_id}
            
            if relationship_type:
                filter_dict["relationship_type"] = relationship_type
            
            # Get outgoing relationships
            relationships = self.db_manager.get_records(
                collection_name=self.collections[MemoryType.RELATIONSHIPS],
                filter={**filter_dict, "source_id": file_id}
            )
            
            return list(relationships) if relationships else []
        
        except Exception as e:
            logger.error(f"Error getting file relationships: {e}")
            return []
    
    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        user_id: str,
        strength: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create file relationship"""
        
        try:
            relationship_id = f"rel_{source_id}_{target_id}_{relationship_type}_{datetime.now().timestamp()}"
            
            relationship = {
                "id": relationship_id,
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
                "user_id": user_id,
                "strength": strength,
                "metadata": json.dumps(metadata or {}),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            self.db_manager.add_record(
                collection_name=self.collections[MemoryType.RELATIONSHIPS],
                record=relationship
            )
            
            logger.info(f"Created relationship: {source_id} -> {target_id} ({relationship_type})")
            
            return True
        
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            return False
    
    def _generate_memory_id(self, file_id: str, user_id: str) -> str:
        """Generate unique memory ID"""
        return f"{user_id}_{file_id}"
    
    def _calculate_content_hash(self, file: GoogleDriveFile) -> str:
        """Calculate content hash for file"""
        hash_string = (
            f"{file.id}|{file.name}|{file.mime_type}|"
            f"{file.modified_time.isoformat() if file.modified_time else ''}|"
            f"{file.size}|{json.dumps(file.parents, sort_keys=True)}"
        )
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def _should_download_content(self, mime_type: str) -> bool:
        """Check if content should be downloaded for processing"""
        # Process text documents, spreadsheets, presentations
        processable_types = [
            "text/plain",
            "text/csv",
            "application/json",
            "application/xml",
            "application/pdf",
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.google-apps.presentation",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ]
        
        return any(mime_type.startswith(pt) for pt in processable_types)
    
    def _extract_content_from_bytes(
        self,
        content: bytes,
        filename: str,
        mime_type: str
    ) -> Optional[str]:
        """Extract text content from bytes"""
        
        try:
            # Use content extractor
            extracted = self.content_extractor.extract_content(
                content, filename, mime_type
            )
            
            return extracted
        
        except Exception as e:
            logger.error(f"Error extracting content from {filename}: {e}")
            return None
    
    async def _store_file_locally(
        self,
        file_id: str,
        content: bytes,
        filename: str
    ) -> Optional[str]:
        """Store file locally"""
        
        try:
            # Create local storage directory
            storage_dir = Path("storage/google_drive")
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Store file
            file_path = storage_dir / f"{file_id}_{filename}"
            
            async with aiofiles.open(file_path, 'wb') as file:
                await file.write(content)
            
            return str(file_path)
        
        except Exception as e:
            logger.error(f"Error storing file locally: {e}")
            return None
    
    async def _process_file_content(self, record: GoogleDriveMemoryRecord):
        """Process file content for embeddings and search"""
        
        try:
            if not record.extracted_content:
                return
            
            # Generate embeddings
            embeddings = self.embeddings_manager.generate_embeddings(
                [record.extracted_content]
            )
            
            if embeddings:
                record.embeddings = embeddings[0].tolist()
                
                # Store in document vectors collection
                vector_record = {
                    "id": f"vec_{record.id}",
                    "file_id": record.file_id,
                    "user_id": record.user_id,
                    "content": record.extracted_content,
                    "content_type": record.mime_type,
                    "title": record.name,
                    "embedding": record.embeddings,
                    "tokens": len(record.extracted_content.split()),
                    "metadata": json.dumps({
                        "size": record.size,
                        "created_time": record.created_time.isoformat() if record.created_time else "",
                        "modified_time": record.modified_time.isoformat() if record.modified_time else "",
                        "mime_type": record.mime_type,
                        "parents": record.parents
                    })
                }
                
                self.db_manager.add_record(
                    collection_name=self.collections[MemoryType.DOCUMENT_VECTORS],
                    record=vector_record
                )
                
                record.content_status = ContentStatus.INDEXED
                self.processed_content += 1
                
                logger.info(f"Processed content for file: {record.name}")
        
        except Exception as e:
            logger.error(f"Error processing file content: {e}")
            record.content_status = ContentStatus.FAILED
            self.failed_processing += 1
    
    async def _store_file_record(self, record: GoogleDriveMemoryRecord):
        """Store file record in memory"""
        
        try:
            record_dict = self._file_record_to_dict(record)
            
            self.db_manager.upsert_record(
                collection_name=self.collections[MemoryType.FILE_METADATA],
                record=record_dict
            )
        
        except Exception as e:
            logger.error(f"Error storing file record: {e}")
            raise
    
    async def _store_folder_record(self, record: GoogleDriveFolderRecord):
        """Store folder record in memory"""
        
        try:
            record_dict = self._folder_record_to_dict(record)
            
            self.db_manager.upsert_record(
                collection_name=self.collections[MemoryType.FOLDER_STRUCTURE],
                record=record_dict
            )
        
        except Exception as e:
            logger.error(f"Error storing folder record: {e}")
            raise
    
    async def _build_folder_path(
        self,
        folder_id: str,
        user_id: str
    ) -> str:
        """Build full folder path"""
        
        try:
            path_parts = []
            current_id = folder_id
            max_depth = 20  # Prevent infinite loops
            depth = 0
            
            while current_id and depth < max_depth:
                record = await self.get_folder_record(current_id, user_id)
                
                if not record:
                    break
                
                path_parts.append(record.name)
                
                # Move to parent
                if record.parents and record.parents[0] != "root":
                    current_id = record.parents[0]
                else:
                    break
                
                depth += 1
            
            # Build path (reverse to get root to current)
            return "/" + "/".join(reversed(path_parts))
        
        except Exception as e:
            logger.error(f"Error building folder path: {e}")
            return f"/{folder_id}"
    
    async def _get_child_folders(
        self,
        parent_id: str,
        user_id: str
    ) -> List[GoogleDriveFile]:
        """Get child folders"""
        
        try:
            files = await self.drive_service.get_files(
                user_id=user_id,
                parent_id=parent_id,
                mime_type="application/vnd.google-apps.folder"
            )
            
            return files
        
        except Exception as e:
            logger.error(f"Error getting child folders: {e}")
            return []
    
    async def _build_folder_children(
        self,
        folder_id: str,
        folder_records: List[GoogleDriveFolderRecord],
        depth: int,
        max_depth: int
    ) -> Dict[str, Any]:
        """Recursively build folder children"""
        
        if depth >= max_depth:
            return {}
        
        children = {}
        
        # Find direct children
        direct_children = [
            f for f in folder_records 
            if folder_id in f.parents
        ]
        
        for child in direct_children:
            children[child.folder_id] = {
                "record": child,
                "children": await self._build_folder_children(
                    child.folder_id, folder_records, depth + 1, max_depth
                )
            }
        
        return children
    
    async def _semantic_search(
        self,
        user_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> List[GoogleDriveMemoryRecord]:
        """Perform semantic search on file content"""
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])[0].tolist()
            
            # Search in document vectors collection
            results = self.db_manager.vector_search(
                collection_name=self.collections[MemoryType.DOCUMENT_VECTORS],
                query_vector=query_embedding,
                vector_column="embedding",
                filter={**({"user_id": user_id} if user_id else {}), **(filters or {})},
                limit=limit
            )
            
            # Convert to file records
            file_records = []
            for result in results:
                file_record = await self.get_file_record(result["file_id"], user_id)
                if file_record:
                    file_records.append(file_record)
            
            return file_records
        
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def _text_search(
        self,
        user_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> List[GoogleDriveMemoryRecord]:
        """Perform text search on file content"""
        
        try:
            # Search in file metadata collection
            search_filter = {
                "user_id": user_id,
                "$textsearch": {"extracted_content": query}
            }
            
            if filters:
                search_filter.update(filters)
            
            results = self.db_manager.get_records(
                collection_name=self.collections[MemoryType.FILE_METADATA],
                filter=search_filter,
                limit=limit
            )
            
            return [self._dict_to_file_record(r) for r in results]
        
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            return []
    
    async def _metadata_search(
        self,
        user_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> List[GoogleDriveMemoryRecord]:
        """Perform search on file metadata"""
        
        try:
            # Search in file metadata fields
            search_filter = {
                "user_id": user_id,
                "$textsearch": {"name": query}
            }
            
            if filters:
                search_filter.update(filters)
            
            results = self.db_manager.get_records(
                collection_name=self.collections[MemoryType.FILE_METADATA],
                filter=search_filter,
                limit=limit
            )
            
            return [self._dict_to_file_record(r) for r in results]
        
        except Exception as e:
            logger.error(f"Error in metadata search: {e}")
            return []
    
    async def _update_access_stats(self, record: GoogleDriveMemoryRecord):
        """Update file access statistics"""
        
        try:
            record.access_count += 1
            record.last_accessed = datetime.now(timezone.utc)
            
            await self._store_file_record(record)
        
        except Exception as e:
            logger.error(f"Error updating access stats: {e}")
    
    async def _update_parent_child_relationships(
        self,
        user_id: str,
        file_id: str,
        parent_ids: List[str]
    ):
        """Update parent-child relationships"""
        
        try:
            # Create relationships for each parent
            for parent_id in parent_ids:
                await self.create_relationship(
                    source_id=parent_id,
                    target_id=file_id,
                    relationship_type="contains",
                    user_id=user_id
                )
        
        except Exception as e:
            logger.error(f"Error updating relationships: {e}")
    
    def _file_record_to_dict(self, record: GoogleDriveMemoryRecord) -> Dict[str, Any]:
        """Convert file record to dictionary"""
        return {
            "id": record.id,
            "file_id": record.file_id,
            "user_id": record.user_id,
            "name": record.name,
            "mime_type": record.mime_type,
            "size": record.size,
            "content_hash": record.content_hash,
            "created_time": record.created_time.isoformat() if record.created_time else "",
            "modified_time": record.modified_time.isoformat() if record.modified_time else "",
            "parents": json.dumps(record.parents),
            "web_view_link": record.web_view_link,
            "web_content_link": record.web_content_link,
            "thumbnail_link": record.thumbnail_link,
            "shared": record.shared,
            "content_status": record.content_status.value,
            "extracted_content": record.extracted_content or "",
            "file_path": record.file_path or "",
            "embeddings": json.dumps(record.embeddings) if record.embeddings else "",
            "metadata": json.dumps(record.metadata),
            "tags": json.dumps(record.tags),
            "relationships": json.dumps(record.relationships),
            "vector_id": record.vector_id or "",
            "last_indexed": record.last_indexed.isoformat() if record.last_indexed else "",
            "access_count": record.access_count,
            "last_accessed": record.last_accessed.isoformat() if record.last_accessed else ""
        }
    
    def _folder_record_to_dict(self, record: GoogleDriveFolderRecord) -> Dict[str, Any]:
        """Convert folder record to dictionary"""
        return {
            "id": record.id,
            "folder_id": record.folder_id,
            "user_id": record.user_id,
            "name": record.name,
            "created_time": record.created_time.isoformat() if record.created_time else "",
            "modified_time": record.modified_time.isoformat() if record.modified_time else "",
            "parents": json.dumps(record.parents),
            "web_view_link": record.web_view_link,
            "shared": record.shared,
            "child_count": record.child_count,
            "path": record.path,
            "depth": record.depth,
            "metadata": json.dumps(record.metadata),
            "last_updated": record.last_updated.isoformat()
        }
    
    def _dict_to_file_record(self, data: Dict[str, Any]) -> GoogleDriveMemoryRecord:
        """Convert dictionary to file record"""
        return GoogleDriveMemoryRecord(
            id=data.get("id", ""),
            file_id=data.get("file_id", ""),
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            mime_type=data.get("mime_type", ""),
            size=data.get("size", 0),
            content_hash=data.get("content_hash", ""),
            created_time=datetime.fromisoformat(data["created_time"]).replace(tzinfo=timezone.utc) if data.get("created_time") else None,
            modified_time=datetime.fromisoformat(data["modified_time"]).replace(tzinfo=timezone.utc) if data.get("modified_time") else None,
            parents=json.loads(data.get("parents", "[]")),
            web_view_link=data.get("web_view_link", ""),
            web_content_link=data.get("web_content_link", ""),
            thumbnail_link=data.get("thumbnail_link", ""),
            shared=data.get("shared", False),
            content_status=ContentStatus(data.get("content_status", "pending")),
            extracted_content=data.get("extracted_content"),
            file_path=data.get("file_path"),
            embeddings=json.loads(data.get("embeddings", "[]")) if data.get("embeddings") else None,
            metadata=json.loads(data.get("metadata", "{}")),
            tags=json.loads(data.get("tags", "[]")),
            relationships=json.loads(data.get("relationships", "[]")),
            vector_id=data.get("vector_id"),
            last_indexed=datetime.fromisoformat(data["last_indexed"]).replace(tzinfo=timezone.utc) if data.get("last_indexed") else None,
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]).replace(tzinfo=timezone.utc) if data.get("last_accessed") else None
        )
    
    def _dict_to_folder_record(self, data: Dict[str, Any]) -> GoogleDriveFolderRecord:
        """Convert dictionary to folder record"""
        return GoogleDriveFolderRecord(
            id=data.get("id", ""),
            folder_id=data.get("folder_id", ""),
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            created_time=datetime.fromisoformat(data["created_time"]).replace(tzinfo=timezone.utc) if data.get("created_time") else None,
            modified_time=datetime.fromisoformat(data["modified_time"]).replace(tzinfo=timezone.utc) if data.get("modified_time") else None,
            parents=json.loads(data.get("parents", "[]")),
            web_view_link=data.get("web_view_link", ""),
            shared=data.get("shared", False),
            child_count=data.get("child_count", 0),
            path=data.get("path", ""),
            depth=data.get("depth", 0),
            metadata=json.loads(data.get("metadata", "{}")),
            last_updated=datetime.fromisoformat(data["last_updated"]).replace(tzinfo=timezone.utc)
        )
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get memory integration statistics"""
        return {
            "indexed_files": self.indexed_files,
            "processed_content": self.processed_content,
            "failed_processing": self.failed_processing,
            "success_rate": (
                (self.processed_content / (self.processed_content + self.failed_processing) * 100)
                if (self.processed_content + self.failed_processing) > 0 else 0
            ),
            "collections": list(self.collections.values()),
            "embedding_dimension": self.embedding_dimension
        }

# Export classes
__all__ = [
    "GoogleDriveMemoryService",
    "GoogleDriveMemoryRecord",
    "GoogleDriveFolderRecord",
    "MemoryType",
    "ContentStatus"
]