"""
Email Canvas Service

Backend service for email canvas with threaded conversations,
compose interface, and attachment management.
"""
import re
import time as _time
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.models import Canvas, CanvasAudit

logger = logging.getLogger(__name__)

# Per-user correspondent cache for autocomplete fallbacks: (fetched_at,
# [(email, name), ...]). Kept tiny — autocomplete is best-effort, and the
# durable address book remains the primary source.
_CORRESPONDENT_CACHE: Dict[str, tuple] = {}

# Per-user integration-signature cache: (fetched_at, signature|None). The
# mailbox is the source (sent mail carries the integration's default
# signature) and shouldn't be rescanned per composer mount.
_SIGNATURE_CACHE: Dict[str, tuple] = {}


class EmailMessage:
    """Represents an email message."""
    def __init__(
        self,
        message_id: str,
        from_email: str,
        to_emails: List[str],
        cc_emails: List[str] = None,
        subject: str = "",
        body: str = "",
        timestamp: datetime = None,
        thread_id: str = None,
        attachments: List[Dict] = None,
        read: bool = False
    ):
        self.message_id = message_id
        self.from_email = from_email
        self.to_emails = to_emails
        self.cc_emails = cc_emails or []
        self.subject = subject
        self.body = body
        self.timestamp = timestamp or datetime.now()
        self.thread_id = thread_id
        self.attachments = attachments or []
        self.read = read


class EmailDraft:
    """Represents an email draft."""
    def __init__(
        self,
        draft_id: str,
        to_emails: List[str],
        cc_emails: List[str] = None,
        subject: str = "",
        body: str = "",
        attachments: List[Dict] = None
    ):
        self.draft_id = draft_id
        self.to_emails = to_emails
        self.cc_emails = cc_emails or []
        self.subject = subject
        self.body = body
        self.attachments = attachments or []


class EmailCanvasService:
    """
    Service for managing email canvases.

    Handles email threads, composition, attachments, and categorization.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_email_canvas(
        self,
        user_id: str,
        subject: str,
        recipients: List[str],
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        layout: str = "conversation",
        template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new email canvas.

        Args:
            user_id: User ID
            subject: Email subject
            recipients: List of recipient emails
            canvas_id: Optional canvas ID
            agent_id: Optional agent ID
            layout: Layout (inbox, conversation, compose)
            template: Optional template ID

        Returns:
            Dict with canvas details
        """
        try:
            canvas_id = canvas_id or str(uuid.uuid4())
            thread_id = str(uuid.uuid4())

            # Create initial draft
            draft = EmailDraft(
                draft_id=str(uuid.uuid4()),
                to_emails=recipients,
                subject=subject,
                body=""
            )

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                action_type="create",
                canvas_type="email",
                details_json={
                    "canvas_type": "email",
                    "component_type": "compose_form",
                    "subject": subject,
                    "layout": layout,
                    "thread_id": thread_id,
                    "draft": self._draft_to_dict(draft),
                    "messages": [],
                    "attachments": [],
                    "template": template
                }
            )

            self.db.add(audit)
            self.db.commit()
            self.db.refresh(audit)

            logger.info(f"Created email canvas {canvas_id}: {subject}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "subject": subject,
                "thread_id": thread_id,
                "draft_id": draft.draft_id
            }

        except Exception as e:
            logger.error(f"Failed to create email canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_message_to_thread(
        self,
        canvas_id: str,
        user_id: str,
        from_email: str,
        to_emails: List[str],
        subject: str,
        body: str,
        attachments: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Add a message to an email thread.

        Args:
            canvas_id: Canvas ID
            user_id: User ID
            from_email: Sender email
            to_emails: Recipient emails
            subject: Subject line
            body: Email body
            attachments: Optional attachments

        Returns:
            Dict with message details
        """
        try:
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "email"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Email canvas not found"}

            metadata = audit.details_json or {}
            thread_id = metadata.get("thread_id")
            messages = metadata.get("messages", [])

            # Create new message
            message = EmailMessage(
                message_id=str(uuid.uuid4()),
                from_email=from_email,
                to_emails=to_emails,
                subject=subject,
                body=body,
                thread_id=thread_id,
                attachments=attachments or []
            )

            messages.append(self._message_to_dict(message))
            metadata["messages"] = messages

            # Create message audit entry
            message_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                action_type="add_message",
                canvas_type="email",
                details_json={
                    "canvas_type": "email",
                    "component_type": "thread_view",
                    **metadata,
                }
            )

            self.db.add(message_audit)
            self.db.commit()

            logger.info(f"Added message to thread {canvas_id}")

            return {
                "success": True,
                "message_id": message.message_id,
                "thread_id": thread_id
            }

        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def save_draft(
        self,
        canvas_id: str,
        user_id: str,
        to_emails: List[str],
        cc_emails: List[str] = None,
        subject: str = "",
        body: str = ""
    ) -> Dict[str, Any]:
        """
        Save an email draft.

        Args:
            canvas_id: Canvas ID
            user_id: User ID
            to_emails: To recipients
            cc_emails: CC recipients
            subject: Subject
            body: Email body

        Returns:
            Dict with draft details
        """
        try:
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "email"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Email canvas not found"}

            metadata = audit.details_json or {}

            # Update draft
            draft = EmailDraft(
                draft_id=metadata.get("draft", {}).get("draft_id", str(uuid.uuid4())),
                to_emails=to_emails,
                cc_emails=cc_emails or [],
                subject=subject,
                body=body
            )

            metadata["draft"] = self._draft_to_dict(draft)
            metadata["last_saved"] = datetime.now().isoformat()

            # Create draft audit entry
            draft_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                action_type="save_draft",
                canvas_type="email",
                details_json={
                    "canvas_type": "email",
                    "component_type": "compose_form",
                    **metadata,
                }
            )

            self.db.add(draft_audit)
            self.db.commit()

            logger.info(f"Saved draft for canvas {canvas_id}")

            return {
                "success": True,
                "draft_id": draft.draft_id,
                "message": "Draft saved"
            }

        except Exception as e:
            logger.error(f"Failed to save draft: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def categorize_email(
        self,
        canvas_id: str,
        user_id: str,
        category: str,
        color: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Categorize an email into a bucket.

        Args:
            canvas_id: Canvas ID
            user_id: User ID
            category: Category name
            color: Optional color hex code

        Returns:
            Dict with categorization status
        """
        try:
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "email"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Email canvas not found"}

            metadata = audit.details_json or {}
            categories = metadata.get("categories", [])

            # Add or update category
            categories.append({
                "name": category,
                "color": color,
                "categorized_by": user_id,
                "categorized_at": datetime.now().isoformat()
            })

            metadata["categories"] = categories

            # Create category audit entry
            category_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                action_type="categorize",
                canvas_type="email",
                details_json={
                    "canvas_type": "email",
                    "component_type": "category_bucket",
                    **metadata,
                }
            )

            self.db.add(category_audit)
            self.db.commit()

            logger.info(f"Categorized email {canvas_id} as {category}")

            return {
                "success": True,
                "category": category,
                "message": f"Email categorized as {category}"
            }

        except Exception as e:
            logger.error(f"Failed to categorize email: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def send_email(
        self,
        canvas_id: str,
        user_id: str,
        to_emails: List[str],
        cc_emails: Optional[List[str]] = None,
        subject: str = "",
        body: str = "",
        agent_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Send the composed email through the deterministic email policy.

        Human-initiated (canvas Send button): the human's click IS the
        authorization for allow/approve decisions, so both send; a BLOCK
        (restricted-sensitivity content, e.g. PII/secrets) always refuses.
        Agent-initiated sends go through the MCP path instead, where the
        same policy forces HITL approval (see mcp_service._check_hitl_policy).

        Every attempt is stamped into CanvasAudit — successful sends as
        ``email_send`` (the rate-cap ledger), blocked/failed as
        ``email_send_attempt`` — and broadcast as a ``canvas:update`` so
        agents/users co-editing the canvas see it live.
        """
        from core.email_policy import evaluate_email_action

        decision = evaluate_email_action(
            {"to": to_emails, "cc": cc_emails, "subject": subject, "body": body},
            {"user_id": user_id, "agent_id": agent_id},
        )
        payload = {"to": to_emails, "cc": cc_emails, "subject": subject}

        if decision["decision"] == "block":
            self.record_send(canvas_id, user_id, agent_id, payload, "blocked", decision, tenant_id)
            return {
                "success": False,
                "error": decision["reason"],
                "blocked_by": "email_policy",
                "status": "blocked",
            }

        try:
            from integrations.outlook_service import OutlookService

            svc = OutlookService()
            result = await svc.send_email(
                user_id=user_id,
                to_recipients=to_emails or [],
                cc_recipients=cc_emails or [],
                subject=subject or "",
                body=body or "",
            )
        except Exception as e:
            logger.error(f"Email canvas send failed: {e}")
            self.record_send(canvas_id, user_id, agent_id, payload, "failed", decision, tenant_id)
            return {"success": False, "error": "Outlook send failed", "status": "failed"}

        ok = result is not None
        self.record_send(canvas_id, user_id, agent_id, payload, "sent" if ok else "failed", decision, tenant_id)
        if not ok:
            return {"success": False, "error": "Outlook send failed", "status": "failed"}
        return {
            "success": True,
            "status": "sent",
            "decision": decision["decision"],
            "policy": decision["policy"],
        }

    async def suggest_contacts(
        self,
        user_id: str,
        query: str = "",
        max_results: int = 20,
    ) -> Dict[str, Any]:
        """Recipient suggestions for the email composer's To/Cc autocomplete.

        Two sources, both from the connected mailbox (the same account the
        Send button dispatches through, so suggestions are always addresses
        the transport can deliver to):

        1. The address book (Graph Contacts.Read) — precise, but existing
           consents were granted before that scope was requested, so it can
           403 for already-connected accounts.
        2. Fallback: correspondents mined from the user's own recent mail
           (inbox + sent; Mail.ReadWrite is already consented), ranked by
           exchange frequency. Cached briefly so keystroke lookups don't
           re-hit Graph.

        No mailbox connected → empty list (the composer degrades to plain
        free-text inputs).
        """
        try:
            from integrations.outlook_service import OutlookService

            svc = OutlookService()
            raw = await svc.get_user_contacts(
                user_id,
                query=(query or "").strip() or None,
                max_results=max(max_results * 2, 25),
            )
        except Exception as e:
            logger.warning(f"Contact suggestions unavailable for {user_id}: {e}")
            raw = []

        seen: set = set()
        contacts: List[Dict[str, str]] = []
        for contact in raw or []:
            name = str(contact.get("display_name") or "").strip()
            for entry in contact.get("email_addresses") or []:
                email = str((entry or {}).get("address") or "").strip()
                if not email or email.lower() in seen:
                    continue
                seen.add(email.lower())
                contacts.append({"name": name, "email": email})
                if len(contacts) >= max_results:
                    return {"success": True, "contacts": contacts, "source": "outlook"}

        # Address book empty/denied → fall back to people the user actually
        # exchanges mail with.
        mined = await self._correspondents_from_mail(user_id, svc=None)
        q = (query or "").strip().lower()
        for email, name in mined:
            if q and q not in email.lower() and q not in name.lower():
                continue
            if email.lower() in seen:
                continue
            seen.add(email.lower())
            contacts.append({"name": name, "email": email})
            if len(contacts) >= max_results:
                break
        return {
            "success": True,
            "contacts": contacts,
            "source": ("outlook_mail_history" if contacts else None) if not raw else "outlook",
        }

    async def _correspondents_from_mail(
        self, user_id: str, svc: Optional[Any] = None, scans: int = 25
    ) -> List[tuple]:
        """(email, name) pairs from the user's recent inbox + sent mail,
        ranked by exchange frequency. TTL-cached per user."""
        import time as _time

        now = _time.time()
        cached = _CORRESPONDENT_CACHE.get(user_id)
        if cached and now - cached[0] < 300:
            return cached[1]

        if svc is None:
            from integrations.outlook_service import OutlookService

            svc = OutlookService()
        counts: Dict[str, int] = {}
        names: Dict[str, str] = {}
        own_addresses: set = set()
        try:
            folders = [
                (await svc.get_user_emails(user_id, folder="sent", max_results=scans), True),
                (await svc.get_user_emails(user_id, folder="inbox", max_results=scans), False),
            ]
        except Exception as e:
            logger.warning(f"Mail-history correspondents unavailable for {user_id}: {e}")
            folders = []

        def note(entry: Any) -> None:
            addr = (entry or {}).get("emailAddress") or {}
            email = str(addr.get("address") or "").strip().lower()
            if not email:
                return
            if email in own_addresses:
                return
            counts[email] = counts.get(email, 0) + 1
            names.setdefault(email, str(addr.get("name") or "").strip())

        for emails, is_sent in folders:
            if is_sent:
                # The sender of sent mail IS the user — collect those
                # addresses first so self-references never get counted.
                for m in emails or []:
                    own_addresses.add(
                        str(((m.get("from_field") or {}).get("emailAddress") or {}).get("address") or "").strip().lower()
                    )
            for m in emails or []:
                if not is_sent:
                    note(m.get("from_field"))
                for r in (m.get("to_recipients") or []) + (m.get("cc_recipients") or []):
                    note(r)

        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        result = [(email, names.get(email, "")) for email, _ in ranked]
        _CORRESPONDENT_CACHE[user_id] = (now, result)
        return result

    async def resolve_reply_recipients(
        self,
        user_id: str,
        subject: str,
        body_hint: str = "",
    ) -> Dict[str, Any]:
        """Prefill To (and Cc) for a reply draft by locating its thread.

        The composer auto-fills when an email canvas carries a Re:/Fw:
        subject but no recipient yet — the common case for drafts expanded
        from chat ("Re: Your Inquiry — WFS Ltd" with an empty To). Two legs:

        1. Subject match: full-mailbox Graph search on the prefix-stripped
           subject; newest message written by someone else → reply To = its
           sender; newest own sent mail → To/Cc = its original recipients.
        2. Token match (agent-invented subjects never match leg 1): search
           by the draft's greeting name and distinctive subject tokens
           (company etc.), then mine the person's address from matching
           threads — participant display names and lead-form bodies
           ("Name : Mark, Kellam … Email : mkellam@wfsltd.ca").

        Nothing found (or no mailbox) → to=None; the composer leaves the
        field to the user/autocomplete.
        """
        import re as _re

        base = _re.sub(r"^\s*((re|fw|fwd)\s*:\s*)+", "", subject or "", flags=_re.IGNORECASE).strip()
        if not base or base.lower() == (subject or "").strip().lower():
            return {"success": True, "to": None, "cc": "", "reason": "not_a_reply"}

        try:
            from integrations.outlook_service import OutlookService

            svc = OutlookService()
            results = await svc.search_emails(user_id, base, max_results=25)
        except Exception as e:
            logger.warning(f"Reply-thread resolution unavailable for {user_id}: {e}")
            results = []

        def strip(s: Any) -> str:
            return _re.sub(r"^\s*((re|fw|fwd)\s*:\s*)+", "", str(s or ""), flags=_re.IGNORECASE).strip().lower()

        own_addresses: set = set()
        try:
            profile = await svc.get_user_profile(user_id)
            for key in ("mail", "userPrincipalName"):
                addr = str((profile or {}).get(key) or "").strip().lower()
                if addr:
                    own_addresses.add(addr)
        except Exception:
            pass

        def addr_of(entry: Any) -> str:
            return str(((entry or {}).get("emailAddress") or {}).get("address") or "").strip()

        def ts(m: Dict[str, Any]) -> str:
            return str(m.get("received_date_time") or m.get("sent_date_time") or "")

        candidates = sorted(
            (m for m in results or [] if base.lower() in strip(m.get("subject"))),
            key=ts,
            reverse=True,
        )
        for m in candidates:
            sender = addr_of(m.get("from_field")).lower()
            if sender and sender not in own_addresses:
                name = str(((m.get("from_field") or {}).get("emailAddress") or {}).get("name") or "").strip()
                to = f"{name} <{sender}>" if name else sender
                return {"success": True, "to": to, "cc": "", "source": "thread"}
        for m in candidates:
            sender = addr_of(m.get("from_field")).lower()
            if sender and sender in own_addresses:
                to = [addr_of(r) for r in (m.get("to_recipients") or []) if addr_of(r)]
                cc = [addr_of(r) for r in (m.get("cc_recipients") or []) if addr_of(r)]
                if to:
                    return {
                        "success": True,
                        "to": ", ".join(to),
                        "cc": ", ".join(cc),
                        "source": "thread",
                    }

        # Leg 2 — token match for agent-invented subjects.
        mined = await self._resolve_by_tokens(
            user_id, svc, subject=subject, body_hint=body_hint, own_addresses=own_addresses
        )
        if mined:
            return {"success": True, "to": mined, "cc": "", "source": "tokens"}
        return {"success": True, "to": None, "cc": "", "source": None}

    # Generic/notification locals never represent the person being replied to.
    _NON_PERSON_LOCALS = ("no-reply", "noreply", "do-not-reply", "notifications", "notification", "postmaster")

    @staticmethod
    def _addr_segments(local: str) -> set:
        """Word segments of an address local part ("mkellam" → {"mkellam"},
        "mark.k" → {"mark", "k"})."""
        import re as _re

        return {s for s in _re.split(r"[^a-z0-9]+", local.lower()) if s}

    def _reply_tokens(self, subject: str, body_hint: str) -> tuple:
        """Token split for the token-match leg: (name_tokens, domain_tokens).

        name_tokens come from the draft's greeting ("Hi Mark," → mark) and
        identify the PERSON; domain_tokens come from the prefix-stripped
        subject ("Re: Your Inquiry — WFS Ltd" → wfs) and identify the
        COMPANY. They are weighted differently — both mkellam@wfsltd.ca and
        singram@wfsteelandcrane.com live at "wfs"-ish domains, so only the
        person token can discriminate. Generic words are dropped.
        """
        import re as _re

        stop = {
            "your", "you", "our", "the", "and", "for", "from", "about", "inquiry",
            "inquiries", "request", "quote", "follow", "up", "re", "thanks",
            "fw", "fwd", "ltd", "llc", "inc", "co", "new", "regarding",
        }
        name_tokens: List[str] = []

        m = _re.search(
            r"(?:^|\n)\s*(?:hi|hey|hello|dear)\s+([a-z][a-z'’-]{2,})",
            (body_hint or "").strip(),
            _re.IGNORECASE,
        )
        if m:
            name = m.group(1).lower()
            if name not in stop and len(name) >= 3:
                name_tokens.append(name)

        domain_tokens: List[str] = []
        base = _re.sub(r"^\s*((re|fw|fwd)\s*:\s*)+", "", subject or "", flags=_re.IGNORECASE)
        for word in _re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", base):
            w = word.lower()
            if w not in stop and w not in domain_tokens and w not in name_tokens:
                domain_tokens.append(w)
        return name_tokens, domain_tokens[:3]

    async def _resolve_by_tokens(
        self,
        user_id: str,
        svc: Any,
        subject: str,
        body_hint: str,
        own_addresses: set,
    ) -> Optional[str]:
        """Mine the likely reply target from threads matching the draft's
        person/company tokens (participant names and lead-form bodies)."""
        import re as _re

        name_tokens, domain_tokens = self._reply_tokens(subject, body_hint)
        if not name_tokens and not domain_tokens:
            return None

        # Evidence weights: a NAME hit is far stronger than a company/
        # domain hit (see _reply_tokens).
        _NAME_WEIGHT, _DOMAIN_WEIGHT = 5, 1
        all_tokens = name_tokens + domain_tokens

        queries = [" ".join(all_tokens), *all_tokens]
        counts: Dict[str, int] = {}
        name_evidenced: set = set()
        for q in dict.fromkeys(queries):  # unique, order-preserving
            try:
                # Multi-token queries go unquoted (KQL AND semantics) — the
                # exact-phrase form would never match non-adjacent words.
                results = await svc.search_emails(user_id, q, max_results=25, quote=False)
            except Exception:
                continue

            def name_match(addr: str, name_words: set) -> bool:
                local = addr.lower().partition("@")[0]
                segments = self._addr_segments(local)
                return any(t in name_words or t in segments for t in name_tokens)

            def domain_match(addr: str) -> bool:
                root = addr.lower().partition("@")[2].split(".")[0]
                # Domain roots abbreviate companies: "wfs" ⊂ "wfsltd.ca".
                return any(t in root for t in all_tokens)

            for m in results or []:
                # Participants whose display name or local part matches.
                for p in [m.get("from_field")] + (m.get("to_recipients") or []) + (m.get("cc_recipients") or []):
                    entry = (p or {}).get("emailAddress") or {}
                    addr = str(entry.get("address") or "").strip().lower()
                    if not addr or addr in own_addresses:
                        continue
                    if addr.partition("@")[0] in self._NON_PERSON_LOCALS:
                        continue
                    name_words = set(_re.findall(r"[a-z']+", str(entry.get("name") or "").lower()))
                    if name_match(addr, name_words):
                        counts[addr] = counts.get(addr, 0) + _NAME_WEIGHT
                        name_evidenced.add(addr)
                    elif domain_match(addr):
                        counts[addr] = counts.get(addr, 0) + _DOMAIN_WEIGHT
                # Lead-form bodies: "Name : Mark, Kellam … Email : x@y.z".
                # Body-mined addresses require NAME evidence — bodies carry
                # too many incidental addresses (links, footers). The window
                # is generous: lead forms interleave many fields between
                # the name and the email.
                body = m.get("body") or {}
                content = body.get("content") if isinstance(body, dict) else ""
                if content and name_tokens:
                    text = _re.sub(r"<[^>]+>", " ", str(content))
                    for addr in _re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text):
                        addr = addr.strip().lower()
                        if addr in own_addresses or addr.partition("@")[0] in self._NON_PERSON_LOCALS:
                            continue
                        idx = text.find(addr)
                        before_words = set(_re.findall(r"[a-z']+", text[max(0, idx - 250):idx].lower()))
                        if name_match(addr, before_words):
                            counts[addr] = counts.get(addr, 0) + _NAME_WEIGHT
                            name_evidenced.add(addr)

        if not counts:
            return None
        # Any name-evidenced candidate outranks every domain-only one —
        # frequency among same-company addresses is not person identity.
        pool = name_evidenced or set(counts)
        addr = sorted(
            ((a, counts[a]) for a in pool),
            key=lambda kv: (-kv[1], kv[0]),
        )[0][0]
        return addr

    SIGNATURE_KEY = "email_signature"
    # Closing phrases that introduce a sign-off block in a sent email.
    _CLOSING_PHRASE = re.compile(
        r"\b(best regards|warm regards|kind regards|regards|sincerely|"
        r"thank you|thanks|cheers|respectfully)\b\s*,?",
        re.IGNORECASE,
    )
    # Forwarded-history headers end the sender's own block.
    _FORWARD_MARKER = re.compile(
        r"^\s*(-{3,}|={3,})?\s*(from|sent|to|subject)\s*:\s*\S|^_{5,}\s*original\s+message\s*_*$",
        re.IGNORECASE,
    )

    async def get_signature(self, user_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        """The user's default email signature for the canvas composer.

        Resolution order:
        1. A signature the user stored in THIS app (deliberate override).
        2. The connected integration's default signature. Outlook's Graph
           API does not expose the client-side signature directly, but the
           integration stamps it on every sent message — so it is recovered
           from the sign-off block of the most recent sent email (cached;
           the mailbox shouldn't be scanned per composer mount). The
           integration value is NOT persisted: saving it (set_signature)
           is a deliberate act.
        """
        from core.user_preference_service import UserPreferenceService

        stored = UserPreferenceService(self.db).get_preference(user_id, workspace_id, self.SIGNATURE_KEY)
        if isinstance(stored, str) and stored.strip():
            return {"success": True, "signature": stored.strip(), "source": "stored"}

        cached = _SIGNATURE_CACHE.get(user_id)
        if cached and _time.time() - cached[0] < 3600:
            return {"success": True, "signature": cached[1], "source": "integration"} if cached[1] else (
                {"success": True, "signature": None, "source": None}
            )

        mined = None
        try:
            from integrations.outlook_service import OutlookService

            svc = OutlookService()
            owner_names: set = set()
            try:
                profile = await svc.get_user_profile(user_id)
                display = str((profile or {}).get("displayName") or (profile or {}).get("mail") or "")
                owner_names = {w for w in re.findall(r"[a-z']{3,}", display.lower())}
            except Exception:
                pass
            for m in await svc.get_user_emails(user_id, folder="sent", max_results=25) or []:
                mined = self._extract_signoff(m.get("body"), owner_names=owner_names)
                if mined:
                    break
        except Exception as e:
            logger.warning(f"Signature mining unavailable for {user_id}: {e}")

        _SIGNATURE_CACHE[user_id] = (_time.time(), mined)
        if mined:
            return {"success": True, "signature": mined, "source": "integration"}
        return {"success": True, "signature": None, "source": None}

    def set_signature(self, user_id: str, signature: str, workspace_id: str = "default") -> Dict[str, Any]:
        """Store (or clear, on empty) the user's default email signature."""
        from core.user_preference_service import UserPreferenceService

        value = (signature or "").strip()
        UserPreferenceService(self.db).set_preference(
            user_id, workspace_id, self.SIGNATURE_KEY, value if value else None
        )
        _SIGNATURE_CACHE.pop(user_id, None)
        return {"success": True, "signature": value if value else None, "source": "stored"}

    def _extract_signoff(self, body: Any, owner_names: Optional[set] = None) -> Optional[str]:
        """The sender's own sign-off block: from the last credible closing
        phrase to the end, truncated at forwarded-history headers. Outlook
        HTML renders "Best Regards, Vipul Chopra" on one line, so the
        phrase may be followed by a short name remainder; anything longer
        ("Thanks for reaching out…") is body prose, not a closing. When
        ``owner_names`` is given, the block must contain one of the user's
        own name tokens — quoted history below a reply carries OTHER
        people's signatures, and those must never become the default.
        Returns None when no clear sign-off exists — never guess garbage."""
        if isinstance(body, dict):
            raw = str(body.get("content") or "")
        else:
            raw = str(body or "")
        text = re.sub(r"<[^>]+>", "\n", raw).replace("&nbsp;", " ")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        for i in range(len(lines) - 1, -1, -1):
            m = self._CLOSING_PHRASE.search(lines[i])
            if not m:
                continue
            remainder = lines[i][m.end():].strip().rstrip(",")
            # A closing phrase swallowed by prose is not a sign-off.
            if len(remainder) > 40:
                continue
            opening = lines[i][m.start():]
            rest: List[str] = []
            for ln in lines[i + 1:]:
                if self._FORWARD_MARKER.match(ln):
                    break
                rest.append(ln)
            rest = [ln for ln in rest if not ln.startswith(("--", "___"))]
            cleaned = [opening] + rest
            # Real Outlook signatures run long (banner + promo lines): a
            # 10-line cap rejected the actual 11-line default.
            if not 2 <= len(cleaned) <= 16:
                # Nothing usable after this closing — keep scanning earlier
                # ones (the real signature may sit above quoted history).
                continue
            if owner_names:
                words = set(re.findall(r"[a-z']+", "\n".join(cleaned).lower()))
                if not (owner_names & words):
                    continue
            return "\n".join(cleaned)
        return None

    def record_send(
        self,
        canvas_id: str,
        user_id: str,
        agent_id: Optional[str],
        payload: Dict[str, Any],
        status: str,
        decision: Dict[str, Any],
        tenant_id: str = "default",
    ) -> None:
        """Stamp a CanvasAudit row for a send attempt + broadcast canvas:update.

        Only successful sends get action_type="email_send" — the rate-cap
        ledger (email_policy._sends_in_last_hour); blocked/failed attempts
        are recorded as "email_send_attempt" so they stay auditable without
        consuming quota.

        canvas_audit.canvas_id is a NOT NULL FK to canvases.id: when no such
        Canvas row exists (e.g. canvas_id was absent), a minimal email Canvas
        row is created first so the audit insert cannot fail on FK
        enforcement (PostgreSQL; SQLite tests don't enforce it).
        """
        canvas_id = canvas_id or f"email_{uuid.uuid4().hex[:8]}"
        if self.db.query(Canvas).filter(Canvas.id == canvas_id).first() is None:
            self.db.add(Canvas(
                id=canvas_id,
                tenant_id=tenant_id,
                created_by=user_id or "system",
                name=payload.get("subject") or "Email canvas",
                canvas_type="email",
                status="active",
            ))

        audit = CanvasAudit(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            canvas_id=canvas_id,
            action_type="email_send" if status == "sent" else "email_send_attempt",
            canvas_type="email",
            details_json={
                "canvas_type": "email",
                "component_type": "compose_form",
                "send_status": status,
                "decision": decision.get("decision"),
                "policy": decision.get("policy"),
                "reason": decision.get("reason"),
                "payload": payload,
                "sent_at": datetime.now().isoformat(),
            },
        )
        self.db.add(audit)
        self.db.commit()
        logger.info(f"Email canvas send recorded: {canvas_id} status={status}")

        # Live broadcast on BOTH channels (canvas page + user panel) so the
        # agent co-editing loop sees the send (canvas:update pattern, #39).
        try:
            import asyncio

            from core.websockets import manager as ws_manager

            message = {
                "type": "canvas:update",
                "data": {
                    "action": "email_send",
                    "canvas_id": canvas_id,
                    "canvas_type": "email",
                    "component": "email",
                    "data": {"status": status, "payload": payload},
                },
            }
            for channel in (f"canvas:{canvas_id}", f"user:{user_id}"):
                try:
                    asyncio.create_task(ws_manager.broadcast(channel, dict(message)))
                except Exception:
                    pass
        except Exception as e:  # pragma: no cover - broadcast never breaks send
            logger.debug(f"Email canvas broadcast failed: {e}")

    def _message_to_dict(self, message: EmailMessage) -> Dict[str, Any]:
        """Convert message to dict."""
        return {
            "message_id": message.message_id,
            "from_email": message.from_email,
            "to_emails": message.to_emails,
            "cc_emails": message.cc_emails,
            "subject": message.subject,
            "body": message.body,
            "timestamp": message.timestamp.isoformat(),
            "thread_id": message.thread_id,
            "attachments": message.attachments,
            "read": message.read
        }

    def _draft_to_dict(self, draft: EmailDraft) -> Dict[str, Any]:
        """Convert draft to dict."""
        return {
            "draft_id": draft.draft_id,
            "to_emails": draft.to_emails,
            "cc_emails": draft.cc_emails,
            "subject": draft.subject,
            "body": draft.body,
            "attachments": draft.attachments
        }
