# -*- coding: utf-8 -*-
"""Coverage wave 106 — cli/main.py (Atom OS CLI entry).
Fully mocked (main_api_app, uvicorn, DaemonManager, OfficeService, cache
preseeding) — no server started, no daemon spawned, no network, no real
documents touched.

Covers: --version, group no-arg help, start (personal/enterprise edition
display, dev reload, host-mount confirm accept/decline + env vars),
daemon (background success / RuntimeError / IOError, foreground delegation),
stop (with pid / without / not running), status (stopped, running full,
zero-metric suppression, note), execute (missing command, with command),
config (+ --show-daemon), preseed-cache (default-all, pricing, models,
governance, error-in-results, exception), office excel/word/pptx/render
read+write success and error paths, _confirm_host_mount decline,
__main__ entry.
"""
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from cli import main as cli_main


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def start_mocks():
    """Mocks required by the `start` command and daemon --foreground."""
    fake_app = MagicMock()
    fake_app.app = object()
    svc = MagicMock()
    svc.is_personal = True
    with patch.dict(sys.modules, {"main_api_app": fake_app}), \
         patch("core.package_feature_service.get_package_feature_service", return_value=svc), \
         patch("uvicorn.run") as u:
        yield u, svc


@pytest.fixture()
def dm():
    """Patched cli.daemon.DaemonManager used by daemon/stop/status/config."""
    mgr = MagicMock()
    with patch("cli.daemon.DaemonManager", new=mgr):
        yield mgr


def _office_svc():
    svc = MagicMock()
    svc.excel.read_range.return_value = {
        "success": True, "cells": [[{"value": "a"}, {"value": "b"}], [{"value": "c"}]],
    }
    svc.excel.write_cell.return_value = {"success": True, "message": "written"}
    svc.word.read_document.return_value = {
        "success": True,
        "paragraphs": [{"style": "Normal", "text": "para1"}],
        "tables": [{"index": 0, "rows": [["r1c1", "r1c2"]]}],
    }
    svc.word.modify_document.return_value = {"success": True, "message": "word written"}
    svc.pptx.read_slides.return_value = {
        "success": True,
        "slides": [{"slide_index": 0, "shapes": [
            {"type": "text", "text": "hello"},
            {"type": "table", "table": [["x"]]},
        ]}],
    }
    svc.pptx.modify_slides.return_value = {"success": True, "message": "pptx written"}
    svc.renderer.render_to_html.return_value = {"success": True, "html": "<p>doc</p>"}
    return svc


# ============================================================================
# group basics
# ============================================================================

def test_version_option(runner):
    res = runner.invoke(cli_main.main_cli, ["--version"])
    assert res.exit_code == 0
    assert "0.1.0" in res.output


def test_group_no_args_shows_help(runner):
    res = runner.invoke(cli_main.main_cli, [])
    assert res.exit_code == 2
    assert "Usage:" in res.output


# ============================================================================
# start
# ============================================================================

def test_start_personal(runner, start_mocks):
    u, _ = start_mocks
    res = runner.invoke(cli_main.main_cli, ["start", "--port", "8000"])
    assert res.exit_code == 0
    assert "Personal Edition" in res.output
    assert "Starting Atom OS" in res.output
    assert "Host: 0.0.0.0" in res.output
    assert "Port: 8000" in res.output
    u.assert_called_once_with("main_api_app:app", host="0.0.0.0", port=8000,
                              workers=1, log_level="info", access_log=True)


def test_start_enterprise_display(runner, start_mocks):
    _, svc = start_mocks
    svc.is_personal = False
    res = runner.invoke(cli_main.main_cli, ["start"])
    assert res.exit_code == 0
    assert "Enterprise Edition" in res.output


def test_start_dev_mode(runner, start_mocks):
    u, _ = start_mocks
    res = runner.invoke(cli_main.main_cli, ["start", "--dev", "--host", "localhost", "--port", "3000"])
    assert res.exit_code == 0
    u.assert_called_once_with("main_api_app:app", host="localhost", port=3000,
                              reload=True, log_level="info")


def test_start_host_mount_confirmed(runner, start_mocks):
    u, _ = start_mocks
    try:
        res = runner.invoke(cli_main.main_cli, ["start", "--host-mount"], input="y\n")
        assert res.exit_code == 0
        assert "HOST FILESYSTEM MOUNT" in res.output
        assert "Host filesystem mount ENABLED" in res.output
        assert "Host mount: True" in res.output
        assert os.environ.get("ATOM_HOST_MOUNT_ENABLED") == "true"
        assert "ATOM_HOST_MOUNT_DIRS" in os.environ
    finally:
        os.environ.pop("ATOM_HOST_MOUNT_ENABLED", None)
        os.environ.pop("ATOM_HOST_MOUNT_DIRS", None)


def test_start_host_mount_declined(runner, start_mocks):
    res = runner.invoke(cli_main.main_cli, ["start", "--host-mount"], input="n\n")
    assert res.exit_code == 1
    assert "Host mount cancelled." in res.output


# ============================================================================
# daemon
# ============================================================================

def test_daemon_background(runner, dm):
    dm.start_daemon.return_value = 4242
    res = runner.invoke(cli_main.main_cli, ["daemon", "--port", "9000"])
    assert res.exit_code == 0
    assert "started as daemon" in res.output
    assert "PID: 4242" in res.output
    assert "Dashboard: http://0.0.0.0:9000" in res.output
    dm.start_daemon.assert_called_once_with(9000, "0.0.0.0", 1, False, False)


def test_daemon_runtime_error(runner, dm):
    dm.start_daemon.side_effect = RuntimeError("already running")
    res = runner.invoke(cli_main.main_cli, ["daemon"])
    assert res.exit_code == 1
    assert "already running" in res.output


def test_daemon_ioerror(runner, dm):
    dm.start_daemon.side_effect = IOError("cannot write pid")
    res = runner.invoke(cli_main.main_cli, ["daemon"])
    assert res.exit_code == 1
    assert "cannot write pid" in res.output


def test_daemon_foreground(runner, dm, start_mocks):
    u, _ = start_mocks
    res = runner.invoke(cli_main.main_cli, ["daemon", "--foreground", "--port", "7777"])
    assert res.exit_code == 0
    assert "foreground mode" in res.output
    u.assert_called_once_with("main_api_app:app", host="0.0.0.0", port=7777,
                              workers=1, log_level="info", access_log=True)
    dm.start_daemon.assert_not_called()


# ============================================================================
# stop / status
# ============================================================================

def test_stop_with_pid(runner, dm):
    dm.stop_daemon.return_value = True
    dm.get_pid.return_value = 4242
    res = runner.invoke(cli_main.main_cli, ["stop"])
    assert res.exit_code == 0
    assert "stopped (PID: 4242)" in res.output


def test_stop_without_pid(runner, dm):
    dm.stop_daemon.return_value = True
    dm.get_pid.return_value = None
    res = runner.invoke(cli_main.main_cli, ["stop"])
    assert res.exit_code == 0
    assert "Atom OS stopped" in res.output


def test_stop_not_running(runner, dm):
    dm.stop_daemon.return_value = False
    res = runner.invoke(cli_main.main_cli, ["stop"])
    assert res.exit_code == 0
    assert "was not running" in res.output


def test_status_stopped(runner, dm):
    dm.get_status.return_value = {"running": False}
    res = runner.invoke(cli_main.main_cli, ["status"])
    assert res.exit_code == 0
    assert "STOPPED" in res.output


def test_status_running_full(runner, dm):
    dm.get_status.return_value = {
        "running": True, "pid": 4242, "memory_mb": 256.5, "cpu_percent": 5.2,
        "uptime_seconds": 3600.0,
    }
    res = runner.invoke(cli_main.main_cli, ["status"])
    assert res.exit_code == 0
    assert "RUNNING" in res.output
    assert "PID: 4242" in res.output
    assert "256.5 MB" in res.output
    assert "5.2%" in res.output
    assert "Uptime: 3600s" in res.output
    assert "Dashboard: http://localhost:8000" in res.output


def test_status_running_zero_metrics_suppressed(runner, dm):
    dm.get_status.return_value = {"running": True, "pid": 4242, "memory_mb": 0.0,
                                  "cpu_percent": 0.0, "uptime_seconds": 0.0}
    res = runner.invoke(cli_main.main_cli, ["status"])
    assert res.exit_code == 0
    assert "MB" not in res.output
    assert "%" not in res.output


def test_status_running_with_note(runner, dm):
    dm.get_status.return_value = {"running": True, "pid": 4242, "note": "watch out"}
    res = runner.invoke(cli_main.main_cli, ["status"])
    assert res.exit_code == 0
    assert "Note: watch out" in res.output


# ============================================================================
# execute / config
# ============================================================================

def test_execute_missing_command(runner):
    res = runner.invoke(cli_main.main_cli, ["execute"])
    assert res.exit_code == 1
    assert "Error: command required" in res.output


def test_execute_with_command(runner):
    res = runner.invoke(cli_main.main_cli, ["execute", "agent.chat('hi')"])
    assert res.exit_code == 0
    assert "Executing Atom command" in res.output
    assert "Command: agent.chat('hi')" in res.output
    assert "not yet implemented" in res.output


def test_config(runner):
    res = runner.invoke(cli_main.main_cli, ["config"])
    assert res.exit_code == 0
    assert "Atom OS Configuration" in res.output
    assert "Environment Variables:" in res.output
    assert "DATABASE_URL" in res.output


def test_config_show_daemon(runner, dm):
    dm.is_running.return_value = True
    res = runner.invoke(cli_main.main_cli, ["config", "--show-daemon"])
    assert res.exit_code == 0
    assert "Daemon Configuration:" in res.output
    assert "Running: True" in res.output


# ============================================================================
# preseed-cache
# ============================================================================

def test_preseed_defaults_to_all(runner):
    with patch("core.byok_cache_preseeding.preseed_all_caches", AsyncMock(return_value={"ok": True})) as all_c, \
         patch("core.byok_cache_preseeding.print_preseed_results") as ppr:
        res = runner.invoke(cli_main.main_cli, ["preseed-cache", "--workspace", "ws-1", "--verbose"])
    assert res.exit_code == 0
    all_c.assert_awaited_once_with(workspace_id="ws-1", verbose=True)
    ppr.assert_called_once_with({"ok": True})


def test_preseed_pricing_only(runner):
    with patch("core.byok_cache_preseeding.preseed_pricing_cache", AsyncMock(return_value={"p": 1})) as pricing, \
         patch("core.byok_cache_preseeding.print_preseed_results"):
        res = runner.invoke(cli_main.main_cli, ["preseed-cache", "--pricing"])
    assert res.exit_code == 0
    pricing.assert_awaited_once_with(verbose=False)


def test_preseed_models_only(runner):
    with patch("core.byok_cache_preseeding.preseed_cognitive_models", AsyncMock(return_value={"m": 1})) as models, \
         patch("core.byok_cache_preseeding.print_preseed_results"):
        res = runner.invoke(cli_main.main_cli, ["preseed-cache", "--models"])
    assert res.exit_code == 0
    models.assert_awaited_once_with(verbose=False)


def test_preseed_governance_only(runner):
    with patch("core.byok_cache_preseeding.preseed_governance_cache", AsyncMock(return_value={"g": 1})) as gov, \
         patch("core.byok_cache_preseeding.print_preseed_results"):
        res = runner.invoke(cli_main.main_cli, ["preseed-cache", "--governance", "--workspace", "w9"])
    assert res.exit_code == 0
    gov.assert_awaited_once_with(workspace_id="w9", verbose=False)


def test_preseed_error_in_results(runner):
    with patch("core.byok_cache_preseeding.preseed_all_caches", AsyncMock(return_value={"error": "boom"})), \
         patch("core.byok_cache_preseeding.print_preseed_results"):
        res = runner.invoke(cli_main.main_cli, ["preseed-cache"])
    assert res.exit_code == 1


def test_preseed_exception(runner):
    with patch("core.byok_cache_preseeding.preseed_all_caches", AsyncMock(side_effect=RuntimeError("down"))):
        res = runner.invoke(cli_main.main_cli, ["preseed-cache"])
    assert res.exit_code == 1
    assert "Pre-seeding failed" in res.output


# ============================================================================
# office commands
# ============================================================================

def test_office_excel_read_cells(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "excel-read", "book.xlsx", "A1:B2"])
    assert res.exit_code == 0
    assert "a\tb" in res.output
    svc.excel.read_range.assert_called_once_with("book.xlsx", "A1:B2")


def test_office_excel_read_value_formula(runner):
    svc = _office_svc()
    svc.excel.read_range.return_value = {"success": True, "value": "42", "formula": "=SUM(A1)"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "excel-read", "book.xlsx"])
    assert res.exit_code == 0
    assert "Value: 42" in res.output
    assert "Formula: =SUM(A1)" in res.output


def test_office_excel_read_error(runner):
    svc = _office_svc()
    svc.excel.read_range.return_value = {"success": False, "error": "no file"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "excel-read", "book.xlsx"])
    assert res.exit_code == 1
    assert "Error: no file" in res.output


def test_office_excel_write(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "excel-write", "b.xlsx", "A1", "7"])
    assert res.exit_code == 0
    assert "written" in res.output
    svc.excel.write_cell.assert_called_once_with("b.xlsx", "A1", "7", False)


def test_office_excel_write_formula_flag(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "excel-write", "b.xlsx", "B2", "=1+1", "--formula"])
    assert res.exit_code == 0
    svc.excel.write_cell.assert_called_once_with("b.xlsx", "B2", "=1+1", True)


def test_office_excel_write_error(runner):
    svc = _office_svc()
    svc.excel.write_cell.return_value = {"success": False, "error": "readonly"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "excel-write", "b.xlsx", "A1", "7"])
    assert res.exit_code == 1
    assert "Error: readonly" in res.output


def test_office_word_read(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "word-read", "doc.docx"])
    assert res.exit_code == 0
    assert "--- paragraphs (1) ---" in res.output
    assert "[Normal] para1" in res.output
    assert "r1c1 | r1c2" in res.output
    svc.word.read_document.assert_called_once_with("doc.docx")


def test_office_word_read_error(runner):
    svc = _office_svc()
    svc.word.read_document.return_value = {"success": False, "error": "bad docx"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "word-read", "doc.docx"])
    assert res.exit_code == 1
    assert "Error: bad docx" in res.output


def test_office_word_write(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "word-write", "doc.docx", "hello", "--style", "Title"])
    assert res.exit_code == 0
    assert "word written" in res.output
    svc.word.modify_document.assert_called_once_with(
        "doc.docx", "append", "hello", {"style": "Title", "target": None}
    )


def test_office_word_write_error(runner):
    svc = _office_svc()
    svc.word.modify_document.return_value = {"success": False, "error": "nope"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "word-write", "doc.docx", "hello"])
    assert res.exit_code == 1


def test_office_pptx_read(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "pptx-read", "deck.pptx"])
    assert res.exit_code == 0
    assert "Slide 1:" in res.output
    assert "[Text Frame] hello" in res.output
    assert "[Table] 1 rows" in res.output
    svc.pptx.read_slides.assert_called_once_with("deck.pptx")


def test_office_pptx_read_error(runner):
    svc = _office_svc()
    svc.pptx.read_slides.return_value = {"success": False, "error": "corrupt"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "pptx-read", "deck.pptx"])
    assert res.exit_code == 1


def test_office_pptx_write(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "pptx-write", "deck.pptx", "content", "--title", "T"])
    assert res.exit_code == 0
    assert "pptx written" in res.output
    svc.pptx.modify_slides.assert_called_once_with(
        "deck.pptx", "add_slide", {"title": "T", "content": "content", "layout_idx": 1}
    )


def test_office_pptx_write_error(runner):
    svc = _office_svc()
    svc.pptx.modify_slides.return_value = {"success": False, "error": "boom"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "pptx-write", "deck.pptx", "content"])
    assert res.exit_code == 1


def test_office_render(runner):
    svc = _office_svc()
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "render", "doc.docx"])
    assert res.exit_code == 0
    assert "<p>doc</p>" in res.output
    svc.renderer.render_to_html.assert_called_once_with("doc.docx")


def test_office_render_error(runner):
    svc = _office_svc()
    svc.renderer.render_to_html.return_value = {"success": False, "error": "render fail"}
    with patch("core.office_service.OfficeService", return_value=svc):
        res = runner.invoke(cli_main.main_cli, ["office", "render", "doc.docx"])
    assert res.exit_code == 1


def test_office_group_no_args_help(runner):
    res = runner.invoke(cli_main.main_cli, ["office"])
    assert res.exit_code == 2
    assert "Usage:" in res.output


def test_main_entry():
    with patch("sys.argv", ["atom-os"]):
        with pytest.raises(SystemExit) as ei:
            runpy.run_path(str(Path(cli_main.__file__)), run_name="__main__")
    assert ei.value.code == 2  # group without subcommand shows help
