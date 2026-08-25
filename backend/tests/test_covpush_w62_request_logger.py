"""Coverage wave 62 — core/llm/gateway/request_logger.py (TDD, mocked db).

Closes the final 4 uncovered lines (rollback-failure fallbacks in
``log_gateway_request`` / ``sweep_gateway_logs``) and locks in the full
contract: auth-header dropping, PII fail-closed redaction, 64 KB truncation,
serialization fallbacks, the cost-estimate chain, best-effort logging
(never raises) and the retention sweep — zero network, zero LLM spend.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.llm.gateway.request_logger import (
    AUTH_HEADER_KEYS,
    MAX_LOG_BODY_CHARS,
    _drop_auth_headers,
    _redact_text,
    _sanitize_body,
    _truncate,
    estimate_cost_usd,
    log_bodies,
    log_gateway_request,
    log_retention_days,
    sweep_gateway_logs,
)

IDENTITY = SimpleNamespace(
    tenant_id="t-1",
    workspace_id="w-1",
    user_id="u-1",
    api_key_id="key-1",
)


def make_db(**overrides):
    db = MagicMock()
    for k, v in overrides.items():
        setattr(db, k, v)
    return db


class TestAuthHeaderDrop:
    def test_drops_sensitive_headers(self):
        headers = {
            "Authorization": "Bearer xyz",
            "X-Api-Key": "atom_sk_x",
            "Cookie": "session=1",
            "Proxy-Authorization": "Basic abc",
            "Content-Type": "application/json",
        }
        result = _drop_auth_headers(headers)
        assert "Content-Type" in result
        for sensitive in AUTH_HEADER_KEYS:
            assert sensitive not in result

    def test_case_insensitive_drop(self):
        assert _drop_auth_headers({"AUTHORIZATION": "x", "Host": "h"}) == {"Host": "h"}

    def test_non_dict_returns_empty(self):
        assert _drop_auth_headers(None) == {}
        assert _drop_auth_headers(["list"]) == {}


class TestRedactText:
    def test_empty_text_passthrough(self):
        assert _redact_text("") == ""
        assert _redact_text(None) is None

    def test_redacts_pii(self):
        with patch("core.pii_redactor.redact_pii", return_value="REDACTED") as r:
            assert _redact_text("call me at 555-1234") == "REDACTED"
        r.assert_called_once_with("call me at 555-1234")

    def test_import_failure_fails_closed(self):
        with patch.dict("sys.modules", {"core.pii_redactor": None}):
            with patch("builtins.__import__", side_effect=ImportError("no pii")):
                assert _redact_text("raw content") == "[redaction unavailable — body omitted]"

    def test_redactor_exception_fails_closed(self):
        with patch("core.pii_redactor.redact_pii", side_effect=RuntimeError("boom")):
            assert _redact_text("raw content") == "[redaction unavailable — body omitted]"


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("short") == "short"

    def test_long_text_truncated(self):
        long = "x" * (MAX_LOG_BODY_CHARS + 100)
        result = _truncate(long)
        assert len(result) == MAX_LOG_BODY_CHARS

    def test_empty_text(self):
        assert _truncate("") == ""


class TestSanitizeBody:
    def test_disabled_returns_none(self):
        assert _sanitize_body({"a": 1}, include_body=False) is None
        assert _sanitize_body(None, include_body=True) is None

    def test_serializes_and_redacts(self):
        with patch("core.llm.gateway.request_logger._redact_text",
                   side_effect=lambda t: f"<{t}>") as redact:
            result = _sanitize_body({"messages": [{"role": "user", "content": "hi"}]},
                                    include_body=True)
        parsed = result[1:-1]  # strip the redact wrapper
        assert json.loads(parsed)["messages"][0]["content"] == "hi"
        redact.assert_called_once()

    def test_json_failure_falls_back_to_str(self):
        with patch("json.dumps", side_effect=TypeError("not serializable")), \
             patch("core.pii_redactor.redact_pii", side_effect=lambda t: t):
            result = _sanitize_body({"a": 1}, include_body=True)
        assert "{'a': 1}" in result


class TestEstimateCost:
    def test_pricing_fetcher_wins(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.0042
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher) as get_f:
            assert estimate_cost_usd("gpt-4o", 100, 20) == 0.0042
        get_f.assert_called_once()

    def test_fetcher_none_falls_back_to_static(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher), \
             patch("core.cost_config.get_llm_cost", return_value=0.01) as static:
            assert estimate_cost_usd("gpt-4o", 100, 20) == 0.01
        static.assert_called_once_with("gpt-4o", 100, 20)

    def test_non_positive_cost_returns_none(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.0
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher), \
             patch("core.cost_config.get_llm_cost", return_value=0.0):
            assert estimate_cost_usd("gpt-4o", 100, 20) is None

    def test_zero_tokens_still_ok(self):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.5
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            assert estimate_cost_usd("m", None, None) == 0.5
        fetcher.estimate_cost.assert_called_once_with("m", 0, 0)

    def test_exception_returns_none(self):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("no pricing")):
            assert estimate_cost_usd("m", 1, 1) is None


class TestLogGatewayRequest:
    def test_writes_full_row_and_returns_id(self):
        db = make_db()
        log_id = log_gateway_request(
            db, IDENTITY,
            provider="openai", model="gpt-4o", stream=True, status_code=200,
            latency_ms=42, prompt_tokens=10, completion_tokens=20,
            cost_usd=0.01, request_body={"a": 1}, response_body={"b": 2},
        )
        assert log_id
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        row = db.add.call_args[0][0]
        assert row.user_id == "u-1"
        assert row.tenant_id == "t-1"
        assert row.workspace_id == "w-1"
        assert row.api_key_id == "key-1"
        assert row.stream is True
        assert row.request_json is None  # bodies disabled by default

    def test_bodies_persisted_when_enabled(self):
        db = make_db()
        # Runtime-settings migration: the module constant became the
        # ``log_bodies()`` helper — patch the helper, not a constant.
        with patch("core.llm.gateway.request_logger.log_bodies", return_value=True):
            log_id = log_gateway_request(
                db, IDENTITY, request_body={"messages": [{"content": "hello"}]},
                response_body={"choices": []},
            )
        row = db.add.call_args[0][0]
        assert "hello" in row.request_json
        assert row.response_json is not None
        assert log_id

    def test_none_identity_is_safe(self):
        # user_id is NOT NULL on GatewayRequestLog — a None identity cannot
        # persist a row; logging must degrade gracefully (None, never raise).
        db = make_db()
        db.commit.side_effect = RuntimeError("NOT NULL constraint failed")
        assert log_gateway_request(db, None, model="m") is None

    def test_add_failure_rolls_back_and_returns_none(self):
        db = make_db()
        db.add.side_effect = RuntimeError("db down")
        assert log_gateway_request(db, IDENTITY) is None
        db.rollback.assert_called_once()

    def test_add_failure_with_rollback_failure_still_none(self):
        db = make_db()
        db.add.side_effect = RuntimeError("db down")
        db.rollback.side_effect = RuntimeError("rollback failed too")
        assert log_gateway_request(db, IDENTITY) is None

    def test_commit_failure_rolls_back_and_returns_none(self):
        db = make_db()
        db.commit.side_effect = RuntimeError("commit failed")
        assert log_gateway_request(db, IDENTITY) is None
        db.rollback.assert_called_once()


class TestSweepGatewayLogs:
    def test_deletes_old_rows_and_returns_count(self):
        db = make_db()
        db.query.return_value.filter.return_value.delete.return_value = 7
        assert sweep_gateway_logs(db) == 7
        db.commit.assert_called_once()

    def test_delete_none_returns_zero(self):
        db = make_db()
        db.query.return_value.filter.return_value.delete.return_value = None
        assert sweep_gateway_logs(db) == 0

    def test_failure_rolls_back_and_returns_zero(self):
        db = make_db()
        db.query.return_value.filter.return_value.delete.side_effect = RuntimeError("db down")
        assert sweep_gateway_logs(db) == 0
        db.rollback.assert_called_once()

    def test_failure_with_rollback_failure_returns_zero(self):
        db = make_db()
        db.query.return_value.filter.return_value.delete.side_effect = RuntimeError("db down")
        db.rollback.side_effect = RuntimeError("rollback failed too")
        assert sweep_gateway_logs(db) == 0

    def test_cutoff_uses_retention_config(self):
        from datetime import datetime, timedelta, timezone

        db = make_db()
        db.query.return_value.filter.return_value.delete.return_value = 1
        sweep_gateway_logs(db)
        cutoff_clause = db.query.return_value.filter.call_args[0][0]
        cutoff = cutoff_clause.right.value  # BindParameter value
        assert isinstance(cutoff, datetime)
        assert cutoff <= datetime.now(timezone.utc)
        assert cutoff >= datetime.now(timezone.utc) - timedelta(days=log_retention_days() + 1)
