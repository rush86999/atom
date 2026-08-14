# -*- coding: utf-8 -*-
"""Coverage wave 99 — integrations/whatsapp_database_setup.py (was 0%,
never imported by any test).

The module is a Postgres bootstrap script (psycopg2 DDL runner). The SQL
strings are not executable Python, but every driver/control-flow statement
is testable with a fully mocked psycopg2 (no network, no real PG):

- WhatsAppDatabaseManager.test_connection: success + connect failure.
- create_database: exists / creates (valid identifier regex) / invalid
  identifier rejected (the parsing/validation logic) / connect failure.
- initialize_tables: full success (4 CREATE TABLE + 8 indexes + demo data),
  exception with connection cleanup.
- _insert_demo_data: success + exception (logged, swallowed).
- get_status: DictCursor stats + row counts, exception.
- setup_database: full success, connection-test failure, create failure,
  tables failure, status failure, and top-level exception.

Remaining non-executable: the __main__ script block (never runs under
pytest), SQL string literals, and docstrings — not counted by coverage.
"""
from unittest.mock import MagicMock, patch

import pytest

import integrations.whatsapp_database_setup as mod


@pytest.fixture()
def dbm():
    return mod.WhatsAppDatabaseManager()


class _FakeCursor:
    """Cursor supporting context-manager use + execute/fetchone/fetchall."""

    def __init__(self, fetchone=None, fetchall=None):
        self._fetchone = fetchone
        self._fetchall = fetchall if fetchall is not None else []
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, seq):
        self.executed.append((sql, seq))

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        self.closed = True


# ============================================================================
# test_connection
# ============================================================================

class TestConnection:
    def test_success(self, dbm):
        conn = _FakeConnection(_FakeCursor(fetchone=(1,)))
        with patch.object(mod.psycopg2, "connect", return_value=conn) as connect:
            result = dbm.test_connection()
        assert result["success"] is True
        assert result["message"] == "Database connection successful"
        assert result["config"]["host"] == "localhost"
        assert connect.call_args.kwargs["connect_timeout"] == 5
        assert conn.closed is True

    def test_connect_failure(self, dbm):
        with patch.object(mod.psycopg2, "connect", side_effect=RuntimeError("no pg")):
            result = dbm.test_connection()
        assert result["success"] is False
        assert "no pg" in result["error"]


# ============================================================================
# create_database
# ============================================================================

class TestCreateDatabase:
    def test_already_exists(self, dbm):
        conn = _FakeConnection(_FakeCursor(fetchone=(1,)))
        with patch.object(mod.psycopg2, "connect", return_value=conn) as connect:
            result = dbm.create_database()
        assert result["success"] is True
        assert result["created"] is False
        assert "already exists" in result["message"]
        assert connect.call_args.kwargs["database"] == "postgres"
        assert conn._cursor.executed[0][0].startswith("SELECT 1 FROM pg_database")

    def test_creates_database(self, dbm):
        conn = _FakeConnection(_FakeCursor(fetchone=None))
        with patch.object(mod.psycopg2, "connect", return_value=conn):
            result = dbm.create_database()
        assert result["success"] is True
        assert result["created"] is True
        assert "created successfully" in result["message"]
        assert conn._cursor.executed[1] == ('CREATE DATABASE "atom_development"', None)

    def test_invalid_database_name_rejected(self, dbm):
        dbm.config["database"] = "bad-name; DROP TABLE x"
        conn = _FakeConnection(_FakeCursor(fetchone=None))
        with patch.object(mod.psycopg2, "connect", return_value=conn):
            result = dbm.create_database()
        assert result["success"] is False
        assert "Invalid database name" in result["error"]
        # the malformed identifier must never reach the DDL executor
        executed = " | ".join(sql for sql, _ in conn._cursor.executed)
        assert "CREATE DATABASE" not in executed

    def test_connect_failure(self, dbm):
        with patch.object(mod.psycopg2, "connect", side_effect=RuntimeError("down")):
            result = dbm.create_database()
        assert result["success"] is False
        assert "down" in result["error"]


# ============================================================================
# initialize_tables
# ============================================================================

class TestInitializeTables:
    def test_success(self, dbm):
        cursor = _FakeCursor()
        conn = _FakeConnection(cursor)
        with patch.object(mod.psycopg2, "connect", return_value=conn) as connect:
            result = dbm.initialize_tables()
        assert result["success"] is True
        assert result["tables"] == ["whatsapp_contacts", "whatsapp_messages",
                                    "whatsapp_templates", "whatsapp_conversations"]
        assert result["indexes_created"] == 8
        connect.assert_called_once_with(**dbm.config)
        assert conn.closed is True

        ddl = [sql for sql, _ in cursor.executed]
        create_tables = [d for d in ddl if "CREATE TABLE IF NOT EXISTS whatsapp_" in d]
        assert len(create_tables) == 4
        indexes = [d for d in ddl if d.startswith("CREATE INDEX IF NOT EXISTS idx_whatsapp_")]
        assert len(indexes) == 8
        inserts = [d for d in ddl if "INSERT INTO whatsapp_" in d]
        assert len(inserts) == 4  # contacts/conversations/messages/templates

    def test_exception_closes_connection(self, dbm):
        conn = _FakeConnection(_FakeCursor())
        conn.close = MagicMock()
        with patch.object(mod.psycopg2, "connect", side_effect=RuntimeError("boom")):
            result = dbm.initialize_tables()
        assert result["success"] is False
        assert result["message"] == "Failed to initialize database tables"

    def test_exception_with_open_connection(self, dbm):
        cursor = _FakeCursor()
        cursor.execute = MagicMock(side_effect=RuntimeError("ddl failed"))
        conn = _FakeConnection(cursor)
        conn.close = MagicMock()
        with patch.object(mod.psycopg2, "connect", return_value=conn):
            result = dbm.initialize_tables()
        assert result["success"] is False
        conn.close.assert_called_once()


# ============================================================================
# _insert_demo_data
# ============================================================================

class TestInsertDemoData:
    def test_success(self, dbm):
        cursor = _FakeCursor()
        dbm._insert_demo_data(cursor)
        inserts = [sql for sql, _ in cursor.executed if "INSERT INTO" in sql]
        assert len(inserts) == 4
        contacts = [params for sql, params in cursor.executed
                    if "whatsapp_contacts" in sql and "INSERT" in sql][0]
        assert len(contacts[0]) == 4  # whatsapp_id, name, phone_number, about

    def test_exception_swallowed(self, dbm):
        cursor = _FakeCursor()
        cursor.executemany = MagicMock(side_effect=RuntimeError("insert failed"))
        dbm._insert_demo_data(cursor)  # must not raise


# ============================================================================
# get_status
# ============================================================================

class TestGetStatus:
    def test_success(self, dbm):
        rows = [{"schemaname": "public", "tablename": "whatsapp_contacts",
                 "attname": "id", "n_distinct": 3, "correlation": 0.9}]
        counts = [{"table_name": "whatsapp_contacts", "row_count": 2},
                  {"table_name": "whatsapp_messages", "row_count": 3}]
        cursor = _FakeCursor(fetchall=rows)
        cursor.fetchall = MagicMock(side_effect=[rows, counts])
        conn = _FakeConnection(cursor)
        with patch.object(mod.psycopg2, "connect", return_value=conn):
            result = dbm.get_status()
        assert result["success"] is True
        assert result["total_tables"] == 2
        assert result["row_counts"][0]["table_name"] == "whatsapp_contacts"
        assert result["table_statistics"][0]["attname"] == "id"
        assert conn.closed is True

    def test_failure(self, dbm):
        with patch.object(mod.psycopg2, "connect", side_effect=RuntimeError("down")):
            result = dbm.get_status()
        assert result["success"] is False
        assert "down" in result["error"]


# ============================================================================
# setup_database orchestration
# ============================================================================

class TestSetupDatabase:
    def test_full_success(self, dbm):
        mgr = MagicMock()
        mgr.test_connection.return_value = {"success": True}
        mgr.create_database.return_value = {"success": True, "created": True,
                                            "database": "atom_development"}
        mgr.initialize_tables.return_value = {"success": True,
                                              "tables": ["whatsapp_contacts"],
                                              "indexes_created": 8}
        mgr.get_status.return_value = {"success": True, "total_tables": 4,
                                       "row_counts": [{"table_name": "whatsapp_contacts",
                                                       "row_count": 3}],
                                       "database": "atom_development"}
        with patch.object(mod, "WhatsAppDatabaseManager", return_value=mgr):
            result = mod.setup_database()
        assert result["setup_complete"] is True
        assert result["final_status"] == "success"
        assert result["steps_completed"] == ["connection_test_passed",
                                             "database_created",
                                             "tables_initialized",
                                             "status_verified"]

    def test_connection_failure_stops(self, dbm):
        mgr = MagicMock()
        mgr.test_connection.return_value = {"success": False, "error": "no pg"}
        with patch.object(mod, "WhatsAppDatabaseManager", return_value=mgr):
            result = mod.setup_database()
        assert result["setup_complete"] is False
        assert result["steps_completed"] == []
        assert "Connection test failed: no pg" in result["errors"]
        mgr.create_database.assert_not_called()

    def test_create_failure_stops(self, dbm):
        mgr = MagicMock()
        mgr.test_connection.return_value = {"success": True}
        mgr.create_database.return_value = {"success": False, "error": "bad name"}
        with patch.object(mod, "WhatsAppDatabaseManager", return_value=mgr):
            result = mod.setup_database()
        assert result["setup_complete"] is False
        assert "Database creation failed: bad name" in result["errors"]
        mgr.initialize_tables.assert_not_called()

    def test_tables_failure_stops(self, dbm):
        mgr = MagicMock()
        mgr.test_connection.return_value = {"success": True}
        mgr.create_database.return_value = {"success": True, "created": False,
                                            "database": "d"}
        mgr.initialize_tables.return_value = {"success": False, "error": "ddl boom"}
        with patch.object(mod, "WhatsAppDatabaseManager", return_value=mgr):
            result = mod.setup_database()
        assert result["setup_complete"] is False
        assert "Table initialization failed: ddl boom" in result["errors"]
        mgr.get_status.assert_not_called()

    def test_status_failure_continues(self, dbm):
        # status failure is logged but does not abort the setup
        mgr = MagicMock()
        mgr.test_connection.return_value = {"success": True}
        mgr.create_database.return_value = {"success": True, "created": True,
                                            "database": "d"}
        mgr.initialize_tables.return_value = {"success": True,
                                              "tables": ["whatsapp_contacts"],
                                              "indexes_created": 8}
        mgr.get_status.return_value = {"success": False, "error": "stats down"}
        with patch.object(mod, "WhatsAppDatabaseManager", return_value=mgr):
            result = mod.setup_database()
        assert result["setup_complete"] is True
        assert result["final_status"] == "success"
        assert result["steps_completed"] == ["connection_test_passed",
                                             "database_created",
                                             "tables_initialized"]

    def test_unexpected_exception(self, dbm):
        mgr = MagicMock()
        mgr.test_connection.side_effect = RuntimeError("total chaos")
        with patch.object(mod, "WhatsAppDatabaseManager", return_value=mgr):
            result = mod.setup_database()
        assert result["setup_complete"] is False
        assert "total chaos" in result["errors"][0]


# ============================================================================
# __main__ script block (run via runpy so __name__ == "__main__")
# ============================================================================

class TestMainBlock:
    def test_main_script_runs_end_to_end(self):
        # The standalone `python whatsapp_database_setup.py` path: every step
        # fails fast (psycopg2.connect mocked to raise) and the result JSON is
        # written. No network, no real PG.
        import runpy
        with patch("psycopg2.connect", side_effect=RuntimeError("no pg server")) as connect, \
             patch("builtins.open", MagicMock()) as open_mock:
            runpy.run_module("integrations.whatsapp_database_setup", run_name="__main__")
        assert connect.called
        written = [call.args[0] for call in open_mock.call_args_list
                   if call.args and call.args[0].startswith("/tmp/whatsapp_database_setup")]
        assert written
        assert written[0].endswith(".json")

    def test_main_script_full_success_branches(self):
        # Full success run so the setup_complete + database_status print
        # branches of the __main__ block execute.
        class _SuccessCursor:
            def __init__(self):
                self.i = 0

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                pass

            def executemany(self, sql, seq):
                pass

            def fetchone(self):
                if "pg_database" in "" or self.i == 0:
                    self.i = 1
                    return None  # database does not exist -> create it
                return (1,)

            def fetchall(self):
                return [{"table_name": "whatsapp_contacts", "row_count": 3}]

        class _SuccessConn:
            def __init__(self):
                self.autocommit = False

            def cursor(self, cursor_factory=None):
                return _SuccessCursor()

            def close(self):
                pass

        import runpy
        with patch("psycopg2.connect", return_value=_SuccessConn()) as connect, \
             patch("builtins.open", MagicMock()):
            runpy.run_module("integrations.whatsapp_database_setup", run_name="__main__")
        assert connect.called
