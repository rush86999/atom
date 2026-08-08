# -*- coding: utf-8 -*-
"""Bug-hunt tests (TDD RED->GREEN) for core/conflict_resolution_service.py.

Each test targets a genuinely-new bug (fix absent from HEAD). Tests are
self-contained: they build an in-memory SQLite schema so they don't depend on
the heavyweight PostgreSQL-backed ``db_session`` fixture from the root conftest.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ConflictLog  # noqa: F401  (ensure model registered)
from core.conflict_resolution_service import ConflictResolutionService


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


# ============================================================================
# BUG 1 (HIGH): calculate_severity mis-classifies a one-sided change to a
# critical field (code/command/local_files) as LOW instead of CRITICAL.
#
# The CRITICAL check guards with `if local_val is not None and remote_val
# is not None`, so when a critical field exists on one side but is MISSING on
# the other (e.g. local adds `code`, remote has none) the inequality is
# skipped and severity falls all the way through to "LOW". Adding/removing
# executable code is exactly the case CRITICAL severity exists to flag.
# ============================================================================


class TestCalculateSeverityOneSidedCriticalField:
    """BUG: one-sided critical-field change should be CRITICAL, not LOW."""

    def test_critical_when_local_has_code_remote_missing(self, db):
        """BUG: local has code, remote has no code -> must be CRITICAL."""
        resolver = ConflictResolutionService(db)
        local = {"skill_id": "s1", "code": "def run(): os.system('rm -rf /')"}
        remote = {"skill_id": "s1"}  # no code at all

        severity = resolver.calculate_severity(local, remote, "CONTENT_MISMATCH")

        assert severity == "CRITICAL", (
            "Adding/replacing executable code on a critical field must be CRITICAL, "
            f"got {severity!r}"
        )

    def test_critical_when_remote_has_code_local_missing(self, db):
        """BUG: remote ships code that local lacks -> must be CRITICAL."""
        resolver = ConflictResolutionService(db)
        local = {"skill_id": "s1"}  # no code
        remote = {"skill_id": "s1", "code": "import subprocess; subprocess.call(...)"}

        severity = resolver.calculate_severity(local, remote, "CONTENT_MISMATCH")

        assert severity == "CRITICAL"

    def test_critical_when_command_added_one_sided(self, db):
        """BUG: one-sided change to `command` field must be CRITICAL."""
        resolver = ConflictResolutionService(db)
        local = {"skill_id": "s1", "command": "bash install.sh"}
        remote = {"skill_id": "s1"}

        severity = resolver.calculate_severity(local, remote, "CONTENT_MISMATCH")

        assert severity == "CRITICAL"

    def test_both_none_still_no_critical(self, db):
        """Regression guard: when both critical values are absent, no CRITICAL."""
        resolver = ConflictResolutionService(db)
        local = {"skill_id": "s1", "description": "a"}
        remote = {"skill_id": "s1", "description": "b"}

        severity = resolver.calculate_severity(local, remote, "OTHER")

        # Only description differs -> LOW (critical fields absent on both sides)
        assert severity == "LOW"

    def test_both_present_unequal_still_critical(self, db):
        """Regression guard: existing two-sided code change must stay CRITICAL."""
        resolver = ConflictResolutionService(db)
        local = {"skill_id": "s1", "code": "a()"}
        remote = {"skill_id": "s1", "code": "b()"}

        severity = resolver.calculate_severity(local, remote, "CONTENT_MISMATCH")

        assert severity == "CRITICAL"
