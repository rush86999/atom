"""
Round 72 — Workstreams C (skill auto-injection) + E (FieldGuide snapshot).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_retrieval_service import SkillRetrievalService


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    # Isolate from dev env vars; set the R72 default explicitly.
    monkeypatch.delenv("ATOM_SKILL_INJECTION_ENABLED", raising=False)
    monkeypatch.delenv("TURN_FACT_EXTRACTION_ENABLED", raising=False)
    monkeypatch.delenv("TURN_FACT_VECTOR_RECALL_ENABLED", raising=False)


def _fake_registry():
    reg = MagicMock()
    reg.list_skills.return_value = [
        {"skill_id": "s1", "skill_name": "invoice_parser", "status": "Active"},
        {"skill_id": "s2", "skill_name": "email_writer", "status": "Active"},
    ]
    reg.get_skill.side_effect = lambda sid: {
        "s1": {"skill_name": "invoice_parser", "description": "Parse invoices and extract line items", "tags": ["invoices", "finance"], "skill_body": "def parse_invoice(x): return x"},
        "s2": {"skill_name": "email_writer", "description": "Draft professional email replies", "tags": ["email", "communication"], "skill_body": "def draft_email(x): return x"},
    }[sid]
    return reg


class TestSkillRetrieval:
    def test_ranks_by_keyword_match(self):
        svc = SkillRetrievalService()
        reg = _fake_registry()
        with patch(
            "core.skill_registry_service.SkillRegistryService", return_value=reg
        ):
            block = svc.retrieve_top_skills(MagicMock(), "t", "ws", "parse invoice line items")
        assert "invoice_parser" in block
        assert "email_writer" not in block

    def test_limit_honored(self):
        svc = SkillRetrievalService()
        reg = _fake_registry()
        with patch(
            "core.skill_registry_service.SkillRegistryService", return_value=reg
        ):
            block = svc.retrieve_top_skills(MagicMock(), "t", "ws", "invoice email finance", limit=1)
        assert block.count("`") == 2  # exactly one skill listed

    def test_no_match_returns_empty(self):
        svc = SkillRetrievalService()
        reg = _fake_registry()
        with patch(
            "core.skill_registry_service.SkillRegistryService", return_value=reg
        ):
            block = svc.retrieve_top_skills(MagicMock(), "t", "ws", "quantum zucchini")
        assert block == ""

    def test_flag_off_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ATOM_SKILL_INJECTION_ENABLED", "false")
        svc = SkillRetrievalService()
        block = svc.retrieve_top_skills(MagicMock(), "t", "ws", "invoice")
        assert block == ""


class TestFieldGuideInjection:
    @patch("core.atom_meta_agent.SessionLocal")
    @pytest.mark.asyncio
    async def test_react_step_includes_guide_block(self, mock_session):
        import core.atom_meta_agent as ama
        db = MagicMock()
        ws = MagicMock()
        ws.tenant_id = "tenant"
        db.query.return_value.filter.return_value.first.return_value = ws
        mock_session.return_value.__enter__.return_value = db
        mock_session.return_value.__exit__.return_value = None

        agent = ama.AtomMetaAgent()
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        captured = {}

        async def fake_generate(**kw):
            captured["system"] = kw.get("system_instruction", "")
            captured["prompt"] = kw.get("prompt", "")
            return ReActStep(thought="t", final_answer="ok")

        from core.react_models import ReActStep
        agent.llm = MagicMock()
        agent.llm.generate_structured_response = fake_generate

        guide_text = (
            "## \U0001f5fa Workspace Field Guide\n_Curated by agents._\n\n- insight\n---\n"
        )
        await agent._react_step(
            "test request",
            {},
            "tool: x",
            "",
            {"_field_guide_context": guide_text},
        )
        assert "Workspace Field Guide" in captured["prompt"]

    @pytest.mark.asyncio
    async def test_react_step_absent_when_no_guide(self):
        import core.atom_meta_agent as ama
        agent = ama.AtomMetaAgent()
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        captured = {}

        async def fake_generate(**kw):
            captured["prompt"] = kw.get("prompt", "")
            return ReActStep(thought="t", final_answer="ok")

        from core.react_models import ReActStep
        agent.llm = MagicMock()
        agent.llm.generate_structured_response = fake_generate

        await agent._react_step(
            "test request", {}, "tool: x", "", {"_field_guide_context": ""}
        )
        assert "Workspace Field Guide" not in captured["prompt"]
