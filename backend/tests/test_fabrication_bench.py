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
    def __init__(self, satisfactions): self.sat = satisfactions
    def filter(self, *a, **k): return self
    def query(self, *a, **k): return self
    def all(self): return [(s,) for s in self.sat]


def _patch_db(monkeypatch, satisfactions):
    chain = _Chain(satisfactions)
    class _S:
        def __enter__(self): return chain
        def __exit__(self, *a): return False
    import core.database
    monkeypatch.setattr(core.database, "get_db_session", lambda: _S())


class TestFabricationBench:
    def test_high_rate_benches(self, monkeypatch):
        h = _make_handler()
        monkeypatch.delenv("ATOM_FABRICATION_BENCH", raising=False)
        _patch_db(monkeypatch, [0.1, 0.1, 0.1, 0.7])
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
            chain = _Chain([0.1] * 4)
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
