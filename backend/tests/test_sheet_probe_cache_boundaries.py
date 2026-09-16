# -*- coding: utf-8 -*-
"""Cache-boundary verification for the per-(file-version, token) sheet probe
cache (``sheet_dataset_service._probe_cached``).

Audit item 7 asks for four properties to be *verified*, not assumed:
content-version invalidation, concurrent cold loads, scope isolation, and
protection against consumers mutating a cached result. The cache docstring
says "returned BY REFERENCE to read-only consumers; callers must not mutate
it" — a documented hazard is not an enforced invariant, and the key falls back
to ``""`` when a row carries neither ``content_hash`` nor ``external_id``,
which collapses distinct files onto one entry.

These tests pin the boundaries. Each asserts a property the cache must hold
regardless of how the probe itself is implemented.
"""
import copy
import threading

import pytest

import core.sheet_dataset_service as sds


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    sds._PROBE_CACHE.clear()
    monkeypatch.setattr(sds, "_PROBE_CACHE_TTL_S", 300.0)
    yield
    sds._PROBE_CACHE.clear()


def _probe_returning(value):
    """Install a stub probe that returns a fresh dict per call (so a test can
    tell a cache HIT from a re-probe)."""
    calls = {"n": 0}

    def _probe(entries, token, max_rows):
        calls["n"] += 1
        out = copy.deepcopy(value)
        out["_probe_calls"] = calls["n"]
        return out

    return _probe, calls


class TestContentVersionInvalidation:
    def test_new_content_hash_reprobes(self, monkeypatch):
        probe, calls = _probe_returning({"row_count": 1, "rows": [{"A": "1"}]})
        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        e1 = [{"content_hash": "h1", "external_id": "E1", "parquet_path": "/p/1"}]
        assert sds._probe_cached(e1, "5216", 10)["_probe_calls"] == 1
        assert sds._probe_cached(e1, "5216", 10)["_probe_calls"] == 1  # hit
        e2 = [{"content_hash": "h2", "external_id": "E1", "parquet_path": "/p/1"}]
        assert sds._probe_cached(e2, "5216", 10)["_probe_calls"] == 2  # re-probe
        assert calls["n"] == 2

    def test_kill_switch_bypasses_cache(self, monkeypatch):
        probe, calls = _probe_returning({"row_count": 1})
        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        monkeypatch.setattr(sds, "_PROBE_CACHE_TTL_S", 0.0)
        e = [{"content_hash": "h1"}]
        sds._probe_cached(e, "t", 10)
        sds._probe_cached(e, "t", 10)
        assert calls["n"] == 2


class TestScopeIsolation:
    def test_files_without_identity_do_not_collide(self, monkeypatch):
        """A row with neither content_hash nor external_id must not produce the
        SAME key as a different such row — otherwise the second file is served
        the first file's probe result."""
        seen = []

        def probe(entries, token, max_rows):
            name = str(entries[0].get("file_name") or "?")
            seen.append(name)
            return {"file_name": name, "row_count": 1,
                    "rows": [{"file": name}]}

        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        a = [{"file_name": "A.xlsx", "parquet_path": "/p/a.parquet"}]
        b = [{"file_name": "B.xlsx", "parquet_path": "/p/b.parquet"}]
        ra = sds._probe_cached(a, "5216", 10)
        rb = sds._probe_cached(b, "5216", 10)
        assert ra["file_name"] == "A.xlsx"
        assert rb["file_name"] == "B.xlsx", (
            "distinct identity-less files collided on the cache key; B was "
            "served A's result")
        assert seen == ["A.xlsx", "B.xlsx"]

    def test_same_content_different_source_keeps_its_own_identity(self, monkeypatch):
        """Identical bytes reached the catalog twice under different
        external_ids (the same attachment on two messages). The probe result
        carries file_name/external_id, so the second caller must not be handed
        the first caller's identity."""
        def probe(entries, token, max_rows):
            e = entries[0]
            return {"file_name": e.get("file_name"),
                    "external_id": e.get("external_id"),
                    "row_count": 1, "rows": [{"A": "1"}]}

        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        a = [{"content_hash": "same", "external_id": "MSG-1",
              "file_name": "quote.xlsx", "parquet_path": "/p/1"}]
        b = [{"content_hash": "same", "external_id": "MSG-2",
              "file_name": "quote.xlsx", "parquet_path": "/p/2"}]
        ra = sds._probe_cached(a, "5216", 10)
        rb = sds._probe_cached(b, "5216", 10)
        assert ra["external_id"] == "MSG-1"
        assert rb["external_id"] == "MSG-2", (
            "a cache hit returned another source's identity")


class TestConsumerMutationProtection:
    def test_mutating_a_returned_result_does_not_corrupt_the_cache(self, monkeypatch):
        probe, calls = _probe_returning(
            {"row_count": 1, "rows": [{"A": "1"}], "columns": ["A"]})
        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        e = [{"content_hash": "h1", "external_id": "E1"}]
        first = sds._probe_cached(e, "t", 10)
        # A consumer treats the result as its own and edits it.
        first["rows"].append({"A": "INJECTED"})
        first["row_count"] = 999
        first["columns"].append("INJECTED")
        second = sds._probe_cached(e, "t", 10)
        assert calls["n"] == 1, "second call should have been a cache hit"
        assert second["row_count"] == 1, "cached row_count was mutated by a consumer"
        assert second["rows"] == [{"A": "1"}], "cached rows were mutated"
        assert second["columns"] == ["A"], "cached columns were mutated"


class TestConcurrentColdLoads:
    def test_concurrent_cold_loads_return_consistent_results(self, monkeypatch):
        """N threads racing on a cold key must each get a complete, equal
        result and leave the cache usable (no torn/half-built entry)."""
        barrier = threading.Barrier(8)
        results = []
        errors = []

        def probe(entries, token, max_rows):
            return {"row_count": 3, "rows": [{"A": str(i)} for i in range(3)]}

        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        e = [{"content_hash": "cold", "external_id": "E1"}]

        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(sds._probe_cached(e, "tok", 10))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"concurrent cold load raised: {errors}"
        assert len(results) == 8
        assert all(r == results[0] for r in results), "threads saw different results"
        assert results[0]["row_count"] == 3
        # the cache is still coherent afterwards
        assert sds._probe_cached(e, "tok", 10)["row_count"] == 3

    def test_cache_eviction_does_not_lose_the_fresh_entry(self, monkeypatch):
        """The >512 overflow path clears the whole cache. A clear triggered by
        one key must not be able to swallow the entry being written."""
        probe, calls = _probe_returning({"row_count": 1})
        monkeypatch.setattr(sds, "_probe_sheet_hits", probe)
        # pre-fill past the eviction bound
        for i in range(513):
            sds._PROBE_CACHE[(f"f{i}", "t", 10)] = (0.0, {"row_count": 1})
        e = [{"content_hash": "fresh", "external_id": "E"}]
        sds._probe_cached(e, "t", 10)
        # after the clear-on-overflow, the just-written entry must be present
        assert sds._probe_cached(e, "t", 10)["_probe_calls"] == 1, (
            "the freshly written entry was evicted by the overflow clear")
        assert calls["n"] == 1
