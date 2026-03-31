"""
Spend Aggregation Service - Consolidates ACU and BYOK costs into Tenant.current_spend_usd.
(Phase 10: Fleet-Aware Hardening Synchronized from SaaS)

This service provides unified spend tracking by aggregating costs from two sources:
1. ACU (Agent Compute Units) consumption from Fly.io hosting
2. BYOK (Bring Your Own Key) token usage costs with markup

New Phase 10 Features:
- get_fleet_spend: Aggregates expenditure specifically across a delegation chain (fleet).
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.models import Tenant, ACUConsumption, TokenUsage, TenantSetting

logger = logging.getLogger(__name__)


class SpendAggregationService:
    """
    Spend aggregation service for unified budget tracking.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_total_spend(
        self,
        tenant_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Calculate total spend for tenant within date range."""
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # 1. Aggregate ACU costs from hosting
            try:
                acu_result = self.db.query(
                    func.sum(ACUConsumption.acu_cost)
                ).filter(
                    ACUConsumption.tenant_id == tenant_id,
                    ACUConsumption.consumption_date >= start_date,
                    ACUConsumption.consumption_date <= end_date
                ).scalar()
                acu_cost_usd = float(acu_result) if acu_result else 0.0
            except Exception:
                acu_cost_usd = 0.0

            # 2. Aggregate BYOK token costs
            try:
                byok_result = self.db.query(
                    func.sum(TokenUsage.cost_usd)
                ).filter(
                    TokenUsage.tenant_id == tenant_id,
                    TokenUsage.timestamp >= start_datetime,
                    TokenUsage.timestamp <= end_datetime
                ).scalar()
                byok_cost_usd = float(byok_result) if byok_result else 0.0
            except Exception as byok_error:
                logger.warning(f"[SpendAggregationService] Error querying BYOK costs: {str(byok_error)}")
                byok_cost_usd = 0.0

            total_spend_usd = acu_cost_usd + byok_cost_usd

            return {
                "acu_cost_usd": round(acu_cost_usd, 4),
                "byok_cost_usd": round(byok_cost_usd, 4),
                "total_spend_usd": round(total_spend_usd, 4)
            }
        except Exception as e:
            logger.error(f"[SpendAggregationService] Error calculating spend for tenant {tenant_id}: {str(e)}")
            return {"acu_cost_usd": 0.0, "byok_cost_usd": 0.0, "total_spend_usd": 0.0, "error": str(e)}

    def get_fleet_spend(self, chain_id: str) -> float:
        """
        Calculate total spend for a specific delegation chain (fleet).
        Aggregates TokenUsage for all executions linked to this chain (Phase 10 Hardening).
        """
        try:
            result = self.db.query(
                func.sum(TokenUsage.cost_usd)
            ).filter(
                TokenUsage.chain_id == chain_id
            ).scalar()

            return float(result) if result else 0.0
        except Exception as e:
            logger.warning(f"[SpendAggregationService] Error calculating fleet spend for chain {chain_id}: {e}")
            return 0.0

    def update_tenant_spend(self, tenant_id: str) -> Dict[str, Any]:
        """Update tenant's current_spend_usd and total_spend_usd with aggregated spend."""
        try:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant: return {"error": f"Tenant {tenant_id} not found"}

            # Calculate current cycle start (Simplified for parity)
            today = date.today()
            cycle_start = date(today.year, today.month, 1) # Default to 1st of month for Upstream

            spend_data = self.get_total_spend(
                tenant_id=tenant_id,
                start_date=cycle_start,
                end_date=today
            )

            if "error" in spend_data: return spend_data

            tenant.current_spend_usd = spend_data["total_spend_usd"]
            
            # Lifetime spend (since creation)
            lifetime_start = tenant.created_at.date() if tenant.created_at else date(2025, 1, 1)
            lifetime_spend = self.get_total_spend(tenant_id=tenant_id, start_date=lifetime_start, end_date=today)
            tenant.total_spend_usd = lifetime_spend["total_spend_usd"]

            self.db.commit()

            budget_limit = tenant.budget_limit_usd or 0.0
            utilization_percent = (tenant.current_spend_usd / budget_limit * 100) if budget_limit > 0 else 0.0

            return {
                "tenant_id": tenant_id,
                "current_spend_usd": round(tenant.current_spend_usd, 4),
                "total_spend_usd": round(tenant.total_spend_usd, 4),
                "budget_limit_usd": budget_limit,
                "utilization_percent": round(utilization_percent, 2)
            }
        except Exception as e:
            logger.error(f"[SpendAggregationService] Error updating spend: {str(e)}")
            self.db.rollback()
            return {"error": str(e)}
