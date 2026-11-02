"""Canvas presentation postconditions bind exact material and operation identity."""
from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import CanvasAudit
from core.oracle import validate
from core.presentation_material import material_sha256, presentation_material
import core.oracle.postcondition_verifiers  # noqa: F401


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory()


def _audit(
    db, canvas_id="canvas-oracle", *, audit_id="audit-1",
    action_type="present", component_type="markdown",
    operation_id="op-1", material=None, workspace_id="default",
    tenant_id="tenant-oracle",
):
    material = material if material is not None else presentation_material(
        "canvas.present_markdown", {"content": "APPROVED total 350.00"})
    db.add(CanvasAudit(
        id=audit_id,
        tenant_id=tenant_id,
        canvas_id=canvas_id,
        action_type=action_type,
        details_json={
            "component_type": component_type,
            "title": "Quote",
            "material": material,
            "material_sha256": material_sha256(material),
            "operation_id": operation_id,
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
        },
    ))
    db.commit()


def _ctx(db, canvas_id="canvas-oracle", audit_id="audit-1",
         content="APPROVED total 350.00", operation_id="op-1",
         action="canvas.present_markdown"):
    material = presentation_material(action, {"content": content})
    return {
        "db": db,
        "canvas_id": canvas_id,
        "audit_id": audit_id,
        "_oracle_expected_operation_id": operation_id,
        "_oracle_expected_material_sha256": material_sha256(material),
        "_oracle_expected_workspace_id": "default",
        "_oracle_expected_tenant_id": "tenant-oracle",
    }


def test_exact_material_and_operation_verifies():
    engine, db = _session()
    try:
        _audit(db)
        result = asyncio.run(validate(
            "canvas.present_markdown", _ctx(db)))
        assert result is not None and result.verified is True, result
        assert "material=" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_missing_audit_row_is_a_refutation_not_a_pass():
    engine, db = _session()
    try:
        result = asyncio.run(validate(
            "canvas.present_markdown", _ctx(db, audit_id="missing")))
        assert result is not None and result.verified is False
        assert "not found" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_component_mismatch_is_a_refutation():
    engine, db = _session()
    try:
        _audit(db, component_type="chart",
               material={"kind": "chart", "chart_type": "bar_chart",
                         "data": [{"x": "A", "y": 350}]})
        result = asyncio.run(validate(
            "canvas.present_markdown", _ctx(db)))
        assert result is not None and result.verified is False
        assert "component_type" in result.evidence
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


def test_wrong_content_with_same_title_is_refuted():
    engine, db = _session()
    try:
        wrong = presentation_material(
            "canvas.present_markdown", {"content": "WRONG total 999.00"})
        _audit(db, material=wrong)
        result = asyncio.run(validate(
            "canvas.present_markdown", _ctx(db)))
        assert result is not None and result.verified is False
        assert "authorized request" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_wrong_chart_values_with_same_count_are_refuted():
    engine, db = _session()
    try:
        approved = presentation_material(
            "canvas.present_chart",
            {"chart_type": "bar_chart", "data": [{"x": "A", "y": 350}]})
        wrong = presentation_material(
            "canvas.present_chart",
            {"chart_type": "bar_chart", "data": [{"x": "A", "y": 999}]})
        _audit(db, component_type="chart", material=wrong)
        ctx = {
            "db": db, "canvas_id": "canvas-oracle", "audit_id": "audit-1",
            "_oracle_expected_operation_id": "op-1",
            "_oracle_expected_material_sha256": material_sha256(approved),
            "_oracle_expected_workspace_id": "default",
            "_oracle_expected_tenant_id": "tenant-oracle",
        }
        result = asyncio.run(validate("canvas.present_chart", ctx))
        assert result is not None and result.verified is False
        assert "authorized request" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_old_audit_with_identical_content_cannot_certify_new_operation():
    engine, db = _session()
    try:
        _audit(db, operation_id="old-operation")
        ctx = _ctx(db, operation_id="new-operation")
        result = asyncio.run(validate("canvas.present_markdown", ctx))
        assert result is not None and result.verified is False
        assert "operation_id" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_missing_material_cannot_verify():
    engine, db = _session()
    try:
        db.add(CanvasAudit(
            id="audit-no-material", tenant_id="tenant-oracle",
            canvas_id="canvas-oracle", action_type="present",
            details_json={"component_type": "markdown", "operation_id": "op-1",
                          "workspace_id": "default",
                          "tenant_id": "tenant-oracle"},
        ))
        db.commit()
        result = asyncio.run(validate(
            "canvas.present_markdown",
            _ctx(db, audit_id="audit-no-material")))
        assert result is not None and result.verified is False
        assert "no material" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_wrong_workspace_is_refuted():
    engine, db = _session()
    try:
        _audit(db, workspace_id="other-workspace")
        result = asyncio.run(validate(
            "canvas.present_markdown", _ctx(db)))
        assert result is not None and result.verified is False
        assert "workspace" in result.evidence
    finally:
        db.close()
        engine.dispose()


def test_exact_audit_id_wins_over_a_newer_latest_row():
    engine, db = _session()
    try:
        _audit(db, audit_id="audit-old", operation_id="op-old")
        _audit(db, audit_id="audit-new", operation_id="op-new")
        result = asyncio.run(validate(
            "canvas.present_markdown",
            _ctx(db, audit_id="audit-old", operation_id="op-old")))
        assert result is not None and result.verified is True, result
    finally:
        db.close()
        engine.dispose()


def test_chart_positive_binds_all_values():
    engine, db = _session()
    try:
        material = presentation_material(
            "canvas.present_chart",
            {"chart_type": "bar_chart", "data": [{"x": "A", "y": 350}]})
        _audit(db, component_type="chart", material=material)
        ctx = {
            "db": db, "canvas_id": "canvas-oracle", "audit_id": "audit-1",
            "_oracle_expected_operation_id": "op-1",
            "_oracle_expected_material_sha256": material_sha256(material),
            "_oracle_expected_workspace_id": "default",
            "_oracle_expected_tenant_id": "tenant-oracle",
        }
        result = asyncio.run(validate("canvas.present_chart", ctx))
        assert result is not None and result.verified is True, result
    finally:
        db.close()
        engine.dispose()
