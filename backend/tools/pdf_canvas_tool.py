"""Agent tools for PDF canvases — governed by agent maturity.

Reads (state/text/versions) are ungated. Write ops (page map, merge) and the
lifecycle (submit for review, APPROVE, attach-to-email) flow through the
``pdf_canvas`` autonomy topic: the gate outcome (owner mode × governance
maturity × skill-scoped trust) decides between

- ``execute``  — the mature hire acts directly (still audited + attributed);
- ``propose``  — an INTERN hire files an AgentProposal (action_type
  ``pdf_canvas_edit``) that a human approves/rejects in the Journey panel;
  on approval ProposalService executes the stored op through the SAME
  PdfCanvasService path a human click uses.

Approval specifically is maturity-tiered: the tool is registered SUPERVISED,
so only operational hires see it; an INTERN that reaches it can only propose
the approval — a human confirms. That is the "review and approval follow
agent maturity" rule.

PDF text returned to the model is UNTRUSTED retrieved data — wrapped in the
same spotlight delimiters as email-attachment reads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.autonomy_policy import OUTCOME_PROPOSE, gate_for_topic
from core.chat_session_context import audit_agent_id

logger = logging.getLogger(__name__)

_MAX_EXTRACT_CHARS = 20_000


def _acting_agent_id(agent_id: Optional[str]) -> Optional[str]:
    return agent_id or audit_agent_id(None)


def _gate(db, user_id: str, agent_id: Optional[str]) -> Dict[str, Any]:
    return gate_for_topic(db, user_id, "pdf_canvas", agent_id)


# Ops whose maturity bar sits ABOVE the topic's intern tier: approving a
# document (it becomes immutable — the version an email quotes), handing it
# to email, DESTRUCTIVE redaction, signing, and external hand-offs
# (archive/DocuSign) are SUPERVISED acts regardless of the topic gate.
_SUPERVISED_OPS = ("approve", "attach_to_email", "redact", "signature",
                   "archive_onedrive", "docusign")
_STATUS_ORDER = {"student": 0, "intern": 1, "supervised": 2, "autonomous": 3}


def _agent_status(db, agent_id: Optional[str]) -> Optional[str]:
    if not agent_id:
        return None
    try:
        from core.models import AgentRegistry

        row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        return str(row.status).lower() if row else None
    except Exception as e:
        logger.debug(f"agent status lookup skipped: {e}")
        return None


def _supervision_shortfall(db, agent_id: Optional[str], op: str) -> Optional[str]:
    """The maturity rule for approval: approve/attach require a SUPERVISED+
    hire even when the topic gate would let an intern execute. Below that the
    op downgrades to a proposal (INTERN) or a refusal naming the earning path
    (STUDENT)."""
    if op not in _SUPERVISED_OPS:
        return None
    status = _agent_status(db, agent_id)
    if status is None:
        return None  # un-attributed call: the topic gate governs alone
    if _STATUS_ORDER.get(status, 0) >= _STATUS_ORDER["supervised"]:
        return None
    return status


def _proposal_status_note(agent_id: Optional[str]) -> str:
    """Why a proposal could(n't) be filed — learning tiers only (STUDENT
    proposes for teaching; INTERN proposes for oversight) per ProposalService."""
    if not agent_id:
        return "No agent attribution on this call, so no proposal was filed."
    try:
        from core.models import AgentRegistry

        with _session() as db:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if agent is None:
            return f"Agent {agent_id} is not registered, so no proposal was filed."
        if str(agent.status).lower() not in ("student", "intern"):
            return (
                f"Agent maturity is '{agent.status}' — operational hires execute "
                "directly instead of proposing."
            )
    except Exception as e:
        logger.debug(f"proposal status note skipped: {e}")
    return ""


def _session():
    from core.database import get_db_session

    return get_db_session()


async def _maybe_propose(
    db,
    user_id: str,
    agent_id: Optional[str],
    canvas_id: str,
    action: Dict[str, Any],
    reasoning: str,
    title: str,
) -> Dict[str, Any]:
    """File an AgentProposal for a gated op. Returns the tool result dict.

    A STUDENT hire's proposal is a TEACHING proposal: the human's
    approve/correct/reject outcome feeds the hire's training loop
    (episodes + corrections in ProposalService)."""
    from core.proposal_service import ProposalService

    try:
        status = _agent_status(db, agent_id)
        if status == "student":
            action = {**action, "student_proposal": True}
        service = ProposalService(db)
        proposal = await service.create_action_proposal(
            intern_agent_id=agent_id,
            trigger_context={"canvas_id": canvas_id, "surface": "pdf_canvas", "agent_status": status},
            proposed_action=action,
            reasoning=reasoning or "Proposed from the PDF canvas tool surface.",
            canvas_id=canvas_id,
            title=title,
        )
        reason = "This PDF action needs human approval — filed as a proposal "
        reason += "in the Journey panel. It executes automatically on approval."
        if status == "student":
            reason += (
                " Teaching proposal: correcting, approving, or rejecting it "
                "feeds this hire's training."
            )
        return {
            "success": False,
            "needs_approval": True,
            "proposal_id": proposal.id,
            "topic": "pdf_canvas",
            "student_proposal": status == "student",
            "reason": reason,
        }
    except PermissionError as e:
        return {
            "success": False,
            "needs_approval": True,
            "topic": "pdf_canvas",
            "reason": f"Approval gate active. {_proposal_status_note(agent_id)} ({e})",
        }
    except ValueError as e:
        return {"success": False, "needs_approval": True, "topic": "pdf_canvas", "reason": str(e)}


async def _gated_write(
    user_id: str,
    canvas_id: str,
    op: str,
    action: Dict[str, Any],
    title: str,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Shared circuit: gate → execute directly, or propose for a human."""
    agent_id = _acting_agent_id(agent_id)
    try:
        with _session() as db:
            gate = _gate(db, user_id, agent_id)
            shortfall = _supervision_shortfall(db, agent_id, op)
            if gate.get("outcome") == OUTCOME_PROPOSE or shortfall:
                if shortfall and gate.get("outcome") != OUTCOME_PROPOSE:
                    # A below-SUPERVISED hire reached an approval-grade op on
                    # a passing topic gate: force the propose path (INTERN
                    # files the proposal; a STUDENT is refused by the
                    # proposal service with the maturity reason).
                    gate = dict(gate, outcome=OUTCOME_PROPOSE,
                                reason=f"Approving/attaching a PDF is a SUPERVISED act — "
                                f"maturity '{shortfall}' proposes for human sign-off.")
                return await _maybe_propose(
                    db, user_id, agent_id, canvas_id,
                    {"action_type": "pdf_canvas_edit", "op": op, "canvas_id": canvas_id, **action},
                    reasoning, title,
                )

            from core.pdf_canvas_service import PdfCanvasService

            svc = PdfCanvasService(db)
            if op == "page_ops":
                result = svc.apply_page_ops(
                    canvas_id, user_id, action.get("pages") or [],
                    base_hash=action.get("base_hash"), agent_id=agent_id,
                )
            elif op == "merge_canvas":
                result = svc.merge_from_canvas(
                    canvas_id, user_id, action.get("from_canvas_id") or "", agent_id=agent_id,
                )
            elif op == "attach_to_email":
                result = svc.attach_to_email(
                    canvas_id, user_id,
                    email_canvas_id=action.get("email_canvas_id"), agent_id=agent_id,
                    flatten=bool(action.get("flatten")),
                )
            elif op == "form":
                result = svc.set_form_fields(
                    canvas_id, user_id, action.get("values") or {},
                    base_hash=action.get("base_hash"), agent_id=agent_id,
                )
            elif op == "flatten":
                result = svc.flatten_form(canvas_id, user_id, agent_id=agent_id)
            elif op == "annotate":
                result = svc.annotate(
                    canvas_id, user_id, action.get("items") or [], agent_id=agent_id,
                )
            elif op == "redact":
                result = svc.redact(
                    canvas_id, user_id, action.get("items") or [], agent_id=agent_id,
                )
            elif op == "signature":
                result = svc.stamp_signature(
                    canvas_id, user_id, int(action.get("page", 0)),
                    action.get("signature_lines") or [], action.get("rect") or [72, 600, 272, 650],
                    label=action.get("label", ""), agent_id=agent_id,
                )
            elif op == "archive_onedrive":
                result = await svc.archive_to_onedrive(
                    canvas_id, user_id,
                    folder_path=action.get("folder_path", ""), agent_id=agent_id,
                )
            elif op == "docusign":
                result = svc.send_to_docusign(
                    canvas_id, user_id,
                    signer_email=action.get("signer_email") or "",
                    signer_name=action.get("signer_name") or "",
                    agent_id=agent_id,
                )
            elif op in ("submit_review", "approve"):
                result = svc.transition(canvas_id, user_id, op, agent_id=agent_id)
            else:
                return {"success": False, "error": f"Unknown pdf_canvas op: {op}"}

        if result.get("success"):
            result["message"] = title.replace("Proposed", "Completed")
        return result
    except Exception as e:
        logger.error(f"pdf_canvas tool op {op} failed: {e}")
        return {"success": False, "error": str(e)}


# ── reads (ungated) ──────────────────────────────────────────────────────


async def pdf_canvas_get_state(user_id: str, canvas_id: str) -> Dict[str, Any]:
    """Read a PDF canvas's state: filename, page count, lifecycle, versions.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id

    Returns:
        {"success", "state": {file, versions, lifecycle}}
    """
    try:
        from core.pdf_canvas_service import PdfCanvasService

        with _session() as db:
            return PdfCanvasService(db).get_state(canvas_id, user_id)
    except Exception as e:
        logger.error(f"pdf_canvas_get_state failed: {e}")
        return {"success": False, "error": str(e)}


async def pdf_canvas_read_text(
    user_id: str,
    canvas_id: str,
    max_chars: int = 8000,
) -> Dict[str, Any]:
    """Read a PDF canvas's per-page TEXT (never raw bytes). Read-only.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        max_chars: Cap on returned text (default 8000)

    Returns:
        {"success", "filename", "pages": [{page, text}], "truncated"}
    """
    try:
        from core.email_policy import spotlight_email_content
        from core.pdf_canvas_service import PdfCanvasService

        with _session() as db:
            result = PdfCanvasService(db).extract_text(canvas_id, user_id)
        if not result.get("success"):
            return result

        joined = []
        for page in result.get("pages") or []:
            label = f"[page {page['page'] + 1}]"
            joined.append(f"{label} {(page.get('text') or '').strip()}")
        text = "\n".join(joined)
        capped = text[: max(1, min(max_chars, _MAX_EXTRACT_CHARS))]
        return {
            "success": True,
            "canvas_id": canvas_id,
            "filename": result.get("filename"),
            "page_count": len(result.get("pages") or []),
            "text": spotlight_email_content(capped),
            "truncated": len(text) > len(capped) or result.get("truncated", False),
        }
    except Exception as e:
        logger.error(f"pdf_canvas_read_text failed: {e}")
        return {"success": False, "error": str(e)}


async def pdf_canvas_list_versions(user_id: str, canvas_id: str) -> Dict[str, Any]:
    """List the version history of a PDF canvas (hash, action, author, time).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id

    Returns:
        {"success", "versions": [...], "lifecycle": {...}}
    """
    try:
        from core.pdf_canvas_service import PdfCanvasService

        with _session() as db:
            result = PdfCanvasService(db).get_state(canvas_id, user_id)
        if result.get("success"):
            state = result["state"]
            return {
                "success": True,
                "canvas_id": canvas_id,
                "versions": state.get("versions", []),
                "lifecycle": state.get("lifecycle", {}),
            }
        return result
    except Exception as e:
        logger.error(f"pdf_canvas_list_versions failed: {e}")
        return {"success": False, "error": str(e)}


# ── writes (maturity-gated) ──────────────────────────────────────────────


async def pdf_canvas_apply_page_ops(
    user_id: str,
    canvas_id: str,
    pages: list,
    base_hash: Optional[str] = None,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Commit a page map (reorder/delete/rotate) to a PDF canvas.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        pages: [{"src_index": int, "rotation": 0|90|180|270}] — full map;
            order = page order, omission = delete, rotation = absolute degrees
        base_hash: Version hash the map was computed against (conflict guard)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)

    Returns:
        {"success", "state"} or {"needs_approval", "proposal_id"}
    """
    return await _gated_write(
        user_id, canvas_id, "page_ops",
        {"pages": pages, "base_hash": base_hash},
        title=f"PDF page edit on canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_merge_canvas(
    user_id: str,
    canvas_id: str,
    from_canvas_id: str,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append every page of another PDF canvas onto this one.

    Args:
        user_id: Owning user id
        canvas_id: Target PDF canvas id
        from_canvas_id: Source PDF canvas id (same owner)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "merge_canvas",
        {"from_canvas_id": from_canvas_id},
        title=f"PDF merge into canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_submit_for_review(
    user_id: str,
    canvas_id: str,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Move a PDF canvas from drafting to in_review (requests approval).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "submit_review", {},
        title=f"Submit PDF canvas {canvas_id[:8]} for review",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_approve(
    user_id: str,
    canvas_id: str,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve a PDF canvas (drafting/in_review → approved, content becomes
    immutable). Maturity-tiered: SUPERVISED+ hires with a passing gate
    approve directly; anyone else files a proposal a human confirms.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "approve", {},
        title=f"Approve PDF canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_attach_to_email(
    user_id: str,
    canvas_id: str,
    email_canvas_id: Optional[str] = None,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Stage the current PDF version onto an email draft (a new draft when
    none is named). The SEND itself still runs the email-send HITL circuit.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        email_canvas_id: Target email canvas (omit to create a fresh draft)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "attach_to_email",
        {"email_canvas_id": email_canvas_id},
        title=f"Attach PDF canvas {canvas_id[:8]} to email",
        reasoning=reasoning, agent_id=agent_id,
    )


# ── P3: trust operations ─────────────────────────────────────────────────


async def pdf_canvas_get_form_fields(user_id: str, canvas_id: str) -> Dict[str, Any]:
    """List the AcroForm fields of a PDF canvas (name, type, current value).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id

    Returns:
        {"success", "fields": {name: {type, value}}}
    """
    try:
        from core.pdf_canvas_service import PdfCanvasService

        with _session() as db:
            return PdfCanvasService(db).get_form_fields(canvas_id, user_id)
    except Exception as e:
        logger.error(f"pdf_canvas_get_form_fields failed: {e}")
        return {"success": False, "error": str(e)}


async def pdf_canvas_set_form_fields(
    user_id: str,
    canvas_id: str,
    values: Dict[str, Any],
    base_hash: Optional[str] = None,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fill AcroForm field values (fields stay interactive until flattened).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        values: {field_name: value} — unknown names are refused
        base_hash: Version hash the values were read against (conflict guard)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "form", {"values": values, "base_hash": base_hash},
        title=f"Fill form fields on canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_flatten(
    user_id: str,
    canvas_id: str,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Burn form values into the page content and strip the interactive
    layer (cross-viewer-safe output; the previous version stays restorable).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "flatten", {},
        title=f"Flatten form on canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_annotate(
    user_id: str,
    canvas_id: str,
    items: list,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add real PDF annotations (note/freetext/rect).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        items: [{page, kind: note|freetext|rect, rect: [x0,y0,x1,y1], text?}]
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "annotate", {"items": items},
        title=f"Annotate canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_redact(
    user_id: str,
    canvas_id: str,
    items: list,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """TRUE redaction: permanently remove exact text from the document
    (content-stream removal + verification — never a black box). SUPERVISED
    act: an INTERN proposes, a human confirms. Refuses unless EVERY target
    is verifiably removed.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        items: [{page, text}] — exact text to remove per page
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "redact", {"items": items},
        title=f"REDACT text on canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_stamp_signature(
    user_id: str,
    canvas_id: str,
    signature_lines: list,
    page: int = 0,
    rect: Optional[list] = None,
    label: str = "",
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Stamp the internal signature (text lines + attribution) on a page.
    Visual approval stamp; external cryptographic signing → DocuSign.

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        signature_lines: The signer's signature text lines
        page: 0-based page index (default 0)
        rect: [x0, y0, x1, y1] PDF coordinates (default bottom-left block)
        label: Attribution line under the signature (e.g. date + name)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "signature",
        {"signature_lines": signature_lines, "page": page,
         "rect": rect or [72, 600, 272, 650], "label": label},
        title=f"Sign canvas {canvas_id[:8]}",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_generate_from_data(
    user_id: str,
    template: str,
    doc: Dict[str, Any],
    title: str = "",
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a NEW PDF canvas from structured business data (template:
    quote | invoice | letter; doc: {company, customer, items: [{description,
    amount}], body}).

    Args:
        user_id: Owning user id
        template: quote | invoice | letter
        doc: The document data
        title: Canvas/PDF title (also becomes the filename)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    agent_id = _acting_agent_id(agent_id)
    try:
        with _session() as db:
            gate = _gate(db, user_id, agent_id)
            if gate.get("outcome") == OUTCOME_PROPOSE:
                return await _maybe_propose(
                    db, user_id, agent_id, canvas_id="",
                    action={"action_type": "pdf_canvas_edit", "op": "generate",
                            "template": template, "doc": doc, "title": title},
                    reasoning=reasoning, title=f"Generate {template}: {title or 'untitled'}",
                )

            from core.pdf_canvas_service import PdfCanvasService

            result = PdfCanvasService(db).generate(
                user_id=user_id, tenant_id="default", template=template,
                doc=doc, title=title, agent_id=agent_id,
            )
        if result.get("success"):
            result["message"] = f"Generated {template} canvas {result['canvas_id'][:8]}"
        return result
    except Exception as e:
        logger.error(f"pdf_canvas_generate_from_data failed: {e}")
        return {"success": False, "error": str(e)}


# ── P4: sign & archive ───────────────────────────────────────────────────


async def pdf_canvas_archive_to_onedrive(
    user_id: str,
    canvas_id: str,
    folder_path: str = "",
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Archive the current version to the owner's OneDrive (Microsoft
    umbrella grant; the reference is stamped on the audit trail).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        folder_path: OneDrive folder (root when empty)
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "archive_onedrive", {"folder_path": folder_path},
        title=f"Archive canvas {canvas_id[:8]} to OneDrive",
        reasoning=reasoning, agent_id=agent_id,
    )


async def pdf_canvas_send_to_docusign(
    user_id: str,
    canvas_id: str,
    signer_email: str,
    signer_name: str,
    reasoning: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Send the current version out for EXTERNAL cryptographic signing via
    DocuSign (env-configured; a clean 'not configured' result otherwise).

    Args:
        user_id: Owning user id
        canvas_id: PDF canvas id
        signer_email: External signer's email
        signer_name: External signer's name
        reasoning: Why — shown to the human when a proposal is filed
        agent_id: Calling agent id (audit + maturity gate)
    """
    return await _gated_write(
        user_id, canvas_id, "docusign",
        {"signer_email": signer_email, "signer_name": signer_name},
        title=f"DocuSign canvas {canvas_id[:8]} for {signer_name}",
        reasoning=reasoning, agent_id=agent_id,
    )
