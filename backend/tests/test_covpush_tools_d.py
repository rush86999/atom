"""Coverage-push + bug-hunt tests for backend/tools (part 4): browser_tool.

All Playwright interaction is mocked — no browsers are launched.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

import tools.browser_tool as bt


def _fake_locator(count=1, tag="BUTTON"):
    loc = MagicMock()
    loc.wait_for = AsyncMock()
    loc.count = AsyncMock(return_value=count)
    nth = MagicMock()
    nth.evaluate = AsyncMock(return_value={"tag": tag, "attrs": {"id": "x"}})
    loc.nth.return_value = nth
    loc.evaluate = AsyncMock(return_value={"tag": tag, "type": ""})
    loc.first = loc
    loc.click = AsyncMock()
    loc.all_inner_texts = AsyncMock(return_value=["one", "two"])
    return loc


def _fake_page():
    page = MagicMock()
    page.goto = AsyncMock(return_value=SimpleNamespace(status=200))
    page.title = AsyncMock(return_value="Test Page")
    page.url = "https://example.com"
    page.screenshot = AsyncMock(return_value=b"png-bytes")
    page.fill = AsyncMock()
    page.select_option = AsyncMock()
    page.click = AsyncMock()
    page.evaluate = AsyncMock(return_value={"result": 42})
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.query_selector_all = AsyncMock(return_value=[])
    page.inner_text = AsyncMock(return_value="body text")
    page.close = AsyncMock()
    page.locator.return_value = _fake_locator()
    context = MagicMock()
    context.cookies = AsyncMock(return_value=[{"name": "a"}, {"name": "b"}])
    page.context = context
    return page


def _session(page=None, user="u-1"):
    session = bt.BrowserSession(session_id="s-1", user_id=user, agent_id="a-1")
    page = page or _fake_page()
    session.page = page
    session.context = page.context
    session.last_used = datetime.now()
    return session


def _manager(session):
    mgr = bt.BrowserSessionManager()
    mgr.sessions[session.session_id] = session
    return mgr


@pytest.fixture
def browser_env():
    with patch("tools.browser_tool.get_browser_manager") as gbm, \
         patch("tools.browser_tool.FeatureFlags.should_enforce_governance",
               return_value=False):
        yield gbm


class TestBrowserHelpers:
    async def test_resolve_selector_confidence_disabled(self):
        with patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", False):
            loc = _fake_locator()
            page = MagicMock()
            page.locator.return_value = loc
            result, conf = await bt._resolve_selector_with_confidence(page, "#a")
        assert conf.level == "high"
        assert result is loc

    async def test_resolve_selector_timeout(self):
        loc = _fake_locator()
        loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        page = MagicMock()
        page.locator.return_value = loc
        result, conf = await bt._resolve_selector_with_confidence(page, "#a")
        assert result is None
        assert conf.level == "ambiguous"

    async def test_resolve_selector_success_high(self):
        loc = _fake_locator(count=1)
        page = MagicMock()
        page.locator.return_value = loc
        result, conf = await bt._resolve_selector_with_confidence(
            page, "[data-testid='btn']")
        assert result is loc
        assert conf.level == "high"
        assert conf.score == 1.0

    async def test_resolve_selector_evaluate_error_swallowed(self):
        loc = _fake_locator(count=2)
        loc.nth.return_value.evaluate = AsyncMock(side_effect=RuntimeError("x"))
        page = MagicMock()
        page.locator.return_value = loc
        result, conf = await bt._resolve_selector_with_confidence(page, "#a")
        assert result is not None

    async def test_resolve_selector_exception(self):
        page = MagicMock()
        page.locator.side_effect = ValueError("malformed")
        result, conf = await bt._resolve_selector_with_confidence(page, "a]")
        assert result is None
        assert conf.level == "ambiguous"
        assert "resolution error" in conf.rationale

    async def test_execute_with_locator(self):
        ok, upgraded, err = await bt._execute_with_locator(None, AsyncMock())
        assert ok is False and err == "no locator resolved"
        action = AsyncMock()
        ok, upgraded, err = await bt._execute_with_locator(_fake_locator(), action)
        assert ok is True and err is None
        failing = AsyncMock(side_effect=PlaywrightError("strict mode violation: 2 elements"))
        ok, upgraded, err = await bt._execute_with_locator(_fake_locator(), failing)
        assert ok is False and upgraded.level == "ambiguous"
        failing2 = AsyncMock(side_effect=PlaywrightError("timeout"))
        ok, upgraded, err = await bt._execute_with_locator(_fake_locator(), failing2)
        assert ok is False and upgraded is None
        failing3 = AsyncMock(side_effect=ValueError("boom"))
        ok, upgraded, err = await bt._execute_with_locator(_fake_locator(), failing3)
        assert ok is False and upgraded is None and "boom" in err

    def test_confidence_to_dict(self):
        assert bt._confidence_to_dict(None) is None
        conf = bt.MatchConfidence(level="high", score=1.0, rationale="r", candidates=[],
                                  chosen_index=0)
        d = bt._confidence_to_dict(conf)
        assert d["level"] == "high"

    def test_write_browser_audit_no_db(self):
        bt._write_browser_audit(None, "a-1", "u-1", "s-1", "click", "started")

    def test_write_browser_audit_success_and_failure(self):
        db = MagicMock()
        db.commit = Mock()
        db.rollback = Mock()
        with patch("core.audit_service.AuditService") as audit_cls:
            audit = MagicMock()
            audit_cls.return_value = audit
            bt._write_browser_audit(db, "a-1", "u-1", "s-1", "click", "success",
                                    confidence=bt.MatchConfidence(
                                        level="high", score=1.0, rationale="r",
                                        candidates=[], chosen_index=0),
                                    error="boom")
            assert audit.create_browser_audit.call_count == 1
            db.commit.side_effect = RuntimeError("commit failed")
            bt._write_browser_audit(db, "a-1", "u-1", "s-1", "click", "started")
            db.rollback.assert_called()
        with patch("core.audit_service.AuditService", side_effect=RuntimeError("no audit")):
            bt._write_browser_audit(db, "a-1", "u-1", "s-1", "click", "started")

    async def test_maybe_gate_with_proposal(self):
        conf = bt.MatchConfidence(level="ambiguous", score=0.0, rationale="r", candidates=[],
                                  chosen_index=-1)
        assert await bt._maybe_gate_with_proposal("click", "#a", conf, "a-1", Mock(), "s-1",
                                                  "u-1", override=True) is None
        high = bt.MatchConfidence(level="high", score=1.0, rationale="r", candidates=[],
                                  chosen_index=0)
        assert await bt._maybe_gate_with_proposal("click", "#a", high, "a-1", Mock(), "s-1",
                                                  "u-1") is None
        with patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", False):
            assert await bt._maybe_gate_with_proposal("click", "#a", conf, "a-1", Mock(),
                                                      "s-1", "u-1") is None
        assert await bt._maybe_gate_with_proposal("click", "#a", conf, None, Mock(), "s-1",
                                                  "u-1") is None
        with patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.ProposalService") as prop_cls:
            proposal = SimpleNamespace(id="prop-1")
            prop_cls.return_value.create_action_proposal = AsyncMock(return_value=proposal)
            res = await bt._maybe_gate_with_proposal(
                "click", "#a", conf, "a-1", Mock(), "s-1", "u-1",
                extra_selectors={"#b": "v"}, per_field_confidence={"#a": {}})
        assert res["requires_approval"] is True and res["proposal_id"] == "prop-1"
        with patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.ProposalService",
                   side_effect=RuntimeError("proposal down")):
            res2 = await bt._maybe_gate_with_proposal("click", "#a", conf, "a-1", Mock(),
                                                      "s-1", "u-1")
        assert res2 is None


class TestBrowserSessionLifecycle:
    async def test_start_firefox(self):
        pw = MagicMock()
        firefox = MagicMock()
        firefox.launch = AsyncMock()
        pw.firefox = firefox
        with patch("tools.browser_tool.async_playwright") as ap:
            ap.return_value.start = AsyncMock(return_value=pw)
            session = bt.BrowserSession("s-1", "u-1", browser_type="firefox")
            assert await session.start() is True
        firefox.launch.assert_awaited_once()

    async def test_start_webkit(self):
        pw = MagicMock()
        webkit = MagicMock()
        webkit.launch = AsyncMock()
        pw.webkit = webkit
        with patch("tools.browser_tool.async_playwright") as ap:
            ap.return_value.start = AsyncMock(return_value=pw)
            session = bt.BrowserSession("s-1", "u-1", browser_type="webkit")
            assert await session.start() is True
        webkit.launch.assert_awaited_once()

    async def test_start_error(self):
        with patch("tools.browser_tool.async_playwright") as ap:
            ap.return_value.start = AsyncMock(side_effect=RuntimeError("no binary"))
            session = bt.BrowserSession("s-1", "u-1")
            with pytest.raises(RuntimeError):
                await session.start()

    async def test_close_full(self):
        session = bt.BrowserSession("s-1", "u-1")
        session.page = MagicMock()
        session.page.close = AsyncMock()
        session.context = MagicMock()
        session.context.close = AsyncMock()
        session.browser = MagicMock()
        session.browser.close = AsyncMock()
        session.playwright = MagicMock()
        session.playwright.stop = AsyncMock()
        assert await session.close() is True
        session.page.close.assert_awaited_once()
        session.playwright.stop.assert_awaited_once()

    async def test_close_partial_and_error(self):
        session = bt.BrowserSession("s-1", "u-1")
        assert await session.close() is True
        session.page = MagicMock()
        session.page.close = AsyncMock(side_effect=RuntimeError("x"))
        assert await session.close() is False

    async def test_manager_create_and_cleanup(self):
        mgr = bt.BrowserSessionManager()
        with patch.object(bt.BrowserSession, "start", new=AsyncMock()):
            session = await mgr.create_session("u-1", headless=True)
        assert mgr.get_session(session.session_id) is session
        assert await mgr.close_session(session.session_id) is True
        assert await mgr.close_session("nope") is False

    async def test_manager_cleanup_expired(self):
        mgr = bt.BrowserSessionManager(session_timeout_minutes=60)
        s1 = _session()
        s1.last_used = datetime.now() - timedelta(minutes=61)
        mgr.sessions["s-1"] = s1
        s2 = _session()
        mgr.sessions["s-2"] = s2
        with patch.object(bt.BrowserSession, "close", new=AsyncMock()):
            count = await mgr.cleanup_expired_sessions()
        assert count == 1
        assert "s-1" not in mgr.sessions


class TestBrowserCreateSession:
    async def test_create_session_no_governance(self, browser_env):
        session = _session()
        browser_env.return_value.create_session = AsyncMock(return_value=session)
        res = await bt.browser_create_session("u-1", agent_id="a-1")
        assert res["success"] is True
        assert res["session_id"] == "s-1"
        assert res["headless"] is True

    async def test_create_session_governance_blocked(self, browser_env):
        agent = SimpleNamespace(id="a-1")
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))
        gov = MagicMock()
        gov.can_perform_action.return_value = {"allowed": False, "reason": "too young"}
        with patch("tools.browser_tool.AgentContextResolver", return_value=resolver), \
             patch("tools.browser_tool.FeatureFlags.should_enforce_governance",
                   return_value=True), \
             patch("tools.browser_tool.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            res = await bt.browser_create_session("u-1", agent_id="a-1", db=Mock())
        assert res["success"] is False
        assert "too young" in res["error"]
        browser_env.return_value.create_session.assert_not_called()

    async def test_create_session_governance_allowed(self, browser_env):
        agent = SimpleNamespace(id="a-1")
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))
        gov = MagicMock()
        gov.can_perform_action.return_value = {"allowed": True, "reason": None}
        gov.record_outcome = AsyncMock()
        session = _session()
        browser_env.return_value.create_session = AsyncMock(return_value=session)
        db = MagicMock()
        db.commit = Mock()
        db.refresh = Mock()
        with patch("tools.browser_tool.AgentContextResolver", return_value=resolver), \
             patch("tools.browser_tool.FeatureFlags.should_enforce_governance",
                   return_value=True), \
             patch("tools.browser_tool.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            res = await bt.browser_create_session("u-1", agent_id="a-1", db=db,
                                                  headless=False, browser_type="firefox")
        assert res["success"] is True and res["agent_id"] == "a-1"
        gov.record_outcome.assert_awaited_once()
        db.commit.assert_called()

    async def test_create_session_error_path(self, browser_env):
        browser_env.return_value.create_session = AsyncMock(
            side_effect=RuntimeError("no browser"))
        res = await bt.browser_create_session("u-1")
        assert res["success"] is False

    async def test_create_session_governance_error_recorded(self, browser_env):
        agent = SimpleNamespace(id="a-1")
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))
        gov = MagicMock()
        gov.can_perform_action.return_value = {"allowed": True, "reason": None}
        gov.record_outcome = AsyncMock()
        db = MagicMock()
        db.commit = Mock()
        db.refresh = Mock()
        browser_env.return_value.create_session = AsyncMock(
            side_effect=RuntimeError("crash"))
        with patch("tools.browser_tool.AgentContextResolver", return_value=resolver), \
             patch("tools.browser_tool.FeatureFlags.should_enforce_governance",
                   return_value=True), \
             patch("tools.browser_tool.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            res = await bt.browser_create_session("u-1", agent_id="a-1", db=db)
        assert res["success"] is False
        gov.record_outcome.assert_awaited_once()


class TestBrowserActions:
    async def test_navigate_not_found_and_wrong_user(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_navigate("s-1", "https://x.com")
        assert res["success"] is False and "not found" in res["error"]
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_navigate("s-1", "https://x.com", user_id="other")
        assert res["success"] is False and "different user" in res["error"]

    @pytest.mark.parametrize("url", [
        "ftp://example.com", "file:///etc/passwd", "javascript:alert(1)",
    ])
    async def test_navigate_bad_scheme(self, browser_env, url):
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_navigate("s-1", url)
        assert res["success"] is False and "scheme" in res["error"]

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/admin", "http://10.0.0.5/x", "http://169.254.169.254/meta",
        "http://192.168.1.1/x", "http://0.0.0.0/x",
    ])
    async def test_navigate_private_ip_blocked(self, browser_env, url):
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_navigate("s-1", url)
        assert res["success"] is False and "private/internal" in res["error"]

    async def test_navigate_success_and_invalid_wait_until(self, browser_env):
        session = _session()
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_navigate("s-1", "https://example.com", wait_until="bogus")
        assert res["success"] is True and res["title"] == "Test Page"
        session.page.goto.assert_awaited_once_with("https://example.com", wait_until="load",
                                                   timeout=30000)

    async def test_navigate_exception(self, browser_env):
        session = _session()
        session.page.goto = AsyncMock(side_effect=PlaywrightError("net error"))
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_navigate("s-1", "https://example.com")
        assert res["success"] is False

    async def test_screenshot_not_found_and_wrong_user(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_screenshot("s-1")
        assert res["success"] is False
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_screenshot("s-1", user_id="other")
        assert res["success"] is False

    async def test_screenshot_data(self, browser_env):
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_screenshot("s-1")
        assert res["success"] is True and res["format"] == "png"
        assert res["size_bytes"] == len(b"png-bytes")

    async def test_screenshot_save_to_file(self, browser_env, tmp_path):
        session = _session()
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.os.getenv", return_value=str(tmp_path)):
            res = await bt.browser_screenshot("s-1", path="shots/one.png")
        assert res["success"] is True and res["path"].endswith("shots/one.png")
        assert (tmp_path / "shots" / "one.png").exists()

    @pytest.mark.parametrize("path", ["../escape.png", "/etc/evil.png"])
    async def test_screenshot_bad_path(self, browser_env, path):
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_screenshot("s-1", path=path)
        assert res["success"] is False

    async def test_screenshot_exception(self, browser_env):
        session = _session()
        session.page.screenshot = AsyncMock(side_effect=RuntimeError("x"))
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_screenshot("s-1")
        assert res["success"] is False

    async def test_fill_form_not_found_and_wrong_user(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_fill_form("s-1", {"#a": "1"})
        assert res["success"] is False
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_fill_form("s-1", {"#a": "1"}, user_id="other")
        assert res["success"] is False

    async def test_fill_form_legacy_path(self, browser_env):
        session = _session()
        el = MagicMock()
        el.evaluate = AsyncMock(return_value="INPUT")
        session.page.query_selector = AsyncMock(
            side_effect=lambda sel: el if sel != "button[type='submit']" else None)
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", False):
            res = await bt.browser_fill_form("s-1", {"#a": "1", "#b": "x"}, submit=True)
        assert res["success"] is True and res["fields_filled"] == 2
        assert res["submitted"] is True
        assert res["submission_method"] == "form_submit"

    async def test_fill_form_legacy_submit_via_form(self, browser_env):
        session = _session()
        el = MagicMock()
        el.evaluate = AsyncMock(return_value="INPUT")
        session.page.query_selector = AsyncMock(return_value=None)
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", False):
            res = await bt.browser_fill_form("s-1", {"#a": "1"}, submit=True)
        assert res["submission_method"] == "form_submit"

    async def test_fill_form_legacy_submit_error(self, browser_env):
        session = _session()
        session.page.evaluate = AsyncMock(side_effect=RuntimeError("js error"))
        session.page.query_selector = AsyncMock(return_value=None)
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", False):
            res = await bt.browser_fill_form("s-1", {"#a": "1"}, submit=True)
        assert res["submitted"] is False and "submit_error" in res

    async def test_fill_form_locator_path(self, browser_env):
        session = _session()
        session.page.locator.return_value = _fake_locator(tag="INPUT")
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True):
            res = await bt.browser_fill_form("s-1", {"#a": "1"}, submit=False)
        assert res["success"] is True and res["fields_filled"] == 1
        assert "match_confidence" in res

    async def test_fill_form_locator_zero_matches(self, browser_env):
        session = _session()
        loc = _fake_locator()
        loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("t"))
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True):
            res = await bt.browser_fill_form("s-1", {"#a": "1"})
        assert res["success"] is True and res["fields_filled"] == 0

    async def test_fill_form_gated(self, browser_env):
        session = _session()
        loc = _fake_locator()
        loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("t"))
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        proposal = SimpleNamespace(id="prop-9")
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.ProposalService") as prop_cls, \
             patch("core.audit_service.AuditService") as audit_cls:
            prop_cls.return_value.create_action_proposal = AsyncMock(return_value=proposal)
            audit = MagicMock()
            audit_cls.return_value = audit
            res = await bt.browser_fill_form("s-1", {"#a": "1"}, agent_id="a-1", db=Mock())
        assert res["requires_approval"] is True and res["proposal_id"] == "prop-9"
        audit.create_browser_audit.assert_called()

    async def test_fill_form_exception(self, browser_env):
        session = _session()
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.datetime") as fake_dt:
            fake_dt.now.side_effect = RuntimeError("boom")
            res = await bt.browser_fill_form("s-1", {"#a": "1"})
        assert res["success"] is False

    async def test_click_not_found_and_wrong_user(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_click("s-1", "#a")
        assert res["success"] is False
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_click("s-1", "#a", user_id="other")
        assert res["success"] is False

    async def test_click_legacy(self, browser_env):
        session = _session()
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", False):
            res = await bt.browser_click("s-1", "#a", wait_for="#b")
        assert res["success"] is True
        session.page.click.assert_awaited_once()

    async def test_click_locator_zero_matches(self, browser_env):
        session = _session()
        loc = _fake_locator()
        loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("t"))
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_click("s-1", "#a", agent_id="a-1", db=Mock())
        assert res["success"] is False and "0 matches" in res["error"]

    async def test_click_locator_success_with_tiebreak(self, browser_env):
        session = _session()
        session.page.url = "https://example.com"
        loc = _fake_locator(count=2)
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        llm = MagicMock()
        upgraded = bt.MatchConfidence(level="high", score=0.9, rationale="llm", candidates=[],
                                      chosen_index=0)
        with patch("tools.browser_tool.get_llm_service", return_value=llm), \
             patch("tools.browser_tool.attach_tiebreak",
                   new=AsyncMock(return_value=upgraded)) as tie:
            res = await bt.browser_click("s-1", "button", agent_id="a-1", db=Mock())
        assert res["success"] is True
        tie.assert_awaited_once()

    async def test_click_gated(self, browser_env):
        session = _session()
        loc = _fake_locator()
        loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("t"))
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        proposal = SimpleNamespace(id="prop-3")
        with patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.ProposalService") as prop_cls:
            prop_cls.return_value.create_action_proposal = AsyncMock(return_value=proposal)
            res = await bt.browser_click("s-1", "#a", agent_id="a-1", db=Mock())
        assert res["requires_approval"] is True and res["proposal_id"] == "prop-3"

    async def test_click_execute_failure(self, browser_env):
        session = _session()
        loc = _fake_locator(count=1)
        loc.click = AsyncMock(side_effect=PlaywrightError("strict mode violation: 2 elements"))
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_click("s-1", "#a")
        assert res["success"] is False
        assert res["match_confidence"]["level"] == "ambiguous"

    async def test_click_exception(self, browser_env):
        session = _session()
        session.page.wait_for_selector = AsyncMock(side_effect=RuntimeError("boom"))
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", False):
            res = await bt.browser_click("s-1", "#a")
        assert res["success"] is False
        assert "boom" in res["error"]

    async def test_extract_text_paths(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_extract_text("s-1")
        assert res["success"] is False
        browser_env.return_value.get_session.return_value = _session()
        res = await bt.browser_extract_text("s-1", user_id="other")
        assert res["success"] is False
        session = _session()
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_extract_text("s-1")
        assert res["success"] is True and res["text"] == "body text"

    async def test_extract_text_locator_path(self, browser_env):
        session = _session()
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_extract_text("s-1", selector=".item")
        assert res["success"] is True and res["text"] == "one\ntwo"
        assert "match_confidence" in res

    async def test_extract_text_zero_matches(self, browser_env):
        session = _session()
        loc = _fake_locator()
        loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("t"))
        session.page.locator.return_value = loc
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_extract_text("s-1", selector=".item")
        assert res["success"] is True and res["text"] == ""

    async def test_extract_text_legacy(self, browser_env):
        session = _session()
        el = MagicMock()
        el.inner_text = AsyncMock(return_value="legacy")
        session.page.query_selector_all = AsyncMock(return_value=[el])
        browser_env.return_value.get_session.return_value = session
        with patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", False):
            res = await bt.browser_extract_text("s-1", selector=".item")
        assert res["success"] is True and res["text"] == "legacy"

    async def test_extract_text_error(self, browser_env):
        session = _session()
        session.page.inner_text = AsyncMock(side_effect=RuntimeError("boom"))
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_extract_text("s-1")
        assert res["success"] is False

    async def test_execute_script_paths(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_execute_script("s-1", "1+1")
        assert res["success"] is False
        session = _session()
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_execute_script("s-1", "1+1", user_id="other")
        assert res["success"] is False
        res = await bt.browser_execute_script("s-1", "1+1")
        assert res["success"] is True and res["result"] == {"result": 42}
        session.page.evaluate = AsyncMock(side_effect=PlaywrightError("x"))
        res = await bt.browser_execute_script("s-1", "1+1")
        assert res["success"] is False

    async def test_close_session_paths(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_close_session("s-1")
        assert res["success"] is False
        session = _session()
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_close_session("s-1", user_id="other")
        assert res["success"] is False
        browser_env.return_value.close_session = AsyncMock(return_value=True)
        res = await bt.browser_close_session("s-1")
        assert res["success"] is True
        browser_env.return_value.close_session = AsyncMock(return_value=False)
        res = await bt.browser_close_session("s-1")
        assert res["success"] is False
        browser_env.return_value.close_session = AsyncMock(side_effect=RuntimeError("x"))
        res = await bt.browser_close_session("s-1")
        assert res["success"] is False

    async def test_get_page_info_paths(self, browser_env):
        browser_env.return_value.get_session.return_value = None
        res = await bt.browser_get_page_info("s-1")
        assert res["success"] is False
        session = _session()
        browser_env.return_value.get_session.return_value = session
        res = await bt.browser_get_page_info("s-1", user_id="other")
        assert res["success"] is False
        res = await bt.browser_get_page_info("s-1")
        assert res["success"] is True and res["cookies_count"] == 2
        session.context.cookies = AsyncMock(side_effect=PlaywrightError("x"))
        res = await bt.browser_get_page_info("s-1")
        assert res["success"] is False

    async def test_get_browser_manager(self):
        assert bt.get_browser_manager() is bt._session_manager
