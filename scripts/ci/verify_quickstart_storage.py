#!/usr/bin/env python3
"""Smoke-test installed storage binaries in an owned temporary store.

No application DB, provider, embedding model, network call or user data is used.
Run with the newly installed quickstart interpreter, before backend boot.
"""
import importlib.metadata
import json
import tempfile


def probe():
    import fastembed  # noqa: F401 — import only; never construct a model
    import lancedb
    import numpy as np
    import pyarrow

    vector = np.array([1.0, 0.0], dtype=np.float32)
    with tempfile.TemporaryDirectory(prefix="atom-quickstart-storage-") as folder:
        db = lancedb.connect(folder)
        table = db.create_table("quickstart_probe", data=[
            {"id": "synthetic-storage-probe", "vector": vector.tolist()}])
        assert table.count_rows() == 1
        rows = table.search(vector).limit(1).to_list()
        assert len(rows) == 1 and rows[0]["id"] == "synthetic-storage-probe"
    return {
        "versions": {name: importlib.metadata.version(name)
                     for name in ("numpy", "pyarrow", "lancedb", "fastembed")},
        "rows_written_and_read": 1,
        "scope": "installed storage binary smoke; synthetic temporary vector store",
        "embedding_model_constructed": False,
        "application_database_accessed": False,
    }


if __name__ == "__main__":
    print(json.dumps(probe(), sort_keys=True))
