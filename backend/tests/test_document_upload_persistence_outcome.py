"""Failure-first proposal: an upload must not look successful when its SQL mirror fails.

Suspicion under test
--------------------
``/api/documents/upload`` writes the LanceDB row first, then mirrors it into the
authoritative SQL ``IngestedDocument`` table inside a broad ``try/except``.  The
public route catches *any* mirror exception (including a failed ``db.commit()``),
logs a warning, and still returns ``DocumentResponse`` with HTTP 200.

That is the exact seam this module probes.  The positive twin uses the real
public API and the existing ``tests.test_document_export.exported`` fixture
(scratch SQL, real LanceDB; only the embedding leaf is doubled).  The negative
twin injects a failure at the narrow persistence seam -- the SQL session's
``commit`` -- while leaving the session's read/query path attached to the real
database, so the identity preflight queries are still honest.  The number of
query and failed-commit calls is counted so the test can prove the seam was
actually exercised.

What is confirmed, and what is not
----------------------------------
Confirmed by the public code and this probe's design: the Lance write precedes
the SQL mirror; a mirror failure is swallowed at the producer.  Not assumed:
Lance and SQL are separate stores, so there is no distributed transaction and
no claim is made about atomicity.  A repair may compensate/retry, roll back or
mark the vector row unavailable, or return a truthful typed non-2xx outcome.
The test therefore accepts either (a) a success that is backed by a durable SQL
row and is readable/exportable, or (b) a truthful non-2xx unavailable/uncertain/
refused outcome.  It does not invent an error code and does not assume a new
engine or schema.  Existing peer rows are snapshotted and must survive.

Current expected result: the fault twin FAILS on the public code because the
upload returns HTTP 200 while the injected SQL commit never persisted the
authoritative row.  That failure is the point of the proposal.  This module was
authored only; it has not been executed here.  The runtime repair is root-owned
after independent execution.
"""
from __future__ import annotations

import contextlib
import json
import uuid

import api.document_routes as routes
import core.database as database_module
from core.models import IngestedDocument
from tests.test_document_export import (
    _read,
    _seed_sql,
    _seed_vector,
    exported,
)


def _post_upload(ctx, text: str, name: str = "mirror-probe.txt"):
    return ctx.client.post(
        "/api/documents/upload",
        files={"file": (name, text.encode("utf-8"), "text/plain")},
    )


def _sql_state(session) -> dict:
    """Stable snapshot of every prior SQL row, including timestamps."""
    session.expire_all()
    columns = (
        "workspace_id", "tenant_id", "external_id", "integration_id",
        "file_name", "file_path", "file_type", "file_size_bytes",
        "content_preview", "ingested_at", "source_content_hash",
        "last_verified_at", "freshness_status",
    )
    return {
        row.id: tuple(getattr(row, column) for column in columns)
        for row in session.query(IngestedDocument).all()
    }


def _vector_state(handler) -> dict:
    """Stable snapshot of every indexed row in this test's workspace store."""
    table = handler.get_table("documents")
    rows = table.to_arrow().to_pylist() if table is not None else []
    return {str(row.get("id")): dict(row) for row in rows}


def _assert_prior_rows_preserved(ctx, sql_before: dict, vector_before: dict):
    for doc_id, before in sql_before.items():
        after = _sql_state(ctx.session).get(doc_id)
        assert after == before, (
            "a fault-injected upload changed a pre-existing SQL row; peer data "
            f"must be preserved (doc_id={doc_id!r}, before={before!r}, "
            f"after={after!r})")
    vector_after = _vector_state(ctx.handler)
    for doc_id, before in vector_before.items():
        assert vector_after.get(doc_id) == before, (
            "a fault-injected upload changed a pre-existing indexed row; peer "
            f"data must be preserved (doc_id={doc_id!r})")


class _CommitFailingSession:
    """A real SQLAlchemy session whose only broken operation is persistence.

    ``query`` and ``add`` are delegated to the real session; the identity
    preflight only reads, so it continues to see the real scratch database.
    Every ``commit`` is counted and refused, modelling the actual mirror seam.
    """

    def __init__(self, session, counter):
        self._session = session
        self._counter = counter

    def query(self, *args, **kwargs):
        self._counter["queries"] += 1
        return self._session.query(*args, **kwargs)

    def add(self, instance):
        self._counter["adds"] += 1
        return self._session.add(instance)

    def commit(self):
        self._counter["commit_attempts"] += 1
        self._counter["commit_failures"] += 1
        raise RuntimeError("injected SQL mirror commit failure")

    def __getattr__(self, name):
        return getattr(self._session, name)


def _commit_failure_seam(counter: dict):
    """Patch ``core.database.get_db_session`` below the route's import.

    The route imports ``get_db_session`` inside the upload function, so replacing
    the module attribute affects both the read-only identity preflight and the
    SQL mirror.  The preflight does not commit; only the mirror's commit fails.
    """
    real_get_db_session = database_module.get_db_session

    @contextlib.contextmanager
    def _patched_get_db_session():
        counter["sessions"] += 1
        with real_get_db_session() as session:
            yield _CommitFailingSession(session, counter)

    return _patched_get_db_session


def _assert_non_success_is_truthful(response):
    """Accept a non-2xx refusal/uncertain/unavailable outcome without pinning it.

    A specific error code would be a made-up contract.  If the server supplies a
    structured error, require a non-empty code and message; otherwise require a
    non-empty explanatory detail.  The point is that the mirror failure is not
    presented as a normal success.
    """
    assert response.status_code >= 400, response.text
    assert response.text.strip(), "non-2xx response has no explanatory body"
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - plain-text refusal is still observable
        return
    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, dict):
        error = detail.get("error", detail)
        if isinstance(error, dict):
            code = error.get("code")
            if code is not None:
                assert isinstance(code, str) and code.strip(), (
                    f"typed error carries an empty code: {response.text!r}")
            assert error.get("message") or detail.get("message"), (
                f"typed error carries no message: {response.text!r}")
        else:
            assert str(detail).strip()
    else:
        assert str(detail).strip()


def _assert_not_false_success(ctx, response, expected_id: str, text: str):
    """A 2xx is allowed only when the document is durably mirrored and usable."""
    if 200 <= response.status_code < 300:
        ctx.session.expire_all()
        row = ctx.session.get(IngestedDocument, expected_id)
        assert row is not None, (
            "upload acknowledged an injected SQL mirror commit failure with "
            f"HTTP {response.status_code} success, but no authoritative SQL "
            "row exists for the new document; this is a false success "
            f"(response={response.text[:500]!r})")
        opened = _read(ctx, expected_id)
        assert opened["content"] == text
        export = ctx.client.get(
            f"/api/documents/{expected_id}/export?format=json")
        assert export.status_code == 200, export.text
        payload = json.loads(export.content)
        assert payload["content"] == text
        assert payload["source_version_status"] == "matched"
    else:
        _assert_non_success_is_truthful(response)


def _seed_peer(ctx):
    """Create a real prior SQL + Lance peer that must survive the probe."""
    text = f"pre-existing peer document {uuid.uuid4().hex}\n"
    doc_id = f"peer-{uuid.uuid4().hex[:12]}"
    version = "ev4:" + "a" * 64
    _seed_vector(
        ctx, text=text, doc_id=doc_id,
        metadata={
            "title": "peer.txt",
            "file_name": "peer.txt",
            "source_content_hash": version,
            "pg_document_id": doc_id,
        },
        source="upload:peer.txt",
    )
    _seed_sql(ctx, doc_id, version=version, file_name="peer.txt")
    return doc_id, text


def test_valid_upload_is_durably_mirrored_and_available(exported, monkeypatch,
                                                       tmp_path):
    """Positive twin: the same public path, with no injected fault."""
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    text = f"valid control upload {uuid.uuid4().hex}\n"

    response = _post_upload(exported, text, "valid-control.txt")
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]
    assert doc_id == routes._content_doc_key(
        text, exported.workspace, exported.user.tenant_id)

    exported.session.expire_all()
    row = exported.session.get(IngestedDocument, doc_id)
    assert row is not None, "valid upload did not create its SQL mirror row"
    assert row.workspace_id == exported.workspace
    assert row.tenant_id == exported.user.tenant_id
    assert row.source_content_hash
    assert row.freshness_status == "fresh"

    opened = _read(exported, doc_id)
    assert opened["content"] == text

    export = exported.client.get(
        f"/api/documents/{doc_id}/export?format=json")
    assert export.status_code == 200, export.text
    payload = json.loads(export.content)
    assert payload["content"] == text
    assert payload["provenance_status"] == "authoritative"
    assert payload["source_version_status"] == "matched"


def test_sql_mirror_commit_failure_is_not_acknowledged_as_success(
        exported, monkeypatch, tmp_path):
    """Failure-first twin: Lance write succeeds, SQL commit is injected failed.

    The upload must either compensate so that a 2xx is backed by the durable SQL
    row (and is readable/exportable), or return a truthful non-2xx outcome.  It
    must not be a normal 200 with only the unmirrored vector row.
    """
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    peer_id, _peer_text = _seed_peer(exported)

    sql_before = _sql_state(exported.session)
    vector_before = _vector_state(exported.handler)
    assert peer_id in sql_before
    assert peer_id in vector_before

    text = f"fault-injected upload {uuid.uuid4().hex}\n"
    expected_id = routes._content_doc_key(
        text, exported.workspace, exported.user.tenant_id)
    assert expected_id != peer_id

    counter = {
        "sessions": 0,
        "queries": 0,
        "adds": 0,
        "commit_attempts": 0,
        "commit_failures": 0,
    }
    patched = _commit_failure_seam(counter)
    with monkeypatch.context() as fault_mp:
        fault_mp.setattr(database_module, "get_db_session", patched)
        response = _post_upload(exported, text, "fault-injected.txt")

    assert counter["commit_attempts"] >= 1, (
        "the SQL mirror commit seam was never reached; the fault injection did "
        f"not exercise the suspected effect (counter={counter!r})")
    assert counter["commit_failures"] == counter["commit_attempts"], (
        "the fault seam was reached but not every injected commit failed "
        f"(counter={counter!r})")
    assert counter["queries"] >= 1, (
        "the identity preflight did not use the real SQL query path; it must "
        f"remain honest under the injected commit failure (counter={counter!r})")

    # Peer data is checked before the failure-first success assertion so the
    # durable-state evidence is collected even while the bug is present.
    _assert_prior_rows_preserved(exported, sql_before, vector_before)
    _assert_not_false_success(exported, response, expected_id, text)
