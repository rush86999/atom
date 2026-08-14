# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/privsec/audit_logger.py timezone-rotation bug
(TDD RED→GREEN).

BUG FIXED (W103-2): `rotate_audit_logs` compared a NAIVE LOCAL mtime
(`datetime.fromtimestamp(st_mtime)`) against an aware UTC `today`
(`datetime.now(timezone.utc).date()`). In any timezone behind UTC (e.g.
PDT), evening writes were rotated as "yesterday" — same-day audit logs were
gzip-compressed mid-day and the handler recreated, silently losing the
live-file rotation boundary (duplicate-rotation footgun; log timestamps on
the compressed file kept the *local* date label while the UTC date had
already advanced). Same bug class as the W71C `cleanup_old_audit_logs` fix.
Fixed: `datetime.fromtimestamp(mtime, tz=timezone.utc)`.

Regression evidence: `tests/test_covpush_w71c_webhooks2.py::
TestPrivsecAuditLogger::test_rotate_same_day_noop` failed ~21:30 PDT
(UTC date = next day) and passes only in local-morning hours; the
deterministic tests below pin the mtime so they fail at ANY time of day
against the buggy code.

Fully mocked/no-network: temp-dir log file, gzip in-place, no LLM.
"""
import gzip
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from importlib import reload

import pytest


@pytest.fixture()
def audit(tmp_path, monkeypatch):
    """Fresh AuditLogger bound to a per-test temp log file."""
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "logs" / "audit.log"))
    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "30")
    if "core.privsec.audit_logger" in sys.modules:
        mod = reload(sys.modules["core.privsec.audit_logger"])
    else:
        import core.privsec.audit_logger as mod

    for instance in (mod.AuditLogger._instance, mod._audit_logger_instance):
        if instance is not None and hasattr(instance, "_audit_handler"):
            instance._audit_handler.close()
            instance._audit_logger = None
    # Drop stale FileHandlers the reload re-attaches to the shared
    # 'atom.audit' logger (reload + append-mode FileHandler would double-write
    # every entry once the same test re-creates the logger).
    logging.getLogger("atom.audit").handlers.clear()
    yield mod
    instance = mod.AuditLogger._instance
    if instance is not None and hasattr(instance, "_audit_handler"):
        instance._audit_handler.close()


def _set_mtime(path, days_ago):
    """Pin a file's mtime deterministically (days_ago can be fractional)."""
    mtime = time.time() - (days_ago * 86400)
    os.utime(path, (mtime, mtime))


def _read_log_lines(path):
    with open(path) as f:
        return [line for line in f if line.strip()]


class TestRotateAuditLogsDeterministic:
    """Deterministic rotation tests (mtime pinned — pass/fail independent
    of the wall-clock timezone the suite runs in)."""

    def test_same_day_utc_mtime_no_rotation(self, audit):
        """W103-2 regression: log written 'today' (UTC mtime) must NOT
        rotate, even when the local date has not yet caught up."""
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        _set_mtime(logger._log_path, 0)  # now (UTC)
        logger.rotate_audit_logs()
        assert logger._log_path.exists()
        assert not list(logger._log_path.parent.glob("*.log.gz"))

    def test_yesterday_utc_mtime_rotates(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        _set_mtime(logger._log_path, 1.5)
        logger.rotate_audit_logs()

        parent = logger._log_path.parent
        gzs = list(parent.glob("*.log.gz"))
        assert len(gzs) == 1
        with gzip.open(gzs[0], "rt") as f:
            assert "spotify" in f.read()
        # Handler re-created → fresh (empty) audit.log exists
        remaining_logs = list(parent.glob("*.log"))
        assert remaining_logs == [logger._log_path]
        assert _read_log_lines(logger._log_path) == []

    def test_two_day_old_mtime_rotates(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        _set_mtime(logger._log_path, 2)
        logger.rotate_audit_logs()
        assert len(list(logger._log_path.parent.glob("*.log.gz"))) == 1

    def test_missing_log_file_noop(self, audit):
        logger = audit.AuditLogger()
        logger._log_path.unlink()  # simulate never-written log
        logger.rotate_audit_logs()  # must not raise
        assert not list(logger._log_path.parent.glob("*.log.gz"))

    def test_rotated_filename_uses_utc_date(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        pin_date = datetime.now(timezone.utc) - timedelta(days=1)
        _set_mtime(logger._log_path, 1)
        logger.rotate_audit_logs()
        gzs = list(logger._log_path.parent.glob("*.log.gz"))
        assert len(gzs) == 1
        assert pin_date.strftime("%Y-%m-%d") in gzs[0].name

    def test_writes_after_rotation_land_in_fresh_log(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        _set_mtime(logger._log_path, 1)
        logger.rotate_audit_logs()
        logger.log_media_action("u2", None, "b", "sonos", {}, "success")
        lines = _read_log_lines(logger._log_path)
        assert json.loads(lines[-1])["service"] == "sonos"
        assert len(lines) == 1  # previous entry went to the gz


class TestCleanupOldAuditLogsDeterministic:
    def test_removes_old_rotated_logs_keeps_fresh(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        # Fabricate an old rotated log + gz older than the 30-day retention
        old_log = logger._log_path.parent / "audit.2020-01-01.log"
        old_log.write_text("old")
        _set_mtime(old_log, 40)
        old_gz = logger._log_path.parent / "audit.2020-01-01.log.gz"
        old_gz.write_text("old.gz")
        _set_mtime(old_gz, 40)

        logger.cleanup_old_audit_logs()

        assert not old_log.exists()
        assert not old_gz.exists()
        assert logger._log_path.exists()  # current log untouched

    def test_keeps_logs_within_retention(self, audit):
        logger = audit.AuditLogger()
        logger.log_media_action("u1", None, "a", "spotify", {}, "success")
        recent = logger._log_path.parent / "audit.2026-07-01.log"
        recent.write_text("recent")
        _set_mtime(recent, 10)

        logger.cleanup_old_audit_logs()

        assert recent.exists()

    def test_cleanup_unreadable_file_logs_error_not_raise(self, audit, caplog):
        logger = audit.AuditLogger()
        old = logger._log_path.parent / "audit.2019-01-01.log"
        old.write_text("old")
        _set_mtime(old, 100)
        # Stat succeeds but unlink raises → caught by except, logged, no raise
        with caplog.at_level("ERROR", logger="core.privsec.audit_logger"):
            import unittest.mock as mock
            with mock.patch("pathlib.Path.unlink", side_effect=OSError("boom")):
                logger.cleanup_old_audit_logs()
        assert "Failed to remove old audit log" in caplog.text
        assert old.exists()
