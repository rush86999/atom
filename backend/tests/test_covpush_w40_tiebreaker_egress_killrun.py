# -*- coding: utf-8 -*-
"""
Coverage push W40 — match-confidence LLM tiebreaker + egress proxy + KillRun.

Targets (repo ≥90%):
  * core/llm/match_confidence_tiebreaker.py  (was ~40%)
  * core/sandbox_egress_proxy.py             (was ~91% — closes the last gaps)
  * core/sandbox_killrun.py                  (was ~52% — DB + guard edge paths)

All LLM calls are mocked (no network, no real provider). The KillRun DB path
uses a real in-memory SQLite table (agent_executions) to prove persistence.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.selector_confidence_service import SelectorCandidate
from core import sandbox_killrun
from core.sandbox_killrun import KillRunAborted, KillRunRegistry
from core.llm import match_confidence_tiebreaker as tiebreaker
from core.sandbox_policy import ALLOWED, BLOCKED, RESTRICTED, SandboxDecision, SandboxPolicy


# ===========================================================================
# Shared fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset_tiebreaker_state():
    tiebreaker._circuit_breaker.reset()
    tiebreaker._tiebreak_cache.clear()
    yield
    tiebreaker._circuit_breaker.reset()
    tiebreaker._tiebreak_cache.clear()


@pytest.fixture(autouse=True)
def _clean_sandbox_env(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("ATOM_SANDBOX"):
            monkeypatch.delenv(k, raising=False)
    yield


@pytest.fixture(autouse=True)
def _reset_killrun_registry():
    sandbox_killrun.get_registry().reset()
    yield
    sandbox_killrun.get_registry().reset()


def _candidates(n: int = 2) -> list:
    return [
        SelectorCandidate(
            selector=f"#btn-{i}",
            match_count=i + 1,
            is_text_only=False,
            appeared_after_ms=0,
            tag_hint="BUTTON" if i == 0 else None,
            attributes={"id": f"btn-{i}"} if i == 0 else {},
        )
        for i in range(n)
    ]


def _llm_success(text: str, **kw):
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value=text, **kw)
    return llm


def _policy(**kw):
    defaults = dict(
        run_id="r1",
        agent_id="a1",
        tier_at_issuance="supervised",
        egress_hosts=("api.anthropic.com", "pypi.org", "api.openai.com"),
    )
    defaults.update(kw)
    return SandboxPolicy(**defaults)


# ===========================================================================
# match_confidence_tiebreaker
# ===========================================================================
class TestTiebreaker:
    @pytest.mark.asyncio
    async def test_success_parses_dict_text_and_caches(self):
        llm = _llm_success({"text": '{"chosen_index": 1, "rationale": "second is the submit"}'})
        r1 = await tiebreaker.break_tie(_candidates(), {"url": "https://example.com/x"}, llm)
        assert r1.chosen_index == 1
        assert r1.used_llm is True
        assert r1.cache_hit is False
        assert "submit" in r1.rationale
        assert llm.generate_completion.await_count == 1

        r2 = await tiebreaker.break_tie(_candidates(), {"url": "https://example.com/x"}, llm)
        assert r2.cache_hit is True
        assert r2.chosen_index == 1
        assert llm.generate_completion.await_count == 1  # amortized — no second call

    @pytest.mark.asyncio
    async def test_success_parses_dict_content(self):
        llm = _llm_success({"content": '{"chosen_index": 0, "rationale": "first"}'})
        r = await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert r.chosen_index == 0
        assert r.used_llm is True

    @pytest.mark.asyncio
    async def test_success_parses_str_with_surrounding_text(self):
        llm = _llm_success('prefix {"chosen_index": -1, "rationale": "none match"} suffix')
        ctx = {"url": "https://a.com", "surrounding_text": "x" * 700}
        r = await tiebreaker.break_tie(_candidates(), ctx, llm)
        assert r.chosen_index == -1
        assert r.used_llm is True

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback_and_opens_breaker_after_5(self, monkeypatch):
        monkeypatch.setattr(tiebreaker, "SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS", 0.01)

        async def slow(*a, **k):
            await asyncio.sleep(5)

        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=slow)
        r = await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert r.chosen_index == -1
        assert r.used_llm is False
        assert "timeout" in r.rationale
        assert tiebreaker._circuit_breaker.failures == 1

        # 4 more failures → breaker opens
        for _ in range(4):
            await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert tiebreaker._circuit_breaker.state == "open"
        assert tiebreaker._circuit_breaker.failures == 5

        # tripped → short-circuit without calling the LLM
        llm.generate_completion = AsyncMock(side_effect=AssertionError("should not be called"))
        r = await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert r.chosen_index == -1
        assert r.used_llm is False
        assert "circuit breaker" in r.rationale

    @pytest.mark.asyncio
    async def test_llm_error_records_failure(self):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("provider down"))
        r = await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert r.chosen_index == -1
        assert r.used_llm is False
        assert "LLM error" in r.rationale
        assert tiebreaker._circuit_breaker.failures == 1

    @pytest.mark.asyncio
    async def test_out_of_range_index_never_upgrades(self):
        llm = _llm_success({"text": '{"chosen_index": 9, "rationale": "garbage"}'})
        r = await tiebreaker.break_tie(_candidates(1), {"url": "https://a.com"}, llm)
        assert r.chosen_index == -1
        assert r.used_llm is False
        assert "out-of-range" in r.rationale

    @pytest.mark.asyncio
    async def test_disabled_flag_short_circuits(self, monkeypatch):
        monkeypatch.setattr(tiebreaker, "SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", False)
        llm = MagicMock()
        r = await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert r.chosen_index == -1
        assert r.used_llm is False
        assert "disabled" in r.rationale
        llm.generate_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_disabled_skips_lookup_and_put(self, monkeypatch):
        monkeypatch.setattr(tiebreaker, "SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED", False)
        llm = _llm_success({"text": '{"chosen_index": 0, "rationale": "ok"}'})
        r = await tiebreaker.break_tie(_candidates(), {"url": "https://a.com"}, llm)
        assert r.chosen_index == 0
        assert tiebreaker._tiebreak_cache == {}  # nothing cached

    def test_circuit_breaker_record_failure_opens(self):
        cb = tiebreaker._CircuitBreaker()
        cb.reset()
        for _ in range(5):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.failures == 5

    def test_circuit_breaker_record_success_closes(self):
        cb = tiebreaker._CircuitBreaker()
        cb.failures = 3
        cb.state = "open"
        cb.opened_at = time.time()
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failures == 0
        assert cb.opened_at == 0.0

        cb.record_success()  # already closed — no log, still fine
        assert cb.state == "closed"

    def test_circuit_breaker_is_tripped_cooldown_and_half_open(self):
        cb = tiebreaker._CircuitBreaker()
        assert cb.is_tripped() is False  # closed

        cb.state = "open"
        cb.opened_at = time.time()  # just opened → in cooldown
        assert cb.is_tripped() is True

        cb.opened_at = time.time() - 121  # cooldown elapsed → half-open probe
        assert cb.is_tripped() is False
        assert cb.state == "half_open"

        cb.opened_at = time.time() - 121  # half-open + elapsed → probe again
        assert cb.is_tripped() is False

    def test_circuit_breaker_reset(self):
        cb = tiebreaker._CircuitBreaker()
        cb.failures = 7
        cb.state = "open"
        cb.opened_at = 123.0
        cb.reset()
        assert cb.failures == 0
        assert cb.state == "closed"
        assert cb.opened_at == 0.0

    def test_cache_key_hashes_selectors_and_hostname(self):
        c1 = _candidates(2)
        k1 = tiebreaker._cache_key(c1, {"url": "https://example.com/page"})
        k2 = tiebreaker._cache_key(c1, {"url": "https://example.com/other"})
        k3 = tiebreaker._cache_key(c1, {"url": "https://elsewhere.com/page"})
        assert k1 == k2  # hostname-scoped, path-insensitive
        assert k1 != k3
        assert len(k1) == 16

        k4 = tiebreaker._cache_key(c1, {})  # no url → empty hostname
        k5 = tiebreaker._cache_key(c1, {"url": ""})
        assert k4 == k5

    def test_cache_get_hit_expired_and_missing(self):
        tiebreaker._tiebreak_cache["live"] = (tiebreaker.TiebreakResult(0, "x", True), time.time() + 60)
        r = tiebreaker._cache_get("live")
        assert r is not None and r.chosen_index == 0

        tiebreaker._tiebreak_cache["stale"] = (tiebreaker.TiebreakResult(0, "x", True), time.time() - 10)
        assert tiebreaker._cache_get("stale") is None
        assert "stale" not in tiebreaker._tiebreak_cache

        assert tiebreaker._cache_get("missing") is None

    def test_cache_put_evicts_oldest(self):
        for i in range(300):
            tiebreaker._cache_put(f"key-{i}", tiebreaker.TiebreakResult(0, "x", True))
        assert len(tiebreaker._tiebreak_cache) == 256
        assert "key-0" not in tiebreaker._tiebreak_cache
        assert "key-299" in tiebreaker._tiebreak_cache

    def test_build_prompt_includes_candidates_and_context(self):
        prompt = tiebreaker._build_prompt(
            _candidates(2),
            {"url": "https://a.com/form", "surrounding_text": "text" * 200},
        )
        assert "#btn-0" in prompt and "#btn-1" in prompt
        assert "https://a.com/form" in prompt
        assert "BUTTON" in prompt
        assert "unknown" in prompt  # tag_hint None candidate
        assert "Surrounding text:" in prompt
        assert "Return ONLY JSON" in prompt

    def test_parse_llm_response_variants(self):
        r = tiebreaker._parse_llm_response("")
        assert r.chosen_index == -1 and "empty" in r.rationale and r.used_llm is True

        r = tiebreaker._parse_llm_response("no braces here")
        assert r.chosen_index == -1 and "non-JSON" in r.rationale

        r = tiebreaker._parse_llm_response("{unclosed")
        assert r.chosen_index == -1 and "non-JSON" in r.rationale

        r = tiebreaker._parse_llm_response('{"chosen_index": 2, "rationale": "two"}')
        assert r.chosen_index == 2 and r.rationale == "two"

        r = tiebreaker._parse_llm_response('{"chosen_index": "not-an-int", "rationale": "bad"}')
        assert r.chosen_index == -1 and "parse failed" in r.rationale

        r = tiebreaker._parse_llm_response('{"rationale": "no index key"}')
        assert r.chosen_index == -1 and r.rationale == "no index key"


# ===========================================================================
# sandbox_egress_proxy — remaining branches
# ===========================================================================
class TestEgressProxyGaps:
    def test_host_matches_empty_host(self):
        from core.sandbox_egress_proxy import host_matches

        assert host_matches("", ("api.anthropic.com",)) is False

    def test_host_matches_wildcard_subdomain(self):
        from core.sandbox_egress_proxy import host_matches

        allowlist = ("*.example.com",)
        assert host_matches("api.example.com", allowlist) is True
        assert host_matches("sub.api.example.com", allowlist) is True
        assert host_matches("example.com", allowlist) is True
        assert host_matches("notexample.com", allowlist) is False
        assert host_matches("evil.com", ("api.anthropic.com",)) is False

    def test_check_egress_disabled_allows(self, monkeypatch):
        from core.sandbox_egress_proxy import check_egress

        monkeypatch.delenv("ATOM_SANDBOX_EGRESS_ENABLED", raising=False)
        d = check_egress(_policy(), url="https://exfil.attacker.com/x", tool_name="t")
        assert d.decision == ALLOWED
        assert d.metadata_json.get("egress_check") == "disabled"

    def test_check_egress_no_host_blocked(self, monkeypatch):
        from core.sandbox_egress_proxy import check_egress

        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(), url="not-a-url-at-all", tool_name="t")
        assert d.decision == BLOCKED
        assert d.metadata_json.get("reason") == "no_host_in_url"

    def test_check_egress_allowlisted_host(self, monkeypatch):
        from core.sandbox_egress_proxy import check_egress

        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(), url="https://api.anthropic.com/v1/messages", tool_name="t")
        assert d.decision == ALLOWED
        assert d.metadata_json.get("host") == "api.anthropic.com"
        assert d.violation_type is None

    def test_check_egress_non_allowlisted_blocked(self, monkeypatch):
        from core.sandbox_egress_proxy import check_egress
        from core.sandbox_policy import VT_EGRESS_HOST

        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(), url="https://exfil.attacker.com/x", tool_name="t")
        assert d.decision == BLOCKED
        assert d.violation_type == VT_EGRESS_HOST
        assert "exfil.attacker.com" in d.violation_detail
        assert d.metadata_json.get("allowlist_size") > 0

    def test_non_http_scheme_blocked(self, monkeypatch):
        from core.sandbox_egress_proxy import check_egress
        from core.sandbox_policy import VT_EGRESS_HOST

        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = check_egress(_policy(), url="file:///etc/passwd", tool_name="t")
        assert d.decision == BLOCKED
        assert d.violation_type == VT_EGRESS_HOST
        assert "non-http(s) scheme" in d.violation_detail

        d2 = check_egress(_policy(), url="ftp://exfil.attacker.com/x", tool_name="t")
        assert d2.decision == BLOCKED

    def test_parse_error_fails_closed(self, monkeypatch):
        """An exception inside check_egress must BLOCK, never ALLOW."""
        from core.sandbox_egress_proxy import check_egress

        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        bad_policy = SandboxPolicy(run_id="r", agent_id="a", tier_at_issuance="x", egress_hosts=None)
        d = check_egress(bad_policy, url="https://exfil.attacker.com/x", tool_name="t")
        assert d.decision == BLOCKED
        assert "egress check error" in d.violation_detail

        def _boom():
            raise RuntimeError("config broken")

        monkeypatch.setattr(
            "core.sandbox_egress_proxy.sandbox_config.is_sandbox_egress_enabled", _boom
        )
        d2 = check_egress(_policy(), url="https://api.anthropic.com", tool_name="t")
        assert d2.decision == BLOCKED

    def test_extract_urls_empty_args(self):
        from core.sandbox_egress_proxy import extract_urls_from_args

        assert extract_urls_from_args({}) == {}
        assert extract_urls_from_args(None) == {}

    def test_extract_urls_http_prefix_without_scheme(self):
        from core.sandbox_egress_proxy import extract_urls_from_args

        urls = extract_urls_from_args({"host": "httpbin.org", "count": 3, "url": 42})
        assert urls == {"host": "httpbin.org"}  # http-prefixed + non-str skipped

    def test_validate_no_url_args_allowed(self):
        from core.sandbox_egress_proxy import validate

        d = validate(_policy(), "browser_click", {})
        assert d.decision == ALLOWED
        assert d.metadata_json.get("reason") == "no_url_args"

    def test_validate_blocked_dominates(self, monkeypatch):
        from core.sandbox_egress_proxy import validate

        monkeypatch.setenv("ATOM_SANDBOX_EGRESS_ENABLED", "true")
        d = validate(
            _policy(),
            "browser_navigate",
            {"url": "https://exfil.attacker.com/x", "callback_url": "https://api.anthropic.com"},
        )
        assert d.decision == BLOCKED
        assert d.metadata_json.get("arg_key") == "url"

    def test_validate_restricted_becomes_worst(self, monkeypatch):
        """A RESTRICTED decision from check_egress propagates as worst."""
        from core import sandbox_egress_proxy
        from core.sandbox_egress_proxy import validate

        def fake_check_egress(policy, *, url, tool_name, args_hash=None):
            decision = RESTRICTED if "evil" in url else ALLOWED
            return SandboxDecision(
                decision=decision,
                phase="D",
                tool_name=tool_name,
                args_hash=args_hash,
                metadata_json={"url": url},
            )

        monkeypatch.setattr(sandbox_egress_proxy, "check_egress", fake_check_egress)
        d = validate(
            _policy(),
            "browser_navigate",
            {"url": "https://ok.example.com", "callback_url": "https://evil.example.com"},
        )
        assert d.decision == RESTRICTED
        assert "evil" in d.metadata_json["url"]

    def test_proxy_allowlist_property(self):
        from core.sandbox_egress_proxy import get_dual_proxy_split

        llm_proxy, tool_proxy = get_dual_proxy_split(_policy(egress_hosts=("custom.tool.com",)))
        assert "api.anthropic.com" in llm_proxy.allowlist
        assert "api.anthropic.com" in tool_proxy.allowlist
        assert "custom.tool.com" in tool_proxy.allowlist
        assert "custom.tool.com" not in llm_proxy.allowlist

    def test_proxy_can_connect_normalizes_input(self):
        from core.sandbox_egress_proxy import LlmProxy

        proxy = LlmProxy()
        assert proxy.can_connect("API.Anthropic.COM:443") is True
        assert proxy.can_connect("") is False
        assert proxy.can_connect("api.openai.com.") is True


# ===========================================================================
# sandbox_killrun — DB persistence + guard edge paths
# ===========================================================================
class TestKillrun:
    @pytest.fixture
    def inmem_engine(self):
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        from core.models import AgentExecution, Base

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[AgentExecution.__table__])
        yield engine
        engine.dispose()

    def test_killrun_persists_status_to_real_db(self, inmem_engine):
        """trigger_killrun updates agent_executions.status → killed_sandbox (real SQLite)."""
        from sqlalchemy.orm import sessionmaker

        from core.models import AgentExecution

        Session = sessionmaker(bind=inmem_engine)
        s1 = Session()
        s1.add(AgentExecution(id="exec-db-1", status="running"))
        s1.commit()

        sandbox_killrun.trigger_killrun(
            "run-db-1", "destructive pattern", tripwire_id="tw1", execution_id="exec-db-1", db=s1
        )
        s1.close()

        s2 = Session()
        try:
            row = s2.query(AgentExecution).filter(AgentExecution.id == "exec-db-1").first()
            assert row is not None
            assert row.status == "killed_sandbox"
        finally:
            s2.close()
        assert sandbox_killrun.is_killed("run-db-1") is True

    def test_killrun_execution_row_missing_is_noop(self, inmem_engine):
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=inmem_engine)
        s = Session()
        sandbox_killrun.trigger_killrun("run-missing", "reason", execution_id="no-such-id", db=s)
        s.close()
        assert sandbox_killrun.is_killed("run-missing") is True

    def test_killrun_owns_session_closed(self, monkeypatch):
        """db=None → trigger_killrun opens and closes its own session."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        monkeypatch.setattr("core.database.SessionLocal", lambda: mock_session)

        sandbox_killrun.trigger_killrun("run-own", "reason")
        assert sandbox_killrun.is_killed("run-own") is True
        mock_session.query.assert_called_once()
        mock_session.close.assert_called_once()

    def test_killrun_db_error_never_raises(self):
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("db down")

        sandbox_killrun.trigger_killrun("run-err", "reason", db=mock_db)
        assert sandbox_killrun.is_killed("run-err") is True  # registry still marked

    def test_killrun_registry_error_never_raises(self, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("registry broken")

        monkeypatch.setattr(KillRunRegistry, "trigger", _boom)
        sandbox_killrun.trigger_killrun("run-boom", "reason")  # no raise
        assert sandbox_killrun.is_killed("run-boom") is False  # registry never marked

    def test_killrun_guard_unknown_reason_when_state_missing(self):
        reg = sandbox_killrun.get_registry()
        reg._killed["ghost"] = None  # type: ignore[attr-defined]
        with pytest.raises(KillRunAborted, match="unknown"):
            sandbox_killrun.guard("ghost")

    def test_killrun_registry_state_and_release(self):
        reg = sandbox_killrun.get_registry()
        state = reg.trigger(
            "run-e", "tripwire fired", tripwire_id="tw1", evidence={"pattern": "DROP TABLE"}
        )
        assert reg.get_state("run-e") is state
        assert state.evidence == {"pattern": "DROP TABLE"}
        assert state.tripwire_id == "tw1"
        assert state.triggered_at > 0
        assert reg.is_killed("run-e") is True

        reg.release("run-e")
        assert reg.is_killed("run-e") is False
        assert reg.get_state("run-e") is None

    def test_killrun_registry_reset(self):
        reg = sandbox_killrun.get_registry()
        reg.trigger("run-r", "reason")
        assert reg.is_killed("run-r") is True
        reg.reset()
        assert reg.is_killed("run-r") is False
        assert reg.get_state("run-r") is None

    def test_killrun_registry_first_instantiation(self):
        original = KillRunRegistry._instance
        try:
            KillRunRegistry._instance = None
            r = KillRunRegistry()
            assert r._killed == {}  # type: ignore[attr-defined]
            assert r._killed_lock is not None  # type: ignore[attr-defined]
        finally:
            KillRunRegistry._instance = original

    def test_killrun_is_killed_predicate_empty(self):
        assert sandbox_killrun.is_killed("") is False
        assert sandbox_killrun.is_killed(None) is False  # type: ignore[arg-type]

    def test_killrun_guard_noop_for_unknown_run(self):
        sandbox_killrun.guard("never-killed")  # no raise
        sandbox_killrun.guard("")
        sandbox_killrun.guard(None)  # type: ignore[arg-type]

    def test_killrun_trigger_evidence_default(self):
        reg = sandbox_killrun.get_registry()
        state = reg.trigger("run-d", "reason")
        assert state.evidence == {}
        assert state.tripwire_id is None

    def test_killrun_trigger_idempotent_first_reason_wins(self):
        reg = sandbox_killrun.get_registry()
        state1 = reg.trigger("run-i", "first reason", tripwire_id="tw1")
        state2 = reg.trigger("run-i", "second reason", tripwire_id="tw2", evidence={"x": 1})
        assert state1 is state2
        assert state2.reason == "first reason"
        assert state2.tripwire_id == "tw1"

    def test_killrun_aborted_is_exception(self):
        assert issubclass(KillRunAborted, Exception)
