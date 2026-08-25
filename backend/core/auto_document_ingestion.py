"""
Automatic Document Ingestion Service for Atom Memory
Auto-ingests documents from connected file storage integrations (Google Drive, Dropbox, etc.)
Supports: Excel, PDF, DOC/DOCX, TXT, CSV, Markdown files
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

# Import for lazy loading to avoid circular imports
# from core.atom_meta_agent import handle_data_event_trigger

logger = logging.getLogger(__name__)

# Strong refs for fire-and-forget post-ingestion agent-trigger tasks (a bare
# create_task result can be garbage-collected mid-flight).
_pending_agent_trigger_tasks: set = set()


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
    # Freshness tracking (mirrors the ORM columns added in core/models.py).
    # See core/doc_freshness_service.py for semantics.
    source_url: Optional[str] = None
    source_content_hash: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    source_modified_at: Optional[datetime] = None
    freshness_status: str = "fresh"  # fresh|stale|outdated|removed|superseded
    superseded_by: Optional[str] = None  # id of a newer same-topic doc


class DocumentParser:
    """
    Parses various document formats and extracts text.
    Uses docling as primary parser with fallback to legacy parsers.
    Reuses existing parsers from DocumentLifecycleLearner where available.
    """
    
    # Docling processor (lazy-loaded)
    _docling_processor = None
    
    @classmethod
    def _get_docling_processor(cls):
        """Get or initialize the docling processor."""
        if cls._docling_processor is None:
            try:
                from core.docling_processor import get_docling_processor, is_docling_available
                if is_docling_available():
                    cls._docling_processor = get_docling_processor()
                    logger.info("Docling processor initialized for DocumentParser")
                else:
                    cls._docling_processor = False  # Mark as unavailable
            except ImportError:
                cls._docling_processor = False
                logger.debug("Docling not available, using fallback parsers")
        return cls._docling_processor if cls._docling_processor else None
    
    @staticmethod
    async def parse_document(file_content: bytes, file_type: str, file_name: str) -> str:
        """Parse document and extract text content"""
        try:
            # Try docling first for supported formats
            docling = DocumentParser._get_docling_processor()
            docling_formats = ['pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls', 'html', 'htm', 'png', 'jpg', 'jpeg', 'tiff']
            
            if docling and file_type in docling_formats:
                try:
                    result = await docling.process_document(
                        source=file_content,
                        file_type=file_type,
                        file_name=file_name,
                        export_format="markdown"
                    )
                    if result.get("success") and result.get("content"):
                        logger.info(f"Docling parsed {file_name}: {result.get('total_chars', 0)} chars")
                        return result["content"]
                    else:
                        logger.warning(f"Docling parse failed for {file_name}, using fallback")
                except Exception as e:
                    logger.warning(f"Docling error for {file_name}: {e}, using fallback")
            
            # Fallback to legacy parsers
            if file_type in ["txt", "md", "toml", "yaml", "yml", "xml", "html", "ini", "cfg", "conf", "log", "sql", "py", "ts", "js", "sh", "bat", "env"]:
                return file_content.decode("utf-8", errors="ignore")
            
            elif file_type == "json":
                try:
                    data = json.loads(file_content.decode("utf-8", errors="ignore"))
                    return json.dumps(data, indent=2)
                except Exception:
                    # Unparseable JSON is not raw text worth embedding —
                    # returning the broken bytes verbatim pollutes memory
                    # with junk rows.
                    return ""
            
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
    def _parse_csv(content: bytes, file_path: str = None, workspace_id: str = "default") -> str:
        """Parse CSV to text - reuses DataIngestionService logic.
        Also extracts implicit formulas from column patterns.
        """
        # Extract formulas from CSV if file_path provided
        if file_path:
            try:
                from core.formula_extractor import get_formula_extractor
                extractor = get_formula_extractor(workspace_id)
                # Need to save content to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='wb') as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    extracted = extractor.extract_from_csv(tmp_path, auto_store=True)
                    if extracted:
                        logger.info(f"Extracted {len(extracted)} formulas from CSV")
                finally:
                    os.unlink(tmp_path)
            except Exception as fe:
                logger.warning(f"CSV formula extraction failed: {fe}")
        
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
            # Use pypdf (PyPDF2 merged into pypdf package)
            import pypdf as PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages[:50]:  # Limit pages
                text_parts.append(page.extract_text() or "")
            return "\n\n".join(text_parts)
        except ImportError:
            logger.warning("pypdf not available, PDF parsing disabled")
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
    
    def __init__(self, workspace_id: str = "default"):
        # Per-workspace construction: settings, ingested-doc cache, LanceDB
        # handler and durable settings rows are all workspace-scoped. The old
        # fixed-"default" singleton meant every non-default workspace's sync
        # read and wrote the default workspace's stores.
        self.workspace_id = (workspace_id or "default").strip() or "default"
        self.settings: Dict[str, IngestionSettings] = {}
        self.ingested_docs: Dict[str, IngestedDocument] = {}  # key = external_id
        self.parser = DocumentParser()
        self._running = False

        # Initialize memory handler
        try:
            from core.lancedb_handler import get_lancedb_handler
            self.memory_handler = get_lancedb_handler(self.workspace_id)
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
            settings = IngestionSettings(
                integration_id=integration_id,
                workspace_id=self.workspace_id
            )
            # Hydrate from the durable row if one exists (restart survival).
            self._load_settings_row(integration_id, settings)
            self.settings[integration_id] = settings
        return self.settings[integration_id]

    def _settings_row_query(self, db, integration_id: str):
        from core.models import IngestionSettings as IngestionSettingsRow

        return (
            db.query(IngestionSettingsRow)
            .filter(
                IngestionSettingsRow.workspace_id == self.workspace_id,
                IngestionSettingsRow.integration_id == integration_id,
            )
            .first()
        )

    @staticmethod
    def _settings_persistence_enabled() -> bool:
        """Same kill switch as hybrid ingestion state (tests disable it)."""
        return os.getenv("ATOM_INGESTION_PERSIST_STATE", "true").lower() in (
            "1", "true", "yes",
        )

    def _load_settings_row(self, integration_id: str, settings: IngestionSettings) -> None:
        """Best-effort hydration from the ``ingestion_settings`` table.

        Settings previously lived only in this process's memory — a restart
        wiped enabled flags, folders and last_sync. Never raises."""
        if not self._settings_persistence_enabled():
            return
        try:
            from core.database import get_db_session

            with get_db_session() as db:
                row = self._settings_row_query(db, integration_id)
                if row is None:
                    return
                settings.enabled = bool(row.enabled)
                settings.auto_sync_new_files = bool(row.auto_sync_new_files)
                settings.file_types = list(row.file_types or settings.file_types)
                settings.sync_folders = list(row.sync_folders or [])
                settings.exclude_folders = list(row.exclude_folders or [])
                settings.max_file_size_mb = row.max_file_size_mb or settings.max_file_size_mb
                settings.sync_frequency_minutes = (
                    row.sync_frequency_minutes or settings.sync_frequency_minutes
                )
                if row.last_sync is not None:
                    # SQLite returns naive datetimes; sync math compares
                    # against timezone-aware now().
                    settings.last_sync = (
                        row.last_sync.replace(tzinfo=timezone.utc)
                        if row.last_sync.tzinfo is None
                        else row.last_sync
                    )
        except Exception as e:
            logger.debug(f"Ingestion settings load skipped for {integration_id}: {e}")

    def _persist_settings(self, settings: IngestionSettings) -> None:
        """Best-effort durable copy of ingestion settings. Never raises.

        Only the document-ingestion columns are touched — hybrid ingestion
        stores its pipeline state (entity_types, sync_mode, …) in the same
        rows and must survive this upsert."""
        if not self._settings_persistence_enabled():
            return
        try:
            from core.database import get_db_session

            with get_db_session() as db:
                row = self._settings_row_query(db, settings.integration_id)
                if row is None:
                    from core.models import IngestionSettings as IngestionSettingsRow

                    row = IngestionSettingsRow(
                        workspace_id=self.workspace_id,
                        integration_id=settings.integration_id,
                    )
                    db.add(row)
                row.enabled = settings.enabled
                row.auto_sync_new_files = settings.auto_sync_new_files
                row.file_types = list(settings.file_types or [])
                row.sync_folders = list(settings.sync_folders or [])
                row.exclude_folders = list(settings.exclude_folders or [])
                row.max_file_size_mb = settings.max_file_size_mb
                row.sync_frequency_minutes = settings.sync_frequency_minutes
                row.last_sync = settings.last_sync
                db.commit()
        except Exception as e:
            logger.warning(
                f"Failed to persist ingestion settings for {settings.integration_id}: {e}"
            )
    
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
        self._persist_settings(settings)
        return settings

    async def process_file_bytes(
        self,
        content: bytes,
        file_name: str,
        source: str = "upload",
        user_id: str = "system",
        workspace_id: Optional[str] = None,
        role: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        external_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parse raw file bytes and ingest the extracted text into Atom memory.

        Shared ingestion path used by cloud-drive connectors (OneDrive, Zoho
        WorkDrive) and direct uploads. Parses with DocumentParser, redacts
        secrets, and writes to LanceDB (documents table) with knowledge
        extraction enabled.

        Args:
            content: Raw file bytes.
            file_name: File name (used to infer type and metadata).
            source: Source label (e.g. "onedrive", "zoho_workdrive").
            user_id: Owning user id.
            workspace_id: Optional workspace override (defaults to service default).
            role: Optional AI-employee role (AgentRegistry.category, lowercased)
                the ingested file is relevant to. Tagged in the LanceDB metadata
                so role-aware recall (WorldModelService) surfaces it to the right
                employee's memory. None/empty = general knowledge.
            external_id: SOURCE-NATIVE unique id (Drive fileId, OneDrive
                driveItem id, Box file id, Dropbox path …). Preferred identity —
                titles are not identity. Falls back to a SHA-256 of the
                extracted text (content addressing) when absent.

        Returns:
            Dict with ``status``, ``file_name``, ``chars_ingested``, ``doc_id``.
        """
        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if not file_ext:
            return {"status": "skipped", "reason": "no_file_extension", "file_name": file_name}

        try:
            text = await self.parser.parse_document(content, file_ext, file_name)
        except Exception as parse_err:
            logger.warning(f"Failed to parse {file_name} ({file_ext}): {parse_err}")
            return {"status": "error", "reason": "parse_failed", "file_name": file_name}

        # Blank-only text is junk; short-but-real content (e.g. "data") is a
        # valid document and must not be dropped.
        if not text or not text.strip():
            return {"status": "skipped", "reason": "no_text", "file_name": file_name}

        # Redact secrets before storage
        if self.redactor:
            try:
                redaction = self.redactor.redact(text)
                if getattr(redaction, "has_secrets", False):
                    logger.info(f"Redacted secrets from {file_name}")
                    text = redaction.redacted_text
            except Exception as redact_err:
                logger.debug(f"Secrets redaction skipped for {file_name}: {redact_err}")

        ws_id = workspace_id or self.workspace_id
        chars_ingested = 0

        # Per-workspace handler: the workspace override previously only
        # stamped metadata — the row still landed in the default workspace's
        # store, invisible to that workspace's recall.
        _handler = self.memory_handler
        if ws_id and ws_id != self.workspace_id:
            try:
                if not hasattr(self, "_ws_handlers"):
                    self._ws_handlers: Dict[str, Any] = {}
                if ws_id not in self._ws_handlers:
                    from core.lancedb_handler import get_lancedb_handler

                    self._ws_handlers[ws_id] = get_lancedb_handler(ws_id)
                _handler = self._ws_handlers[ws_id]
            except Exception as ws_handler_err:  # noqa: BLE001 — fall back to default
                logger.warning(
                    f"workspace handler unavailable for {ws_id}, using default: {ws_handler_err}"
                )
                _handler = self.memory_handler

        # Join-key bridge (hybrid search, Step 1): the file-ingest path creates
        # no PG IngestedDocument row, so vector hits from here can't resolve to
        # documents.cat. Stamp a stable doc_id + source_type:"file" so the
        # hybrid service can flag these as bridged:false (no PG row) rather
        # than silently returning unresolvable hits.
        # Identity key (idempotency contract): prefer the SOURCE-NATIVE id the
        # connector passes (external_id param, else extra_metadata fallback);
        # otherwise fall back to a SHA-256 of the extracted text
        # (content-addressing: identical content = one row, any filename).
        # The id is SOURCE-SCOPED — two integrations may reuse the same raw
        # external id string, and one file's refresh must never delete the
        # other's row. Never key on file NAME.
        import hashlib as _hashlib

        from core.doc_freshness_service import hash_text

        _content_hash = hash_text(text)
        _external_id = str(
            external_id or (extra_metadata or {}).get("external_id") or ""
        ).strip()
        if _external_id:
            _identity_input = f"{source}:{_external_id}"
            _file_doc_id = f"ext_{_hashlib.sha1(_identity_input.encode('utf-8')).hexdigest()[:24]}"
        else:
            _file_doc_id = "doc_" + _hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]

        _meta: Dict[str, Any] = {
            "file_name": file_name,
            "file_type": file_ext,
            "file_size": len(content),
            "integration_id": source,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "pg_document_id": _file_doc_id,
            "source_type": "file",
            "source_content_hash": _content_hash,
            "freshness_status": "fresh",
        }
        if _external_id:
            _meta["external_id"] = _external_id
        # Connector-supplied context (e.g. WorkDrive folder path / root)
        if extra_metadata:
            _meta.update({k: v for k, v in extra_metadata.items() if v})
        # AI-employee relevance tag (Round 80): lets role-aware recall surface
        # this file to the employee whose role it was ingested for.
        if role:
            _meta["role"] = str(role).lower()

        if _handler:
            try:
                # Shared upsert contract (hash-skip / delete prior / write).
                from core.vector_upsert import upsert_document

                _upsert_status = await upsert_document(
                    _handler,
                    table_name="documents",
                    text=text,
                    doc_id=_file_doc_id,
                    source=f"{source}:{file_name}",
                    metadata=_meta,
                    user_id=user_id,
                    workspace_id=ws_id,
                )
                if _upsert_status == "written":
                    chars_ingested = len(text)
                    logger.info(f"Ingested {file_name} ({chars_ingested} chars) from {source}")
                else:
                    return {
                        "status": "skipped",
                        "reason": "unchanged",
                        "file_name": file_name,
                        "chars_ingested": 0,
                        "source": source,
                        "doc_id": _file_doc_id,
                    }
            except Exception as ingest_err:
                logger.error(f"Failed to ingest {file_name} to memory: {ingest_err}")
                return {"status": "error", "reason": "ingest_failed", "file_name": file_name}
        else:
            logger.warning("No memory_handler available; file content not stored")

        return {
            "status": "ingested" if chars_ingested else "skipped",
            "file_name": file_name,
            "chars_ingested": chars_ingested,
            "source": source,
            "doc_id": _file_doc_id,
        }

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
            minutes_since = (datetime.now(timezone.utc) - settings.last_sync).total_seconds() / 60
            if minutes_since < settings.sync_frequency_minutes:
                return {"skipped": True, "reason": "Recently synced"}
        
        logger.info(f"Starting document sync for {integration_id}")
        
        results = {
            "integration_id": integration_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "files_found": 0,
            "files_ingested": 0,
            "files_skipped": 0,
            "errors": [],
            "newly_ingested_files": []
        }
        
        try:
            # Fetch file list from integration
            files = await self._list_files(integration_id, settings)
            results["files_found"] = len(files)

            # Track which external_ids the source currently reports. Used after
            # the loop to tombstone docs that were deleted upstream.
            seen_external_ids: Set[str] = set()

            for file_info in files:
                # LAMBDA SAFEGUARD: Check if we are approaching timeout (10 mins)
                # If running longer than 10 minutes, stop and let the next scheduled run pick up the rest
                if (datetime.now(timezone.utc) - datetime.fromisoformat(results["started_at"])).total_seconds() > 600:
                    logger.warning(f"Ingestion time limit reached (10m) for {integration_id}. Stopping early.")
                    results["errors"].append("Time limit reached - continuing in next run")
                    break

                try:
                    # Skip if already ingested and not modified
                    external_id = file_info.get("id")
                    if external_id:
                        seen_external_ids.add(external_id)
                    existing: Optional[IngestedDocument] = None
                    if external_id in self.ingested_docs:
                        existing = self.ingested_docs[external_id]
                        if file_info.get("modified_at") == existing.external_modified_at:
                            results["files_skipped"] += 1
                            continue
                        # Source modified_at differs → the stored copy is stale
                        # even if the re-download below later fails. Record it
                        # now so retrieval can downrank it.
                        try:
                            self._mark_doc_stale(existing, reason="source_modified_at_changed")
                        except Exception as stale_err:
                            logger.warning(f"Failed to mark stale for {external_id}: {stale_err}")
                    
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
                        from core.doc_freshness_service import (
                            hash_text,
                            extra_columns_for_ingest,
                        )

                        source_modified = file_info.get("modified_at")
                        content_hash = hash_text(text)
                        # Content-level idempotency: source modified_at can
                        # change (touch/rename) without the bytes changing —
                        # skip the rewrite and just refresh the cache marker.
                        if existing and existing.source_content_hash == content_hash:
                            existing.external_modified_at = source_modified
                            results["files_skipped"] += 1
                            continue
                        # Join-key bridge (hybrid search, Step 1): generate the PG
                        # row id BEFORE the LanceDB write and pass it as doc_id so
                        # the LanceDB documents row id equals the IngestedDocument
                        # id. Vector hits then resolve directly to
                        # documents.cat("knowledge/documents/<id>") paths.
                        new_id = f"doc_{datetime.now(timezone.utc).timestamp()}"
                        # Source URL: best-effort canonical locator from the
                        # integration-provided metadata.
                        source_url = (
                            file_info.get("url")
                            or file_info.get("web_url")
                            or file_info.get("webViewLink")
                            or f"{integration_id}:{file_info.get('path', '')}"
                        )

                        success = await asyncio.to_thread(
                            self.memory_handler.add_document,
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
                                "ingested_at": datetime.now(timezone.utc).isoformat(),
                                "source_url": source_url,
                                "source_content_hash": content_hash,
                                "freshness_status": "fresh",
                                "pg_document_id": new_id,
                                "source_type": "ingested",
                            },
                            user_id="system",
                            doc_id=new_id,
                            # Freshness columns as TOP-LEVEL filterable columns
                            # (not buried in the metadata JSON blob — see the
                            # warning in lancedb_handler.py add_document).
                            extra_columns=extra_columns_for_ingest(
                                freshness_status="fresh",
                                source_modified_at=source_modified
                                if isinstance(source_modified, datetime)
                                else None,
                                source_url=source_url,
                            ),
                        )

                        if success:
                            # Re-ingest of a modified file: remove the OLD
                            # vector row so search returns exactly one (fresh)
                            # copy instead of a stale+fresh duplicate pair.
                            if existing and existing.id and existing.id != new_id:
                                try:
                                    await asyncio.to_thread(
                                        self.memory_handler.delete_documents_by_id,
                                        "documents",
                                        existing.id,
                                    )
                                except Exception as old_del_err:  # noqa: BLE001 — best-effort cleanup
                                    logger.warning(
                                        f"Failed to remove superseded row {existing.id}: {old_del_err}"
                                    )
                            # Record ingestion (in-memory cache + DB for
                            # cross-run freshness tracking).
                            self.ingested_docs[external_id] = IngestedDocument(
                                id=new_id,
                                file_name=file_info.get("name", ""),
                                file_path=file_info.get("path", ""),
                                file_type=file_ext,
                                integration_id=integration_id,
                                workspace_id=self.workspace_id,
                                file_size_bytes=file_size,
                                content_preview=text[:500],
                                ingested_at=datetime.now(timezone.utc),
                                external_id=external_id,
                                external_modified_at=source_modified,
                                source_url=source_url,
                                source_content_hash=content_hash,
                                last_verified_at=datetime.now(timezone.utc),
                                source_modified_at=source_modified
                                if isinstance(source_modified, datetime)
                                else None,
                                freshness_status="fresh",
                            )
                            try:
                                self._persist_freshness_on_ingest(
                                    self.ingested_docs[external_id],
                                    source_url=source_url,
                                    content_hash=content_hash,
                                    source_modified_at=source_modified
                                    if isinstance(source_modified, datetime)
                                    else None,
                                )
                            except Exception as persist_err:
                                logger.warning(
                                    f"Freshness persist failed for {external_id}: {persist_err}"
                                )
                            results["files_ingested"] += 1
                            results["newly_ingested_files"].append(file_info.get("name"))

                            # Supersession: does this new doc obsolete an
                            # older same-topic doc in the same workspace?
                            try:
                                self._maybe_supersede_older_docs(
                                    text=text,
                                    new_doc_id=new_id,
                                    source_modified_at=source_modified,
                                )
                            except Exception as sup_err:
                                logger.warning(f"Supersession check failed for {new_id}: {sup_err}")
                
                except Exception as file_err:
                    results["errors"].append(f"{file_info.get('name')}: {str(file_err)}")

            # Reevaluate freshness across the workspace: tombstone docs that
            # were deleted upstream (absent from seen_external_ids) and age out
            # docs whose last verification is beyond the TTL.
            try:
                reeval = self._reevaluate_workspace(seen_external_ids)
                results["freshness"] = reeval
            except Exception as reeval_err:
                logger.warning(f"Freshness reevaluate failed for {integration_id}: {reeval_err}")
                results["freshness"] = {"error": str(reeval_err)}

            settings.last_sync = datetime.now(timezone.utc)
            self._persist_settings(settings)
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["success"] = True
            
            # TRIGGER AGENT IF FILES WERE INGESTED
            if results["files_ingested"] > 0:
                try:
                    from core.atom_meta_agent import handle_data_event_trigger
                    logger.info(f"Triggering Atom Agent for {results['files_ingested']} new documents in {integration_id}")

                    # Fire-and-forget (resolved: create_task, NOT await).
                    # Awaiting ran a FULL meta-agent turn inline — sync
                    # close-out blocked for minutes on LLM latency/retries.
                    # Mirrors the turn-fact extraction pending-set pattern:
                    # strong task ref prevents GC; done-callback discards.
                    _trigger_task = asyncio.create_task(handle_data_event_trigger(
                        event_type="document_ingestion",
                        data={
                            "integration_id": integration_id,
                            "count": results["files_ingested"],
                            "files": results["newly_ingested_files"]
                        },
                        workspace_id="default"
                    ))
                    _pending_agent_trigger_tasks.add(_trigger_task)
                    _trigger_task.add_done_callback(
                        lambda t: _pending_agent_trigger_tasks.discard(t)
                    )
                except Exception as trigger_err:
                    logger.warning(f"Failed to trigger agent after ingestion: {trigger_err}")
            
            
        except Exception as e:
            results["error"] = str(e)
            results["success"] = False
            logger.error(f"Sync failed for {integration_id}: {e}")

        return results

    # ====================================================================
    # Freshness helpers
    # ====================================================================

    def _freshness_session(self):
        """Open a short-lived DB session for freshness persistence.

        Mirrors the pattern in IngestionPipelineService._record_doc_ingestion
        (SessionLocal() opened and closed per call) so we don't leak a long-
        lived session across the async sync loop.
        """
        from core.database import SessionLocal
        return SessionLocal()

    def _persist_freshness_on_ingest(
        self,
        doc: IngestedDocument,
        *,
        source_url: Optional[str],
        content_hash: str,
        source_modified_at: Optional[datetime],
    ) -> None:
        """Upsert the IngestedDocument row and stamp it fresh.

        Persists to the ``ingested_documents`` table so freshness survives
        across sync runs (the in-memory ``self.ingested_docs`` cache is lost
        on restart). Also writes the new freshness columns.
        """
        from core.models import IngestedDocument as IngestedDocumentModel
        from core.doc_freshness_service import DocFreshnessService

        session = self._freshness_session()
        try:
            existing = (
                session.query(IngestedDocumentModel)
                .filter(
                    IngestedDocumentModel.workspace_id == doc.workspace_id,
                    IngestedDocumentModel.external_id == doc.external_id,
                )
                .first()
            )
            if existing is None:
                existing = IngestedDocumentModel(
                    id=doc.id,
                    workspace_id=doc.workspace_id,
                    file_name=doc.file_name,
                    file_path=doc.file_path,
                    file_type=doc.file_type,
                    integration_id=doc.integration_id,
                    file_size_bytes=doc.file_size_bytes,
                    content_preview=doc.content_preview,
                    external_id=doc.external_id,
                    external_modified_at=doc.external_modified_at,
                )
                session.add(existing)
            else:
                # Keep columns in sync with the freshly fetched version.
                existing.file_name = doc.file_name
                existing.file_path = doc.file_path
                existing.file_type = doc.file_type
                existing.file_size_bytes = doc.file_size_bytes
                existing.content_preview = doc.content_preview
                existing.external_modified_at = doc.external_modified_at

            svc = DocFreshnessService(session, workspace_id=doc.workspace_id)
            svc.mark_on_ingest(
                existing,
                source_url=source_url,
                content_hash=content_hash,
                source_modified_at=source_modified_at,
            )
        finally:
            session.close()

    def _mark_doc_stale(self, doc: IngestedDocument, *, reason: str) -> None:
        """Record a doc as stale (source changed) before re-ingest."""
        from core.models import IngestedDocument as IngestedDocumentModel
        from core.doc_freshness_service import DocFreshnessService

        doc.freshness_status = "stale"
        session = self._freshness_session()
        try:
            row = (
                session.query(IngestedDocumentModel)
                .filter(
                    IngestedDocumentModel.workspace_id == doc.workspace_id,
                    IngestedDocumentModel.external_id == doc.external_id,
                )
                .first()
            )
            if row is not None:
                svc = DocFreshnessService(session, workspace_id=doc.workspace_id)
                svc.mark_stale(row, reason=reason)
        finally:
            session.close()

    def _reevaluate_workspace(self, seen_external_ids: Set[str]) -> Dict[str, Any]:
        """Recompute freshness for all docs in this workspace.

        Returns the summary dict from DocFreshnessService.reevaluate_workspace.
        """
        from core.doc_freshness_service import DocFreshnessService

        session = self._freshness_session()
        try:
            svc = DocFreshnessService(session, workspace_id=self.workspace_id)
            summary = svc.reevaluate_workspace(self.workspace_id, seen_external_ids)
            return summary.as_dict()
        finally:
            session.close()

    def _maybe_supersede_older_docs(
        self,
        *,
        text: str,
        new_doc_id: str,
        source_modified_at: Optional[datetime],
    ) -> None:
        """Detect whether this newly ingested doc supersedes older same-topic docs.

        Hybrid detection (see doc_freshness_service.detect_supersession):
        semantic near-duplicate OR entity overlap, confirmed by a newer-
        timestamp heuristic. Candidates are marked ``superseded`` and linked,
        and the Postgres GraphRAG cascade stamps their derived nodes/edges.
        """
        from core.doc_freshness_service import (
            DocFreshnessService,
            detect_supersession,
            doc_ts,
        )
        from core.models import IngestedDocument as IngestedDocumentModel

        session = self._freshness_session()
        try:
            # Gather older docs in the same workspace that are still
            # fresh/stale (candidates for supersession). Bounded by recent docs
            # to keep the per-ingest cost predictable.
            older_rows = (
                session.query(IngestedDocumentModel)
                .filter(
                    IngestedDocumentModel.workspace_id == self.workspace_id,
                    IngestedDocumentModel.id != new_doc_id,
                    IngestedDocumentModel.freshness_status.in_(["fresh", "stale"]),
                )
                .order_by(IngestedDocumentModel.ingested_at.desc())
                .limit(50)
                .all()
            )
            if not older_rows:
                return

            older_docs = [
                {
                    "doc_id": r.id,
                    "text": r.content_preview or "",
                    "ingested_at": r.ingested_at,
                    "external_modified_at": r.external_modified_at or r.source_modified_at,
                    "freshness_status": r.freshness_status,
                }
                for r in older_rows
            ]

            # Newer doc's embedding + entity set.
            newer_embedding = None
            if self.memory_handler is not None:
                try:
                    newer_embedding = self.memory_handler.embed_text(text)
                    if newer_embedding is not None and hasattr(newer_embedding, "tolist"):
                        newer_embedding = newer_embedding.tolist()
                except Exception:
                    newer_embedding = None

            svc = DocFreshnessService(session, workspace_id=self.workspace_id)
            newer_entities = svc.entity_set_for_doc(new_doc_id)
            older_entity_sets = {r.id: svc.entity_set_for_doc(r.id) for r in older_rows}

            candidates = detect_supersession(
                newer_doc_id=new_doc_id,
                newer_text=text,
                newer_embedding=newer_embedding,
                newer_entities=newer_entities,
                newer_ts=source_modified_at if isinstance(source_modified_at, datetime) else None,
                older_docs=older_docs,
                older_entity_sets=older_entity_sets,
            )
            if not candidates:
                return

            logger.info(
                f"Supersession: {new_doc_id} obsoletes {len(candidates)} older doc(s)"
            )
            svc.apply_supersession(
                candidates,
                new_doc_id,
                cascade_to_graph=svc.cascade_graph_supersession,
            )
        finally:
            session.close()

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
    
    # Integration-specific implementations
    async def _list_google_drive_files(self, settings: IngestionSettings) -> List[Dict]:
        """List files from Google Drive"""
        try:
            import os

            from integrations.google_drive_service import google_drive_service

            access_token = os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN")
            if not access_token:
                logger.warning("Google Drive access token not configured")
                return []

            result = await google_drive_service.list_files(
                access_token=access_token,
                page_size=getattr(settings, "max_files", 100)
            )

            if result["status"] == "success":
                files = result["data"].get("files", [])
                logger.info(f"Listed {len(files)} files from Google Drive")
                return files
            else:
                logger.error(f"Failed to list Google Drive files: {result.get('message')}")
                return []

        except Exception as e:
            logger.error(f"Google Drive file listing error: {e}")
            return []

    async def _download_google_drive_file(self, file_info: Dict) -> Optional[bytes]:
        """Download from Google Drive"""
        try:
            import os
            import httpx

            access_token = os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN")
            if not access_token:
                logger.warning("Google Drive access token not configured")
                return None

            file_id = file_info.get("id")
            if not file_id:
                return None

            # Get download URL based on MIME type
            mime_type = file_info.get("mimeType", "")
            if "google-apps" in mime_type:
                # Google Docs format - need to export
                export_formats = {
                    "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }
                export_mime = export_formats.get(mime_type, "application/pdf")
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={export_mime}"
            else:
                # Regular file - direct download
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=60.0
                )
                response.raise_for_status()
                return response.content

        except Exception as e:
            logger.error(f"Google Drive download error: {e}")
            return None
    
    async def _list_dropbox_files(self, settings: IngestionSettings) -> List[Dict]:
        """List files from Dropbox"""
        try:
            import os
            import httpx

            access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
            if not access_token:
                logger.warning("Dropbox access token not configured")
                return []

            # List files in Dropbox using API v2
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }

                # Use list_folder endpoint
                response = await client.post(
                    "https://api.dropboxapi.com/2/files/list_folder",
                    headers=headers,
                    json={"path": "", "recursive": False, "limit": getattr(settings, "max_files", 100)},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                files = []
                for entry in data.get("entries", []):
                    if entry.get(".tag") == "file":
                        files.append({
                            "id": entry.get("id"),
                            "name": entry.get("name"),
                            "path_lower": entry.get("path_lower"),
                            "size": entry.get("size"),
                            "client_modified": entry.get("client_modified"),
                            "server_modified": entry.get("server_modified")
                        })

                logger.info(f"Listed {len(files)} files from Dropbox")
                return files

        except Exception as e:
            logger.error(f"Dropbox file listing error: {e}")
            return []

    async def _download_dropbox_file(self, file_info: Dict) -> Optional[bytes]:
        """Download from Dropbox"""
        try:
            import os
            import httpx

            access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
            if not access_token:
                logger.warning("Dropbox access token not configured")
                return None

            path = file_info.get("path_lower")
            if not path:
                return None

            # Download file using Dropbox API
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }

                # Get temporary download link
                post_response = await client.post(
                    "https://api.dropboxapi.com/2/files/get_temporary_link",
                    headers=headers,
                    json={"path": path},
                    timeout=30.0
                )
                post_response.raise_for_status()
                link_data = post_response.json()

                # Download file content
                download_url = link_data.get("link")
                if download_url:
                    download_response = await client.get(download_url, timeout=60.0)
                    download_response.raise_for_status()
                    return download_response.content

        except Exception as e:
            logger.error(f"Dropbox download error: {e}")
            return None
    
    async def _list_onedrive_files(self, settings: IngestionSettings) -> List[Dict]:
        """List files from OneDrive via the Graph-backed integration service."""
        try:
            import os

            from integrations.onedrive_service import onedrive_service

            access_token = os.getenv("ONEDRIVE_ACCESS_TOKEN")
            if not access_token:
                logger.warning("OneDrive access token not configured")
                return []

            result = await onedrive_service.list_files(
                access_token=access_token,
                page_size=getattr(settings, "max_files", 100),
            )
            if result.get("status") != "success":
                logger.error(f"Failed to list OneDrive files: {result.get('message')}")
                return []

            files = []
            for item in result.get("data", {}).get("value", []):
                # Skip folders — only file items have a "file" facet.
                if "file" not in (item or {}):
                    continue
                files.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "path": item.get("parentReference", {}).get("path", ""),
                    "size": item.get("size", 0),
                    "modified_at": item.get("lastModifiedDateTime"),
                    "url": item.get("webUrl"),
                })
            logger.info(f"Listed {len(files)} files from OneDrive")
            return files

        except Exception as e:
            logger.error(f"OneDrive file listing error: {e}")
            return []

    async def _download_onedrive_file(self, file_info: Dict) -> Optional[bytes]:
        """Download from OneDrive via the Graph-backed integration service."""
        try:
            import os

            from integrations.onedrive_service import onedrive_service

            access_token = os.getenv("ONEDRIVE_ACCESS_TOKEN")
            if not access_token:
                logger.warning("OneDrive access token not configured")
                return None

            file_id = file_info.get("id")
            if not file_id:
                return None
            return await onedrive_service.download_file_bytes(
                access_token=access_token, file_id=file_id
            )

        except Exception as e:
            logger.error(f"OneDrive download error: {e}")
            return None

    async def _list_notion_pages(self, settings: IngestionSettings) -> List[Dict]:
        """List pages from Notion via the search endpoint."""
        try:
            import os

            from integrations.notion_service import NotionService

            token = os.getenv("NOTION_ACCESS_TOKEN") or os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
            if not token:
                logger.warning("Notion access token not configured")
                return []

            notion = NotionService(config={"access_token": token})
            data = notion.search(page_size=getattr(settings, "max_files", 100))
            pages = []
            for item in data.get("results", []):
                if item.get("object") != "page":
                    continue
                # Best-effort title: check common title property locations.
                title = item.get("url", "").rsplit("/", 1)[-1] or "Untitled"
                props = item.get("properties", {})
                for value in props.values():
                    if value.get("type") == "title" and value.get("title"):
                        title = "".join(
                            part.get("plain_text", "") for part in value["title"]
                        )
                        break
                pages.append({
                    "id": item.get("id"),
                    "name": f"{title}.md",
                    "path": title,
                    "size": 0,
                    "modified_at": item.get("last_edited_time"),
                    "url": item.get("url"),
                })
            logger.info(f"Listed {len(pages)} pages from Notion")
            return pages

        except Exception as e:
            logger.error(f"Notion page listing error: {e}")
            return []

    async def _download_notion_content(self, file_info: Dict) -> Optional[bytes]:
        """Flatten a Notion page's blocks into markdown-ish text bytes."""
        try:
            import os

            from integrations.notion_service import NotionService

            token = os.getenv("NOTION_ACCESS_TOKEN") or os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
            if not token:
                logger.warning("Notion access token not configured")
                return None

            page_id = file_info.get("id")
            if not page_id:
                return None

            notion = NotionService(config={"access_token": token})
            parts: List[str] = [f"# {file_info.get('path') or file_info.get('name') or page_id}"]
            cursor = None
            while True:
                kwargs = {"page_size": 100}
                if cursor:
                    kwargs["start_cursor"] = cursor
                data = notion.get_block_children(page_id, **kwargs)
                results = data.get("results", [])
                if not results and not cursor:
                    break
                for block in results:
                    # Any rich-text-bearing sub-key of the block payload.
                    for value in block.values():
                        if isinstance(value, dict) and isinstance(value.get("rich_text"), list):
                            text = "".join(
                                rt.get("plain_text", "")
                                for rt in value["rich_text"]
                            )
                            if text:
                                prefix = "- " if block.get("type") == "bulleted_list_item" else ""
                                parts.append(prefix + text)
                        elif isinstance(value, dict) and isinstance(value.get("title"), list):
                            text = "".join(
                                rt.get("plain_text", "") for rt in value["title"]
                            )
                            if text:
                                parts.append(text)
                cursor = data.get("next_cursor")
                if not data.get("has_more") or not cursor:
                    break

            return "\n\n".join(parts).encode("utf-8")

        except Exception as e:
            logger.error(f"Notion content download error: {e}")
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
                # Real vector cleanup: delete the stored row by its doc id.
                if self.memory_handler and doc.id:
                    try:
                        await asyncio.to_thread(
                            self.memory_handler.delete_documents_by_id,
                            "documents",
                            doc.id,
                        )
                    except Exception as del_err:  # noqa: BLE001 — removal best-effort
                        logger.warning(f"LanceDB delete failed for {doc.id}: {del_err}")
                del self.ingested_docs[ext_id]
                count += 1

        # Best-effort removal of the durable freshness rows so deleted docs
        # don't reappear in freshness reevaluations.
        try:
            from core.models import IngestedDocument as IngestedDocumentRow

            with self._freshness_session() as db:
                db.query(IngestedDocumentRow).filter(
                    IngestedDocumentRow.integration_id == integration_id
                ).delete(synchronize_session=False)
                db.commit()
        except Exception as db_err:  # noqa: BLE001
            logger.warning(f"IngestedDocument cleanup skipped for {integration_id}: {db_err}")

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


# Per-workspace singleton registry (R84d). ``_doc_ingestion_service`` is kept
# as the "default"-workspace alias for backward compatibility.
_doc_ingestion_service: Optional[AutoDocumentIngestionService] = None
_doc_ingestion_services: Dict[str, AutoDocumentIngestionService] = {}


def get_document_ingestion_service(
    workspace_id: str = "default",
) -> AutoDocumentIngestionService:
    """Get or create the document ingestion service for a workspace.

    One instance per workspace: each binds its own LanceDB handler, settings
    cache and durable ``ingestion_settings`` rows to that workspace. Callers
    that pass no workspace get the shared "default" instance (previous
    behavior).
    """
    global _doc_ingestion_service
    ws = (workspace_id or "default").strip() or "default"
    service = _doc_ingestion_services.get(ws)
    if service is None:
        service = AutoDocumentIngestionService(workspace_id=ws)
        _doc_ingestion_services[ws] = service
        if ws == "default":
            _doc_ingestion_service = service
    return service


def reset_document_ingestion_services() -> None:
    """Drop all cached per-workspace instances (test isolation helper)."""
    global _doc_ingestion_service
    _doc_ingestion_services.clear()
    _doc_ingestion_service = None


# Alias for backward compatibility with tests
AutoDocumentIngestion = AutoDocumentIngestionService
