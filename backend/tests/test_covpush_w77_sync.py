"""Coverage wave 77 — RED tests for core/sync_service.py.

Real bug (TDD red->green): the SyncState model (core/models.py) is
missing every column that sync_service.py uses — device_id, user_id,
last_sync_at, auto_sync_enabled, total_syncs, successful_syncs,
failed_syncs, last_successful_sync_at, pending_actions_count.
Every _update_sync_state() call raises AttributeError (silently
swallowed) and get_sync_status() returns {"error": ...} — sync state
tracking is completely dead. RED: constructing SyncState with the
service's fields must work, and the service must be able to persist
and read the marketplace_sync singleton.
"""
from datetime import datetime, timezone

from core.models import SyncState


class TestSyncStateModelColumns:
    """REAL BUG: model missing all columns the service relies on."""

    def test_sync_state_accepts_service_fields(self):
        state = SyncState(
            id="marketplace_sync",
            device_id="marketplace_sync",
            user_id="system",
        )
        assert state.device_id == "marketplace_sync"
        assert state.user_id == "system"
        # Counter columns are ints (defaults apply at flush); the service
        # increments defensively with (value or 0) so a fresh row works:
        state.total_syncs = (state.total_syncs or 0) + 1
        assert state.total_syncs == 1

    def test_sync_state_fields_writable(self):
        state = SyncState(device_id="marketplace_sync")
        state.last_sync_at = datetime.now(timezone.utc)
        state.auto_sync_enabled = True
        state.total_syncs = (state.total_syncs or 0) + 1
        state.successful_syncs = (state.successful_syncs or 0) + 1
        state.failed_syncs = (state.failed_syncs or 0) + 1
        state.pending_actions_count = 1
        state.last_successful_sync_at = datetime.now(timezone.utc)
        assert state.total_syncs == 1


import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.sync_service import SyncService, get_sync_status
from core.models import SkillCache, CategoryCache, SyncState, WebSocketState


@pytest.fixture
def fake_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.fixture
def patched_session(fake_db):
    cm = MagicMock()
    cm.__enter__.return_value = fake_db
    with patch("core.sync_service.SessionLocal", return_value=cm):
        yield fake_db


@pytest.fixture
def service():
    saas = MagicMock()
    ws = MagicMock()
    ws.is_connected = False
    return SyncService(saas, ws)


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_start_without_client(self):
        s = SyncService(MagicMock(), ws_client=None)
        assert await s.start_websocket() is False

    @pytest.mark.asyncio
    async def test_start_already_connected(self):
        ws = MagicMock()
        ws.is_connected = True
        s = SyncService(MagicMock(), ws_client=ws)
        assert await s.start_websocket() is True
        ws.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_success_default_handler(self):
        ws = MagicMock()
        ws.is_connected = False
        ws.connect = AsyncMock()
        s = SyncService(MagicMock(), ws_client=ws)
        assert await s.start_websocket() is True
        assert s._websocket_enabled is True
        # default handler passed to connect
        handler = ws.connect.call_args[0][0]
        assert callable(handler)
        assert handler.__self__ is s

    @pytest.mark.asyncio
    async def test_start_connect_failure(self):
        ws = MagicMock()
        ws.is_connected = False
        ws.connect = AsyncMock(side_effect=RuntimeError("no ws"))
        s = SyncService(MagicMock(), ws_client=ws)
        assert await s.start_websocket() is False
        assert s._websocket_enabled is False

    @pytest.mark.asyncio
    async def test_stop_with_client(self):
        ws = MagicMock()
        ws.disconnect = AsyncMock()
        s = SyncService(MagicMock(), ws_client=ws)
        await s.stop_websocket()
        ws.disconnect.assert_awaited_once()
        assert s._websocket_enabled is False

    @pytest.mark.asyncio
    async def test_stop_without_client(self):
        s = SyncService(MagicMock(), ws_client=None)
        await s.stop_websocket()
        assert s._websocket_enabled is False

    def test_websocket_enabled_property(self):
        ws = MagicMock()
        ws.is_connected = True
        s = SyncService(MagicMock(), ws_client=ws)
        s._websocket_enabled = True
        assert s.websocket_enabled is True
        s._websocket_enabled = False
        assert s.websocket_enabled is False

    @pytest.mark.asyncio
    async def test_default_message_handler(self):
        s = SyncService(MagicMock())
        await s._handle_websocket_message("skill_update", {"x": 1})  # smoke, no raise


class TestSyncSkills:
    @pytest.mark.asyncio
    async def test_single_page(self, service, patched_session):
        service.saas_client.fetch_skills = AsyncMock(return_value={
            "skills": [{"skill_id": f"s{i}", "name": f"S{i}"} for i in range(3)]})
        result = await service.sync_skills()
        assert result == {"success": True, "count": 3}

    @pytest.mark.asyncio
    async def test_paginated_full_batches(self, service, patched_session):
        full = [{"skill_id": f"s{i}", "name": f"S{i}"} for i in range(service.MAX_BATCH_SIZE)]
        service.saas_client.fetch_skills = AsyncMock(side_effect=[
            {"skills": full}, {"skills": [{"skill_id": "s-last"}]}])
        result = await service.sync_skills()
        assert result["count"] == service.MAX_BATCH_SIZE + 1
        assert service.saas_client.fetch_skills.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_response(self, service, patched_session):
        service.saas_client.fetch_skills = AsyncMock(return_value={"skills": []})
        result = await service.sync_skills()
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_missing_skills_key(self, service, patched_session):
        service.saas_client.fetch_skills = AsyncMock(return_value={})
        result = await service.sync_skills()
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_error(self, service, patched_session):
        service.saas_client.fetch_skills = AsyncMock(side_effect=RuntimeError("net"))
        result = await service.sync_skills()
        assert result["success"] is False
        assert result["count"] == 0


class TestSyncCategories:
    @pytest.mark.asyncio
    async def test_success(self, service, patched_session):
        service.saas_client.get_categories = AsyncMock(return_value=[
            {"name": "a"}, {"name": "b"}])
        result = await service.sync_categories()
        assert result == {"success": True, "count": 2}

    @pytest.mark.asyncio
    async def test_empty(self, service, patched_session):
        service.saas_client.get_categories = AsyncMock(return_value=[])
        result = await service.sync_categories()
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_error(self, service, patched_session):
        service.saas_client.get_categories = AsyncMock(side_effect=RuntimeError("net"))
        result = await service.sync_categories()
        assert result["success"] is False
        assert result["count"] == 0


class TestCacheSkill:
    @pytest.mark.asyncio
    async def test_missing_skill_id(self, service, patched_session):
        await service.cache_skill({"name": "no id"})  # no raise, no write
        patched_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_skill_cached(self, service, patched_session):
        await service.cache_skill({"skill_id": "s1", "name": "S1"})
        entry = patched_session.add.call_args[0][0]
        assert entry.skill_id == "s1"
        assert entry.expires_at is not None
        patched_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_no_conflict_updates(self, service, patched_session):
        existing = MagicMock()
        existing.skill_data = {"skill_id": "s1", "version": 1}
        patched_session.query.return_value.filter.return_value.first.return_value = existing
        resolver = MagicMock()
        resolver.detect_skill_conflict.return_value = None  # no conflict
        with patch("core.conflict_resolution_service.ConflictResolutionService", return_value=resolver):
            await service.cache_skill({"skill_id": "s1", "name": "S1"})
        assert existing.skill_data == {"skill_id": "s1", "name": "S1"}
        assert existing.expires_at is not None
        assert service._conflicts_detected == 0
        patched_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_conflict_auto_resolved(self, service, patched_session):
        existing = MagicMock()
        existing.skill_data = {"skill_id": "s1", "version": 1}
        patched_session.query.return_value.filter.return_value.first.return_value = existing
        resolver = MagicMock()
        resolver.detect_skill_conflict.return_value = "VERSION_MISMATCH"
        resolver.calculate_severity.return_value = "HIGH"
        resolver.auto_resolve_conflict.return_value = {"skill_id": "s1", "version": 2}
        with patch("core.conflict_resolution_service.ConflictResolutionService", return_value=resolver):
            await service.cache_skill({"skill_id": "s1", "version": 2})
        assert existing.skill_data == {"skill_id": "s1", "version": 2}
        assert service._conflicts_detected == 1
        assert service._conflicts_resolved == 1

    @pytest.mark.asyncio
    async def test_conflict_strategy_manual_logged(self, service, patched_session):
        service.DEFAULT_CONFLICT_STRATEGY = "manual"
        existing = MagicMock()
        existing.skill_data = {"skill_id": "s1", "version": 1}
        patched_session.query.return_value.filter.return_value.first.return_value = existing
        resolver = MagicMock()
        resolver.detect_skill_conflict.return_value = "CONTENT_MISMATCH"
        resolver.calculate_severity.return_value = "CRITICAL"
        with patch("core.conflict_resolution_service.ConflictResolutionService", return_value=resolver):
            await service.cache_skill({"skill_id": "s1", "version": 2})
        resolver.log_conflict.assert_called_once()
        assert service._conflicts_manual == 1
        assert patched_session.commit.call_count == 0  # manual conflicts not cached

    @pytest.mark.asyncio
    async def test_conflict_auto_resolve_returns_none(self, service, patched_session):
        service.DEFAULT_CONFLICT_STRATEGY = "merge"
        existing = MagicMock()
        existing.skill_data = {"skill_id": "s1"}
        patched_session.query.return_value.filter.return_value.first.return_value = existing
        resolver = MagicMock()
        resolver.detect_skill_conflict.return_value = "OTHER"
        resolver.auto_resolve_conflict.return_value = None
        with patch("core.conflict_resolution_service.ConflictResolutionService", return_value=resolver):
            await service.cache_skill({"skill_id": "s1"})
        assert service._conflicts_detected == 1
        assert patched_session.commit.call_count == 0

    @pytest.mark.asyncio
    async def test_operation_error_swallowed(self, service, patched_session):
        patched_session.query.side_effect = RuntimeError("db down")
        await service.cache_skill({"skill_id": "s1"})  # no raise


class TestCacheCategory:
    @pytest.mark.asyncio
    async def test_missing_name(self, service, patched_session):
        await service.cache_category({"description": "x"})
        patched_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_category(self, service, patched_session):
        await service.cache_category({"name": "automation"})
        entry = patched_session.add.call_args[0][0]
        assert entry.category_name == "automation"

    @pytest.mark.asyncio
    async def test_existing_category_updated(self, service, patched_session):
        existing = MagicMock()
        patched_session.query.return_value.filter.return_value.first.return_value = existing
        await service.cache_category({"name": "automation", "count": 5})
        assert existing.category_data == {"name": "automation", "count": 5}
        assert existing.expires_at is not None

    @pytest.mark.asyncio
    async def test_category_by_category_key(self, service, patched_session):
        await service.cache_category({"category": "dev"})
        entry = patched_session.add.call_args[0][0]
        assert entry.category_name == "dev"

    @pytest.mark.asyncio
    async def test_error_swallowed(self, service, patched_session):
        patched_session.query.side_effect = RuntimeError("db down")
        await service.cache_category({"name": "x"})


class TestInvalidateCache:
    @pytest.mark.asyncio
    async def test_counts_invalidated(self, service, patched_session):
        patched_session.query.return_value.filter.return_value.count.side_effect = [2, 3]
        total = await service.invalidate_expired_cache()
        assert total == 5

    @pytest.mark.asyncio
    async def test_zero_invalidated(self, service, patched_session):
        patched_session.query.return_value.filter.return_value.count.side_effect = [0, 0]
        assert await service.invalidate_expired_cache() == 0

    @pytest.mark.asyncio
    async def test_error_returns_zero(self, service, patched_session):
        patched_session.query.side_effect = RuntimeError("db down")
        assert await service.invalidate_expired_cache() == 0


class TestSyncAll:
    @pytest.mark.asyncio
    async def test_already_syncing(self, service):
        service._syncing = True
        result = await service.sync_all()
        assert result["success"] is False
        assert result["error"] == "sync_already_in_progress"

    @pytest.mark.asyncio
    async def test_full_success(self, service, patched_session):
        service.saas_client.fetch_skills = AsyncMock(return_value={
            "skills": [{"skill_id": "s1"}, {"skill_id": "s2"}]})
        service.saas_client.get_categories = AsyncMock(return_value=[{"name": "a"}])
        service.ws_client.connect = AsyncMock()
        result = await service.sync_all(enable_websocket=True)
        assert result["success"] is True
        assert result["skills_synced"] == 2
        assert result["categories_synced"] == 1
        assert result["websocket_enabled"] is True
        assert result["conflicts"]["conflicts_detected"] == 0
        assert service._syncing is False
        service.ws_client.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_websocket_already_enabled_skips_start(self, service, patched_session):
        service._websocket_enabled = True
        service.saas_client.fetch_skills = AsyncMock(return_value={"skills": []})
        service.saas_client.get_categories = AsyncMock(return_value=[])
        result = await service.sync_all(enable_websocket=True)
        assert result["success"] is True
        service.ws_client.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_path(self, service, patched_session):
        # sync_categories swallows its own errors, so mock the method itself
        # to make the failure propagate to sync_all's handler.
        service.sync_categories = AsyncMock(side_effect=RuntimeError("boom"))
        result = await service.sync_all(enable_websocket=False)
        assert result["success"] is False
        assert result["error"] == "sync_failed"
        assert service._syncing is False


class TestUpdateSyncState:
    def test_syncing_increments_total(self, patched_session):
        state = MagicMock()
        state.total_syncs = None
        patched_session.query.return_value.filter.return_value.first.return_value = state
        s = SyncService(MagicMock())
        s._update_sync_state(status="syncing")
        assert state.total_syncs == 1
        assert state.last_sync_at is not None
        assert state.auto_sync_enabled is True

    def test_success_increments_and_resets_pending(self, patched_session):
        state = MagicMock()
        state.successful_syncs = 3
        state.pending_actions_count = 5
        state.total_syncs = 2
        patched_session.query.return_value.filter.return_value.first.return_value = state
        s = SyncService(MagicMock())
        s._conflicts_detected = 2
        s._conflicts_resolved = 1
        s._conflicts_manual = 1
        s._update_sync_state(status="success", skills_synced=4, categories_synced=2)
        assert state.successful_syncs == 4
        assert state.pending_actions_count == 0
        assert state.last_successful_sync_at is not None
        patched_session.commit.assert_called_once()

    def test_error_increments_failed(self, patched_session):
        state = MagicMock()
        state.failed_syncs = None
        patched_session.query.return_value.filter.return_value.first.return_value = state
        s = SyncService(MagicMock())
        s._update_sync_state(status="error", error_message="kaboom")
        assert state.failed_syncs == 1
        assert state.pending_actions_count == 1

    def test_creates_singleton_when_missing(self, patched_session):
        patched_session.query.return_value.filter.return_value.first.return_value = None
        s = SyncService(MagicMock())
        s._update_sync_state(status="error")
        added = patched_session.add.call_args[0][0]
        assert added.id == "marketplace_sync"
        assert added.device_id == "marketplace_sync"
        assert added.user_id == "system"

    def test_db_error_swallowed(self, patched_session):
        patched_session.query.side_effect = RuntimeError("db down")
        s = SyncService(MagicMock())
        s._update_sync_state(status="error")  # no raise


class TestGetSyncStatus:
    def test_no_state(self, patched_session):
        patched_session.query.return_value.filter.return_value.first.return_value = None
        patched_session.query.return_value.first.return_value = None
        patched_session.query.return_value.count.side_effect = [4, 2]
        result = get_sync_status()
        assert result["sync"]["status"] == "idle"
        assert result["cache"]["skills_count"] == 4
        assert result["cache"]["categories_count"] == 2
        assert result["websocket"]["connected"] is False

    def test_with_sync_and_ws_state(self, patched_session):
        sync_state = SyncState(id="marketplace_sync", device_id="marketplace_sync")
        sync_state.last_sync_at = datetime.now(timezone.utc)
        sync_state.last_successful_sync_at = datetime.now(timezone.utc)
        sync_state.pending_actions_count = 1
        sync_state.total_syncs = 2
        sync_state.successful_syncs = 1
        sync_state.failed_syncs = 1
        ws_state = WebSocketState(connected=True)
        ws_state.last_connected_at = datetime.now(timezone.utc)
        ws_state.last_message_at = datetime.now(timezone.utc)
        ws_state.fallback_to_polling = True
        ws_state.reconnect_attempts = 3

        # get_sync_status: sync state query goes through .filter().first(),
        # websocket state through bare .first().
        patched_session.query.return_value.filter.return_value.first.return_value = sync_state
        patched_session.query.return_value.first.return_value = ws_state
        patched_session.query.return_value.count.side_effect = [0, 0]
        result = get_sync_status()
        assert result["sync"]["status"] == "syncing"
        assert result["sync"]["total_syncs"] == 2
        assert result["sync"]["last_sync_at"] is not None
        assert result["websocket"]["connected"] is True
        assert result["websocket"]["fallback_to_polling"] is True
        assert result["websocket"]["reconnect_attempts"] == 3

    def test_with_idle_state(self, patched_session):
        sync_state = SyncState(device_id="marketplace_sync")
        sync_state.pending_actions_count = 0
        patched_session.query.return_value.filter.return_value.first.return_value = sync_state
        patched_session.query.return_value.first.return_value = None
        patched_session.query.return_value.count.side_effect = [0, 0]
        result = get_sync_status()
        assert result["sync"]["status"] == "idle"
        assert result["sync"]["last_sync_at"] is None

    def test_error(self, patched_session):
        patched_session.query.side_effect = RuntimeError("db down")
        result = get_sync_status()
        assert "error" in result


class TestConflictMetrics:
    def test_metrics_and_reset(self, service):
        service._conflicts_detected = 3
        service._conflicts_resolved = 2
        service._conflicts_manual = 1
        m = service.get_conflict_metrics()
        assert m == {"conflicts_detected": 3, "conflicts_resolved": 2, "conflicts_manual": 1}
        service.reset_conflict_metrics()
        assert service.get_conflict_metrics() == {
            "conflicts_detected": 0, "conflicts_resolved": 0, "conflicts_manual": 0}

    def test_is_syncing_property(self, service):
        assert service.is_syncing is False
        service._syncing = True
        assert service.is_syncing is True
