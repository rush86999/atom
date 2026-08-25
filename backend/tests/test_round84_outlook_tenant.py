"""Round 84 — data-journey bug #2: Outlook learner ingested under wrong tenant.

``Microsoft365LifecycleLearner._persist_to_graph`` passed ``tenant_id=workspace_id``
to ``ingest_structured_data`` — same typo-bug as the historical sync path.
Outlook-extracted nodes were filed under a bogus tenant and never showed
up in tenant-scoped graph reads. Fix resolves the workspace's REAL tenant
from the Workspace row (fallback "default").
"""

from unittest.mock import MagicMock, patch

import pytest

import core.microsoft365_learner as m365


@pytest.mark.asyncio
async def test_outlook_nodes_ingested_under_workspace_tenant():
    learner = m365.Microsoft365LifecycleLearner()

    engine = MagicMock()

    workspace_row = MagicMock(tenant_id="tenant-7")

    def fake_get_db_session():
        ctx = MagicMock()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = workspace_row
        ctx.__enter__ = MagicMock(return_value=db)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("core.graphrag_engine.GraphRAGEngine", return_value=engine), \
         patch("core.database.get_db_session", fake_get_db_session):
        ok = await learner._persist_to_graph(
            "ws-1",
            [{"id": "e1", "type": "order", "name": "PO-1", "properties": {}}],
            [],
        )

    assert ok is True
    kwargs = engine.ingest_structured_data.call_args.kwargs
    assert kwargs["workspace_id"] == "ws-1"
    assert kwargs["tenant_id"] == "tenant-7"


@pytest.mark.asyncio
async def test_missing_workspace_falls_back_to_default_tenant():
    learner = m365.Microsoft365LifecycleLearner()
    engine = MagicMock()

    def fake_get_db_session():
        ctx = MagicMock()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        ctx.__enter__ = MagicMock(return_value=db)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("core.graphrag_engine.GraphRAGEngine", return_value=engine), \
         patch("core.database.get_db_session", fake_get_db_session):
        ok = await learner._persist_to_graph(
            "ws-missing", [{"id": "e1", "type": "order", "name": "PO-1", "properties": {}}], []
        )

    assert ok is True
    assert engine.ingest_structured_data.call_args.kwargs["tenant_id"] == "default"


@pytest.mark.asyncio
async def test_db_failure_falls_back_and_never_raises():
    learner = m365.Microsoft365LifecycleLearner()
    engine = MagicMock()

    with patch("core.graphrag_engine.GraphRAGEngine", return_value=engine), \
         patch("core.database.get_db_session",
               side_effect=RuntimeError("db down")):
        ok = await learner._persist_to_graph(
            "ws-2", [{"id": "e1", "type": "order", "name": "PO-1", "properties": {}}], []
        )

    assert ok is True
    assert engine.ingest_structured_data.call_args.kwargs["tenant_id"] == "default"
