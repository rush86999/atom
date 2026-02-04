"""
Financial & Ops Automations - Phase 37
Cost Leak Detection, Budget Guardrails, Invoice Reconciliation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== COST LEAK DETECTION ====================

@dataclass
class SaaSSubscription:
    """SaaS subscription record"""
    id: str
    name: str
    monthly_cost: float
    last_used: datetime
    user_count: int
    active_users: int = 0
    category: str = "general"

class CostLeakDetector:
    """Detects unused SaaS subscriptions and redundant tools"""
    
    def __init__(self, unused_threshold_days: int = 30):
        self.unused_threshold_days = unused_threshold_days
        self._subscriptions: Dict[str, SaaSSubscription] = {}
    
    def add_subscription(self, sub: SaaSSubscription):
        self._subscriptions[sub.id] = sub
    
    def detect_unused(self) -> List[Dict[str, Any]]:
        """Find subscriptions not used in threshold period"""
        cutoff = datetime.now() - timedelta(days=self.unused_threshold_days)
        unused = []
        
        for sub in self._subscriptions.values():
            if sub.last_used < cutoff:
                unused.append({
                    "id": sub.id,
                    "name": sub.name,
                    "monthly_cost": sub.monthly_cost,
                    "days_unused": (datetime.now() - sub.last_used).days,
                    "recommendation": "Cancel or review usage"
                })
        
        return sorted(unused, key=lambda x: -x["monthly_cost"])
    
    def detect_redundant(self) -> List[Dict[str, Any]]:
        """Find tools in same category that could be consolidated"""
        by_category = {}
        for sub in self._subscriptions.values():
            if sub.category not in by_category:
                by_category[sub.category] = []
            by_category[sub.category].append(sub)
        
        redundant = []
        for category, subs in by_category.items():
            if len(subs) > 1:
                total_cost = sum(s.monthly_cost for s in subs)
                redundant.append({
                    "category": category,
                    "tools": [s.name for s in subs],
                    "total_monthly_cost": total_cost,
                    "recommendation": f"Consolidate {len(subs)} tools in {category}"
                })
        
        return redundant
    
    def get_savings_report(self) -> Dict[str, Any]:
        """Generate potential savings report"""
        unused = self.detect_unused()
        redundant = self.detect_redundant()
        
        unused_savings = sum(u["monthly_cost"] for u in unused)
        
        return {
            "unused_subscriptions": unused,
            "redundant_tools": redundant,
            "potential_monthly_savings": unused_savings,
            "potential_annual_savings": unused_savings * 12
        }

# ==================== BUDGET GUARDRAILS ====================

class SpendStatus(Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    PAUSED = "paused"

@dataclass
class BudgetLimit:
    """Budget limit configuration"""
    category: str
    monthly_limit: float
    current_spend: float = 0
    deal_stage_required: Optional[str] = None  # e.g., "closed_won"
    milestone_required: Optional[str] = None   # e.g., "kickoff_complete"

class BudgetGuardrails:
    """Enforces spending limits and approval rules"""
    
    def __init__(self):
        self._limits: Dict[str, BudgetLimit] = {}
        self._paused_categories: set = set()
    
    def set_limit(self, limit: BudgetLimit):
        self._limits[limit.category] = limit
    
    def check_spend(
        self,
        category: str,
        amount: float,
        deal_stage: Optional[str] = None,
        milestone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if spend is allowed"""
        
        if category in self._paused_categories:
            return {"status": SpendStatus.PAUSED.value, "reason": "Category spending paused"}
        
        limit = self._limits.get(category)
        if not limit:
            return {"status": SpendStatus.APPROVED.value, "reason": "No limit set"}
        
        # Check deal stage requirement
        if limit.deal_stage_required:
            if deal_stage != limit.deal_stage_required:
                return {
                    "status": SpendStatus.REJECTED.value,
                    "reason": f"Requires deal stage: {limit.deal_stage_required}"
                }
        
        # Check milestone requirement
        if limit.milestone_required:
            if milestone != limit.milestone_required:
                return {
                    "status": SpendStatus.PENDING.value,
                    "reason": f"Waiting for milestone: {limit.milestone_required}"
                }
        
        # Check budget limit
        if limit.current_spend + amount > limit.monthly_limit:
            self._paused_categories.add(category)
            return {
                "status": SpendStatus.PAUSED.value,
                "reason": f"Would exceed limit: ${limit.monthly_limit}",
                "remaining": limit.monthly_limit - limit.current_spend
            }
        
        return {"status": SpendStatus.APPROVED.value, "remaining": limit.monthly_limit - limit.current_spend - amount}
    
    def record_spend(self, category: str, amount: float):
        """Record approved spend"""
        if category in self._limits:
            self._limits[category].current_spend += amount

# ==================== INVOICE RECONCILIATION ====================

@dataclass
class Invoice:
    id: str
    vendor: str
    amount: float
    date: datetime
    contract_id: Optional[str] = None
    approval_id: Optional[str] = None

@dataclass
class Contract:
    id: str
    vendor: str
    monthly_amount: float
    start_date: datetime
    end_date: datetime

class InvoiceReconciler:
    """Matches invoices to contracts and approvals"""
    
    def __init__(self, tolerance_percent: float = 5.0):
        self.tolerance_percent = tolerance_percent
        self._invoices: List[Invoice] = []
        self._contracts: Dict[str, Contract] = {}
        self._approvals: Dict[str, Dict] = {}
    
    def add_invoice(self, invoice: Invoice):
        self._invoices.append(invoice)
    
    def add_contract(self, contract: Contract):
        self._contracts[contract.id] = contract
    
    def add_approval(self, approval_id: str, details: Dict):
        self._approvals[approval_id] = details
    
    def reconcile(self) -> Dict[str, Any]:
        """Match invoices and flag discrepancies"""
        matched = []
        discrepancies = []
        unmatched = []
        
        for inv in self._invoices:
            result = self._match_invoice(inv)
            
            if result["status"] == "matched":
                matched.append(result)
            elif result["status"] == "discrepancy":
                discrepancies.append(result)
            else:
                unmatched.append(result)
        
        return {
            "matched": matched,
            "discrepancies": discrepancies,
            "unmatched": unmatched,
            "summary": {
                "total_invoices": len(self._invoices),
                "matched_count": len(matched),
                "discrepancy_count": len(discrepancies),
                "unmatched_count": len(unmatched)
            }
        }
    
    def _match_invoice(self, invoice: Invoice) -> Dict[str, Any]:
        """Match single invoice"""
        result = {"invoice_id": invoice.id, "vendor": invoice.vendor, "amount": invoice.amount}
        
        # Find matching contract
        contract = None
        if invoice.contract_id:
            contract = self._contracts.get(invoice.contract_id)
        else:
            # Try to find by vendor
            for c in self._contracts.values():
                if c.vendor.lower() == invoice.vendor.lower():
                    contract = c
                    break
        
        if not contract:
            result["status"] = "unmatched"
            result["reason"] = "No matching contract found"
            return result
        
        # Check amount within tolerance
        expected = contract.monthly_amount
        diff_percent = abs(invoice.amount - expected) / expected * 100
        
        if diff_percent > self.tolerance_percent:
            result["status"] = "discrepancy"
            result["expected_amount"] = expected
            result["difference"] = invoice.amount - expected
            result["difference_percent"] = round(diff_percent, 1)
            result["reason"] = f"Amount differs by {result['difference_percent']}%"
            return result
        
        result["status"] = "matched"
        result["contract_id"] = contract.id
        return result

# Global instances
cost_detector = CostLeakDetector()
budget_guardrails = BudgetGuardrails()
invoice_reconciler = InvoiceReconciler()
