"""Scratch billing/ledger store for tests that dispatch paid work.

``TESTING=1`` redirects the app to an isolated database, but a test that
believes it configured billing must own the store it asserts against. These
helpers build a throwaway SQLite file, point the durable writers at it, and
seed the real ``Tenant``/``TenantSetting`` policy rows the reservation path
reads — never the live dev DB, never a bypass flag.

This is the supported way for legacy success fixtures (which construct a
handler with a tenant id that does not exist anywhere) to stay honest: seed a
scratch tenant policy instead of weakening admission.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import (
    Base,
    Tenant,
    TenantSetting,
    TokenUsage,
    Workspace,
)


def install_scratch_billing(
    monkeypatch,
    tmp_path,
    *,
    tenant_id: str,
    workspace_id: str | None = None,
    limit: float = 0.0,
    mode: str = "soft_stop",
    spend: float = 0.0,
    filename: str = "scratch-billing.db",
):
    """Point the LLM ledger + budget policy at a scratch SQLite file.

    ``limit=0.0``/``mode="soft_stop"`` is the intended "no cap configured"
    observe policy (still an *enforced* admission path: the reservation row is
    written). Use ``mode="hard_stop"`` with a positive limit to test refusals.

    Returns the session factory so a control can inspect the ledger directly.
    """
    workspace_id = workspace_id or f"ws-{tenant_id}"
    engine = create_engine(
        f"sqlite:///{tmp_path}/{filename}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    # The durable writers resolve SessionLocal at call time (see
    # spend_aggregation_service), so these patches cover admission,
    # settlement and any ordinary handler DB access in the same test.
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", scratch_session)
    monkeypatch.setattr("core.database.engine", engine, raising=False)

    with Session() as db:
        if db.query(Tenant.id).filter(Tenant.id == tenant_id).first() is None:
            db.add(Tenant(
                id=tenant_id, name=tenant_id,
                subdomain=tenant_id.replace("_", "-")))
        if workspace_id and db.query(Workspace.id).filter(
                Workspace.id == workspace_id).first() is None:
            db.add(Workspace(
                id=workspace_id, name=workspace_id, tenant_id=tenant_id))
        if db.query(TenantSetting.id).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == "billing").first() is None:
            db.add(TenantSetting(
                tenant_id=tenant_id, setting_key="billing",
                setting_value=json.dumps({
                    "budget_limit_usd": limit,
                    "enforcement": {"mode": mode},
                })))
        if spend:
            db.add(TokenUsage(
                agent_id=None, workspace_id=workspace_id,
                tenant_id=tenant_id, model_name="scratch-seed",
                cost_usd=spend, pricing_status="priced",
                reservation_status="none", timestamp=datetime.now()))
        db.commit()

    return Session
