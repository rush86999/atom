"""
Persistent rate-usage records for quota-aware LLM routing.

The in-memory ``ProviderRateTracker`` window dies with the process; monthly
subscription allowances (e.g. OpenCode Go) survive restarts only if usage is
persisted. This module writes one row per tracked LLM call (best-effort) and
exposes monthly aggregates for the routing layer and the debug endpoint.

Design notes:

- The ``RateUsageRecord`` model is declared on the shared declarative base so
  dev ``create_all`` picks it up; the table is also lazily ensured on first use
  (``ensure_table``) so production/tests never depend on alembic bookkeeping.
- Writes are fire-and-forget: any failure logs at debug level and leaves the
  in-memory window authoritative for routing decisions (graceful degradation).
- Monthly reads are cached for 60s so the hot BPC path never hits the DB per
  request; the cache is only populated when monthly limits are configured.
"""
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import sessionmaker

from core.database import engine as _default_engine
from core.models import Base

logger = logging.getLogger(__name__)

MONTHLY_CACHE_SECONDS = 60


class RateUsageRecord(Base):
    """One tracked LLM call for quota-aware rate routing (opencode-go, ...)."""

    __tablename__ = "rate_usage_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id = Column(String(100), nullable=False, index=True)
    model_id = Column(String(200), nullable=True, index=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_rate_usage_month", "provider_id", "created_at"),
    )


class RateUsagePersistence:
    """Best-effort DB persistence + monthly aggregates for rate usage."""

    def __init__(self, engine=None) -> None:
        self._engine = engine or _default_engine
        self._session_factory = sessionmaker(bind=self._engine)
        self._lock = threading.Lock()
        self._table_ready = False
        # (provider_id, model_id|None, period) -> (ts, aggregated) cache
        self._monthly_cache: Dict[tuple, Any] = {}

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        if self._table_ready:
            return
        with self._lock:
            if self._table_ready:
                return
            try:
                Base.metadata.create_all(bind=self._engine, tables=[RateUsageRecord.__table__])
                self._table_ready = True
            except Exception as e:
                logger.debug(f"Could not ensure rate_usage_records table: {e}")

    # ------------------------------------------------------------------
    # Writes (fire-and-forget)
    # ------------------------------------------------------------------

    def record(self, provider_id: str, model_id: Optional[str],
               input_tokens: int, output_tokens: int) -> None:
        """Persist a tracked call (best-effort; never raises)."""
        try:
            self._ensure_table()
            if not self._table_ready:
                return
            session = self._session_factory()
            try:
                session.add(RateUsageRecord(
                    provider_id=provider_id,
                    model_id=model_id,
                    input_tokens=int(input_tokens or 0),
                    output_tokens=int(output_tokens or 0),
                ))
                session.commit()
            finally:
                session.close()
            self._monthly_cache.clear()  # stale after a write
        except Exception as e:
            logger.debug(f"Rate usage persist failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    # Monthly reads (cached)
    # ------------------------------------------------------------------

    def monthly_usage(self, provider_id: str, model_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Aggregated usage since the start of the current calendar month.

        Returns None when persistence is unavailable. ``model_id`` aggregates
        a single model; None aggregates the whole provider.
        """
        try:
            self._ensure_table()
            if not self._table_ready:
                return None
            now = datetime.now(timezone.utc)
            period = (now.year, now.month)
            cache_key = (provider_id, model_id, period)
            with self._lock:
                cached = self._monthly_cache.get(cache_key)
                if cached and time.time() - cached[0] < MONTHLY_CACHE_SECONDS:
                    return cached[1]
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            session = self._session_factory()
            try:
                q = session.query(
                    func.sum(RateUsageRecord.input_tokens).label("input_tokens"),
                    func.sum(RateUsageRecord.output_tokens).label("output_tokens"),
                    func.count(RateUsageRecord.id).label("requests"),
                ).filter(
                    RateUsageRecord.provider_id == provider_id,
                    RateUsageRecord.created_at >= month_start,
                )
                if model_id:
                    q = q.filter(RateUsageRecord.model_id == model_id)
                row = q.one()
            finally:
                session.close()
            result = {
                "provider": provider_id,
                "model": model_id,
                "period": f"{now.year}-{now.month:02d}",
                "requests": int(row.requests or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "total_tokens": int((row.input_tokens or 0) + (row.output_tokens or 0)),
            }
            with self._lock:
                self._monthly_cache[cache_key] = (time.time(), result)
            return result
        except Exception as e:
            logger.debug(f"Rate usage monthly read failed (non-fatal): {e}")
            return None


# Singleton instance
_persistence: Optional[RateUsagePersistence] = None
_singleton_lock = threading.Lock()


def get_rate_usage_persistence() -> RateUsagePersistence:
    """Get or create the singleton RateUsagePersistence instance."""
    global _persistence
    if _persistence is None:
        with _singleton_lock:
            if _persistence is None:
                _persistence = RateUsagePersistence()
                logger.info("Created RateUsagePersistence singleton instance")
    return _persistence
