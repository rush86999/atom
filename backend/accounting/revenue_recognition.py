from datetime import datetime
import logging
from typing import Any, Dict, Optional
from accounting.ledger import EventSourcedLedger
from accounting.models import Account, AccountType, EntryType
from service_delivery.models import Contract, Milestone, Project
from sqlalchemy.orm import Session, joinedload

from core.database import get_db_session

logger = logging.getLogger(__name__)

class RevenueRecognitionService:
    """
    Automates the transition from Deferred Revenue to Recognized Revenue.
    """

    async def record_revenue_recognition(self, milestone_id: str) -> Dict[str, Any]:
        """Record revenue recognition for a milestone using context manager."""
        with get_db_session() as db:
            milestone = db.query(Milestone).options(
                joinedload(Milestone.project)
                .joinedload(Project.contract)
                .joinedload(Contract.product_service)
            ).filter(Milestone.id == milestone_id).first()
            if not milestone:
                return {"status": "error", "message": f"Milestone {milestone_id} not found"}

            project = milestone.project
            contract = project.contract if project else None

            if not contract:
                return {"status": "error", "message": "Contract or project not found for milestone"}

            workspace_id = milestone.workspace_id
            amount = milestone.amount

            if amount <= 0:
                return {"status": "success", "message": "Zero amount milestone, no entry needed"}

            # 1. Resolve Accounts
            # We look for "Sales Revenue" (4000) and "Deferred Revenue" (2100)
            revenue_acc = db.query(Account).filter(
                Account.workspace_id == workspace_id,
                Account.code == "4000"
            ).first()

            deferred_acc = db.query(Account).filter(
                Account.workspace_id == workspace_id,
                Account.code == "2100"
            ).first()

            if not revenue_acc or not deferred_acc:
                return {
                    "status": "error",
                    "message": "Required accounts (4000 or 2100) not found in Chart of Accounts"
                }

            # 2. Record Transaction
            ledger = EventSourcedLedger(db)

            product_name = contract.product_service.name if contract.product_service else "General Service"
            description = f"Revenue Recognition for Milestone: {milestone.name} ({product_name})"

            entries = [
                {"account_id": deferred_acc.id, "type": EntryType.DEBIT, "amount": amount},
                {"account_id": revenue_acc.id, "type": EntryType.CREDIT, "amount": amount}
            ]

            metadata = {
                "milestone_id": milestone_id,
                "project_id": project.id,
                "contract_id": contract.id,
                "product_service_id": contract.product_service_id,
                "type": "revenue_recognition"
            }

            tx = ledger.record_transaction(
                workspace_id=workspace_id,
                transaction_date=datetime.utcnow(),
                description=description,
                entries=entries,
                source="auto_recognition",
                metadata=metadata
            )

            return {
                "status": "success",
                "transaction_id": tx.id,
                "amount": amount,
                "product": product_name
            }

revenue_recognition_service = RevenueRecognitionService()
