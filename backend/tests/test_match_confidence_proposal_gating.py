# -*- coding: utf-8 -*-
"""
TDD tests for Phase 4 — AUTONOMOUS override → ProposalService gating.

Verifies that partial/ambiguous selector matches route through
ProposalService.create_action_proposal for ALL tiers (including
AUTONOMOUS, whose tier is currently routed by history not current-call
certainty), and that approved proposals re-execute without re-gating.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.browser_tool import browser_click, browser_fill_form, browser_extract_text
from core.selector_confidence_service import (
    AMBIGUOUS,
    HIGH,
    PARTIAL,
    MatchConfidence,
    SelectorCandidate,
)


# Common patches applied to every gating test
_COMMON_PATCHES = [
    "tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL",
    "core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL",
]


def _gate_patches(value: bool = True):
    """Return a list of patch() contexts for both module bindings."""
    return [patch(p, value) for p in _COMMON_PATCHES]


def _make_locator_mock(count: int = 1):
    loc = MagicMock()
    loc.wait_for = AsyncMock()
    loc.count = AsyncMock(return_value=count)
    loc.first = loc
    nth = MagicMock()
    nth.evaluate = AsyncMock(
        return_value={"tag": "BUTTON", "attrs": {}}
    )
    loc.nth = Mock(return_value=nth)
    loc.click = AsyncMock()
    loc.fill = AsyncMock()
    loc.all_inner_texts = AsyncMock(return_value=["hello"])
    return loc


def _autonomous_agent():
    a = MagicMock()
    a.id = "auto-agent-1"
    a.name = "Auto Agent"
    a.status = "AUTONOMOUS"
    a.confidence_score = 0.95
    a.category = "automation"
    a.tenant_id = "default"
    a.user_id = "system"
    return a


def _setup_session(locator_by_selector, user_id="user-1"):
    """Build a mock browser manager + session."""
    mock_session = MagicMock()
    mock_session.user_id = user_id
    mock_session.last_used = None
    mock_session.page = MagicMock()

    if callable(locator_by_selector):
        mock_session.page.locator = Mock(side_effect=locator_by_selector)
    else:
        mock_session.page.locator = Mock(side_effect=lambda s: locator_by_selector.get(s))

    mock_mgr = MagicMock()
    mock_mgr.get_session = Mock(return_value=mock_session)
    return mock_mgr, mock_session


def _setup_proposal_service():
    """Mock ProposalService; return (patch_context, proposal_mock)."""
    mock_proposal = MagicMock()
    mock_proposal.id = "prop-123"

    mock_ps = MagicMock()
    mock_ps.create_action_proposal = AsyncMock(return_value=mock_proposal)
    mock_ps_cls = MagicMock(return_value=mock_ps)
    return mock_ps_cls, mock_proposal


# ===========================================================================
# Gating tests
# ===========================================================================
class TestProposalGating:
    @pytest.mark.asyncio
    async def test_autonomous_agent_partial_match_creates_proposal_not_click(self):
        """AUTONOMOUS + partial match + FORCE_PROPOSAL=true → requires_approval, no click."""
        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.get_llm_service", return_value=None):

            mock_mgr_instance, mock_session = _setup_session({"button.submit": _make_locator_mock(count=2)})
            mock_mgr.return_value = mock_mgr_instance

            mock_db = MagicMock()
            agent = _autonomous_agent()
            mock_db.query.return_value.filter.return_value.first.return_value = agent

            mock_ps_cls, mock_proposal = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                result = await browser_click(
                    session_id="s1",
                    selector="button.submit",
                    user_id="user-1",
                    agent_id="auto-agent-1",
                    db=mock_db,
                )

            assert result["requires_approval"] is True
            assert result["proposal_id"] == "prop-123"
            assert result["match_confidence"]["level"] == "partial"

    @pytest.mark.asyncio
    async def test_autonomous_agent_high_match_proceeds_without_proposal(self):
        """AUTONOMOUS + high match → click executes, no proposal."""
        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", True):

            mock_mgr_instance, mock_session = _setup_session({"#unique-submit": _make_locator_mock(count=1)})
            mock_mgr.return_value = mock_mgr_instance

            mock_db = MagicMock()

            mock_ps_cls, _ = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                result = await browser_click(
                    session_id="s1",
                    selector="#unique-submit",
                    user_id="user-1",
                    agent_id="auto-agent-1",
                    db=mock_db,
                )

            assert result["success"] is True
            assert result["match_confidence"]["level"] == "high"
            mock_ps_cls.return_value.create_action_proposal.assert_not_called()

    @pytest.mark.asyncio
    async def test_approved_proposal_executes_without_re_gating(self):
        """match_confidence_override=True → gate skipped, action executes."""
        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", True):

            mock_mgr_instance, mock_session = _setup_session({"button.submit": _make_locator_mock(count=2)})
            mock_mgr.return_value = mock_mgr_instance

            mock_db = MagicMock()

            mock_ps_cls, _ = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                # Override = post-approval re-execution
                result = await browser_click(
                    session_id="s1",
                    selector="button.submit",
                    user_id="user-1",
                    agent_id="auto-agent-1",
                    db=mock_db,
                    match_confidence_override=True,
                )

            assert result["success"] is True
            mock_ps_cls.return_value.create_action_proposal.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_proposal_disabled_does_not_gate(self):
        """MATCH_CONFIDENCE_FORCE_PROPOSAL=false (shadow) → click proceeds, only annotates."""
        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", False), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", False):

            mock_mgr_instance, mock_session = _setup_session({"button": _make_locator_mock(count=3)})
            mock_mgr.return_value = mock_mgr_instance

            mock_db = MagicMock()

            mock_ps_cls, _ = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                result = await browser_click(
                    session_id="s1",
                    selector="button",
                    user_id="user-1",
                    agent_id="auto-agent-1",
                    db=mock_db,
                )

            # Shadow mode: executes despite ambiguous
            assert result["success"] is True
            assert result["match_confidence"]["level"] == "ambiguous"
            mock_ps_cls.return_value.create_action_proposal.assert_not_called()

    @pytest.mark.asyncio
    async def test_fill_form_gates_whole_form_on_one_ambiguous_field(self):
        """Form with one ambiguous field → whole form gated, no fills execute."""
        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.get_llm_service", return_value=None):

            mock_mgr_instance, mock_session = _setup_session({
                "input.name": _make_locator_mock(count=3),  # ambiguous
                "#email": _make_locator_mock(count=1),      # high
            })
            mock_mgr.return_value = mock_mgr_instance
            mock_session.page.fill = AsyncMock()

            mock_db = MagicMock()
            agent = _autonomous_agent()
            mock_db.query.return_value.filter.return_value.first.return_value = agent

            mock_ps_cls, mock_proposal = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                result = await browser_fill_form(
                    session_id="s1",
                    selectors={"input.name": "Alice", "#email": "a@b.c"},
                    user_id="user-1",
                    agent_id="auto-agent-1",
                    db=mock_db,
                )

            assert result["requires_approval"] is True
            assert result["proposal_id"] == "prop-123"
            # NO fills executed (transactional integrity)
            mock_session.page.fill.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_text_never_gates_even_when_ambiguous(self):
        """extract_text with ambiguous matches → annotates only, never gates."""
        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", True):

            mock_mgr_instance, mock_session = _setup_session({"div.price": _make_locator_mock(count=5)})
            mock_mgr.return_value = mock_mgr_instance

            mock_db = MagicMock()

            mock_ps_cls, _ = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                result = await browser_extract_text(
                    session_id="s1",
                    selector="div.price",
                    user_id="user-1",
                )

            # Read-only: never gates
            assert result["success"] is True
            assert result["match_confidence"]["level"] == "ambiguous"
            mock_ps_cls.return_value.create_action_proposal.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_match_routes_to_proposal_not_timeout(self):
        """0 matches → ambiguous + proposal (no 5s timeout burn)."""
        from playwright.async_api import TimeoutError as PWTimeoutError

        with patch("tools.browser_tool.get_browser_manager") as mock_mgr, \
             patch("tools.browser_tool.BROWSER_LOCATOR_API_ENABLED", True), \
             patch("tools.browser_tool.SELECTOR_CONFIDENCE_ENABLED", True), \
             patch("tools.browser_tool.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("core.selector_confidence_service.MATCH_CONFIDENCE_FORCE_PROPOSAL", True), \
             patch("tools.browser_tool.get_llm_service", return_value=None):

            loc = _make_locator_mock(count=0)
            loc.wait_for = AsyncMock(side_effect=PWTimeoutError("timeout"))
            mock_mgr_instance, mock_session = _setup_session({".nonexistent": loc})
            mock_mgr.return_value = mock_mgr_instance

            mock_db = MagicMock()
            agent = _autonomous_agent()
            mock_db.query.return_value.filter.return_value.first.return_value = agent

            mock_ps_cls, mock_proposal = _setup_proposal_service()
            with patch("tools.browser_tool.ProposalService", mock_ps_cls):
                result = await browser_click(
                    session_id="s1",
                    selector=".nonexistent",
                    user_id="user-1",
                    agent_id="auto-agent-1",
                    db=mock_db,
                )

            assert result["requires_approval"] is True
            assert result["proposal_id"] == "prop-123"
            assert result["match_confidence"]["level"] == "ambiguous"
            assert result["match_confidence"]["score"] == 0.0
