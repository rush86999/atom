"""The one AgentRegistry visibility rule shared by agent reads and writers.

``GET /api/agents`` and an audit-linked correction write must answer the same
question: which registry rows may this actor act on? They previously drifted —
the reader showed the actor's own workspace plus shared/legacy rows, while the
correction writer was built with the Personal-Edition ``"default"`` workspace
and could see neither a real-workspace agent nor (after a scope-only fix) the
shared rows the reader still lists.

The rule here is deliberately the SAME predicate the agent reader already used:
the actor's exact current workspace plus the existing shared/legacy rows
(``NULL``, ``""``, ``"default"``), with tenant compatibility (``NULL``, ``""``,
``"default"`` or the actor's tenant). It never admits a foreign workspace or a
foreign tenant, and it has no administrator-wide bypass.

Both scope dictionaries this accepts come from the authoritative persisted
``User`` row: ``api.agent_routes._reader_scope`` and
``core.audit_access.resolve_audit_scope`` share the ``workspace_id`` /
``tenant_id`` / ``personal`` keys this predicate reads.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.models import AgentRegistry
from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID


def agent_reader_condition(scope: Dict[str, Any]):
    """Scope AgentRegistry reads/writes to the current workspace + shared rows.

    Personal/null and ``default`` registry entries are the existing shared
    surface. Current-workspace agents are included; peer workspace and foreign
    tenant rows are not. No administrator-wide bypass is invented here.
    """
    workspace = scope["workspace_id"]
    if scope.get("personal"):
        workspace_condition = or_(
            AgentRegistry.workspace_id.is_(None),
            AgentRegistry.workspace_id == "",
            AgentRegistry.workspace_id == workspace,
        )
    else:
        workspace_condition = or_(
            AgentRegistry.workspace_id.is_(None),
            AgentRegistry.workspace_id == "",
            AgentRegistry.workspace_id == PERSONAL_WORKSPACE_ID,
            AgentRegistry.workspace_id == workspace,
        )
    # Personal/default is an existing shared-registry alias, not a foreign
    # tenant. A contradictory real tenant still does not match.
    tenant_condition = or_(
        AgentRegistry.tenant_id.is_(None),
        AgentRegistry.tenant_id == "",
        AgentRegistry.tenant_id == PERSONAL_TENANT_ID,
        AgentRegistry.tenant_id == scope["tenant_id"],
    )
    return and_(workspace_condition, tenant_condition)


def scoped_agent_for_scope(
    db: Session,
    scope: Dict[str, Any],
    agent_id: str,
) -> Optional[AgentRegistry]:
    """Load one AgentRegistry row inside an already-resolved actor scope."""
    return (
        db.query(AgentRegistry)
        .filter(
            AgentRegistry.id == str(agent_id),
            agent_reader_condition(scope),
        )
        .populate_existing()
        .first()
    )
