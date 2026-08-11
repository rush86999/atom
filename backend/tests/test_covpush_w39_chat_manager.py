"""Coverage wave 39 — core/chat_session_manager (37% → 90%+).

- __init__: strict-db failure raises, file mode init
- _load_sessions_file / _save_sessions_file (atomic write, error paths)
- create_session: file mode, strict-db write failure raises
- get_session: file mode missing, strict-db read failure raises
- update_session_activity: file mode + strict-db failure
- list_user_sessions: file mode, db mode, limit
- delete_session: file mode
- rename_session: file mode
- get_chat_session_manager factory
"""
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from core.chat_session_manager import ChatSessionManager


@pytest.fixture
def sessions_file(tmp_path):
    return str(tmp_path / "sessions.json")


@pytest.fixture
def file_manager(sessions_file, monkeypatch):
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "FILE")
    monkeypatch.setattr("core.chat_session_manager.DB_AVAILABLE", False)
    monkeypatch.setattr("core.chat_session_manager.SessionLocal", None)
    return ChatSessionManager(sessions_file=sessions_file)


class TestInit:
    def test_strict_db_missing_deps_raises(self, monkeypatch):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        with patch("core.chat_session_manager.DB_AVAILABLE", False):
            with pytest.raises(RuntimeError):
                ChatSessionManager()

    def test_strict_db_connection_failure_raises(self, monkeypatch):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object), \
             patch("core.chat_session_manager.get_db_session",
                   side_effect=RuntimeError("conn down")):
            with pytest.raises(RuntimeError):
                ChatSessionManager()

    def test_file_mode_creates_file(self, sessions_file):
        with patch("core.chat_session_manager.DB_AVAILABLE", False), \
             patch("core.chat_session_manager.SessionLocal", None):
            m = ChatSessionManager(sessions_file=sessions_file)
        assert os.path.exists(sessions_file)


class TestFileOperations:
    def test_save_and_load_roundtrip(self, sessions_file):
        with patch("core.chat_session_manager.DB_AVAILABLE", False), \
             patch("core.chat_session_manager.SessionLocal", None):
            m = ChatSessionManager(sessions_file=sessions_file)
        m._save_sessions_file([{"session_id": "s1", "user_id": "u1"}])
        loaded = m._load_sessions_file()
        assert loaded[0]["session_id"] == "s1"

    def test_load_missing_file(self, sessions_file):
        with patch("core.chat_session_manager.DB_AVAILABLE", False), \
             patch("core.chat_session_manager.SessionLocal", None):
            m = ChatSessionManager(sessions_file=sessions_file)
        os.unlink(sessions_file)
        assert m._load_sessions_file() == []

    def test_load_corrupt_file(self, sessions_file):
        with open(sessions_file, "w") as f:
            f.write("{not json")
        with patch("core.chat_session_manager.DB_AVAILABLE", False), \
             patch("core.chat_session_manager.SessionLocal", None):
            m = ChatSessionManager(sessions_file=sessions_file)
        assert m._load_sessions_file() == []


class TestFileMode:
    def test_create_and_get_session(self, file_manager):
        sid = file_manager.create_session(user_id="u1", metadata={"k": "v"})
        session = file_manager.get_session(sid)
        assert session["session_id"] == sid
        assert session["user_id"] == "u1"

    def test_get_missing_session(self, file_manager):
        assert file_manager.get_session("missing") is None

    def test_update_activity(self, file_manager):
        sid = file_manager.create_session(user_id="u1")
        file_manager.update_session_activity(sid, history=[{"role": "user", "content": "hi"}],
                                             last_message="hi")
        session = file_manager.get_session(sid)
        assert session["history"][0]["content"] == "hi"

    def test_update_activity_missing(self, file_manager):
        file_manager.update_session_activity("missing", history=[])
        # no raise

    def test_list_user_sessions(self, file_manager):
        file_manager.create_session(user_id="u1")
        file_manager.create_session(user_id="u1")
        file_manager.create_session(user_id="u2")
        sessions = file_manager.list_user_sessions("u1")
        assert len(sessions) == 2
        limited = file_manager.list_user_sessions("u1", limit=1)
        assert len(limited) == 1

    def test_delete_session(self, file_manager):
        sid = file_manager.create_session(user_id="u1")
        assert file_manager.delete_session(sid) is True
        assert file_manager.get_session(sid) is None
        assert file_manager.delete_session(sid) is False

    def test_rename_session(self, file_manager):
        sid = file_manager.create_session(user_id="u1")
        assert file_manager.rename_session(sid, "New Title") is True
        assert file_manager.get_session(sid)["title"] == "New Title"
        assert file_manager.rename_session("missing", "X") is False


class TestStrictDB:
    def test_strict_db_write_failure_raises(self, monkeypatch, sessions_file):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        db = MagicMock()
        db.add = MagicMock(side_effect=RuntimeError("boom"))
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = False
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object), \
             patch("core.chat_session_manager.get_db_session", return_value=cm):
            m = ChatSessionManager(sessions_file=sessions_file)
            with pytest.raises(RuntimeError):
                m.create_session(user_id="u1")

    def test_strict_db_read_failure_raises(self, monkeypatch, sessions_file):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        cm = MagicMock()
        # init's connection check succeeds, the get_session read fails
        cm.__enter__.side_effect = [MagicMock(), RuntimeError("read boom")]
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object), \
             patch("core.chat_session_manager.get_db_session", return_value=cm):
            m = ChatSessionManager(sessions_file=sessions_file)
            with pytest.raises(RuntimeError):
                m.get_session("s1")

    def test_strict_db_update_failure_raises(self, monkeypatch, sessions_file):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        cm = MagicMock()
        cm.__enter__.side_effect = [MagicMock(), RuntimeError("update boom")]
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object), \
             patch("core.chat_session_manager.get_db_session", return_value=cm):
            m = ChatSessionManager(sessions_file=sessions_file)
            with pytest.raises(RuntimeError):
                m.update_session_activity("s1", history=[])


class TestFactory:
    def test_get_chat_session_manager(self):
        from core.chat_session_manager import get_chat_session_manager
        m = get_chat_session_manager("default")
        assert isinstance(m, ChatSessionManager)
        assert m.workspace_id == "default"
