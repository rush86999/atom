"""
TDD bug-hunt tests for the deeplinks / proposal / match-confidence territory.

Covers (each RED first):
  - /api/deeplinks/audit: IDOR when user_id filter is absent (agent_id/resource_type
    filters previously let any authenticated user read any user's audit rows).
  - parse_deep_link: double-``unquote`` after ``parse_qs`` corrupts values that
    legitimately contain percent sequences (breaks generate->parse round-trip);
    blank query values were dropped.
  - generate_deep_link: accepted resource ids that produce links parse_deep_link
    then rejects (space / path separators) — generated-but-undeployable links.
  - proposal_service.reject_proposal: no status guard — an already-executed
    proposal could be flipped to REJECTED, corrupting the audit state machine.
  - match_confidence_tiebreaker: an LLM returning an out-of-range chosen_index
    was propagated as a HIGH upgrade (used_llm=True), bypassing proposal gating.
  - str(e) leaks in the deep-link error paths returned to clients.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from api.deeplinks import get_deeplink_audit
from core.deeplinks import (
    DeepLinkParseException,
    DeepLinkSecurityException,
    execute_deep_link,
    generate_deep_link,
    parse_deep_link,
)
from core.llm.match_confidence_tiebreaker import (
    _circuit_breaker,
    _tiebreak_cache,
    break_tie,
)
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    DeepLinkAudit,
    ProposalStatus,
    ProposalType,
)
from core.proposal_service import ProposalService
from core.selector_confidence_service import (
    HIGH,
    PARTIAL,
    MatchConfidence,
    SelectorCandidate,
    attach_tiebreak,
)


@pytest.fixture(autouse=True)
def _audit_off(monkeypatch):
    monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)


@pytest.fixture(autouse=True)
def _isolate_tiebreaker_state():
    _tiebreak_cache.clear()
    _circuit_breaker.reset()
    yield
    _tiebreak_cache.clear()
    _circuit_breaker.reset()


@pytest.fixture
def db(worker_database):
    session = worker_database()
    from core.models import GatewayApiKey, User

    session.query(GatewayApiKey).delete()
    session.query(User).delete()
    session.query(DeepLinkAudit).delete()
    session.query(AgentProposal).delete()
    session.query(AgentRegistry).delete()
    session.commit()
    yield session
    session.close()


def _candidate(selector: str = "button", match_count: int = 2) -> SelectorCandidate:
    return SelectorCandidate(
        selector=selector,
        match_count=match_count,
        is_text_only=True,
        appeared_after_ms=0,
        tag_hint="BUTTON",
        attributes={},
    )


def _partial_confidence() -> MatchConfidence:
    return MatchConfidence(
        level=PARTIAL,
        score=0.70,
        rationale="2 matches (-0.30); text-only (-0.15)",
        candidates=[_candidate(), _candidate(selector="button.submit")],
        chosen_index=0,
    )


# ===========================================================================
# BUG 1 — /api/deeplinks/audit IDOR: user scope dropped when user_id absent
# ===========================================================================
class TestDeeplinkAuditScoping:
    def _seed(self, db, user_id, url, resource_id="agent-1"):
        row = DeepLinkAudit(
            id=f"dl-{user_id}-{resource_id}",
            user_id=user_id,
            agent_id="agent-1",
            resource_type="agent",
            resource_id=resource_id,
            action="execute",
            source="external",
            deeplink_url=url,
            status="success",
        )
        db.add(row)
        db.commit()
        return row

    @pytest.mark.asyncio
    async def test_absent_user_id_filter_does_not_leak_other_users(self, db):
        self._seed(db, "user-a", "atom://agent/agent-1?message=alice-secret")
        self._seed(db, "user-b", "atom://agent/agent-1?message=bob-secret")

        response = await get_deeplink_audit(
            user_id=None,
            agent_id=None,
            resource_type=None,
            limit=100,
            offset=0,
            current_user=SimpleNamespace(id="user-a"),
            db=db,
        )

        assert len(response) == 1
        assert response[0].user_id == "user-a"
        assert "bob-secret" not in response[0].deeplink_url

    @pytest.mark.asyncio
    async def test_foreign_user_id_filter_is_forced_back_to_caller(self, db):
        self._seed(db, "user-a", "atom://agent/agent-1?message=alice-secret")
        self._seed(db, "user-b", "atom://agent/agent-1?message=bob-secret")

        response = await get_deeplink_audit(
            user_id="user-b",
            agent_id=None,
            resource_type=None,
            limit=100,
            offset=0,
            current_user=SimpleNamespace(id="user-a"),
            db=db,
        )

        assert len(response) == 1
        assert response[0].user_id == "user-a"
        assert "bob-secret" not in response[0].deeplink_url

    @pytest.mark.asyncio
    async def test_agent_filter_does_not_widen_scope(self, db):
        self._seed(db, "user-a", "atom://agent/agent-1?message=a")
        self._seed(db, "user-b", "atom://agent/agent-2?message=b")

        response = await get_deeplink_audit(
            user_id=None,
            agent_id="agent-2",
            resource_type=None,
            limit=100,
            offset=0,
            current_user=SimpleNamespace(id="user-a"),
            db=db,
        )

        assert len(response) == 0


# ============================================================================
# BUG 2 — parse_deep_link double-unquote corrupts percent-escaped values
# ============================================================================
class TestParseDeepLinkEncoding:
    def test_generate_parse_roundtrip_preserves_percent_escapes(self):
        url = generate_deep_link("agent", "a-1", message="50%2F100", session="s-1")
        link = parse_deep_link(url)
        assert link.parameters["message"] == "50%2F100"
        assert link.parameters["session"] == "s-1"

    def test_percent_sequence_not_double_decoded(self):
        link = parse_deep_link("atom://agent/a-1?message=100%2525")
        assert link.parameters["message"] == "100%25"

    def test_empty_query_value_is_preserved(self):
        url = generate_deep_link("agent", "a-1", session="")
        link = parse_deep_link(url)
        assert link.parameters["session"] == ""

    def test_invalid_json_params_does_not_leak_decoder_detail(self):
        with pytest.raises(DeepLinkParseException) as exc:
            parse_deep_link("atom://tool/chart?params=%7Bbad%20json%7D")
        assert "Expecting" not in str(exc.value)


# ===========================================================================
# BUG 3 — generate_deep_link accepts ids that produce unparseable links
# ===========================================================================
class TestGenerateValidation:
    @pytest.mark.parametrize("bad_id", ["a b", "a/b", "../etc/passwd", "id\x00\\"])
    def test_generate_rejects_unparseable_resource_id(self, bad_id):
        with pytest.raises(ValueError):
            generate_deep_link("agent", bad_id)

    def test_generate_accepts_valid_resource_ids(self):
        assert generate_deep_link("agent", "agent-42_1") == "atom://agent/agent-42_1"


# ===========================================================================
# BUG 4 — reject_proposal lacks a status guard (executed -> rejected flip)
# ===========================================================================
class TestProposalRejectStateGuard:
    @pytest.fixture
    def intern_agent(self, db):
        agent = AgentRegistry(
            id="bughunt-intern",
            name="BugHunt Intern",
            category="testing",
            module_path="agents.test_agent",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db.add(agent)
        db.commit()
        return agent

    @pytest.mark.asyncio
    async def test_reject_after_approve_raises_and_preserves_state(self, db, intern_agent):
        service = ProposalService(db)
        proposal = await service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present", "canvas_type": "chart"},
            reasoning="TDD bughunt",
        )

        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            await service.approve_proposal(proposal.id, user_id="approver-1")

        db.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value

        with pytest.raises(ValueError):
            await service.reject_proposal(proposal.id, user_id="reviewer-1", reason="nope")

        db.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value

    @pytest.mark.asyncio
    async def test_reject_twice_raises(self, db, intern_agent):
        service = ProposalService(db)
        proposal = await service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present"},
            reasoning="TDD bughunt 2",
        )

        await service.reject_proposal(proposal.id, user_id="reviewer-1", reason="first")
        with pytest.raises(ValueError):
            await service.reject_proposal(proposal.id, user_id="reviewer-1", reason="again")


# ===========================================================================
# BUG 5 — tiebreaker out-of-range chosen_index must not upgrade to high
# ===========================================================================
class TestTiebreakOutOfRange:
    @pytest.mark.asyncio
    async def test_out_of_range_index_falls_through(self):
        llm_service = MagicMock()
        llm_service.generate_completion = AsyncMock(
            return_value={"text": '{"chosen_index": 99, "rationale": "oops"}', "success": True}
        )

        with patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED",
            True,
        ):
            result = await break_tie(
                candidates=[_candidate(), _candidate()],
                page_context={"url": "https://example.com/form"},
                llm_service=llm_service,
            )

        assert result.chosen_index == -1
        assert result.used_llm is False

    @pytest.mark.asyncio
    async def test_attach_tiebreak_keeps_partial_on_out_of_range_index(self):
        llm_service = MagicMock()
        llm_service.generate_completion = AsyncMock(
            return_value={"text": '{"chosen_index": 42, "rationale": "bogus"}', "success": True}
        )

        with patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED",
            True,
        ):
            original = _partial_confidence()
            upgraded = await attach_tiebreak(
                original,
                {"url": "https://example.com/form"},
                llm_service,
            )

        assert upgraded.level == PARTIAL
        assert upgraded.chosen_index == original.chosen_index


# ===========================================================================
# BUG 7 — approve_proposal crashed on ACTION proposals: the temporary swap in
# _execute_proposed_action_with assigned the read-only `proposed_action`
# property (AttributeError: no setter) — approval always failed end-to-end.
# ===========================================================================
class TestProposalApproveExecutes:
    @pytest.fixture
    def intern_agent(self, db):
        agent = AgentRegistry(
            id="bughunt-intern-approve",
            name="BugHunt Intern Approve",
            category="testing",
            module_path="agents.test_agent",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db.add(agent)
        db.commit()
        return agent

    @pytest.mark.asyncio
    async def test_approve_proposal_with_action_does_not_crash(self, db, intern_agent):
        service = ProposalService(db)
        proposal = await service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present", "canvas_type": "chart"},
            reasoning="TDD bughunt approve",
        )

        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True, "executed_at": "now"}
            result = await service.approve_proposal(proposal.id, user_id="approver-1")

        assert result["success"] is True
        db.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value
        assert proposal.execution_result["success"] is True


# ===========================================================================
# BUG 6 — str(e) leaks from deep-link error paths
# ===========================================================================
class TestDeepLinkErrorLeaks:
    @pytest.mark.asyncio
    async def test_execute_deep_link_hides_internal_exception_detail(self):
        secret = "psycopg2://user:pass@10.0.0.5/atom"
        conf = MagicMock()
        conf.resource_type = "agent"
        db = MagicMock()
        db.query.side_effect = RuntimeError(secret)

        with patch("core.deeplinks.parse_deep_link", return_value=conf):
            result = await execute_deep_link("atom://agent/x", user_id="u1", db=db)

        assert result["success"] is False
        assert secret not in result["error"]