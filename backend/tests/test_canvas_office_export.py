"""Public-route controls for generated Canvas DOCX/PPTX export.

Scratch SQLite only. Real Canvas authority, real office renderers, public route.
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pptx import Presentation
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.canvas_routes import router
from core.auth import create_access_token, get_current_user
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.models import Canvas, CanvasAudit, Tenant, User, Workspace


class World:
    def __init__(self, tmp_path):
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/canvas-export.db",
            connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8]
        self.tenant = f"tenant-{suffix}"
        self.ws = f"ws-{suffix}"
        self.user = f"user-{suffix}"
        self.peer = f"peer-{suffix}"
        with self.Session() as db:
            db.add(Tenant(id=self.tenant, name="T", subdomain=f"t-{suffix}",
                          edition="personal", is_active=True))
            db.add(Workspace(id=self.ws, name="W", tenant_id=self.tenant))
            for uid, role in ((self.user, "member"), (self.peer, "member")):
                db.add(User(
                    id=uid, tenant_id=self.tenant, workspace_id=self.ws,
                    email=f"{uid}@example.com", hashed_password="x",
                    first_name="U", last_name="Ser", role=role,
                    status="active", is_active=True))
            db.commit()

    def token(self, uid):
        with self.Session() as db:
            user = db.query(User).filter(User.id == uid).one()
            return create_access_token({"sub": user.id}, user=user)

    def create_canvas(self, *, canvas_type="docs", title="Spec",
                      content="# Heading\n\nIntro.\n\n- One\n- Two\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
                      review_status="accepted"):
        canvas_id = f"canvas-{uuid.uuid4().hex[:10]}"
        audit_id = f"audit-{uuid.uuid4().hex[:10]}"
        with self.Session() as db:
            db.add(Canvas(
                id=canvas_id, tenant_id=self.tenant, workspace_id=self.ws,
                created_by=self.user, name=title, canvas_type=canvas_type,
                content={"title": title, "content": content},
                status="active"))
            db.add(CanvasAudit(
                id=audit_id, canvas_id=canvas_id, tenant_id=self.tenant,
                user_id=self.user, canvas_type=canvas_type,
                action_type="update",
                details_json={
                    "title": title, "content": content,
                    "review_status": review_status,
                }))
            db.commit()
        return canvas_id, audit_id

    def client(self, user_id=None):
        app = FastAPI()
        app.include_router(router)
        actor_id = user_id or self.user

        def override_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        async def override_user():
            db = self.Session()
            try:
                return db.query(User).filter(User.id == actor_id).one()
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[require_pilot_user] = lambda: None
        return TestClient(app)


def _export(client, canvas_id, fmt="docx", **params):
    return client.get(
        f"/api/canvas/{canvas_id}/export/office",
        params={"format": fmt, **params})


def test_generated_document_exports_real_docx_with_stable_bytes(world):
    canvas_id, audit_id = world.create_canvas()
    client = world.client()
    first = _export(client, canvas_id, "docx",
                    expected_audit_id=audit_id)
    assert first.status_code == 200, first.text
    assert first.headers["etag"] == (
        '"sha256:' + hashlib.sha256(first.content).hexdigest() + '"')
    assert first.headers["content-disposition"].endswith('.docx"')
    document = Document(io.BytesIO(first.content))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Intro." in text
    assert any((p.style.name or "").lower().startswith("heading")
               for p in document.paragraphs if p.text.strip())
    assert any("list bullet" in (p.style.name or "").lower()
               for p in document.paragraphs if p.text.strip())
    assert len(document.tables) == 1
    assert first.headers["x-atom-source-audit-id"] == audit_id
    assert first.headers["x-atom-output-sha256"] == (
        hashlib.sha256(first.content).hexdigest())

    second = _export(client, canvas_id, "docx",
                     expected_audit_id=audit_id)
    assert second.status_code == 200
    assert second.content == first.content


def test_generated_presentation_exports_real_pptx(world):
    content = (
        "Slide 1: Opening\n- Alpha\n- Beta\nNotes: speaker note\n\n"
        "Slide 2: Numbers\n| A | B |\n|---|---|\n| 1 | 2 |\n")
    canvas_id, audit_id = world.create_canvas(
        canvas_type="markdown", title="Deck", content=content)
    client = world.client()
    response = _export(client, canvas_id, "pptx",
                       expected_audit_id=audit_id)
    assert response.status_code == 200, response.text
    presentation = Presentation(io.BytesIO(response.content))
    assert len(presentation.slides) == 2
    titles = []
    for slide in presentation.slides:
        title_shape = slide.shapes.title
        titles.append(title_shape.text if title_shape is not None else "")
    assert titles == ["Opening", "Numbers"]
    assert any(slide.has_notes_slide
               and slide.notes_slide.notes_text_frame.text.strip()
               for slide in presentation.slides)


def test_export_refuses_stale_foreign_withheld_empty_and_wrong_format(world):
    canvas_id, audit_id = world.create_canvas()
    client = world.client()

    stale = _export(client, canvas_id, "docx",
                    expected_audit_id="different-audit")
    assert stale.status_code == 409
    assert stale.json()["detail"]["error"] == "canvas_source_changed"

    # Foreign user is denied by the existing Canvas authority adapter.
    foreign = _export(world.client(world.peer), canvas_id, "docx")
    assert foreign.status_code in (403, 404), foreign.text

    # Withheld review state.
    withheld_id, withheld_audit = world.create_canvas(
        title="Withheld", review_status="pending_review")
    withheld = _export(client, withheld_id, "docx",
                       expected_audit_id=withheld_audit)
    assert withheld.status_code == 409
    assert withheld.json()["detail"]["error"] == "canvas_export_withheld"

    empty_id, empty_audit = world.create_canvas(title="Empty", content="")
    empty = _export(client, empty_id, "docx",
                    expected_audit_id=empty_audit)
    assert empty.status_code == 409
    assert empty.json()["detail"]["error"] == "canvas_export_empty"

    wrong = _export(client, canvas_id, "pptx",
                    expected_audit_id=audit_id)
    assert wrong.status_code == 409
    assert wrong.json()["detail"]["error"] == (
        "canvas_export_format_unsupported")


def test_export_stable_in_fresh_child_process(world, tmp_path):
    canvas_id, audit_id = world.create_canvas()
    parent = _export(world.client(), canvas_id, "docx",
                     expected_audit_id=audit_id)
    assert parent.status_code == 200
    helper = Path(__file__).resolve().parent / "helpers" / "canvas_office_export_child.py"
    env = os.environ.copy()
    env.update({
        "TESTING": "1",
        "PYTEST_VERSION": "canvas-export-child",
        "DATABASE_URL": str(world.engine.url),
        "ATOM_OFFICE_DIR": str(tmp_path / "office-child"),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1])
        + os.pathsep + env.get("PYTHONPATH", ""),
    })
    completed = subprocess.run(
        [sys.executable, str(helper), str(world.engine.url), canvas_id,
         audit_id, world.user, world.tenant, world.ws, "docx"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, (
        completed.stdout + "\n" + completed.stderr)
    payload = json.loads(
        completed.stdout.splitlines()[-1].split("RESULT_JSON:", 1)[1])
    print("PARENT_EXPORT", len(parent.content),
          hashlib.sha256(parent.content).hexdigest(),
          parent.headers.get("x-atom-output-sha256"))
    print("CHILD_EXPORT", payload)
    assert payload["sha256"] == hashlib.sha256(parent.content).hexdigest()
    assert payload["status"] == 200


def test_presentation_stable_in_fresh_child_process(world, tmp_path):
    content = (
        "Slide 1: Opening\n- Alpha\n- Beta\nNotes: speaker note one\n\n"
        "Slide 2: Numbers\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        "Notes: speaker note two")
    canvas_id, audit_id = world.create_canvas(
        canvas_type="markdown", title="Fresh Deck", content=content)
    parent = _export(world.client(), canvas_id, "pptx",
                     expected_audit_id=audit_id)
    assert parent.status_code == 200, parent.text
    from pptx import Presentation as PptxPresentation
    deck = PptxPresentation(io.BytesIO(parent.content))
    assert len(deck.slides) == 2
    titles = [s.shapes.title.text if s.shapes.title is not None else ""
              for s in deck.slides]
    assert titles == ["Opening", "Numbers"]
    assert any("Alpha" in shape.text_frame.text
               for shape in deck.slides[0].shapes
               if getattr(shape, "has_text_frame", False))
    table = next(shape.table for shape in deck.slides[1].shapes
                 if getattr(shape, "has_table", False))
    assert [[c.text for c in row.cells] for row in table.rows] == [
        ["A", "B"], ["1", "2"]]
    assert "speaker note one" in deck.slides[0].notes_slide.notes_text_frame.text
    assert "speaker note two" in deck.slides[1].notes_slide.notes_text_frame.text

    before_audits = None
    with world.Session() as db:
        before_audits = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).count()
    helper = Path(__file__).resolve().parent / "helpers" / "canvas_office_export_child.py"
    env = os.environ.copy()
    env.update({
        "TESTING": "1",
        "PYTEST_VERSION": "canvas-export-pptx-child",
        "DATABASE_URL": str(world.engine.url),
        "ATOM_OFFICE_DIR": str(tmp_path / "office-child-pptx"),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1])
        + os.pathsep + env.get("PYTHONPATH", ""),
    })
    completed = subprocess.run(
        [sys.executable, str(helper), str(world.engine.url), canvas_id,
         audit_id, world.user, world.tenant, world.ws, "pptx"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, (
        completed.stdout + "\n" + completed.stderr)
    payload = json.loads(
        completed.stdout.splitlines()[-1].split("RESULT_JSON:", 1)[1])
    assert payload["sha256"] == hashlib.sha256(parent.content).hexdigest()
    assert payload["format"] == "pptx"
    assert payload["slide_count"] == 2
    assert [item["title"] for item in payload["slides"]] == [
        "Opening", "Numbers"]
    assert "Alpha" in payload["slides"][0]["body"]
    assert payload["slides"][1]["tables"] == [
        [["A", "B"], ["1", "2"]]]
    assert "speaker note one" in payload["slides"][0]["notes"]
    assert payload["model_calls"] is False
    with world.Session() as db:
        after_audits = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).count()
    assert after_audits == before_audits


def test_default_office_dir_is_anchored_across_launch_cwd(world, monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("ATOM_OFFICE_DIR", raising=False)
    canvas_id, audit_id = world.create_canvas()

    monkeypatch.chdir(repo_root)
    root_export = _export(world.client(), canvas_id, "docx",
                          expected_audit_id=audit_id)
    assert root_export.status_code == 200, root_export.text

    monkeypatch.chdir(backend_dir)
    backend_export = _export(world.client(), canvas_id, "docx",
                             expected_audit_id=audit_id)
    assert backend_export.status_code == 200, backend_export.text
    assert backend_export.content == root_export.content


@pytest.fixture()
def world(tmp_path):
    return World(tmp_path)


def test_export_rechecks_source_and_retries_on_concurrent_save(world, monkeypatch):
    import api.canvas_routes as canvas_routes

    canvas_id, audit_id = world.create_canvas()
    original_validate = canvas_routes._validate_docx_package

    def mutate_then_validate(body, source_text, title=None):
        original_validate(body, source_text, title)
        with world.Session() as db:
            db.add(CanvasAudit(
                id=f"audit-{uuid.uuid4().hex[:10]}", canvas_id=canvas_id,
                tenant_id=world.tenant, user_id=world.user,
                canvas_type="docs", action_type="update",
                details_json={
                    "title": "Spec",
                    "content": "# Concurrent edit",
                    "review_status": "accepted",
                }))
            db.commit()

    monkeypatch.setattr(canvas_routes, "_validate_docx_package",
                        mutate_then_validate)
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "canvas_source_changed"


def test_export_has_no_canvas_or_business_write_effect(world):
    canvas_id, audit_id = world.create_canvas()
    with world.Session() as db:
        before = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).count()
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 200
    with world.Session() as db:
        after = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).count()
    assert after == before


def test_validators_refuse_wrong_same_shape_docx_and_missing_pptx_body():
    import api.canvas_routes as canvas_routes
    from docx import Document as DocxDocument
    from pptx import Presentation as PptxPresentation

    wrong_docx = DocxDocument()
    wrong_docx.add_heading("Wrong title", level=1)
    wrong_docx.add_paragraph("Wrong bullet", style="List Bullet")
    table = wrong_docx.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Wrong"
    table.cell(0, 1).text = "Shape"
    table.cell(1, 0).text = "9"
    table.cell(1, 1).text = "8"
    buffer = io.BytesIO()
    wrong_docx.save(buffer)
    with pytest.raises(ValueError):
        canvas_routes._validate_docx_package(
            buffer.getvalue(),
            "# Expected title\n\n- Expected bullet\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n",
            "Expected title",
        )

    missing_body = PptxPresentation()
    slide = missing_body.slides.add_slide(missing_body.slide_layouts[5])
    slide.shapes.title.text = "Opening"
    pptx_buffer = io.BytesIO()
    missing_body.save(pptx_buffer)
    with pytest.raises(ValueError):
        canvas_routes._validate_pptx_package(
            pptx_buffer.getvalue(),
            "Slide 1: Opening\n- Required body\nNotes: required note\n",
        )


def test_export_renderer_error_never_echoes_local_paths(world, monkeypatch):
    from core.office_service import WordManager

    def leaky_renderer(*args, **kwargs):
        return {"success": False,
                "error": "/private/secret/office/token.txt: permission denied"}

    monkeypatch.setattr(
        WordManager, "create_from_markdown", leaky_renderer)
    canvas_id, audit_id = world.create_canvas()
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 422
    detail = response.json()["detail"]
    body = json.dumps(detail)
    assert "/private/" not in body
    assert "token" not in body.lower()
    assert detail["error"] == "canvas_export_render_failed"
    assert detail["stage"] == "render"


def _set_audit_details(world, canvas_id, **values):
    with world.Session() as db:
        row = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).one()
        details = dict(row.details_json or {})
        details.update(values)
        row.details_json = details
        db.commit()


def _requirement():
    return {
        "requirement_id": "result-quote-1",
        "operation": "quote_calculation",
        "subject": "PO-0090",
        "label": "quote calculation",
    }


def _job_services(world):
    from core.assignment_executor import AssignmentExecutor
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    runs = GoalRunService(
        workspace_id=world.ws, tenant_id=world.tenant,
        session_factory=world.Session)
    goals = GoalService(
        workspace_id=world.ws, tenant_id=world.tenant,
        session_factory=world.Session)
    lifecycle = TaskLifecycle(runs, goals)
    return lifecycle, AssignmentExecutor(lifecycle)


def _quote_step():
    from core.assignment_plan import new_step

    return new_step(
        step_id="calculate",
        title="Calculate the quote",
        operation_type="calculate",
        adapter="quote.calculate",
        inputs={
            "line_items": [{
                "item_id": "B",
                "quantity": "1",
                "unit": "each",
                "pack_size": "1",
                "unit_price": "100.00",
                "price_basis": "contract",
                "currency": "USD",
                "category": "B",
                "source_ref": {
                    "resource_id": "price-list",
                    "source_version": "v1",
                },
            }],
            "currency": "USD",
            "freight": "0",
            "tax": {"basis": "none"},
            "as_of": "2026-11-01",
            "rounding": "half_up",
            "scale": 2,
            "rounding_authority": "customer agreement",
            "source_evidence": [{
                "resource_id": "price-list",
                "source_version": "v1",
            }],
        },
        effect="local",
    )


def _create_real_quote_job(world, canvas_id, *, provenance=None,
                           with_artifact=None, requirements=True):
    from core.assignment_plan import new_assignment, new_deliverable

    lifecycle, executor = _job_services(world)
    steps = [_quote_step()]
    deliverables = []
    if with_artifact is not None:
        from core.assignment_plan import new_step

        steps.append(new_step(
            step_id="deliverable",
            title="Render the quote document",
            operation_type="present",
            adapter="artifact.document",
            depends_on=["calculate"],
            inputs={
                "path": str(with_artifact),
                "title": "Quote",
                "content": (
                    "# Quote\n\nTotal: 100.00 USD.\n"),
            },
            effect="local",
        ))
        deliverables.append(new_deliverable(
            deliverable_id="del-document", kind="document",
            description="quote document", step_id="deliverable"))
    plan = new_assignment(
        objective="Quote for the saved canvas",
        workspace_id=world.ws,
        tenant_id=world.tenant,
        steps=steps,
        deliverables=deliverables,
        business_requirements=(
            [{
                "requirement_id": "result-quote-1",
                "operation": "quote_calculation",
                "subject": "PO-0090",
                "label": "quote calculation",
            }] if requirements else []
        ),
        authorized_actions=["calculate", "present"],
        provenance={
            "canvas_id": canvas_id,
            "requester_id": world.user,
            **(provenance or {}),
        },
    )
    created = executor.create_assignment(
        f"conv-{canvas_id}", "Quote for the saved canvas", assignment=plan)
    import asyncio
    started = asyncio.run(executor.execute(created["run_id"]))
    return lifecycle, created["run_id"], started


def _bind_canvas_to_run(world, canvas_id, run_id):
    with world.Session() as db:
        db.query(Canvas).filter(Canvas.id == canvas_id).update(
            {"goal_run_id": run_id}, synchronize_session=False)
        db.commit()


def test_export_refuses_unresolved_assignment_business_result(world):
    canvas_id, audit_id = world.create_canvas()
    from core.assignment_plan import new_assignment

    lifecycle, executor = _job_services(world)
    plan = new_assignment(
        objective="Unfinished quote",
        workspace_id=world.ws, tenant_id=world.tenant,
        steps=[_quote_step()],
        authorized_actions=["calculate"],
        business_requirements=[{
            "requirement_id": "result-quote-1",
            "operation": "quote_calculation",
            "subject": "PO-0090",
            "label": "quote calculation",
        }],
        provenance={"canvas_id": canvas_id, "requester_id": world.user},
    )
    created = executor.create_assignment(
        f"conv-{canvas_id}", "Unfinished quote", assignment=plan)
    _bind_canvas_to_run(world, canvas_id, created["run_id"])
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "canvas_export_business_result_required")
    assert response.headers.get("x-atom-business-result") is None


def test_copied_flags_for_a_missing_job_cannot_certify(world):
    canvas_id, audit_id = world.create_canvas()
    _set_audit_details(
        world, canvas_id,
        assignment={
            "run_id": "job-that-does-not-exist",
            "business_requirements": [{
                "requirement_id": "result-quote-1",
                "operation": "quote_calculation",
                "subject": "PO-0090",
                "label": "quote calculation",
            }],
            "steps": [{
                "step_id": "quote-step-1",
                "adapter": "quote.calculate",
                "status": "applied",
                "result": {
                    "value": 1200,
                    "unit": "USD",
                    "verification": {"status": "verified"},
                },
            }],
        },
    )
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "canvas_export_job_binding_required")
    assert response.headers.get("x-atom-business-result") is None


def test_nonempty_business_requirements_cannot_vanish(world):
    canvas_id, audit_id = world.create_canvas()
    _set_audit_details(
        world, canvas_id,
        business_requirements=[{
            "label": "invoice reconciliation",
            "operation": "invoice.reconcile",
            "subject_identity": {"po_id": "PO-0090"},
        }],
        assignment={"run_id": "scratch-job"},
    )
    shadowed = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert shadowed.status_code == 409, shadowed.text
    assert shadowed.headers.get("x-atom-business-result") is None


@pytest.mark.parametrize("shape", ["malformed", "non_list", "unknown",
                                   "contradictory"])
def test_malformed_or_contradictory_business_requirements_fail_closed(
        world, shape):
    canvas_id, audit_id = world.create_canvas()
    requirement = _requirement()
    if shape == "malformed":
        _set_audit_details(
            world, canvas_id, business_requirements=[None])
    elif shape == "non_list":
        _set_audit_details(
            world, canvas_id, business_requirements={"operation":
                                                     "quote_calculation"})
    elif shape == "unknown":
        _set_audit_details(
            world, canvas_id,
            business_requirements=[{
                "requirement_id": "result-invoice-1",
                "operation": "invoice.reconcile",
                "subject_identity": {"po_id": "PO-0090"},
            }])
    else:
        _set_audit_details(
            world, canvas_id,
            business_requirements=[requirement],
            assignment={"business_requirements": [{
                **_requirement(),
                "requirement_id": "result-quote-2",
            }]})
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.headers.get("x-atom-business-result") is None
    assert response.json()["detail"]["error"].startswith(
        "canvas_export_business_requirements_")


def test_real_calculation_without_exact_output_binding_is_not_certified(
        world):
    # The decisive root case: a real completed calculation job with a real
    # receipt is bound to the canvas, but the canvas body has no exact
    # output/body/source binding and shows an arbitrary contradictory total.
    canvas_id, audit_id = world.create_canvas(
        content="# Quote\n\nTotal: 9999.00 USD.\n")
    lifecycle, run_id, started = _create_real_quote_job(world, canvas_id)
    assert started["assignment"]["status"] == "completed", started
    assert lifecycle.get_assignment(run_id)["status"] == "completed"
    _bind_canvas_to_run(world, canvas_id, run_id)
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "canvas_export_output_binding_required")
    assert response.headers.get("x-atom-business-result") is None


def test_real_executor_artifact_exports_as_verified(
        world, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    canvas_content = "# Quote\n\nTotal: 100.00 USD.\n"
    canvas_id, audit_id = world.create_canvas(
        title="Quote", content=canvas_content)
    _lifecycle, run_id, started = _create_real_quote_job(
        world, canvas_id, with_artifact=tmp_path / "quote.docx")
    assert started["assignment"]["status"] == "completed", started
    _bind_canvas_to_run(world, canvas_id, run_id)
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 200, response.text
    assert response.headers["x-atom-business-result"] == (
        "required_results_verified")
    assert response.headers["x-atom-artifact-scope"] == "assignment_bound"


def test_same_owner_unrelated_job_cannot_certify(world):
    canvas_id, audit_id = world.create_canvas()
    other_canvas, _ = world.create_canvas(title="Other")
    _lifecycle, _run_id, _started = _create_real_quote_job(
        world, other_canvas)
    _set_audit_details(
        world, canvas_id,
        business_requirements=[_requirement()])
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "canvas_export_job_binding_required")


def test_foreign_workspace_job_binding_is_refused(world):
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    from core.assignment_executor import AssignmentExecutor

    canvas_id, audit_id = world.create_canvas()
    world.create_canvas(title="Other")
    runs = GoalRunService(
        workspace_id="foreign-ws", tenant_id="foreign-tenant",
        session_factory=world.Session)
    goals = GoalService(
        workspace_id="foreign-ws", tenant_id="foreign-tenant",
        session_factory=world.Session)
    executor = AssignmentExecutor(TaskLifecycle(runs, goals))
    from core.assignment_plan import new_assignment
    plan = new_assignment(
        objective="Foreign quote",
        workspace_id="foreign-ws", tenant_id="foreign-tenant",
        steps=[_quote_step()],
        authorized_actions=["calculate"],
        provenance={"canvas_id": canvas_id, "requester_id": "foreign"},
    )
    created = executor.create_assignment(
        f"conv-{canvas_id}", "Foreign quote", assignment=plan)
    _bind_canvas_to_run(world, canvas_id, created["run_id"])
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "canvas_export_job_binding_required")


def test_stale_job_source_revision_is_refused(world):
    canvas_id, audit_id = world.create_canvas()
    _lifecycle, run_id, _started = _create_real_quote_job(
        world, canvas_id,
        provenance={"state_revision": 7,
                    "source": {"sha256": "old-source",
                               "source_version": "v-old"}})
    _bind_canvas_to_run(world, canvas_id, run_id)
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == (
        "canvas_export_source_changed")


def test_manual_edit_after_verified_artifact_is_refused(
        world, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    canvas_content = "# Quote\n\nTotal: 100.00 USD.\n"
    canvas_id, audit_id = world.create_canvas(
        title="Quote", content=canvas_content)
    _lifecycle, run_id, started = _create_real_quote_job(
        world, canvas_id, with_artifact=tmp_path / "quote.docx")
    assert started["assignment"]["status"] == "completed", started
    _bind_canvas_to_run(world, canvas_id, run_id)
    verified = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert verified.status_code == 200, verified.text
    assert verified.headers["x-atom-business-result"] == (
        "required_results_verified")

    with world.Session() as db:
        db.add(CanvasAudit(
            id=f"audit-{uuid.uuid4().hex[:10]}", canvas_id=canvas_id,
            tenant_id=world.tenant, user_id=world.user,
            canvas_type="docs", action_type="update",
            details_json={
                "title": "Quote",
                "content": "# Quote\n\nTotal: 900.00 USD.\n",
                "review_status": "accepted",
            }))
        db.commit()
    edited = _export(world.client(), canvas_id, "docx")
    assert edited.status_code == 409, edited.text
    assert edited.json()["detail"]["error"] == (
        "canvas_export_artifact_binding_mismatch")
    assert edited.headers.get("x-atom-business-result") is None


@pytest.mark.parametrize("corruption", ["section_order", "heading_level"])
def test_renderer_cannot_reorder_or_demote_exported_docx(
        world, monkeypatch, corruption):
    from core.office_service import WordManager

    canvas_id, audit_id = world.create_canvas(
        content="# First\n\nSection A.\n\n## Second\n\nSection B.\n")
    original = WordManager.create_from_markdown

    def corrupt(self, path, *args, **kwargs):
        result = original(self, path, *args, **kwargs)
        document = Document(path)
        if corruption == "section_order":
            paragraph = next(
                p for p in document.paragraphs if p.text == "Section A.")
            heading = next(
                p for p in document.paragraphs if p.text == "Second")
            body = document.element.body
            body.remove(paragraph._p)
            body.insert(list(body).index(heading._p) + 1, paragraph._p)
        else:
            next(p for p in document.paragraphs
                 if p.text == "Second").style = document.styles["Heading 1"]
        document.save(path)
        return result

    monkeypatch.setattr(WordManager, "create_from_markdown", corrupt)
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code == 422, response.text
    assert response.headers.get("x-atom-business-result") is None
    assert response.headers.get("content-disposition") is None


def test_export_rechecks_revoked_actor_with_fresh_authoritative_state(
        world, monkeypatch):
    from core.office_service import WordManager
    from core.models import User as UserRow

    canvas_id, audit_id = world.create_canvas()
    original = WordManager.create_from_markdown

    def revoke_during_render(self, path, *args, **kwargs):
        result = original(self, path, *args, **kwargs)
        with world.Session() as peer:
            peer.query(UserRow).filter(UserRow.id == world.user).update(
                {"is_active": False, "status": "disabled"},
                synchronize_session=False)
            peer.commit()
        return result

    monkeypatch.setattr(
        WordManager, "create_from_markdown", revoke_during_render)
    response = _export(world.client(), canvas_id, "docx",
                       expected_audit_id=audit_id)
    assert response.status_code in (401, 403, 404), response.text
    assert response.headers.get("content-disposition") is None
    assert not response.content.startswith(b"PK")
