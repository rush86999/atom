"""
Email Canvas Service

Backend service for email canvas with threaded conversations,
compose interface, and attachment management.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
import uuid

from core.models import CanvasAudit

logger = logging.getLogger(__name__)


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
                workspace_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="email",
                component_type="compose_form",
                action="create",
                audit_metadata={
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

            metadata = audit.audit_metadata
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
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="email",
                component_type="thread_view",
                action="add_message",
                audit_metadata=metadata
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

            metadata = audit.audit_metadata

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
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="email",
                component_type="compose_form",
                action="save_draft",
                audit_metadata=metadata
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

            metadata = audit.audit_metadata
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
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="email",
                component_type="category_bucket",
                action="categorize",
                audit_metadata=metadata
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
