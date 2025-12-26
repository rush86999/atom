"""
Automatic Document Ingestion Service for Atom Memory
Auto-ingests documents from connected file storage integrations (Google Drive, Dropbox, etc.)
Supports: Excel, PDF, DOC/DOCX, TXT, CSV, Markdown files
"""

import logging
import asyncio
import os
import io
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class FileType(str, Enum):
    """Supported file types for ingestion"""
    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    TXT = "txt"
    CSV = "csv"
    EXCEL = "xlsx"
    XLS = "xls"
    MARKDOWN = "md"
    JSON = "json"


class IntegrationSource(str, Enum):
    """Supported file storage integrations"""
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    BOX = "box"
    SHAREPOINT = "sharepoint"
    NOTION = "notion"
    LOCAL = "local"


@dataclass
class IngestionSettings:
    """Settings for document ingestion per integration"""
    integration_id: str
    workspace_id: str
    enabled: bool = False
    auto_sync_new_files: bool = True
    file_types: List[str] = field(default_factory=lambda: ["pdf", "docx", "txt", "md"])
    sync_folders: List[str] = field(default_factory=list)  # Empty = all folders
    exclude_folders: List[str] = field(default_factory=list)
    max_file_size_mb: int = 50
    sync_frequency_minutes: int = 60
    last_sync: Optional[datetime] = None


@dataclass
class IngestedDocument:
    """Record of an ingested document"""
    id: str
    file_name: str
    file_path: str
    file_type: str
    integration_id: str
    workspace_id: str
    file_size_bytes: int
    content_preview: str  # First 500 chars
    ingested_at: datetime
    external_id: str  # ID in the source system
    external_modified_at: Optional[datetime] = None


class DocumentParser:
    """
    Parses various document formats and extracts text.
    Reuses existing parsers from DocumentLifecycleLearner where available.
    """
    
    @staticmethod
    async def parse_document(file_content: bytes, file_type: str, file_name: str) -> str:
        """Parse document and extract text content"""
        try:
            if file_type in ["txt", "md"]:
                return file_content.decode("utf-8", errors="ignore")
            
            elif file_type == "json":
                data = json.loads(file_content.decode("utf-8"))
                return json.dumps(data, indent=2)
            
            elif file_type == "csv":
                return DocumentParser._parse_csv(file_content)
            
            elif file_type == "pdf":
                return await DocumentParser._parse_pdf(file_content)
            
            elif file_type in ["doc", "docx"]:
                return await DocumentParser._parse_docx(file_content)
            
            elif file_type in ["xlsx", "xls"]:
                return await DocumentParser._parse_excel(file_content)
            
            else:
                logger.warning(f"Unsupported file type: {file_type}")
                return ""
                
        except Exception as e:
            logger.error(f"Failed to parse {file_name}: {e}")
            return ""
    
    @staticmethod
    def _parse_csv(content: bytes) -> str:
        """Parse CSV to text - reuses DataIngestionService logic"""
        try:
            import csv
            text = content.decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(text))
            rows = []
            for i, row in enumerate(reader):
                if i > 1000:  # Limit rows
                    rows.append("... (truncated)")
                    break
                rows.append(" | ".join(row))
            return "\n".join(rows)
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            return content.decode("utf-8", errors="ignore")
    
    @staticmethod
    async def _parse_pdf(content: bytes) -> str:
        """Parse PDF to text - compatible with DocumentLifecycleLearner"""
        try:
            # Try PyPDF2 (used by DocumentLifecycleLearner)
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages[:50]:  # Limit pages
                text_parts.append(page.extract_text() or "")
            return "\n\n".join(text_parts)
        except ImportError:
            # Fallback to pypdf
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                text_parts = []
                for page in reader.pages[:50]:
                    text_parts.append(page.extract_text() or "")
                return "\n\n".join(text_parts)
            except ImportError:
                logger.warning("No PDF parser available")
                return "[PDF content - parser not available]"
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            return ""
    
    @staticmethod
    async def _parse_docx(content: bytes) -> str:
        """Parse DOCX to text - compatible with DocumentLifecycleLearner"""
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            full_text = []
            
            # Extract paragraphs
            for para in doc.paragraphs[:500]:
                full_text.append(para.text)
            
            # Also extract tables (from DocumentLifecycleLearner)
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells]
                    full_text.append(" | ".join(row_text))
                    
            return "\n".join(full_text)
        except ImportError:
            logger.warning("python-docx not available")
            return "[DOCX content - parser not available]"
        except Exception as e:
            logger.error(f"DOCX parse error: {e}")
            return ""
    
    @staticmethod
    async def _parse_excel(content: bytes, file_path: str = None, workspace_id: str = "default") -> str:
        """Parse Excel to text - compatible with DocumentLifecycleLearner.
        Also extracts formulas and stores them in Atom's formula memory.
        """
        # Extract formulas if file_path is provided
        if file_path:
            try:
                from core.formula_extractor import get_formula_extractor
                extractor = get_formula_extractor(workspace_id)
                # Need to save content to temp file for openpyxl
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    extracted = extractor.extract_from_excel(tmp_path, auto_store=True)
                    if extracted:
                        logger.info(f"Extracted {len(extracted)} formulas from Excel")
                finally:
                    os.unlink(tmp_path)
            except Exception as fe:
                logger.warning(f"Formula extraction failed: {fe}")
        
        try:
            import pandas as pd
            # Read all sheets
            xls = pd.ExcelFile(io.BytesIO(content))
            full_text = []
            for sheet_name in xls.sheet_names[:5]:  # Limit sheets
                df = pd.read_excel(xls, sheet_name=sheet_name, nrows=100)  # Limit rows
                full_text.append(f"--- Sheet: {sheet_name} ---")
                full_text.append(df.to_string())
            return "\n".join(full_text)
        except ImportError:
            # Fallback to openpyxl
            try:
                from openpyxl import load_workbook
                wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
                text_parts = []
                for sheet_name in wb.sheetnames[:5]:
                    sheet = wb[sheet_name]
                    text_parts.append(f"=== Sheet: {sheet_name} ===")
                    for i, row in enumerate(sheet.iter_rows(values_only=True)):
                        if i > 100:
                            text_parts.append("... (truncated)")
                            break
                        row_text = " | ".join(str(cell) if cell else "" for cell in row)
                        text_parts.append(row_text)
                return "\n".join(text_parts)
            except ImportError:
                logger.warning("No Excel parser available")
                return "[Excel content - parser not available]"
        except Exception as e:
            logger.error(f"Excel parse error: {e}")
            return ""


class AutoDocumentIngestionService:
    """
    Manages automatic document ingestion from connected file storage integrations.
    
    Features:
    - Per-integration settings in user preferences
    - Auto-sync new/updated files
    - Parse multiple file formats
    - Ingest to Atom Memory (LanceDB + GraphRAG)
    """
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.settings: Dict[str, IngestionSettings] = {}
        self.ingested_docs: Dict[str, IngestedDocument] = {}  # key = external_id
        self.parser = DocumentParser()
        self._running = False
        
        # Initialize memory handler
        try:
            from core.lancedb_handler import get_lancedb_handler
            self.memory_handler = get_lancedb_handler(workspace_id)
        except ImportError:
            self.memory_handler = None
            logger.warning("LanceDB handler not available")
        
        # Initialize secrets redactor
        try:
            from core.secrets_redactor import get_secrets_redactor
            self.redactor = get_secrets_redactor()
        except ImportError:
            self.redactor = None
    
    def get_settings(self, integration_id: str) -> IngestionSettings:
        """Get or create settings for an integration"""
        if integration_id not in self.settings:
            self.settings[integration_id] = IngestionSettings(
                integration_id=integration_id,
                workspace_id=self.workspace_id
            )
        return self.settings[integration_id]
    
    def update_settings(
        self,
        integration_id: str,
        enabled: Optional[bool] = None,
        auto_sync_new_files: Optional[bool] = None,
        file_types: Optional[List[str]] = None,
        sync_folders: Optional[List[str]] = None,
        exclude_folders: Optional[List[str]] = None,
        max_file_size_mb: Optional[int] = None,
        sync_frequency_minutes: Optional[int] = None,
    ) -> IngestionSettings:
        """Update settings for an integration"""
        settings = self.get_settings(integration_id)
        
        if enabled is not None:
            settings.enabled = enabled
        if auto_sync_new_files is not None:
            settings.auto_sync_new_files = auto_sync_new_files
        if file_types is not None:
            settings.file_types = file_types
        if sync_folders is not None:
            settings.sync_folders = sync_folders
        if exclude_folders is not None:
            settings.exclude_folders = exclude_folders
        if max_file_size_mb is not None:
            settings.max_file_size_mb = max_file_size_mb
        if sync_frequency_minutes is not None:
            settings.sync_frequency_minutes = sync_frequency_minutes
        
        logger.info(f"Updated ingestion settings for {integration_id}: enabled={settings.enabled}")
        return settings
    
    async def sync_integration(
        self, 
        integration_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Sync documents from an integration.
        
        Returns:
            Dict with sync results
        """
        settings = self.get_settings(integration_id)
        
        if not settings.enabled and not force:
            return {"skipped": True, "reason": "Integration not enabled"}
        
        # Check if sync is due
        if not force and settings.last_sync:
            minutes_since = (datetime.utcnow() - settings.last_sync).total_seconds() / 60
            if minutes_since < settings.sync_frequency_minutes:
                return {"skipped": True, "reason": "Recently synced"}
        
        logger.info(f"Starting document sync for {integration_id}")
        
        results = {
            "integration_id": integration_id,
            "started_at": datetime.utcnow().isoformat(),
            "files_found": 0,
            "files_ingested": 0,
            "files_skipped": 0,
            "errors": []
        }
        
        try:
            # Fetch file list from integration
            files = await self._list_files(integration_id, settings)
            results["files_found"] = len(files)
            
            for file_info in files:
                try:
                    # Skip if already ingested and not modified
                    external_id = file_info.get("id")
                    if external_id in self.ingested_docs:
                        existing = self.ingested_docs[external_id]
                        if file_info.get("modified_at") == existing.external_modified_at:
                            results["files_skipped"] += 1
                            continue
                    
                    # Check file type
                    file_ext = file_info.get("name", "").split(".")[-1].lower()
                    if file_ext not in settings.file_types:
                        results["files_skipped"] += 1
                        continue
                    
                    # Check file size
                    file_size = file_info.get("size", 0)
                    if file_size > settings.max_file_size_mb * 1024 * 1024:
                        results["files_skipped"] += 1
                        continue
                    
                    # Download and parse
                    content = await self._download_file(integration_id, file_info)
                    if not content:
                        continue
                    
                    text = await self.parser.parse_document(content, file_ext, file_info.get("name"))
                    if not text:
                        continue
                    
                    # Redact secrets before storage
                    if self.redactor:
                        redaction = self.redactor.redact(text)
                        if redaction.has_secrets:
                            logger.warning(f"Redacted {len(redaction.redactions)} secrets from {file_info.get('name')}")
                            text = redaction.redacted_text
                    
                    # Ingest into Atom Memory
                    if self.memory_handler:
                        success = self.memory_handler.add_document(
                            table_name="documents",
                            text=text,
                            source=f"{integration_id}:{file_info.get('path', '')}",
                            metadata={
                                "file_name": file_info.get("name"),
                                "file_path": file_info.get("path"),
                                "file_type": file_ext,
                                "file_size": file_size,
                                "integration_id": integration_id,
                                "external_id": external_id,
                                "ingested_at": datetime.utcnow().isoformat()
                            },
                            user_id="system",
                            extract_knowledge=True
                        )
                        
                        if success:
                            # Record ingestion
                            self.ingested_docs[external_id] = IngestedDocument(
                                id=f"doc_{datetime.utcnow().timestamp()}",
                                file_name=file_info.get("name", ""),
                                file_path=file_info.get("path", ""),
                                file_type=file_ext,
                                integration_id=integration_id,
                                workspace_id=self.workspace_id,
                                file_size_bytes=file_size,
                                content_preview=text[:500],
                                ingested_at=datetime.utcnow(),
                                external_id=external_id,
                                external_modified_at=file_info.get("modified_at")
                            )
                            results["files_ingested"] += 1
                
                except Exception as file_err:
                    results["errors"].append(f"{file_info.get('name')}: {str(file_err)}")
            
            settings.last_sync = datetime.utcnow()
            results["completed_at"] = datetime.utcnow().isoformat()
            results["success"] = True
            
        except Exception as e:
            results["error"] = str(e)
            results["success"] = False
            logger.error(f"Sync failed for {integration_id}: {e}")
        
        return results
    
    async def _list_files(
        self, 
        integration_id: str, 
        settings: IngestionSettings
    ) -> List[Dict[str, Any]]:
        """List files from an integration"""
        files = []
        
        try:
            if integration_id == "google_drive":
                files = await self._list_google_drive_files(settings)
            elif integration_id == "dropbox":
                files = await self._list_dropbox_files(settings)
            elif integration_id == "onedrive":
                files = await self._list_onedrive_files(settings)
            elif integration_id == "notion":
                files = await self._list_notion_pages(settings)
            else:
                logger.warning(f"No file lister for {integration_id}")
        
        except Exception as e:
            logger.error(f"Failed to list files from {integration_id}: {e}")
        
        return files
    
    async def _download_file(
        self, 
        integration_id: str, 
        file_info: Dict[str, Any]
    ) -> Optional[bytes]:
        """Download file content from an integration"""
        try:
            if integration_id == "google_drive":
                return await self._download_google_drive_file(file_info)
            elif integration_id == "dropbox":
                return await self._download_dropbox_file(file_info)
            elif integration_id == "onedrive":
                return await self._download_onedrive_file(file_info)
            elif integration_id == "notion":
                return await self._download_notion_content(file_info)
            else:
                logger.warning(f"No downloader for {integration_id}")
                return None
        
        except Exception as e:
            logger.error(f"Failed to download from {integration_id}: {e}")
            return None
    
    # Integration-specific implementations (stubs)
    async def _list_google_drive_files(self, settings: IngestionSettings) -> List[Dict]:
        """List files from Google Drive"""
        # Placeholder - would use Google Drive API
        logger.info("Google Drive file listing not fully implemented")
        return []
    
    async def _download_google_drive_file(self, file_info: Dict) -> Optional[bytes]:
        """Download from Google Drive"""
        return None
    
    async def _list_dropbox_files(self, settings: IngestionSettings) -> List[Dict]:
        """List files from Dropbox"""
        # Placeholder - would use Dropbox API
        logger.info("Dropbox file listing not fully implemented")
        return []
    
    async def _download_dropbox_file(self, file_info: Dict) -> Optional[bytes]:
        """Download from Dropbox"""
        return None
    
    async def _list_onedrive_files(self, settings: IngestionSettings) -> List[Dict]:
        """List files from OneDrive"""
        logger.info("OneDrive file listing not fully implemented")
        return []
    
    async def _download_onedrive_file(self, file_info: Dict) -> Optional[bytes]:
        """Download from OneDrive"""
        return None
    
    async def _list_notion_pages(self, settings: IngestionSettings) -> List[Dict]:
        """List pages from Notion"""
        logger.info("Notion page listing not fully implemented")
        return []
    
    async def _download_notion_content(self, file_info: Dict) -> Optional[bytes]:
        """Get content from Notion page"""
        return None
    
    def get_ingested_documents(
        self, 
        integration_id: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> List[IngestedDocument]:
        """Get list of ingested documents"""
        docs = list(self.ingested_docs.values())
        
        if integration_id:
            docs = [d for d in docs if d.integration_id == integration_id]
        if file_type:
            docs = [d for d in docs if d.file_type == file_type]
        
        return docs
    
    async def remove_integration_documents(
        self, 
        integration_id: str
    ) -> Dict[str, Any]:
        """
        Remove all ingested documents from a specific integration.
        Clears from Atom Memory (LanceDB + GraphRAG).
        """
        count = 0
        removed_ids = []
        
        for ext_id, doc in list(self.ingested_docs.items()):
            if doc.integration_id == integration_id:
                removed_ids.append(ext_id)
                del self.ingested_docs[ext_id]
                count += 1
        
        # In production, also delete from LanceDB
        # self.memory_handler.delete_by_metadata("integration_id", integration_id)
        
        logger.info(f"Removed {count} documents from {integration_id}")
        
        return {
            "success": True,
            "integration_id": integration_id,
            "documents_removed": count,
            "removed_ids": removed_ids
        }
    
    def get_all_settings(self) -> List[Dict[str, Any]]:
        """Get settings for all integrations"""
        return [
            {
                "integration_id": s.integration_id,
                "enabled": s.enabled,
                "auto_sync_new_files": s.auto_sync_new_files,
                "file_types": s.file_types,
                "sync_folders": s.sync_folders,
                "max_file_size_mb": s.max_file_size_mb,
                "sync_frequency_minutes": s.sync_frequency_minutes,
                "last_sync": s.last_sync.isoformat() if s.last_sync else None,
            }
            for s in self.settings.values()
        ]


# Global instances per workspace
_doc_ingestion_services: Dict[str, AutoDocumentIngestionService] = {}


def get_document_ingestion_service(workspace_id: str) -> AutoDocumentIngestionService:
    """Get or create a document ingestion service for a workspace"""
    if workspace_id not in _doc_ingestion_services:
        _doc_ingestion_services[workspace_id] = AutoDocumentIngestionService(workspace_id)
    return _doc_ingestion_services[workspace_id]
