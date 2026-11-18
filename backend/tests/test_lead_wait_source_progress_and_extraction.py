"""Unavailable sources yield a wait, and valid indexed revisions retain their namespace.

The same source-extraction contract covers ordinary uploaded binary documents:
the upload route stores the real OOXML path on the authoritative
``IngestedDocument`` row and the extracted workbook text in LanceDB under the
matching extraction revision. ``document.text`` must therefore read that
version-matched indexed text rather than decoding the ZIP container as text.
"""
import asyncio
import hashlib
import os
from types import SimpleNamespace
import pytest
from core.assignment_executor import NeedsContext, _document_text_read
from core.assignment_resources import (
    resolve_assignment_source, resource_binding,
)
from core.doc_freshness_service import extraction_content_hash
from core.models import IngestedDocument
from tests.test_assignment_routes import route_env
from tests.test_lead_wait_source_disappears import test_accepted_invoice_unavailable_before_consumption_stays_unresolved as _removed_case

pytestmark = pytest.mark.timeout(45)


def test_source_gap_returns_instead_of_syncing_applied_receipt_forever(route_env, tmp_path, monkeypatch):
    from core.assignment_executor import AssignmentExecutor
    original = AssignmentExecutor._source_consumption_gap
    repeats = {}
    def observe(self, assignment, record):
        result = original(self, assignment, record)
        if result:
            step, gap = result
            key = (step['step_id'], gap.get('reason'))
            repeats[key] = repeats.get(key, 0) + 1
            if repeats[key] > 1:
                raise RuntimeError('lead observed repeated identical source gap without yielding')
        return result
    monkeypatch.setattr(AssignmentExecutor, '_source_consumption_gap', observe)
    _removed_case(route_env, tmp_path, monkeypatch, 'removed')
    assert repeats and max(repeats.values()) == 1, 'source gap was repeatedly overwritten by the applied operation instead of yielding a wait'


@pytest.mark.parametrize('revision_kind', ['ev4', 'manual_opaque'])
def test_valid_indexed_source_version_is_not_a_binary_file_digest(route_env, tmp_path, monkeypatch, revision_kind):
    from core.assignment_executor import AssignmentExecutor, _document_text_read
    from core.assignment_plan import new_assignment, new_step
    from core.models import IngestedDocument
    import core.lancedb_handler as lance
    binary = tmp_path/'original.bin'
    binary.write_bytes(b'original binary source bytes distinct from extracted text')
    version = ('ev4:'+hashlib.sha256(binary.read_bytes()).hexdigest()) if revision_kind=='ev4' else 'manual-revision-17'
    doc = IngestedDocument(id='lead-indexed-current', workspace_id='ws-1', tenant_id='tenant-1', file_name=binary.name, file_path=str(binary), file_type='pdf', integration_id='upload', external_id='lead-indexed-current', source_content_hash=version, freshness_status='fresh')
    route_env['db'].add(doc); route_env['db'].commit()
    indexed = {'id':doc.id,'text':'{"po_id":"PO-INDEXED","quantity":"2"}','source':binary.name,'metadata':{'source_content_hash':version,'pg_document_id':doc.id,'workspace_id':'ws-1','tenant_id':'tenant-1'}}
    monkeypatch.setattr(lance,'get_lancedb_handler',lambda workspace:SimpleNamespace(get_document_by_id=lambda table, identity:indexed))
    binding = {'kind':'document','source':'upload','document_id':doc.id,'resource_id':doc.id,'source_version':version,'workspace_id':'ws-1','tenant_id':'tenant-1','access_scope':{'user_id':'lead-1','workspace_id':'ws-1','tenant_id':'tenant-1'}}
    result = asyncio.run(_document_text_read({'resource_binding':binding},{'workspace_id':'ws-1','tenant_id':'tenant-1'}))
    assert result['verification']['status']=='verified'
    step = new_step(step_id='accepted-index', title='Read authorized indexed text', operation_type='retrieve', adapter='document.text', inputs={'resource_binding':binding}, effect='read_only')
    step.update(status='applied',operation_id='accepted-index-operation',result=result)
    assignment = new_assignment(objective='Use verified indexed text',steps=[step])
    problem = AssignmentExecutor(route_env['lifecycle'])._source_consumption_gap(assignment,{})
    assert problem is None, ('valid indexed revision was miscompared with raw binary bytes', problem)


# ---------------------------------------------------------------------------
# Ordinary uploaded binary documents (normal-upload replay regression)
#
# ``POST /api/documents/upload`` stores the real
# ``data/office/uploads/<doc_id>.xlsx`` path on the authoritative
# ``IngestedDocument`` row and stores the extracted workbook text in LanceDB
# under the same extraction revision. ``document.text`` used to prefer that
# path unconditionally, so ``_document_read`` decoded the OOXML ZIP container
# ("PK\\x03\\x04...", NUL and other C0 controls) as text and recorded the read
# as applied/verified. The artifact renderer then rejected the composed
# markdown.
#
# These tests pin the raw-path shortcut to the suffixes ``_document_read``
# really decodes as text, require container/binary uploads to use the
# authoritative version-matched indexed extraction, and keep the stale/scope
# refusals and the legacy-ingestion pseudo path (``upload:<name>``) on that
# same indexed branch.
# ---------------------------------------------------------------------------

DOC_ID = "doc_35ac92054d4656ee3645eaf2"
WORKBOOK_TEXT = (
    "WORKBOOK INDEX: 1 sheets\n"
    "- Prices: 2 data rows, 4 cols | headers: Item, Qty, Price, Currency\n"
    "Item | Qty | Price | Currency\n"
    "A | 2 | 100.00 | USD\n"
    "B | 3 | 50.00 | USD\n"
)
# A bounded OOXML ZIP prefix plus NUL/high bytes. Reading this as text is the
# raw-container read this regression forbids; it is not a valid workbook, so a
# silent fallback to the path cannot look like a successful extraction.
ZIP_BYTES = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00\xff" * 64

CONTEXT = {"workspace_id": "ws-1", "tenant_id": "tenant-1"}


def _upload_xlsx(
    route_env, tmp_path, *, file_name="price-book.xlsx",
    freshness="fresh", indexed_text=WORKBOOK_TEXT, indexed_version=None,
    file_path=None,
):
    """The exact row shape the ordinary upload route persists."""
    path = tmp_path / "data" / "office" / "uploads" / f"{DOC_ID}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ZIP_BYTES)
    version = extraction_content_hash(WORKBOOK_TEXT)
    row = IngestedDocument(
        id=DOC_ID,
        workspace_id="ws-1",
        tenant_id="tenant-1",
        file_name=file_name,
        file_path=str(path) if file_path is None else file_path,
        file_type="xlsx",
        integration_id="manual_upload",
        external_id=f"upload_{DOC_ID}",
        source_content_hash=version,
        file_size_bytes=len(ZIP_BYTES),
        content_preview=WORKBOOK_TEXT[:500],
        freshness_status=freshness,
    )
    route_env["db"].add(row)
    route_env["db"].commit()
    document = {
        "id": DOC_ID,
        "text": indexed_text,
        "source": f"upload:{file_name}",
        "metadata": {
            "source_content_hash": (
                version if indexed_version is None else indexed_version),
            "pg_document_id": DOC_ID,
            "filename": file_name,
        },
    }
    return path, version, row, document


def _index(monkeypatch, document):
    import core.lancedb_handler as lance

    def by_id(_table, doc_id):
        return document if doc_id == document["id"] else None

    handler = SimpleNamespace(get_document_by_id=by_id)
    monkeypatch.setattr(
        lance, "get_lancedb_handler", lambda workspace: handler)


def _resolved_read(route_env, *, source_version=None):
    reference = {"kind": "document", "document_id": DOC_ID}
    if source_version:
        reference["source_version"] = source_version
    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"], reference)
    binding = resource_binding(resolved)
    inputs = {"resource_binding": binding}
    if resolved.get("path"):
        # The planner copies the server-resolved path only when a
        # document_id is present; reproduce that exact step input shape.
        inputs["path"] = str(resolved["path"])
    return asyncio.run(_document_text_read(inputs, dict(CONTEXT)))


def _assert_no_raw_container(text):
    assert not text.startswith("PK"), (
        "document.text returned the raw OOXML ZIP container")
    assert "\x00" not in text
    assert "\ufffd" not in text
    assert not any(ch not in "\n\r\t" and ord(ch) < 0x20 for ch in text), (
        "the extracted text still carries C0 controls that the DOCX renderer "
        "rejects as invalid XML")


def test_ordinary_upload_xlsx_uses_versioned_indexed_text(
        route_env, tmp_path, monkeypatch):
    _path, version, _row, document = _upload_xlsx(route_env, tmp_path)
    _index(monkeypatch, document)

    result = _resolved_read(route_env, source_version=version)

    assert result["status"] == "applied"
    assert result["summary"].startswith("read extracted text from")
    assert result["text"] == WORKBOOK_TEXT
    assert "Item, Qty, Price, Currency" in result["text"]
    _assert_no_raw_container(result["text"])
    assert result["source_version"] == version
    assert result["verification"]["status"] == "verified"
    assert result["verification"]["version"] == version
    assert result["extraction"]["indexed_version"] == version
    assert result["extraction"]["authoritative_version"] == version


def test_ordinary_upload_xlsx_stale_index_is_refused(
        route_env, tmp_path, monkeypatch):
    _path, _version, _row, document = _upload_xlsx(
        route_env, tmp_path,
        indexed_version=extraction_content_hash("an older extraction"))
    _index(monkeypatch, document)

    with pytest.raises(NeedsContext) as raised:
        _resolved_read(route_env)

    assert raised.value.gap["concept"] == "document_extraction_stale"


def test_ordinary_upload_xlsx_stale_authority_is_refused(
        route_env, tmp_path, monkeypatch):
    path, version, row, document = _upload_xlsx(route_env, tmp_path)
    _index(monkeypatch, document)
    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": DOC_ID,
         "source_version": version})
    # Authority went stale after resolution: the next read must refuse rather
    # than fall back to the still-present local file.
    row.freshness_status = "stale"
    route_env["db"].commit()
    assert path.is_file()

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_document_text_read(
            {"resource_binding": resource_binding(resolved),
             "path": str(path)}, dict(CONTEXT)))

    assert raised.value.gap["concept"] == "document_freshness"


def test_ordinary_upload_xlsx_out_of_scope_is_refused(
        route_env, tmp_path, monkeypatch):
    _path, version, _row, document = _upload_xlsx(route_env, tmp_path)
    _index(monkeypatch, document)
    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": DOC_ID,
         "source_version": version})
    binding = resource_binding(resolved)
    binding.pop("workspace_id", None)

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_document_text_read(
            {"resource_binding": binding, "path": str(resolved["path"])},
            {"workspace_id": "ws-2", "tenant_id": "tenant-1"}))

    assert raised.value.gap["concept"] == "document_scope"


def test_legacy_ingestion_pseudo_path_still_cannot_raw_read(
        route_env, tmp_path, monkeypatch):
    # ``POST /api/document-ingestion/upload`` records file_path="upload:<name>"
    # (never a real file). It must stay on the indexed branch: this pins the
    # code path only and makes no claim about that route's artifact predicates,
    # whose open negative is tracked separately.
    _path, _version, _row, document = _upload_xlsx(
        route_env, tmp_path, file_name="price-book.xlsx",
        file_path="upload:price-book.xlsx")
    _index(monkeypatch, document)

    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": DOC_ID})
    binding = resource_binding(resolved)
    result = asyncio.run(_document_text_read(
        {"resource_binding": binding, "path": str(resolved["path"])},
        dict(CONTEXT)))

    assert result["summary"].startswith("read extracted text from")
    assert result["text"].startswith("WORKBOOK INDEX: 1 sheets")
    _assert_no_raw_container(result["text"])


def test_text_and_json_path_reads_keep_their_real_content(
        route_env, tmp_path, monkeypatch):
    text_path = tmp_path / "notes.txt"
    text_path.write_text("local notes are the source")
    json_path = tmp_path / "invoice.json"
    json_path.write_text('{"invoice_id": "INV-1", "total": "370.00"}')
    # The indexed text is deliberately different: a genuinely text-native file
    # must still be read from its authorized path (the 2026-11-03 behavior).
    for doc_id, path, file_type in (
            (f"{DOC_ID}-txt", text_path, "txt"),
            (f"{DOC_ID}-json", json_path, "json")):
        route_env["db"].add(IngestedDocument(
            id=doc_id, workspace_id="ws-1", tenant_id="tenant-1",
            file_name=path.name, file_path=str(path), file_type=file_type,
            integration_id="manual_upload",
            external_id=f"upload_{doc_id}",
            source_content_hash=extraction_content_hash("other extraction"),
            freshness_status="fresh"))
    route_env["db"].commit()

    text_read = asyncio.run(_document_text_read(
        {"resource_binding": {
            "document_id": f"{DOC_ID}-txt",
            "resource_id": f"{DOC_ID}-txt",
            "representation": "document_text",
            "source": "manual_upload",
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        }, "path": str(text_path)}, dict(CONTEXT)))
    assert text_read["text"] == "local notes are the source"

    json_read = asyncio.run(_document_text_read(
        {"resource_binding": {
            "document_id": f"{DOC_ID}-json",
            "resource_id": f"{DOC_ID}-json",
            "representation": "document_text",
            "source": "manual_upload",
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        }, "path": str(json_path)}, dict(CONTEXT)))
    assert json_read["data"]["invoice_id"] == "INV-1"
    assert "local notes" not in json_read["text"]


# ---------------------------------------------------------------------------
# Legacy ingestion upload as an assignment source
#
# ``POST /api/document-ingestion/upload`` stores file_path="upload:<name>" and
# never materializes bytes. The read adapter already serves that row from the
# version-matched indexed extraction, but consumption treated the pseudo path
# as a missing local file and parked every accepted read as source_unavailable.
# These mounted-route twins cover upload -> list -> accept/read -> consumption,
# the stale-index and foreign-workspace refusals, and the preserved G2 rule for
# a materialized upload whose file disappears after acceptance.
# ---------------------------------------------------------------------------

LEGACY_TEXT = "ITEM,QTY,PRICE\nWidget,2,10.00\nBolt,3,4.00\n"


@pytest.fixture()
def mounted_document_routes(route_env, tmp_path, monkeypatch):
    """Mount the real ingest/upload routes beside the assignment routes."""
    import numpy as np
    import api.document_ingestion_routes as di
    import api.document_routes as dr
    from core.embedding_service import EmbeddingService
    from core.lancedb_handler import LanceDBHandler

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)

    handlers = {}

    def handler_for(workspace_id=None, **_kwargs):
        workspace = str(workspace_id or "ws-1")
        if workspace not in handlers:
            handlers[workspace] = LanceDBHandler(
                db_path=str(tmp_path / "lancedb" / workspace),
                workspace_id=workspace, tenant_id="tenant-1")
        return handlers[workspace]

    monkeypatch.setattr(di, "get_lancedb_handler", handler_for)
    monkeypatch.setattr(dr, "get_lancedb_handler", handler_for)
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", handler_for)
    route_env["client"].app.include_router(di.router)
    route_env["client"].app.include_router(dr.router)
    route_env["handlers"] = handlers
    return route_env


def _legacy_upload(env, text=LEGACY_TEXT, name="price-book.txt"):
    response = env["client"].post(
        "/api/document-ingestion/upload",
        files={"file": (name, text.encode("utf-8"), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["data"]["document_id"]


def _start_from_document(env, monkeypatch, document_id, *,
                         objective="Read the uploaded price book"):
    async def proposal(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "Read the authorized source.",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read source",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", proposal)
    response = env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": objective,
            "sources": [{"document_id": document_id}],
            "authorized_actions": ["retrieve"],
            "use_model": False,
        })
    return response


def _document_step(assignment):
    return next(
        step for step in assignment["steps"]
        if step["adapter"] == "document.text")


def _open_gap_concepts(env, run_id):
    record = env["lifecycle"].get_task(run_id) or {}
    return {
        str(question.get("concept") or "")
        for question in
        (record.get("task_revision") or {}).get("unresolved") or []
        if question.get("status") == "open"
    }


def test_legacy_ingestion_upload_is_listed_read_and_consumable(
        mounted_document_routes, monkeypatch):
    env = mounted_document_routes
    doc_id = _legacy_upload(env)

    row = env["db"].query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).first()
    assert row is not None
    assert row.file_path == "upload:price-book.txt"
    assert not os.path.isfile(row.file_path)

    listing = env["client"].get("/api/assignments/sources")
    assert listing.status_code == 200, listing.text
    entry = next(
        item for item in listing.json()
        if item.get("document_id") == doc_id)
    assert entry["source_version"] == row.source_content_hash

    response = _start_from_document(env, monkeypatch, doc_id)
    assert response.status_code == 200, response.text
    assignment = env["lifecycle"].get_assignment(
        response.json()["run_id"])

    step = _document_step(assignment)
    assert step["status"] == "applied", step
    assert not step.get("gap_ids"), step
    assert "Widget,2,10.00" in step["result"]["text"]
    assert step["result"]["source_version"] == row.source_content_hash
    assert not _open_gap_concepts(env, response.json()["run_id"])


def test_legacy_ingestion_stale_index_is_refused(
        mounted_document_routes, monkeypatch):
    env = mounted_document_routes
    doc_id = _legacy_upload(env)
    handler = env["handlers"]["ws-1"]
    indexed = handler.get_document_by_id("documents", doc_id)
    metadata = dict(indexed["metadata"])
    metadata["source_content_hash"] = extraction_content_hash(
        "an older extraction")
    assert handler.delete_documents_by_id("documents", doc_id)
    assert handler.add_document(
        "documents", text="an older extraction", source=indexed["source"],
        metadata=metadata, user_id="lead-1", workspace_id="ws-1",
        doc_id=doc_id, extra_columns={"freshness_status": "fresh"})

    response = _start_from_document(env, monkeypatch, doc_id)
    assert response.status_code == 200, response.text
    assignment = env["lifecycle"].get_assignment(
        response.json()["run_id"])

    step = _document_step(assignment)
    assert step["status"] == "waiting", step
    assert "document_extraction_stale" in _open_gap_concepts(
        env, response.json()["run_id"])
    assert not (step.get("result") or {}).get("text")


def test_legacy_ingestion_foreign_workspace_document_is_refused(
        mounted_document_routes, monkeypatch):
    env = mounted_document_routes
    from core.models import GoalRun

    env["current"]["user"] = env["users"]["other"]
    try:
        foreign_id = _legacy_upload(env, name="foreign-book.txt")
    finally:
        env["current"]["user"] = env["users"]["lead"]

    listing = env["client"].get("/api/assignments/sources")
    assert listing.status_code == 200, listing.text
    assert not any(
        item.get("document_id") == foreign_id
        for item in listing.json())

    before = env["db"].query(GoalRun).count()
    response = _start_from_document(env, monkeypatch, foreign_id)
    assert response.status_code == 404, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "resource_not_found"
    assert env["db"].query(GoalRun).count() == before


def test_materialized_upload_disappearance_still_parks(
        mounted_document_routes, monkeypatch):
    env = mounted_document_routes
    uploaded = env["client"].post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"local notes are the source",
                        "text/plain")})
    assert uploaded.status_code == 200, uploaded.text
    doc_id = uploaded.json()["id"]
    row = env["db"].query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).first()
    assert row is not None and os.path.isabs(row.file_path)
    assert os.path.isfile(row.file_path)

    response = _start_from_document(env, monkeypatch, doc_id)
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assert _document_step(
        env["lifecycle"].get_assignment(run_id))["status"] == "applied"

    os.unlink(row.file_path)
    replay = env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {
                "kind": "document",
                "document_id": doc_id,
                "source_version": row.source_content_hash,
            },
            "reason": "same authorized source",
        })
    assert replay.status_code == 200, replay.text

    step = _document_step(env["lifecycle"].get_assignment(run_id))
    assert step["status"] == "waiting", step
    assert "source_unavailable" in str(step.get("waiting") or {})

