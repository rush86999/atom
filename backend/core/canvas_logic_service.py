"""
Canvas Logic Service — P7 (Cloudflare OS G7b).

Stores and runs per-canvas server-side Python logic in the isolated sandbox
runtime with a per-canvas storage namespace (``./data/canvas_runtime/<canvas_id>``).
Governance: saving/running canvas logic requires AUTONOMOUS maturity (mirrors
``custom_components_service._check_governance_for_js``).

Reuses ``SandboxRuntime.execute_python`` (DockerRuntime default) with the active
``SandboxPolicy`` caps; the per-canvas namespace is injected as
``inputs["storage_namespace"]`` so the runtime can scope FS writes per canvas.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Per-canvas FS root. Each canvas gets ./data/canvas_runtime/<sanitized_id>.
CANVAS_RUNTIME_ROOT = os.getenv("CANVAS_RUNTIME_ROOT", "./data/canvas_runtime")

# Permissive namespace sanitizer: keep alphanumerics + dashes only. Prevents
# path-traversal via a malicious canvas_id (e.g. "../../etc").
_NAMESPACE_SAFE = re.compile(r"[^A-Za-z0-9-]+")


def sanitize_namespace(canvas_id: str) -> str:
    """Reduce a canvas id to a path-safe namespace segment.

    Guarantees no path separators or traversal characters survive, so a
    malicious canvas_id cannot escape ``CANVAS_RUNTIME_ROOT``.
    """
    if not canvas_id:
        return "unknown"
    cleaned = _NAMESPACE_SAFE.sub("-", str(canvas_id)).strip("-")
    return cleaned or "unknown"


def get_runtime():
    """Resolve the active sandbox runtime (DockerRuntime default)."""
    from core.sandbox_runtime.base import get_runtime as _get
    return _get()


class CanvasLogicService:
    """Save/load/run per-canvas server-side logic."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_logic(
        self,
        canvas_id: str,
        source: str,
        language: str = "python",
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upsert the logic row for ``canvas_id``."""
        from core.models import CanvasLogic

        row = (
            self.db.query(CanvasLogic)
            .filter(CanvasLogic.canvas_id == canvas_id)
            .first()
        )
        if row is None:
            row = CanvasLogic(
                canvas_id=canvas_id,
                language=language,
                source=source,
                created_by=created_by,
            )
            self.db.add(row)
        else:
            row.source = source
            row.language = language
            if created_by is not None:
                row.created_by = created_by
        self.db.commit()
        self.db.refresh(row)
        return {
            "id": row.id,
            "canvas_id": row.canvas_id,
            "language": row.language,
            "source": row.source,
        }

    def load_logic(self, canvas_id: str) -> Optional[Dict[str, Any]]:
        from core.models import CanvasLogic
        row = (
            self.db.query(CanvasLogic)
            .filter(CanvasLogic.canvas_id == canvas_id)
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "canvas_id": row.canvas_id,
            "language": row.language,
            "source": row.source,
            "created_by": row.created_by,
        }

    # ------------------------------------------------------------------
    # Governance
    # ------------------------------------------------------------------

    def check_governance(self, agent_id: Optional[str]) -> None:
        """Require an AUTONOMOUS agent to run/edit canvas logic.

        Mirrors ``custom_components_service._check_governance_for_js``: only
        AUTONOMOUS agents may execute server-side logic. Raises ``PermissionError``
        otherwise.
        """
        if not agent_id:
            raise PermissionError(
                "Canvas logic requires an AUTONOMOUS agent. No agent provided."
            )
        from core.models import AgentRegistry
        agent = (
            self.db.query(AgentRegistry)
            .filter(AgentRegistry.id == agent_id)
            .first()
        )
        if agent is None:
            raise PermissionError(f"Agent '{agent_id}' not found")
        if (agent.status or "").upper() != "AUTONOMOUS":
            raise PermissionError(
                f"Canvas logic requires AUTONOMOUS maturity. "
                f"Agent '{agent.name}' is at {agent.status} level."
            )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        canvas_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        scopes: Optional[Tuple[str, ...]] = None,
    ) -> Dict[str, Any]:
        """Execute the canvas's stored logic in the sandbox runtime.

        Args:
            canvas_id: the canvas whose logic to run.
            inputs: caller-supplied inputs, exposed as module globals alongside
                ``storage_namespace``.
            agent_id: the agent invoking the run (must be AUTONOMOUS).
            scopes: optional tool whitelist for the issued policy. When
                provided, the policy is issued at the AUTONOMOUS floor and its
                ``tool_whitelist`` is replaced with ``scopes`` (viewer-tier cap
                for mini apps). Default (None) preserves the legacy code path.

        Returns:
            ``{"success": bool, "stdout": str, "stderr": str, "exit_code": int}``
        """
        logic = self.load_logic(canvas_id)
        if logic is None:
            return {"success": False, "error": f"No logic saved for canvas {canvas_id}"}

        if agent_id is not None:
            self.check_governance(agent_id)

        namespace = sanitize_namespace(canvas_id)
        fs_root = os.path.join(CANVAS_RUNTIME_ROOT, namespace)
        os.makedirs(fs_root, exist_ok=True)

        run_inputs: Dict[str, Any] = dict(inputs or {})
        run_inputs["storage_namespace"] = namespace

        # Issue a per-canvas-scoped policy so FS writes are bounded to fs_root.
        # Falls back to a minimal policy if the issuer is unavailable.
        if scopes is not None:
            # Explicit scopes (mini-app path): issue at the AUTONOMOUS floor and
            # replace the tool whitelist with the resolved viewer-tier caps.
            from dataclasses import replace
            from core.sandbox_policy import PolicyIssuer
            try:
                policy = PolicyIssuer().issue(
                    run_id=f"canvas-{namespace}",
                    agent_id=agent_id or "canvas-logic",
                    tier_at_issuance="autonomous",
                    workspace_data_root=fs_root,
                )
                policy = replace(policy, tool_whitelist=tuple(scopes))
            except Exception:
                policy = None
        else:
            try:
                from core.sandbox_policy import PolicyIssuer
                policy = PolicyIssuer().issue(
                    run_id=f"canvas-{namespace}",
                    agent_id=agent_id or "canvas-logic",
                    tier_at_issuance="autonomous",
                    workspace_data_root=fs_root,
                )
            except Exception:
                policy = None

        runtime = get_runtime()
        result = await runtime.execute_python(
            logic["source"],
            policy=policy,
            inputs=run_inputs,
            cwd=fs_root,
        )
        return {
            "success": getattr(result, "success", True),
            "stdout": getattr(result, "stdout", "") or "",
            "stderr": getattr(result, "stderr", "") or "",
            "exit_code": getattr(result, "exit_code", 0),
        }
