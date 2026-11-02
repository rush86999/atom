"""The canvas postcondition oracle reads the audit system of record.

The tool's own success flag is not evidence: only a durable audit row for the
presented canvas may verify the mutation. Missing or mismatched rows refute.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import CanvasAudit
from core.oracle import validate


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory()


def _audit(db, canvas_id="canvas-oracle", *, action_type="present",
           component_type="markdown"):
    db.add(CanvasAudit(
        id=f"audit-{canvas_id}-{component_type}",
        tenant_id="tenant-oracle",
        canvas_id=canvas_id,
        action_type=action_type,
        details_json={"component_type": component_type},
    ))
    db.commit()


def test_audit_row_verifies_the_presented_canvas():
    engine, db = _session()
    try:
        _audit(db)
        result = asyncio.run(validate(
            "canvas.present_markdown",
            {"canvas_id": "canvas-oracle", "db": db}))
        assert result is not None and result.verified is True
        assert "canvas_audit" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_missing_audit_row_is_a_refutation_not_a_pass():
    engine, db = _session()
    try:
        result = asyncio.run(validate(
            "canvas.present_markdown",
            {"canvas_id": "never-presented", "db": db}))
        assert result is not None and result.verified is False
        assert "no canvas_audit row" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_component_mismatch_is_a_refutation():
    engine, db = _session()
    try:
        _audit(db, "canvas-chart", component_type="chart")
        result = asyncio.run(validate(
            "canvas.present_markdown",
            {"canvas_id": "canvas-chart", "db": db}))
        assert result is not None and result.verified is False
        assert "component_type='chart'" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_missing_identity_is_unavailable_not_applied():
    engine, db = _session()
    try:
        result = asyncio.run(validate("canvas.present_markdown", {"db": db}))
        assert result is not None and result.verified is False
        assert "missing canvas_id" in result.evidence
    finally:
        db.close()
        engine.dispose()
