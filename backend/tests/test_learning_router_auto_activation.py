# -*- coding: utf-8 -*-
"""Self-activation of the learning router: ``ATOM_LEARNING_ROUTER=auto``.

The router's default mode is ``auto`` — re-ranking by learned
satisfaction/quality/fabrication history stays OFF (plain BPC ordering) until
the verdict history is thick enough to re-rank, then flips itself on, and falls
back again once that evidence ages out of the window. "Is it on?" is therefore a
DATA question, answerable from `llm_routing_feedback` alone, with no manual
toggle:

* ``true`` / ``false`` remain operator overrides and must win over the data;
* observation is NEVER gated — rows accrue in every mode (otherwise auto could
  never learn anything to flip on);
* the gate fails CLOSED (static ordering is always safe) when the query fails.

``readiness_report()`` exists so the Settings surface can explain the state
instead of showing an opaque "auto".
"""
import pytest

from core.llm import learning_router_registry as reg


class _Session:
    """Fake SQLAlchemy session: ``session.query(col).filter(...).all()``.

    The readiness query is ``db.query(Model.model_id).filter(...).all()`` — so
    ``__enter__`` must hand back the SESSION (with a callable ``query``), not the
    result chain. Getting that wrong silently exercises the real DB instead of
    the fake and the gate then reports "not ready" for reasons unrelated to the
    test.
    """

    def __init__(self, model_ids):
        self._ids = list(model_ids)

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def all(self):
        return [(m,) for m in self._ids]


def _patch_db(monkeypatch, model_ids, raises=False):
    class _Ctx:
        def __enter__(self):
            if raises:
                raise RuntimeError("db down")
            return _Session(model_ids)

        def __exit__(self, *a):
            return False

    import core.database

    monkeypatch.setattr(core.database, "get_db_session", lambda: _Ctx())


def _reset_cache():
    reg._lr_ready_cache = {"ts": 0.0, "ready": False, "logged": None}


@pytest.fixture(autouse=True)
def _clean_mode(monkeypatch):
    """Mode comes from the resolver; keep these tests on the data gate alone."""
    monkeypatch.setenv("ATOM_LEARNING_ROUTER", "auto")
    monkeypatch.delenv("ATOM_LEARNING_ROUTER_AUTO_MIN_ROWS", raising=False)
    monkeypatch.delenv("ATOM_LEARNING_ROUTER_AUTO_MIN_MODELS", raising=False)
    monkeypatch.delenv("ATOM_LEARNING_ROUTER_AUTO_MIN_PER_MODEL", raising=False)
    _reset_cache()
    yield
    _reset_cache()


class TestAutoGate:
    def test_default_mode_is_auto(self, monkeypatch):
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        assert reg.learning_router_mode() == "auto"

    def test_thin_history_keeps_static_ordering(self, monkeypatch):
        _patch_db(monkeypatch, ["m1"] * 5)
        assert reg.learning_history_ready() is False
        assert reg.learning_router_enabled() is False

    def test_total_rows_below_threshold_not_ready(self, monkeypatch):
        """2 models x 14 = 28 rows < 30 — the ROW floor is independent."""
        _patch_db(monkeypatch, ["m1"] * 14 + ["m2"] * 14)
        assert reg.learning_history_ready() is False

    def test_one_model_cannot_justify_a_relative_decision(self, monkeypatch):
        """Enough rows but a single model: re-ranking is relative, so no."""
        _patch_db(monkeypatch, ["m1"] * 60)
        assert reg.learning_history_ready() is False

    def test_flips_on_at_threshold(self, monkeypatch):
        _patch_db(monkeypatch, ["m1"] * 16 + ["m2"] * 16)
        assert reg.learning_history_ready() is True
        assert reg.learning_router_enabled() is True

    def test_falls_back_when_evidence_ages_out(self, monkeypatch):
        """Revocation is symmetric: no recent evidence -> static ordering."""
        _patch_db(monkeypatch, ["m1"] * 16 + ["m2"] * 16)
        assert reg.learning_router_enabled() is True
        _reset_cache()
        _patch_db(monkeypatch, [])  # window passed / rows purged
        assert reg.learning_router_enabled() is False

    def test_query_failure_fails_closed(self, monkeypatch):
        _patch_db(monkeypatch, [], raises=True)
        assert reg.learning_history_ready() is False
        assert reg.learning_router_enabled() is False


class TestOperatorOverrides:
    def test_explicit_true_wins_over_thin_data(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        _patch_db(monkeypatch, [])
        assert reg.learning_router_mode() == "true"
        assert reg.learning_router_enabled() is True

    def test_explicit_false_wins_over_rich_data(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        _patch_db(monkeypatch, ["m1"] * 60 + ["m2"] * 60)
        assert reg.learning_router_mode() == "false"
        assert reg.learning_router_enabled() is False

    @pytest.mark.parametrize(
        "raw,expected",
        [("1", "true"), ("yes", "true"), ("on", "true"), ("0", "false"),
         ("no", "false"), ("off", "false"), ("AUTO", "auto")],
    )
    def test_legacy_truthy_strings_still_parse(self, monkeypatch, raw, expected):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", raw)
        assert reg.learning_router_mode() == expected


class TestReadinessReport:
    def test_reports_the_gap_while_waiting(self, monkeypatch):
        _patch_db(monkeypatch, ["m1"] * 3)
        report = reg.readiness_report()
        assert report["mode"] == "auto"
        assert report["ready"] is False and report["enabled"] is False
        assert report["rows_in_window"] == 3
        assert "3/30 observations" in report["reason"]
        assert "0/2 models" in report["reason"]

    def test_reports_active_when_thick(self, monkeypatch):
        _patch_db(monkeypatch, ["m1"] * 20 + ["m2"] * 20)
        report = reg.readiness_report()
        assert report["ready"] is True and report["enabled"] is True
        assert report["models_with_enough_observations"] == 2
        assert "active" in report["reason"]

    def test_reports_manual_override_reason(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        _patch_db(monkeypatch, ["m1"] * 60)
        report = reg.readiness_report()
        assert report["mode"] == "false"
        assert "switched off manually" in report["reason"]

    def test_report_never_raises_on_db_failure(self, monkeypatch):
        _patch_db(monkeypatch, [], raises=True)
        report = reg.readiness_report()
        assert report["rows_in_window"] == 0
        assert "unavailable" in report["reason"]

    def test_thresholds_are_surfaced_not_hardcoded_in_ui(self, monkeypatch):
        _patch_db(monkeypatch, [])
        report = reg.readiness_report()
        assert report["thresholds"] == {
            "min_rows": reg._LR_AUTO_MIN_ROWS,
            "min_models": reg._LR_AUTO_MIN_MODELS,
            "min_observations_per_model": reg._LR_AUTO_MIN_PER_MODEL,
            "window_days": reg._LR_AUTO_WINDOW_DAYS,
        }


class TestStatusEndpoint:
    """The management surface must be admin-gated and never 500 on metrics."""

    def test_requires_admin(self):
        from fastapi import HTTPException
        from api.learning_router_routes import _require_admin

        class _Anon:
            role = "user"

        with pytest.raises(HTTPException) as exc:
            _require_admin(_Anon())
        assert exc.value.status_code == 403

    def test_returns_readiness_shape(self, monkeypatch):
        import asyncio
        from api.learning_router_routes import learning_router_status

        _patch_db(monkeypatch, ["m1"] * 40 + ["m2"] * 40)
        payload = asyncio.run(learning_router_status(_admin=object()))
        assert payload["success"] is True
        data = payload["data"]
        assert data["mode"] == "auto"
        assert data["enabled"] is True
        assert "thresholds" in data and "reason" in data
