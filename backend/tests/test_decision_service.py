"""Tests for DecisionService — local Ollaya decision sidecar (Phase 1).

TDD red-green: this suite defines the contract before implementation.
Contract (mirrors turn_fact_extractor + stage_router conventions):
- NEVER raises. Every public method catches all exceptions → fallback result.
- Flag-off (ATOM_OLLAYA_ENABLED=false) → source="disabled", no HTTP.
- Timeout/error/malformed → source="fallback", answers={}.
- Success parses choice/noul/score from /v1/systemone wire format.
- Circuit breaker: N consecutive failures → fast short-circuit (source="breaker").
"""

import os
os.environ["TESTING"] = "1"

import json
import pytest
from unittest.mock import patch, MagicMock


def _svc():
    from core import decision_service as ds
    import importlib
    importlib.reload(ds)
    return ds


class TestDisabledContract:
    def test_disabled_makes_no_http_call(self):
        ds = _svc()
        with patch.object(ds, "ollaya_enabled", return_value=False), \
             patch.object(ds, "_post_decide", side_effect=AssertionError("must not call HTTP")):
            out = ds.decide("hello", questions={"q": {"type": "noul", "instructions": "Is this a test?"}})
            assert out["source"] == "disabled"
            assert out["answers"] == {}


class TestFallbackContract:
    def test_timeout_never_raises(self):
        ds = _svc()
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_run_cli_preset", side_effect=TimeoutError("slow")):
            out = ds.decide("hello", preset="triage")
            assert out["source"] == "fallback"
            assert out["answers"] == {}

    def test_malformed_payload_falls_back(self):
        ds = _svc()
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_run_cli_preset", return_value={"garbage": 1}):
            out = ds.decide("hello", preset="triage")
            assert out["source"] == "fallback"
            assert out["answers"] == {}

    def test_connection_error_never_raises(self):
        ds = _svc()
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_run_cli_preset", side_effect=ConnectionError("down")):
            out = ds.decide("hello", preset="triage")
            assert out["source"] in ("fallback", "breaker")
            assert out["answers"] == {}

    def test_http_path_timeout_never_raises(self):
        ds = _svc()
        questions = {"q": {"type": "noul", "instructions": "Is this a test?"}}
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_post_decide", side_effect=TimeoutError("slow")):
            out = ds.decide("hello", questions=questions)
            assert out["source"] == "fallback"
            assert out["answers"] == {}

    def test_timeout_override_reaches_transport(self):
        ds = _svc()
        questions = {"q": {"type": "noul", "instructions": "Is this a test?"}}
        wire = {"model": "laya", "answers": {"q": {"type": "noul", "noul": 0.5}}}
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_post_decide", return_value=wire) as m:
            out = ds.decide("hello", questions=questions, timeout_s=30.0)
            assert out["source"] == "ollaya"
            assert m.call_args[0][1] == 30.0


class TestSuccessParsing:
    def test_parses_systemone_wire_format(self):
        ds = _svc()
        wire = {
            "model": "laya:en",
            "answers": {
                "intent": {"type": "choice", "choice": "refund", "confidence": 0.99,
                           "probabilities": {"refund": 0.99, "other": 0.01}},
                "urgent": {"type": "noul", "noul": 0.12},
                "frustration": {"type": "score", "score": 1.7, "confidence": 0.35,
                                "legend": {"0": "calm", "3": "angry"},
                                "probabilities": {"0": 0.1, "3": 0.2}},
            },
        }
        questions = {"intent": {"type": "choice", "instructions": "i",
                                "criteria": {"refund": "r", "other": "o"}}}
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_post_decide", return_value=wire):
            out = ds.decide("charged twice", questions=questions)
            assert out["source"] == "ollaya"
            assert out["answers"]["intent"]["choice"] == "refund"
            assert out["answers"]["urgent"]["noul"] == pytest.approx(0.12)
            assert out["answers"]["frustration"]["score"] == pytest.approx(1.7)

    def test_preset_resolves_via_cli_layer(self):
        ds = _svc()
        wire = {"model": "laya:en",
                "answers": {"refund_requested": {"type": "noul", "noul": 0.9}}}
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_run_cli_preset", return_value=wire) as m:
            out = ds.decide("charged twice", preset="triage")
            assert out["source"] == "ollaya"
            assert out["answers"]["refund_requested"]["noul"] == pytest.approx(0.9)
            m.assert_called_once()
            assert m.call_args[0][1] == "triage"


class TestCircuitBreaker:
    def test_opens_after_consecutive_failures(self):
        ds = _svc()
        ds.reset_breaker()
        with patch.object(ds, "ollaya_enabled", return_value=True), \
             patch.object(ds, "_run_cli_preset", side_effect=ConnectionError("down")):
            for _ in range(ds._BREAKER_THRESHOLD):
                out = ds.decide("x", preset="triage")
                assert out["answers"] == {}
            # next call short-circuits without touching HTTP
            with patch.object(ds, "_run_cli_preset", side_effect=AssertionError("breaker must skip HTTP")):
                out = ds.decide("x", preset="triage")
                assert out["source"] == "breaker"
        ds.reset_breaker()
