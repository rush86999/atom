"""Cross-process mutation lock used by LanceDB writers and the re-embed swap.

The two-process probe that found the lost-write bug is reproduced by
``test_cross_process_lock_blocks_and_releases`` (raw lock) and
``test_handler_writes_block_behind_another_process`` (the production write
path).  Both use a real second OS process: an in-process RLock cannot tell
another process anything, so a thread-only test would pass on the old code.

``TestLocalLockFailureFailsClosed`` covers the other half of the contract: if
a LOCAL store's advisory lock cannot be acquired, the mutation must fail
before touching the dataset (a second process really holds the lock there; the
acquisition error itself is injected so the test is deterministic).
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[1]

_CHILD = r"""
import json, os, sys, time
from core.lance_write_lock import process_table_write_lock
store = os.environ["LOCK_TEST_STORE"]
with process_table_write_lock(store, os.environ["LOCK_TEST_TABLE"]) as held:
    json.dump({"held": held}, open(os.environ["LOCK_TEST_READY"] + ".tmp", "w"))
    os.replace(os.environ["LOCK_TEST_READY"] + ".tmp", os.environ["LOCK_TEST_READY"])
    deadline = time.time() + 60
    while time.time() < deadline:
        if os.path.exists(os.environ["LOCK_TEST_RELEASE"]):
            break
        time.sleep(0.02)
"""


def _spawn_lock_holder(tmp_path, store, table="lock_probe"):
    ready = tmp_path / "ready.json"
    release = tmp_path / "release"
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": str(BACKEND),
        "LOCK_TEST_STORE": str(store),
        "LOCK_TEST_TABLE": table,
        "LOCK_TEST_READY": str(ready),
        "LOCK_TEST_RELEASE": str(release),
    })
    proc = subprocess.Popen(
        [sys.executable, "-c", _CHILD], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    deadline = time.time() + 60
    while time.time() < deadline:
        if ready.exists():
            assert json.load(open(ready))["held"] is True
            return proc, release
        if proc.poll() is not None:
            out = proc.communicate()[0]
            pytest.fail(f"lock holder exited early: {out}")
        time.sleep(0.02)
    proc.kill()
    pytest.fail("lock holder never acquired the lock")


def _stop_holder(proc, release):
    release.write_text("go")
    try:
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()


def _assert_blocks_then_completes(run, timeout_s=25):
    """Run ``run`` in a thread and prove it stays blocked >= 1s."""
    done = threading.Event()
    error = []

    def target():
        try:
            run()
        except Exception as exc:  # noqa: BLE001 - surfaced below
            error.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    assert not done.wait(timeout=1.0), "operation did not wait for the other process's lock"
    return done, thread, error


class TestLockPrimitives:
    def test_local_and_remote_store_detection(self):
        from core.lance_write_lock import is_local_store

        assert is_local_store("/tmp/x")
        assert not is_local_store("s3://bucket/x")
        assert not is_local_store("db://catalog/x")
        assert not is_local_store("gs://bucket/x")

    def test_lock_path_is_stable_and_table_specific(self, tmp_path):
        from core.lance_write_lock import lock_file_path

        store = tmp_path / "lance"
        a = lock_file_path(str(store), "documents")
        b = lock_file_path(str(store), "episodes")
        assert a != b
        assert a == lock_file_path(str(store), "documents")
        # Sibling of the store, never inside the dataset directory.
        assert not a.startswith(str(store).rstrip(os.sep) + os.sep)
        assert os.path.dirname(a) != str(store)

    def test_cross_process_lock_blocks_and_releases(self, tmp_path):
        from core.lance_write_lock import process_table_write_lock

        store = tmp_path / "lance"
        store.mkdir(parents=True, exist_ok=True)
        proc, release = _spawn_lock_holder(tmp_path, store)
        acquired = threading.Event()

        def take_lock():
            with process_table_write_lock(str(store), "lock_probe") as held:
                assert held is True
                acquired.set()

        done, thread, error = _assert_blocks_then_completes(take_lock)
        assert not acquired.is_set()
        _stop_holder(proc, release)
        done.wait(timeout=30)
        thread.join(timeout=30)
        assert acquired.is_set()
        assert not error


@pytest.fixture
def handler(tmp_path, monkeypatch):
    from core import embedding_registry
    from core.lancedb_handler import LanceDBHandler

    monkeypatch.setenv("LANCEDB_URI", str(tmp_path / "lance"))
    monkeypatch.setenv("EMBEDDING_REGISTRY_FILE", str(tmp_path / "registry.json"))
    embedding_registry.reload()
    h = LanceDBHandler()
    monkeypatch.setattr(
        h, "_active_embedding_identity", lambda: {"provider": "test", "model": "m1"}
    )
    monkeypatch.setattr(h, "embed_text", lambda text: np.array([0.5] * 384))
    monkeypatch.setattr(h, "_schedule_reembed", lambda table_name: None)
    h.create_table("docs_t")
    yield h
    embedding_registry.reload()


class TestHandlerWritesUseTheProcessLock:
    def _row(self):
        return {
            "id": "seed", "user_id": "u", "workspace_id": "default",
            "text": "hello", "source": "s", "metadata": "{}",
            "created_at": "now", "vector": [0.0] * 384,
        }

    def test_handler_writes_block_behind_another_process(self, handler, tmp_path):
        handler.get_table_nocheck("docs_t").add([self._row()])
        proc, release = _spawn_lock_holder(tmp_path, Path(handler.db_path), "docs_t")
        results = []

        def write():
            results.append(handler.add_document("docs_t", "late", doc_id="late"))

        done, thread, error = _assert_blocks_then_completes(write)
        _stop_holder(proc, release)
        done.wait(timeout=30)
        thread.join(timeout=30)
        assert not error
        assert results == [True]
        ids = {r["id"] for r in handler.get_table_nocheck("docs_t").to_arrow().to_pylist()}
        assert ids == {"seed", "late"}

    def test_handler_delete_blocks_behind_another_process(self, handler, tmp_path):
        handler.get_table_nocheck("docs_t").add([self._row()])
        proc, release = _spawn_lock_holder(tmp_path, Path(handler.db_path), "docs_t")
        results = []

        def delete():
            results.append(handler.delete_documents_by_id("docs_t", "seed"))

        done, thread, error = _assert_blocks_then_completes(delete)
        _stop_holder(proc, release)
        done.wait(timeout=30)
        thread.join(timeout=30)
        assert not error
        assert results == [True]
        assert handler.get_table_nocheck("docs_t").count_rows() == 0


class TestLocalLockFailureFailsClosed:
    """A local store whose lock cannot be acquired must not mutate anything.

    ``_acquire`` is monkeypatched to raise while a REAL second OS process holds
    the lock file, so the failure represents genuine contention on a held lock
    rather than a path that could accidentally succeed.  The read at the end
    uses a fresh connection, never the writer's handle.
    """

    def _row(self):
        return {
            "id": "seed", "user_id": "u", "workspace_id": "default",
            "text": "hello", "source": "s", "metadata": "{}",
            "created_at": "now", "vector": [0.0] * 384,
        }

    @staticmethod
    def _boom(fd):
        raise OSError("injected lock acquisition failure")

    def test_acquisition_error_with_other_process_holding_lock(
        self, handler, tmp_path, monkeypatch
    ):
        import core.lance_write_lock as lock_mod

        handler.get_table_nocheck("docs_t").add([self._row()])
        proc, release = _spawn_lock_holder(tmp_path, Path(handler.db_path), "docs_t")
        monkeypatch.setattr(lock_mod, "_acquire", self._boom)
        results = {}

        def write():
            # Nested create path is not taken (table exists), but both
            # mutation APIs must report failure, not block or commit.
            results["insert"] = handler.add_document(
                "docs_t", "must not land", doc_id="blocked-insert"
            )
            results["delete"] = handler.delete_documents_by_id("docs_t", "seed")

        thread = threading.Thread(target=write, daemon=True)
        try:
            thread.start()
            thread.join(timeout=15)
            assert not thread.is_alive(), (
                "writer blocked instead of failing closed"
            )
        finally:
            _stop_holder(proc, release)
        thread.join(timeout=30)

        assert results == {"insert": False, "delete": False}

        import lancedb

        fresh = lancedb.connect(handler.db_path).open_table("docs_t")
        rows = fresh.to_arrow().to_pylist()
        assert [r["id"] for r in rows] == ["seed"]
        assert fresh.count_rows() == 1

    def test_nested_create_path_is_fail_closed(self, handler, monkeypatch):
        """The guarded outer call fails before its nested create can run."""
        import core.lance_write_lock as lock_mod

        monkeypatch.setattr(lock_mod, "_acquire", self._boom)
        assert handler.add_document("nested_new", "x", doc_id="nested") is False
        assert "nested_new" not in handler.db.table_names()

    def test_nested_guard_reuses_one_acquisition(self, handler, monkeypatch):
        """A guarded call nested inside another must not take a second lock."""
        import core.lance_write_lock as lock_mod

        calls = []
        real = lock_mod._acquire

        def counting(fd):
            calls.append(fd)
            return real(fd)

        monkeypatch.setattr(lock_mod, "_acquire", counting)
        # New table -> create_table is entered from inside add_document's guard.
        assert handler.add_document("nested_ok", "x", doc_id="n1") is True
        assert len(calls) == 1
        assert handler.get_table_nocheck("nested_ok").count_rows() == 1

    def test_mutation_guard_refuses_before_raw_write(self, handler, monkeypatch):
        """bytewax-style raw table writes get the same fail-closed guard."""
        import core.lance_write_lock as lock_mod
        from core.lance_write_lock import WriteLockUnavailable

        monkeypatch.setattr(lock_mod, "_acquire", self._boom)
        wrote = False
        with pytest.raises(WriteLockUnavailable):
            with handler.mutation_guard("docs_t"):
                handler.get_table_nocheck("docs_t").add([self._row()])
                wrote = True
        assert wrote is False
        assert handler.get_table_nocheck("docs_t").count_rows() == 0

    def test_remote_ordinary_write_proceeds_without_a_lock(self, handler, monkeypatch):
        """No lock exists on an object store: inserts stay best-effort."""
        handler.get_table_nocheck("docs_t").add([self._row()])
        monkeypatch.setattr(handler, "db_path", "s3://bucket/fake-store")
        assert handler.add_document("docs_t", "remote", doc_id="remote") is True
        ids = {
            r["id"]
            for r in handler.get_table_nocheck("docs_t").to_arrow().to_pylist()
        }
        assert ids == {"seed", "remote"}

    def test_remote_overwrite_refuses_without_shared_protocol(
        self, handler, monkeypatch
    ):
        """The whole-table swap must not run on a non-lockable store."""
        from core import embedding_registry

        handler.get_table_nocheck("docs_t").add([self._row()])
        before = handler.get_table_nocheck("docs_t")
        before_version = int(before.version)
        embedding_registry.set_identity("docs_t", "old", "m0", 384)
        monkeypatch.setattr(handler, "db_path", "s3://bucket/fake-store")

        handler._reembed_table_worker("docs_t")

        after = handler.get_table_nocheck("docs_t")
        assert int(after.version) == before_version
        assert [r["id"] for r in after.to_arrow().to_pylist()] == ["seed"]
        assert embedding_registry.get("docs_t") == {
            "provider": "old", "model": "m0", "dim": 384,
        }


class TestRawHandleMaintenanceTakesTheLock:
    def test_version_cleanup_fails_closed_when_lock_unavailable(
        self, tmp_path, monkeypatch
    ):
        """db_safety mutates through a raw handle; it must not bypass the lock."""
        import lancedb

        import core.lance_write_lock as lock_mod

        store = tmp_path / "store"
        store.mkdir()
        lancedb.connect(str(store)).create_table("docs", data=[{"id": "1"}])

        monkeypatch.delenv("TESTING", raising=False)

        def _boom(fd):
            raise OSError("injected lock failure")

        monkeypatch.setattr(lock_mod, "_acquire", _boom)

        from core.db_safety import lance_version_cleanup_step

        out = lance_version_cleanup_step(retention_hours=0, root=str(tmp_path))
        assert out["tables"] == 1
        assert out["cleaned"] == 0
        assert out["errors"] == 1
