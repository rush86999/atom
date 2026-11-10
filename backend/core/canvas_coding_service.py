"""
Coding Workspace Canvas Service

Backend service for coding canvas with code editor,
diff views, repo browser, and PR reviews.
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.canvas_authority import (
    CanvasAuthorityError,
    claim_active_actor,
    require_active_actor,
    require_canvas_read,
    require_canvas_write,
    reserve_canvas_id,
)
from core.models import CanvasAudit

logger = logging.getLogger(__name__)


def _authority_refusal(exc: CanvasAuthorityError) -> Dict[str, Any]:
    return {
        "success": False,
        "error": str(exc),
        "http_status": exc.status_code,
        "error_code": exc.code,
    }


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

    def _actor(self, user_id: str) -> Dict[str, Any]:
        return require_active_actor(self.db, user_id)

    def get_coding_canvas(self, canvas_id: str, user_id: str) -> Dict[str, Any]:
        """Return the latest coding state for an authorized reader."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_read(self.db, canvas_id, actor)
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "coding",
            ).order_by(desc(CanvasAudit.created_at)).first()
            if not audit:
                return {
                    "success": False,
                    "error": "Coding canvas not found",
                    "http_status": 404,
                    "error_code": "CANVAS_NOT_FOUND",
                }
            return {
                "success": True,
                "data": audit.details_json or {},
            }
        except CanvasAuthorityError as exc:
            return _authority_refusal(exc)
        except Exception as exc:  # noqa: BLE001 - unreadable is not a pass
            logger.error("Failed to read coding canvas: %s", type(exc).__name__)
            return {
                "success": False,
                "error": "Coding canvas could not be read",
                "http_status": 503,
                "error_code": "CODING_CANVAS_READ_FAILED",
            }

    def create_coding_canvas(
        self,
        user_id: str,
        repo: str,
        branch: str,
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        layout: str = "repo_view"
    ) -> Dict[str, Any]:
        """Create a new coding canvas for the current active actor."""
        try:
            actor = self._actor(user_id)
            requested_id = str(canvas_id).strip() if canvas_id is not None else ""
            canvas_id = requested_id or str(uuid.uuid4())

            # The existing Canvas primary key is the atomic id reservation.
            # Any existing id (same owner, another owner or another family)
            # is refused; creation is not an implicit upsert.
            reserve_canvas_id(
                self.db,
                canvas_id=canvas_id,
                actor=actor,
                title=repo,
                canvas_type="coding",
            )
            claim_active_actor(self.db, actor)

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                agent_id=agent_id,
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="create",
                canvas_type="coding",
                details_json={
                    "canvas_type": "coding",
                    "component_type": "repo_browser",
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

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
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
        """Add a file for the current authorized actor."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_write(self.db, canvas_id, actor)

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "coding"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Coding canvas not found"}

            metadata = audit.details_json or {}
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
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="add_file",
                canvas_type="coding",
                details_json={
                    "canvas_type": "coding",
                    "component_type": "code_editor",
                    **metadata,
                }
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "file_id": code_file.file_id, "path": path}

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
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
        """Add a diff view for the current authorized actor."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_write(self.db, canvas_id, actor)

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "coding"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Coding canvas not found"}

            metadata = audit.details_json or {}
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
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="add_diff",
                canvas_type="coding",
                details_json={
                    "canvas_type": "coding",
                    "component_type": "diff_view",
                    **metadata,
                }
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "diff_id": diff["diff_id"]}

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
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
