"""Coverage wave 10g — small pure-logic core cluster (TDD).

Modules: core/agent_worker_wrapper, core/agent_radio/radio_breaker,
core/hybrid_search/backfill_matcher, core/vfs_registry.

Real-bug probes (RED first):
- WG1: ``agent_worker_wrapper.execute_agent_background`` slices
  ``request[:50]`` for its log line, but ``request = task_data.get("request")``
  returns ``None`` when the key is absent -> ``TypeError`` on every malformed
  task before the worker even reaches the agent.
- WG2: ``radio_breaker.classify_responsibility_breakpoints`` double-counts the
  single concept "api integration" because ``r"integration"`` and
  ``r"api integration"`` both match the same substring -> a one-signal task
  wrongly crosses the ``>= 2`` threshold and auto-attaches a fleet thread.
- WG3: ``vfs_registry.register_provider`` accepts a prefix containing ``/``
  (e.g. ``"a/b"``), but ``resolve_provider`` splits on the first ``/`` and so
  can never resolve it -> a registered provider is silently unreachable. The
  registry must fail fast at registration, like it already does for empty.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# WG1 — agent_worker_wrapper: None request must not crash the log line
# ---------------------------------------------------------------------------
class TestAgentWorkerWrapperNullRequest:
    def test_missing_request_key_does_not_crash(self):
        """A task payload without ``request`` must be handled, not crash the logger."""
        from core import agent_worker_wrapper as aw

        # AtomMetaAgent is imported lazily inside the function; short-circuit the
        # body right after the logging line by making the constructor blow up,
        # so we isolate the logging-path crash from the execution path.
        with patch("core.atom_meta_agent.AtomMetaAgent", side_effect=RuntimeError("stop")):
            # Before the fix this raised TypeError: 'NoneType' is not subscriptable
            # on the ``request[:50]`` log line. After the fix it reaches the
            # constructor and raises our sentinel RuntimeError instead.
            with pytest.raises(RuntimeError, match="stop"):
                aw.execute_agent_background(
                    {"context": {}, "trigger_mode": "manual", "tenant_id": "t1"}
                )

    def test_none_request_value_does_not_crash(self):
        from core import agent_worker_wrapper as aw

        with patch("core.atom_meta_agent.AtomMetaAgent", side_effect=RuntimeError("stop")):
            with pytest.raises(RuntimeError, match="stop"):
                aw.execute_agent_background(
                    {"request": None, "trigger_mode": "manual", "tenant_id": "t1"}
                )

    def test_short_request_is_logged_intact(self):
        """A present request must still be logged (no behaviour regression)."""
        from core import agent_worker_wrapper as aw

        captured: list[str] = []

        with patch("core.agent_worker_wrapper.logger") as log:
            log.info = lambda msg, *a, **k: captured.append(msg)
            with patch("core.atom_meta_agent.AtomMetaAgent", side_effect=RuntimeError("stop")):
                with pytest.raises(RuntimeError):
                    aw.execute_agent_background(
                        {"request": "hi", "trigger_mode": "manual", "tenant_id": "t1"}
                    )
        # The "Executing agent" log line is present and contains the request.
        assert any("Executing agent" in m and "Request: hi" in m for m in captured)


# ---------------------------------------------------------------------------
# WG2 — radio_breaker: overlapping patterns must not double-count one signal
# ---------------------------------------------------------------------------
class TestRadioBreakerOverlap:
    def test_api_integration_is_one_concept_not_two(self):
        from core.agent_radio.radio_breaker import classify_responsibility_breakpoints as cls

        v = cls("api integration")
        # The phrase "api integration" is a single responsibility signal; the
        # bare ``integration`` pattern must not count it a second time. Exactly
        # one of the overlapping patterns survives (the more specific label).
        assert v.score == 1, v
        assert len(v.reasons) == 1, v.reasons
        assert v.reasons[0] in ("integration", "api integration")
        assert v.triggered is False

    def test_distinct_signals_still_trigger(self):
        from core.agent_radio.radio_breaker import classify_responsibility_breakpoints as cls

        # Two genuinely distinct breakpoint signals -> triggers.
        v = cls("legacy migration with security review")
        assert v.triggered is True
        assert v.score >= 2

    def test_empty_and_none(self):
        from core.agent_radio.radio_breaker import classify_responsibility_breakpoints as cls

        assert cls("").triggered is False
        assert cls(None).triggered is False

    def test_bounded_override_wins(self):
        from core.agent_radio.radio_breaker import classify_responsibility_breakpoints as cls

        # "rename a" is bounded local work even though it co-occurs with refactor.
        v = cls("refactor and rename a function")
        assert v.triggered is False
        assert v.reasons == ["bounded local work"]


# ---------------------------------------------------------------------------
# WG3 — vfs_registry: slash-containing prefix must be rejected at registration
# ---------------------------------------------------------------------------
class TestVFSRegistryPrefixValidation:
    def test_register_slash_prefix_is_rejected(self):
        import core.vfs_registry as vr

        bad = SimpleNamespace(prefix="a/b")
        with pytest.raises(ValueError):
            vr.register_provider(bad)

    def test_register_empty_prefix_is_rejected(self):
        import core.vfs_registry as vr

        with pytest.raises(ValueError):
            vr.register_provider(SimpleNamespace(prefix=""))

    def test_register_and_resolve_roundtrip(self):
        import core.vfs_registry as vr

        prov = SimpleNamespace(prefix="knowledge")
        vr.register_provider(prov)
        assert vr.get_provider("knowledge") is prov
        assert vr.resolve_provider("knowledge/documents/x") is prov
        assert vr.resolve_provider("knowledge") is prov  # bare prefix resolves
        assert "knowledge" in vr.list_prefixes()

    def test_resolve_edge_cases(self):
        import core.vfs_registry as vr

        assert vr.resolve_provider("") is None
        assert vr.resolve_provider(None) is None
        assert vr.resolve_provider("///knowledge/x") is not None  # leading slashes
        assert vr.resolve_provider("unknown/x") is None


# ---------------------------------------------------------------------------
# backfill_matcher — pure resolution behaviour (no bug, lock in the contract)
# ---------------------------------------------------------------------------
class TestBackfillMatcher:
    def _row(self, rid):
        return SimpleNamespace(id=rid)

    def test_external_id_hit_wins(self):
        from core.hybrid_search.backfill_matcher import match_pg_row

        db = MagicMock()
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.first.return_value = self._row("pg-ext")
        db.query.return_value = chain

        out = match_pg_row(db, {"external_id": "ext-1", "file_name": "f"}, "lid")
        assert out == "pg-ext"

    def test_falls_through_to_file_name_when_external_misses(self):
        from core.hybrid_search.backfill_matcher import match_pg_row

        db = MagicMock()
        miss = MagicMock()
        miss.filter.return_value = miss
        miss.order_by.return_value = miss
        miss.first.return_value = None
        hit = MagicMock()
        hit.filter.return_value = hit
        hit.order_by.return_value = hit
        hit.first.return_value = self._row("pg-file")
        db.query.side_effect = [miss, hit]

        out = match_pg_row(db, {"external_id": "ext-1", "file_name": "f"}, "lid")
        assert out == "pg-file"

    def test_returns_none_when_no_signals(self):
        from core.hybrid_search.backfill_matcher import match_pg_row

        db = MagicMock()
        # No external_id, no file_name -> the function should not even query.
        out = match_pg_row(db, {"integration_id": "int1"}, "lid")
        assert out is None
        db.query.assert_not_called()

    def test_file_name_leg_applies_integration_filter(self):
        from core.hybrid_search.backfill_matcher import match_pg_row

        db = MagicMock()
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.first.return_value = self._row("pg-file-int")
        db.query.return_value = chain

        out = match_pg_row(db, {"file_name": "f", "integration_id": "int1"}, "lid")
        assert out == "pg-file-int"
        # integration_id is present -> filter() called at least twice (file_name + integration)
        assert chain.filter.call_count >= 2


# ---------------------------------------------------------------------------
# agent_worker_wrapper — full execution path + error re-raise
# ---------------------------------------------------------------------------
class TestAgentWorkerWrapperExecution:
    def test_successful_execution_returns_result(self):
        from unittest.mock import AsyncMock
        from core import agent_worker_wrapper as aw

        atom = MagicMock()
        atom.execute = AsyncMock(return_value={"status": "ok"})
        with patch("core.atom_meta_agent.AtomMetaAgent", return_value=atom):
            result = aw.execute_agent_background(
                {"request": "do thing", "trigger_mode": "manual", "tenant_id": "t1"}
            )
        assert result == {"status": "ok"}
        # execute was driven on a fresh event loop and awaited to completion
        atom.execute.assert_called_once()

    def test_invalid_trigger_mode_raises_value_error(self):
        from core import agent_worker_wrapper as aw

        atom = MagicMock()
        atom.execute = MagicMock(return_value={"status": "ok"})
        with patch("core.atom_meta_agent.AtomMetaAgent", return_value=atom):
            # AgentTriggerMode("bogus") raises ValueError; the wrapper re-raises.
            with pytest.raises(ValueError):
                aw.execute_agent_background(
                    {"request": "x", "trigger_mode": "bogus", "tenant_id": "t1"}
                )

    def test_execution_error_is_reraised(self):
        from unittest.mock import AsyncMock
        from core import agent_worker_wrapper as aw

        atom = MagicMock()
        atom.execute = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.atom_meta_agent.AtomMetaAgent", return_value=atom):
            with pytest.raises(RuntimeError, match="boom"):
                aw.execute_agent_background(
                    {"request": "x", "trigger_mode": "manual", "tenant_id": "t1"}
                )


# ---------------------------------------------------------------------------
# radio_breaker — should_attach_thread gate hook
# ---------------------------------------------------------------------------
class TestRadioBreakerGateHook:
    def test_gate_disabled_short_circuits(self):
        from core.agent_radio import radio_breaker, radio_config

        # should_attach_thread imports radio_config lazily and reads
        # breakpoint_gate_enabled() off the live module object, so patch the
        # function in place on that module.
        with patch.object(radio_config, "breakpoint_gate_enabled", return_value=False):
            v = radio_breaker.should_attach_thread("legacy migration refactor")
        assert v.triggered is False
        assert v.reasons == ["gate disabled"]
        assert v.score == 0

    def test_gate_enabled_delegates_to_classifier(self):
        from core.agent_radio import radio_breaker, radio_config

        with patch.object(radio_config, "breakpoint_gate_enabled", return_value=True):
            v = radio_breaker.should_attach_thread("legacy migration refactor")
        assert v.triggered is True
        assert v.score >= 2

