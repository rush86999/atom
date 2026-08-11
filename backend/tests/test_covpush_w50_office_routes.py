"""Coverage wave 50 — api/office_routes.py (72% → 90%+).

Every endpoint: success + service-failure 400 + path-validation 400 + 401
unauthenticated. OfficeService + OfficeSyncService mocked — no filesystem.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.office_routes import router
from core.auth import get_current_user
from core.database import get_db_session


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/office")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_db_session] = lambda: Mock()
    return TestClient(app)


@pytest.fixture
def office(monkeypatch):
    svc = MagicMock()
    for name in ("read_range", "write_cell"):
        getattr(svc.excel, name).return_value = {"success": True, "data": {}}
    for name in ("recalculate", "insert_rows", "insert_columns",
                 "get_evaluated_range", "add_pivot_table", "run_excel_macro"):
        m = AsyncMock(return_value={"success": True, "data": {}})
        setattr(svc.excel, name, m)
    svc.word.read_document.return_value = {"success": True, "data": {}}
    svc.word.modify_document.return_value = {"success": True, "data": {}}
    svc.pptx.read_slides.return_value = {"success": True, "data": {}}
    svc.pptx.modify_slides.return_value = {"success": True, "data": {}}
    monkeypatch.setattr("api.office_routes.office_service", svc)
    monkeypatch.setattr("api.office_routes._validate_office_path", lambda p: p)
    return svc


class TestReadExcel:
    def test_success(self, client, office):
        assert client.get("/api/v1/office/excel", params={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1"}).status_code == 200

    def test_service_failure_400(self, client, office):
        office.excel.read_range.return_value = {"success": False, "error": "bad"}
        assert client.get("/api/v1/office/excel", params={
            "file_path": "a.xlsx"}).status_code == 400

    def test_path_validation_400(self, client, office):
        with patch("api.office_routes._validate_office_path",
                   side_effect=ValueError("outside scope")):
            resp = client.get("/api/v1/office/excel", params={"file_path": "../evil.xlsx"})
        assert resp.status_code == 400

    def test_unauth_401(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/office")
        assert TestClient(app).get("/api/v1/office/excel",
                                   params={"file_path": "a.xlsx"}).status_code == 401


class TestWriteExcel:
    def test_success(self, client, office):
        assert client.post("/api/v1/office/excel", json={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1", "value": 5}).status_code == 200

    def test_failure_400(self, client, office):
        office.excel.write_cell.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/excel", json={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1", "value": 5}).status_code == 400

    def test_formula_flag_forwarded(self, client, office):
        client.post("/api/v1/office/excel", json={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A1", "value": "=1+1",
            "is_formula": True})
        office.excel.write_cell.assert_called_once()


class TestRecalculate:
    def test_success(self, client, office):
        assert client.post("/api/v1/office/excel/recalculate",
                           params={"file_path": "a.xlsx"}).status_code == 200

    def test_failure_400(self, client, office):
        office.excel.recalculate.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/excel/recalculate",
                           params={"file_path": "a.xlsx"}).status_code == 400


class TestInsertRowsColumns:
    def test_insert_rows_success_and_failure(self, client, office):
        assert client.post("/api/v1/office/excel/insert-rows", params={
            "file_path": "a.xlsx", "sheet_name": "S", "row": 2}).status_code == 200
        office.excel.insert_rows.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/excel/insert-rows", params={
            "file_path": "a.xlsx", "sheet_name": "S", "row": 2}).status_code == 400

    def test_insert_columns_success_and_failure(self, client, office):
        assert client.post("/api/v1/office/excel/insert-columns", params={
            "file_path": "a.xlsx", "sheet_name": "S", "column": 2}).status_code == 200
        office.excel.insert_columns.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/excel/insert-columns", params={
            "file_path": "a.xlsx", "sheet_name": "S", "column": 2}).status_code == 400


class TestFormulaResult:
    def test_success_and_failure(self, client, office):
        assert client.get("/api/v1/office/excel/formula-result", params={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A4"}).status_code == 200
        office.excel.get_evaluated_range.return_value = {"success": False, "error": "bad"}
        assert client.get("/api/v1/office/excel/formula-result", params={
            "file_path": "a.xlsx", "cell_path": "/Sheet1/A4"}).status_code == 400


class TestPivotTable:
    def test_success_and_failure(self, client, office):
        body = {"file_path": "a.xlsx", "sheet_name": "S", "pivot_sheet_name": "P",
                "data_range": "A1:C10", "rows": ["r"], "columns": ["c"], "values": []}
        assert client.post("/api/v1/office/excel/pivot-table", json=body).status_code == 200
        office.excel.add_pivot_table.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/excel/pivot-table", json=body).status_code == 400


class TestRunMacro:
    def test_success_and_failure(self, client, office):
        body = {"file_path": "a.xlsx", "macro_name": "M"}
        assert client.post("/api/v1/office/excel/run-macro", json=body).status_code == 200
        office.excel.run_excel_macro.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/excel/run-macro", json=body).status_code == 400


class TestWord:
    def test_read_success_and_failure(self, client, office):
        assert client.get("/api/v1/office/word",
                          params={"file_path": "a.docx"}).status_code == 200
        office.word.read_document.return_value = {"success": False, "error": "bad"}
        assert client.get("/api/v1/office/word",
                          params={"file_path": "a.docx"}).status_code == 400

    def test_modify_success_and_failure(self, client, office):
        body = {"file_path": "a.docx", "action": "append", "content": "x"}
        assert client.post("/api/v1/office/word", json=body).status_code == 200
        office.word.modify_document.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/word", json=body).status_code == 400


class TestPptx:
    def test_read_success_and_failure(self, client, office):
        assert client.get("/api/v1/office/pptx",
                          params={"file_path": "a.pptx"}).status_code == 200
        office.pptx.read_slides.return_value = {"success": False, "error": "bad"}
        assert client.get("/api/v1/office/pptx",
                          params={"file_path": "a.pptx"}).status_code == 400

    def test_modify_success_and_failure(self, client, office):
        body = {"file_path": "a.pptx", "action": "add_slide", "options": {}}
        assert client.post("/api/v1/office/pptx", json=body).status_code == 200
        office.pptx.modify_slides.return_value = {"success": False, "error": "bad"}
        assert client.post("/api/v1/office/pptx", json=body).status_code == 400


class TestPresentAndSync:
    def test_present_success(self, client, office):
        with patch("api.office_routes.OfficeSyncService") as sync_cls:
            sync = sync_cls.return_value
            sync.broadcast_file_update = Mock()
            resp = client.post("/api/v1/office/present", json={
                "file_path": "a.xlsx", "user_id": "forged"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # R58: identity from token, never the body
        sync.broadcast_file_update.assert_called_once()
        _, kwargs = sync.broadcast_file_update.call_args
        assert kwargs["user_id"] == "u1"

    def test_present_canvas_id_generated(self, client, office):
        with patch("api.office_routes.OfficeSyncService") as sync_cls:
            resp = client.post("/api/v1/office/present", json={
                "file_path": "a.xlsx", "user_id": "x"})
        assert resp.json()["canvas_id"].startswith("canvas_")

    def test_sync_update_success_and_failure(self, client, office):
        with patch("api.office_routes.OfficeSyncService") as sync_cls:
            sync = sync_cls.return_value
            sync.sync_canvas_to_file.return_value = {"success": True}
            resp = client.post("/api/v1/office/sync-update", json={
                "canvas_id": "c1", "file_path": "a.xlsx", "user_id": "forged",
                "edit_type": "cell", "data": {}})
            assert resp.status_code == 200
            sync.sync_canvas_to_file.assert_called_once()
            _, kwargs = sync.sync_canvas_to_file.call_args
            assert kwargs["user_id"] == "u1"
            sync.sync_canvas_to_file.return_value = {"success": False, "error": "bad"}
            resp = client.post("/api/v1/office/sync-update", json={
                "canvas_id": "c1", "file_path": "a.xlsx", "user_id": "x",
                "edit_type": "cell", "data": {}})
            assert resp.status_code == 400
