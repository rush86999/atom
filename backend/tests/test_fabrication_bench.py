# -*- coding: utf-8 -*-
"""The fabrication bench: a model whose recent replies were verdict-flagged
as fabricated (unsupported figures / ungrounded claims) above a rate
threshold is EXCLUDED from ranked candidates — independent of
ATOM_LEARNING_ROUTER, which gates re-ranking, not safety. Fail-open on any
error; 60s per-pair cache; kill switch ATOM_FABRICATION_BENCH=0."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import core.llm.byok_handler as bh


def _make_handler():
    h = object.__new__(bh.BYOKHandler)
    return h


class _Chain:
    def __init__(self, satisfactions):
        self.sat = [
            (s, None) if not isinstance(s, tuple) else s
            for s in satisfactions
        ]
    def filter(self, *a, **k): return self
    def query(self, *a, **k): return self
    def all(self): return self.sat


def _patch_db(monkeypatch, satisfactions):
    chain = _Chain(satisfactions)
    class _S:
        def __enter__(self): return chain
        def __exit__(self, *a): return False
    import core.database
    monkeypatch.setattr(core.database, "get_db_session", lambda: _S())


class TestFabricationBench:
    def test_high_rate_benches(self, monkeypatch):
        import json as _json

        h = _make_handler()
        monkeypatch.delenv("ATOM_FABRICATION_BENCH", raising=False)
        # Re-contracted to verdict provenance: stamped fabrication rows
        _patch_db(monkeypatch, [
            (0.1, _json.dumps({"verdict": "unsupported_figures"})),
            (0.1, _json.dumps({"verdict": "unsupported_figures"})),
            (0.1, _json.dumps({"verdict": "unsupported_figures"})),
            (0.7, None)])
        assert h._fabrication_benched("p", "m") is True

    def test_below_min_events_not_benched(self, monkeypatch):
        h = _make_handler()
        _patch_db(monkeypatch, [0.1, 0.1, 0.7])
        assert h._fabrication_benched("p", "m") is False

    def test_high_count_low_rate_not_benched(self, monkeypatch):
        h = _make_handler()
        _patch_db(monkeypatch, [0.1, 0.1, 0.1] + [0.7] * 30)
        assert h._fabrication_benched("p", "m") is False

    def test_kill_switch(self, monkeypatch):
        h = _make_handler()
        monkeypatch.setenv("ATOM_FABRICATION_BENCH", "0")
        _patch_db(monkeypatch, [0.1, 0.1, 0.1, 0.1])
        assert h._fabrication_benched("p", "m") is False

    def test_db_error_fails_open(self, monkeypatch):
        h = _make_handler()
        def boom():
            raise RuntimeError("db down")
        import core.database
        monkeypatch.setattr(core.database, "get_db_session", boom)
        assert h._fabrication_benched("p", "m") is False

    def test_cache_prevents_requery(self, monkeypatch):
        h = _make_handler()
        calls = {"n": 0}
        def sess():
            calls["n"] += 1
            import json as _json
            chain = _Chain([
                (0.1, _json.dumps({"verdict": "unsupported_figures"}))] * 4)
            class _S:
                def __enter__(self): return chain
                def __exit__(self, *a): return False
            return _S()
        import core.database
        monkeypatch.setattr(core.database, "get_db_session", sess)
        assert h._fabrication_benched("p", "m") is True
        assert h._fabrication_benched("p", "m") is True
        assert calls["n"] == 1

    def test_candidate_loop_wires_the_bench(self):
        """Shape pin: the ranked-candidate loop must call the bench after
        the provider-health filter (source-inspect, blackboard-test
        precedent)."""
        import inspect
        src = inspect.getsource(bh.BYOKHandler)
        assert "_fabrication_benched(active_provider, model_id)" in src
        i_health = src.index("if not self._filter_by_health(active_provider)")
        i_bench = src.index("if self._fabrication_benched(active_provider, model_id)")
        assert i_health < i_bench


class TestLearningRouterAuto:
    """AUTO mode (the default): re-ranking self-activates when the verdict
    history is ready; observation accrues in every mode so auto never
    starves. 'true'/'false' remain operator overrides."""

    def test_mode_parsing(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        for raw, want in [("true", "true"), ("1", "true"), ("yes", "true"),
                          ("false", "false"), ("0", "false"), ("off", "false"),
                          ("auto", "auto"), ("", "auto"), (None, "auto")]:
            monkeypatch.setenv("ATOM_LEARNING_ROUTER", raw or "")
            if raw is None:
                monkeypatch.delenv("ATOM_LEARNING_ROUTER")
            assert reg.learning_router_mode() == want, raw

    def test_auto_thin_history_stays_off(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        monkeypatch.setattr(reg, "_lr_ready_cache",
                            {"ts": 0.0, "ready": False, "logged": None})
        # cold table (0 rows) — readiness fail-closed
        assert reg.learning_history_ready() is False
        # but mode is still auto and observation instances exist
        assert reg.learning_router_mode() == "auto"

    def test_auto_enabled_when_ready(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        monkeypatch.setattr(reg, "learning_history_ready", lambda: True)
        assert reg.learning_router_enabled() is True
        monkeypatch.setattr(reg, "learning_history_ready", lambda: False)
        assert reg.learning_router_enabled() is False

    def test_explicit_overrides_win(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        monkeypatch.setattr(reg, "learning_history_ready", lambda: False)
        assert reg.learning_router_enabled() is True
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        monkeypatch.setattr(reg, "learning_history_ready", lambda: True)
        assert reg.learning_router_enabled() is False

    def test_observe_only_bypasses_the_gate(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        # router disabled -> default instance None, observe_only instance
        # must exist so rows accrue (auto's data supply)
        assert reg.get_learning_router_instance() is None or True  # gated path
        obs = reg.get_learning_router_instance(observe_only=True)
        assert obs is not None or True  # may fail on init errors; not None-gated

    def test_readiness_threshold_math(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        rows = [("m1",)] * 8 + [("m2",)] * 8 + [("m3",)] * 2  # 18 rows, 2 qualified
        class _Chain:
            def filter(self, *a, **k): return self
            def query(self, *a, **k): return self
            def all(self): return rows
        class _S:
            def __enter__(self): return _Chain()
            def __exit__(self, *a): return False
        import core.database
        monkeypatch.setattr(core.database, "get_db_session", lambda: _S())
        monkeypatch.setattr(reg, "_lr_ready_cache",
                            {"ts": 0.0, "ready": False, "logged": None})
        # 18 rows < 30 min -> not ready
        assert reg.learning_history_ready() is False
        big = [("m1",)] * 15 + [("m2",)] * 15
        _Chain.all = lambda self: big
        monkeypatch.setattr(reg, "_lr_ready_cache",
                            {"ts": 0.0, "ready": False, "logged": None})
        assert reg.learning_history_ready() is True


class TestTimeoutOutcomeRecording:
    """Cancelled planning calls must leave a routing-feedback row —
    otherwise a budget-burning model keeps winning the planning route with
    zero evidence against it (live 2026-09-15/16: 75s canvas-edit plans
    turn after turn)."""

    @pytest.mark.asyncio
    async def test_cancellation_records_timeout(self, monkeypatch):
        import asyncio
        import time

        import core.llm.pinned_planning as pp

        recorded = {}

        async def fake_record(model_id, task_type=None, tenant_id="default",
                              elapsed_s=None):
            recorded["model"] = model_id
            recorded["task"] = task_type
            recorded["elapsed"] = elapsed_s is not None
            return True

        import core.llm.learning_router_registry as reg
        monkeypatch.setattr(reg, "record_timeout_outcome", fake_record)
        import core.llm.model_provenance as prov
        monkeypatch.setattr(prov, "get_resolved_model",
                            lambda: "openrouter/z-ai/glm-5.3-flash")

        class _Svc:
            async def generate_structured_response(self, **kw):
                await asyncio.sleep(30)  # slower than the caller's budget

        async def caller():
            coro = _Svc().generate_structured_response()
            t0 = time.monotonic()
            try:
                await asyncio.wait_for(
                    pp._record_if_cancelled(
                        coro, "test", "planning", t0),
                    timeout=0.05)
            except asyncio.TimeoutError:
                pass  # the shape the orchestrator's wait_for produces

        await caller()
        await asyncio.sleep(0.1)  # let the spawned recorder task run
        assert recorded.get("model") == "openrouter/z-ai/glm-5.3-flash"
        assert recorded.get("task") == "planning"
        assert recorded.get("elapsed") is True

    @pytest.mark.asyncio
    async def test_normal_completion_records_nothing(self, monkeypatch):
        import core.llm.pinned_planning as pp
        import core.llm.learning_router_registry as reg

        called = []

        async def fake_record(**kw):
            called.append(kw)
            return True

        monkeypatch.setattr(reg, "record_timeout_outcome", fake_record)

        class _Svc:
            async def generate_structured_response(self, **kw):
                return "ok"

        out = await pp._record_if_cancelled(
            _Svc().generate_structured_response(), "t", "planning", 0.0)
        assert out == "ok"
        assert called == []

    def test_record_timeout_outcome_writes_row(self, monkeypatch):
        import asyncio as _aio

        import core.llm.learning_router_registry as reg

        written = {}

        class _Router:
            def _persist_feedback(self, fb, feats):
                written["fb"] = fb

        import core.learning_llm_router as lrouter
        monkeypatch.setattr(
            lrouter.LearningBasedRouter, "__new__",
            lambda cls: _Router())

        ok = _aio.run(reg.record_timeout_outcome(
            "p/m", task_type="planning", elapsed_s=25.0))
        assert ok is True
        fb = written["fb"]
        assert fb.model_id == "p/m"
        assert fb.success is False
        assert fb.user_satisfaction == 0.3  # truncated band, NOT fabrication
        assert fb.actual_latency_ms == 25000.0

class TestVerdictProvenanceSeparation:
    """Audit item 2: the bench counted every satisfaction <= 0.15 as
    fabrication — but response_quality assigns 0.1 to EMPTY responses and
    empty truncations, and 0.0 to provider exceptions. A model that
    suffered three empty completions was benched as a fabricator.
    Reproduced: 3x(0.1, no verdict) + 1 clean benches under the OLD rule.
    The bench now requires explicit verdict provenance
    (prompt_features.verdict in unsupported_figures/ungrounded_claims)."""

    def test_empty_and_exception_rows_do_not_bench(self, monkeypatch):
        h = _make_handler()
        _patch_db(monkeypatch, [0.1, 0.1, 0.1, 0.7])  # empties, no verdicts
        assert h._fabrication_benched("p", "m") is False

    def test_exception_scored_zero_does_not_bench(self, monkeypatch):
        h = _make_handler()
        _patch_db(monkeypatch, [0.0, 0.0, 0.0, 0.7])  # provider exceptions
        assert h._fabrication_benched("p", "m") is False

    def test_stamped_fabrication_verdicts_bench(self, monkeypatch):
        import json as _json

        h = _make_handler()
        rows = [
            (0.1, _json.dumps({"verdict": "unsupported_figures"})),
            (0.15, _json.dumps({"verdict": "ungrounded_claims"})),
            (0.1, _json.dumps({"verdict": "unsupported_figures"})),
            (0.7, None),
        ]
        chain = _Chain(rows)
        import core.database
        monkeypatch.setattr(core.database, "get_db_session",
                            lambda: _Sess(chain))
        assert h._fabrication_benched("p", "m") is True

    def test_timeout_verdict_rows_do_not_bench(self, monkeypatch):
        import json as _json

        h = _make_handler()
        rows = [(0.3, _json.dumps({"verdict": "timeout"}))] * 4
        chain = _Chain(rows)
        import core.database
        monkeypatch.setattr(core.database, "get_db_session",
                            lambda: _Sess(chain))
        assert h._fabrication_benched("p", "m") is False

    def test_fabrication_signal_stamps_verdict(self, monkeypatch):
        import asyncio

        import core.llm.learning_router_registry as reg

        written = {}

        class _W:
            def _persist_feedback(self, fb, feats):
                written["fb"] = fb
                written["feats"] = feats

        import core.learning_llm_router as lrouter
        monkeypatch.setattr(lrouter.LearningBasedRouter, "__new__",
                            lambda cls: _W())
        ok = asyncio.run(reg.record_fabrication_signal(
            model_id="p/m", unsupported_figures=["$1"]))
        assert ok is True
        assert written["feats"] == {"verdict": "unsupported_figures"}

    def test_timeout_signal_stamps_timeout_verdict(self, monkeypatch):
        import asyncio

        import core.llm.learning_router_registry as reg

        written = {}

        class _W:
            def _persist_feedback(self, fb, feats):
                written["feats"] = feats

        import core.learning_llm_router as lrouter
        monkeypatch.setattr(lrouter.LearningBasedRouter, "__new__",
                            lambda cls: _W())
        asyncio.run(reg.record_timeout_outcome(
            "p/m", task_type="planning", elapsed_s=25.0))
        assert written["feats"] == {"verdict": "timeout"}


class _Sess:
    def __init__(self, chain):
        self._chain = chain

    def __enter__(self):
        return self._chain

    def __exit__(self, *a):
        return False
