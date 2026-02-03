import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import dateparser
from accounting.models import Bill, BillStatus, Document, Entity, EntityType, Invoice, InvoiceStatus
from sqlalchemy.orm import Session

from core.automation_settings import get_automation_settings
from integrations.ai_enhanced_service import (
    AIModelType,
    AIRequest,
    AIServiceType,
    AITaskType,
    ai_enhanced_service,
)

logger = logging.getLogger(__name__)

class AIDocumentProcessor:
    """
    Service for extracting structured financial data from documents using AI.
    """

    def __init__(self, db: Session):
        self.db = db

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
            logger.warning(f"No raw text found for document {document_id}")
            # In a real implementation, we would trigger OCR here
            return None

        # 1. AI Extraction
        extraction_data = await self._ai_extract(raw_text, doc_type)
        if not extraction_data:
            return None

        # 2. Entity Matching/Creation
        entity_name = extraction_data.get("entity_name")
        entity_type = EntityType.VENDOR if doc_type == "bill" else EntityType.CUSTOMER
        entity = self._get_or_create_entity(workspace_id, entity_name, entity_type)

        # 3. Record Creation
        if doc_type == "bill":
            record = self._create_bill(workspace_id, entity.id, extraction_data)
        else:
            record = self._create_invoice(workspace_id, entity.id, extraction_data)

        if record:
            # Link document to record
            if doc_type == "bill":
                document.bill_id = record.id
            else:
                document.invoice_id = record.id
            
            document.extracted_data = extraction_data
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            
        return record

    async def _ai_extract(self, text: str, doc_type: str) -> Optional[Dict[str, Any]]:
        """Call AI to extract structured info from text"""
        prompt = (
            f"Extract financial information from this {doc_type} text. "
            "Identify the name of the " + ("vendor" if doc_type == "bill" else "customer") + " as 'entity_name'. "
            "Extract 'number', 'date', 'due_date', 'amount', 'currency', and 'description'. "
            "Return ONLY a clean JSON object."
        )

        ai_request = AIRequest(
            request_id=f"extraction_{datetime.utcnow().timestamp()}",
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

    def _get_or_create_entity(self, workspace_id: str, name: str, entity_type: EntityType) -> Entity:
        """Find entity by name or create a new one"""
        entity = self.db.query(Entity).filter(
            Entity.workspace_id == workspace_id,
            Entity.name.ilike(f"%{name}%")
        ).first()

        if not entity:
            logger.info(f"Creating new {entity_type} entity: {name}")
            entity = Entity(
                workspace_id=workspace_id,
                name=name,
                type=entity_type
            )
            self.db.add(entity)
            self.db.flush()
        
        return entity

    def _create_bill(self, workspace_id: str, vendor_id: str, data: Dict[str, Any]) -> Bill:
        """Create a Bill record from extracted data"""
        return Bill(
            workspace_id=workspace_id,
            vendor_id=vendor_id,
            bill_number=data.get("number"),
            issue_date=self._parse_date(data.get("date")),
            due_date=self._parse_date(data.get("due_date")),
            amount=float(data.get("amount", 0)),
            currency=data.get("currency", "USD"),
            description=data.get("description"),
            status=BillStatus.DRAFT
        )

    def _create_invoice(self, workspace_id: str, customer_id: str, data: Dict[str, Any]) -> Invoice:
        """Create an Invoice record from extracted data"""
        return Invoice(
            workspace_id=workspace_id,
            customer_id=customer_id,
            invoice_number=data.get("number"),
            issue_date=self._parse_date(data.get("date")),
            due_date=self._parse_date(data.get("due_date")),
            amount=float(data.get("amount", 0)),
            currency=data.get("currency", "USD"),
            description=data.get("description"),
            status=InvoiceStatus.DRAFT
        )

    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """Robust date parsing using dateparser"""
        if not date_str:
            return datetime.utcnow()
        try:
            dt = dateparser.parse(date_str)
            return dt if dt else datetime.utcnow()
        except (ValueError, TypeError, AttributeError):
            return datetime.utcnow()
