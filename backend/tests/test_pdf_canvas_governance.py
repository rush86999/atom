"""PDF canvas governance tests — maturity-based review & approval (P2).

- Lifecycle state machine: submit_review → approve → immutable (edits
  refused) → reopen → editable again; archived terminal.
- tools/pdf_canvas_tool.py gating: a passing gate executes directly with NO
  proposal; a proposing gate files an AgentProposal (INTERN hires only) whose
  human approval executes the stored op through ProposalService — the same
  deterministic service a human click uses.
- Approval itself is maturity-tiered: an INTERN's approve becomes a proposal
  for a human; a SUPERVISED-tier gate approves directly.
"""

import os

os.environ.setdefault("TESTING", "1")

import contextlib

import pytest
from unittest.mock import patch

import tools.pdf_canvas_tool as tool_mod


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    monkeypatch.setenv("ATOM_PDF_CANVAS_DIR", str(tmp_path / "pdf_blobs"))
    eng = create_engine(f"sqlite:///{tmp_path}/pdf_canvas_gov.db")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)
    with Session() as s:
        yield s


@pytest.fixture
def session_ctx(db_session):
    @contextlib.contextmanager
    def _ctx():
        yield db_session

    with patch("core.database.get_db_session", _ctx):
        yield db_session


@pytest.fixture
def svc(session_ctx):
    from core.pdf_canvas_service import PdfCanvasService

    return PdfCanvasService(session_ctx)


@pytest.fixture
def canvas(svc):
    import io

    from reportlab.pdfgen import canvas as rl

    buf = io.BytesIO()
    c = rl.Canvas(buf, pagesize=(612, 792))
    for i in range(2):
        c.setFont("Helvetica", 12)
        c.drawString(72, 700, f"contract p{i + 1}")
        c.showPage()
    c.save()

    result = svc.create_pdf_canvas("u-1", filename="contract.pdf", content_bytes=buf.getvalue())
    assert result["success"]
    return result["canvas_id"]


@pytest.fixture
def agent(svc):
    from core.models import AgentRegistry

    row = AgentRegistry(
        name="Pdf Hire", category="Operations",
        module_path="operations.documents", class_name="PdfHire",
        status="intern", user_id="u-1",
    )
    svc.db.add(row)
    svc.db.commit()
    return row.id


def _gate(outcome: str):
    return {
        "topic": "pdf_canvas",
        "mode": "auto_if_mature",
        "outcome": outcome,
        "reason": f"test gate -> {outcome}",
    }


@pytest.fixture
def propose_gate():
    with patch.object(tool_mod, "gate_for_topic", return_value=_gate("propose")):
        yield


@pytest.fixture
def execute_gate():
    with patch.object(tool_mod, "gate_for_topic", return_value=_gate("execute")):
        yield


# ── lifecycle state machine ──────────────────────────────────────────────


def test_lifecycle_transitions_and_immutability(svc, canvas):
    assert svc.get_state(canvas, "u-1")["state"]["lifecycle"]["state"] == "drafting"

    assert svc.transition(canvas, "u-1", "submit_review")["success"]
    assert svc.get_state(canvas, "u-1")["state"]["lifecycle"]["state"] == "in_review"

    approved = svc.transition(canvas, "u-1", "approve")
    assert approved["success"]
    assert approved["state"]["lifecycle"]["state"] == "approved"
    assert approved["state"]["lifecycle"]["approved_by"] == "user:u-1"

    # approved = immutable: page ops refuse with the immutable signal
    blocked = svc.apply_page_ops(canvas, "u-1", [{"src_index": 0, "rotation": 90}])
    assert blocked["success"] is False and blocked.get("immutable") is True
    blocked_merge = svc.merge_from_canvas(canvas, "u-1", canvas)
    assert blocked_merge.get("immutable") is True

    # reopen is the audited way back; edits work again
    assert svc.transition(canvas, "u-1", "reopen")["success"]
    ok = svc.apply_page_ops(canvas, "u-1", [{"src_index": 0, "rotation": 90}, {"src_index": 1, "rotation": 0}])
    assert ok["success"] is True

    assert svc.transition(canvas, "u-1", "archive")["success"]
    assert svc.get_state(canvas, "u-1")["state"]["lifecycle"]["state"] == "archived"


def test_transition_state_machine(svc, canvas):
    # reopen only from approved
    assert svc.transition(canvas, "u-1", "reopen")["success"] is False
    # submit_review only from drafting
    svc.transition(canvas, "u-1", "submit_review")
    assert svc.transition(canvas, "u-1", "submit_review")["success"] is False
    # unknown transition
    assert svc.transition(canvas, "u-1", "bless")["success"] is False
    # double-approve is refused
    svc.transition(canvas, "u-1", "approve")
    assert svc.transition(canvas, "u-1", "approve")["success"] is False


# ── maturity-gated tools ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_gate_applies_directly(session_ctx, canvas, agent, execute_gate):
    state = session_ctx.query.__self__ if False else None  # noqa: F841 (session via svc)
    from core.models import AgentProposal

    from core.pdf_canvas_service import PdfCanvasService

    svc = PdfCanvasService(session_ctx)
    before = svc.get_state(canvas, "u-1")["state"]["file"]["hash"]

    result = await tool_mod.pdf_canvas_apply_page_ops(
        "u-1", canvas,
        [{"src_index": 1, "rotation": 0}, {"src_index": 0, "rotation": 90}],
        base_hash=before, agent_id=agent,
    )
    assert result["success"] is True
    assert result["state"]["file"]["hash"] != before
    assert session_ctx.query(AgentProposal).count() == 0
    # agent attribution landed on the audit trail
    assert result["state"]["versions"][-1]["author"] == f"agent:{agent}"


@pytest.mark.asyncio
async def test_propose_gate_files_proposal_and_approval_executes(session_ctx, canvas, agent, propose_gate):
    from core.models import AgentProposal

    from core.pdf_canvas_service import PdfCanvasService
    from core.proposal_service import ProposalService

    svc = PdfCanvasService(session_ctx)
    before = svc.get_state(canvas, "u-1")["state"]["file"]["hash"]

    result = await tool_mod.pdf_canvas_apply_page_ops(
        "u-1", canvas, [{"src_index": 1, "rotation": 0}], base_hash=before,
        reasoning="drop the signature page", agent_id=agent,
    )
    assert result["success"] is False and result["needs_approval"] is True
    proposal_id = result["proposal_id"]
    assert proposal_id

    row = session_ctx.query(AgentProposal).filter(AgentProposal.id == proposal_id).one()
    assert row.status == "pending_approval"
    assert row.proposal_data["action_type"] == "pdf_canvas_edit"
    assert row.proposal_data["op"] == "page_ops"
    assert row.proposal_data["pages"] == [{"src_index": 1, "rotation": 0}]

    # human approves → the stored op executes through the real service path
    execution = await ProposalService(session_ctx).approve_proposal(proposal_id, "human-1")
    assert execution["success"] is True
    after = svc.get_state(canvas, "u-1")["state"]
    assert after["file"]["page_count"] == 1
    assert after["file"]["hash"] != before


@pytest.mark.asyncio
async def test_intern_approve_downgrades_to_proposal_even_with_passing_gate(
    session_ctx, canvas, agent, execute_gate,
):
    """The maturity rule for approval: approve is a SUPERVISED act. An INTERN
    with a passing topic gate still only PROPOSES the approval — a human
    confirms. (Page edits, one tier lower, execute directly.)"""
    from core.models import AgentProposal

    from core.pdf_canvas_service import PdfCanvasService
    from core.proposal_service import ProposalService

    svc = PdfCanvasService(session_ctx)
    result = await tool_mod.pdf_canvas_approve("u-1", canvas, reasoning="looks complete", agent_id=agent)
    assert result["needs_approval"] is True and result["proposal_id"]
    row = session_ctx.query(AgentProposal).filter(AgentProposal.id == result["proposal_id"]).one()
    assert row.proposal_data["op"] == "approve"

    # the human confirms → the transition executes
    await ProposalService(session_ctx).approve_proposal(result["proposal_id"], "human-1")
    assert svc.get_state(canvas, "u-1")["state"]["lifecycle"]["state"] == "approved"
    assert svc.get_state(canvas, "u-1")["state"]["lifecycle"]["approved_by"] == f"agent:{agent}"


@pytest.mark.asyncio
async def test_supervised_hire_approves_directly(session_ctx, canvas, agent, execute_gate):
    from core.models import AgentRegistry, AgentProposal

    from core.pdf_canvas_service import PdfCanvasService

    svc = PdfCanvasService(session_ctx)
    svc.db.query(AgentRegistry).filter(AgentRegistry.id == agent).update({"status": "supervised"})
    svc.db.commit()

    result = await tool_mod.pdf_canvas_approve("u-1", canvas, agent_id=agent)
    assert result["success"] is True
    assert session_ctx.query(AgentProposal).count() == 0
    assert svc.get_state(canvas, "u-1")["state"]["lifecycle"]["state"] == "approved"


@pytest.mark.asyncio
async def test_student_hire_proposes_for_teaching(session_ctx, canvas, propose_gate):
    """A STUDENT hire CAN be asked to propose — proposing is the teaching
    loop: the proposal is tagged for training, and the human's
    approve/correct/reject outcome feeds the hire's learning."""
    from core.models import AgentProposal, AgentRegistry

    from core.pdf_canvas_service import PdfCanvasService
    from core.proposal_service import ProposalService

    svc = PdfCanvasService(session_ctx)
    student = AgentRegistry(
        name="Student Hire", category="Operations",
        module_path="operations.documents", class_name="StudentHire",
        status="student", user_id="u-1",
    )
    svc.db.add(student)
    svc.db.commit()

    before = svc.get_state(canvas, "u-1")["state"]["file"]["hash"]
    result = await tool_mod.pdf_canvas_apply_page_ops(
        "u-1", canvas, [{"src_index": 0, "rotation": 90}],
        reasoning="learning to rotate pages", agent_id=student.id,
    )
    assert result["success"] is False and result["needs_approval"] is True
    assert result["student_proposal"] is True
    proposal_id = result["proposal_id"]

    row = session_ctx.query(AgentProposal).filter(AgentProposal.id == proposal_id).one()
    assert row.proposal_data["student_proposal"] is True
    assert row.proposal_data["op"] == "page_ops"

    # the human's approval executes the student's proposed edit — and the
    # outcome flows into the training loop (episode + execution result)
    execution = await ProposalService(session_ctx).approve_proposal(proposal_id, "human-1")
    assert execution["success"] is True
    after = svc.get_state(canvas, "u-1")["state"]
    assert after["file"]["hash"] != before

    refreshed = session_ctx.query(AgentProposal).filter(AgentProposal.id == proposal_id).one()
    assert refreshed.status == "executed"


@pytest.mark.asyncio
async def test_operational_hire_cannot_propose(session_ctx, canvas, propose_gate):
    """Bug 8 intent preserved: when the gate says propose (owner pinned the
    topic, or trust/maturity below bar), an operational (SUPERVISED) hire
    must NOT file a proposal — it's refused, fail-closed at the service
    layer. (On a passing gate it would simply execute directly instead.)"""
    from core.models import AgentProposal, AgentRegistry

    from core.pdf_canvas_service import PdfCanvasService

    svc = PdfCanvasService(session_ctx)
    supervised = AgentRegistry(
        name="Ops Hire", category="Operations",
        module_path="operations.documents", class_name="OpsHire",
        status="supervised", user_id="u-1",
    )
    svc.db.add(supervised)
    svc.db.commit()

    result = await tool_mod.pdf_canvas_apply_page_ops(
        "u-1", canvas, [{"src_index": 0, "rotation": 90}], agent_id=supervised.id,
    )
    assert result["success"] is False and result["needs_approval"] is True
    assert "proposal_id" not in result
    assert session_ctx.query(AgentProposal).count() == 0


@pytest.mark.asyncio
async def test_redact_is_a_supervised_act_for_agents(session_ctx, canvas, agent, execute_gate):
    """Redaction is destructive: an INTERN with a passing topic gate still
    only PROPOSES it — the human confirms before content is removed."""
    from core.models import AgentProposal

    from core.pdf_canvas_service import PdfCanvasService

    svc = PdfCanvasService(session_ctx)
    before = svc.get_state(canvas, "u-1")["state"]["file"]["hash"]

    result = await tool_mod.pdf_canvas_redact(
        "u-1", canvas, [{"page": 0, "text": "contract p1"}],
        reasoning="remove the stale page-one footer", agent_id=agent,
    )
    assert result["success"] is False and result["needs_approval"] is True
    row = session_ctx.query(AgentProposal).filter(AgentProposal.id == result["proposal_id"]).one()
    assert row.proposal_data["op"] == "redact"

    # the canvas is untouched until the human approves
    assert svc.get_state(canvas, "u-1")["state"]["file"]["hash"] == before


@pytest.mark.asyncio
async def test_attach_to_email_gated_path(session_ctx, canvas, agent, execute_gate):
    from core.models import AgentRegistry

    from core.pdf_canvas_service import PdfCanvasService

    # attach (like approve) is a SUPERVISED op — promote the hire so the
    # direct path is exercised; the INTERN path files a proposal instead.
    svc = PdfCanvasService(session_ctx)
    svc.db.query(AgentRegistry).filter(AgentRegistry.id == agent).update({"status": "supervised"})
    svc.db.commit()

    result = await tool_mod.pdf_canvas_attach_to_email("u-1", canvas, agent_id=agent)
    assert result["success"] is True
    assert result["created_email_canvas"] is True
    # provenance stamped on the pdf audit trail
    state = svc.get_state(canvas, "u-1")["state"]
    assert state["lifecycle"]["last_attachment"]["hash"] == state["file"]["hash"]
