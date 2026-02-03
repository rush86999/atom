"""
AI Accounting - Reconciliation & Anomaly Detection - Phase 40
Continuous reconciliation, anomaly flagging, confidence scoring.
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class AnomalyType(Enum):
    UNUSUAL_AMOUNT = "unusual_amount"
    DUPLICATE_VENDOR = "duplicate_vendor"
    MISSING_TRANSACTION = "missing_transaction"
    TIMING_DIFFERENCE = "timing_difference"
    UNEXPECTED_CATEGORY = "unexpected_category"
    DUPLICATE_TRANSACTION = "duplicate_transaction"

class ReconciliationStatus(Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    DISCREPANCY = "discrepancy"
    PENDING = "pending"

@dataclass
class ReconciliationEntry:
    """Entry for reconciliation tracking"""
    id: str
    source: str  # bank, ledger, etc.
    date: datetime
    amount: float
    description: str
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    matched_with: Optional[str] = None
    discrepancy_amount: float = 0.0

@dataclass
class Anomaly:
    """Detected anomaly"""
    id: str
    anomaly_type: AnomalyType
    severity: str  # low, medium, high
    description: str
    transaction_ids: List[str]
    confidence: float
    suggested_action: str
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False

@dataclass
class EntryConfidence:
    """Confidence scoring for journal entry"""
    entry_id: str
    confidence_percent: float
    reasoning: str
    data_sources: List[str]
    last_updated: datetime
    change_log: List[Dict[str, Any]] = field(default_factory=list)

class ReconciliationEngine:
    """
    Continuous reconciliation engine with anomaly detection.
    Runs daily instead of month-end.
    """
    
    # Thresholds for anomaly detection
    AMOUNT_ZSCORE_THRESHOLD = 2.5  # Standard deviations
    DUPLICATE_TIME_WINDOW_HOURS = 48
    
    def __init__(self):
        self._bank_entries: Dict[str, ReconciliationEntry] = {}
        self._ledger_entries: Dict[str, ReconciliationEntry] = {}
        self._anomalies: List[Anomaly] = []
        self._vendor_history: Dict[str, List[float]] = {}  # vendor -> amounts
        self._entry_confidence: Dict[str, EntryConfidence] = {}
    
    # ==================== CONTINUOUS RECONCILIATION ====================
    
    def add_bank_entry(self, entry: ReconciliationEntry):
        """Add entry from bank feed"""
        self._bank_entries[entry.id] = entry
        self._update_vendor_history(entry.description, entry.amount)
    
    def add_ledger_entry(self, entry: ReconciliationEntry):
        """Add entry from ledger/books"""
        self._ledger_entries[entry.id] = entry
    
    def reconcile(self) -> Dict[str, Any]:
        """
        Run continuous reconciliation.
        Matches bank entries to ledger entries.
        """
        matched = []
        unmatched_bank = []
        unmatched_ledger = []
        discrepancies = []
        
        # Match bank entries to ledger
        for bank_id, bank_entry in self._bank_entries.items():
            if bank_entry.status == ReconciliationStatus.MATCHED:
                continue
            
            match = self._find_match(bank_entry, self._ledger_entries)
            
            if match:
                ledger_entry = self._ledger_entries[match]
                
                # Check for amount discrepancy
                diff = abs(bank_entry.amount - ledger_entry.amount)
                if diff > 0.01:  # Tolerance for rounding
                    bank_entry.status = ReconciliationStatus.DISCREPANCY
                    bank_entry.matched_with = match
                    bank_entry.discrepancy_amount = diff
                    discrepancies.append({
                        "bank_id": bank_id,
                        "ledger_id": match,
                        "bank_amount": bank_entry.amount,
                        "ledger_amount": ledger_entry.amount,
                        "difference": diff
                    })
                else:
                    bank_entry.status = ReconciliationStatus.MATCHED
                    bank_entry.matched_with = match
                    ledger_entry.status = ReconciliationStatus.MATCHED
                    ledger_entry.matched_with = bank_id
                    matched.append({"bank_id": bank_id, "ledger_id": match})
            else:
                unmatched_bank.append(bank_id)
        
        # Find unmatched ledger entries
        for ledger_id, ledger_entry in self._ledger_entries.items():
            if ledger_entry.status == ReconciliationStatus.PENDING:
                unmatched_ledger.append(ledger_id)
        
        return {
            "matched_count": len(matched),
            "unmatched_bank": unmatched_bank,
            "unmatched_ledger": unmatched_ledger,
            "discrepancies": discrepancies,
            "status": "reconciled"
        }
    
    def _find_match(self, entry: ReconciliationEntry, candidates: Dict[str, ReconciliationEntry]) -> Optional[str]:
        """Find matching entry based on amount, date, description"""
        for cand_id, cand in candidates.items():
            if cand.status == ReconciliationStatus.MATCHED:
                continue
            
            # Amount match (within 1%)
            if abs(entry.amount - cand.amount) / max(abs(entry.amount), 1) > 0.01:
                continue
            
            # Date match (within 5 days for timing differences)
            if abs((entry.date - cand.date).days) > 5:
                continue
            
            # Description similarity (simple check)
            if self._description_similarity(entry.description, cand.description) > 0.5:
                return cand_id
        
        return None
    
    def _description_similarity(self, desc1: str, desc2: str) -> float:
        """Simple word overlap similarity"""
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))
    
    # ==================== ANOMALY DETECTION ====================
    
    def detect_anomalies(self) -> List[Anomaly]:
        """Run anomaly detection on all entries"""
        new_anomalies = []
        
        # Detect unusual amounts
        new_anomalies.extend(self._detect_unusual_amounts())
        
        # Detect duplicates
        new_anomalies.extend(self._detect_duplicates())
        
        # Detect missing transactions
        new_anomalies.extend(self._detect_missing())
        
        self._anomalies.extend(new_anomalies)
        return new_anomalies
    
    def _detect_unusual_amounts(self) -> List[Anomaly]:
        """Flag transactions with unusual amounts for their vendor"""
        anomalies = []
        
        for entry_id, entry in self._bank_entries.items():
            vendor = entry.description.lower()
            if vendor not in self._vendor_history:
                continue
            
            history = self._vendor_history[vendor]
            if len(history) < 3:
                continue
            
            mean = statistics.mean(history)
            stdev = statistics.stdev(history) if len(history) > 1 else 0
            
            if stdev == 0:
                continue
            
            zscore = abs(entry.amount - mean) / stdev
            
            if zscore > self.AMOUNT_ZSCORE_THRESHOLD:
                anomalies.append(Anomaly(
                    id=f"anomaly_{entry_id}",
                    anomaly_type=AnomalyType.UNUSUAL_AMOUNT,
                    severity="high" if zscore > 4 else "medium",
                    description=f"Amount ${entry.amount:.2f} is {zscore:.1f} std devs from mean ${mean:.2f}",
                    transaction_ids=[entry_id],
                    confidence=min(0.95, 0.5 + (zscore - 2) * 0.15),
                    suggested_action="Review transaction for accuracy"
                ))
        
        return anomalies
    
    def _detect_duplicates(self) -> List[Anomaly]:
        """Detect potential duplicate transactions"""
        anomalies = []
        entries = list(self._bank_entries.values())
        
        for i, entry1 in enumerate(entries):
            for entry2 in entries[i+1:]:
                # Same amount
                if entry1.amount != entry2.amount:
                    continue
                
                # Within time window
                hours_diff = abs((entry1.date - entry2.date).total_seconds() / 3600)
                if hours_diff > self.DUPLICATE_TIME_WINDOW_HOURS:
                    continue
                
                # Similar description
                if self._description_similarity(entry1.description, entry2.description) > 0.7:
                    anomalies.append(Anomaly(
                        id=f"dup_{entry1.id}_{entry2.id}",
                        anomaly_type=AnomalyType.DUPLICATE_TRANSACTION,
                        severity="medium",
                        description=f"Possible duplicate: ${entry1.amount:.2f} at {entry1.description}",
                        transaction_ids=[entry1.id, entry2.id],
                        confidence=0.85,
                        suggested_action="Verify if both transactions are valid"
                    ))
        
        return anomalies
    
    def _detect_missing(self) -> List[Anomaly]:
        """Detect missing transactions (gaps in recurring patterns)"""
        # Simplified: check for unmatched entries older than 3 days
        anomalies = []
        now = datetime.now()
        
        for entry_id, entry in self._bank_entries.items():
            if entry.status == ReconciliationStatus.PENDING:
                age_days = (now - entry.date).days
                if age_days > 3:
                    anomalies.append(Anomaly(
                        id=f"missing_{entry_id}",
                        anomaly_type=AnomalyType.MISSING_TRANSACTION,
                        severity="low",
                        description=f"Bank entry not matched to ledger for {age_days} days",
                        transaction_ids=[entry_id],
                        confidence=0.7,
                        suggested_action="Add corresponding ledger entry"
                    ))
        
        return anomalies
    
    def _update_vendor_history(self, vendor: str, amount: float):
        """Track vendor spending patterns"""
        vendor_key = vendor.lower()
        if vendor_key not in self._vendor_history:
            self._vendor_history[vendor_key] = []
        self._vendor_history[vendor_key].append(abs(amount))
    
    # ==================== CONFIDENCE SCORING ====================
    
    def score_entry_confidence(self, entry_id: str, sources: List[str], reasoning: str) -> EntryConfidence:
        """Calculate and store confidence for a journal entry"""
        
        # Score based on data sources
        source_score = min(1.0, len(sources) * 0.3)
        
        # Score based on matching
        match_score = 0.0
        if entry_id in self._bank_entries:
            entry = self._bank_entries[entry_id]
            if entry.status == ReconciliationStatus.MATCHED:
                match_score = 0.5
            elif entry.status == ReconciliationStatus.DISCREPANCY:
                match_score = 0.2
        
        confidence = (source_score + match_score) / 2 * 100
        
        entry_conf = EntryConfidence(
            entry_id=entry_id,
            confidence_percent=round(confidence, 1),
            reasoning=reasoning,
            data_sources=sources,
            last_updated=datetime.now()
        )
        
        self._entry_confidence[entry_id] = entry_conf
        return entry_conf
    
    def get_anomalies(self, unresolved_only: bool = True) -> List[Anomaly]:
        """Get detected anomalies"""
        if unresolved_only:
            return [a for a in self._anomalies if not a.resolved]
        return self._anomalies
    
    def resolve_anomaly(self, anomaly_id: str):
        """Mark anomaly as resolved"""
        for a in self._anomalies:
            if a.id == anomaly_id:
                a.resolved = True
                break

# Global instance
reconciliation_engine = ReconciliationEngine()
