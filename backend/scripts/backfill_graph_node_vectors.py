"""Backfill the LanceDB graph_nodes vector index (P1.5).

Mirrors all existing GraphNode rows for a workspace into the LanceDB
`graph_nodes` table so local_search's vector leg works on every backend
(SQLite included — the pgvector leg only ever ran on Postgres). Idempotent per
node id on the SQL side; the LanceDB mirror appends, so use --rebuild to drop
the table first for a clean re-embed (e.g. after switching the embedding
provider).

Usage (run from the repo root with the backend venv):

    PYTHONPATH=. python backend/scripts/backfill_graph_node_vectors.py [--workspace ID] [--rebuild]
"""

import argparse
import sys

from core.graphrag_engine import GraphRAGEngine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace ID to backfill (default: the engine's own workspace).",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop the graph_nodes table first for a clean re-embed.",
    )
    args = parser.parse_args()

    engine = GraphRAGEngine()
    if args.rebuild:
        try:
            from core.lancedb_handler import get_lancedb_handler

            handler = get_lancedb_handler(args.workspace)
            handler.drop_table("graph_nodes")
            print("Dropped graph_nodes table (rebuild).")
        except Exception as e:  # noqa: BLE001
            print(f"Rebuild drop skipped ({e}); continuing with incremental backfill.")

    result = engine.backfill_node_vectors(workspace_id=args.workspace)
    print(
        f"Backfill complete: {result['embedded']} embedded, "
        f"{result['skipped']} skipped (workspace={result['workspace']})."
    )
    return 0 if result["skipped"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())