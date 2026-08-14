"""
Shared fixtures for the coverage_expansion suites.

These suites exercise real services against the global ``core.database``
engine. Under ``ATOM_MOCK_DATABASE=true`` that engine is a fresh in-memory
SQLite with NO tables, which made every suite that grabs sessions straight
from ``core.database.SessionLocal`` fail with
"sqlite3.OperationalError: no such table: ...".

Provision the schema before each test and clear all rows so every test
starts from a clean slate even when the whole directory runs in a single
process (committed fixture rows used to leak between suites and caused
UNIQUE-constraint cross-file failures under pytest-xdist).
"""

import pytest


@pytest.fixture(autouse=True)
def provision_mock_database():
    """Ensure the shared in-memory mock database has tables and no rows."""
    from core.database import engine, Base

    Base.metadata.create_all(engine)

    # Delete rows in reverse dependency order so FK constraints stay happy.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    yield
