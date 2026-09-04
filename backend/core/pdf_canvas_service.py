"""PDF canvas service — load, edit, and hand off to email.

State model follows the email canvas: the latest CanvasAudit row with
canvas_type="pdf" IS the canvas (details_json["content"] carries the full
state), so the generic /api/canvas/{id} read, the /history + /restore
endpoints, and the chat co-editor all work without a parallel store. File
bytes never live in the audit row — they sit content-addressed in
core.pdf_canvas_store and the state references them by sha256.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from core import pdf_engine
from core.models import Canvas, CanvasAudit
from core.pdf_canvas_store import read_blob, save_blob

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPE = "application/pdf"
# Defensive read-back cap for extract_text (a 2000-page scan must not block
# a request thread).
MAX_EXTRACT_PAGES = 50


def _audit_now():
    """Microsecond client-side timestamp — same-second audit rows tie on the
    SECOND-precision server default and the latest-state lookup becomes
    nondeterministic (see canvas_email_service._audit_now)."""
    return datetime.now(timezone.utc)


class PdfCanvasService:
    def __init__(self, db: Session):
        self.db = db

    # ── state helpers ────────────────────────────────────────────────────

    def _latest_pdf_audit(self, canvas_id: str) -> Optional[CanvasAudit]:
        return (
            self.db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id, CanvasAudit.canvas_type == "pdf")
            .order_by(desc(CanvasAudit.created_at))
            .first()
        )

    def _canvas_owner_id(self, canvas_id: str) -> Optional[str]:
        first = (
            self.db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id, CanvasAudit.canvas_type == "pdf")
            .order_by(CanvasAudit.created_at.asc())
            .first()
        )
        return first.user_id if first else None

    def _require_owner(self, canvas_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """The canvas's latest state + owner check in one query pass. Returns
        None-shaped errors the way canvas_email_service does."""
        if self._canvas_owner_id(canvas_id) != user_id:
            return {"success": False, "error": "Not the canvas owner"}
        audit = self._latest_pdf_audit(canvas_id)
        if not audit:
            return {"success": False, "error": "PDF canvas not found"}
        state = (audit.details_json or {}).get("content")
        if not isinstance(state, dict) or "file" not in state:
            return {"success": False, "error": "PDF canvas state is missing or corrupt"}
        return state

    def _append_state(
        self,
        canvas_id: str,
        user_id: str,
        agent_id: Optional[str],
        state: Dict[str, Any],
        action_type: str,
        title: Optional[str] = None,
        **extra: Any,
    ) -> CanvasAudit:
        audit = CanvasAudit(
            id=str(uuid.uuid4()),
            created_at=_audit_now(),
            tenant_id="default",
            agent_id=agent_id,
            user_id=user_id,
            canvas_id=canvas_id,
            action_type=action_type,
            canvas_type="pdf",
            details_json={"canvas_type": "pdf", "content": state, **extra},
        )
        if title:
            audit.details_json["title"] = title
        self.db.add(audit)
        self.db.commit()
        return audit

    def _broadcast(self, user_id: str, canvas_id: str, state: Dict[str, Any], title: Optional[str]) -> None:
        """canvas:update on both channels (canvas page + user panel) so the
        co-editing loop sees every mutation — same best-effort pattern as
        canvas_email_service.record_send (a broadcast failure never breaks
        the write, and outside a running loop the task creation is skipped)."""
        try:
            import asyncio

            from core.websockets import manager as ws_manager

            message = {
                "type": "canvas:update",
                "data": {
                    "action": "update",
                    "canvas_id": canvas_id,
                    "canvas_type": "pdf",
                    "component": "pdf",
                    "data": state,
                    "title": title,
                },
            }
            for channel in (f"canvas:{canvas_id}", f"user:{user_id}"):
                try:
                    asyncio.create_task(ws_manager.broadcast(channel, dict(message)))
                except Exception:
                    pass
        except Exception as e:  # broadcast never breaks a write
            logger.debug(f"PDF canvas broadcast failed: {e}")

    # ── lifecycle ────────────────────────────────────────────────────────

    def create_pdf_canvas(
        self,
        user_id: str,
        tenant_id: str = "default",
        title: Optional[str] = None,
        filename: Optional[str] = None,
        content_bytes: Optional[bytes] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create from an upload, or a blank single-page canvas when no bytes
        are given. The creating user owns it (Canvas.created_by is the
        authoritative owner check for every later read/write)."""
        try:
            if content_bytes is not None:
                if not content_bytes:
                    return {"success": False, "error": "uploaded file is empty"}
                info = pdf_engine.load_info(content_bytes)
                fname = filename or "document.pdf"
                source = "upload"
            else:
                content_bytes = pdf_engine.blank_pdf(title or "")
                info = pdf_engine.load_info(content_bytes)
                fname = filename or "document.pdf"
                source = "blank"

            canvas_id = str(uuid.uuid4())
            blob_hash = save_blob(user_id, canvas_id, content_bytes)
            now = datetime.now(timezone.utc).isoformat()
            state = {
                "file": {
                    "hash": blob_hash,
                    "page_count": info["page_count"],
                    "size_bytes": len(content_bytes),
                    "filename": fname,
                },
                "versions": [
                    {
                        "hash": blob_hash,
                        "action": "create",
                        "author": f"agent:{agent_id}" if agent_id else f"user:{user_id}",
                        "at": now,
                    }
                ],
                "lifecycle": {"state": "drafting", "approved_by": None, "approved_at": None},
                "source": source,
            }

            # Canvas row: NOT NULL FK target for every audit row + the
            # authoritative owner (canvas_crud_tool._verify_canvas_owner).
            self.db.add(Canvas(
                id=canvas_id,
                tenant_id=tenant_id or "default",
                created_by=user_id,
                name=title or fname,
                canvas_type="pdf",
                status="active",
            ))
            self._append_state(canvas_id, user_id, agent_id, state, "create", title=title or fname)
            logger.info(f"Created pdf canvas {canvas_id}: {fname} ({info['page_count']} pages)")
            return {"success": True, "canvas_id": canvas_id, "state": state}
        except pdf_engine.PdfEngineError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Failed to create pdf canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    # ── edits ────────────────────────────────────────────────────────────

    _MUTABLE_STATES = ("drafting", "in_review")

    def _check_mutable(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Approved-and-beyond documents are immutable (playbook pattern):
        edits must reopen the canvas first — never silently fork an approved
        artifact, because the approved version may already be quoted in an
        outbound email."""
        if state.get("lifecycle", {}).get("state") not in self._MUTABLE_STATES:
            return {
                "success": False,
                "immutable": True,
                "error": (
                    "This PDF is approved and immutable — reopen it to edit "
                    "(a reopen is itself audited)"
                ),
            }
        return None

    def apply_page_ops(
        self,
        canvas_id: str,
        user_id: str,
        pages: List[Dict[str, int]],
        base_hash: Optional[str] = None,
        agent_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Materialize the user/agent's page map (reorder + delete + rotate)
        as a new immutable version. base_hash is the optimistic-concurrency
        guard: a save computed against a stale version is refused with a
        conflict so two co-editors can't silently drop each other's pages."""
        return self._mutate_bytes(
            canvas_id, user_id, "page_ops",
            lambda data: pdf_engine.build_pages(data, pages),
            agent_id=agent_id, base_hash=base_hash, title=title,
        )

    def _mutate_bytes(
        self,
        canvas_id: str,
        user_id: str,
        action: str,
        transform,
        agent_id: Optional[str] = None,
        base_hash: Optional[str] = None,
        title: Optional[str] = None,
        allow_conflict: bool = False,
        extra_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Shared circuit for every content mutation: owner + immutability +
        conflict checks → deterministic engine transform → new content-
        addressed version → audit row → broadcast."""
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        immutable = self._check_mutable(state)
        if immutable:
            return immutable
        current_hash = state["file"]["hash"]
        if base_hash and base_hash != current_hash:
            return {
                "success": False,
                "error": "version conflict: the document changed since it was loaded — reload and retry",
                "conflict": True,
                "current_hash": current_hash,
            }

        data = read_blob(user_id, canvas_id, current_hash)
        if data is None:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}
        try:
            new_bytes = transform(data)
            info = pdf_engine.load_info(new_bytes)
        except pdf_engine.PdfEngineError as e:
            return {"success": False, "error": str(e)}

        new_hash = save_blob(user_id, canvas_id, new_bytes)
        state["file"] = {
            "hash": new_hash,
            "page_count": info["page_count"],
            "size_bytes": len(new_bytes),
            "filename": state["file"].get("filename") or "document.pdf",
        }
        state["versions"].append({
            "hash": new_hash,
            "action": action,
            "author": f"agent:{agent_id}" if agent_id else f"user:{user_id}",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self._append_state(canvas_id, user_id, agent_id, state, f"pdf_{action}",
                           base_hash=base_hash, title=title)
        self._broadcast(user_id, canvas_id, state, title)
        result = {"success": True, "state": state}
        if extra_result:
            result.update(extra_result)
        return result

    # ── trust operations (P3) — same versioned circuit ───────────────────

    def get_form_fields(self, canvas_id: str, user_id: str) -> Dict[str, Any]:
        """Field inventory of the current version (fill UI / agent read-back)."""
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        data = read_blob(user_id, canvas_id, state["file"]["hash"])
        if data is None:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}
        try:
            return {"success": True, "fields": pdf_engine.get_form_fields(data)}
        except pdf_engine.PdfEngineError as e:
            return {"success": False, "error": str(e)}

    def set_form_fields(self, canvas_id: str, user_id: str, values: Dict[str, Any],
                        base_hash: Optional[str] = None, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Fill AcroForm values (fields stay interactive until flattened)."""
        return self._mutate_bytes(
            canvas_id, user_id, "form_fill",
            lambda data: pdf_engine.set_form_fields(data, values),
            agent_id=agent_id, base_hash=base_hash,
        )

    def flatten_form(self, canvas_id: str, user_id: str,
                     agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Burn form values into the content and strip the interactive layer."""
        return self._mutate_bytes(
            canvas_id, user_id, "form_flatten",
            pdf_engine.flatten_form,
            agent_id=agent_id,
        )

    def annotate(self, canvas_id: str, user_id: str, items: List[Dict[str, Any]],
                 agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Add real PDF annotations (note/freetext/rect)."""
        return self._mutate_bytes(
            canvas_id, user_id, "annotate",
            lambda data: pdf_engine.annotate(data, items),
            agent_id=agent_id,
        )

    def redact(self, canvas_id: str, user_id: str, items: List[Dict[str, Any]],
               agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Content-level redaction with mandatory verification. `failed`
        items (not locatable in the content stream) come back to the caller —
        a partial redaction is surfaced, never silently accepted."""
        def transform(data: bytes) -> bytes:
            outcome = pdf_engine.redact(data, items)
            if outcome["failed"]:
                # message deliberately ≠ "PDF canvas not found" (the 404
                # phrase) — a redaction miss is a 400 policy refusal
                raise pdf_engine.PdfEngineError(
                    "redaction target not found in content stream: "
                    + "; ".join(f"p{f['page'] + 1}:{f['text'][:30]}" for f in outcome["failed"])
                )
            return outcome["bytes"]

        return self._mutate_bytes(
            canvas_id, user_id, "redact", transform, agent_id=agent_id,
        )

    def stamp_signature(self, canvas_id: str, user_id: str, page_no: int,
                        signature_lines: List[str], rect: List[float], label: str = "",
                        agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Internal signing stamp (script-style signature + attribution)."""
        return self._mutate_bytes(
            canvas_id, user_id, "signature",
            lambda data: pdf_engine.stamp_signature(data, page_no, signature_lines, rect, label),
            agent_id=agent_id,
        )

    def generate(
        self,
        user_id: str,
        tenant_id: str,
        template: str,
        doc: Dict[str, Any],
        title: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a PDF canvas from structured business data (quote/invoice/
        letter) — the outbound-generation half of the lifecycle."""
        try:
            content_bytes = pdf_engine.generate_document(template, doc, title or "")
        except pdf_engine.PdfEngineError as e:
            return {"success": False, "error": str(e)}
        return self.create_pdf_canvas(
            user_id=user_id, tenant_id=tenant_id,
            title=title, filename=f"{(title or template).strip()}.pdf",
            content_bytes=content_bytes, agent_id=agent_id,
        )

    async def extract_text_ocr(self, canvas_id: str, user_id: str) -> Dict[str, Any]:
        """Text with OCR fallback: pages with no text layer (scans) go
        through DocumentParser (Docling) instead of coming back empty."""
        result = self.extract_text(canvas_id, user_id)
        if not result.get("success"):
            return result
        if any((p.get("text") or "").strip() for p in result.get("pages", [])):
            return result

        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        data = read_blob(user_id, canvas_id, state["file"]["hash"])
        if data is None:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}
        try:
            from core.auto_document_ingestion import DocumentParser

            text = await DocumentParser().parse_document(
                data, "pdf", state["file"].get("filename") or "document.pdf"
            )
        except Exception as e:
            return {"success": False, "error": f"OCR fallback failed: {e}"}
        if not text:
            return {**result, "ocr": False,
                    "note": "no text layer and OCR produced nothing (empty or image-only scan)"}
        return {
            "success": True,
            "filename": state["file"].get("filename"),
            "hash": state["file"]["hash"],
            "pages": [{"page": 0, "text": text[:20000]}],
            "ocr": True,
            "truncated": False,
        }

    def merge_upload(
        self,
        canvas_id: str,
        user_id: str,
        filename: str,
        content_bytes: bytes,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append every page of an uploaded PDF after the current pages."""
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        immutable = self._check_mutable(state)
        if immutable:
            return immutable
        return self._merge_bytes(canvas_id, user_id, state, filename, content_bytes, agent_id)

    def merge_from_canvas(
        self,
        canvas_id: str,
        user_id: str,
        from_canvas_id: str,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append every page of another PDF canvas the same user owns."""
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        immutable = self._check_mutable(state)
        if immutable:
            return immutable
        source_state = self._require_owner(from_canvas_id, user_id)
        if "success" in source_state:
            return {"success": False, "error": f"source canvas unavailable: {source_state['error']}"}
        source_bytes = read_blob(user_id, from_canvas_id, source_state["file"]["hash"])
        if source_bytes is None:
            return {"success": False, "error": "stored PDF bytes are missing for the source canvas"}
        filename = source_state["file"].get("filename") or "merged.pdf"
        return self._merge_bytes(canvas_id, user_id, state, filename, source_bytes, agent_id,
                                 from_canvas_id=from_canvas_id)

    def _merge_bytes(
        self,
        canvas_id: str,
        user_id: str,
        state: Dict[str, Any],
        filename: str,
        source_bytes: bytes,
        agent_id: Optional[str],
        from_canvas_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            source_info = pdf_engine.load_info(source_bytes)
            new_bytes = pdf_engine.append_pdf(
                read_blob(user_id, canvas_id, state["file"]["hash"]) or b"", source_bytes
            )
            info = pdf_engine.load_info(new_bytes)
        except pdf_engine.PdfEngineError as e:
            return {"success": False, "error": str(e)}
        if info["page_count"] == state["file"]["page_count"]:
            return {"success": False, "error": f"merge produced no new pages ({source_info['page_count']} in source)"}

        new_hash = save_blob(user_id, canvas_id, new_bytes)
        state["file"] = {
            "hash": new_hash,
            "page_count": info["page_count"],
            "size_bytes": len(new_bytes),
            "filename": state["file"].get("filename") or "document.pdf",
        }
        state["versions"].append({
            "hash": new_hash,
            "action": f"merge{'_canvas' if from_canvas_id else '_upload'}",
            "author": f"agent:{agent_id}" if agent_id else f"user:{user_id}",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self._append_state(canvas_id, user_id, agent_id, state, "pdf_merge",
                           source=filename, from_canvas_id=from_canvas_id)
        self._broadcast(user_id, canvas_id, state, None)
        return {"success": True, "state": state}

    # ── read-back ────────────────────────────────────────────────────────

    def get_state(self, canvas_id: str, user_id: str) -> Dict[str, Any]:
        """Public state read for tools/routes (owner-checked)."""
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        return {"success": True, "canvas_id": canvas_id, "state": state}

    def get_bytes(self, canvas_id: str, user_id: str, content_hash_hex: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Resolve the current (or a named) version to raw bytes for streaming."""
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return None
        h = content_hash_hex or state["file"]["hash"]
        data = read_blob(user_id, canvas_id, h)
        if data is None:
            return None
        return {"bytes": data, "hash": h, "state": state}

    def extract_text(self, canvas_id: str, user_id: str) -> Dict[str, Any]:
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        data = read_blob(user_id, canvas_id, state["file"]["hash"])
        if data is None:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}
        try:
            pages = pdf_engine.extract_text(data, max_pages=MAX_EXTRACT_PAGES)
        except pdf_engine.PdfEngineError as e:
            return {"success": False, "error": str(e)}
        return {
            "success": True,
            "filename": state["file"].get("filename"),
            "hash": state["file"]["hash"],
            "pages": pages,
            "truncated": state["file"]["page_count"] > len(pages),
        }

    # ── lifecycle transitions ────────────────────────────────────────────

    _TRANSITIONS: Dict[str, Dict[str, Any]] = {
        "submit_review": {"from": ("drafting",), "to": "in_review", "action": "pdf_submit_review"},
        "approve": {"from": ("drafting", "in_review"), "to": "approved", "action": "pdf_approve"},
        "reopen": {"from": ("approved",), "to": "drafting", "action": "pdf_reopen"},
        # archive is the cleanup path — reachable from any state (a dead
        # draft is archivable, not just approved work).
        "archive": {
            "from": ("drafting", "in_review", "approved", "archived"),
            "to": "archived",
            "action": "pdf_archive",
        },
    }

    def transition(
        self,
        canvas_id: str,
        user_id: str,
        transition_name: str,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lifecycle move (drafting → in_review → approved → archived, plus
        reopen). The caller (route or agent tool) enforces WHO may approve —
        this method only enforces the state machine and audits the move.
        Approved canvases are immutable; reopen is the audited way back."""
        spec = self._TRANSITIONS.get(transition_name)
        if not spec:
            return {"success": False, "error": f"Unknown lifecycle transition: {transition_name}"}
        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        current = state.get("lifecycle", {}).get("state") or "drafting"
        if current not in spec["from"]:
            return {
                "success": False,
                "error": f"Cannot {transition_name.replace('_', ' ')} from '{current}' "
                f"(allowed from: {', '.join(spec['from'])})",
            }

        state["lifecycle"]["state"] = spec["to"]
        if spec["to"] == "approved":
            state["lifecycle"]["approved_by"] = f"agent:{agent_id}" if agent_id else f"user:{user_id}"
            state["lifecycle"]["approved_at"] = datetime.now(timezone.utc).isoformat()
        if spec["to"] == "drafting":
            state["lifecycle"]["approved_by"] = None
            state["lifecycle"]["approved_at"] = None
        state["versions"].append({
            "hash": state["file"]["hash"],
            "action": transition_name,
            "author": f"agent:{agent_id}" if agent_id else f"user:{user_id}",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self._append_state(canvas_id, user_id, agent_id, state, spec["action"],
                           from_state=current, to_state=spec["to"])
        self._broadcast(user_id, canvas_id, state, None)
        return {"success": True, "state": state}

    # ── handoff to email ─────────────────────────────────────────────────

    def attach_to_email(
        self,
        canvas_id: str,
        user_id: str,
        email_canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        flatten: bool = False,
    ) -> Dict[str, Any]:
        """Stage the current version onto an email canvas (a new draft one when
        none is named) via the EXISTING staged-attachment path — the email
        side's send policy, caps, and audit stay the only send mechanism.

        flatten=True stages a FLATTENED COPY (form values burned in, no
        interactive layer — cross-viewer-safe) without mutating the canvas:
        the canvas keeps its editable version; the email carries the frozen
        one. Provenance records whether flattening happened.

        Provenance is stamped on the PDF canvas's own audit trail
        (pdf_attached_to_email → email_canvas_id + attachment_id + version
        hash), so "which PDF version went out with that email" is answerable
        from either side of the chain."""
        from core.canvas_email_service import EmailCanvasService

        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        resolved = self.get_bytes(canvas_id, user_id)
        if not resolved:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}

        staging_bytes = resolved["bytes"]
        if flatten:
            try:
                staging_bytes = pdf_engine.flatten_form(staging_bytes)
            except pdf_engine.PdfEngineError as e:
                return {"success": False, "error": f"flatten failed: {e}"}

        email_service = EmailCanvasService(self.db)
        created_email = False
        if not email_canvas_id:
            filename = state["file"].get("filename") or "document.pdf"
            subject = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip() or "Document"
            created = email_service.create_email_canvas(user_id=user_id, subject=subject, recipients=[])
            if not created.get("success"):
                return {"success": False, "error": created.get("error", "Failed to create email canvas")}
            email_canvas_id = created["canvas_id"]
            created_email = True

        staged = email_service.stage_attachments(
            email_canvas_id,
            user_id,
            [{
                "filename": state["file"].get("filename") or "document.pdf",
                "content_bytes": staging_bytes,
                "content_type": PDF_CONTENT_TYPE,
            }],
            agent_id=agent_id,
        )
        if not staged.get("success"):
            return {"success": False, "error": staged.get("error", "Failed to stage attachment")}

        attachment = (staged.get("attachments") or [{}])[0]
        state["lifecycle"]["last_attachment"] = {
            "email_canvas_id": email_canvas_id,
            "attachment_id": attachment.get("attachment_id"),
            "hash": resolved["hash"],
            "flattened": flatten,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self._append_state(
            canvas_id, user_id, agent_id, state, "pdf_attached_to_email",
            email_canvas_id=email_canvas_id,
            attachment_id=attachment.get("attachment_id"),
            version_hash=resolved["hash"],
            flattened=flatten,
        )
        self._broadcast(user_id, canvas_id, state, None)
        logger.info(f"Attached pdf canvas {canvas_id} (hash {resolved['hash'][:12]}, flattened={flatten}) to email canvas {email_canvas_id}")
        return {
            "success": True,
            "email_canvas_id": email_canvas_id,
            "created_email_canvas": created_email,
            "attachment_id": attachment.get("attachment_id"),
            "version_hash": resolved["hash"],
            "filename": state["file"].get("filename"),
            "flattened": flatten,
        }

    async def archive_to_onedrive(
        self,
        canvas_id: str,
        user_id: str,
        folder_path: str = "",
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Archive the current version to the owner's OneDrive (P4 archival
        step; WorkDrive upload + certified PDF/A remain future work). Uses
        the Microsoft umbrella grant — the same token family Outlook uses."""
        from integrations.outlook_service import OutlookService

        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        resolved = self.get_bytes(canvas_id, user_id)
        if not resolved:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}

        token = await OutlookService(self.db)._get_access_token(user_id)
        if not token:
            return {"success": False, "error": "no connected Microsoft account — connect OneDrive/Outlook first"}

        from integrations.onedrive_service import OneDriveService

        result = await OneDriveService().upload_file(
            token, state["file"].get("filename") or "document.pdf",
            resolved["bytes"], folder_path=folder_path,
        )
        success = bool(result.get("success") or result.get("id"))
        state["lifecycle"]["archive_ref"] = {
            "provider": "onedrive",
            "folder": folder_path or "/",
            "hash": resolved["hash"],
            "file_id": result.get("id"),
            "at": datetime.now(timezone.utc).isoformat(),
            "by": f"agent:{agent_id}" if agent_id else f"user:{user_id}",
        }
        self._append_state(canvas_id, user_id, agent_id, state, "pdf_archived",
                           provider="onedrive", version_hash=resolved["hash"],
                           file_id=result.get("id"))
        self._broadcast(user_id, canvas_id, state, None)
        if success:
            return {"success": True, "file_id": result.get("id"), "hash": resolved["hash"],
                    "filename": state["file"].get("filename")}
        return {"success": False, "error": result.get("error") or "OneDrive upload failed"}

    def send_to_docusign(
        self,
        canvas_id: str,
        user_id: str,
        signer_email: str,
        signer_name: str,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send the current version out for EXTERNAL cryptographic signing
        (DocuSign envelope). The envelope id is stamped on the canvas audit
        trail; the signed bytes stay DocuSign-authoritative (fetched on
        demand), matching the received-attachment stance."""
        from integrations import docusign_service

        state = self._require_owner(canvas_id, user_id)
        if "success" in state:
            return state
        resolved = self.get_bytes(canvas_id, user_id)
        if not resolved:
            return {"success": False, "error": "stored PDF bytes are missing for the current version"}

        filename = state["file"].get("filename") or "document.pdf"
        result = docusign_service.send_for_signature(
            filename, resolved["bytes"], signer_email, signer_name,
            email_subject=f"Please sign: {filename}",
        )
        if not result.get("success"):
            return result

        envelope_id = result.get("envelope_id")
        state["lifecycle"]["docusign"] = {
            "envelope_id": envelope_id,
            "envelope_status": result.get("status"),
            "signer_email": signer_email,
            "hash": resolved["hash"],
            "at": datetime.now(timezone.utc).isoformat(),
            "by": f"agent:{agent_id}" if agent_id else f"user:{user_id}",
        }
        self._append_state(canvas_id, user_id, agent_id, state, "pdf_sent_to_docusign",
                           envelope_id=envelope_id, signer_email=signer_email,
                           version_hash=resolved["hash"])
        self._broadcast(user_id, canvas_id, state, None)
        return {"success": True, "envelope_id": envelope_id,
                "status": result.get("status"), "filename": filename}

    async def create_from_email_attachment(
        self,
        user_id: str,
        tenant_id: str,
        email_canvas_id: str,
        attachment_id: str,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Turn an email-canvas attachment (staged OR received — received
        bytes stream through from the mailbox) into a PDF canvas. Provenance
        stamped on the audit trail (source email canvas + attachment id)."""
        from core.canvas_email_service import EmailCanvasService

        resolved = await EmailCanvasService(self.db).get_attachment_bytes(
            email_canvas_id, user_id, attachment_id
        )
        if not resolved or resolved.get("bytes") is None:
            return {"success": False, "error": "attachment content unavailable"}

        record = resolved.get("record") or {}
        filename = record.get("filename") or "attachment.pdf"
        if not filename.lower().endswith(".pdf"):
            return {"success": False, "error": f"not a PDF attachment: {filename}"}

        result = self.create_pdf_canvas(
            user_id=user_id, tenant_id=tenant_id,
            title=filename.rsplit(".", 1)[0], filename=filename,
            content_bytes=resolved["bytes"], agent_id=agent_id,
        )
        if result.get("success"):
            state = result["state"]
            state["source"] = "email_attachment"
            state["source_ref"] = {
                "email_canvas_id": email_canvas_id,
                "attachment_id": attachment_id,
            }
            self._append_state(
                result["canvas_id"], user_id, agent_id, state, "pdf_created_from_attachment",
                email_canvas_id=email_canvas_id, attachment_id=attachment_id,
            )
        return result
