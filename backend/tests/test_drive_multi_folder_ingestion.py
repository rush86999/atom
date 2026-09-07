"""Multi-folder ingestion for the drive integrations (GDrive, OneDrive, Zoho).

The panels let a user tick several folders and start ingestion on all of them
at once. Fully mocked (service methods patched, fake get_current_user), zero
network, zero LLM spend.

Covers:
- POST /api/gdrive/ingest-folders: success aggregation, not_connected,
  per-folder failure isolation, empty-folders 422, anon 401.
- POST /api/onedrive/ingest-folders: same.
- GoogleDriveService.ingest_folder_to_memory / OneDriveService
  .ingest_folder_to_memory: subtree walk scoped to the folder, folder_path
  metadata stamped, tally returned.
- POST /api/zoho-workdrive/ingest-folder with folder_ids: batch aggregation,
  per-folder isolation, legacy single folder_id form unchanged, missing ids
  422.
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import gdrive_journey_routes as gjr
from integrations import onedrive_journey_routes as ojr
from integrations.google_drive_service import GoogleDriveService
from integrations.onedrive_service import OneDriveService
from api import zoho_workdrive_routes as zwr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "multi-folder-user"
    u.email = "mf@x.com"
    return u


def _folder_tally(folder_id, name, ingested):
    return {
        "success": True,
        "folder_id": folder_id,
        "folder_name": name,
        "files_found": ingested,
        "files_ingested": ingested,
        "files_skipped": [],
        "errors": [],
    }


@pytest.fixture(autouse=True)
def _clear_ingest_job_registry():
    # Ingest jobs live in a module-global registry (core.ingest_jobs) —
    # clear it around each test so running jobs never coalesce across tests.
    from core import ingest_jobs

    ingest_jobs.registry.clear()
    yield
    ingest_jobs.registry.clear()


def _await_ingest_job(client, base, job_id, timeout=5.0):
    # Ingest runs as a background task; poll the job-status endpoint until it
    # leaves "running" (mocked service calls resolve fast).
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"{base}/ingest/jobs/{job_id}")
        assert status.status_code == 200
        job = status.json()["data"]
        if job["status"] != "running":
            return job
        time.sleep(0.02)
    raise AssertionError(f"ingest job {job_id} never finished")


# ---------------------------------------------------------------- Google Drive


@pytest.fixture
def gdrive_client(user):
    app = FastAPI()
    app.include_router(gjr.router)
    # Single-file ingest lives on the bare /api router the panel posts to.
    app.include_router(gjr.ingest_router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


class TestGdriveIngestFolders:
    def test_success_aggregates_folders(self, gdrive_client):
        mock_ingest = AsyncMock(
            side_effect=[
                _folder_tally("fldA", "A", 3),
                _folder_tally("fldB", "B", 2),
            ]
        )
        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(gjr._service, "ingest_folder_to_memory", new=mock_ingest), \
             patch.object(gjr, "record_ingestion_feedback") as feedback:
            resp = gdrive_client.post(
                "/api/gdrive/ingest-folders",
                json={"folders": [{"id": "fldA", "name": "A"}, {"id": "fldB"}]},
            )
        assert resp.status_code == 200
        started = resp.json()["data"]
        assert started["status"] == "started"
        job = _await_ingest_job(gdrive_client, "/api/gdrive", started["job_id"])
        assert job["status"] == "completed"
        body = job["result"]
        assert body["success"] is True
        assert body["folders_requested"] == 2
        assert body["folders_succeeded"] == 2
        assert body["files_ingested"] == 5
        assert [r["folder_id"] for r in body["results"]] == ["fldA", "fldB"]
        mock_ingest.assert_any_await("tok", "fldA", folder_name="A")
        mock_ingest.assert_any_await("tok", "fldB", folder_name=None)
        # per-app feedback recorded for THIS integration
        feedback.assert_called_once()
        assert feedback.call_args.args[1] == "google_drive"
        assert feedback.call_args.args[2] == 5
        assert feedback.call_args.args[3] is True

    def test_folder_failure_isolated(self, gdrive_client):
        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            gjr._service,
            "ingest_folder_to_memory",
            new=AsyncMock(
                side_effect=[RuntimeError("walk exploded"), _folder_tally("fldB", "B", 1)]
            ),
        ):
            resp = gdrive_client.post(
                "/api/gdrive/ingest-folders",
                json={"folders": [{"id": "fldA"}, {"id": "fldB", "name": "B"}]},
            )
        job = _await_ingest_job(gdrive_client, "/api/gdrive", resp.json()["data"]["job_id"])
        body = job["result"]
        assert body["success"] is True
        assert body["folders_succeeded"] == 1
        assert body["files_ingested"] == 1
        assert body["results"][0]["success"] is False
        assert "walk exploded" in body["results"][0]["error"]

    def test_not_connected(self, gdrive_client):
        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value=None)
        ):
            resp = gdrive_client.post(
                "/api/gdrive/ingest-folders", json={"folders": [{"id": "f"}]}
            )
        assert resp.json() == {"success": False, "error": "not_connected"}

    def test_empty_folders_422(self, gdrive_client):
        resp = gdrive_client.post("/api/gdrive/ingest-folders", json={"folders": []})
        assert resp.status_code == 422

    def test_anonymous_401(self):
        app = FastAPI()
        app.include_router(gjr.router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/gdrive/ingest-folders", json={"folders": [{"id": "f"}]})
        assert resp.status_code == 401


# -------------------------------------------------------------------- OneDrive


@pytest.fixture
def onedrive_client(user):
    app = FastAPI()
    app.include_router(ojr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


class TestOnedriveIngestFolders:
    def test_success_aggregates_folders(self, onedrive_client):
        mock_ingest = AsyncMock(side_effect=[_folder_tally("f1", "Docs", 4)])
        with patch.object(
            ojr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(ojr._service, "ingest_folder_to_memory", new=mock_ingest), \
             patch.object(ojr, "record_ingestion_feedback") as feedback:
            resp = onedrive_client.post(
                "/api/onedrive/ingest-folders",
                json={"folders": [{"id": "f1", "name": "Docs"}]},
            )
        assert resp.status_code == 200
        job = _await_ingest_job(onedrive_client, "/api/onedrive", resp.json()["data"]["job_id"])
        body = job["result"]
        assert body["success"] is True
        assert body["files_ingested"] == 4
        mock_ingest.assert_awaited_once_with("tok", "f1", folder_name="Docs")
        assert feedback.call_args.args[1] == "onedrive"
        assert feedback.call_args.args[2] == 4


class TestPerAppFeedbackRecording:
    """Every user-triggered ingest records feedback against its own app, so
    the integration card's counts move (record_ingestion_feedback)."""

    def test_gdrive_single_file_records(self, gdrive_client, user):
        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            gjr._service, "ingest_file_to_memory",
            new=AsyncMock(return_value={"success": True, "result": {"status": "ingested"}}),
        ), patch.object(gjr, "record_ingestion_feedback") as feedback:
            resp = gdrive_client.post(
                "/api/ingest-gdrive-document",
                json={"file_id": "doc1"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        feedback.assert_called_once_with(user, "google_drive", 1, True)

    def test_gdrive_single_file_failure_records_not_ingested(self, gdrive_client, user):
        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            gjr._service, "ingest_file_to_memory",
            new=AsyncMock(return_value={"success": False, "error": "nope"}),
        ), patch.object(gjr, "record_ingestion_feedback") as feedback:
            gdrive_client.post("/api/ingest-gdrive-document", json={"file_id": "doc1"})
        feedback.assert_called_once_with(user, "google_drive", 0, False)

    def test_gdrive_sync_records_totals(self, gdrive_client, user):
        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            gjr._service, "full_sync",
            new=AsyncMock(return_value={"success": True, "files_ingested": 9}),
        ), patch.object(gjr, "record_ingestion_feedback") as feedback:
            resp = gdrive_client.post("/api/gdrive/sync")
        assert resp.status_code == 200
        feedback.assert_called_once_with(user, "google_drive", 9, True)

    def test_onedrive_single_file_records(self, onedrive_client, user):
        with patch.object(
            ojr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            ojr._service, "ingest_file_to_memory",
            new=AsyncMock(return_value={"success": True, "result": {"status": "ingested"}}),
        ), patch.object(ojr, "record_ingestion_feedback") as feedback:
            resp = onedrive_client.post(
                "/api/onedrive/ingest-document", json={"file_id": "doc1"}
            )
        assert resp.status_code == 200
        feedback.assert_called_once_with(user, "onedrive", 1, True)

    def test_zoho_batch_records_under_suite_key(self, zoho_client, user):
        tree = AsyncMock(
            side_effect=[
                {"success": True, "folder_id": "fA", "files_ingested": 2, "errors": []},
                {"success": True, "folder_id": "fB", "files_ingested": 3, "errors": []},
            ]
        )
        with patch.object(zwr.zoho_service, "ingest_folder_tree", new=tree), \
             patch.object(zwr, "record_ingestion_feedback") as feedback:
            resp = zoho_client.post(
                "/api/zoho-workdrive/ingest-folder",
                json={"folder_ids": ["fA", "fB"]},
            )
        assert resp.status_code == 200
        # zoho-workdrive's status card reads the shared "zoho" sync entry
        feedback.assert_called_once_with(user, "zoho", 5, True)

    def test_zoho_single_file_records_under_suite_key(self, zoho_client, user):
        with patch.object(
            zwr.zoho_service, "ingest_file_to_memory",
            new=AsyncMock(return_value={"success": True, "doc_id": "d1"}),
        ), patch.object(zwr, "record_ingestion_feedback") as feedback:
            zoho_client.post("/api/zoho-workdrive/ingest", json={"file_id": "f1"})
        feedback.assert_called_once_with(user, "zoho", 1, True)

    def test_recording_failure_never_breaks_ingest(self, gdrive_client, user):
        # The route relies on the helper's never-raise contract, so prove the
        # contract at its layer: the hybrid service factory exploding must
        # not propagate out of record_ingestion_feedback.
        from core.ingestion_feedback import record_ingestion_feedback

        with patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            side_effect=RuntimeError("stats down"),
        ):
            record_ingestion_feedback(user, "google_drive", 3, True)  # must not raise

        with patch.object(
            gjr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            gjr._service, "ingest_folder_to_memory",
            new=AsyncMock(return_value=_folder_tally("fldA", "A", 1)),
        ):
            resp = gdrive_client.post(
                "/api/gdrive/ingest-folders", json={"folders": [{"id": "fldA"}]}
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_folder_failure_isolated(self, onedrive_client):
        with patch.object(
            ojr._service, "get_access_token", new=AsyncMock(return_value="tok")
        ), patch.object(
            ojr._service,
            "ingest_folder_to_memory",
            new=AsyncMock(
                side_effect=[RuntimeError("404"), _folder_tally("f2", "B", 0)]
            ),
        ):
            resp = onedrive_client.post(
                "/api/onedrive/ingest-folders",
                json={"folders": [{"id": "f1"}, {"id": "f2"}]},
            )
        job = _await_ingest_job(onedrive_client, "/api/onedrive", resp.json()["data"]["job_id"])
        body = job["result"]
        assert body["folders_succeeded"] == 1
        assert "404" in body["results"][0]["error"]

    def test_not_connected(self, onedrive_client):
        with patch.object(
            ojr._service, "get_access_token", new=AsyncMock(return_value=None)
        ):
            resp = onedrive_client.post(
                "/api/onedrive/ingest-folders", json={"folders": [{"id": "f"}]}
            )
        assert resp.json() == {"success": False, "error": "not_connected"}

    def test_anonymous_401(self):
        app = FastAPI()
        app.include_router(ojr.router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/onedrive/ingest-folders", json={"folders": [{"id": "f"}]})
        assert resp.status_code == 401


# ------------------------------------------------------- service folder walks


def _walk_file(fid, name, path):
    return {"id": fid, "name": name, "path": path, "depth": 1}


class _IngestResult:
    """ingest_file_to_memory stub returning a queued result per call.

    Plain callable (not async): AsyncMock side_effect results must be
    plain values — this Python returns side-effect coroutines unawaited.
    """

    def __init__(self, results):
        self.results = list(results)
        self.metadata = []

    def __call__(self, token, file_id, extra_metadata=None):
        self.metadata.append((file_id, extra_metadata))
        return self.results.pop(0)


INGESTED = {"success": True, "result": {"status": "ingested"}}
NO_TEXT = {"success": True, "result": {"status": "skipped", "reason": "no_text"}}


@pytest.mark.asyncio
async def test_gdrive_service_ingest_folder_scopes_walk():
    svc = GoogleDriveService(tenant_id="u1", config={})
    walked = [_walk_file("a", "a.pdf", "/Reports"), _walk_file("b", "b.docx", "/Reports")]
    stub = _IngestResult([INGESTED, NO_TEXT])
    mock_walk = AsyncMock(return_value=walked)
    with patch.object(svc, "walk_files", new=mock_walk), \
         patch.object(svc, "ingest_file_to_memory", new=AsyncMock(side_effect=stub)):
        res = await svc.ingest_folder_to_memory("tok", "fld1", folder_name="Reports")
    assert res["success"] is True
    assert res["folder_id"] == "fld1"
    assert res["files_ingested"] == 1
    assert res["files_skipped"] == ["b.docx (no_text)"]
    mock_walk.assert_awaited_once_with("tok", folder_id="fld1")
    # folder-path context stamped into memory metadata
    assert stub.metadata[0] == ("a", {"folder_path": "/Reports", "modified_at": ""})


@pytest.mark.asyncio
async def test_onedrive_service_ingest_folder_scopes_walk():
    svc = OneDriveService(tenant_id="u1", config={})
    walked = [_walk_file("x", "x.pdf", "/Invoices")]
    stub = _IngestResult([INGESTED])
    mock_walk = AsyncMock(return_value=walked)
    with patch.object(svc, "walk_files", new=mock_walk), \
         patch.object(svc, "ingest_file_to_memory", new=AsyncMock(side_effect=stub)):
        res = await svc.ingest_folder_to_memory("tok", "root-xyz")
    assert res["files_ingested"] == 1
    mock_walk.assert_awaited_once_with("tok", folder_id="root-xyz")
    assert stub.metadata[0][1] == {"folder_path": "/Invoices", "modified_at": ""}


# ----------------------------------------------------------------------- Zoho


@pytest.fixture
def zoho_client(user):
    app = FastAPI()
    app.include_router(zwr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


class TestZohoIngestFolderBatch:
    @staticmethod
    def _await_zoho_job(client, job_id, timeout=5.0):
        # Ingest runs as a background task; poll the job-status endpoint
        # until it leaves "running" (mocked service calls resolve fast).
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = client.get(f"/api/zoho-workdrive/ingest-folder/jobs/{job_id}")
            assert status.status_code == 200
            job = status.json()["data"]
            if job["status"] != "running":
                return job
            time.sleep(0.02)
        raise AssertionError(f"ingest job {job_id} never finished")

    def test_batch_folder_ids_aggregates(self, zoho_client):
        tree = AsyncMock(
            side_effect=[
                {"success": True, "folder_id": "fA", "files_ingested": 2, "errors": []},
                {"success": True, "folder_id": "fB", "files_ingested": 3, "errors": []},
            ]
        )
        with patch.object(zwr.zoho_service, "ingest_folder_tree", new=tree):
            resp = zoho_client.post(
                "/api/zoho-workdrive/ingest-folder",
                json={"folder_ids": ["fA", "fB"], "recursive": True},
            )
        assert resp.status_code == 200
        job = self._await_zoho_job(zoho_client, resp.json()["data"]["job_id"])
        assert job["status"] == "completed"
        body = job["result"]
        assert body["success"] is True
        assert body["folders_requested"] == 2
        assert body["folders_succeeded"] == 2
        assert body["files_ingested"] == 5
        assert [r["folder_id"] for r in body["results"]] == ["fA", "fB"]
        assert tree.await_count == 2
        # identity comes from the token, never the client
        assert tree.await_args_list[0].args[0] == "multi-folder-user"

    def test_batch_folder_failure_isolated(self, zoho_client):
        with patch.object(
            zwr.zoho_service,
            "ingest_folder_tree",
            new=AsyncMock(
                side_effect=[
                    RuntimeError("boom"),
                    {"success": True, "folder_id": "fB", "files_ingested": 1, "errors": []},
                ]
            ),
        ):
            resp = zoho_client.post(
                "/api/zoho-workdrive/ingest-folder",
                json={"folder_ids": ["fA", "fB"]},
            )
        job = self._await_zoho_job(zoho_client, resp.json()["data"]["job_id"])
        body = job["result"]
        assert body["success"] is True
        assert body["folders_succeeded"] == 1
        assert body["results"][0]["success"] is False

    def test_single_folder_id_form_unchanged(self, zoho_client):
        with patch.object(
            zwr.zoho_service,
            "ingest_folder_tree",
            new=AsyncMock(
                return_value={"success": True, "folder_id": "solo", "files_ingested": 7, "errors": []}
            ),
        ) as tree:
            resp = zoho_client.post(
                "/api/zoho-workdrive/ingest-folder", json={"folder_id": "solo"}
            )
        assert resp.status_code == 200
        job = self._await_zoho_job(zoho_client, resp.json()["data"]["job_id"])
        result = job["result"]
        # legacy shape preserved in the job result: the tree result itself,
        # not the batch envelope
        assert result["folder_id"] == "solo"
        assert result["files_ingested"] == 7
        assert "results" not in result
        tree.assert_awaited_once()

    def test_missing_ids_422(self, zoho_client):
        resp = zoho_client.post("/api/zoho-workdrive/ingest-folder", json={})
        assert resp.status_code == 422

    def test_batch_respects_workspace_scope(self, zoho_client):
        with patch.object(
            zwr.zoho_service,
            "ingest_folder_tree",
            new=AsyncMock(
                return_value={"success": True, "folder_id": "t1", "files_ingested": 0, "errors": []}
            ),
        ) as tree:
            zoho_client.post(
                "/api/zoho-workdrive/ingest-folder",
                json={"folder_ids": ["t1"], "team_id": "team9", "workspace_id": "ws9"},
            )
        kwargs = tree.await_args.kwargs
        assert kwargs["max_files"] == 500
        assert tree.await_args.args[2] == "team9"
        assert tree.await_args.args[3] == "ws9"


# ===========================================================================
# Generalization: EVERY app integration's user/agent-triggered ingest
# records per-app feedback (not just the drives).
# ===========================================================================


class _FakeHybrid:
    def __init__(self):
        self.recorded = []

    def record_sync_completion(self, integration_id, records, success):
        self.recorded.append((integration_id, records, success))


class TestStatusSyncKey:
    def test_suite_apps_share_the_zoho_entry(self):
        from core.ingestion_feedback import status_sync_key

        for catalog_id in ("zoho-books", "zoho_books", "zoho-workdrive",
                           "zoho_crm", "zoho-inventory"):
            assert status_sync_key(catalog_id) == "zoho", catalog_id

    def test_other_apps_record_under_their_own_id(self):
        from core.ingestion_feedback import status_sync_key

        for catalog_id in ("google_drive", "onedrive", "dropbox", "box",
                           "notion", "sharepoint"):
            assert status_sync_key(catalog_id) == catalog_id


class TestDocumentIngestionRoutes:
    """The generic per-app document-ingestion surfaces."""

    @pytest.fixture
    def doc_client(self, user):
        from api import document_ingestion_routes as doc_routes
        from core.security_dependencies import get_current_user as sec_user

        app = FastAPI()
        app.include_router(doc_routes.router)
        app.dependency_overrides[sec_user] = lambda: user
        c = TestClient(app, raise_server_exceptions=False)
        yield c
        app.dependency_overrides.clear()

    def test_sync_records_per_app(self, doc_client, user):
        stub = MagicMock()
        stub.sync_integration = AsyncMock(
            return_value={"success": True, "files_found": 9,
                          "files_ingested": 7, "files_skipped": 2, "errors": []}
        )
        with patch(
            "core.auto_document_ingestion.get_document_ingestion_service",
            return_value=stub,
        ), patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            return_value=_FakeHybrid(),
        ) as hybrid_factory:
            resp = doc_client.post("/api/document-ingestion/sync/google_drive")
        assert resp.status_code == 200
        assert resp.json()["files_ingested"] == 7
        recorded = hybrid_factory.return_value.recorded
        assert recorded == [("google_drive", 7, True)]

    def test_sync_for_suite_app_records_under_zoho(self, doc_client):
        stub = MagicMock()
        stub.sync_integration = AsyncMock(
            return_value={"success": True, "files_found": 3,
                          "files_ingested": 3, "files_skipped": 0, "errors": []}
        )
        with patch(
            "core.auto_document_ingestion.get_document_ingestion_service",
            return_value=stub,
        ), patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            return_value=_FakeHybrid(),
        ) as hybrid_factory:
            doc_client.post("/api/document-ingestion/sync/zoho-workdrive")
        recorded = hybrid_factory.return_value.recorded
        assert recorded == [("zoho", 3, True)]

    def test_index_structure_records_rows_written(self, doc_client):
        indexer = MagicMock()
        indexer.index_structure = AsyncMock(
            return_value={"success": True, "integration_id": "onedrive",
                          "rows_found": 120, "rows_written": 118,
                          "counts": {"file": 118}, "truncated": False}
        )
        with patch(
            # module-level import in the routes module — patch it there
            "api.document_ingestion_routes.IntegrationMemoryIndexer",
            return_value=indexer,
        ), patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            return_value=_FakeHybrid(),
        ) as hybrid_factory:
            resp = doc_client.post(
                "/api/document-ingestion/integrations/onedrive/index-structure",
                json={},
            )
        assert resp.status_code == 200
        recorded = hybrid_factory.return_value.recorded
        assert recorded == [("onedrive", 118, True)]

    def test_sync_recording_failure_does_not_break_sync(self, doc_client):
        stub = MagicMock()
        stub.sync_integration = AsyncMock(
            return_value={"success": True, "files_found": 1,
                          "files_ingested": 1, "files_skipped": 0, "errors": []}
        )
        with patch(
            "core.auto_document_ingestion.get_document_ingestion_service",
            return_value=stub,
        ), patch(
            # the helper imports this inside its body — a factory explosion
            # must be swallowed, not surfaced as a failed sync
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            side_effect=RuntimeError("nope"),
        ):
            resp = doc_client.post("/api/document-ingestion/sync/dropbox")
        # The helper swallows the recording failure; the sync still succeeds.
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestStorageSyncRoutes:
    """Box / Dropbox full-tree syncs record per-app feedback."""

    def test_box_sync_records(self, user):
        from integrations import box_routes

        app = FastAPI()
        app.include_router(box_routes.router)
        app.dependency_overrides[get_current_user] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        with patch.object(
            box_routes.box_service, "full_sync",
            new=AsyncMock(return_value={"success": True, "files_ingested": 5}),
        ), patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            return_value=_FakeHybrid(),
        ) as hybrid_factory:
            resp = client.post("/api/box/sync")
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert hybrid_factory.return_value.recorded == [("box", 5, True)]

    def test_dropbox_sync_records(self, user):
        from integrations import dropbox_routes

        app = FastAPI()
        app.include_router(dropbox_routes.router)
        app.dependency_overrides[get_current_user] = lambda: user
        client = TestClient(app, raise_server_exceptions=False)
        with patch.object(
            dropbox_routes.dropbox_auth_handler, "ensure_valid_token",
            new=AsyncMock(return_value="tok"),
        ), patch.object(
            dropbox_routes.dropbox_service, "full_sync",
            new=AsyncMock(return_value={"success": True, "files_ingested": 6}),
        ), patch(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            return_value=_FakeHybrid(),
        ) as hybrid_factory:
            resp = client.post("/api/dropbox/files/sync")
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert hybrid_factory.return_value.recorded == [("dropbox", 6, True)]


def test_zoho_full_sync_route_records_under_suite_key(user):
    from api import zoho_workdrive_routes as zwr

    app = FastAPI()
    app.include_router(zwr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app, raise_server_exceptions=False)
    with patch.object(
        zwr.zoho_service, "full_sync",
        new=AsyncMock(return_value={"success": True, "files_ingested": 11}),
    ), patch(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        return_value=_FakeHybrid(),
    ) as hybrid_factory:
        resp = client.post("/api/zoho-workdrive/full-sync")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert hybrid_factory.return_value.recorded == [("zoho", 11, True)]


class TestAgentJitIngestRecords:
    """The agent's just-in-time item pull records per-app feedback too."""

    @pytest.mark.asyncio
    async def test_ingest_item_records_for_its_integration(self, monkeypatch):
        import tools.drive_tool as dt

        class _Settings:
            enabled = True
            max_file_size_mb = None

        monkeypatch.setattr(dt, "_settings_for", lambda iid, ws: _Settings())
        monkeypatch.setitem(
            dt.FILE_FETCHERS, "onedrive", AsyncMock(return_value=b"pdf-bytes")
        )
        monkeypatch.setitem(
            dt.STRUCTURE_ADAPTERS, "onedrive", AsyncMock(return_value=[])
        )

        class _FakeIngestor:
            def __init__(self, *a, **k):
                pass

            async def process_file_bytes(self, *a, **kw):
                return {"status": "ingested"}

        recorded = []

        class _FakeHybrid:
            def record_sync_completion(self, integration_id, records, success):
                recorded.append((integration_id, records, success))

        monkeypatch.setattr(
            "core.auto_document_ingestion.AutoDocumentIngestionService",
            _FakeIngestor,
        )
        monkeypatch.setattr(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            lambda ws: _FakeHybrid(),
        )

        # pytest-asyncio (NOT asyncio.run — closing the loop here would break
        # later sync tests that rely on a set main-thread loop).
        out = await dt.integration_ingest_item(
            "onedrive", "file-1", file_name="a.pdf", workspace_id="ws-9"
        )
        assert out["success"] is True
        assert recorded == [("onedrive", 1, True)]

    def test_workspace_id_reaches_the_recorder_without_a_user(self, monkeypatch):
        """Agent tools have no user object — the workspace they pass must be
        the one feedback lands in."""
        from core.ingestion_feedback import record_ingestion_feedback

        seen = {}

        class _FakeHybrid:
            def record_sync_completion(self, integration_id, records, success):
                seen["key"] = integration_id

        def _factory(ws):
            seen["ws"] = ws
            return _FakeHybrid()

        monkeypatch.setattr(
            "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
            _factory,
        )

        record_ingestion_feedback(
            None, "zoho_crm", 1, True, workspace_id="ws-agent"
        )
        assert seen["ws"] == "ws-agent"
        assert seen["key"] == "zoho"  # suite app → shared sync key
