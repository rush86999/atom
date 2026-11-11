"""Focused regression: recoverable native workbook recalc failure.

The runtime selects LibreOffice when ``soffice`` is present.  In the reported
#846 journey the installed binary aborted with
``com::sun::star::uno::RuntimeException`` and wrote no output, so the runtime
returned the untouched file and the public write result stayed partial even
though the existing ``formulas`` fallback was installed.

These tests use a deterministic failing executable and, where feasible, the
real ``formulas`` library.  No app server, database, provider or live
LibreOffice install is used.
"""

from __future__ import annotations

import asyncio
import stat
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from openpyxl import Workbook, load_workbook


def _book(path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = 1
    ws["A2"] = 2
    ws["A3"] = "=SUM(A1:A2)"
    wb.save(path)
    return path


def _failing_soffice(tmp_path: Path) -> Path:
    path = tmp_path / "fake-soffice"
    path.write_text(
        "#!/bin/sh\n"
        "echo 'com::sun::star::uno::RuntimeException' >&2\n"
        "exit 1\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class _FakeTmpDir:
    def __init__(self, path: Path):
        self._path = path

    def __enter__(self) -> str:
        return str(self._path)

    def __exit__(self, *exc) -> bool:
        return False


def test_native_no_output_falls_back_to_real_formulas(tmp_path):
    """The reported case: soffice aborts with no output → formulas caches it."""
    from core.workbook_runtime import WorkbookRuntime

    path = _book(tmp_path / "book.xlsx")
    rt = WorkbookRuntime()
    rt._soffice = str(_failing_soffice(tmp_path))
    rt._has_formulas = True

    engine = {}
    result = asyncio.run(rt.recalculate(path, engine_out=engine))

    assert result == path
    assert engine == {"engine": "formulas"}
    # Formula source survives; only the cached value is added.
    assert load_workbook(path, data_only=False)["Sheet1"]["A3"].value == "=SUM(A1:A2)"
    assert load_workbook(path, data_only=True)["Sheet1"]["A3"].value == 3


def test_native_success_is_kept_and_fallback_is_not_used(tmp_path):
    from core.workbook_runtime import WorkbookRuntime

    path = _book(tmp_path / "book.xlsx")
    rt = WorkbookRuntime()
    rt._soffice = "/usr/bin/soffice"
    rt._has_formulas = True
    rt._recalc_with_soffice = AsyncMock(return_value=path)
    rt._recalc_with_formulas = AsyncMock(return_value=path)

    engine = {}
    result = asyncio.run(rt.recalculate(path, engine_out=engine))

    assert result == path
    assert engine == {"engine": "libreoffice"}
    rt._recalc_with_formulas.assert_not_awaited()


def test_native_valid_zip_but_not_xlsx_is_rejected(tmp_path, monkeypatch):
    from core import workbook_runtime as wb

    path = _book(tmp_path / "book.xlsx")
    rt = wb.WorkbookRuntime()
    rt._soffice = "/usr/bin/soffice"
    rt._has_formulas = True
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with zipfile.ZipFile(out_dir / path.name, "w") as archive:
        archive.writestr("readme.txt", "a valid ZIP, but not a workbook")
    rt._recalc_with_formulas = AsyncMock(return_value=path)

    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"")
    proc.returncode = 0

    monkeypatch.setattr(
        wb.tempfile, "TemporaryDirectory",
        lambda: _FakeTmpDir(out_dir))
    monkeypatch.setattr(
        wb.asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))

    engine = {}
    result = asyncio.run(rt.recalculate(path, engine_out=engine))

    assert result == path
    assert engine == {"engine": "formulas"}
    rt._recalc_with_formulas.assert_awaited_once()
    # The ZIP was not accepted as a workbook.
    assert load_workbook(path, data_only=False)["Sheet1"]["A3"].value == "=SUM(A1:A2)"


def test_native_nonzero_exit_with_valid_workbook_is_rejected(tmp_path, monkeypatch):
    from core import workbook_runtime as wb

    path = _book(tmp_path / "book.xlsx")
    rt = wb.WorkbookRuntime()
    rt._soffice = "/usr/bin/soffice"
    rt._has_formulas = True
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # A readable workbook is still not acceptable when the CLI failed.
    native = Workbook()
    native.active["A1"] = "native-marker"
    native.save(out_dir / path.name)
    rt._recalc_with_formulas = AsyncMock(return_value=path)

    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"RuntimeException")
    proc.returncode = 2

    monkeypatch.setattr(
        wb.tempfile, "TemporaryDirectory",
        lambda: _FakeTmpDir(out_dir))
    monkeypatch.setattr(
        wb.asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))

    engine = {}
    result = asyncio.run(rt.recalculate(path, engine_out=engine))

    assert result == path
    assert engine == {"engine": "formulas"}
    rt._recalc_with_formulas.assert_awaited_once()
    # The failed native output never replaced the authoritative workbook.
    assert load_workbook(path, data_only=False)["Sheet1"]["A1"].value == 1
    assert load_workbook(path, data_only=False)["Sheet1"]["A3"].value == "=SUM(A1:A2)"


def test_atomic_replace_failure_preserves_original_and_cleans_stage(
        tmp_path, monkeypatch):
    from core import workbook_runtime as wb

    path = _book(tmp_path / "book.xlsx")
    before = path.read_bytes()
    rt = wb.WorkbookRuntime()
    rt._soffice = "/usr/bin/soffice"
    rt._has_formulas = True
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _book(out_dir / path.name)

    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"")
    proc.returncode = 0

    monkeypatch.setattr(
        wb.tempfile, "TemporaryDirectory",
        lambda: _FakeTmpDir(out_dir))
    monkeypatch.setattr(
        wb.asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))
    monkeypatch.setattr(
        wb.os, "replace", Mock(side_effect=OSError("replace failed")))

    result = asyncio.run(rt._recalc_with_soffice(path))

    assert result is None
    assert path.read_bytes() == before
    assert list(tmp_path.glob(f".{path.name}.*")) == []


def test_native_timeout_kills_and_reaps_the_child(tmp_path, monkeypatch):
    from core import workbook_runtime as wb

    path = _book(tmp_path / "book.xlsx")
    rt = wb.WorkbookRuntime()
    rt._soffice = "/usr/bin/soffice"

    proc = Mock()
    proc.returncode = None
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    proc.kill = Mock()
    proc.wait = AsyncMock(
        side_effect=lambda: setattr(proc, "returncode", -9))

    monkeypatch.setattr(
        wb.asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))

    result = asyncio.run(rt._recalc_with_soffice(path))

    assert result is None
    proc.kill.assert_called_once()
    proc.wait.assert_awaited_once()


def test_macro_enabled_native_failure_keeps_original_and_skips_fallback(tmp_path):
    from core.workbook_runtime import WorkbookRuntime

    path = tmp_path / "book.xlsm"
    path.write_bytes(b"macro payload placeholder")
    rt = WorkbookRuntime()
    rt._soffice = "/usr/bin/soffice"
    rt._has_formulas = True
    rt._recalc_with_soffice = AsyncMock(return_value=None)
    rt._recalc_with_formulas = AsyncMock(return_value=path)

    engine = {}
    result = asyncio.run(rt.recalculate(path, engine_out=engine))

    assert result == path
    assert engine == {"engine": "none"}
    rt._recalc_with_formulas.assert_not_awaited()
    assert path.read_bytes() == b"macro payload placeholder"


def test_write_cell_after_native_failure_reports_formulas_complete(tmp_path, monkeypatch):
    """The ordinary first-sync path must return a truthful complete result."""
    from core.office_service import ExcelManager
    from core.workbook_runtime import WorkbookRuntime

    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    path = _book(tmp_path / "book.xlsx")
    rt = WorkbookRuntime()
    rt._soffice = str(_failing_soffice(tmp_path))
    rt._has_formulas = True

    with patch("core.workbook_runtime.get_workbook_runtime", return_value=rt):
        result = ExcelManager().write_cell(
            str(path), "/Sheet1/C1", "=A1+A2", is_formula=True)

    assert result["success"] is True
    assert result["recalc_status"] == "complete"
    assert result["recalc_engine"] == "formulas"
    assert result["formula_gaps"] == []
    assert result["value"] == 3
    assert load_workbook(path, data_only=False)["Sheet1"]["C1"].value == "=A1+A2"
    assert load_workbook(path, data_only=True)["Sheet1"]["C1"].value == 3


def test_explicit_recalculate_reports_failure_when_engine_none(
        tmp_path, monkeypatch):
    """The explicit route can express failure: engine_out none must not pass."""
    from core.office_service import ExcelManager
    from core.workbook_runtime import WorkbookRuntime

    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    path = _book(tmp_path / "book.xlsx")
    rt = WorkbookRuntime()

    async def _no_engine(file_path, *, engine_out=None):
        engine_out["engine"] = "none"
        return Path(file_path)

    rt.recalculate = _no_engine
    with patch("core.workbook_runtime.get_workbook_runtime", return_value=rt):
        result = asyncio.run(ExcelManager.recalculate(str(path)))

    assert result["success"] is False
    assert "No formula engine" in result["error"]
