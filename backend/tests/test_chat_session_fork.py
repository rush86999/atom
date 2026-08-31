"""
Fork agent chat session — POST /api/atom-agent/sessions/{id}/fork.

A fork creates a NEW session owned by the same user and copies the source
conversation into it, so the user can take a chat in a different direction
without polluting the original. Pins the contract:
- ownership check (a fork must not leak another user's chat);
- full copy by default, optional up_to_message_id truncation;
- copied metadata is scrubbed of the source session/user identity (the
  LanceDB history filter is a metadata LIKE substring — a stale
  session_id in copied metadata would cross-link the two conversations);
- lineage recorded on the new session; channel/thread bindings NOT
  inherited.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from core.atom_agent_endpoints import fork_session


USER = "user-1"
OTHER = "user-2"


def _msg(mid, role="user", text=None, extra_meta=None):
    meta = {"session_id": "src-session", "user_id": USER, "intent": "chat"}
    meta.update(extra_meta or {})
    return {
        "id": mid,
        "role": role,
        "text": text or f"message {mid}",
        "created_at": "2026-08-30T12:00:00+00:00",
        "metadata": meta,
    }


def _make_manager(session=None):
    manager = MagicMock()
    manager.get_session.return_value = session
    manager.create_session.return_value = "new-session"
    return manager


def _make_history(messages):
    history = MagicMock()
    history.get_session_history.return_value = messages
    history.save_message.return_value = True
    return history


async def _run(session, messages, payload=None):
    user = SimpleNamespace(id=USER)
    manager = _make_manager(session)
    history = _make_history(messages)
    with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=manager), \
         patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=history):
        result = await fork_session(
            session_id="src-session",
            payload=payload,
            current_user=user,
        )
    return result, manager, history


class TestForkSession:
    @pytest.mark.asyncio
    async def test_fork_copies_all_messages(self):
        session = {"session_id": "src-session", "user_id": USER, "title": "Sales Chat"}
        result, manager, history = await _run(session, [_msg("m1"), _msg("m2", "assistant"), _msg("m3")])

        assert result["success"] is True
        assert result["session_id"] == "new-session"
        assert result["forked_from"] == "src-session"
        assert result["messages_copied"] == 3
        assert result["title"] == "Fork: Sales Chat"

        # New session records lineage
        create_kwargs = manager.create_session.call_args.kwargs
        assert create_kwargs["user_id"] == USER
        assert create_kwargs["metadata"]["forked_from"] == "src-session"
        assert create_kwargs["metadata"]["fork_message_count"] == 3
        # Channel/thread bindings are NOT inherited
        assert "channel_id" not in create_kwargs
        assert "thread_id" not in create_kwargs

        # Every message copied into the NEW session
        assert history.save_message.call_count == 3
        for call in history.save_message.call_args_list:
            assert call.kwargs["session_id"] == "new-session"
            assert call.kwargs["user_id"] == USER

        manager.rename_session.assert_called_once_with("new-session", "Fork: Sales Chat")
        manager.update_session_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_copied_metadata_scrubbed_and_marked(self):
        """Source identity must not ride along in copied metadata — the
        history lookup is a metadata LIKE substring, so a stale
        session_id would cross-link fork and original. save_message
        re-stamps the NEW session identity itself; what the endpoint
        passes must be identity-free apart from the fork markers."""
        session = {"session_id": "src-session", "user_id": USER, "title": None}
        _, _, history = await _run(session, [_msg("m1")])

        call = history.save_message.call_args
        meta = call.kwargs["metadata"]
        assert "session_id" not in meta            # scrubbed; re-stamped by save_message
        assert "user_id" not in meta
        assert call.kwargs["session_id"] == "new-session"   # identity via the argument
        assert call.kwargs["user_id"] == USER
        assert meta["forked"] is True
        assert meta["forked_from"] == "src-session"
        assert meta["intent"] == "chat"                 # intent/agent metadata preserved

    @pytest.mark.asyncio
    async def test_fork_up_to_message_id_truncates_inclusive(self):
        session = {"session_id": "src-session", "user_id": USER, "title": "T"}
        result, _, history = await _run(
            session,
            [_msg("m1"), _msg("m2"), _msg("m3"), _msg("m4")],
            payload={"up_to_message_id": "m2"},
        )
        assert result["messages_copied"] == 2
        copied_texts = [c.kwargs["content"] for c in history.save_message.call_args_list]
        assert copied_texts == ["message m1", "message m2"]

    @pytest.mark.asyncio
    async def test_unknown_up_to_message_id_fails(self):
        session = {"session_id": "src-session", "user_id": USER, "title": "T"}
        result, manager, _ = await _run(
            session, [_msg("m1")], payload={"up_to_message_id": "nope"}
        )
        assert result["success"] is False
        assert "not found" in result["error"]
        manager.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_other_users_session_forbidden(self):
        session = {"session_id": "src-session", "user_id": OTHER, "title": "T"}
        with pytest.raises(HTTPException) as exc:
            await _run(session, [_msg("m1")])
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_session_returns_error(self):
        result, manager, _ = await _run(None, [])
        assert result == {"success": False, "error": "Session not found"}
        manager.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_save_failure_reports_true_count(self):
        session = {"session_id": "src-session", "user_id": USER, "title": "T"}
        manager = _make_manager(session)
        history = _make_history([_msg("m1"), _msg("m2"), _msg("m3")])
        history.save_message.side_effect = [True, False, True]
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=history):
            result = await fork_session(
                session_id="src-session", payload=None, current_user=SimpleNamespace(id=USER)
            )
        assert result["success"] is True
        assert result["messages_copied"] == 2
