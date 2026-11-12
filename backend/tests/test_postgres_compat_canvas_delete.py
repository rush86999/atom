"""PostgreSQL compatibility for the canvas delete/restore flows.

The local dev backend runs SQLite, but deployments run PostgreSQL. The
delete/restore semantics (strict recency, idempotent double-delete,
listing exclusion) must behave IDENTICALLY on both. These tests run the
full scenario against a real throwaway PostgreSQL database and SKIP when
no disposable cluster is explicitly configured — they exist to catch
dialect-specific regressions (timestamp precision, timezone handling,
window ordering).

Explicit, disposable configuration
----------------------------------
There is deliberately NO default connection. The suite never assumes a
workstation-local server, never guesses a username, and never starts
Docker. Point it at a throwaway cluster with:

``ATOM_COMPAT_PG_ADMIN_DSN``
    SQLAlchemy URL for the cluster's maintenance database. Use a Unix
    socket to keep the run off the network, e.g.::

        postgresql+psycopg2://compat@/postgres?host=/tmp/pg-compat/socket

    The URL is only read from the environment; nothing connects until
    the fixture runs.

``ATOM_COMPAT_PG_TEST_DB``
    Base name for the scratch database this suite creates and drops.
    Defaults to ``atom_compat_test``. Every fixture run appends a random
    suffix, so an existing database is never reused or pre-dropped. The
    base must be a plain SQL identifier, must not be the admin database,
    a PostgreSQL system database, or a name that does not look disposable
    (``test``/``compat``/``scratch``/``tmp``).

If ``ATOM_COMPAT_PG_ADMIN_DSN`` is unset the tests skip. If it is set but
unusable they FAIL — an explicit opt-in should not silently degrade into
a skipped compatibility check.

Nothing is dropped before ``CREATE DATABASE``. If a database with the
chosen scratch name already exists, the run fails and leaves that
database untouched; cleanup only drops the database this run created.

The shared ``tests/fixtures/postgresql.py`` fixture is intentionally not
reused: it defaults to a fixed TCP loopback endpoint and may run Docker
Compose, which is exactly what a disposable, never-touch-the-workstation
run must not do.
"""

import datetime as dt
import os
import re
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from core.database import Base
from core.models import Canvas, CanvasAudit, Tenant, User

_ADMIN_DSN_ENV = "ATOM_COMPAT_PG_ADMIN_DSN"
_TEST_DB_ENV = "ATOM_COMPAT_PG_TEST_DB"
_DEFAULT_TEST_DB = "atom_compat_test"

# Never drop one of these, whatever the environment says.
_SYSTEM_DATABASES = frozenset({"postgres", "template0", "template1"})
# A scratch database must look disposable; this is a seat belt against a
# typo pointing the fixture at a real database on an explicitly supplied
# cluster.
_DISPOSABLE_DB_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DISPOSABLE_HINTS = ("test", "compat", "scratch", "tmp", "temp")

# PostgreSQL silently truncates identifiers longer than this many bytes.
_PG_IDENTIFIER_MAX_BYTES = 63


def _unique_scratch_db_name(base: str) -> str:
    """Return a per-run scratch database name that is unlikely to collide.

    The suffix keeps the configured base recognisable while making a
    pre-existing database (e.g. a leftover from a crashed run) a loud
    collision instead of something this fixture silently drops.
    """
    suffix = f"_{uuid.uuid4().hex[:12]}"
    return f"{base[: _PG_IDENTIFIER_MAX_BYTES - len(suffix)]}{suffix}"


def _compat_pg_configured() -> bool:
    return bool(os.environ.get(_ADMIN_DSN_ENV, "").strip())


def _compat_pg_urls():
    """Return ``(admin_url, test_db_base)`` from explicit config.

    Parsing happens per-test (not at import) so a missing/invalid value
    raises a useful, located failure instead of a collection error. The
    actual scratch database name is derived per run by
    ``_unique_scratch_db_name``.
    """
    raw_admin = os.environ.get(_ADMIN_DSN_ENV, "").strip()
    if not raw_admin:
        pytest.skip(
            f"{_ADMIN_DSN_ENV} is not set; no disposable PostgreSQL "
            "cluster was explicitly configured"
        )

    try:
        admin_url = make_url(raw_admin)
    except ArgumentError as exc:
        pytest.fail(f"{_ADMIN_DSN_ENV} is not a valid SQLAlchemy URL: {exc}")

    if admin_url.get_backend_name() != "postgresql":
        pytest.fail(
            f"{_ADMIN_DSN_ENV} must be a PostgreSQL URL, got "
            f"{admin_url.drivername!r}"
        )
    if admin_url.drivername == "postgresql":
        # Pin the installed driver rather than relying on SQLAlchemy's
        # default selection.
        admin_url = admin_url.set(drivername="postgresql+psycopg2")

    test_db = (
        os.environ.get(_TEST_DB_ENV, _DEFAULT_TEST_DB).strip()
        or _DEFAULT_TEST_DB
    )
    admin_db = admin_url.database or "postgres"

    if not _DISPOSABLE_DB_RE.match(test_db):
        pytest.fail(
            f"{_TEST_DB_ENV}={test_db!r} must be a plain SQL identifier "
            "(letters, digits, underscore; must not start with a digit)"
        )
    if test_db == admin_db:
        pytest.fail(
            f"{_TEST_DB_ENV}={test_db!r} must differ from the admin "
            f"database {admin_db!r}"
        )
    if test_db.lower() in _SYSTEM_DATABASES:
        pytest.fail(f"{_TEST_DB_ENV}={test_db!r} is a PostgreSQL system database")
    if not any(hint in test_db.lower() for hint in _DISPOSABLE_HINTS):
        pytest.fail(
            f"{_TEST_DB_ENV}={test_db!r} does not look disposable "
            f"(expected one of {_DISPOSABLE_HINTS}); refusing to drop it"
        )

    admin_url = admin_url.set(database=admin_db)
    return admin_url, test_db


def _create_schema(engine):
    """Create the full model schema, tolerating a cluster without pgvector.

    ``Base.metadata.create_all`` is all-or-nothing, so on a cluster with
    the Python pgvector package installed but the SQL extension missing
    we fall back to creating tables one by one and skip only the
    vector-dependent ones. The canvas tables never require pgvector.
    """
    try:
        Base.metadata.create_all(engine)
        return
    except Exception as exc:  # noqa: BLE001 - inspect the dialect error
        if "vector" not in str(exc).lower():
            raise

    created = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
            created += 1
        except Exception as exc:  # noqa: BLE001
            if "vector" in str(exc).lower():
                continue
            raise
    if not created:
        raise RuntimeError("no model tables could be created on PostgreSQL")


def _drop_scratch_database(admin_url, test_db):
    """Drop the scratch database through its explicitly configured admin URL."""
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db}"'))
    finally:
        admin.dispose()


@pytest.fixture
def pg_session():
    """Create a dedicated scratch database, yield a session, then drop it.

    The base name comes only from explicit configuration and is validated
    in ``_compat_pg_urls``; a random suffix makes the actual database
    unique per run. Nothing is dropped before ``CREATE DATABASE``, and
    cleanup runs only when this fixture created the database itself, so a
    pre-existing collision fails loudly instead of destroying that data.
    """
    admin_url, test_db_base = _compat_pg_urls()
    test_db = _unique_scratch_db_name(test_db_base)
    test_url = admin_url.set(database=test_db)

    created = False
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{test_db}"'))
        created = True
    except Exception as exc:  # noqa: BLE001 - surface as a test failure
        pytest.fail(
            f"could not create scratch PostgreSQL database {test_db!r} via "
            f"{_ADMIN_DSN_ENV}: {exc}"
        )
    finally:
        admin.dispose()

    engine = create_engine(test_url)
    try:
        _create_schema(engine)
        # Guard against URL rewriting/typos silently aiming at another DB.
        with engine.connect() as conn:
            actual_db = conn.execute(text("SELECT current_database()")).scalar()
        assert actual_db == test_db, (
            f"connected to {actual_db!r}, expected scratch database {test_db!r}"
        )

        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as session:
            yield session, engine
    finally:
        engine.dispose()
        if created:
            _drop_scratch_database(admin_url, test_db)


pg = pytest.mark.skipif(
    not _compat_pg_configured(),
    reason=(
        f"{_ADMIN_DSN_ENV} is not set; no disposable PostgreSQL cluster "
        "was explicitly configured"
    ),
)


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
