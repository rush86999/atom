"""
Round 52 — Office service str(e) leak sweep
(Red-Green-Refactor).

core/office_service.py returns raw exception strings in every failure dict,
and api/office_routes.py (mounted via safe_import_router) forwards those
dicts verbatim into HTTPException(detail=...) on 13 endpoints. Internal
exception details (filesystem paths, openpyxl/docx internals, line info)
therefore reach the client. Fix: generic error strings in the service
(descriptive of the operation, not the exception); logger retains {e}.
"""

from unittest.mock import MagicMock, patch

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user

SECRET = "secret-internal-detail-xyz"


def _make_client(monkeypatch):
    from api.office_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id="u-52", email="u@example.com"
    )
    return TestClient(app, raise_server_exceptions=False)


class TestOfficeServiceNoLeak:
    def test_excel_read_range_does_not_leak(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "book.xlsx"
        f.write_bytes(b"dummy")

        from core.office_service import ExcelManager

        with patch(
            "core.office_service.openpyxl.load_workbook",
            side_effect=RuntimeError(SECRET),
        ):
            res = ExcelManager().read_range(str(f), "/Sheet1/A1")

        assert res.get("success") is False
        assert SECRET not in res.get("error", ""), (
            f"read_range leaks internal exception detail: {res.get('error')!r}"
        )

    def test_excel_write_cell_does_not_leak(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "book.xlsx"
        f.write_bytes(b"dummy")

        from core.office_service import ExcelManager

        with patch(
            "core.office_service.openpyxl.load_workbook",
            side_effect=RuntimeError(SECRET),
        ):
            res = ExcelManager().write_cell(str(f), "/Sheet1/A1", "=1+1")

        assert res.get("success") is False
        assert SECRET not in res.get("error", ""), (
            f"write_cell leaks internal exception detail: {res.get('error')!r}"
        )

    def test_word_read_does_not_leak(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "doc.docx"
        f.write_bytes(b"dummy")

        from core.office_service import WordManager

        with patch(
            "core.office_service.docx.Document",
            side_effect=RuntimeError(SECRET),
        ):
            res = WordManager().read_document(str(f))

        assert res.get("success") is False
        assert SECRET not in res.get("error", ""), (
            f"read_document leaks internal exception detail: {res.get('error')!r}"
        )

    def test_pptx_read_does_not_leak(self, monkeypatch, tmp_path):
        pytest.importorskip("pptx")
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "deck.pptx"
        f.write_bytes(b"dummy")

        from core.office_service import PowerPointManager

        with patch(
            "core.office_service.pptx.Presentation",
            side_effect=RuntimeError(SECRET),
        ):
            res = PowerPointManager().read_presentation(str(f))

        assert res.get("success") is False
        assert SECRET not in res.get("error", ""), (
            f"read_presentation leaks internal exception detail: {res.get('error')!r}"
        )

    def test_render_html_does_not_leak(self, monkeypatch, tmp_path):
        pytest.importorskip("mammoth")
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "doc.docx"
        f.write_bytes(b"dummy")

        from core.office_service import DocumentRenderer, MAMMOTH_AVAILABLE

        with patch("core.office_service.MAMMOTH_AVAILABLE", True), patch(
            "core.office_service.mammoth.convert_to_html",
            side_effect=RuntimeError(SECRET),
        ):
            res = DocumentRenderer().render_to_html(str(f))

        assert res.get("success") is False
        assert SECRET not in res.get("error", ""), (
            f"render_to_html leaks internal exception detail: {res.get('error')!r}"
        )

    def test_http_surface_does_not_leak(self, monkeypatch, tmp_path):
        """GET /excel — real service + real route, end to end."""
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
        f = tmp_path / "book.xlsx"
        f.write_bytes(b"dummy")

        with patch(
            "core.office_service.openpyxl.load_workbook",
            side_effect=RuntimeError(SECRET),
        ):
            client = _make_client(monkeypatch)
            resp = client.get(
                "/excel", params={"file_path": str(f), "cell_path": "/Sheet1/A1"}
            )

        assert resp.status_code == 400
        assert SECRET not in resp.text, (
            f"HTTP surface leaks internal exception detail: {resp.text[:200]!r}"
        )

    def test_office_routes_module_imports_cleanly(self):
        """Bonus: office_routes used List[] with no List import — the module
        never imported (NameError). In dev safe_import_router silently mounted
        an empty router (all 14 endpoints 404); in production it raised and
        crashed app startup."""
        import importlib

        import api.office_routes

        importlib.reload(api.office_routes)
        assert hasattr(api.office_routes, "router")
        assert len(api.office_routes.router.routes) >= 10, (
            "office router registered no routes — module was dead"
        )
        assert hasattr(api.office_routes, "uuid"), (
            "office_routes uses uuid.uuid4() in /present without importing uuid"
        )
