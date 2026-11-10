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
import uuid
from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import IntegrityError

from core.models import Tenant, ACUConsumption, TokenUsage, TenantSetting

logger = logging.getLogger(__name__)


def record_llm_usage(
    *,
    provider_id: Optional[str],
    model_name: Optional[str],
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: Optional[float] = None,
    agent_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    chain_id: Optional[str] = None,
    request_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
) -> str:
    """Settle one actual LLM provider attempt into the durable usage ledger.

    ``TokenUsage`` is the single ledger SpendAggregation already reads. This
    helper does not create a parallel store. ``cost_usd=None`` means
    unpriced/unknown (an explicit liability); ``0.0`` means known free.
    ``attempt_id`` is the server-owned idempotency key: replaying the same
    attempt returns the existing row; a different material under the same key
    is a conflict, never a second charge.

    Uses a dedicated session so it can never commit a caller's business work.
    """
    # Resolve the current SessionLocal at call time so scratch/test database
    # patches apply instead of a stale module-level binding.
    from core.database import SessionLocal

    session = SessionLocal()
    try:
        if attempt_id:
            existing = session.query(TokenUsage).filter(
                TokenUsage.attempt_id == str(attempt_id)).first()
            if existing is not None:
                same = (
                    existing.provider_id == provider_id
                    and existing.model_name == model_name
                    and int(existing.prompt_tokens or 0) == int(prompt_tokens or 0)
                    and int(existing.completion_tokens or 0) == int(completion_tokens or 0)
                    and existing.cost_usd == cost_usd
                    and existing.agent_id == agent_id
                    and existing.workspace_id == workspace_id
                    and existing.tenant_id == tenant_id
                )
                if not same:
                    raise ValueError(
                        f"attempt_id {attempt_id!r} already settled with "
                        "different usage material")
                return str(existing.id)
        row = TokenUsage(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            chain_id=chain_id,
            provider_id=provider_id,
            request_id=request_id,
            attempt_id=str(attempt_id) if attempt_id else None,
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
            total_tokens=int(prompt_tokens or 0) + int(completion_tokens or 0),
            billed=True,
            cost_usd=cost_usd,
            pricing_status=(
                "unknown" if cost_usd is None
                else "free" if float(cost_usd) == 0.0
                else "priced"),
            model_name=model_name,
        )
        session.add(row)
        session.commit()
        return str(row.id)
    except IntegrityError:
        session.rollback()
        if attempt_id:
            existing = session.query(TokenUsage).filter(
                TokenUsage.attempt_id == str(attempt_id)).first()
            if existing is not None:
                return str(existing.id)
        raise
    finally:
        session.close()



class SpendAggregationService:
    """
    Spend aggregation service for unified budget tracking.
    """

    def __init__(self, db: Session):
        self.db = db

    def _budget_limit_from_setting(self, tenant_id: str) -> float:
        """Read the budget limit from TenantSetting['billing']['budget_limit_usd'].

        This is the admin-configured source (set via the budget control API at
        api/admin/budget_routes.py). Returns 0.0 if unset (meaning no limit).
        """
        try:
            from core.models import TenantSetting
            import json

            row = (
                self.db.query(TenantSetting)
                .filter(
                    TenantSetting.tenant_id == tenant_id,
                    TenantSetting.setting_key == "billing",
                )
                .first()
            )
            if row and row.setting_value:
                data = json.loads(row.setting_value)
                if isinstance(data, dict):
                    limit = data.get("budget_limit_usd")
                    if limit is not None:
                        return float(limit)
        except Exception as e:
            logger.debug(f"Could not read budget limit from settings for {tenant_id}: {e}")
        return 0.0

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

    def get_unpriced_usage(
        self, tenant_id: str, start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Count durable rows whose cost is unknown (NULL), distinct from free 0.

        These are unpriced liabilities, not zero-cost work. A hard-stop budget
        must refuse or require reconciliation while this count is non-zero.
        Rows without a tenant are not attributed to any tenant budget.
        """
        try:
            today = date.today()
            start = start_date or date(today.year, today.month, 1)
            end = end_date or today
            start_dt = datetime.combine(start, datetime.min.time())
            end_dt = datetime.combine(end, datetime.max.time())
            return int(self.db.query(func.count(TokenUsage.id)).filter(
                TokenUsage.tenant_id == tenant_id,
                or_(TokenUsage.pricing_status == "unknown",
                    TokenUsage.cost_usd.is_(None)),
                TokenUsage.timestamp >= start_dt,
                TokenUsage.timestamp <= end_dt,
            ).scalar() or 0)
        except Exception as e:
            logger.warning(
                f"[SpendAggregationService] unpriced usage read failed for "
                f"{tenant_id}: {e}")
            return 0

    def update_tenant_spend(
        self, tenant_id: str, *, persist: bool = True,
    ) -> Dict[str, Any]:
        """Compute spend, optionally persisting the existing cached rollup.

        Budget preflight uses persist=False: it must neither commit nor roll
        back business edits owned by the caller. Existing rollup writers keep
        their historical persistence by default.
        """
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

            current_spend_usd = spend_data["total_spend_usd"]
            
            # Lifetime spend (since creation).
            # NOTE (W104-2): created_at is UTC (func.now()) while `today` is
            # local — for tenants created after ~17:00 local the UTC date is
            # the NEXT day, producing an inverted [start > end] range that
            # silently returned 0.0 lifetime spend. Clamp to today.
            lifetime_start = tenant.created_at.date() if tenant.created_at else date(2025, 1, 1)
            if lifetime_start > today:
                lifetime_start = today
            lifetime_spend = self.get_total_spend(tenant_id=tenant_id, start_date=lifetime_start, end_date=today)
            total_spend_usd = lifetime_spend["total_spend_usd"]

            if persist:
                tenant.current_spend_usd = current_spend_usd
                tenant.total_spend_usd = total_spend_usd
                self.db.commit()

            # Budget limit: prefer the persisted Tenant attribute; fall back to
            # the admin-configured limit in TenantSetting['billing'] (set via
            # the budget control API). The Tenant attribute is not a declared
            # column in all deployments, so the setting is the reliable source.
            budget_limit = getattr(tenant, "budget_limit_usd", None)
            if not budget_limit:
                budget_limit = self._budget_limit_from_setting(tenant_id)
            budget_limit = float(budget_limit or 0.0)
            utilization_percent = (current_spend_usd / budget_limit * 100) if budget_limit > 0 else 0.0

            return {
                "tenant_id": tenant_id,
                "current_spend_usd": round(current_spend_usd, 4),
                "total_spend_usd": round(total_spend_usd, 4),
                "budget_limit_usd": budget_limit,
                "utilization_percent": round(utilization_percent, 2)
            }
        except Exception as e:
            logger.error(f"[SpendAggregationService] Error updating spend: {str(e)}")
            if persist:
                self.db.rollback()
            return {"error": str(e)}
