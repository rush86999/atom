
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from accounting.models import Bill, Entity, Transaction, EntityType, BillStatus
from ecommerce.models import EcommerceOrder, EcommerceOrderItem

logger = logging.getLogger(__name__)

class FinancialForensicsService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_vendor_price_drift(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Detects vendors whose average bill amount has increased by >15% over the last 90 days.
        """
        alerts = []
        
        # 1. Get all vendors
        vendors = self.db.query(Entity).filter(
            Entity.workspace_id == workspace_id,
            Entity.type == EntityType.VENDOR
        ).all()
        
        for vendor in vendors:
            # Get bills from last 90 days
            bills = self.db.query(Bill).filter(
                Bill.workspace_id == workspace_id,
                Bill.vendor_id == vendor.id,
                Bill.status != BillStatus.VOID,
                Bill.issue_date >= datetime.utcnow() - timedelta(days=90)
            ).order_by(Bill.issue_date).all()
            
            if len(bills) < 2:
                continue
                
            # Simple Drift Logic: Compare first half average vs last half average
            # (In a real system, we'd do linear regression)
            midpoint = len(bills) // 2
            first_half = bills[:midpoint]
            last_half = bills[midpoint:]
            
            avg_first = sum(b.amount for b in first_half) / len(first_half)
            avg_last = sum(b.amount for b in last_half) / len(last_half)
            
            if avg_first > 0:
                drift_pct = ((avg_last - avg_first) / avg_first) * 100
                if drift_pct > 15.0:
                    alerts.append({
                        "vendor_name": vendor.name,
                        "drift_percentage": round(drift_pct, 1),
                        "avg_previous": round(avg_first, 2),
                        "avg_recent": round(avg_last, 2),
                        "bill_count": len(bills)
                    })
                    
        return alerts

    def detect_subscription_waste(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identifies recurring monthly payments that might be unused.
        """
        waste_candidates = []
        
        # 1. Find potential subscriptions (Frequency analysis on Transactions)
        # Group by description and amount (simplified recognition)
        # In production, we'd fuzzy match merchant names
        
        # Get transactions from last 60 days
        transactions = self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.transaction_date >= datetime.utcnow() - timedelta(days=60)
        ).all()
        
        # Naive clustering: Key = (Description, Amount)
        clusters = {}
        for tx in transactions:
            key = (tx.description, tx.amount)
            if key not in clusters:
                clusters[key] = []
            clusters[key].append(tx)
            
        for (desc, amt), txs in clusters.items():
            if len(txs) >= 2 and amt is not None and amt > 0: # Appeared at least twice in 60 days (monthly)
                # Check utilization logic (Mocked for now - assume all > $1000 SaaS without logins are waste)
                # In real world, we'd check SSO logs
                
                # Mock "Unused" heuristic: If no logins in last 30 days. 
                # Since we don't have SSO logs linked yet, we'll mark any recurring > $50 as "Verify Usage"
                if amt > 49.00: 
                    waste_candidates.append({
                        "subscription": desc,
                        "monthly_cost": amt,
                        "status": "Potential Waste",
                        "recommendation": "Verify last login date or cancellation policy."
                    })

        return waste_candidates

    def analyze_pricing_margins(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Detects products sold with low margins (< 20%) based on Cost of Goods Sold estimates.
        """
        alerts = []
        
        # 1. Get recent order items
        recent_items = self.db.query(EcommerceOrderItem).join(EcommerceOrder).filter(
            EcommerceOrder.workspace_id == workspace_id,
            EcommerceOrder.created_at >= datetime.utcnow() - timedelta(days=30)
        ).all()
        
        # Group by SKU
        sku_stats = {}
        for item in recent_items:
            sku = item.sku
            if sku not in sku_stats:
                sku_stats[sku] = []
            sku_stats[sku].append(item.price)
            
        for sku, prices in sku_stats.items():
            avg_price = sum(prices) / len(prices)
            
            # Mock Cost Basis: Assume 85% of average price is cost (simulating 15% margin)
            # In real system, we'd query inventory cost
            estimated_cost = avg_price * 0.85 
            
            # Check margin against target 20%
            current_margin = (avg_price - estimated_cost) / avg_price
            
            if current_margin < 0.20:
                alerts.append({
                    "sku": sku,
                    "avg_price": round(avg_price, 2),
                    "estimated_margin": round(current_margin * 100, 1),
                    "target_margin": "20.0",
                    "recommendation": "Increase price or renegotiate supplier cost."
                })
        
        return alerts
