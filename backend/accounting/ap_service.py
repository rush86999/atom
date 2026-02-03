import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from accounting.ledger import DoubleEntryEngine, EventSourcedLedger
from accounting.models import Account, AccountType, Bill, BillStatus, Document, Entity, EntityType
from sqlalchemy.orm import Session

from integrations.pdf_processing.pdf_ocr_service import PDFOCRService

logger = logging.getLogger(__name__)

class APService:
    """
    Service for handling Accounts Payable automation, including OCR for invoices
    and automated recording in the ledger.
    """

    def __init__(self, db: Session):
        self.db = db
        self.ocr_service = PDFOCRService()
        self.ledger = EventSourcedLedger(db)

    async def process_invoice_document(
        self, 
        document_id: str, 
        workspace_id: str,
        expense_account_code: str = "5100" # Default to Software/Subscriptions
    ) -> Dict[str, Any]:
        """
        Process a previously uploaded document as an invoice.
        """
        doc = self.db.query(Document).filter(Document.id == document_id, Document.workspace_id == workspace_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # 1. OCR Extraction
        ocr_result = await self.ocr_service.process_pdf(
            doc.file_path, 
            use_ocr=True, 
            use_advanced_comprehension=True
        )

        extracted_text = ocr_result.get("extracted_content", {}).get("text", "")
        
        # 2. Structure Data with AI (In a real system, we'd use a specific financial prompt)
        # For this implementation, we'll simulate the structured extraction
        invoice_data = await self._parse_invoice_text(extracted_text)
        
        # Store extracted data in document
        doc.extracted_data = invoice_data
        self.db.flush()

        # 3. Resolve Vendor
        vendor_name = invoice_data.get("vendor_name", "Unknown Vendor")
        vendor = self._resolve_vendor(vendor_name, workspace_id)

        # 4. Create Bill
        amount = float(invoice_data.get("amount", 0.0))
        due_date_str = invoice_data.get("due_date")
        issue_date_str = invoice_data.get("issue_date")
        
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d") if due_date_str else datetime.now()
        issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d") if issue_date_str else datetime.now()

        bill = Bill(
            workspace_id=workspace_id,
            vendor_id=vendor.id,
            bill_number=invoice_data.get("invoice_number"),
            amount=amount,
            issue_date=issue_date,
            due_date=due_date,
            description=f"Automated ingestion for {vendor_name}",
            status=BillStatus.OPEN
        )
        self.db.add(bill)
        self.db.flush()

        # Link document to bill
        doc.bill_id = bill.id

        # 5. Create Ledger Entry (Accrual)
        # Find Accounts Payable liability account and the Expense account
        ap_account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id, 
            Account.type == AccountType.LIABILITY,
            Account.code == "2000"
        ).first()

        expense_account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.code == expense_account_code
        ).first()

        if ap_account and expense_account:
            entries = DoubleEntryEngine.create_bill_entry(
                payable_account_id=ap_account.id,
                expense_account_id=expense_account.id,
                amount=amount,
                description=f"Bill {bill.bill_number or bill.id} from {vendor_name}"
            )
            
            tx = self.ledger.record_transaction(
                workspace_id=workspace_id,
                transaction_date=issue_date,
                description=f"Accrual for Bill {bill.bill_number or bill.id}",
                entries=entries,
                source="ap_automation",
                metadata={"bill_id": bill.id, "vendor_id": vendor.id}
            )
            
            bill.transaction_id = tx.id
            self.db.commit()
            
            return {
                "status": "success",
                "bill_id": bill.id,
                "transaction_id": tx.id,
                "vendor": vendor_name,
                "amount": amount,
                "confidence": invoice_data.get("confidence", 1.0)
            }
        
        return {
            "status": "partial_success", 
            "bill_id": bill.id, 
            "message": "Bill created but ledger entry failed (accounts missing)",
            "confidence": invoice_data.get("confidence", 0.5)
        }

    async def _parse_invoice_text(self, text: str) -> Dict[str, Any]:
        """
        Simulates AI parsing of raw text into structured invoice data with confidence scoring.
        """
        # In production, this would be a call to gpt-4 or similar with a schema
        # We'll simulate lower confidence if the text is very short or missing key terms
        confidence = 0.95
        if len(text) < 50:
            confidence = 0.6
        if "Invoice" not in text and "INV" not in text:
            confidence -= 0.2
            
        return {
            "vendor_name": "CloudServices Inc",
            "invoice_number": f"INV-{datetime.now().strftime('%Y%m%d')}",
            "amount": 299.99,
            "issue_date": datetime.now().strftime("%Y-%m-%d"),
            "due_date": datetime.now().strftime("%Y-%m-%d"),
            "currency": "USD",
            "confidence": max(0.0, confidence)
        }

    def _resolve_vendor(self, name: str, workspace_id: str) -> Entity:
        """
        Fuzzy match vendor or create a new one.
        """
        vendor = self.db.query(Entity).filter(
            Entity.workspace_id == workspace_id,
            Entity.type.in_([EntityType.VENDOR, EntityType.BOTH]),
            Entity.name == name
        ).first()

        if not vendor:
            vendor = Entity(
                workspace_id=workspace_id,
                name=name,
                type=EntityType.VENDOR
            )
            self.db.add(vendor)
            self.db.flush()
        
        return vendor
