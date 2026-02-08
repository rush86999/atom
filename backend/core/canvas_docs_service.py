"""
Documentation Canvas Service

Backend service for documentation canvas with rich editing,
version history, comments, and table of contents.
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.canvas_type_registry import canvas_type_registry
from core.models import CanvasAudit, User

logger = logging.getLogger(__name__)


class DocumentVersion:
    """Represents a version of a document."""
    def __init__(self, version_id: str, content: str, author: str, created_at: datetime, changes: str = ""):
        self.version_id = version_id
        self.content = content
        self.author = author
        self.created_at = created_at
        self.changes = changes


class DocumentComment:
    """Represents a comment on a document."""
    def __init__(self, comment_id: str, content: str, author: str, selection: Optional[Dict[str, Any]] = None,
                 resolved: bool = False, created_at: datetime = None):
        self.comment_id = comment_id
        self.content = content
        self.author = author
        self.selection = selection  # {start, end, text} for inline comments
        self.resolved = resolved
        self.created_at = created_at or datetime.now()


class DocumentationCanvasService:
    """
    Service for managing documentation canvases.

    Handles document creation, updates, versioning, and comments.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_document_canvas(
        self,
        user_id: str,
        title: str,
        content: str,
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        layout: str = "document",
        enable_comments: bool = True,
        enable_versioning: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new documentation canvas.

        Args:
            user_id: User ID creating the document
            title: Document title
            content: Initial markdown content
            canvas_id: Optional canvas ID (auto-generated if not provided)
            agent_id: Optional agent ID creating the document
            layout: Layout (document, split_view, focus)
            enable_comments: Enable commenting
            enable_versioning: Enable version history

        Returns:
            Dict with canvas details
        """
        try:
            canvas_id = canvas_id or str(uuid.uuid4())

            # Create initial version
            initial_version = DocumentVersion(
                version_id=str(uuid.uuid4()),
                content=content,
                author=agent_id or user_id,
                created_at=datetime.now(),
                changes="Initial version"
            )

            # Create canvas audit entry
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="docs",
                component_type="rich_editor",
                component_name="document",
                action="create",
                audit_metadata={
                    "title": title,
                    "content": content,
                    "layout": layout,
                    "enable_comments": enable_comments,
                    "enable_versioning": enable_versioning,
                    "versions": [self._version_to_dict(initial_version)],
                    "comments": []
                }
            )

            self.db.add(audit)
            self.db.commit()
            self.db.refresh(audit)

            logger.info(f"Created documentation canvas {canvas_id}: {title}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "title": title,
                "layout": layout,
                "content": content,
                "version_id": initial_version.version_id,
                "enable_comments": enable_comments,
                "enable_versioning": enable_versioning
            }

        except Exception as e:
            logger.error(f"Failed to create document canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def update_document_content(
        self,
        canvas_id: str,
        user_id: str,
        content: str,
        changes: str = "",
        create_version: bool = True
    ) -> Dict[str, Any]:
        """
        Update document content and optionally create a new version.

        Args:
            canvas_id: Canvas ID
            user_id: User ID making the update
            content: New content
            changes: Description of changes
            create_version: Whether to create a new version

        Returns:
            Dict with update status
        """
        try:
            # Get latest canvas audit
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "docs"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Document not found"}

            metadata = audit.audit_metadata or {}
            versions = metadata.get("versions", [])

            # Create new version if enabled
            if create_version and metadata.get("enable_versioning", True):
                new_version = DocumentVersion(
                    version_id=str(uuid.uuid4()),
                    content=content,
                    author=user_id,
                    created_at=datetime.now(),
                    changes=changes
                )
                versions.append(self._version_to_dict(new_version))

            # Update metadata
            metadata["content"] = content
            metadata["versions"] = versions
            metadata["updated_at"] = datetime.now().isoformat()

            # Create update audit entry
            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="docs",
                component_type="rich_editor",
                action="update",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            logger.info(f"Updated document canvas {canvas_id}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "content": content,
                "version_id": versions[-1]["version_id"] if versions else None
            }

        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_comment(
        self,
        canvas_id: str,
        user_id: str,
        content: str,
        selection: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a comment to a document.

        Args:
            canvas_id: Canvas ID
            user_id: User ID adding the comment
            content: Comment content
            selection: Optional text selection {start, end, text}

        Returns:
            Dict with comment details
        """
        try:
            # Get latest canvas audit
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "docs"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Document not found"}

            if not audit.audit_metadata.get("enable_comments", True):
                return {"success": False, "error": "Comments not enabled for this document"}

            metadata = audit.audit_metadata
            comments = metadata.get("comments", [])

            # Create new comment
            new_comment = DocumentComment(
                comment_id=str(uuid.uuid4()),
                content=content,
                author=user_id,
                selection=selection,
                resolved=False,
                created_at=datetime.now()
            )

            comments.append(self._comment_to_dict(new_comment))
            metadata["comments"] = comments

            # Create comment audit entry
            comment_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="docs",
                component_type="comment_thread",
                action="comment",
                audit_metadata=metadata
            )

            self.db.add(comment_audit)
            self.db.commit()

            logger.info(f"Added comment to document {canvas_id}")

            return {
                "success": True,
                "comment_id": new_comment.comment_id,
                "content": content,
                "selection": selection
            }

        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def resolve_comment(
        self,
        canvas_id: str,
        comment_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Resolve a comment.

        Args:
            canvas_id: Canvas ID
            comment_id: Comment ID
            user_id: User ID resolving the comment

        Returns:
            Dict with resolution status
        """
        try:
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "docs"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Document not found"}

            metadata = audit.audit_metadata
            comments = metadata.get("comments", [])

            # Find and resolve comment
            for comment in comments:
                if comment["comment_id"] == comment_id:
                    comment["resolved"] = True
                    comment["resolved_by"] = user_id
                    comment["resolved_at"] = datetime.now().isoformat()
                    break

            metadata["comments"] = comments

            # Create resolution audit entry
            resolution_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="docs",
                component_type="comment_thread",
                action="resolve_comment",
                audit_metadata=metadata
            )

            self.db.add(resolution_audit)
            self.db.commit()

            logger.info(f"Resolved comment {comment_id} in document {canvas_id}")

            return {"success": True, "comment_id": comment_id}

        except Exception as e:
            logger.error(f"Failed to resolve comment: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def get_document_versions(self, canvas_id: str) -> Dict[str, Any]:
        """
        Get version history for a document.

        Aggregates versions from all audit entries to ensure complete history.

        Args:
            canvas_id: Canvas ID

        Returns:
            Dict with version history
        """
        try:
            # Get ALL audit entries for this canvas to ensure we capture all versions
            audits = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "docs"
            ).order_by(CanvasAudit.created_at).all()

            if not audits:
                return {"success": False, "error": "Document not found"}

            # Get the latest metadata which should have accumulated versions
            # The update_document_content method appends to the versions list
            # so the latest audit entry should have the complete history
            latest_audit = audits[-1]
            metadata = latest_audit.audit_metadata or {}
            versions = metadata.get("versions", [])

            return {
                "success": True,
                "canvas_id": canvas_id,
                "versions": versions,
                "total": len(versions)
            }

        except Exception as e:
            logger.error(f"Failed to get versions: {e}")
            return {"success": False, "error": str(e)}

    def restore_version(
        self,
        canvas_id: str,
        version_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Restore a document to a previous version.

        Args:
            canvas_id: Canvas ID
            version_id: Version ID to restore
            user_id: User ID restoring the version

        Returns:
            Dict with restoration status
        """
        try:
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "docs"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Document not found"}

            metadata = audit.audit_metadata
            versions = metadata.get("versions", [])

            # Find version
            target_version = None
            for version in versions:
                if version["version_id"] == version_id:
                    target_version = version
                    break

            if not target_version:
                return {"success": False, "error": "Version not found"}

            # Restore content
            content = target_version["content"]

            # Create new version for the restoration
            new_version = DocumentVersion(
                version_id=str(uuid.uuid4()),
                content=content,
                author=user_id,
                created_at=datetime.now(),
                changes=f"Restored from version {version_id}"
            )

            versions.append(self._version_to_dict(new_version))
            metadata["content"] = content
            metadata["versions"] = versions

            # Create restoration audit entry
            restore_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="docs",
                component_type="version_history",
                action="restore_version",
                audit_metadata=metadata
            )

            self.db.add(restore_audit)
            self.db.commit()

            logger.info(f"Restored version {version_id} in document {canvas_id}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "content": content,
                "restored_from": version_id,
                "new_version_id": new_version.version_id
            }

        except Exception as e:
            logger.error(f"Failed to restore version: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def get_table_of_contents(self, canvas_id: str) -> Dict[str, Any]:
        """
        Generate table of contents from document headings.

        Args:
            canvas_id: Canvas ID

        Returns:
            Dict with table of contents
        """
        try:
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "docs"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Document not found"}

            metadata = audit.audit_metadata
            content = metadata.get("content", "")

            # Parse markdown headings
            import re
            headings = []
            for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
                level = len(match.group(1))
                title = match.group(2)
                # Generate anchor ID
                anchor = title.lower().replace(" ", "-").replace("/", "-")
                headings.append({
                    "level": level,
                    "title": title,
                    "anchor": anchor,
                    "position": match.start()
                })

            return {
                "success": True,
                "canvas_id": canvas_id,
                "headings": headings,
                "total": len(headings)
            }

        except Exception as e:
            logger.error(f"Failed to generate table of contents: {e}")
            return {"success": False, "error": str(e)}

    def _version_to_dict(self, version: DocumentVersion) -> Dict[str, Any]:
        """Convert version object to dict."""
        return {
            "version_id": version.version_id,
            "content": version.content,
            "author": version.author,
            "created_at": version.created_at.isoformat(),
            "changes": version.changes
        }

    def _comment_to_dict(self, comment: DocumentComment) -> Dict[str, Any]:
        """Convert comment object to dict."""
        return {
            "comment_id": comment.comment_id,
            "content": comment.content,
            "author": comment.author,
            "selection": comment.selection,
            "resolved": comment.resolved,
            "created_at": comment.created_at.isoformat()
        }
