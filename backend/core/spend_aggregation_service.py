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
import math
import uuid
from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, update, text
from sqlalchemy.exc import IntegrityError

from core.models import Tenant, ACUConsumption, TokenUsage, TenantSetting

logger = logging.getLogger(__name__)

# Process-local fail-closed marker for a durable settlement write that did
# not persist. A hard stop must not treat a lost write as successful budget;
# it refuses until restart/reconciliation. This is not a second ledger.
_SETTLEMENT_FAILURE_REASON: Optional[str] = None


def mark_settlement_failure(reason: str) -> None:
    """Record that actual paid usage could not be persisted."""
    global _SETTLEMENT_FAILURE_REASON
    _SETTLEMENT_FAILURE_REASON = reason or "settlement_write_failed"
    logger.error("durable LLM settlement degraded: %s", _SETTLEMENT_FAILURE_REASON)


class DurableUsageIntentError(RuntimeError):
    """A paid dispatch could not persist its durable unknown/liability intent."""


class BudgetReservationRefused(RuntimeError):
    """Atomic hard-stop admission refused the reservation before dispatch."""

    def __init__(self, reason: str, *, status_code: str = "BUDGET_EXCEEDED"):
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


def settlement_failure_reason() -> Optional[str]:
    """Reason a prior settlement write failed, or None when healthy."""
    return _SETTLEMENT_FAILURE_REASON


def clear_settlement_failure() -> None:
    """Explicit reconciliation/restart reset; never called on success alone."""
    global _SETTLEMENT_FAILURE_REASON
    _SETTLEMENT_FAILURE_REASON = None



class BudgetPolicyUnavailable(RuntimeError):
    """The configured billing policy cannot be read/validated safely."""


_VALID_MODES = {"alert_only", "soft_stop", "hard_stop", "approval"}


def read_billing_policy(
    session: Session, tenant_id: str, *, strict: bool = False,
) -> tuple[float, str]:
    """One reader for the existing billing limit + enforcement mode.

    ``strict=True`` (the reservation path) raises ``BudgetPolicyUnavailable``
    for a malformed/contradictory configured policy instead of collapsing an
    invalid cap to 0/unlimited. ``strict=False`` preserves the historical
    lenient defaults for existing callers/tests. A genuinely absent policy
    (no row / no limit) remains the intended no-limit/observe default.
    """
    tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        # The single-tenant default scope has no Tenant row by design; that is
        # an intentional no-limit/observe policy, not an unreadable configured
        # policy. A missing NON-default tenant is an unresolved/misconfigured
        # scope and must fail closed under strict admission.
        if strict and tenant_id != "default":
            raise BudgetPolicyUnavailable("tenant not found")
        return 0.0, "soft_stop"

    limit = getattr(tenant, "budget_limit_usd", None)
    if isinstance(limit, bool):
        if strict:
            raise BudgetPolicyUnavailable("invalid tenant budget limit")
        limit = None
    if limit is not None:
        try:
            limit = float(limit)
        except (TypeError, ValueError):
            if strict:
                raise BudgetPolicyUnavailable("invalid tenant budget limit")
            limit = None
        if limit is not None and (
                not math.isfinite(limit) or limit < 0):
            if strict:
                raise BudgetPolicyUnavailable("invalid tenant budget limit")
            limit = None

    mode = "soft_stop"
    row = session.query(TenantSetting).filter(
        TenantSetting.tenant_id == tenant_id,
        TenantSetting.setting_key == "billing",
    ).first()
    if row is None:
        return float(limit or 0.0), mode
    if not row.setting_value:
        if strict:
            raise BudgetPolicyUnavailable("empty billing policy")
        return float(limit or 0.0), mode
    try:
        data = json.loads(row.setting_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        if strict:
            raise BudgetPolicyUnavailable("unreadable billing policy")
        return float(limit or 0.0), mode
    if not isinstance(data, dict):
        if strict:
            raise BudgetPolicyUnavailable("invalid billing policy")
        return float(limit or 0.0), mode

    raw_limit = data.get("budget_limit_usd")
    if raw_limit is not None:
        if isinstance(raw_limit, bool):
            if strict:
                raise BudgetPolicyUnavailable("invalid billing cap")
            parsed_limit = None
        else:
            try:
                parsed_limit = float(raw_limit)
            except (TypeError, ValueError):
                if strict:
                    raise BudgetPolicyUnavailable("invalid billing cap")
                parsed_limit = None
        if parsed_limit is not None:
            if not math.isfinite(parsed_limit) or parsed_limit < 0:
                if strict:
                    raise BudgetPolicyUnavailable("invalid billing cap")
            else:
                limit = parsed_limit

    enforcement = data.get("enforcement")
    if enforcement is not None and not isinstance(enforcement, dict):
        if strict:
            raise BudgetPolicyUnavailable("invalid enforcement policy")
        enforcement = {}
    raw_mode = (enforcement or {}).get("mode")
    if raw_mode is not None:
        if not isinstance(raw_mode, str) or raw_mode not in _VALID_MODES:
            if strict:
                raise BudgetPolicyUnavailable("invalid enforcement mode")
            logger.warning(
                "Invalid enforcement mode %r for tenant %s; using soft_stop",
                raw_mode, tenant_id)
        else:
            mode = raw_mode
    return float(limit or 0.0), mode


def _utc_today() -> date:
    """Current date on the same clock that stamps TokenUsage rows.

    ``TokenUsage.timestamp`` defaults to ``func.now()``, which SQLite stores
    as UTC. Every cycle/admission window over that column must therefore be
    derived from the UTC date, never the local date: after ~19:00 in UTC-5
    the local date lags the UTC date, and a local-date window silently
    excludes rows settled seconds ago (observed as current_spend dropping
    the newest settlement between 00:00 UTC and local midnight).
    """
    return datetime.now(timezone.utc).date()


def _admission_totals(
    session: Session, tenant_id: str,
) -> tuple[float, float]:
    """Return (actual, active_reserved) in the configured cycle window."""
    today = _utc_today()
    cycle_start = date(today.year, today.month, 1)
    spend = SpendAggregationService(session).get_total_spend(
        tenant_id=tenant_id, start_date=cycle_start, end_date=today)
    if "error" in spend:
        raise RuntimeError("spend read failed")
    start_dt = datetime.combine(cycle_start, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())
    reserved = session.query(func.sum(TokenUsage.reserved_cost_usd)).filter(
        TokenUsage.tenant_id == tenant_id,
        TokenUsage.reservation_status.in_(("active", "uncertain")),
        TokenUsage.timestamp >= start_dt,
        TokenUsage.timestamp <= end_dt,
    ).scalar()
    return float(spend["total_spend_usd"]), float(reserved or 0.0)


def _lock_tenant_for_admission(session: Session, tenant_id: str) -> None:
    """Serialize Postgres reservations on the existing tenant row.

    SQLite has one writer at a time; the reservation INSERT/flush acquires that
    write lock, so the following sum sees every committed reservation.
    """
    try:
        dialect = session.get_bind().dialect.name
    except Exception:
        dialect = ""
    if dialect == "postgresql":
        session.query(Tenant).filter(
            Tenant.id == tenant_id).with_for_update().first()
    elif dialect == "sqlite":
        # Acquire the single writer lock BEFORE the read/sum. A deferred
        # read-then-write would keep a stale snapshot and could admit two
        # reservations against 90. BEGIN IMMEDIATE waits for the other writer
        # and then the following query sees its committed row.
        conn = session.connection()
        conn.exec_driver_sql("PRAGMA busy_timeout=30000")
        conn.exec_driver_sql("BEGIN IMMEDIATE")


def begin_llm_usage(
    *,
    provider_id: Optional[str],
    model_name: Optional[str],
    agent_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    chain_id: Optional[str] = None,
    request_id: Optional[str] = None,
    attempt_id: str,
    reserved_cost_usd: Optional[float] = None,
    enforce_budget: bool = False,
) -> str:
    """Persist the durable paid-liability/reservation row BEFORE dispatch.

    This is the pending-intent/reservation use of the existing ``TokenUsage``
    ledger, not a parallel store. For a production dispatch, the caller passes
    ``enforce_budget=True`` and a conservative ``reserved_cost_usd`` bound.
    Under configured hard_stop, the INSERT is the serialization point (SQLite
    write lock) or follows a Tenant ``FOR UPDATE`` lock (Postgres), then the
    transaction sums actual + active reservations. A loser rolls back and
    raises ``BudgetReservationRefused`` before any provider call.

    A failed settlement write leaves the active reservation/unknown row in
    place; a restart reads it, so the liability is not forgotten. Timeout or
    uncertain usage never auto-releases it. A later ``record_llm_usage``
    settles this exact row once.
    """
    if reserved_cost_usd is not None:
        if isinstance(reserved_cost_usd, bool):
            raise BudgetReservationRefused(
                "invalid reservation bound",
                status_code="BUDGET_UNPRICED_USAGE")
        try:
            bound_value = float(reserved_cost_usd)
        except (TypeError, ValueError):
            bound_value = None
        # A caller-supplied bound must be finite and non-negative. A malformed
        # bound cannot lower liability or hide unknown pricing; refuse before
        # creating any row so hard-stop dispatches nothing.
        if (bound_value is None or not math.isfinite(bound_value)
                or bound_value < 0):
            raise BudgetReservationRefused(
                "invalid reservation bound",
                status_code="BUDGET_UNPRICED_USAGE")
        reserved_cost_usd = bound_value

    from core.database import SessionLocal

    session = None
    try:
        session = SessionLocal()
        if tenant_id:
            _lock_tenant_for_admission(session, tenant_id)
        existing = session.query(TokenUsage).filter(
            TokenUsage.attempt_id == str(attempt_id)).first()
        if existing is not None:
            if not _intent_binding_matches(
                existing,
                request_id=request_id,
                provider_id=provider_id,
                model_name=model_name,
                agent_id=agent_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                execution_id=execution_id,
                chain_id=chain_id,
            ):
                raise DurableUsageIntentError(
                    "durable usage intent binding conflict")
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
            attempt_id=str(attempt_id),
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            billed=False,
            cost_usd=None,
            pricing_status="unknown",
            reserved_cost_usd=(
                reserved_cost_usd if enforce_budget else 0.0),
            reservation_status=("active" if enforce_budget else "none"),
            model_name=model_name,
        )
        session.add(row)
        # Flush first: on SQLite this takes the single writer lock, so a
        # concurrent reservation waits and then sees this committed row.
        session.flush()
        if enforce_budget and tenant_id:
            try:
                limit, mode = read_billing_policy(
                    session, tenant_id, strict=True)
            except BudgetPolicyUnavailable:
                raise BudgetReservationRefused(
                    "billing policy unavailable",
                    status_code="BUDGET_STATUS_UNAVAILABLE") from None
            if mode == "hard_stop" and limit > 0:
                if reserved_cost_usd is None:
                    raise BudgetReservationRefused(
                        "unknown pricing; hard_stop cannot reserve a bounded "
                        "cost", status_code="BUDGET_UNPRICED_USAGE")
                try:
                    actual, active_reserved = _admission_totals(
                        session, tenant_id)
                except Exception:
                    raise BudgetReservationRefused(
                        "budget state unavailable",
                        status_code="BUDGET_STATUS_UNAVAILABLE") from None
                if actual + active_reserved > limit + 1e-9:
                    raise BudgetReservationRefused(
                        "atomic budget reservation would exceed the configured "
                        f"limit ({actual + active_reserved:.4f} > "
                        f"{limit:.4f})",
                        status_code="BUDGET_EXCEEDED")
        session.commit()
        return str(row.id)
    except BudgetReservationRefused:
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        raise
    except Exception as intent_err:
        # Do not put SQL/params in the degraded reason or log.
        mark_settlement_failure(
            f"intent_write_failed:{type(intent_err).__name__}")
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        raise DurableUsageIntentError(
            "durable usage intent could not be persisted") from None
    finally:
        if session is not None:
            session.close()


def _normalize_cost(cost_usd: Optional[float]) -> Optional[float]:
    """Finite, non-negative cost or explicit unknown.

    Invalid configured pricing (negative/NaN/inf/type junk) is unknown, never
    free and never an admitted negative/infinite bound.
    """
    if cost_usd is None or isinstance(cost_usd, bool):
        # bool is not a numeric price: float(False)==0 would otherwise become
        # authoritative free and float(True)==1 a fake one-dollar charge.
        return None
    try:
        value = float(cost_usd)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _usage_pricing_status(cost_usd: Optional[float]) -> str:
    cost = _normalize_cost(cost_usd)
    if cost is None:
        return "unknown"
    return "free" if cost == 0.0 else "priced"


def _intent_binding_matches(
    row: TokenUsage,
    *,
    request_id: Optional[str],
    provider_id: Optional[str],
    model_name: Optional[str],
    agent_id: Optional[str],
    workspace_id: Optional[str],
    tenant_id: Optional[str],
    execution_id: Optional[str],
    chain_id: Optional[str],
) -> bool:
    """Exact immutable binding recorded by ``begin_llm_usage``.

    ``None`` is a real binding value: a settlement call must pass the same
    value, not silently rewrite the scope. No field is reassigned by settle.
    """
    return (
        row.request_id == request_id
        and row.provider_id == provider_id
        and row.model_name == model_name
        and row.agent_id == agent_id
        and row.workspace_id == workspace_id
        and row.tenant_id == tenant_id
        and row.execution_id == execution_id
        and row.chain_id == chain_id
    )


def _material_matches(
    row: TokenUsage,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: Optional[float],
) -> bool:
    return (
        int(row.prompt_tokens or 0) == int(prompt_tokens or 0)
        and int(row.completion_tokens or 0) == int(completion_tokens or 0)
        and row.cost_usd == cost_usd
    )


def _settle_pending_intent(
    session: Session,
    *,
    existing: TokenUsage,
    provider_id: Optional[str],
    model_name: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: Optional[float],
    agent_id: Optional[str],
    workspace_id: Optional[str],
    tenant_id: Optional[str],
    execution_id: Optional[str],
    chain_id: Optional[str],
    request_id: Optional[str],
) -> str:
    """Settle the exact pending/weak-unknown intent with one DB CAS.

    The conditional UPDATE only matches the recorded immutable binding while
    the row is still unknown/NULL. A stale writer that read the pending row
    cannot overwrite an actual settlement: it gets zero rows, reloads the
    authoritative row, and either returns an exact replay or refuses with a
    conflict. No binding field is reassigned.
    """
    cost_usd = _normalize_cost(cost_usd)
    binding = dict(
        request_id=request_id,
        provider_id=provider_id,
        model_name=model_name,
        agent_id=agent_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        execution_id=execution_id,
        chain_id=chain_id,
    )
    if not _intent_binding_matches(existing, **binding):
        raise ValueError("pending usage intent binding mismatch")

    stmt = (
        update(TokenUsage)
        .where(
            TokenUsage.attempt_id == str(existing.attempt_id),
            TokenUsage.request_id == request_id,
            TokenUsage.provider_id == provider_id,
            TokenUsage.model_name == model_name,
            TokenUsage.agent_id == agent_id,
            TokenUsage.workspace_id == workspace_id,
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.execution_id == execution_id,
            TokenUsage.chain_id == chain_id,
            TokenUsage.pricing_status == "unknown",
            TokenUsage.cost_usd.is_(None),
            TokenUsage.reserved_cost_usd == existing.reserved_cost_usd,
            TokenUsage.reservation_status == existing.reservation_status,
        )
        .values(
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
            total_tokens=int(prompt_tokens or 0) + int(completion_tokens or 0),
            cost_usd=cost_usd,
            pricing_status=_usage_pricing_status(cost_usd),
            reserved_cost_usd=(
                existing.reserved_cost_usd if cost_usd is None else 0.0),
            reservation_status=(
                "uncertain" if cost_usd is None else "settled"),
            billed=True,
        )
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    if result.rowcount == 1:
        session.commit()
        return str(existing.id)

    session.rollback()
    authoritative = (
        session.query(TokenUsage)
        .filter(TokenUsage.attempt_id == str(existing.attempt_id))
        .populate_existing()
        .first()
    )
    if authoritative is None:
        raise ValueError("pending usage intent disappeared")
    if (
        _intent_binding_matches(authoritative, **binding)
        and authoritative.billed is True
        and _material_matches(
            authoritative,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )
    ):
        return str(authoritative.id)
    raise ValueError(
        "pending usage intent changed or conflicting usage material")


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
    cost_usd = _normalize_cost(cost_usd)
    # Resolve the current SessionLocal at call time so scratch/test database
    # patches apply instead of a stale module-level binding.
    from core.database import SessionLocal

    session = None
    try:
        session = SessionLocal()
        if attempt_id:
            existing = session.query(TokenUsage).filter(
                TokenUsage.attempt_id == str(attempt_id)).first()
            if existing is not None:
                if (
                    existing.pricing_status == "unknown"
                    and existing.cost_usd is None
                ):
                    # Settle the exact pre-dispatch intent with one CAS over
                    # the immutable binding. A stale/conflicting writer cannot
                    # overwrite an actual settlement or reassign its scope.
                    return _settle_pending_intent(
                        session,
                        existing=existing,
                        provider_id=provider_id,
                        model_name=model_name,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost_usd=cost_usd,
                        agent_id=agent_id,
                        workspace_id=workspace_id,
                        tenant_id=tenant_id,
                        execution_id=execution_id,
                        chain_id=chain_id,
                        request_id=request_id,
                    )
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
            pricing_status=_usage_pricing_status(cost_usd),
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
    except Exception as settle_err:
        # A lost write is unpriced/unreconciled spend, not a successful
        # budget outcome. Keep the caller's transaction untouched. Never
        # expose raw SQL/params in the durable reason.
        mark_settlement_failure(
            f"settlement_write_failed:{type(settle_err).__name__}")
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        raise
    finally:
        if session is not None:
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
        Delegates to the one billing-policy reader so the limit/mode parsing
        cannot drift from the reservation path.
        """
        try:
            limit, _mode = read_billing_policy(
                self.db, tenant_id, strict=False)
            return float(limit)
        except Exception as e:
            logger.debug(
                f"Could not read budget limit from settings for {tenant_id}: {e}")
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
            today = _utc_today()
            start = start_date or date(today.year, today.month, 1)
            end = end_date or today
            start_dt = datetime.combine(start, datetime.min.time())
            end_dt = datetime.combine(end, datetime.max.time())
            return int(self.db.query(func.count(TokenUsage.id)).filter(
                TokenUsage.tenant_id == tenant_id,
                or_(TokenUsage.pricing_status == "unknown",
                    TokenUsage.cost_usd.is_(None)),
                # An active reservation with a known bound is a committed
                # reservation, not an unpriced actual; it is counted in
                # committed_spend_usd. An active reservation with no bound
                # remains an unpriced liability and is counted here.
                or_(TokenUsage.reservation_status != "active",
                    TokenUsage.reserved_cost_usd.is_(None)),
                TokenUsage.timestamp >= start_dt,
                TokenUsage.timestamp <= end_dt,
            ).scalar() or 0)
        except Exception as e:
            logger.warning(
                f"[SpendAggregationService] unpriced usage read failed for "
                f"{tenant_id}: {e}")
            raise

    def get_unattributed_unpriced(
        self, start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Count unknown-cost rows with no resolved tenant (unattributed).

        These are not assigned to any tenant budget by guessing. A hard stop
        must refuse until they are reconciled so the liability cannot
        silently disappear.
        """
        try:
            today = _utc_today()
            start = start_date or date(today.year, today.month, 1)
            end = end_date or today
            start_dt = datetime.combine(start, datetime.min.time())
            end_dt = datetime.combine(end, datetime.max.time())
            return int(self.db.query(func.count(TokenUsage.id)).filter(
                TokenUsage.tenant_id.is_(None),
                or_(TokenUsage.pricing_status == "unknown",
                    TokenUsage.cost_usd.is_(None)),
                TokenUsage.timestamp >= start_dt,
                TokenUsage.timestamp <= end_dt,
            ).scalar() or 0)
        except Exception as e:
            logger.warning(
                f"[SpendAggregationService] unattributed unpriced read "
                f"failed: {e}")
            raise

    def update_tenant_spend(
        self, tenant_id: str, *, persist: bool = True,
        include_liabilities: bool = False,
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
            today = _utc_today()
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
            # Unknown-cost liabilities travel WITH the spend read so a hard
            # stop cannot allow on a spend number that silently omits them.
            # A read failure here becomes {"error": ...} above, which the
            # hard-stop path treats as BUDGET_STATUS_UNAVAILABLE. Only the
            # budget preflight asks for them; dashboard callers keep the
            # previous result shape.
            unpriced_usage_rows = 0
            unattributed_unpriced_rows = 0
            reserved_spend_usd = 0.0
            if include_liabilities:
                start_dt = datetime.combine(cycle_start, datetime.min.time())
                end_dt = datetime.combine(today, datetime.max.time())
                reserved_result = self.db.query(
                    func.sum(TokenUsage.reserved_cost_usd)
                ).filter(
                    TokenUsage.tenant_id == tenant_id,
                    TokenUsage.reservation_status.in_(("active", "uncertain")),
                    TokenUsage.timestamp >= start_dt,
                    TokenUsage.timestamp <= end_dt,
                ).scalar()
                reserved_spend_usd = float(reserved_result or 0.0)
                unpriced_usage_rows = self.get_unpriced_usage(tenant_id)
                unattributed_unpriced_rows = (
                    self.get_unattributed_unpriced())
            committed_spend_usd = current_spend_usd + reserved_spend_usd
            utilization_percent = (
                committed_spend_usd / budget_limit * 100
                if budget_limit > 0 else 0.0)

            return {
                "tenant_id": tenant_id,
                "current_spend_usd": round(current_spend_usd, 4),
                "reserved_spend_usd": round(reserved_spend_usd, 4),
                "committed_spend_usd": round(committed_spend_usd, 4),
                "total_spend_usd": round(total_spend_usd, 4),
                "budget_limit_usd": budget_limit,
                "utilization_percent": round(utilization_percent, 2),
                "unpriced_usage_rows": unpriced_usage_rows,
                "unattributed_unpriced_rows": unattributed_unpriced_rows,
            }
        except Exception as e:
            logger.error(f"[SpendAggregationService] Error updating spend: {str(e)}")
            if persist:
                self.db.rollback()
            return {"error": str(e)}
