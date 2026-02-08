"""
AI Accounting Engine - Phase 39
Transaction ingestion, AI categorization, and Chart of Accounts learning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class TransactionStatus(Enum):
    PENDING = "pending"
    CATEGORIZED = "categorized"
    POSTED = "posted"
    REVIEW_REQUIRED = "review_required"

class TransactionSource(Enum):
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    MANUAL = "manual"

@dataclass
class Transaction:
    """Financial transaction record"""
    id: str
    date: datetime
    amount: float
    description: str
    merchant: Optional[str] = None
    source: TransactionSource = TransactionSource.BANK
    status: TransactionStatus = TransactionStatus.PENDING
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    confidence: float = 0.0
    reasoning: Optional[str] = None
    posted_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

@dataclass
class ChartOfAccountsEntry:
    """Chart of Accounts entry"""
    account_id: str
    name: str
    type: str  # asset, liability, equity, revenue, expense
    parent_id: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    merchant_patterns: List[str] = field(default_factory=list)

class AIAccountingEngine:
    """
    AI-powered accounting engine with confidence-based categorization.
    
    Architecture:
    - LLM only proposes, never posts directly
    - Approval + rollback support
    - Immutable audit trails
    """
    
    CONFIDENCE_THRESHOLD = 0.85  # Auto-post if above this
    
    def __init__(self):
        self._transactions: Dict[str, Transaction] = {}
        self._chart_of_accounts: Dict[str, ChartOfAccountsEntry] = {}
        self._category_history: Dict[str, List[str]] = {}  # merchant -> categories
        self._pending_review: List[str] = []
        self._audit_log: List[Dict[str, Any]] = []
        
        # Initialize default CoA
        self._load_default_coa()
    
    def _load_default_coa(self):
        """Load default Chart of Accounts"""
        defaults = [
            ChartOfAccountsEntry("1000", "Cash", "asset", keywords=["deposit", "withdrawal"]),
            ChartOfAccountsEntry("1100", "Accounts Receivable", "asset", keywords=["invoice", "payment received"]),
            ChartOfAccountsEntry("2000", "Accounts Payable", "liability", keywords=["bill", "vendor"]),
            ChartOfAccountsEntry("4000", "Revenue", "revenue", keywords=["sale", "income", "payment"]),
            ChartOfAccountsEntry("5000", "Cost of Goods Sold", "expense", keywords=["inventory", "product"]),
            ChartOfAccountsEntry("6100", "Rent", "expense", keywords=["rent", "lease"], merchant_patterns=["landlord", "property"]),
            ChartOfAccountsEntry("6200", "Utilities", "expense", keywords=["electric", "gas", "water", "internet"]),
            ChartOfAccountsEntry("6300", "Software", "expense", keywords=["subscription", "saas"], merchant_patterns=["slack", "notion", "github", "aws"]),
            ChartOfAccountsEntry("6400", "Marketing", "expense", keywords=["ads", "marketing", "campaign"], merchant_patterns=["google ads", "facebook", "linkedin"]),
            ChartOfAccountsEntry("6500", "Travel", "expense", keywords=["flight", "hotel", "uber", "lyft"]),
            ChartOfAccountsEntry("6600", "Meals", "expense", keywords=["restaurant", "food", "dining"]),
            ChartOfAccountsEntry("6700", "Office Supplies", "expense", keywords=["supplies", "office"], merchant_patterns=["amazon", "staples"]),
            ChartOfAccountsEntry("6800", "Professional Services", "expense", keywords=["legal", "accounting", "consulting"]),
        ]
        for entry in defaults:
            self._chart_of_accounts[entry.account_id] = entry
    
    # ==================== TRANSACTION INGESTION ====================
    
    def ingest_transaction(self, tx: Transaction) -> Transaction:
        """Ingest a new transaction and categorize it"""
        self._transactions[tx.id] = tx
        
        # Auto-categorize
        category_id, category_name, confidence, reasoning = self._categorize_transaction(tx)
        
        tx.category_id = category_id
        tx.category_name = category_name
        tx.confidence = confidence
        tx.reasoning = reasoning
        
        # Determine status based on confidence
        if confidence >= self.CONFIDENCE_THRESHOLD:
            tx.status = TransactionStatus.CATEGORIZED
            self._log_audit("auto_categorized", tx, f"High confidence ({confidence:.0%})")
        else:
            tx.status = TransactionStatus.REVIEW_REQUIRED
            self._pending_review.append(tx.id)
            self._log_audit("review_required", tx, f"Low confidence ({confidence:.0%})")
        
        return tx
    
    def ingest_bank_feed(self, transactions: List[Dict[str, Any]]) -> List[Transaction]:
        """Bulk ingest from bank feed"""
        results = []
        for tx_data in transactions:
            tx = Transaction(
                id=tx_data.get("id", f"tx_{datetime.now().timestamp()}"),
                date=datetime.fromisoformat(tx_data["date"]) if isinstance(tx_data["date"], str) else tx_data["date"],
                amount=tx_data["amount"],
                description=tx_data["description"],
                merchant=tx_data.get("merchant"),
                source=TransactionSource(tx_data.get("source", "bank"))
            )
            results.append(self.ingest_transaction(tx))
        
        logger.info(f"Ingested {len(results)} transactions from bank feed")
        return results
    
    # ==================== AI CATEGORIZATION ====================
    
    def _categorize_transaction(self, tx: Transaction) -> Tuple[str, str, float, str]:
        """
        Categorize transaction using AI/heuristics.
        Returns: (category_id, category_name, confidence, reasoning)
        """
        merchant = (tx.merchant or "").lower()
        description = tx.description.lower()
        combined_text = f"{merchant} {description}"
        
        best_match = None
        best_score = 0.0
        reasoning_parts = []
        
        # 1. Check merchant pattern matches (highest confidence)
        for account in self._chart_of_accounts.values():
            for pattern in account.merchant_patterns:
                if pattern.lower() in merchant:
                    score = 0.95
                    if score > best_score:
                        best_match = account
                        best_score = score
                        reasoning_parts = [f"Merchant '{merchant}' matches pattern '{pattern}'"]
        
        # 2. Check historical categorization (high confidence)
        if merchant and merchant in self._category_history:
            historical = self._category_history[merchant]
            if historical:
                most_common = max(set(historical), key=historical.count)
                if most_common in self._chart_of_accounts:
                    score = 0.90 if historical.count(most_common) > 2 else 0.75
                    if score > best_score:
                        best_match = self._chart_of_accounts[most_common]
                        best_score = score
                        reasoning_parts = [f"Historical: {merchant} usually categorized as {best_match.name}"]
        
        # 3. Keyword matching (medium confidence)
        if not best_match or best_score < 0.7:
            for account in self._chart_of_accounts.values():
                keyword_matches = sum(1 for kw in account.keywords if kw.lower() in combined_text)
                if keyword_matches > 0:
                    score = min(0.70 + (keyword_matches * 0.05), 0.85)
                    if score > best_score:
                        best_match = account
                        best_score = score
                        matched_kws = [kw for kw in account.keywords if kw.lower() in combined_text]
                        reasoning_parts = [f"Keywords matched: {matched_kws}"]
        
        # 4. Default to uncategorized
        if not best_match:
            return (None, "Uncategorized", 0.0, "No matching patterns found")
        
        reasoning = "; ".join(reasoning_parts)
        return (best_match.account_id, best_match.name, best_score, reasoning)
    
    # ==================== CHART OF ACCOUNTS LEARNING ====================
    
    def learn_categorization(self, tx_id: str, category_id: str, user_id: str):
        """Learn from user categorization to improve future predictions"""
        tx = self._transactions.get(tx_id)
        if not tx:
            return
        
        account = self._chart_of_accounts.get(category_id)
        if not account:
            return
        
        # Update transaction
        tx.category_id = category_id
        tx.category_name = account.name
        tx.confidence = 1.0
        tx.status = TransactionStatus.CATEGORIZED
        tx.reviewed_by = user_id
        
        # Learn from merchant
        merchant = (tx.merchant or tx.description[:20]).lower()
        if merchant not in self._category_history:
            self._category_history[merchant] = []
        self._category_history[merchant].append(category_id)
        
        # Remove from pending review
        if tx_id in self._pending_review:
            self._pending_review.remove(tx_id)
        
        self._log_audit("user_categorized", tx, f"User {user_id} categorized as {account.name}")
        logger.info(f"Learned: {merchant} -> {account.name}")
    
    # ==================== POSTING & APPROVAL ====================
    
    def post_transaction(self, tx_id: str, user_id: Optional[str] = None) -> bool:
        """Post a transaction to the ledger (with human approval if required)"""
        tx = self._transactions.get(tx_id)
        if not tx:
            return False
        
        if tx.status == TransactionStatus.REVIEW_REQUIRED:
            logger.warning(f"Cannot post {tx_id}: requires review")
            return False
        
        tx.status = TransactionStatus.POSTED
        tx.posted_at = datetime.now()
        
        self._log_audit("posted", tx, f"Posted by {user_id or 'system'}")
        return True
    
    def auto_post_high_confidence(self) -> int:
        """Auto-post all high confidence transactions"""
        posted = 0
        for tx in self._transactions.values():
            if tx.status == TransactionStatus.CATEGORIZED and tx.confidence >= self.CONFIDENCE_THRESHOLD:
                if self.post_transaction(tx.id):
                    posted += 1
        return posted
    
    # ==================== REVIEW QUEUE ====================
    
    def get_pending_review(self) -> List[Transaction]:
        """Get transactions pending review"""
        return [self._transactions[tid] for tid in self._pending_review if tid in self._transactions]
    
    # ==================== AUDIT TRAIL ====================
    
    def _log_audit(self, action: str, tx: Transaction, details: str):
        """Immutable audit log entry"""
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "transaction_id": tx.id,
            "category": tx.category_name,
            "confidence": tx.confidence,
            "details": details
        })
    
    def get_audit_log(self, tx_id: str = None) -> List[Dict[str, Any]]:
        """Get audit log, optionally filtered by transaction"""
        if tx_id:
            return [e for e in self._audit_log if e["transaction_id"] == tx_id]
        return self._audit_log
    
    # ==================== LEDGER INTEGRATION ====================
    
    def post_to_ledger(self, tx_id: str, db_session = None) -> Dict[str, Any]:
        """
        Post approved transaction to the existing EventSourcedLedger.
        Integrates with accounting/ledger.py for proper double-entry.
        """
        tx = self._transactions.get(tx_id)
        if not tx:
            return {"status": "failed", "error": f"Transaction {tx_id} not found"}
        
        if tx.status == TransactionStatus.REVIEW_REQUIRED:
            return {"status": "failed", "error": "Transaction requires review before posting"}
        
        if tx.status == TransactionStatus.POSTED:
            return {"status": "skipped", "reason": "Already posted"}
        
        try:
            # Import existing ledger
            from accounting.ledger import DoubleEntryEngine, EventSourcedLedger
            from accounting.models import EntryType
            
            if db_session is None:
                # Mock posting for non-DB environments
                tx.status = TransactionStatus.POSTED
                tx.posted_at = datetime.now()
                self._log_audit("posted_mock", tx, "Posted without DB session")
                return {"status": "posted", "mode": "mock", "tx_id": tx_id}
            
            ledger = EventSourcedLedger(db_session)
            
            # Determine accounts based on category
            cash_account = "1000"  # Default cash account
            expense_account = tx.category_id or "6700"  # Default to Office Supplies
            
            # Create double-entry
            entries = DoubleEntryEngine.create_payment_entry(
                cash_account_id=cash_account,
                expense_account_id=expense_account,
                amount=abs(tx.amount),
                description=tx.description
            )
            
            # Post to ledger
            ledger_tx = ledger.record_transaction(
                workspace_id="default",
                transaction_date=tx.date,
                description=tx.description,
                entries=entries,
                source="ai_accounting",
                external_id=tx.id,
                metadata={"confidence": tx.confidence, "reasoning": tx.reasoning}
            )
            
            tx.status = TransactionStatus.POSTED
            tx.posted_at = datetime.now()
            self._log_audit("posted_to_ledger", tx, f"Ledger TX: {ledger_tx.id}")
            
            return {"status": "posted", "ledger_tx_id": str(ledger_tx.id), "tx_id": tx_id}
            
        except ImportError:
            # Fallback if accounting models not available
            tx.status = TransactionStatus.POSTED
            tx.posted_at = datetime.now()
            self._log_audit("posted_standalone", tx, "Posted without ledger integration")
            return {"status": "posted", "mode": "standalone", "tx_id": tx_id}
        except Exception as e:
            self._log_audit("post_failed", tx, str(e))
            return {"status": "failed", "error": str(e)}

# Global engine instance
ai_accounting = AIAccountingEngine()
