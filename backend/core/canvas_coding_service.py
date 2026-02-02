"""
Coding Workspace Canvas Service

Backend service for coding canvas with code editor,
diff views, repo browser, and PR reviews.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from core.models import CanvasAudit

logger = logging.getLogger(__name__)


class CodeFile:
    """Represents a code file."""
    def __init__(
        self,
        file_id: str,
        path: str,
        content: str,
        language: str = "text",
        status: str = "modified"  # added, modified, deleted
    ):
        self.file_id = file_id
        self.path = path
        self.content = content
        self.language = language
        self.status = status


class DiffHunk:
    """Represents a diff hunk."""
    def __init__(
        self,
        hunk_id: str,
        old_start: int,
        old_lines: List[str],
        new_start: int,
        new_lines: List[str]
    ):
        self.hunk_id = hunk_id
        self.old_start = old_start
        self.old_lines = old_lines
        self.new_start = new_start
        self.new_lines = new_lines


class PullRequestReview:
    """Represents a PR review."""
    def __init__(
        self,
        review_id: str,
        pr_number: int,
        title: str,
        description: str,
        status: str = "open"  # open, merged, closed
    ):
        self.review_id = review_id
        self.pr_number = pr_number
        self.title = title
        self.description = description
        self.status = status


class CodingCanvasService:
    """Service for managing coding canvases."""

    def __init__(self, db: Session):
        self.db = db

    def create_coding_canvas(
        self,
        user_id: str,
        repo: str,
        branch: str,
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        layout: str = "repo_view"
    ) -> Dict[str, Any]:
        """Create a new coding canvas."""
        try:
            canvas_id = canvas_id or str(uuid.uuid4())

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="coding",
                component_type="repo_browser",
                action="create",
                audit_metadata={
                    "repo": repo,
                    "branch": branch,
                    "layout": layout,
                    "files": [],
                    "diffs": [],
                    "pull_requests": [],
                    "comments": []
                }
            )

            self.db.add(audit)
            self.db.commit()

            logger.info(f"Created coding canvas {canvas_id}: {repo}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "repo": repo,
                "branch": branch
            }

        except Exception as e:
            logger.error(f"Failed to create coding canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_file(
        self,
        canvas_id: str,
        user_id: str,
        path: str,
        content: str,
        language: str = "text"
    ) -> Dict[str, Any]:
        """Add a file to the coding workspace."""
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "coding"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Coding canvas not found"}

            metadata = audit.audit_metadata
            files = metadata.get("files", [])

            code_file = CodeFile(
                file_id=str(uuid.uuid4()),
                path=path,
                content=content,
                language=language
            )

            files.append(self._file_to_dict(code_file))
            metadata["files"] = files

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="coding",
                component_type="code_editor",
                action="add_file",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "file_id": code_file.file_id, "path": path}

        except Exception as e:
            logger.error(f"Failed to add file: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_diff(
        self,
        canvas_id: str,
        user_id: str,
        file_path: str,
        old_content: str,
        new_content: str
    ) -> Dict[str, Any]:
        """Add a diff view."""
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "coding"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Coding canvas not found"}

            metadata = audit.audit_metadata
            diffs = metadata.get("diffs", [])

            diff = {
                "diff_id": str(uuid.uuid4()),
                "file_path": file_path,
                "old_content": old_content,
                "new_content": new_content,
                "created_at": datetime.now().isoformat()
            }

            diffs.append(diff)
            metadata["diffs"] = diffs

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="coding",
                component_type="diff_view",
                action="add_diff",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "diff_id": diff["diff_id"]}

        except Exception as e:
            logger.error(f"Failed to add diff: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def _file_to_dict(self, file: CodeFile) -> Dict[str, Any]:
        """Convert file to dict."""
        return {
            "file_id": file.file_id,
            "path": file.path,
            "content": file.content,
            "language": file.language,
            "status": file.status
        }
