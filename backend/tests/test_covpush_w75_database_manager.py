"""Coverage wave 75 — core/database_manager.py (29% → 95%+).

Closes the async manager surface: URL conversion (sqlite/postgresql/fallback),
initialize (idempotent/success/failure), close, _get_session lazy-init,
execute/fetch_one/fetch_all (success + error), create_user (success/exists/
error), get_user_by_email (row/none/error), create/get_workflow_execution,
plus the deprecated sync get_db_session context manager (commit/rollback/
close combos), get_db_session_for_request, SessionHealthMonitor
(record/percentile/stats) and get_monitored_db_session (success/error).
All DB I/O is mocked — zero real engines.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core import database_manager as dm


@pytest.fixture
def manager():
    cfg = MagicMock()
    cfg.database.url = "sqlite:///./data/test_atom.db"
    with patch.object(dm, "get_config", return_value=cfg):
        m = dm.DatabaseManager()
        return m


def make_session():
    """AsyncMock session whose `async with` yields the configured mock."""
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    return session


class TestInit:
    def test_sqlite_url_conversion(self, manager):
        assert manager.async_db_url == "sqlite+aiosqlite:///./data/test_atom.db"

    def test_postgresql_url_conversion(self):
        cfg = MagicMock()
        cfg.database.url = "postgresql://user:pass@host:5432/db"
        with patch.object(dm, "get_config", return_value=cfg):
            m = dm.DatabaseManager()
        assert m.async_db_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_unknown_url_falls_back(self):
        cfg = MagicMock()
        cfg.database.url = "oracle://x"
        with patch.object(dm, "get_config", return_value=cfg):
            m = dm.DatabaseManager()
        assert m.async_db_url == "sqlite+aiosqlite:///atom_data.db"

    def test_not_initialized_by_default(self, manager):
        assert manager._initialized is False
        assert manager.engine is None

    async def test_initialize_success(self, manager):
        mock_engine = AsyncMock()
        begin_cm = AsyncMock()
        begin_cm.run_sync = AsyncMock()
        mock_engine.begin = MagicMock(return_value=begin_cm)
        with patch.object(dm, "create_async_engine", return_value=mock_engine) as ce, \
             patch.object(dm, "async_sessionmaker", return_value="session-maker") as sm:
            await manager.initialize()
        assert manager._initialized is True
        assert manager.async_session_maker == "session-maker"
        ce.assert_called_once()
        sm.assert_called_once()

    async def test_initialize_idempotent(self, manager):
        manager._initialized = True
        manager.engine = "already"
        with patch.object(dm, "create_async_engine") as ce:
            await manager.initialize()
        ce.assert_not_called()

    async def test_initialize_failure_raises(self, manager):
        with patch.object(dm, "create_async_engine",
                          side_effect=RuntimeError("conn refused")):
            with pytest.raises(RuntimeError):
                await manager.initialize()
        assert manager._initialized is False

    async def test_close(self, manager):
        mock_engine = AsyncMock()
        manager.engine = mock_engine
        manager.async_session_maker = "sm"
        manager._initialized = True
        await manager.close()
        mock_engine.dispose.assert_awaited_once()
        assert manager.engine is None
        assert manager._initialized is False

    async def test_close_when_no_engine(self, manager):
        await manager.close()  # must not raise

    async def test_get_session_lazy_initializes(self, manager):
        with patch.object(manager, "initialize", new=AsyncMock()) as init:
            manager.async_session_maker = MagicMock(return_value="sess")
            sess = await manager._get_session()
        init.assert_awaited_once()
        assert sess == "sess"

    async def test_get_session_already_initialized(self, manager):
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value="sess")
        with patch.object(manager, "initialize", new=AsyncMock()) as init:
            sess = await manager._get_session()
        init.assert_not_called()
        assert sess == "sess"


class TestRawSql:
    async def test_execute_success(self, manager):
        session = make_session()
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        result = await manager.execute("INSERT INTO t (a) VALUES (:a)", ("x",))
        assert result is session.execute.return_value
        session.commit.assert_awaited_once()

    async def test_execute_error_rolls_back(self, manager):
        session = make_session()
        session.execute.side_effect = RuntimeError("bad sql")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            await manager.execute("SELECT bad", ())
        session.rollback.assert_awaited_once()

    async def test_fetch_one_row(self, manager):
        session = make_session()
        row = MagicMock()
        row._mapping = {"id": "1", "email": "a@b.c"}
        result = MagicMock()
        result.fetchone.return_value = row
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        out = await manager.fetch_one("SELECT * FROM users WHERE id=:id", ("1",))
        assert out == {"id": "1", "email": "a@b.c"}

    async def test_fetch_one_none(self, manager):
        session = make_session()
        result = MagicMock()
        result.fetchone.return_value = None
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        assert await manager.fetch_one("SELECT 1", ()) is None

    async def test_fetch_one_error(self, manager):
        session = make_session()
        session.execute.side_effect = RuntimeError("boom")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            await manager.fetch_one("SELECT 1", ())

    async def test_fetch_all(self, manager):
        session = make_session()
        r1, r2 = MagicMock(), MagicMock()
        r1._mapping = {"id": "1"}
        r2._mapping = {"id": "2"}
        result = MagicMock()
        result.fetchall.return_value = [r1, r2]
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        out = await manager.fetch_all("SELECT id FROM t", ())
        assert out == [{"id": "1"}, {"id": "2"}]

    async def test_fetch_all_error(self, manager):
        session = make_session()
        session.execute.side_effect = RuntimeError("boom")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            await manager.fetch_all("SELECT id FROM t", ())


class TestUserOperations:
    async def test_create_user_success(self, manager):
        session = make_session()
        result = MagicMock()
        result.fetchone.return_value = None
        session.execute.return_value = result
        session.add = MagicMock()
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        out = await manager.create_user("a@b.c", name="Alice")
        assert out["email"] == "a@b.c"
        assert out["name"] == "Alice"
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()

    async def test_create_user_already_exists(self, manager):
        session = make_session()
        result = MagicMock()
        result.fetchone.return_value = MagicMock()
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(ValueError, match="already exists"):
            await manager.create_user("a@b.c")
        session.rollback.assert_awaited_once()

    async def test_create_user_error(self, manager):
        session = make_session()
        session.execute.side_effect = RuntimeError("boom")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            await manager.create_user("a@b.c")
        session.rollback.assert_awaited_once()

    async def test_get_user_by_email_found(self, manager):
        session = make_session()
        row = MagicMock()
        row._mapping = {"id": "u1", "email": "a@b.c", "first_name": "A",
                        "last_name": "B", "role": "member", "status": "active"}
        result = MagicMock()
        result.fetchone.return_value = row
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        out = await manager.get_user_by_email("a@b.c")
        assert out["name"] == "A B"
        assert out["role"] == "member"

    async def test_get_user_by_email_not_found(self, manager):
        session = make_session()
        result = MagicMock()
        result.fetchone.return_value = None
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        assert await manager.get_user_by_email("nobody@x") is None

    async def test_get_user_by_email_error(self, manager):
        session = make_session()
        session.execute.side_effect = RuntimeError("boom")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            await manager.get_user_by_email("a@b.c")


class TestWorkflowExecution:
    async def test_create_workflow_execution(self, manager):
        session = make_session()
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with patch.object(dm, "WorkflowExecution") as WFE:
            WFE.return_value = "exec"
            out = await manager.create_workflow_execution(name="w1")
        assert out == "exec"
        session.add.assert_called_once_with("exec")
        session.commit.assert_awaited_once()

    async def test_create_workflow_execution_error(self, manager):
        session = make_session()
        session.commit.side_effect = RuntimeError("boom")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with patch.object(dm, "WorkflowExecution"):
            with pytest.raises(RuntimeError):
                await manager.create_workflow_execution(name="w1")
        session.rollback.assert_awaited_once()

    async def test_get_workflow_execution_found(self, manager):
        session = make_session()
        row = MagicMock()
        row._mapping = {"execution_id": "e1", "name": "w1"}
        result = MagicMock()
        result.fetchone.return_value = row
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with patch.object(dm, "WorkflowExecution") as WFE:
            WFE.return_value = "wfe"
            out = await manager.get_workflow_execution("e1")
        assert out == "wfe"

    async def test_get_workflow_execution_not_found(self, manager):
        session = make_session()
        result = MagicMock()
        result.fetchone.return_value = None
        session.execute.return_value = result
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        assert await manager.get_workflow_execution("e1") is None

    async def test_get_workflow_execution_error(self, manager):
        session = make_session()
        session.execute.side_effect = RuntimeError("boom")
        manager._initialized = True
        manager.async_session_maker = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            await manager.get_workflow_execution("e1")


class TestSyncSessionContext:
    def test_commit_on_success(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with dm.get_db_session(commit=True) as db:
                db.query.return_value.all.return_value = [1]
        sess.commit.assert_called_once()
        sess.close.assert_called_once()

    def test_no_commit_by_default(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with dm.get_db_session() as db:
                pass
        sess.commit.assert_not_called()
        sess.close.assert_called_once()

    def test_rollback_on_error(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with pytest.raises(RuntimeError):
                with dm.get_db_session(rollback_on_error=True) as db:
                    raise RuntimeError("boom")
        sess.rollback.assert_called_once()

    def test_no_rollback_when_disabled(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with pytest.raises(RuntimeError):
                with dm.get_db_session(rollback_on_error=False) as db:
                    raise RuntimeError("boom")
        sess.rollback.assert_not_called()

    def test_close_disabled_keeps_session(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with dm.get_db_session(close=False) as db:
                pass
        sess.close.assert_not_called()

    def test_deprecation_warning(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with pytest.warns(DeprecationWarning):
                with dm.get_db_session() as db:
                    pass

    def test_request_session_yields_and_closes(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess):
            with pytest.warns(DeprecationWarning):
                gen = dm.get_db_session_for_request()
                db = next(gen)
            assert db is sess
            with pytest.raises(StopIteration):
                next(gen)
        sess.close.assert_called()


class TestSessionHealthMonitor:
    def test_record_and_stats(self):
        m = dm.SessionHealthMonitor(max_samples=100)
        m.record_session_creation(0.05)
        m.record_session_creation(0.15)
        m.record_query(0.01)
        m.record_query(0.03)
        m.record_error()
        stats = m.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["error_count"] == 1
        assert stats["error_rate"] == 0.5
        assert stats["avg_creation_time"] == 0.1
        assert stats["avg_query_time"] == 0.02
        assert stats["p95_creation_time"] == 0.15
        assert stats["p99_creation_time"] == 0.15

    def test_empty_stats(self):
        m = dm.SessionHealthMonitor()
        stats = m.get_stats()
        assert stats["total_sessions"] == 0
        assert stats["error_rate"] == 0.0
        assert stats["avg_creation_time"] == 0.0
        assert stats["p95_creation_time"] == 0.0

    def test_percentile_odd_index(self):
        m = dm.SessionHealthMonitor()
        m.record_session_creation(0.01)
        m.record_session_creation(0.02)
        m.record_session_creation(0.03)
        m.record_session_creation(0.04)
        assert m._percentile(m.creation_times, 95) == 0.04


class TestMonitoredSession:
    def test_success_records_creation(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess), \
             patch.object(dm, "session_health_monitor") as shm:
            with pytest.warns(DeprecationWarning):
                with dm.get_monitored_db_session(commit=True) as db:
                    db.query.return_value.all.return_value = [1]
        shm.record_session_creation.assert_called_once()
        shm.record_error.assert_not_called()
        sess.commit.assert_called_once()

    def test_error_records_error(self):
        sess = MagicMock()
        with patch.object(dm, "SessionLocal", return_value=sess), \
             patch.object(dm, "session_health_monitor") as shm:
            with pytest.warns(DeprecationWarning):
                with pytest.raises(RuntimeError):
                    with dm.get_monitored_db_session() as db:
                        raise RuntimeError("boom")
        shm.record_error.assert_called_once()
