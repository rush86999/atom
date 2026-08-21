# -*- coding: utf-8 -*-
"""Coverage wave 77b — standalone push for 6 backend modules to >=95%.

Targets (each >=95% with THIS file alone):
1. core/graphrag/community_detection.py          (Leiden / community detection)
2. core/graphrag/multi_hop_expansion.py          (cue-driven multi-hop expansion)
3. core/oracle/postcondition_verifiers.py        (R53 postcondition oracle)
4. core/memory/memory_consolidation_service.py   (POMDP episode sync/consolidation)
5. core/llm/registry/models.py                   (LLMModel registry model)
6. core/llm/registry/provider_health.py          (circuit-breaker health tracking)

Fully mocked: expression-evaluating fake session for the graphrag modules,
dict-backed fake cache for provider health, fake DB/lifecycle/manager for the
consolidation service, fake igraph/leidenalg modules for import-path coverage.
Zero LLM spend, zero network, no real DB.

BUG FIX (multi_hop_expansion.py:338): the early-termination check compared the
average relevance of a hop level against min_relevance_score — but every node
in that level already passed the per-node `relevance >= min` filter, so the
average could NEVER fall below the threshold and `enable_early_termination`
was dead code. Fixed: terminate when the average cannot survive one more hop
(avg < min_relevance / decay). Regression test:
TestEarlyTermination::test_early_termination_fires_when_average_cannot_survive_next_hop
"""

import asyncio
import builtins
import importlib
import json
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

from core.graphrag.community_detection import (
    ClusteringAlgorithm,
    Community,
    CommunityConfig,
    CommunityDetectionService,
    CommunityHierarchy,
    DetectionResult,
    LeidenAlgorithm,
    ResolutionPolicy,
    get_community_detector,
    get_leiden_algorithm,
)
from core.graphrag.multi_hop_expansion import (
    ActivationCue,
    ExpansionConfig,
    ExpansionNode,
    ExpansionPath,
    ExpansionResult,
    ExpansionStrategy,
    MultiHopExpander,
    SQLMultiHopExpander,
    TraversalConstraint,
    get_multi_hop_expander,
    get_sql_expander,
)
from core.llm.registry.models import LLMModel
from core.llm.registry.provider_health import (
    CONSECUTIVE_FAILURES_THRESHOLD,
    CONSECUTIVE_SUCCESSES_RECOVERY,
    DEGRADED_ERROR_RATE,
    HEALTH_STATE_TTL,
    HealthState,
    ProviderHealthService,
)
from core.memory.pomdp_memory_framework import (
    MemoryEntry,
    MemoryStatus,
    MemoryType,
    ObservationSpace,
)
from core.models import CommunityMembership, GraphCommunity, GraphEdge, GraphNode
from core.oracle import get_postcondition, validate
from core.oracle import postcondition_verifiers as pv  # noqa: F401  (registers verifiers)

import core.memory.memory_consolidation_service as mcs


def _run(coro):
    return asyncio.run(coro)


# ============================================================================
# Fake session: evaluates SQLAlchemy filter expressions against in-memory rows
# ============================================================================

def _bound_value(expr):
    v = getattr(expr.right, "effective_value", None)
    if v is None:
        v = getattr(expr.right, "value", None)
    return v


def _matches(expr, row):
    if isinstance(expr, BooleanClauseList):
        return any(_matches(c, row) for c in expr.clauses)
    if isinstance(expr, BinaryExpression):
        left, right = expr.left, expr.right
        op_name = getattr(expr.operator, "__name__", "")
        if op_name == "in_op":
            vals = _bound_value(expr)
            return getattr(row, left.name, None) in (vals or [])
        if hasattr(left, "name"):
            left_val = getattr(row, left.name, None)
        else:
            left_val = _bound_value(expr)
        if hasattr(right, "name"):
            return left_val == getattr(row, right.name, None)
        return left_val == _bound_value(expr)
    return True


def _model_key(model):
    tablename = getattr(model, "__tablename__", None)
    if tablename:
        return tablename
    table = getattr(model, "table", None)
    if table is not None:
        return table.name
    return str(model)


class FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model
        self._criteria = []

    def filter(self, *criteria):
        q = FakeQuery(self._session, self._model)
        q._criteria = list(criteria)
        return q

    def _rows(self):
        return self._session.rows_for(self._model)

    def _applies(self, row):
        return all(_matches(c, row) for c in self._criteria)

    def all(self):
        rows = [r for r in self._rows() if self._applies(r)]
        if not hasattr(self._model, "__tablename__") and getattr(self._model, "table", None) is not None:
            col = self._model
            return [(getattr(r, col.name),) for r in rows]
        return rows

    def first(self):
        for r in self._rows():
            if self._applies(r):
                return r
        return None

    def delete(self, synchronize_session=False):
        remaining = [r for r in self._rows() if not self._applies(r)]
        self._session.replace_rows(self._model, remaining)
        return len(self._rows()) - len(remaining)


class FakeSession:
    def __init__(self, model_rows=None):
        self._data = {}
        self.added = []
        self.rolled_back = False
        self._fail_commit = False
        for model, rows in (model_rows or {}).items():
            self._data[_model_key(model)] = list(rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def rows_for(self, model):
        return self._data.setdefault(_model_key(model), [])

    def replace_rows(self, model, rows):
        self._data[_model_key(model)] = rows

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self._fail_commit:
            raise RuntimeError("commit boom")

    def rollback(self):
        self.rolled_back = True


def gnode(nid, name=None, ntype="user", props=None, ws="ws-1"):
    return SimpleNamespace(
        id=nid, name=name or nid, type=ntype, properties=props or {}, workspace_id=ws,
    )


def gedge(src, tgt, rel="related_to", ws="ws-1", props=None):
    return SimpleNamespace(
        source_node_id=src, target_node_id=tgt, relationship_type=rel,
        workspace_id=ws, properties=props or {},
    )


def clique(prefix, size, ws="ws-1"):
    nodes = [gnode(f"{prefix}{i}", ntype="user", ws=ws) for i in range(1, size + 1)]
    edges = [
        gedge(f"{prefix}{i}", f"{prefix}{j}", rel="related_to", ws=ws)
        for i in range(1, size + 1) for j in range(i + 1, size + 1)
    ]
    return nodes, edges


# ============================================================================
# 1. provider_health
# ============================================================================

class FakeCache:
    def __init__(self, seed=None):
        self._store = dict(seed or {})
        self.writes = []

    async def get_async(self, key, tenant_id=None):
        return self._store.get(key)

    async def set_async(self, key, value, ttl=300, tenant_id=None):
        self._store[key] = value
        self.writes.append((key, value, ttl))
        return True

    def last_state(self):
        return json.loads(self.writes[-1][1])["current_state"]


def payload(state, **overrides):
    p = {
        "current_state": state.value,
        "success_count": 0,
        "error_count": 0,
        "consecutive_failures": 0,
        "consecutive_successes": 0,
        "avg_latency_ms": None,
    }
    p.update(overrides)
    return p


def seed_json(payload_dict):
    return json.dumps(payload_dict)


class TestProviderHealthRecordSuccess:
    async def test_first_request_becomes_healthy(self):
        cache = FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=100)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_rolling_latency_average(self):
        cache = FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=100)
        await svc.record_success("openai", latency_ms=300)
        data = json.loads(cache.writes[-1][1])
        assert data["success_count"] == 2
        assert data["consecutive_successes"] == 2
        assert data["consecutive_failures"] == 0
        assert abs(data["avg_latency_ms"] - 200.0) < 1e-9
        assert data["last_success_ts"] is not None

    async def test_success_uses_existing_latency_when_present(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.HEALTHY, success_count=4, error_count=0,
                    consecutive_successes=4, avg_latency_ms=100)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=200)
        data = json.loads(cache.writes[-1][1])
        assert abs(data["avg_latency_ms"] - 120.0) < 1e-9

    async def test_success_resets_failure_streak(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.UNHEALTHY, success_count=3, error_count=6,
                    consecutive_failures=5, consecutive_successes=0, avg_latency_ms=100)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        data = json.loads(cache.writes[-1][1])
        assert data["consecutive_failures"] == 0
        assert data["consecutive_successes"] == 1

    async def test_unhealthy_recovers_after_threshold_successes(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.UNHEALTHY, success_count=3, error_count=6,
                    consecutive_failures=5,
                    consecutive_successes=CONSECUTIVE_SUCCESSES_RECOVERY - 1)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_unhealthy_stays_unhealthy_below_threshold(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.UNHEALTHY, success_count=3, error_count=6,
                    consecutive_failures=5, consecutive_successes=3)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.UNHEALTHY.value

    async def test_degraded_recovers_after_threshold_successes(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.DEGRADED, success_count=30, error_count=4,
                    consecutive_failures=0,
                    consecutive_successes=CONSECUTIVE_SUCCESSES_RECOVERY - 1)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_rate_limited_recovers_after_threshold_successes(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.RATE_LIMITED, success_count=40, error_count=1,
                    consecutive_failures=0,
                    consecutive_successes=CONSECUTIVE_SUCCESSES_RECOVERY - 1)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_rate_limited_stays_limited_below_threshold(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.RATE_LIMITED, success_count=40, error_count=1,
                    consecutive_failures=0, consecutive_successes=2)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.RATE_LIMITED.value

    async def test_healthy_stays_healthy_on_success(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.HEALTHY, success_count=5, error_count=0,
                    consecutive_successes=5)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_data_written_with_ttl(self):
        cache = FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.writes[-1][2] == HEALTH_STATE_TTL

    async def test_default_cache_service_constructed(self):
        with patch("core.llm.registry.provider_health.UniversalCacheService") as cls:
            svc = ProviderHealthService()
            cls.assert_called_once_with()
            assert svc.cache is cls.return_value


class TestProviderHealthRecordFailure:
    async def test_first_failure_tracks_counters(self):
        cache = FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="timeout")
        data = json.loads(cache.writes[-1][1])
        assert data["error_count"] == 1
        assert data["consecutive_failures"] == 1
        assert data["consecutive_successes"] == 0
        assert data["last_error"] == "timeout"
        assert data["last_error_ts"] is not None
        assert await svc.get_health_state("openai") == HealthState.HEALTHY

    async def test_consecutive_failures_mark_unhealthy(self):
        cache = FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        for _ in range(CONSECUTIVE_FAILURES_THRESHOLD):
            await svc.record_failure("openai", error="api_error")
        assert cache.last_state() == HealthState.UNHEALTHY.value

    async def test_rate_limited_error_sets_rate_limited(self):
        cache = FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="rate_limited")
        assert cache.last_state() == HealthState.RATE_LIMITED.value

    async def test_error_rate_degraded_with_minimum_samples(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.HEALTHY, success_count=20, error_count=1)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="api_error")
        await svc.record_failure("openai", error="api_error")
        assert cache.last_state() == HealthState.DEGRADED.value

    async def test_error_rate_unhealthy_with_minimum_samples(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.HEALTHY, success_count=10, error_count=1)
        )})
        svc = ProviderHealthService(cache_service=cache)
        for _ in range(4):
            await svc.record_failure("openai", error="api_error")
        assert cache.last_state() == HealthState.UNHEALTHY.value

    async def test_no_state_flip_below_minimum_samples(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.HEALTHY, success_count=5, error_count=0)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="timeout")
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_failure_resets_success_streak(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.HEALTHY, success_count=10, error_count=0,
                    consecutive_successes=10)
        )})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="timeout")
        data = json.loads(cache.writes[-1][1])
        assert data["consecutive_successes"] == 0
        assert data["consecutive_failures"] == 1


class TestProviderHealthReads:
    async def test_default_state_for_unknown_provider(self):
        svc = ProviderHealthService(cache_service=FakeCache())
        assert await svc.get_health_state("nobody") == HealthState.HEALTHY

    async def test_get_health_state_round_trip(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.DEGRADED, success_count=20, error_count=4)
        )})
        svc = ProviderHealthService(cache_service=cache)
        assert await svc.get_health_state("openai") == HealthState.DEGRADED

    async def test_get_health_state_unknown_value_falls_back_healthy(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": '{"current_state": "swapping"}'})
        svc = ProviderHealthService(cache_service=cache)
        assert await svc.get_health_state("openai") == HealthState.HEALTHY

    async def test_corrupt_json_treated_as_missing(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": "{not json"})
        svc = ProviderHealthService(cache_service=cache)
        assert await svc.get_health_state("openai") == HealthState.HEALTHY

    async def test_safe_state_none_returns_healthy(self):
        assert ProviderHealthService._safe_state(None) == HealthState.HEALTHY

    async def test_safe_state_valid_returns_enum(self):
        assert ProviderHealthService._safe_state("degraded") == HealthState.DEGRADED

    async def test_safe_state_unknown_returns_healthy(self, caplog):
        with caplog.at_level("WARNING", logger="core.llm.registry.provider_health"):
            state = ProviderHealthService._safe_state("exploded")
        assert state == HealthState.HEALTHY
        assert "Unknown provider health state" in caplog.text

    async def test_get_health_metrics_empty_shape(self):
        svc = ProviderHealthService(cache_service=FakeCache())
        m = await svc.get_health_metrics("nobody")
        assert m["provider"] == "nobody"
        assert m["state"] == HealthState.HEALTHY.value
        assert m["success_count"] == 0
        assert m["error_count"] == 0
        assert m["consecutive_failures"] == 0
        assert m["avg_latency_ms"] is None

    async def test_get_health_metrics_full_shape(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": seed_json(
            payload(HealthState.RATE_LIMITED, success_count=40, error_count=2,
                    consecutive_failures=1, consecutive_successes=5,
                    avg_latency_ms=120.5, last_error="rate_limited")
        )})
        svc = ProviderHealthService(cache_service=cache)
        m = await svc.get_health_metrics("openai")
        assert m["state"] == HealthState.RATE_LIMITED.value
        assert m["success_count"] == 40
        assert m["error_count"] == 2
        assert m["consecutive_failures"] == 1
        assert m["consecutive_successes"] == 5
        assert m["avg_latency_ms"] == 120.5
        assert m["last_error"] == "rate_limited"
        assert m["last_success_ts"] is None

    async def test_get_health_metrics_unknown_state(self):
        cache = FakeCache(seed={"llm_registry:provider_health:openai": '{"current_state": "exploded", "success_count": 2}'})
        svc = ProviderHealthService(cache_service=cache)
        m = await svc.get_health_metrics("openai")
        assert m["state"] == HealthState.HEALTHY.value
        assert m["success_count"] == 2

    async def test_get_all_health_maps_providers(self):
        cache = FakeCache(seed={
            "llm_registry:provider_health:openai": seed_json(
                payload(HealthState.HEALTHY, success_count=5)),
            "llm_registry:provider_health:anthropic": seed_json(
                payload(HealthState.UNHEALTHY, success_count=1, error_count=5)),
        })
        svc = ProviderHealthService(cache_service=cache)
        all_health = await svc.get_all_health(["openai", "anthropic", "missing"])
        assert all_health["openai"]["state"] == HealthState.HEALTHY.value
        assert all_health["anthropic"]["state"] == HealthState.UNHEALTHY.value
        assert all_health["missing"]["state"] == HealthState.HEALTHY.value


class TestProviderHealthPriorityKeying:
    def test_priority_ordering(self):
        svc = ProviderHealthService(cache_service=FakeCache())
        assert svc.get_health_priority(HealthState.HEALTHY) == 0
        assert svc.get_health_priority(HealthState.DEGRADED) == 1
        assert svc.get_health_priority(HealthState.RATE_LIMITED) == 2
        assert svc.get_health_priority(HealthState.UNHEALTHY) == 3

    def test_priority_unknown_state_defaults_worst(self):
        svc = ProviderHealthService(cache_service=FakeCache())
        assert svc.get_health_priority("bogus") == 3

    def test_key_prefix(self):
        svc = ProviderHealthService(cache_service=FakeCache())
        assert svc._get_key("openai") == "llm_registry:provider_health:openai"

    def test_enum_values(self):
        assert HealthState.HEALTHY.value == "healthy"
        assert HealthState.DEGRADED.value == "degraded"
        assert HealthState.UNHEALTHY.value == "unhealthy"
        assert HealthState.RATE_LIMITED.value == "rate_limited"


# ============================================================================
# 2. registry models
# ============================================================================

class TestRegistryModels:
    def test_table_name(self):
        assert LLMModel.__tablename__ == "llm_models"

    def test_unique_constraint(self):
        names = [c.name for c in LLMModel.__table_args__ if isinstance(c, type(LLMModel.__table_args__[0])) and hasattr(c, "name")]
        assert "llm_models_unique_model" in names

    def test_metadata_column_mapping(self):
        assert "metadata" in LLMModel.__table__.c

    def test_hybrid_capabilities_set(self):
        assert LLMModel.HYBRID_CAPABILITIES == {
            "vision", "tools", "function_calling", "audio", "computer_use",
        }

    def test_get_hybrid_capabilities_returns_copy(self):
        caps = LLMModel.get_hybrid_capabilities()
        caps.add("custom")
        assert "custom" not in LLMModel.HYBRID_CAPABILITIES

    def test_id_defaults_to_uuid(self):
        assert LLMModel.__table__.c.id.default is not None
        m = LLMModel(id=uuid.uuid4(), tenant_id="t", provider="p", model_name="m")
        assert isinstance(m.id, uuid.UUID)
        fresh = LLMModel(tenant_id="t", provider="p", model_name="m")
        assert fresh.id is None  # column default applies at flush, not construction

    def test_sync_capabilities_sets_all_flags(self):
        m = LLMModel(
            tenant_id="t", provider="p", model_name="m",
            capabilities=["vision", "tools", "function_calling", "audio", "computer_use"],
        )
        m.sync_capabilities()
        assert m.supports_vision is True
        assert m.supports_tools is True
        assert m.supports_function_calling is True
        assert m.supports_audio is True
        assert m.supports_computer_use is True

    def test_sync_capabilities_clears_unset_flags(self):
        m = LLMModel(
            tenant_id="t", provider="p", model_name="m",
            capabilities=["tools"],
            supports_vision=True, supports_audio=True,
        )
        m.sync_capabilities()
        assert m.supports_tools is True
        assert m.supports_vision is False
        assert m.supports_audio is False
        assert m.supports_function_calling is False
        assert m.supports_computer_use is False

    def test_sync_capabilities_none_caps(self):
        m = LLMModel(tenant_id="t", provider="p", model_name="m", capabilities=None)
        m.sync_capabilities()
        assert m.supports_vision is False

    def test_to_dict_full(self):
        now = datetime(2026, 8, 1, 12, 0, 0)
        m = LLMModel(
            id=uuid.uuid4(), tenant_id="t1", provider="openai", model_name="gpt-4o",
            context_window=128000,
            input_price_per_token=Decimal("0.0000025"),
            output_price_per_token=Decimal("0.00001"),
            capabilities=["vision", "tools"],
            provider_metadata={"family": "gpt"},
            supports_vision=True,
            supports_tools=True,
            supports_function_calling=False,
            supports_audio=False,
            supports_computer_use=False,
            discovered_at=now, created_at=now, updated_at=now, last_refreshed_at=now,
            is_deprecated=True, deprecated_at=now, deprecation_reason="superseded",
            quality_score=Decimal("95.50"),
        )
        d = m.to_dict()
        assert d["provider"] == "openai"
        assert d["model_name"] == "gpt-4o"
        assert d["context_window"] == 128000
        assert d["input_price_per_token"] == 2.5e-06
        assert d["output_price_per_token"] == 1e-05
        assert d["capabilities"] == ["vision", "tools"]
        assert d["metadata"] == {"family": "gpt"}
        assert d["supports_vision"] is True
        assert d["supports_computer_use"] is False
        assert d["discovered_at"] == "2026-08-01T12:00:00"
        assert d["updated_at"] == "2026-08-01T12:00:00"
        assert d["last_refreshed_at"] == "2026-08-01T12:00:00"
        assert d["is_deprecated"] is True
        assert d["deprecated_at"] == "2026-08-01T12:00:00"
        assert d["deprecation_reason"] == "superseded"
        assert d["quality_score"] == 95.5

    def test_to_dict_empty_branches(self):
        m = LLMModel(tenant_id="t", provider="p", model_name="m")
        d = m.to_dict()
        assert d["context_window"] is None
        assert d["input_price_per_token"] is None
        assert d["output_price_per_token"] is None
        assert d["capabilities"] == []
        assert d["metadata"] == {}
        assert d["discovered_at"] is None
        assert d["created_at"] is None
        assert d["updated_at"] is None
        assert d["last_refreshed_at"] is None
        assert d["deprecated_at"] is None
        assert d["quality_score"] is None
        assert d["id"] == str(m.id)

    def test_repr(self):
        m = LLMModel(tenant_id="t1", provider="openai", model_name="gpt-4o")
        r = repr(m)
        assert r.startswith("<LLMModel(id=")
        assert "tenant_id=t1" in r
        assert "provider=openai" in r
        assert "model_name=gpt-4o" in r


# ============================================================================
# 3. postcondition verifiers
# ============================================================================

class FakeOracleDB:
    def __init__(self, row=None, raise_on_query=False):
        self._row = row
        self._raise_on_query = raise_on_query

    def query(self, model):
        if self._raise_on_query:
            raise RuntimeError("db exploded")
        return SimpleNamespace(
            filter=lambda *a, **kw: SimpleNamespace(first=lambda: self._row)
        )


def wf(status, wf_id="wf_1"):
    return SimpleNamespace(id=wf_id, status=status)


class TestWorkflowVerifier:
    def test_missing_ctx(self):
        res = _run(pv._verify_workflow_triggered({}))
        assert res.action == "trigger_workflow"
        assert res.verified is False
        assert res.evidence == "missing workflow_id or db session"

    def test_missing_db(self):
        res = _run(pv._verify_workflow_triggered({"workflow_id": "wf_1"}))
        assert res.verified is False

    @pytest.mark.parametrize("status", ["active", "running", "enabled", "true", "Active", "RUNNING"])
    def test_active_statuses_verified(self, status):
        res = _run(pv._verify_workflow_triggered(
            {"workflow_id": "wf_1", "db": FakeOracleDB(wf(status))}
        ))
        assert res.verified is True
        assert res.evidence == "workflow.status == 'Active'" or "workflow.status" in res.evidence

    @pytest.mark.parametrize("status", ["paused", "archived", "completed", "draft", ""])
    def test_inactive_statuses_unverified(self, status):
        res = _run(pv._verify_workflow_triggered(
            {"workflow_id": "wf_1", "db": FakeOracleDB(wf(status))}
        ))
        assert res.verified is False

    def test_status_none_unverified(self):
        res = _run(pv._verify_workflow_triggered(
            {"workflow_id": "wf_1", "db": FakeOracleDB(wf(None))}
        ))
        assert res.verified is False

    def test_workflow_not_in_db(self):
        res = _run(pv._verify_workflow_triggered(
            {"workflow_id": "wf_1", "db": FakeOracleDB(None)}
        ))
        assert res.verified is False
        assert "not in DB" in res.evidence

    def test_db_read_back_exception(self):
        res = _run(pv._verify_workflow_triggered(
            {"workflow_id": "wf_1", "db": FakeOracleDB(raise_on_query=True)}
        ))
        assert res.verified is False
        assert "DB read-back failed" in res.evidence


class TestTaskVerifier:
    def test_missing_ctx(self):
        res = _run(pv._verify_task_created({}))
        assert res.action == "tasks.create"
        assert res.verified is False
        assert res.evidence == "missing task_id or db session"

    def test_task_present(self):
        res = _run(pv._verify_task_created(
            {"task_id": "task_1", "db": FakeOracleDB(SimpleNamespace(id="task_1"))}
        ))
        assert res.verified is True
        assert "present in DB" in res.evidence

    def test_task_absent(self):
        res = _run(pv._verify_task_created(
            {"task_id": "task_1", "db": FakeOracleDB(None)}
        ))
        assert res.verified is False
        assert "absent in DB" in res.evidence

    def test_db_read_back_exception(self):
        res = _run(pv._verify_task_created(
            {"task_id": "task_1", "db": FakeOracleDB(raise_on_query=True)}
        ))
        assert res.verified is False
        assert "DB read-back failed" in res.evidence


class TestOracleRegistry:
    def test_verifiers_registered(self):
        assert callable(get_postcondition("trigger_workflow"))
        assert callable(get_postcondition("tasks.create"))
        assert get_postcondition("no_such_action") is None

    def test_validate_workflow_round_trip(self):
        res = _run(validate("trigger_workflow", {"workflow_id": "wf_1", "db": FakeOracleDB(wf("active"))}))
        assert res is not None
        assert res.verified is True

    def test_validate_task_round_trip(self):
        res = _run(validate("tasks.create", {"task_id": "task_1", "db": FakeOracleDB(SimpleNamespace(id="task_1"))}))
        assert res is not None
        assert res.verified is True

    def test_validate_unknown_action_none(self):
        assert _run(validate("no_such_action", {})) is None


# ============================================================================
# 4. memory consolidation service
# ============================================================================

def make_episode(**overrides):
    defaults = dict(
        id="ep_1", agent_id="agent_1", status="completed",
        started_at=datetime.now(), tenant_id="ws_1",
        task_description="analyze sales", human_intervention_count=0,
        total_steps=6, maturity_at_time="AUTONOMOUS", importance_score=0.8,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_observation(agent_id="agent_1", task_type="WORKFLOW"):
    return ObservationSpace(
        timestamp=datetime.now(), agent_id=agent_id, workspace_id="ws_1",
        task_type=task_type, user_intent="intent", available_tools=[],
        system_state={}, resource_constraints={}, recent_success_rate=1.0,
        recent_intervention_count=0,
    )


def make_memory(agent_id="agent_1", quality=0.9, access=12, status=MemoryStatus.CONSOLIDATED,
                task_type="WORKFLOW", created=None, learning=0.5, success=True,
                intervention=False):
    return MemoryEntry(
        id="mem_12345678", memory_type=MemoryType.EPISODIC,
        observation=make_observation(agent_id=agent_id, task_type=task_type),
        content={}, status=status, quality_score=quality, access_count=access,
        learning_value=learning, success_outcome=success,
        intervention_required=intervention,
        created_at=created if created is not None else datetime.now(),
    )


class MemFakeQuery:
    def __init__(self, rows, limit=None):
        self._rows = rows
        self._limit = limit

    def filter(self, *a, **kw):
        return self

    def order_by(self, *a, **kw):
        return self

    def limit(self, n):
        return MemFakeQuery(self._rows, limit=n)

    def all(self):
        rows = self._rows
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows


class MemFakeDB:
    def __init__(self, episodes):
        self._episodes = episodes

    def query(self, *a, **kw):
        return MemFakeQuery(self._episodes)


def make_lifecycle():
    lc = MagicMock()
    lc.consolidate_similar_episodes = AsyncMock(return_value={"consolidated": 3, "skipped": 0, "errors": 0})
    lc.decay_old_episodes = AsyncMock(return_value={"affected": 2, "expired": 1})
    return lc


def make_manager(memories=None):
    mgr = MagicMock()
    mgr._episodic_memory = memories if memories is not None else {}
    mgr.trigger_manage_cycle = MagicMock(return_value=None)
    mgr.get_memory_statistics = MagicMock(return_value={"total": len(mgr._episodic_memory)})
    return mgr


def build_svc(db=None, lifecycle=None, manager=None, pomdp=True, raise_mgr=None):
    lc = lifecycle if lifecycle is not None else make_lifecycle()
    mgr = manager if manager is not None else make_manager()
    with patch.object(mcs, "POMDP_AVAILABLE", pomdp), \
            patch.object(mcs, "get_lancedb_handler", return_value=MagicMock()), \
            patch.object(mcs, "EpisodeLifecycleService", return_value=lc), \
            patch.object(mcs, "get_memory_manager",
                         side_effect=raise_mgr if raise_mgr else lambda db, lh: mgr):
        svc = mcs.MemoryConsolidationService(db or MemFakeDB([]))
    return svc, lc, mgr


class TestConsolidationInit:
    def test_pomdp_unavailable_degraded(self):
        svc, _, _ = build_svc(pomdp=False)
        assert svc.memory_manager is None
        assert svc.pomdp_consolidation is None
        assert svc._consolidation_in_progress is False

    def test_pomdp_init_failure_logged(self, caplog):
        def boom(db, lh):
            raise RuntimeError("boom")

        with caplog.at_level("WARNING", logger="core.memory.memory_consolidation_service"):
            svc, _, _ = build_svc(raise_mgr=boom)
        assert svc.memory_manager is None
        assert "Failed to initialize POMDP consolidation" in caplog.text

    def test_pomdp_full_init(self):
        svc, _, mgr = build_svc()
        assert svc.memory_manager is mgr
        assert svc.pomdp_consolidation is not None

    def test_factory(self):
        with patch.object(mcs, "POMDP_AVAILABLE", False), \
                patch.object(mcs, "get_lancedb_handler", return_value=MagicMock()), \
                patch.object(mcs, "EpisodeLifecycleService", return_value=MagicMock()):
            svc = mcs.get_consolidation_service(MemFakeDB([]))
        assert isinstance(svc, mcs.MemoryConsolidationService)

    def test_import_error_sets_pomdp_unavailable(self, caplog):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if "pomdp_memory_framework" in name:
                raise ImportError("simulated missing pomdp")
            return real_import(name, *args, **kwargs)

        mod_name = "core.memory.memory_consolidation_service"
        with patch.object(builtins, "__import__", side_effect=fake_import), \
                caplog.at_level("WARNING", logger="core.memory.memory_consolidation_service"):
            mod = importlib.reload(sys.modules[mod_name])
        assert mod.POMDP_AVAILABLE is False
        assert "POMDP Memory Framework not available" in caplog.text
        importlib.reload(sys.modules[mod_name])
        assert sys.modules[mod_name].POMDP_AVAILABLE is True


class TestSyncEpisodes:
    def test_pomdp_unavailable_zeros(self):
        svc, _, _ = build_svc(pomdp=False)
        assert _run(svc.sync_episodes_to_memory("agent_1")) == {"synced": 0, "skipped": 0, "errors": 0}

    def test_sync_success_derives_entry_fields(self):
        svc, _, mgr = build_svc()
        episodes = [
            make_episode(id="ep_1", human_intervention_count=0, total_steps=6),
            make_episode(id="ep_2", human_intervention_count=2, total_steps=4),
        ]
        svc.db = MemFakeDB(episodes)
        result = _run(svc.sync_episodes_to_memory("agent_1"))
        assert result == {"synced": 2, "skipped": 0, "errors": 0}
        e1 = mgr._episodic_memory["ep_1"]
        e2 = mgr._episodic_memory["ep_2"]
        assert e1.reward == 1.0
        assert e2.reward == 0.5
        assert e1.next_state == "success"
        assert e2.next_state == "partial_success"
        assert e1.success_outcome is True
        assert e2.intervention_required is True
        assert e1.content["episode_id"] == "ep_1"
        assert e1.quality_score == 0.8
        assert e1.task_complexity == 4
        assert e1.autonomy_level == 4
        assert e1.status == MemoryStatus.INDEXED

    def test_sync_limit_respected(self):
        svc, _, mgr = build_svc()
        svc.db = MemFakeDB([make_episode(id=f"ep_{i}") for i in range(3)])
        result = _run(svc.sync_episodes_to_memory("agent_1", limit=1))
        assert result["synced"] == 1

    def test_sync_error_episode_counted(self):
        svc, _, mgr = build_svc()
        bad = make_episode(id="bad", human_intervention_count=None)
        good = make_episode(id="good")
        svc.db = MemFakeDB([bad, good])
        result = _run(svc.sync_episodes_to_memory("agent_1"))
        assert result == {"synced": 1, "skipped": 0, "errors": 1}
        assert "good" in mgr._episodic_memory


class TestConsolidationHelpers:
    def test_observation_mapping(self):
        svc, _, _ = build_svc(pomdp=False)
        obs = svc._episode_to_observation(make_episode())
        assert obs.agent_id == "agent_1"
        assert obs.workspace_id == "ws_1"
        assert obs.user_intent == "analyze sales"
        assert obs.recent_success_rate == 1.0
        assert obs.recent_intervention_count == 0

    def test_observation_defaults(self):
        svc, _, _ = build_svc(pomdp=False)
        obs = svc._episode_to_observation(make_episode(tenant_id=None, started_at=None))
        assert obs.workspace_id == "default"
        assert obs.timestamp is not None

    def test_task_complexity_branches(self):
        svc, _, _ = build_svc(pomdp=False)
        assert svc._infer_task_complexity(make_episode(human_intervention_count=0, total_steps=6)) == 4
        assert svc._infer_task_complexity(make_episode(human_intervention_count=0, total_steps=2)) == 3
        assert svc._infer_task_complexity(make_episode(human_intervention_count=0, total_steps=None)) == 3
        assert svc._infer_task_complexity(make_episode(human_intervention_count=1, total_steps=5)) == 2
        assert svc._infer_task_complexity(make_episode(human_intervention_count=3, total_steps=5)) == 1

    def test_autonomy_level_branches(self):
        svc, _, _ = build_svc(pomdp=False)
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="STUDENT")) == 1
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="INTERN")) == 2
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="SUPERVISED")) == 3
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="AUTONOMOUS")) == 4
        assert svc._infer_autonomy_level(make_episode(maturity_at_time="UNKNOWN")) == 1


class TestConsolidationCycle:
    def test_already_running_guard(self):
        svc, _, _ = build_svc(pomdp=False)
        svc._consolidation_in_progress = True
        assert _run(svc.run_consolidation_cycle("agent_1")) == {"consolidated": 0, "status": "already_running"}

    def test_agent_path_uses_pomdp_and_lifecycle(self):
        svc, lc, mgr = build_svc()
        mgr._episodic_memory = {"a": make_memory(status=MemoryStatus.EXPIRED)}
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(return_value=7)
        result = _run(svc.run_consolidation_cycle("agent_1"))
        svc.pomdp_consolidation.consolidate_memories.assert_awaited_once_with(agent_id="agent_1", batch_size=50)
        mgr.trigger_manage_cycle.assert_called_once_with()
        lc.consolidate_similar_episodes.assert_awaited_once_with(agent_id="agent_1", similarity_threshold=0.85)
        assert result["consolidated"] == 10
        assert result["expired"] == 1
        assert result["duration_seconds"] >= 0.0
        assert svc._consolidation_in_progress is False
        assert svc._last_consolidation is not None

    def test_all_agents_path_skips_pomdp_consolidation(self):
        svc, lc, _ = build_svc()
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(return_value=7)
        result = _run(svc.run_consolidation_cycle())
        svc.pomdp_consolidation.consolidate_memories.assert_not_awaited()
        lc.consolidate_similar_episodes.assert_not_awaited()
        assert result["consolidated"] == 0

    def test_pomdp_unavailable_runs_lifecycle_only(self):
        svc, lc, _ = build_svc(pomdp=False)
        result = _run(svc.run_consolidation_cycle("agent_1"))
        assert result["consolidated"] == 3
        assert svc._consolidation_in_progress is False

    def test_exception_resets_in_progress_flag(self):
        svc, _, _ = build_svc()
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            _run(svc.run_consolidation_cycle("agent_1"))
        assert svc._consolidation_in_progress is False


class TestForgettingCurve:
    def test_pomdp_unavailable_falls_back_to_lifecycle(self):
        svc, lc, _ = build_svc(pomdp=False)
        assert _run(svc.apply_forgetting_curve("agent_1", days_threshold=7)) == {"affected": 2, "expired": 1}
        lc.decay_old_episodes.assert_awaited_once_with(days_threshold=7)

    def test_pomdp_unavailable_default_threshold(self):
        svc, lc, _ = build_svc(pomdp=False)
        _run(svc.apply_forgetting_curve("agent_1"))
        lc.decay_old_episodes.assert_awaited_once_with(days_threshold=90)

    def test_decay_and_skip_other_agents(self):
        old = make_memory(quality=0.9, created=datetime.now() - timedelta(days=40))
        other = make_memory(agent_id="other", created=datetime.now() - timedelta(days=40))
        svc, _, _ = build_svc(manager=make_manager({"old": old, "other": other}))
        result = _run(svc.apply_forgetting_curve("agent_1", days_threshold=30))
        assert result == {"affected": 1, "expired": 0}
        assert old.quality_score < 0.9
        assert other.quality_score == 0.9

    def test_low_quality_marked_expired(self):
        old = make_memory(quality=0.11, created=datetime.now() - timedelta(days=100))
        svc, _, _ = build_svc(manager=make_manager({"old": old}))
        result = _run(svc.apply_forgetting_curve("agent_1", days_threshold=1))
        assert result == {"affected": 1, "expired": 1}
        assert old.status == MemoryStatus.EXPIRED

    def test_recent_memory_untouched(self):
        fresh = make_memory(created=datetime.now())
        svc, _, _ = build_svc(manager=make_manager({"fresh": fresh}))
        assert _run(svc.apply_forgetting_curve("agent_1", days_threshold=30)) == {"affected": 0, "expired": 0}


class TestReplayCriticalMemories:
    def test_pomdp_unavailable_empty(self):
        svc, _, _ = build_svc(pomdp=False)
        assert _run(svc.replay_critical_memories("agent_1")) == []

    def test_filters_and_replays(self):
        eligible = make_memory(quality=0.9, access=15, learning=0.8)
        memories = {
            "eligible": eligible,
            "lowq": make_memory(quality=0.6, access=15),
            "few": make_memory(quality=0.9, access=3),
            "exp": make_memory(quality=0.9, access=15, status=MemoryStatus.EXPIRED),
            "other": make_memory(agent_id="other", quality=0.9, access=15),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        replayed = _run(svc.replay_critical_memories("agent_1", limit=5))
        assert len(replayed) == 1
        assert eligible.access_count == 16
        assert eligible.quality_score == pytest.approx(0.945)
        assert eligible.learning_value == pytest.approx(0.84)
        assert replayed[0]["memory_id"] == "mem_1234"

    def test_sorted_by_learning_value_and_limited(self):
        memories = {
            f"m{i}": make_memory(quality=0.9, access=15, learning=(i + 1) / 10.0)
            for i in range(4)
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        replayed = _run(svc.replay_critical_memories("agent_1", limit=2))
        assert len(replayed) == 2
        assert replayed[0]["learning_value"] > replayed[1]["learning_value"]


class TestExtractPatterns:
    def test_pomdp_unavailable_empty(self):
        svc, _, _ = build_svc(pomdp=False)
        assert _run(svc.extract_patterns("agent_1")) == []

    def test_pattern_found_with_metrics(self):
        memories = {f"m{i}": make_memory(quality=0.8, success=True, intervention=False) for i in range(3)}
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "WORKFLOW"
        assert patterns[0]["sample_size"] == 3
        assert patterns[0]["avg_quality"] == 0.8
        assert patterns[0]["success_rate"] == 1.0
        assert patterns[0]["avg_intervention_rate"] == 0.0

    def test_below_min_size_skipped(self):
        memories = {f"m{i}": make_memory() for i in range(2)}
        svc, _, _ = build_svc(manager=make_manager(memories))
        assert _run(svc.extract_patterns("agent_1")) == []

    def test_unknown_task_type_and_status_filter(self):
        memories = {
            "a": make_memory(task_type=None),
            "b": make_memory(status=MemoryStatus.INDEXED),
            "c": make_memory(task_type=None),
            "d": make_memory(task_type=None),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert len(patterns) == 1
        assert patterns[0]["pattern_type"] == "UNKNOWN"
        assert patterns[0]["sample_size"] == 3

    def test_mixed_success_and_intervention_rates(self):
        memories = {
            "a": make_memory(success=True, intervention=False),
            "b": make_memory(success=False, intervention=True),
            "c": make_memory(success=True, intervention=True),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert patterns[0]["success_rate"] == pytest.approx(0.667, abs=0.001)
        assert patterns[0]["avg_intervention_rate"] == pytest.approx(0.667, abs=0.001)

    def test_multiple_task_types(self):
        memories = {
            "a": make_memory(task_type="REPORT"), "b": make_memory(task_type="REPORT"),
            "c": make_memory(task_type="REPORT"), "d": make_memory(task_type="WORKFLOW"),
            "e": make_memory(task_type="WORKFLOW"), "f": make_memory(task_type="WORKFLOW"),
        }
        svc, _, _ = build_svc(manager=make_manager(memories))
        patterns = _run(svc.extract_patterns("agent_1"))
        assert {p["pattern_type"] for p in patterns} == {"REPORT", "WORKFLOW"}


class TestConsolidationStatus:
    def test_status_never_consolidated(self):
        svc, _, _ = build_svc(pomdp=False)
        status = svc.get_consolidation_status()
        assert status["last_consolidation"] is None
        assert status["in_progress"] is False
        assert status["pomdp_available"] is False
        assert status["memory_statistics"] == {}

    def test_status_after_cycle(self):
        svc, _, mgr = build_svc()
        mgr.get_memory_statistics = MagicMock(return_value={"total": 5})
        svc.pomdp_consolidation.consolidate_memories = AsyncMock(return_value=1)
        _run(svc.run_consolidation_cycle("agent_1"))
        status = svc.get_consolidation_status()
        assert status["last_consolidation"] is not None
        assert status["in_progress"] is False
        assert status["pomdp_available"] is True
        assert status["memory_statistics"] == {"total": 5}


# ============================================================================
# 5. multi-hop expansion
# ============================================================================

class TestExpansionDataclasses:
    def test_expansion_node_eq_hash(self):
        a = ExpansionNode(id="x", name="x", entity_type="t")
        b = ExpansionNode(id="x", name="x", entity_type="t")
        c = ExpansionNode(id="y", name="y", entity_type="t")
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert a in {b}

    def test_expansion_path_add_hop_with_decay(self):
        path = ExpansionPath()
        node_x = ExpansionNode(id="x", name="x", entity_type="t", relevance_score=0.8, confidence=0.9)
        path.add_hop(node_x, "related_to", decay=0.5)
        assert path.nodes == [node_x]
        assert path.relationships == ["related_to"]
        assert path.total_relevance == pytest.approx(0.8 * 0.5)
        assert path.confidence == pytest.approx(0.9)

    def test_expansion_path_add_hop_default_decay(self):
        path = ExpansionPath()
        node_x = ExpansionNode(id="x", name="x", entity_type="t", relevance_score=0.8)
        path.add_hop(node_x, "related_to")
        assert path.total_relevance == pytest.approx(0.8 * ExpansionConfig().relevance_decay)

    def test_enums(self):
        assert ExpansionStrategy.BFS.value == "bfs"
        assert ActivationCue.CONFIDENCE_THRESHOLD.value == "confidence"
        assert TraversalConstraint.MAX_HOPS.value == "max_hops"


def expander_config(**overrides):
    defaults = dict(
        max_hop_depth=4, max_nodes_per_hop=50, max_total_nodes=200,
        min_relevance_score=0.3, relevance_decay=0.85,
        enable_early_termination=True,
    )
    defaults.update(overrides)
    return ExpansionConfig(**defaults)


class TestMultiHopExpander:
    def test_expand_start_node_missing(self):
        sess = FakeSession({GraphNode: [gnode("n2")], GraphEdge: []})
        result = MultiHopExpander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 0
        assert result.max_depth_reached == 0
        assert result.metadata == {}

    def test_expand_start_node_in_other_workspace(self):
        sess = FakeSession({GraphNode: [gnode("n1", ws="ws-2")], GraphEdge: []})
        result = MultiHopExpander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 0

    def test_expand_chain_full_depth(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3"), gnode("n4")]
        edges = [gedge("n1", "n2"), gedge("n2", "n3"), gedge("n3", "n4")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        result = MultiHopExpander(expander_config(max_hop_depth=4)).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 4
        assert result.max_depth_reached == 3
        assert result.strategy_used == ExpansionStrategy.BIDIRECTIONAL
        assert result.metadata["workspace_id"] == "ws-1"
        assert result.metadata["visited_count"] == 4
        assert result.metadata["path_count"] == 3
        assert result.relationships[0]["type"] == "related_to"
        assert result.relationships[0]["hop_level"] == 1

    def test_expand_cycle_dedup(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [gedge("n1", "n2"), gedge("n2", "n1")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        result = MultiHopExpander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 2
        assert result.max_depth_reached == 1

    def test_expand_relevance_filter_skips_all(self):
        nodes = [gnode("n1"), gnode("n2", ntype="gadget")]
        edges = [gedge("n1", "n2", rel="weird_rel")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        cfg = expander_config(min_relevance_score=0.9)
        result = MultiHopExpander(cfg).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 1
        assert result.max_depth_reached == 0

    def test_expand_max_total_nodes_hard_cap(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3")]
        edges = [gedge("n1", "n2"), gedge("n2", "n3")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        cfg = expander_config(max_total_nodes=2)
        result = MultiHopExpander(cfg).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 2
        assert result.max_depth_reached == 1

    def test_expand_max_nodes_per_hop_truncates(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3"), gnode("n4"), gnode("n5")]
        edges = [gedge("n1", "n2"), gedge("n1", "n3"), gedge("n1", "n4"), gedge("n2", "n5")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        cfg = expander_config(max_nodes_per_hop=2)
        result = MultiHopExpander(cfg).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 4
        assert result.max_depth_reached == 2

    def test_expand_branching_paths(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3")]
        edges = [gedge("n1", "n2"), gedge("n1", "n3")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        result = MultiHopExpander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 3
        assert result.metadata["path_count"] == 2

    def test_expand_uses_patched_get_db_session(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [gedge("n1", "n2")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        with patch("core.graphrag.multi_hop_expansion.get_db_session", return_value=sess):
            result = MultiHopExpander().expand("n1", "ws-1")
        assert result.total_nodes_found == 2

    def test_get_neighbors_both_directions(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3")]
        edges = [gedge("n1", "n2"), gedge("n2", "n3")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        current = ExpansionNode(id="n2", name="n2", entity_type="user")
        neighbors = MultiHopExpander()._get_neighbors_with_cues(current, "ws-1", sess)
        assert {n.id for n, _, _ in neighbors} == {"n1", "n3"}

    def test_get_neighbors_missing_target_skipped(self):
        nodes = [gnode("n1")]
        edges = [gedge("n1", "n9")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        current = ExpansionNode(id="n1", name="n1", entity_type="user")
        assert MultiHopExpander()._get_neighbors_with_cues(current, "ws-1", sess) == []

    def test_get_neighbors_none_rel_type_defaults(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [gedge("n1", "n2", rel=None)]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        current = ExpansionNode(id="n1", name="n1", entity_type="user")
        neighbors = MultiHopExpander()._get_neighbors_with_cues(current, "ws-1", sess)
        assert neighbors[0][1] == "related_to"

    def test_get_neighbors_sorted_by_activation_desc(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3")]
        edges = [gedge("n1", "n3", rel="weird_rel"), gedge("n1", "n2", rel="belongs_to")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        current = ExpansionNode(id="n1", name="n1", entity_type="user")
        neighbors = MultiHopExpander()._get_neighbors_with_cues(current, "ws-1", sess)
        assert [n.id for n, _, _ in neighbors] == ["n2", "n3"]

    def test_get_neighbors_top_n(self):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3"), gnode("n4")]
        edges = [gedge("n1", "n2"), gedge("n1", "n3"), gedge("n1", "n4")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        current = ExpansionNode(id="n1", name="n1", entity_type="user")
        cfg = expander_config(max_nodes_per_hop=2)
        assert len(MultiHopExpander(cfg)._get_neighbors_with_cues(current, "ws-1", sess)) == 2

    def test_activation_score_cues(self):
        expander = MultiHopExpander()
        to_node = gnode("n2", ntype="user", props={})
        from_node = ExpansionNode(id="n1", name="n1", entity_type="user")
        base = expander._calculate_activation_score(from_node, to_node, "weird_rel", "outgoing", None, {})
        assert base == pytest.approx(0.5 + 0.15 + 0.2 + 0.1)
        incoming = expander._calculate_activation_score(from_node, to_node, "weird_rel", "incoming", None, {})
        assert incoming == pytest.approx(base - 0.1)
        known_rel = expander._calculate_activation_score(from_node, to_node, "belongs_to", "incoming", None, {})
        assert known_rel == pytest.approx(0.5 + 0.3 + 0.2)
        unknown_entity = expander._calculate_activation_score(
            from_node, gnode("n3", ntype="gadget"), "belongs_to", "incoming", None, {})
        assert unknown_entity == pytest.approx(0.5 + 0.3 + 0.1)
        clamped = expander._calculate_activation_score(
            from_node, to_node, "belongs_to", "outgoing", None, {})
        assert clamped == 1.0

    def test_activation_score_confidence_sources(self):
        expander = MultiHopExpander()
        from_node = ExpansionNode(id="n1", name="n1", entity_type="user")
        to_node = gnode("n2", ntype="user")
        with_edge = expander._calculate_activation_score(
            from_node, to_node, "weird_rel", "outgoing", None, {"confidence": 0.5})
        with_node = expander._calculate_activation_score(
            from_node, gnode("n3", ntype="user", props={"confidence": 0.25}), "weird_rel", "outgoing", None, None)
        assert with_edge == pytest.approx(with_node * 2)
        no_conf = expander._calculate_activation_score(
            from_node, to_node, "weird_rel", "outgoing", None, {})
        assert no_conf == pytest.approx(0.5 + 0.15 + 0.2 + 0.1)

    def test_hop_relevance_math(self):
        expander = MultiHopExpander()
        to_node = gnode("n2", ntype="user")
        r1 = expander._calculate_hop_relevance(None, to_node, "belongs_to", 1, None)
        assert r1 == pytest.approx(0.85 * 1.0 * 1.0)
        r2 = expander._calculate_hop_relevance(None, to_node, "belongs_to", 2, None)
        assert r2 == pytest.approx(0.85 ** 2 * 1.0 * 1.0)
        low = expander._calculate_hop_relevance(None, gnode("n3", ntype="gadget"), "weird_rel", 1, None)
        assert low == pytest.approx(0.85 * 0.75 * 0.75)


class TestEarlyTermination:
    def test_fires_when_average_cannot_survive_next_hop(self, caplog):
        nodes = [
            gnode("n1", ntype="gadget"), gnode("n2", ntype="gadget"),
            gnode("n3", ntype="gadget"), gnode("n4", ntype="gadget"),
            gnode("n5", ntype="gadget"), gnode("n6", ntype="gadget"),
            gnode("n7", ntype="gadget"), gnode("n8", ntype="gadget"),
        ]
        edges = [
            gedge("n1", "n2", rel="weird_rel"),
            gedge("n2", "n3", rel="weird_rel"), gedge("n2", "n4", rel="weird_rel"),
            gedge("n3", "n5", rel="weird_rel"), gedge("n3", "n6", rel="weird_rel"),
            gedge("n3", "n7", rel="weird_rel"), gedge("n3", "n8", rel="weird_rel"),
        ]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        cfg = expander_config(max_hop_depth=6)
        with caplog.at_level("DEBUG", logger="core.graphrag.multi_hop_expansion"):
            result = MultiHopExpander(cfg).expand("n1", "ws-1", session=sess)
        assert any("Early termination at hop 3" in r.message for r in caplog.records)
        assert result.total_nodes_found == 8
        assert result.max_depth_reached == 3

    def test_not_fired_when_average_survives(self, caplog):
        nodes = [gnode("n1"), gnode("n2"), gnode("n3")]
        edges = [gedge("n1", "n2"), gedge("n2", "n3")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        with caplog.at_level("DEBUG", logger="core.graphrag.multi_hop_expansion"):
            result = MultiHopExpander().expand("n1", "ws-1", session=sess)
        assert not any("Early termination" in r.message for r in caplog.records)
        assert result.total_nodes_found == 3

    def test_zero_decay_does_not_crash(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [gedge("n1", "n2")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        cfg = expander_config(relevance_decay=0.0)
        result = MultiHopExpander(cfg).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 1

    def test_early_termination_disabled(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [gedge("n1", "n2")]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        cfg = expander_config(enable_early_termination=False)
        result = MultiHopExpander(cfg).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 2


class TestSQLMultiHopExpander:
    def test_factories(self):
        assert isinstance(get_multi_hop_expander(), MultiHopExpander)
        assert isinstance(get_sql_expander(), SQLMultiHopExpander)
        cfg = expander_config()
        assert get_multi_hop_expander(cfg).config is cfg
        assert get_sql_expander(cfg).config is cfg

    def test_expand_sql_impl_success(self):
        session = MagicMock()
        node_rows = [
            SimpleNamespace(id="n1", name="one", type="user", description=None,
                            properties=None, hop_level=0, relevance_score=1.0),
            SimpleNamespace(id="n1", name="one", type="user", description=None,
                            properties=None, hop_level=0, relevance_score=1.0),
            SimpleNamespace(id="n2", name="two", type="task", description=None,
                            properties={"k": "v"}, hop_level=1, relevance_score=0.5),
        ]
        rel_rows = [
            SimpleNamespace(source_node_id="n1", target_node_id="n2",
                            relationship_type="related_to", properties=None),
        ]
        session.execute.side_effect = [
            SimpleNamespace(fetchall=lambda: node_rows),
            SimpleNamespace(fetchall=lambda: rel_rows),
        ]
        expander = SQLMultiHopExpander(expander_config())
        result = expander._expand_sql_impl("n1", "ws-1", 4, session)
        assert result.total_nodes_found == 2
        assert result.max_depth_reached == 1
        assert result.nodes[0].id == "n1"
        assert result.nodes[1].properties == {"k": "v"}
        assert result.relationships[0]["type"] == "related_to"
        assert session.execute.call_count == 2

    def test_expand_sql_impl_no_nodes_skips_rel_query(self):
        session = MagicMock()
        session.execute.side_effect = [SimpleNamespace(fetchall=lambda: [])]
        result = SQLMultiHopExpander()._expand_sql_impl("n1", "ws-1", 4, session)
        assert result.total_nodes_found == 0
        assert session.execute.call_count == 1

    def test_expand_sql_impl_exception_sets_metadata(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("sql boom")
        result = SQLMultiHopExpander()._expand_sql_impl("n1", "ws-1", 4, session)
        assert result.metadata["error"] == "expansion_failed"

    def test_expand_sql_session_none_uses_patched_session(self):
        session = MagicMock()
        session.execute.side_effect = [SimpleNamespace(fetchall=lambda: [])]
        with patch("core.graphrag.multi_hop_expansion.get_db_session", return_value=session):
            result = SQLMultiHopExpander().expand_sql("n1", "ws-1")
        assert result.total_nodes_found == 0

    def test_expand_sql_max_depth_override(self):
        session = MagicMock()
        session.execute.side_effect = [SimpleNamespace(fetchall=lambda: [])]
        SQLMultiHopExpander().expand_sql("n1", "ws-1", max_depth=2, session=session)
        args = session.execute.call_args.args
        assert args[1]["max_depth"] == 2

    def test_expand_sql_default_max_depth_from_config(self):
        session = MagicMock()
        session.execute.side_effect = [SimpleNamespace(fetchall=lambda: [])]
        SQLMultiHopExpander(expander_config(max_hop_depth=7)).expand_sql("n1", "ws-1", session=session)
        args = session.execute.call_args.args
        assert args[1]["max_depth"] == 7


# ============================================================================
# 6. community detection
# ============================================================================

class TestCommunityDataclasses:
    def test_community_post_init_size(self):
        c = Community(id="c1", nodes={"a", "b", "c"})
        assert c.size == 3
        assert c.level == 0

    def test_hierarchy_defaults(self):
        h = CommunityHierarchy()
        assert h.root_communities == []
        assert h.levels == {}
        assert h.max_depth == 0

    def test_detection_result_defaults(self):
        r = DetectionResult()
        assert r.num_communities == 0
        assert r.algorithm_used.value == ClusteringAlgorithm.LEIDEN.value

    def test_enums(self):
        assert ClusteringAlgorithm.LEIDEN.value == "leiden"
        assert ResolutionPolicy.ADAPTIVE.value == "adaptive"


class _FakeVS:
    def __init__(self, names):
        self._names = names

    def __getitem__(self, i):
        return {"name": self._names[i]}


class _FakeES:
    def __init__(self):
        self.weights = None

    def __setitem__(self, key, value):
        self.weights = value


class _FakeIGraph:
    def __init__(self):
        self.vs = _FakeVS([])
        self.es = _FakeES()
        self._edges = []

    def add_vertices(self, names):
        self.vs = _FakeVS(list(names))

    def add_edges(self, edges):
        self._edges = list(edges)


class _FakeIGraphModule:
    Graph = _FakeIGraph


class _FakePartition:
    def __init__(self, membership, q):
        self.membership = membership
        self.q = q


class _FakeLeidenAlg:
    RBConfigurationVertexPartition = object()

    def find_partition(self, graph, cls, **kwargs):
        return _FakePartition([0, 0, 0, 1, 1, 1], 0.42)


class TestLeidenAlgorithm:
    def test_detect_uses_networkx_path(self):
        algo = LeidenAlgorithm()
        graph = __import__("networkx").Graph()
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        result = algo.detect(graph, 1.0)
        assert result.execution_time_ms >= 0.0
        assert result.num_communities >= 1

    def test_detect_uses_simple_path_when_no_networkx(self):
        algo = LeidenAlgorithm()
        fake_graph = SimpleNamespace(nodes=lambda: ["a", "b", "c"])
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", False):
            result = algo.detect(fake_graph, 1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LABEL_PROPAGATION.value
        assert result.num_communities == 1
        assert result.execution_time_ms >= 0.0

    def test_detect_simple_with_networkx_components_and_size_filter(self):
        algo = LeidenAlgorithm()
        graph = __import__("networkx").Graph()
        graph.add_edges_from([("a", "b"), ("b", "c")])
        graph.add_node("x")
        graph.add_node("y")
        result = algo._detect_simple(graph, 1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LABEL_PROPAGATION.value
        assert result.num_communities == 1

    def test_detect_simple_no_networkx_basic_fallback(self):
        algo = LeidenAlgorithm()
        fake_graph = SimpleNamespace(nodes=lambda: ["a", "b", "c"])
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", False):
            result = algo._detect_simple(fake_graph, 1.0)
        assert result.num_communities == 1
        assert result.communities[0].nodes == {"a", "b", "c"}

    def test_detect_with_networkx_success_path(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a"), ("d", "e"), ("e", "f"), ("f", "d")])
        ig_stub = _FakeIGraphModule()
        la_stub = _FakeLeidenAlg()
        with patch.dict(sys.modules, {"igraph": ig_stub, "leidenalg": la_stub}):
            result = LeidenAlgorithm()._detect_with_networkx(graph, 1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LEIDEN.value
        assert result.num_communities == 2
        assert result.modularity == 0.42
        assert ig_stub.Graph().add_edges  # module surface used

    def test_detect_with_networkx_import_error_falls_back_to_louvain(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        with patch.dict(sys.modules, {"igraph": None}):
            result = LeidenAlgorithm()._detect_with_networkx(graph, 1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LOUVAIN.value

    def test_detect_with_nx_louvain_unweighted(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        result = LeidenAlgorithm()._detect_with_nx_louvain(graph, 1.0)
        assert result.num_communities == 1

    def test_detect_with_nx_louvain_weighted_and_small_skip(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edge("a", "b", weight=2.0)
        graph.add_edge("b", "c", weight=2.0)
        graph.add_edge("c", "a", weight=2.0)
        graph.add_node("iso")
        result = LeidenAlgorithm()._detect_with_nx_louvain(graph, 1.0)
        assert result.num_communities == 1
        assert result.modularity is not None

    def test_nx_to_igraph_with_weights(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edge("a", "b", weight=3.0)
        graph.add_edge("b", "c")
        ig_stub = _FakeIGraphModule()
        with patch.dict(sys.modules, {"igraph": ig_stub}):
            g = LeidenAlgorithm()._nx_to_igraph(graph)
        assert isinstance(g, _FakeIGraph)
        assert g.es.weights == [3.0, 1.0]

    def test_nx_to_igraph_without_weights(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edge("a", "b")
        ig_stub = _FakeIGraphModule()
        with patch.dict(sys.modules, {"igraph": ig_stub}):
            LeidenAlgorithm()._nx_to_igraph(graph)
        assert ig_stub.Graph().es.weights is None

    def test_partition_to_result_groups_and_filters(self):
        ig_stub = _FakeIGraphModule()
        with patch.dict(sys.modules, {"igraph": ig_stub}):
            graph = ig_stub.Graph()
            graph.add_vertices(["a", "b", "c", "d", "e", "f"])
        partition = _FakePartition([0, 0, 0, 1, 1, 1], 0.42)
        result = LeidenAlgorithm()._partition_to_result(partition, graph, 1.0)
        assert result.num_communities == 2
        assert result.modularity == 0.42
        small = _FakePartition([0, 0, 1], 0.1)
        result2 = LeidenAlgorithm()._partition_to_result(small, graph, 1.0)
        assert result2.num_communities == 0

    def test_factories(self):
        cfg = CommunityConfig()
        assert get_community_detector(cfg).config is cfg
        assert get_leiden_algorithm(cfg).config is cfg


class TestCommunityDetectionService:
    def _svc(self, **overrides):
        cfg = CommunityConfig(**overrides)
        return CommunityDetectionService(cfg)

    def test_detect_communities_graph_too_small(self):
        sess = FakeSession({GraphNode: [gnode("n1"), gnode("n2")], GraphEdge: []})
        result = self._svc().detect_communities("ws-1", session=sess)
        assert result.num_communities == 0
        assert result.metadata["reason"] == "graph_too_small"

    def test_detect_communities_full_flow(self):
        nodes, edges = clique("n", 4)
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges,
                            GraphCommunity: [], CommunityMembership: []})
        result = self._svc(resolution_policy=ResolutionPolicy.FIXED, base_resolution=1.0).detect_communities("ws-1", session=sess)
        assert result.num_communities == 1
        assert result.coverage == 1.0
        assert result.metadata["graph_nodes"] == 4
        assert result.metadata["graph_edges"] == 6
        # real partition ids are algorithm-named (leiden_comm_<i>); keep the
        # name assertion agnostic to the backend actually installed
        assert result.communities[0].name.startswith("user_community_")
        assert set(result.communities[0].keywords) == {"n1", "n2", "n3", "n4"}
        assert result.communities[0].description.startswith("Community of 4 user entities")
        assert len(sess.added) == 5

    def test_detect_communities_uses_patched_session(self):
        nodes, edges = clique("n", 4)
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges,
                            GraphCommunity: [], CommunityMembership: []})
        with patch("core.graphrag.community_detection.get_db_session", return_value=sess):
            result = self._svc(resolution_policy=ResolutionPolicy.FIXED, base_resolution=1.0).detect_communities("ws-1")
        assert result.num_communities == 1

    def test_detect_store_false(self):
        nodes, edges = clique("n", 4)
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges,
                            GraphCommunity: [], CommunityMembership: []})
        result = self._svc(resolution_policy=ResolutionPolicy.FIXED, base_resolution=1.0).detect_communities("ws-1", session=sess, store_results=False)
        assert result.num_communities == 1
        assert sess.added == []

    def test_build_graph_handles_missing_edge_properties(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [SimpleNamespace(source_node_id="n1", target_node_id="n2",
                                 relationship_type="rel", workspace_id="ws-1",
                                 properties=None)]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        graph = self._svc()._build_graph("ws-1", sess)
        assert graph.number_of_nodes() == 2
        assert graph["n1"]["n2"]["weight"] == 1.0
        assert graph["n1"]["n2"]["relationship_type"] == "rel"

    def test_build_graph_edge_weight_from_properties(self):
        nodes = [gnode("n1"), gnode("n2")]
        edges = [gedge("n1", "n2", props={"weight": 0.5})]
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        graph = self._svc()._build_graph("ws-1", sess)
        assert graph["n1"]["n2"]["weight"] == 0.5

    def test_build_graph_raises_without_networkx(self):
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", False):
            with pytest.raises(ImportError):
                self._svc()._build_graph("ws-1", FakeSession({}))

    def test_get_resolution_fixed(self):
        svc = self._svc(resolution_policy=ResolutionPolicy.FIXED, base_resolution=1.7)
        assert svc._get_resolution("ws-1", None, None) == 1.7

    def test_get_resolution_adaptive_density(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
        svc = self._svc()
        res = svc._get_resolution("ws-1", None, graph)
        assert res == pytest.approx(1.0 * (1 + 4 / 6))

    def test_get_resolution_adaptive_clamps(self):
        nx = __import__("networkx")
        graph = nx.Graph()
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        dense = self._svc(base_resolution=2.5, max_resolution=2.0)
        assert dense._get_resolution("ws-1", None, graph) == 2.0
        sparse = self._svc(base_resolution=0.2, min_resolution=0.5)
        assert sparse._get_resolution("ws-1", None, graph) == 0.5

    def test_get_resolution_adaptive_empty_and_single(self):
        nx = __import__("networkx")
        empty = nx.Graph()
        svc = self._svc(base_resolution=1.3)
        assert svc._get_resolution("ws-1", None, empty) == 1.3
        single = nx.Graph()
        single.add_node("a")
        assert svc._get_resolution("ws-1", None, single) == 1.3

    def test_get_resolution_hierarchical_and_fallthrough(self):
        svc = self._svc(resolution_policy=ResolutionPolicy.HIERARCHICAL, base_resolution=1.1)
        assert svc._get_resolution("ws-1", None, None) == 1.1
        svc2 = self._svc()
        svc2.config.resolution_policy = "bogus"
        assert svc2._get_resolution("ws-1", None, None) == 1.0

    def test_enrich_communities_with_missing_nodes(self):
        sess = FakeSession({GraphNode: [gnode("n1")]})
        community = Community(id="c1", nodes={"n1", "n9"})
        result = DetectionResult(communities=[community])
        self._svc()._enrich_communities(result, "ws-1", sess)
        assert community.name == "user_community_c1"
        assert community.keywords == ["n1"]

    def test_enrich_communities_empty_entity_types(self):
        sess = FakeSession({GraphNode: []})
        community = Community(id="c1", nodes={"n9", "n10"})
        result = DetectionResult(communities=[community])
        self._svc()._enrich_communities(result, "ws-1", sess)
        assert community.name == "mixed_community_c1"
        assert community.description == "Community of 2 mixed entities: "

    def test_enrich_communities_description_truncation(self):
        nodes = [gnode(f"n{i}") for i in range(1, 6)]
        sess = FakeSession({GraphNode: nodes})
        community = Community(id="c1", nodes={f"n{i}" for i in range(1, 6)})
        result = DetectionResult(communities=[community])
        self._svc()._enrich_communities(result, "ws-1", sess)
        assert community.description.endswith("...")

    def test_store_communities_clears_old_and_mints_uuids(self):
        old_comm = SimpleNamespace(id="old1", workspace_id="ws-1")
        old_membership = SimpleNamespace(community_id="old1", node_id="n1")
        sess = FakeSession({GraphCommunity: [old_comm], CommunityMembership: [old_membership]})
        community = Community(id="comm_0", nodes={"n1", "n2"}, level=0,
                              summary="", description="desc", name="name")
        result = DetectionResult(communities=[community])
        self._svc()._store_communities(result, "ws-1", sess)
        assert sess.rows_for(CommunityMembership) == []
        assert sess.rows_for(GraphCommunity) == []
        stored = [o for o in sess.added if isinstance(o, SimpleNamespace) or o.__class__.__name__ == "GraphCommunity"]
        assert len(stored) == 1
        assert str(stored[0].id) != "comm_0"
        assert stored[0].summary == "desc"

    def test_store_communities_summary_fallbacks(self):
        sess = FakeSession({GraphCommunity: [], CommunityMembership: []})
        community = Community(id="keep-me", nodes={"n1"})
        community.name = "keep-me"
        result = DetectionResult(communities=[community])
        self._svc()._store_communities(result, "ws-1", sess)
        stored = sess.added[0]
        assert stored.id == "keep-me"
        assert stored.summary == "keep-me"

    def test_store_communities_all_empty_summary(self):
        sess = FakeSession({GraphCommunity: [], CommunityMembership: []})
        community = Community(id="x", nodes={"n1"})
        community.name = ""
        community.description = ""
        result = DetectionResult(communities=[community])
        self._svc()._store_communities(result, "ws-1", sess)
        assert sess.added[0].summary == "community"

    def test_store_communities_commit_failure_rolls_back(self):
        sess = FakeSession({GraphCommunity: [], CommunityMembership: []})
        sess._fail_commit = True
        community = Community(id="comm_0", nodes={"n1"})
        result = DetectionResult(communities=[community])
        self._svc()._store_communities(result, "ws-1", sess)
        assert sess.rolled_back is True

    def test_detect_hierarchy_disabled(self):
        sess = FakeSession({GraphNode: [], GraphEdge: []})
        hierarchy = self._svc(enable_hierarchy=False).detect_hierarchy("ws-1", session=sess)
        assert hierarchy.levels == {}

    def test_detect_hierarchy_enabled(self):
        nodes, edges = clique("n", 4)
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges,
                            GraphCommunity: [], CommunityMembership: []})
        hierarchy = self._svc(resolution_policy=ResolutionPolicy.FIXED, base_resolution=1.0).detect_hierarchy("ws-1", session=sess)
        assert set(hierarchy.levels.keys()) == {0, 1, 2}
        assert hierarchy.max_depth == 3
        assert hierarchy.root_communities == hierarchy.levels[0]
        assert all(c.level == level for level, comms in hierarchy.levels.items() for c in comms)

    def test_detect_hierarchy_uses_patched_session(self):
        nodes, edges = clique("n", 4)
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges,
                            GraphCommunity: [], CommunityMembership: []})
        with patch("core.graphrag.community_detection.get_db_session", return_value=sess):
            hierarchy = self._svc(resolution_policy=ResolutionPolicy.FIXED, base_resolution=1.0).detect_hierarchy("ws-1")
        assert hierarchy.max_depth == 3


# ============================================================================
# Module-import path coverage. MUST run last in this file: importlib.reload
# replaces the module globals (enums/classes), which would otherwise desync
# the class objects bound at import time above.
# ============================================================================

class TestModuleImportPaths:
    def test_community_detection_igraph_import_success_and_restore(self):
        mod = sys.modules["core.graphrag.community_detection"]
        stub = SimpleNamespace()
        with patch.dict(sys.modules, {"igraph": stub}):
            reloaded = importlib.reload(mod)
            assert reloaded.IGRAPH_AVAILABLE is True
            assert reloaded.ig is stub
        sys.modules.pop("igraph", None)
        restored = importlib.reload(mod)
        # env-agnostic: poppng the sys.modules entry forces re-import, so the
        # flag must match whatever the environment actually provides.
        try:
            import igraph  # noqa: F401
            igraph_importable = True
        except ImportError:
            igraph_importable = False
        assert restored.IGRAPH_AVAILABLE is igraph_importable
        assert (restored.ig is None) is (not igraph_importable)

    def test_community_detection_networkx_import_failure_and_restore(self, caplog):
        mod = sys.modules["core.graphrag.community_detection"]
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "networkx":
                raise ImportError("simulated missing networkx")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import), \
                caplog.at_level("WARNING", logger="core.graphrag.community_detection"):
            reloaded = importlib.reload(mod)
        assert reloaded.NETWORKX_AVAILABLE is False
        assert "NetworkX not available" in caplog.text
        restored = importlib.reload(mod)
        assert restored.NETWORKX_AVAILABLE is True
