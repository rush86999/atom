"""
Terminal Canvas Service

Backend service for terminal canvas with command execution,
file trees, process monitoring, and log viewing.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import CanvasAudit

logger = logging.getLogger(__name__)


class TerminalOutput:
    """Represents terminal command output."""
    def __init__(
        self,
        output_id: str,
        command: str,
        output: str,
        exit_code: int = 0,
        timestamp: datetime = None
    ):
        self.output_id = output_id
        self.command = command
        self.output = output
        self.exit_code = exit_code
        self.timestamp = timestamp or datetime.now()


class FileNode:
    """Represents a file or directory in the file tree."""
    def __init__(
        self,
        node_id: str,
        name: str,
        node_type: str,  # file, directory
        path: str,
        children: List = None,
        size: Optional[int] = None
    ):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.path = path
        self.children = children or []
        self.size = size


class ProcessInfo:
    """Represents a running process."""
    def __init__(
        self,
        pid: int,
        name: str,
        cpu_percent: float,
        memory_mb: float,
        user: str = ""
    ):
        self.pid = pid
        self.name = name
        self.cpu_percent = cpu_percent
        self.memory_mb = memory_mb
        self.user = user


class TerminalCanvasService:
    """Service for managing terminal canvases."""

    def __init__(self, db: Session):
        self.db = db

    def create_terminal_canvas(
        self,
        user_id: str,
        command: str,
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        working_dir: str = "."
    ) -> Dict[str, Any]:
        """Create a new terminal canvas."""
        try:
            canvas_id = canvas_id or str(uuid.uuid4())

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="terminal",
                component_type="shell_output",
                action="create",
                audit_metadata={
                    "working_dir": working_dir,
                    "command": command,
                    "outputs": [],
                    "file_tree": {},
                    "processes": [],
                    "logs": []
                }
            )

            self.db.add(audit)
            self.db.commit()

            logger.info(f"Created terminal canvas {canvas_id}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "command": command,
                "working_dir": working_dir
            }

        except Exception as e:
            logger.error(f"Failed to create terminal canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_output(
        self,
        canvas_id: str,
        user_id: str,
        command: str,
        output: str,
        exit_code: int = 0
    ) -> Dict[str, Any]:
        """Add command output to the terminal."""
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "terminal"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Terminal canvas not found"}

            metadata = audit.audit_metadata
            outputs = metadata.get("outputs", [])

            term_output = TerminalOutput(
                output_id=str(uuid.uuid4()),
                command=command,
                output=output,
                exit_code=exit_code
            )

            outputs.append(self._output_to_dict(term_output))
            metadata["outputs"] = outputs

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="terminal",
                component_type="shell_output",
                action="add_output",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "output_id": term_output.output_id}

        except Exception as e:
            logger.error(f"Failed to add output: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def update_file_tree(
        self,
        canvas_id: str,
        user_id: str,
        file_tree: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update the file tree."""
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "terminal"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Terminal canvas not found"}

            metadata = audit.audit_metadata
            metadata["file_tree"] = file_tree

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="terminal",
                component_type="file_tree",
                action="update_tree",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to update file tree: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def _output_to_dict(self, output: TerminalOutput) -> Dict[str, Any]:
        """Convert output to dict."""
        return {
            "output_id": output.output_id,
            "command": output.command,
            "output": output.output,
            "exit_code": output.exit_code,
            "timestamp": output.timestamp.isoformat()
        }
