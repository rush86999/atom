"""
ATOM Document Logic Service
Unified ingestion for Google Docs, Word, Excel, and PDF to extract business rules.
"""

from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, List, Optional
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException


try:
    from ai_enhanced_service import AIRequest, AITaskType, ai_enhanced_service

    from integrations.atom_ingestion_pipeline import RecordType, atom_ingestion_pipeline
except ImportError:
    logging.warning("Core services not available for Document Logic Service")

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    GOOGLE_DOC = "google_doc"
    MS_WORD = "docx"
    MS_EXCEL = "xlsx"
    PDF = "pdf"
    CSV = "csv"

class DocumentLogicService:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    async def ingest_document(self, file_path: str, doc_type: DocumentType, workspace_id: str):
        """
        Parses a document and extracts logic/rules to be stored in LanceDB.
        """
        # Start audit logging
        audit_ctx = log_integration_attempt("document_logic", "ingest_document", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("document_logic"):
                logger.warning(f"Circuit breaker is open for document_logic")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Document_logic integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("document_logic")
            if is_limited:
                logger.warning(f"Rate limit exceeded for document_logic")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for document_logic"
                )
        except HTTPException:
            raise
        except Exception as e:
            log_integration_complete(audit_ctx, error=e)
            raise

        logger.info(f"Ingesting {doc_type.value} from {file_path}")
        
        # 1. Extraction (Simulated for Now)
        content = self._extract_text(file_path, doc_type)
        
        # 2. AI Processing: Extract Logic Snippets
        logic_snippets = await self._extract_logic_with_ai(content)
        
        # 3. Ingest to Memory
        for snippet in logic_snippets:
            atom_ingestion_pipeline.ingest_record(
                app_type=doc_type.value,
                record_type="document",
                data={
                    "file_path": file_path,
                    "logic_snippet": snippet,
                    "workspace_id": workspace_id,
                    "ingested_at": datetime.now().isoformat()
                }
            )
        
        return {"snippets_extracted": len(logic_snippets)}

    def _extract_text(self, file_path: str, doc_type: DocumentType) -> str:
        # Placeholder for actual library-based extraction (PyPDF2, openpyxl, etc.)
        return "Example business rule: All orders over $500 require CFO approval."

    async def _extract_logic_with_ai(self, content: str) -> List[str]:
        """
        Uses LLM to find discrete business rules/logic in unstructured text.
        """
        # Simulated AI return
        return ["orders_over_500_require_cfo_approval"]

# Global singleton
document_logic_service = DocumentLogicService()
