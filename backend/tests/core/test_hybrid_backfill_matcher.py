"""Backfill matcher tests (Step 5)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    from core.models import Base, IngestedDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            IngestedDocument(
                id="pg_adapter_1",
                workspace_id="default",
                tenant_id="default",
                file_name="budget.csv",
                file_path="/budget.csv",
                file_type="csv",
                integration_id="google_drive",
                file_size_bytes=1,
                content_preview="Q1 revenue",
                external_id="drive_ext_77",
                ingested_at=datetime.now(timezone.utc),
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            IngestedDocument(
                id="pg_file_1",
                workspace_id="default",
                tenant_id="default",
                file_name="notes.pdf",
                file_path="/notes.pdf",
                file_type="pdf",
                integration_id="onedrive",
                file_size_bytes=1,
                content_preview="meeting notes",
                external_id="file_e2",
                ingested_at=datetime.now(timezone.utc),
                created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
            IngestedDocument(
                id="pg_file_2",
                workspace_id="default",
                tenant_id="default",
                file_name="notes.pdf",
                file_path="/notes2.pdf",
                file_type="pdf",
                integration_id="onedrive",
                file_size_bytes=1,
                content_preview="older copy",
                external_id="file_e3",
                ingested_at=datetime.now(timezone.utc),
                created_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    session.commit()
    yield session
    session.close()


def test_external_id_leg_matches_exactly(db):
    from core.hybrid_search.backfill_matcher import match_pg_row

    pg_id = match_pg_row(db, {"external_id": "drive_ext_77", "file_name": "x"}, "12345.6")
    assert pg_id == "pg_adapter_1"


def test_file_heuristic_leg_matches_by_name_and_integration(db):
    from core.hybrid_search.backfill_matcher import match_pg_row

    pg_id = match_pg_row(db, {"file_name": "notes.pdf", "integration_id": "onedrive"}, "67890.1")
    # Earliest created_at wins on ties → pg_file_2
    assert pg_id == "pg_file_2"


def test_no_match_returns_none(db):
    from core.hybrid_search.backfill_matcher import match_pg_row

    assert match_pg_row(db, {"file_name": "ghost.pdf"}, "1.0") is None
    assert match_pg_row(db, {"external_id": "nope"}, "1.0") is None
    assert match_pg_row(db, {}, "1.0") is None


def test_never_raises_on_garbage(db):
    from core.hybrid_search.backfill_matcher import match_pg_row

    assert match_pg_row(db, {"external_id": None, "file_name": None}, "1.0") is None
