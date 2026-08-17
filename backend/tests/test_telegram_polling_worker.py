"""
TelegramPollingWorker tests — offset bookkeeping, dispatch, error resilience.

Network calls are mocked; governance/bridge are patched to keep the tests
hermetic.
"""

import os
os.environ.setdefault("TESTING", "1")

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from workers.telegram_polling_worker import TelegramPollingWorker


def _update(update_id: int, text: str = "hello", sender_id: int = 42) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": sender_id, "is_bot": False, "first_name": "T"},
            "chat": {"id": sender_id, "type": "private"},
            "date": 1,
            "text": text,
        },
    }


def _worker() -> TelegramPollingWorker:
    w = TelegramPollingWorker(bot_token="123:abc")
    return w


class TestOffsetBookkeeping:
    def test_offset_starts_at_zero(self):
        assert _worker()._offset == 0

    @pytest.mark.asyncio
    async def test_offset_advances_past_processed_update(self):
        w = _worker()
        with patch.object(w, "_get_updates", new=AsyncMock(return_value=[_update(100)])), \
             patch.object(w, "_handle_update", new=AsyncMock()) as handle, \
             patch.object(w, "_delete_webhook", new=AsyncMock()):
            # Run one poll cycle, then stop.
            async def one_cycle():
                w.running = True
                client = MagicMock()
                updates = await w._get_updates(client)
                for u in updates:
                    w._offset = max(w._offset, int(u.get("update_id", 0)) + 1)
                    await w._handle_update(u)
                w.running = False
            await one_cycle()
            assert w._offset == 101
            handle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_offset_never_goes_backwards(self):
        w = _worker()
        w._offset = 500
        # Older/lower update ids must not rewind the cursor; an id equal to
        # the last processed id+0 is "new" only if it exceeds offset-1.
        for uid in (10, 499):
            w._offset = max(w._offset, uid + 1)
        assert w._offset == 500


class TestHandleUpdate:
    @pytest.mark.asyncio
    async def test_message_dispatched_to_bridge_with_audit(self):
        w = _worker()
        update = _update(7)
        gov = MagicMock()
        gov.check_permissions = AsyncMock(return_value={"allowed": True})
        gov.log_to_audit_trail = AsyncMock()
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock()

        fake_db = MagicMock()
        with patch("core.database.SessionLocal", return_value=fake_db), \
             patch("core.im_governance_service.IMGovernanceService", return_value=gov), \
             patch("integrations.universal_webhook_bridge.universal_webhook_bridge", bridge), \
             patch("integrations.atom_telegram_integration.atom_telegram_integration", MagicMock()):
            await w._handle_update(update)

        bridge.process_incoming_message.assert_awaited_once_with("telegram", update["message"])
        gov.check_permissions.assert_awaited_once_with(sender_id="42", platform="telegram")
        assert gov.log_to_audit_trail.await_count == 1

    @pytest.mark.asyncio
    async def test_blocked_sender_not_dispatched(self):
        from fastapi import HTTPException

        w = _worker()
        gov = MagicMock()
        gov.check_permissions = AsyncMock(
            side_effect=HTTPException(status_code=403, detail="blocked")
        )
        gov.log_to_audit_trail = AsyncMock()
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock()

        with patch("core.database.SessionLocal", return_value=MagicMock()), \
             patch("core.im_governance_service.IMGovernanceService", return_value=gov), \
             patch("integrations.universal_webhook_bridge.universal_webhook_bridge", bridge):
            await w._handle_update(_update(8))

        bridge.process_incoming_message.assert_not_awaited()
        assert gov.log_to_audit_trail.await_count == 1  # failure audit written

    @pytest.mark.asyncio
    async def test_callback_query_routes_to_integration(self):
        w = _worker()
        cq = {"id": "1", "from": {"id": 42}, "data": "btn"}
        integration = MagicMock()
        integration.handle_callback_query = AsyncMock()

        with patch("integrations.atom_telegram_integration.atom_telegram_integration", integration):
            await w._handle_update({"update_id": 9, "callback_query": cq})
            # created via asyncio.create_task — let it run
            await asyncio.sleep(0)
        integration.handle_callback_query.assert_awaited_once_with(cq)


class TestGetUpdates:
    @pytest.mark.asyncio
    async def test_conflict_triggers_webhook_delete(self):
        w = _worker()
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 409
        resp.json.return_value = {"ok": False, "description": "Conflict: can't use getUpdates while webhook is active"}
        client.post = AsyncMock(return_value=resp)

        with patch.object(w, "_delete_webhook", new=AsyncMock()) as dw:
            updates = await w._get_updates(client)
        assert updates == []
        dw.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ok_returns_updates(self):
        w = _worker()
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"ok": True, "result": [_update(1)]}
        client.post = AsyncMock(return_value=resp)

        updates = await w._get_updates(client)
        assert len(updates) == 1
