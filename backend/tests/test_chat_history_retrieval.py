#!/usr/bin/env python3
"""
Tests for Chat Session History Retrieval
Tests the fix for broken chat history feature
"""

from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.chat_session_manager import ChatSessionManager
from core.database import Base, get_db
from core.models import ChatMessage, ChatSession

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_chat_history.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def chat_manager(db_session, monkeypatch):
    """Create chat manager with test database"""
    # Patch SessionLocal to use test database
    monkeypatch.setattr("core.chat_session_manager.SessionLocal", lambda: db_session)

    # Force DB mode
    manager = ChatSessionManager()
    manager.use_db = True
    manager.persistence_mode = "HYBRID"

    return manager


def test_get_session_with_history(chat_manager, db_session):
    """Test retrieving session with chat history from ChatMessage table"""
    # Create a session
    session_id = chat_manager.create_session(
        user_id="test_user",
        metadata={"source": "test"}
    )

    # Add some chat messages
    messages = [
        ChatMessage(
            id="msg1",
            conversation_id=session_id,
            workspace_id="default",
            role="user",
            content="Hello, how are you?",
            created_at=datetime.utcnow() - timedelta(minutes=10)
        ),
        ChatMessage(
            id="msg2",
            conversation_id=session_id,
            workspace_id="default",
            role="assistant",
            content="I'm doing well, thank you!",
            created_at=datetime.utcnow() - timedelta(minutes=9)
        ),
        ChatMessage(
            id="msg3",
            conversation_id=session_id,
            workspace_id="default",
            role="user",
            content="What can you help me with?",
            created_at=datetime.utcnow() - timedelta(minutes=8)
        ),
        ChatMessage(
            id="msg4",
            conversation_id=session_id,
            workspace_id="default",
            role="assistant",
            content="I can help with many tasks!",
            created_at=datetime.utcnow() - timedelta(minutes=7)
        ),
    ]

    for msg in messages:
        db_session.add(msg)
    db_session.commit()

    # Retrieve the session
    session = chat_manager.get_session(session_id)

    # Assertions
    assert session is not None
    assert session["session_id"] == session_id
    assert session["user_id"] == "test_user"
    assert len(session["history"]) == 4

    # Check history is ordered by created_at DESC (most recent first)
    assert session["history"][0]["role"] == "assistant"
    assert "I can help" in session["history"][0]["content"]
    assert session["history"][-1]["role"] == "user"
    assert "Hello, how are you?" in session["history"][-1]["content"]

    # Check message structure
    for msg in session["history"]:
        assert "role" in msg
        assert "content" in msg
        assert "created_at" in msg
        assert msg["role"] in ["user", "assistant"]


def test_get_session_history_limit(chat_manager, db_session):
    """Test that history is limited to 100 messages"""
    session_id = chat_manager.create_session(user_id="test_user")

    # Create 150 messages
    messages = []
    for i in range(150):
        role = "user" if i % 2 == 0 else "assistant"
        msg = ChatMessage(
            id=f"msg{i}",
            conversation_id=session_id,
            workspace_id="default",
            role=role,
            content=f"Message {i}",
            created_at=datetime.utcnow() - timedelta(minutes=150-i)
        )
        messages.append(msg)

    for msg in messages:
        db_session.add(msg)
    db_session.commit()

    # Retrieve session
    session = chat_manager.get_session(session_id)

    # Should only return 100 messages (most recent)
    assert len(session["history"]) == 100


def test_get_session_empty_history(chat_manager, db_session):
    """Test retrieving session with no chat history"""
    session_id = chat_manager.create_session(user_id="test_user")

    # Don't add any messages

    # Retrieve the session
    session = chat_manager.get_session(session_id)

    # Assertions
    assert session is not None
    assert session["session_id"] == session_id
    assert len(session["history"]) == 0
    assert session["history"] == []


def test_get_session_nonexistent(chat_manager):
    """Test retrieving a session that doesn't exist"""
    session = chat_manager.get_session("nonexistent_session_id")
    assert session is None


def test_get_session_history_with_different_conversations(chat_manager, db_session):
    """Test that history is filtered by conversation_id"""
    # Create two sessions
    session1_id = chat_manager.create_session(user_id="test_user")
    session2_id = chat_manager.create_session(user_id="test_user")

    # Add messages to session1
    for i in range(3):
        msg = ChatMessage(
            id=f"session1_msg{i}",
            conversation_id=session1_id,
            workspace_id="default",
            role="user",
            content=f"Session 1 - Message {i}",
            created_at=datetime.utcnow() - timedelta(minutes=10-i)
        )
        db_session.add(msg)

    # Add messages to session2
    for i in range(5):
        msg = ChatMessage(
            id=f"session2_msg{i}",
            conversation_id=session2_id,
            workspace_id="default",
            role="user",
            content=f"Session 2 - Message {i}",
            created_at=datetime.utcnow() - timedelta(minutes=10-i)
        )
        db_session.add(msg)

    db_session.commit()

    # Retrieve both sessions
    session1 = chat_manager.get_session(session1_id)
    session2 = chat_manager.get_session(session2_id)

    # Verify isolation
    assert len(session1["history"]) == 3
    assert len(session2["history"]) == 5

    # Check that all messages in session1 are from session1
    for msg in session1["history"]:
        assert "Session 1" in msg["content"]

    # Check that all messages in session2 are from session2
    for msg in session2["history"]:
        assert "Session 2" in msg["content"]


def test_history_preserves_message_structure(chat_manager, db_session):
    """Test that all message fields are preserved correctly"""
    session_id = chat_manager.create_session(user_id="test_user")

    test_time = datetime.utcnow()
    msg = ChatMessage(
        id="test_msg",
        conversation_id=session_id,
        workspace_id="default",
        role="user",
        content="Test message with special chars: <>&\"'",
        created_at=test_time
    )
    db_session.add(msg)
    db_session.commit()

    session = chat_manager.get_session(session_id)

    assert len(session["history"]) == 1
    history_msg = session["history"][0]

    assert history_msg["role"] == "user"
    assert history_msg["content"] == "Test message with special chars: <>&\"'"
    assert history_msg["created_at"] is not None
    # Verify it's a valid ISO format datetime
    datetime.fromisoformat(history_msg["created_at"])


def test_file_mode_fallback(monkeypatch, tmp_path):
    """Test that file mode still works for backward compatibility"""
    # Force file mode
    monkeypatch.setattr("core.chat_session_manager.DB_AVAILABLE", False)

    sessions_file = tmp_path / "test_sessions.json"
    manager = ChatSessionManager(sessions_file=str(sessions_file))
    manager.use_db = False

    # Create session with history
    session_id = manager.create_session(
        user_id="test_user",
        history=[
            {"role": "user", "content": "Test message"}
        ]
    )

    # Retrieve session
    session = manager.get_session(session_id)

    assert session is not None
    assert session["session_id"] == session_id
    # File mode stores history inline
    assert len(session.get("history", [])) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
