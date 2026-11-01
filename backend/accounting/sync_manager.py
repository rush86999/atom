from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import logging
from typing import Any, Dict, List, Optional
from accounting.categorizer import AICategorizer
from accounting.models import Account, EntryType, JournalEntry, Transaction
from sqlalchemy.orm import Session

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    ingestion_pipeline,
)
from integrations.quickbooks_service import QuickBooksService
from integrations.xero_service import XeroService
from integrations.zoho_books_service import ZohoBooksService

logger = logging.getLogger(__name__)


class TransactionMappingError(ValueError):
    """A provider transaction cannot be mapped without inventing a fact."""

    def __init__(self, platform: str, external_id: str, field: str,
                 message: str):
        super().__init__(message)
        self.platform = platform
        self.external_id = external_id
        self.field = field
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "external_id": self.external_id,
            "field": self.field,
            "error": self.message,
        }


def _required_external_id(record: Dict[str, Any], key: str,
                          platform: str) -> str:
    value = str(record.get(key) or "").strip()
    if not value:
        raise TransactionMappingError(
            platform, "", key,
            f"{platform} record has no stable {key}; duplicate identity is unknown")
    return value


def _required_decimal(record: Dict[str, Any], key: str, platform: str,
                      external_id: str) -> Decimal:
    raw = record.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise TransactionMappingError(
            platform, external_id, key,
            f"{platform} record {external_id} has no amount")
    if isinstance(raw, bool):
        raise TransactionMappingError(
            platform, external_id, key,
            f"{platform} amount must be decimal, not boolean")
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError) as exc:
        raise TransactionMappingError(
            platform, external_id, key,
            f"{platform} amount is not a decimal: {raw!r}") from exc
    if not value.is_finite():
        raise TransactionMappingError(
            platform, external_id, key,
            f"{platform} amount must be finite")
    return value


def _required_date(record: Dict[str, Any], key: str, platform: str,
                   external_id: str) -> datetime:
    raw = record.get(key)
    if raw in (None, ""):
        raise TransactionMappingError(
            platform, external_id, key,
            f"{platform} record {external_id} has no transaction date")
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise TransactionMappingError(
        platform, external_id, key,
        f"{platform} transaction date is not ISO: {raw!r}")


class AccountingSyncManager:
    """
    Unified manager for synchronizing data across multiple accounting ledgers 
    (Zoho, Xero, QuickBooks, Stripe/Plaid).
    """

    def __init__(self, db: Session):
        self.db = db
        self.zoho = ZohoBooksService()
        self.xero = XeroService()
        self.qbo = QuickBooksService()
        self.categorizer = AICategorizer(db)
        # Populated by the mapping pass.  A record that cannot be mapped is
        # reported, never defaulted to today/USD/zero.
        self.last_mapping_errors: List[Dict[str, Any]] = []

    async def sync_external_transactions(
        self, 
        workspace_id: str, 
        platform: str, 
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pull transactions from an external platform and ingest into ATOM's ledger.
        """
        raw_transactions = []
        
        if platform == "zoho":
            raw_transactions = await self.zoho.get_bank_transactions(
                credentials["access_token"], 
                credentials["organization_id"],
                credentials.get("account_id")
            )
            mapped_txs = self._map_zoho_transactions(raw_transactions, workspace_id)
            
        elif platform == "xero":
            raw_transactions = await self.xero.get_invoices(
                credentials["access_token"],
                credentials["tenant_id"]
            )
            mapped_txs = self._map_xero_transactions(raw_transactions, workspace_id)
            
        elif platform == "quickbooks":
            raw_transactions = await self.qbo.get_expenses(
                credentials["realm_id"],
                credentials["access_token"]
            )
            mapped_txs = self._map_qbo_transactions(raw_transactions, workspace_id)
        
        else:
            raise ValueError(f"Unsupported platform: {platform}")

        mapping_errors = list(self.last_mapping_errors)
        ingestion_errors: List[Dict[str, Any]] = []
        ingested_count = 0
        for tx_data in mapped_txs:
            # Exact duplicate identity: workspace + provider + external ID.
            # The old JSON substring check treated "z1" as a match for "z10".
            exists = self.db.query(Transaction).filter(
                Transaction.workspace_id == workspace_id,
                Transaction.external_id == tx_data["external_id"],
                Transaction.source == platform,
            ).first()

            if not exists:
                tx = Transaction(
                    workspace_id=workspace_id,
                    external_id=tx_data["external_id"],
                    source=platform,
                    description=tx_data["description"],
                    amount=tx_data["amount"],
                    transaction_date=tx_data["date"],
                    metadata_json={
                        "external_id": tx_data["external_id"],
                        "platform": platform,
                    },
                )
                self.db.add(tx)
                self.db.flush()

                # Auto-categorize
                self.categorizer.categorize_transaction(tx.id)
                ingested_count += 1

                # Ingest into semantic memory (LanceDB + Knowledge Graph).
                # A failure here is a searchability gap, not a successful
                # sync; report it instead of only logging it.
                try:
                    await ingestion_pipeline.ingest_message(
                        app_type=platform if platform != "quickbooks" else "quickbooks",
                        message_data={
                            "id": f"tx_{tx.id}",
                            "timestamp": tx.transaction_date.isoformat(),
                            "sender": platform,
                            "content": f"Financial Transaction: {tx.description}. Amount: {tx.amount}. Merchant: {tx.metadata_json.get('merchant', 'Unknown')}",
                            "metadata": {
                                "transaction_id": tx.id,
                                "workspace_id": workspace_id,
                                "amount": str(tx.amount),
                                "external_id": tx_data["external_id"],
                            },
                        },
                    )
                except Exception as ex:
                    logger.error(
                        f"Failed to ingest transaction {tx.id} into semantic "
                        f"memory: {ex}")
                    ingestion_errors.append({
                        "transaction_id": tx.id,
                        "external_id": tx_data["external_id"],
                        "error": f"{type(ex).__name__}: {ex}"[:300],
                    })

        self.db.commit()
        if mapping_errors or ingestion_errors:
            status = "partial" if ingested_count else "failed"
        else:
            status = "success"
        return {
            "status": status,
            "ingested": ingested_count,
            "platform": platform,
            "mapping_errors": mapping_errors,
            "ingestion_errors": ingestion_errors,
        }

    def _map_zoho_transactions(self, raw: List[Dict], ws_id: str) -> List[Dict]:
        self.last_mapping_errors = []
        mapped: List[Dict] = []
        for record in raw or []:
            try:
                external_id = _required_external_id(
                    record, "transaction_id", "zoho")
                mapped.append({
                    "description": record.get(
                        "description", "Zoho Transaction"),
                    "amount": _required_decimal(
                        record, "amount", "zoho", external_id),
                    "date": _required_date(
                        record, "date", "zoho", external_id),
                    "external_id": external_id,
                })
            except TransactionMappingError as exc:
                self.last_mapping_errors.append(exc.to_dict())
        return mapped

    def _map_xero_transactions(self, raw: List[Dict], ws_id: str) -> List[Dict]:
        self.last_mapping_errors = []
        mapped: List[Dict] = []
        for record in raw or []:
            try:
                external_id = _required_external_id(
                    record, "InvoiceID", "xero")
                mapped.append({
                    "description": f"Xero Invoice: {record.get('InvoiceNumber','')}",
                    "amount": _required_decimal(
                        record, "Total", "xero", external_id),
                    "date": _required_date(
                        record, "DateString", "xero", external_id),
                    "external_id": external_id,
                })
            except TransactionMappingError as exc:
                self.last_mapping_errors.append(exc.to_dict())
        return mapped

    def _map_qbo_transactions(self, raw: List[Dict], ws_id: str) -> List[Dict]:
        self.last_mapping_errors = []
        mapped: List[Dict] = []
        for record in raw or []:
            try:
                external_id = _required_external_id(record, "Id", "quickbooks")
                mapped.append({
                    "description": record.get("PrivateNote", "QBO Expense"),
                    "amount": _required_decimal(
                        record, "TotalAmt", "quickbooks", external_id),
                    "date": _required_date(
                        record, "TxnDate", "quickbooks", external_id),
                    "external_id": external_id,
                })
            except TransactionMappingError as exc:
                self.last_mapping_errors.append(exc.to_dict())
        return mapped
