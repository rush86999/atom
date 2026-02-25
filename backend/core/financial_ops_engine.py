"""
Financial & Ops Automations - Phase 37
Cost Leak Detection, Budget Guardrails, Invoice Reconciliation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Union

from core.decimal_utils import to_decimal, round_money

logger = logging.getLogger(__name__)

# ==================== COST LEAK DETECTION ====================

@dataclass
class SaaSSubscription:
    """SaaS subscription record"""
    id: str
    name: str
    monthly_cost: Decimal
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
                    "monthly_cost": float(sub.monthly_cost),  # Convert for JSON serialization
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
                total_cost = sum((to_decimal(s.monthly_cost) for s in subs), Decimal('0.00'))
                redundant.append({
                    "category": category,
                    "tools": [s.name for s in subs],
                    "total_monthly_cost": float(total_cost),  # Convert for JSON serialization
                    "recommendation": f"Consolidate {len(subs)} tools in {category}"
                })

        return redundant
    
    def get_savings_report(self) -> Dict[str, Any]:
        """Generate potential savings report"""
        unused = self.detect_unused()
        redundant = self.detect_redundant()

        unused_savings = sum((to_decimal(u["monthly_cost"]) for u in unused), Decimal('0.00'))

        return {
            "unused_subscriptions": unused,
            "redundant_tools": redundant,
            "potential_monthly_savings": float(unused_savings),  # Convert for JSON serialization
            "potential_annual_savings": float(unused_savings * 12)
        }

    def validate_categorization(self) -> Dict[str, Any]:
        """
        Validate that all subscriptions have valid categories.

        Returns:
            Dict with:
            - valid: bool - True if all subscriptions categorized
            - uncategorized: List[str] - IDs of subscriptions with empty/invalid categories
            - invalid: List[str] - IDs of subscriptions with None or missing categories
        """
        uncategorized = []
        invalid = []

        for sub_id, sub in self._subscriptions.items():
            if not sub.category or sub.category.strip() == "":
                uncategorized.append(sub_id)
            if sub.category is None:
                invalid.append(sub_id)

        return {
            "valid": len(uncategorized) == 0 and len(invalid) == 0,
            "uncategorized": uncategorized,
            "invalid": invalid
        }

    def get_subscription_by_id(self, sub_id: str) -> Optional[SaaSSubscription]:
        """
        Get subscription by ID.

        Args:
            sub_id: Subscription ID

        Returns:
            SaaSSubscription or None if not found
        """
        return self._subscriptions.get(sub_id)

    def calculate_total_cost(self) -> Decimal:
        """
        Calculate total monthly cost of all subscriptions.

        Returns:
            Decimal: Total monthly cost across all subscriptions
        """
        total = sum((to_decimal(sub.monthly_cost) for sub in self._subscriptions.values()), Decimal('0.00'))
        return total

    def verify_savings_calculation(self) -> Dict[str, Any]:
        """
        Verify savings calculation by recalculating from detected unused subscriptions.

        Returns:
            Dict with:
            - match: bool - True if recalculated savings matches report
            - expected: Decimal - Recalculated savings from unused subscriptions
            - actual: Decimal - Savings from get_savings_report()
            - diff: Decimal - Difference between expected and actual
        """
        # Recalculate from unused subscriptions
        unused = self.detect_unused()
        expected_savings = sum((to_decimal(u["monthly_cost"]) for u in unused), Decimal('0.00'))

        # Get actual from report
        report = self.get_savings_report()
        actual_savings = to_decimal(report["potential_monthly_savings"])

        diff = abs(expected_savings - actual_savings)

        return {
            "match": diff == Decimal('0.00'),
            "expected": expected_savings,
            "actual": actual_savings,
            "diff": diff
        }

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect unusual cost patterns in subscriptions.

        Returns:
            List of anomaly dictionaries with type, subscription_id, description
        """
        anomalies = []

        for sub in self._subscriptions.values():
            # Anomaly 1: Zero user cost (high cost with no active users)
            if sub.active_users == 0 and sub.monthly_cost > Decimal('100.00'):
                anomalies.append({
                    "type": "zero_active_users_high_cost",
                    "subscription_id": sub.id,
                    "description": f"Subscription '{sub.name}' costs ${sub.monthly_cost}/month but has 0 active users"
                })

            # Anomaly 2: Cost spike (if we had historical data)
            # Not implemented without historical data

            # Anomaly 3: Very high unused cost
            cutoff = datetime.now() - timedelta(days=self.unused_threshold_days)
            if sub.last_used < cutoff and sub.monthly_cost > Decimal('500.00'):
                anomalies.append({
                    "type": "high_cost_unused",
                    "subscription_id": sub.id,
                    "description": f"Subscription '{sub.name}' costs ${sub.monthly_cost}/month and hasn't been used in {(datetime.now() - sub.last_used).days} days"
                })

            # Anomaly 4: Inactive but has active users (data inconsistency)
            if sub.active_users > 0 and sub.last_used < cutoff:
                anomalies.append({
                    "type": "data_inconsistency",
                    "subscription_id": sub.id,
                    "description": f"Subscription '{sub.name}' has {sub.active_users} active users but last_used is {(datetime.now() - sub.last_used).days} days ago"
                })

        return anomalies

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
    monthly_limit: Decimal
    current_spend: Decimal = Decimal('0.00')
    deal_stage_required: Optional[str] = None  # e.g., "closed_won"
    milestone_required: Optional[str] = None   # e.g., "kickoff_complete"
    warn_threshold_pct: int = 80  # Warn at this percentage
    pause_threshold_pct: int = 90  # Pause at this percentage
    block_threshold_pct: int = 100  # Block at this percentage

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
        amount: Union[Decimal, str, float],
        deal_stage: Optional[str] = None,
        milestone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if spend is allowed"""

        if category in self._paused_categories:
            return {"status": SpendStatus.PAUSED.value, "reason": "Category spending paused"}

        limit = self._limits.get(category)
        if not limit:
            return {"status": SpendStatus.APPROVED.value, "reason": "No limit set"}

        # Convert amount to Decimal
        amount_decimal = to_decimal(amount)

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
        if limit.current_spend + amount_decimal > limit.monthly_limit:
            self._paused_categories.add(category)
            return {
                "status": SpendStatus.PAUSED.value,
                "reason": f"Would exceed limit: ${limit.monthly_limit}",
                "remaining": float(limit.monthly_limit - limit.current_spend)
            }

        return {"status": SpendStatus.APPROVED.value, "remaining": float(limit.monthly_limit - limit.current_spend - amount_decimal)}
    
    def record_spend(self, category: str, amount: Union[Decimal, str, float]):
        """Record approved spend"""
        if category in self._limits:
            self._limits[category].current_spend += to_decimal(amount)

# ==================== INVOICE RECONCILIATION ====================

@dataclass
class Invoice:
    id: str
    vendor: str
    amount: Decimal
    date: datetime
    contract_id: Optional[str] = None
    approval_id: Optional[str] = None

@dataclass
class Contract:
    id: str
    vendor: str
    monthly_amount: Decimal
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
        result = {"invoice_id": invoice.id, "vendor": invoice.vendor, "amount": float(invoice.amount)}

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
        diff_percent = abs(float(invoice.amount - expected)) / float(expected) * 100

        if diff_percent > self.tolerance_percent:
            result["status"] = "discrepancy"
            result["expected_amount"] = float(expected)
            result["difference"] = float(invoice.amount - expected)
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
