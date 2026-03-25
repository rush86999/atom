"""
Canvas Context Extractor for Episodic Memory

Extracts terminal state, editor state, and canvas node state
to provide rich context for agent episodic memory.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import json
import logging

from core.models import Canvas, IntegrationCanvasNode, IntegrationConnection

logger = logging.getLogger(__name__)


class CanvasContextExtractor:
    """Extracts canvas context for episodic memory storage"""

    def __init__(self, db: Session):
        self.db = db

    def extract_canvas_context(
        self,
        canvas_id: str,
        tenant_id: str,
        include_terminal: bool = True,
        include_editor: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Extract full canvas context including terminal and editor state
        """
        # Security: Verify tenant owns the canvas
        canvas = self.db.query(Canvas).filter(
            Canvas.id == canvas_id,
            Canvas.tenant_id == tenant_id
        ).first()

        if not canvas:
            logger.warning(f"Canvas {canvas_id} not found for tenant {tenant_id}")
            return None

        # Extract basic canvas metadata
        context = {
            "canvas_id": canvas_id,
            "tenant_id": tenant_id,
            "canvas_name": canvas.name,
            "canvas_type": canvas.canvas_type,
            "created_at": canvas.created_at.isoformat() if canvas.created_at else None,
            "updated_at": canvas.updated_at.isoformat() if canvas.updated_at else None,
        }

        # Extract nodes
        nodes = self.db.query(IntegrationCanvasNode).filter(
            IntegrationCanvasNode.canvas_id == canvas_id
        ).all()

        # Categorize nodes
        terminal_nodes = []
        editor_nodes = []
        skill_nodes = []
        data_nodes = []

        for node in nodes:
            node_type = node.integration_id
            
            node_data = {
                "id": node.id,
                "type": node_type,
                "name": node.display_name or node_type,
                "position": node.position,
                "data": node.config or {},
            }

            if node_type == "terminal":
                terminal_nodes.append(node_data)
            elif node_type == "editor":
                editor_nodes.append(node_data)
            elif node_type == "skill":
                skill_nodes.append(node_data)
            else:
                data_nodes.append(node_data)

        context["nodes"] = {
            "terminal": terminal_nodes if include_terminal else [],
            "editor": editor_nodes if include_editor else [],
            "skill": skill_nodes,
            "data": data_nodes,
            "total_count": len(nodes)
        }

        # Extract terminal state
        if include_terminal and terminal_nodes:
            context["terminal_state"] = self._extract_terminal_state(terminal_nodes)

        # Extract editor state
        if include_editor and editor_nodes:
            context["editor_state"] = self._extract_editor_state(editor_nodes)

        # Extract connections (edges)
        edges = self.db.query(IntegrationConnection).filter(
            IntegrationConnection.canvas_id == canvas_id
        ).all()
        
        context["edges"] = [
            {
                "id": edge.id,
                "source_id": edge.source_node_id,
                "target_id": edge.target_node_id,
                "type": edge.connection_type
            }
            for edge in edges
        ]

        # Add summary of content if no nodes exist but content is present
        if not nodes and canvas.content:
            context["canvas_content_summary"] = self._summarize_canvas_content(canvas.content)

        return context

    def _extract_terminal_state(self, terminal_nodes: List[Dict]) -> Dict[str, Any]:
        """Extract terminal state from terminal nodes"""
        state = {
            "active_terminals": len(terminal_nodes),
            "command_history": [],
            "current_directories": [],
            "environments": []
        }

        for node in terminal_nodes:
            data = node.get("data", {})
            if "commands" in data:
                state["command_history"].extend(data["commands"][-10:])
            if "cwd" in data:
                state["current_directories"].append(data["cwd"])
            if "env" in data:
                state["environments"].append({
                    "node_id": node["id"],
                    "vars": list(data["env"].keys()) if isinstance(data["env"], dict) else []
                })

        return state

    def _extract_editor_state(self, editor_nodes: List[Dict]) -> Dict[str, Any]:
        """Extract editor state from editor nodes"""
        state = {
            "open_files": [],
            "active_editors": len(editor_nodes),
            "language_counts": {}
        }

        for node in editor_nodes:
            data = node.get("data", {})
            if "filename" in data:
                state["open_files"].append({
                    "node_id": node["id"],
                    "filename": data["filename"],
                    "language": data.get("language", "unknown")
                })
            if "language" in data:
                lang = data["language"]
                state["language_counts"][lang] = state["language_counts"].get(lang, 0) + 1

        return state

    def _summarize_canvas_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize canvas content JSON when no nodes exist"""
        summary = {
            "has_content": True,
            "content_keys": list(content.keys()) if isinstance(content, dict) else [],
        }

        if isinstance(content, dict) and "nodes" in content and isinstance(content["nodes"], list):
            node_types = {}
            for node in content["nodes"]:
                node_type = node.get("type", "unknown")
                node_types[node_type] = node_types.get(node_type, 0) + 1

            summary["node_types"] = node_types
            summary["total_nodes"] = len(content["nodes"])

        return summary

    def format_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format canvas context for LLM prompt"""
        if not context:
            return ""

        lines = [
            f"Canvas: {context.get('canvas_name', 'Untitled')} ({context['canvas_id']})",
            f"Nodes: {context.get('nodes', {}).get('total_count', 0)} total"
        ]

        terminal_state = context.get("terminal_state", {})
        if terminal_state.get("active_terminals"):
            lines.append(f"\nTerminal Sessions: {terminal_state['active_terminals']}")
            if terminal_state.get("current_directories"):
                lines.append(f"Working Directories: {', '.join(terminal_state['current_directories'])}")

        editor_state = context.get("editor_state", {})
        if editor_state.get("active_editors"):
            lines.append(f"\nOpen Files: {editor_state['active_editors']}")
            for file_info in editor_state.get("open_files", [])[:5]:
                lines.append(f"  - {file_info['filename']} ({file_info['language']})")

        return "\n".join(lines)

    async def generate_presentation_summary(
        self,
        canvas_id: str,
        tenant_id: str,
        force_refresh: bool = False
    ) -> Optional[str]:
        """
        Generate LLM-based presentation summary for canvas
        """
        from core.canvas_presentation_summary import CanvasPresentationSummaryService

        # Extract canvas state (sync)
        context = self.extract_canvas_context(
            canvas_id,
            tenant_id,
            include_terminal=True,
            include_editor=True
        )

        if not context:
            return None

        # Generate presentation summary using LLM (async)
        summary_service = CanvasPresentationSummaryService(self.db)
        summary = await summary_service.generate_presentation_summary(
            canvas_id=canvas_id,
            canvas_type=context.get('canvas_type', 'generic'),
            canvas_state=context,
            tenant_id=tenant_id,
            use_cache=not force_refresh
        )

        return summary
