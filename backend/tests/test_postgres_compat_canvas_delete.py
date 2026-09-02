"""PostgreSQL compatibility for the canvas delete/restore flows.

The local dev backend runs SQLite, but deployments run PostgreSQL. The
delete/restore semantics (strict recency, idempotent double-delete,
listing exclusion) must behave IDENTICALLY on both. These tests run the
full scenario against a real throwaway PostgreSQL database and SKIP when
no local Postgres is reachable — they exist to catch dialect-specific
regressions (timestamp precision, timezone handling, window ordering).
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from core.database import Base
from core.models import Canvas, CanvasAudit, Tenant, User

ADMIN = "postgresql+psycopg2://rushiparikh@localhost:5432/postgres"
TESTDB = "atom_compat_test"


def _pg_available() -> bool:
    try:
        eng = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
        with eng.connect():
            pass
        eng.dispose()
        return True
    except Exception:
        return False


pg = pytest.mark.skipif(not _pg_available(), reason="local PostgreSQL not reachable")


@pytest.fixture
def pg_session():
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TESTDB}"))
        c.execute(text(f"CREATE DATABASE {TESTDB}"))
    admin.dispose()

    engine = create_engine(f"postgresql+psycopg2://rushiparikh@localhost:5432/{TESTDB}")
    from core.models import Canvas as _C  # ensure models imported before create_all
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    with Sess() as s:
        yield s, engine
    engine.dispose()
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TESTDB}"))
    admin.dispose()


@pg
def test_pg_delete_restore_strict_recency(pg_session):
    s, engine = pg_session
    CID = "compat-640ec9a9"

    s.add(Tenant(id="default", name="compat tenant", subdomain="compat"))
    s.add(User(id="u-1", email="compat@test.local", first_name="c", last_name="t",
               role="owner", status="active", tenant_id="default"))
    s.add(Canvas(id=CID, tenant_id="default", created_by="u-1", name="compat",
                 canvas_type="email", status="active",
                 content={"body": "compat draft"}))
    # LEGACY second-precision rows (what func.now() wrote before the µs fix)
    t0 = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    s.add(CanvasAudit(canvas_id=CID, tenant_id="default", action_type="create",
                      user_id="u-1", canvas_type="email",
                      details_json={"content": {"body": "compat draft"}}, created_at=t0))
    s.add(CanvasAudit(canvas_id=CID, tenant_id="default", action_type="delete",
                      user_id="u-1", canvas_type="email",
                      details_json={"deleted": True}, created_at=t0 + dt.timedelta(seconds=1)))
    s.commit()

    import asyncio
    from tools.canvas_crud_tool import delete_canvas, restore_deleted_canvas, list_canvases

    def patch_session(sess):
        ctx = Mock()
        ctx.__enter__ = Mock(return_value=sess)
        ctx.__exit__ = Mock(return_value=False)
        return patch("core.database.get_db_session", return_value=ctx)

    with patch_session(s):
        res = asyncio.run(restore_deleted_canvas("u-1", CID))
    assert res["success"], res

    rows = s.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == CID
    ).order_by(CanvasAudit.created_at.desc()).all()
    assert rows[0].action_type == "restore"
    # the new row must carry µs precision and sort strictly past the
    # legacy second-precision tombstone (strict recency on PostgreSQL)
    assert rows[0].created_at > rows[1].created_at
    assert rows[0].created_at.microsecond > 0

    with patch_session(s):
        res = asyncio.run(delete_canvas("u-1", CID))
    assert res["success"], res

    with patch_session(s):
        lst = asyncio.run(list_canvases("u-1"))
    assert all(c["canvas_id"] != CID for c in lst["canvases"])

    with patch_session(s):
        res = asyncio.run(delete_canvas("u-1", CID))
    assert res["success"] and res.get("already_deleted"), res


@pg
def test_pg_idempotent_delete_and_listing(pg_session):
    s, engine = pg_session
    CID = "compat-idem-1"

    s.add(Tenant(id="default", name="compat tenant", subdomain="compat"))
    s.add(User(id="u-1", email="compat2@test.local", first_name="c", last_name="t",
               role="owner", status="active", tenant_id="default"))
    s.add(Canvas(id=CID, tenant_id="default", created_by="u-1", name="idem",
                 canvas_type="document", status="active", content={"content": "x"}))
    s.add(CanvasAudit(canvas_id=CID, tenant_id="default", action_type="create",
                      user_id="u-1", canvas_type="document",
                      details_json={"content": {"content": "x"}}))
    s.commit()

    import asyncio
    from tools.canvas_crud_tool import delete_canvas, list_canvases

    def patch_session(sess):
        ctx = Mock()
        ctx.__enter__ = Mock(return_value=sess)
        ctx.__exit__ = Mock(return_value=False)
        return patch("core.database.get_db_session", return_value=ctx)

    with patch_session(s):
        r1 = asyncio.run(delete_canvas("u-1", CID))
        assert r1["success"] and not r1.get("already_deleted")
        # idempotent double-delete on PostgreSQL
        r2 = asyncio.run(delete_canvas("u-1", CID))
        assert r2["success"] and r2.get("already_deleted")

    with patch_session(s):
        lst = asyncio.run(list_canvases("u-1"))
    assert all(c["canvas_id"] != CID for c in lst["canvases"])
