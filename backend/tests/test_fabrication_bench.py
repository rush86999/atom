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
