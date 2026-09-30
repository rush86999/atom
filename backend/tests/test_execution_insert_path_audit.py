"""Audit: does every production insert of an AgentExecution get an owner?

WHY THIS IS A TEST AND NOT A COMMENT
The boot sweep's whole safety argument rests on one thing: every running row
carries an owner it can check. A single insert that bypasses the mapper event
produces a row that is permanently UNKNOWN -- and under the current policy an
UNKNOWN row is deliberately never reconciled, so that path's turns would stay
`running` forever. That is the correct failure direction (never fail a live
turn) and also a silent one, so the bypass needs to be caught mechanically.

The stamp is applied by a `before_insert` mapper listener on `AgentExecution`, so
the paths that defeat it are the ones that never build an ORM instance:
`__table__.insert()`, `session.execute(insert(...))`, `bulk_insert_mappings`,
`bulk_save_objects`, `copy_from`, and raw `INSERT INTO agent_executions` SQL.

This scans the production tree only. Test fixtures legitimately build rows
directly, and `tests/` is where the negative controls live -- including the ones
that need an unstamped row to exist at all.

A note on what this does NOT cover: a row written by an older build, or copied
in from a database snapshot, has no owner either, and no amount of scanning
finds that. Those rows are exactly the `missing_stamp` UNKNOWN case, and the
policy for them is "reported, never reconciled".
"""
from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

#: (label, regex). Each is a way to write a row without an ORM instance, i.e.
#: without the mapper listener.
BYPASS_PATTERNS = (
    ("table_insert", re.compile(r"AgentExecution\.__table__\.insert")),
    ("core_insert", re.compile(r"\bexecute\(\s*insert\s*\(")),
    ("bulk_insert_mappings", re.compile(r"bulk_insert_mappings\s*\(")),
    ("bulk_save_objects", re.compile(r"bulk_save_objects\s*\(")),
    ("copy_from", re.compile(r"copy_from\s*=")),
    ("raw_sql_insert", re.compile(r"INSERT\s+INTO\s+agent_executions", re.I)),
)

SCANNED_DIRS = ("core", "integrations", "api", "ai", "tools", "services")


def _production_files():
    for name in SCANNED_DIRS:
        root = BACKEND / name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or ".archive" in path.parts:
                continue
            yield path
    # the app entry point lives at the backend root
    for path in BACKEND.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        yield path


def test_no_production_insert_path_bypasses_the_owner_stamp():
    hits = []
    for path in _production_files():
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for label, pattern in BYPASS_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{path.relative_to(BACKEND)}:{line} [{label}]")
    assert not hits, (
        "insert path(s) that bypass the AgentExecution owner stamp were found. "
        "Their rows can never be attributed, so the boot sweep will leave them "
        "running forever as UNKNOWN:\n  " + "\n  ".join(hits))


def test_the_listener_is_actually_registered_and_fires():
    """A scan that passes because the listener is gone would be worthless.

    Checked two ways on purpose: the registry says it is attached, AND an actual
    insert comes out stamped. The second is the one that matters -- SQLAlchemy's
    introspection surface has moved between versions, and a check that only
    reads it can fail on a rename while the product is fine, or pass on a stale
    attribute while the product is broken.
    """
    from core.models import AgentExecution, _stamp_execution_owner
    from sqlalchemy import event

    assert event.contains(AgentExecution, "before_insert", _stamp_execution_owner), (
        "the owner stamp is not registered as a before_insert listener on "
        "AgentExecution")

    import os
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.models_registration import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        row = AgentExecution(id=str(uuid.uuid4()), status="running",
                             triggered_by="audit")
        session.add(row)
        session.commit()
        owner = (row.metadata_json or {}).get("owner")
        assert owner and owner.get("pid") == os.getpid(), (
            "an insert came out without an owner: the listener is registered but "
            "did not fire")
    finally:
        session.close()
        engine.dispose()
