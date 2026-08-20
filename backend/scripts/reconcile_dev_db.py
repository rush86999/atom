"""
Dev-DB reconcile (hybrid-DB drift, R71-style guarded DDL).

The alembic revision chain is broken (KeyError on '0e360bb1a3d3...'), so
pending guarded migrations never run against the dev SQLite stores. This
applies the SAME idempotent, guarded operations the migration declares, to
whichever DATABASE_URL the .env resolves to. Safe to re-run.
"""

import sys

from sqlalchemy import Column, String, inspect, text
from sqlalchemy.engine import create_engine

from core.database import get_database_url


def _table_exists(insp: inspect, name: str) -> bool:
    return name in insp.get_table_names()


def _column_exists(insp: inspect, table: str, column: str) -> bool:
    if not _table_exists(insp, table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def main() -> int:
    url = get_database_url()
    print(f"Reconciling: {url}")
    engine = create_engine(url)
    insp = inspect(engine)

    changed = []

    # 20260816_org_ingestion_sharing -> graph_nodes.sensitivity
    if _table_exists(insp, "graph_nodes") and not _column_exists(
        insp, "graph_nodes", "sensitivity"
    ):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE graph_nodes ADD COLUMN sensitivity VARCHAR(20) "
                    "DEFAULT 'internal'"
                )
            )
        changed.append("graph_nodes.sensitivity")

    # P2.2 bi-temporal graph edges (valid_from / invalid_at / invalidation_reason).
    # Shipped via create_all on fresh DBs only; hybrid dev DBs drift.
    if _table_exists(insp, "graph_edges"):
        edge_cols = {
            "valid_from": "ALTER TABLE graph_edges ADD COLUMN valid_from DATETIME",
            "invalid_at": "ALTER TABLE graph_edges ADD COLUMN invalid_at DATETIME",
            "invalidation_reason": (
                "ALTER TABLE graph_edges ADD COLUMN invalidation_reason TEXT"
            ),
        }
        for col, ddl in edge_cols.items():
            if not _column_exists(insp, "graph_edges", col):
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                changed.append(f"graph_edges.{col}")

    engine.dispose()

    if changed:
        print("Applied:", ", ".join(changed))
    else:
        print("No drift detected — dev DB is in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())