from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
from typing import Any, Dict, List, Optional
from accounting.models import Bill, BillStatus, Document, Entity, EntityType, Invoice, InvoiceStatus
import dateparser
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.automation_settings import get_automation_settings

# Optional PDF OCR integration
try:
    from integrations.pdf_processing.pdf_ocr_service import PDFOCRService
    PDF_OCR_AVAILABLE = True
except ImportError:
    PDF_OCR_AVAILABLE = False
    PDFOCRService = None
# Optional AI enhanced service integration (W109-3: previously a bare import
# that made the whole module unimportable when the optional service is absent —
# matching the try/except pattern used by core/business_health_service.py).
try:
    from integrations.ai_enhanced_service import (
        AIModelType,
        AIRequest,
        AIServiceType,
        AITaskType,
        ai_enhanced_service,
    )
except Exception:
    AIModelType = None
    AIRequest = None
    AIServiceType = None
    AITaskType = None
    ai_enhanced_service = None

logger = logging.getLogger(__name__)

class DocumentFactError(ValueError):
    """A financial document is missing a required fact; it is not defaulted."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {"field": self.field, "error": self.message}


class AIDocumentProcessor:
    """
    Service for extracting structured financial data from documents using AI.
    """

    def __init__(self, db: Session):
        self.db = db
        # Populated when a document cannot be turned into a draft without
        # inventing a vendor, date, currency or amount.
        self.last_obligations: List[Dict[str, Any]] = []
        # Initialize PDF OCR service if available
        self.pdf_ocr_service = PDFOCRService() if PDF_OCR_AVAILABLE else None

    async def process_document(
        self, 
        workspace_id: str, 
        document_id: str,
        doc_type: str = "bill" # "bill" or "invoice"
    ) -> Optional[Any]:
        """
        Extract data from a document and create the corresponding record.
        """
        if not get_automation_settings().is_accounting_enabled():
            logger.info("Accounting disabled, skipping document processing")
            return None

        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return None

        # For MVP, we assume document already has some raw text extracted via OCR
        # in document.extracted_data["raw_text"]
        raw_text = document.extracted_data.get("raw_text") if document.extracted_data else ""
        if not raw_text:
            logger.warning(f"No raw text found for document {document_id}, attempting OCR extraction")
            # Attempt OCR extraction if PDF OCR service is available
            if self.pdf_ocr_service and document.file_path:
                raw_text = await self._perform_ocr(document)
                if not raw_text:
                    logger.error(f"OCR extraction failed for document {document_id}")
                    return None
            else:
                logger.error(f"No raw text found and OCR service unavailable for document {document_id}")
                return None

        # 1. AI Extraction
        self.last_obligations = []
        extraction_data = await self._ai_extract(raw_text, doc_type)
        if not extraction_data:
            return None

        # 2. Validate the facts a draft needs.  Missing currency, date,
        # number or amount is an obligation, never today/USD/zero.
        required = ("entity_name", "number", "date", "amount", "currency")
        missing = [field for field in required
                   if extraction_data.get(field) in (None, "")]
        if missing:
            self.last_obligations = [
                {"field": field,
                 "error": f"the document has no {field}; it was not defaulted"}
                for field in missing
            ]
            logger.warning(
                "Document %s not drafted; missing %s", document_id, missing)
            return None

        try:
            # 3. Entity Matching/Creation (exact identity, ambiguity refused)
            entity_name = extraction_data.get("entity_name")
            entity_type = (
                EntityType.VENDOR if doc_type == "bill" else EntityType.CUSTOMER)
            entity = self._get_or_create_entity(
                workspace_id, entity_name, entity_type)

            # 4. Record Creation
            if doc_type == "bill":
                record = self._create_bill(
                    workspace_id, entity.id, extraction_data)
            else:
                record = self._create_invoice(
                    workspace_id, entity.id, extraction_data)
        except DocumentFactError as exc:
            self.last_obligations = [exc.to_dict()]
            logger.warning("Document %s not drafted: %s", document_id, exc)
            return None

        if record:
            # Link document to record.  Preserve the original raw text and
            # prior extraction history instead of overwriting the document.
            if doc_type == "bill":
                document.bill_id = record.id
            else:
                document.invoice_id = record.id

            preserved = dict(document.extracted_data or {})
            preserved.setdefault("raw_text", raw_text)
            preserved["extraction"] = extraction_data
            preserved["extraction_source"] = "ai_document_processor"
            preserved["extraction_updated_at"] = datetime.now(
                timezone.utc).isoformat()
            document.extracted_data = preserved
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

        return record

    async def _ai_extract(self, text: str, doc_type: str) -> Optional[Dict[str, Any]]:
        """Call AI to extract structured info from text"""
        # The optional AI service may be absent (guarded import above sets
        # the enums to None) — degrade gracefully instead of AttributeError.
        if AIRequest is None or AITaskType is None or ai_enhanced_service is None:
            logger.debug("AI extraction unavailable — AI service not configured")
            return None
        prompt = (
            f"Extract financial information from this {doc_type} text. "
            "Identify the name of the " + ("vendor" if doc_type == "bill" else "customer") + " as 'entity_name'. "
            "Extract 'number', 'date', 'due_date', 'amount', 'currency', and 'description'. "
            "Return ONLY a clean JSON object."
        )

        ai_request = AIRequest(
            request_id=f"extraction_{datetime.now(timezone.utc).timestamp()}",
            task_type=AITaskType.NATURAL_LANGUAGE_COMMANDS,
            model_type=AIModelType.GPT_4,
            service_type=AIServiceType.OPENAI,
            input_data={
                "text": text,
                "instruction": prompt
            }
        )

        try:
            ai_response = await ai_enhanced_service.process_ai_request(ai_request)
            data = ai_response.output_data
            logger.debug(f"AI Output Data: {data}")
            if isinstance(data, str):
                # Clean potential markdown code blocks
                data = data.replace("```json", "").replace("```", "").strip()
                data = json.loads(data)
            return data
        except Exception as e:
            logger.error(f"AI Extraction failed: {e}")
            return None

    def _get_or_create_entity(self, workspace_id: str, name: str,
                              entity_type: EntityType,
                              *, allow_create: bool = False) -> Entity:
        """Resolve exactly one entity by exact normalized name.

        The old ``ilike('%name%')`` matched "Acme" to "Acme Holdings" and
        silently attached the document to the wrong vendor.  Two exact-name
        rows are ambiguous and must be resolved by the owner.  Creating an
        unknown vendor/customer is an explicit decision, not an extraction
        side effect, so ``allow_create`` defaults to false.
        """
        normalized = str(name or "").strip()
        if not normalized:
            raise DocumentFactError(
                "entity_name", "the document has no vendor/customer name")
        matches = self.db.query(Entity).filter(
            Entity.workspace_id == workspace_id,
            Entity.type == entity_type,
            func.lower(Entity.name) == normalized.lower(),
        ).all()
        if len(matches) > 1:
            raise DocumentFactError(
                "entity_name",
                f"multiple {entity_type.value} identities match {normalized!r}")
        if matches:
            return matches[0]
        if not allow_create:
            raise DocumentFactError(
                "entity_name",
                f"no {entity_type.value} identity matches {normalized!r}; "
                "confirm or create it explicitly")

        logger.info(f"Creating new {entity_type} entity: {normalized}")
        entity = Entity(
            workspace_id=workspace_id,
            name=normalized,
            type=entity_type,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def _required_decimal(self, data: Dict[str, Any], field: str) -> Decimal:
        raw = data.get(field)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise DocumentFactError(field, f"the document has no {field}")
        if isinstance(raw, bool):
            raise DocumentFactError(field, f"{field} must be decimal, not boolean")
        try:
            value = Decimal(str(raw).strip())
        except (InvalidOperation, ValueError) as exc:
            raise DocumentFactError(
                field, f"{field} is not a decimal: {raw!r}") from exc
        if not value.is_finite():
            raise DocumentFactError(field, f"{field} must be finite")
        return value

    def _required_date(self, data: Dict[str, Any], field: str) -> datetime:
        raw = data.get(field)
        if raw in (None, ""):
            raise DocumentFactError(field, f"the document has no {field}")
        parsed = self._parse_date(raw)
        if parsed is None:
            raise DocumentFactError(
                field, f"{field} is not a recognizable date: {raw!r}")
        return parsed

    def _create_bill(self, workspace_id: str, vendor_id: str, data: Dict[str, Any]) -> Bill:
        """Create a Bill draft from validated extracted data."""
        return Bill(
            workspace_id=workspace_id,
            vendor_id=vendor_id,
            bill_number=data.get("number"),
            issue_date=self._required_date(data, "date"),
            due_date=self._parse_date(data.get("due_date")),
            amount=self._required_decimal(data, "amount"),
            currency=str(data.get("currency") or "").strip().upper(),
            description=data.get("description"),
            status=BillStatus.DRAFT
        )

    def _create_invoice(self, workspace_id: str, customer_id: str, data: Dict[str, Any]) -> Invoice:
        """Create an Invoice draft from validated extracted data."""
        return Invoice(
            workspace_id=workspace_id,
            customer_id=customer_id,
            invoice_number=data.get("number"),
            issue_date=self._required_date(data, "date"),
            due_date=self._parse_date(data.get("due_date")),
            amount=self._required_decimal(data, "amount"),
            currency=str(data.get("currency") or "").strip().upper(),
            description=data.get("description"),
            status=InvoiceStatus.DRAFT
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse a date or return None; never substitute the current time."""
        if not date_str:
            return None
        try:
            return dateparser.parse(date_str)
        except (ValueError, TypeError, AttributeError):
            return None

    async def _perform_ocr(self, document) -> Optional[str]:
        """
        Perform OCR extraction on a document using the PDF OCR service.

        Args:
            document: Document model instance with file_path attribute

        Returns:
            Extracted text content or None if extraction fails
        """
        if not self.pdf_ocr_service:
            logger.error("PDF OCR service not available")
            return None

        try:
            import asyncio
            from pathlib import Path

            # Read PDF file
            file_path = Path(document.file_path)
            if not file_path.exists():
                logger.error(f"Document file not found: {document.file_path}")
                return None

            with open(file_path, 'rb') as f:
                pdf_data = f.read()

            # Process PDF with OCR service
            result = await self.pdf_ocr_service.process_pdf(
                pdf_data=pdf_data,
                perform_ocr=True,
                fallback_strategy="cascade",
                use_advanced_comprehension=False
            )

            if result.get("success") and result.get("extracted_text"):
                logger.info(f"Successfully extracted {result.get('total_chars', 0)} characters from document")
                return result["extracted_text"]
            else:
                logger.error(f"OCR processing failed: {result.get('error', 'Unknown error')}")
                return None

        except Exception as e:
            logger.error(f"OCR extraction failed for document {document.id}: {e}")
            return None
