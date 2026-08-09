"""Coverage push + bug hunt for integrations/workspace_sync_service.py.

Target: >=75% line coverage. TDD: failing test first, then minimal fix.

Bug found (fixed):
- B1: platform handlers (_apply_slack_change / _apply_discord_change /
  _apply_google_chat_change / _apply_teams_change) returned None when a
  matched change type lacked its required data (e.g. MEMBER_ADD without
  email), so propagate_change crashed with
  AttributeError: 'NoneType' object has no attribute 'get' — the sync
  recorded a misleading failure instead of a clean "missing data" error.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, UnifiedWorkspace, WorkspaceSyncLog
from integrations.workspace_sync_service import (
    ChangeType,
    SyncConflictResolution,
    WorkspaceSyncService,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def service(db_session):
    return WorkspaceSyncService(db_session)


def _make_workspace(db_session, **kwargs):
    svc = WorkspaceSyncService(db_session)
    return svc.create_unified_workspace(
        user_id=kwargs.get("user_id", "user-1"),
        name=kwargs.get("name", "WS"),
        slack_workspace_id=kwargs.get("slack_workspace_id"),
        discord_guild_id=kwargs.get("discord_guild_id"),
        google_chat_space_id=kwargs.get("google_chat_space_id"),
        teams_team_id=kwargs.get("teams_team_id"),
    )


class TestCapabilitiesAndHealth:
    def test_get_capabilities_shape(self, service):
        caps = service.get_capabilities()
        assert caps["supports_webhooks"] is False
        op_ids = [op["id"] for op in caps["operations"]]
        assert op_ids == [
            "sync_workspace",
            "list_syncs",
            "get_sync_status",
            "cancel_sync",
            "invalidate_cache",
        ]

    def test_health_check_healthy(self, db_session, service):
        result = service.health_check()
        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["database_connected"] is True

    def test_health_check_db_error(self, db_session):
        svc = WorkspaceSyncService(db_session)
        with patch.object(db_session, "execute", side_effect=RuntimeError("db down")):
            result = svc.health_check()
        assert result["healthy"] is False
        assert result["status"] == "unhealthy"
        assert "db down" not in json.dumps(result)

    def test_health_check_no_db(self):
        svc = WorkspaceSyncService(None)
        result = svc.health_check()
        assert result["healthy"] is False
        assert result["message"] == "Database not configured"


class TestPlatformIdHelpers:
    def test_get_platform_id_known(self, db_session):
        ws = _make_workspace(db_session, slack_workspace_id="T1", teams_team_id="TM1")
        assert WorkspaceSyncService._get_platform_id(ws, "slack") == "T1"
        assert WorkspaceSyncService._get_platform_id(ws, "teams") == "TM1"

    def test_get_platform_id_unknown(self, db_session):
        ws = _make_workspace(db_session)
        assert WorkspaceSyncService._get_platform_id(ws, "telegram") is None

    def test_set_platform_id_known(self, db_session):
        ws = _make_workspace(db_session)
        WorkspaceSyncService._set_platform_id(ws, "discord", "G1")
        assert ws.discord_guild_id == "G1"

    def test_set_platform_id_unknown_raises(self, db_session):
        ws = _make_workspace(db_session)
        with pytest.raises(ValueError, match="Unsupported platform"):
            WorkspaceSyncService._set_platform_id(ws, "telegram", "x")


class TestCreateUnifiedWorkspace:
    def test_create_all_platforms(self, db_session, service):
        ws = service.create_unified_workspace(
            user_id="u1",
            name="All",
            slack_workspace_id="T1",
            discord_guild_id="G1",
            google_chat_space_id="S1",
            teams_team_id="TM1",
        )
        assert ws.id
        assert ws.platform_count == 4
        assert ws.sync_status == "pending"
        assert db_session.query(UnifiedWorkspace).count() == 1
        log = db_session.query(WorkspaceSyncLog).first()
        assert log.operation == "create"
        assert log.status == "success"

    def test_create_no_platforms_default_config(self, db_session, service):
        ws = service.create_unified_workspace(user_id="u1", name="Empty")
        assert ws.platform_count == 0
        assert ws.sync_config["auto_sync"] is True
        assert ws.sync_config["conflict_resolution"] == SyncConflictResolution.LATEST_WINS

    def test_create_custom_sync_config(self, db_session, service):
        ws = service.create_unified_workspace(
            user_id="u1", name="Cfg", sync_config={"auto_sync": False}
        )
        assert ws.sync_config == {"auto_sync": False}

    def test_create_rolls_back_on_error(self, db_session, service):
        with patch(
            "integrations.workspace_sync_service.UnifiedWorkspace",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError):
                service.create_unified_workspace(user_id="u1", name="X")
        assert db_session.query(UnifiedWorkspace).count() == 0


class TestAddPlatform:
    def test_add_platform_success(self, db_session, service):
        ws = _make_workspace(db_session, slack_workspace_id="T1")
        updated = service.add_platform_to_workspace(ws.id, "discord", "G1")
        assert updated.discord_guild_id == "G1"
        assert updated.platform_count == 2
        log = (
            db_session.query(WorkspaceSyncLog)
            .filter_by(operation="update")
            .first()
        )
        assert log.change_type == "platform_add"

    def test_add_platform_not_found(self, db_session, service):
        with pytest.raises(ValueError, match="not found"):
            service.add_platform_to_workspace("nope", "slack", "T1")

    def test_add_platform_unknown_platform_raises(self, db_session, service):
        ws = _make_workspace(db_session)
        with pytest.raises(ValueError, match="Unsupported platform"):
            service.add_platform_to_workspace(ws.id, "telegram", "x")

    def test_add_platform_already_exists_logs_warning(self, db_session, service, caplog):
        ws = _make_workspace(db_session, slack_workspace_id="T1")
        with caplog.at_level("WARNING"):
            updated = service.add_platform_to_workspace(ws.id, "slack", "T1")
        assert updated.slack_workspace_id == "T1"
        assert "already exists" in caplog.text


class TestPropagateChange:
    def test_no_targets(self, db_session, service):
        ws = _make_workspace(db_session, slack_workspace_id="T1")
        result = service.propagate_change(
            ws.id, "slack", ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}
        )
        assert result == {"status": "no_targets", "targets": []}

    def test_workspace_not_found(self, db_session, service):
        with pytest.raises(ValueError, match="not found"):
            service.propagate_change(
                "nope", "slack", ChangeType.WORKSPACE_NAME_CHANGE, {}
            )

    def test_success_all_targets(self, db_session, service):
        ws = _make_workspace(
            db_session,
            slack_workspace_id="T1",
            discord_guild_id="G1",
            google_chat_space_id="S1",
            teams_team_id="TM1",
        )
        result = service.propagate_change(
            ws.id,
            "slack",
            ChangeType.MEMBER_ADD,
            {"email": "a@b.c", "user_id": "u1"},
        )
        assert result["status"] == "success"
        assert set(result["successful_platforms"]) == {"discord", "google_chat", "teams"}
        assert result["failed_platforms"] == []
        assert ws.sync_status == "active"
        assert ws.last_sync_at is not None
        log = (
            db_session.query(WorkspaceSyncLog)
            .filter_by(operation="propagate")
            .first()
        )
        assert log.status == "success"
        assert log.duration_ms is not None

    def test_partial_failure(self, db_session, service):
        ws = _make_workspace(
            db_session, slack_workspace_id="T1", discord_guild_id="G1"
        )
        with patch(
            "integrations.workspace_sync_service.WorkspaceSyncService._apply_discord_change",
            return_value={"success": False, "error": "discord rejected"},
        ):
            result = service.propagate_change(
                ws.id,
                "teams",
                ChangeType.WORKSPACE_NAME_CHANGE,
                {"new_name": "X"},
            )
        assert result["status"] == "partial_failure"
        assert result["successful_platforms"] == ["slack"]
        assert result["failed_platforms"] == ["discord"]

    def test_all_fail(self, db_session, service):
        ws = _make_workspace(
            db_session, slack_workspace_id="T1", discord_guild_id="G1"
        )
        with patch(
            "integrations.workspace_sync_service.WorkspaceSyncService._apply_discord_change",
            side_effect=RuntimeError("discord exploded"),
        ), patch(
            "integrations.workspace_sync_service.WorkspaceSyncService._apply_slack_change",
            side_effect=RuntimeError("slack exploded"),
        ):
            result = service.propagate_change(
                ws.id,
                "teams",
                ChangeType.WORKSPACE_NAME_CHANGE,
                {"new_name": "X"},
            )
        assert result["status"] == "failure"
        assert ws.sync_status == "error"
        log = (
            db_session.query(WorkspaceSyncLog)
            .filter_by(operation="propagate")
            .first()
        )
        assert log.status == "failure"
        assert "2 platforms failed" in log.error_message

    def test_missing_data_returns_clean_failure_not_attributeerror(self, db_session, service):
        """B1 RED: MEMBER_ADD without email must produce a clean failure dict,
        not crash with AttributeError in propagate_change."""
        ws = _make_workspace(
            db_session,
            slack_workspace_id="T1",
            discord_guild_id="G1",
            google_chat_space_id="S1",
            teams_team_id="TM1",
        )
        result = service.propagate_change(
            ws.id, "slack", ChangeType.MEMBER_ADD, {}
        )
        assert result["status"] == "failure"
        assert "NoneType" not in repr(result)
        assert "has no attribute" not in repr(result)
        for platform, res in result["results"].items():
            assert res["success"] is False
            assert res["error"]


class TestGetWorkspaceSyncStatus:
    def test_status_with_logs(self, db_session, service):
        ws = _make_workspace(
            db_session, slack_workspace_id="T1", discord_guild_id="G1"
        )
        service.propagate_change(
            ws.id,
            "teams",
            ChangeType.WORKSPACE_NAME_CHANGE,
            {"new_name": "Y"},
        )
        status = service.get_workspace_sync_status(ws.id)
        assert status["workspace_id"] == ws.id
        assert status["name"] == "WS"
        assert status["platforms"]["slack"] == "T1"
        assert status["recent_syncs"][0]["operation"] == "propagate"

    def test_status_not_found(self, db_session, service):
        with pytest.raises(ValueError, match="not found"):
            service.get_workspace_sync_status("nope")


class TestLogHelpers:
    def test_update_sync_log_duration(self, db_session, service):
        log = WorkspaceSyncLog(
            unified_workspace_id="w1",
            operation="propagate",
            source_platform="slack",
            target_platforms=["discord"],
            change_type="member_add",
            change_data={},
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.flush()
        service._update_sync_log(
            log.id, "success", completed_at=datetime.now(timezone.utc)
        )
        db_session.commit()
        db_session.refresh(log)
        assert log.status == "success"
        assert log.duration_ms is not None

    def test_update_sync_log_naive_started_at(self, db_session, service):
        log = WorkspaceSyncLog(
            unified_workspace_id="w1",
            operation="propagate",
            source_platform="slack",
            target_platforms=[],
            change_type="member_add",
            change_data={},
            status="in_progress",
            started_at=datetime.now(),
        )
        db_session.add(log)
        db_session.flush()
        service._update_sync_log(
            log.id, "success", completed_at=datetime.now(timezone.utc)
        )
        db_session.commit()
        db_session.refresh(log)
        assert log.status == "success"

    def test_update_sync_log_missing_log(self, db_session, service):
        service._update_sync_log("nope", "success")

    def test_update_sync_log_no_completed_at(self, db_session, service):
        log = WorkspaceSyncLog(
            unified_workspace_id="w1",
            operation="propagate",
            source_platform="slack",
            target_platforms=[],
            change_type="member_add",
            change_data={},
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.flush()
        service._update_sync_log(log.id, "failure")
        db_session.commit()
        db_session.refresh(log)
        assert log.status == "failure"
        assert log.duration_ms is None

    def test_get_connected_platforms_exclude(self, db_session, service):
        ws = _make_workspace(
            db_session,
            slack_workspace_id="T1",
            discord_guild_id="G1",
            teams_team_id="TM1",
        )
        assert service._get_connected_platforms(ws) == ["slack", "discord", "teams"]
        assert service._get_connected_platforms(ws, exclude="discord") == [
            "slack",
            "teams",
        ]
        assert service._get_connected_platforms(ws, exclude="teams") == [
            "slack",
            "discord",
        ]

    def test_apply_change_no_platform_id(self, db_session, service):
        ws = _make_workspace(db_session, slack_workspace_id="T1")
        result = service._apply_change_to_platform(
            ws, "discord", ChangeType.MEMBER_ADD, {}, "latest"
        )
        assert result["success"] is False
        assert "No platform ID found" in result["error"]

    def test_apply_change_unknown_platform(self, db_session, service):
        ws = _make_workspace(db_session, slack_workspace_id="T1")
        result = service._apply_change_to_platform(
            ws, "telegram", ChangeType.MEMBER_ADD, {}, "latest"
        )
        assert result["success"] is False


class TestSlackHandler:
    def test_name_change(self, service):
        result = service._apply_slack_change("T1", ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "N"})
        assert result["success"] is True

    def test_member_add_with_email(self, service):
        result = service._apply_slack_change("T1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is True

    def test_member_remove_with_user_id(self, service):
        result = service._apply_slack_change("T1", ChangeType.MEMBER_REMOVE, {"user_id": "u1"})
        assert result["success"] is True

    def test_channel_add(self, service):
        result = service._apply_slack_change("T1", ChangeType.CHANNEL_ADD, {"channel_name": "c1"})
        assert result["success"] is True

    def test_channel_remove(self, service):
        result = service._apply_slack_change("T1", ChangeType.CHANNEL_REMOVE, {"channel_id": "ch1"})
        assert result["success"] is True

    def test_settings_change_unhandled_logged(self, service):
        result = service._apply_slack_change("T1", ChangeType.SETTINGS_CHANGE, {})
        assert result["success"] is True

    def test_missing_data_clean_failure(self, service):
        result = service._apply_slack_change("T1", ChangeType.MEMBER_ADD, {})
        assert result["success"] is False
        assert "Missing" in result["error"]

    def test_import_error(self, service):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "integrations.slack_enhanced_service":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = service._apply_slack_change("T1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False
        assert "unavailable" in result["error"]

    def test_generic_error(self, service):
        with patch(
            "integrations.slack_enhanced_service.SlackEnhancedService",
            side_effect=RuntimeError("slack api down"),
        ):
            result = service._apply_slack_change("T1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False
        assert "slack api down" in result["error"]


class TestDiscordHandler:
    @pytest.mark.parametrize(
        "change_type, data",
        [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "N"}),
            (ChangeType.MEMBER_ADD, {"user_id": "u1"}),
            (ChangeType.MEMBER_REMOVE, {"user_id": "u1"}),
            (ChangeType.CHANNEL_ADD, {"channel_name": "c1"}),
            (ChangeType.CHANNEL_REMOVE, {"channel_id": "ch1"}),
            (ChangeType.SETTINGS_CHANGE, {}),
        ],
    )
    def test_change_types(self, service, change_type, data):
        result = service._apply_discord_change("G1", change_type, data)
        assert result["success"] is True

    def test_missing_data_clean_failure(self, service):
        result = service._apply_discord_change("G1", ChangeType.MEMBER_ADD, {})
        assert result["success"] is False

    def test_service_not_available(self, service):
        import integrations.atom_discord_integration as adi

        with patch.object(adi, "atom_discord_integration", None):
            result = service._apply_discord_change("G1", ChangeType.MEMBER_ADD, {"user_id": "u1"})
        assert result["success"] is False
        assert "not available" in result["error"]

    def test_import_error(self, service):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "integrations.atom_discord_integration":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = service._apply_discord_change("G1", ChangeType.MEMBER_ADD, {"user_id": "u1"})
        assert result["success"] is False
        assert "unavailable" in result["error"]

    def test_generic_error(self, service):
        import integrations.atom_discord_integration as adi

        class _Boom:
            def __bool__(self):
                raise RuntimeError("discord api down")

        with patch.object(adi, "atom_discord_integration", _Boom()):
            result = service._apply_discord_change("G1", ChangeType.MEMBER_ADD, {"user_id": "u1"})
        assert result["success"] is False
        assert "discord api down" in result["error"]


class TestGoogleChatHandler:
    @pytest.mark.parametrize(
        "change_type, data",
        [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "N"}),
            (ChangeType.MEMBER_ADD, {"email": "a@b.c"}),
            (ChangeType.MEMBER_REMOVE, {"member_name": "m1"}),
            (ChangeType.CHANNEL_ADD, {}),
            (ChangeType.CHANNEL_REMOVE, {}),
            (ChangeType.SETTINGS_CHANGE, {}),
        ],
    )
    def test_change_types(self, service, change_type, data):
        result = service._apply_google_chat_change("S1", change_type, data)
        assert result["success"] is True

    def test_missing_data_clean_failure(self, service):
        result = service._apply_google_chat_change("S1", ChangeType.MEMBER_ADD, {})
        assert result["success"] is False

    def test_service_not_available(self, service):
        import integrations.atom_google_chat_integration as agc

        with patch.object(agc, "atom_google_chat_integration", None):
            result = service._apply_google_chat_change("S1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False

    def test_import_error(self, service):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "integrations.atom_google_chat_integration":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = service._apply_google_chat_change("S1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False

    def test_generic_error(self, service):
        import integrations.atom_google_chat_integration as agc

        class _Boom:
            def __bool__(self):
                raise RuntimeError("gchat api down")

        with patch.object(agc, "atom_google_chat_integration", _Boom()):
            result = service._apply_google_chat_change("S1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False
        assert "gchat api down" in result["error"]


class TestTeamsHandler:
    @pytest.mark.parametrize(
        "change_type, data",
        [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "N"}),
            (ChangeType.MEMBER_ADD, {"email": "a@b.c"}),
            (ChangeType.MEMBER_REMOVE, {"user_id": "u1"}),
            (ChangeType.CHANNEL_ADD, {"channel_name": "c1"}),
            (ChangeType.CHANNEL_REMOVE, {"channel_id": "ch1"}),
            (ChangeType.SETTINGS_CHANGE, {}),
        ],
    )
    def test_change_types(self, service, change_type, data):
        result = service._apply_teams_change("TM1", change_type, data)
        assert result["success"] is True

    def test_missing_data_clean_failure(self, service):
        result = service._apply_teams_change("TM1", ChangeType.MEMBER_ADD, {})
        assert result["success"] is False

    def test_service_not_available(self, service):
        import integrations.atom_teams_integration as ati

        with patch.object(ati, "atom_teams_integration", None):
            result = service._apply_teams_change("TM1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False

    def test_import_error(self, service):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "integrations.atom_teams_integration":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = service._apply_teams_change("TM1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False

    def test_generic_error(self, service):
        import integrations.atom_teams_integration as ati

        class _Boom:
            def __bool__(self):
                raise RuntimeError("teams api down")

        with patch.object(ati, "atom_teams_integration", _Boom()):
            result = service._apply_teams_change("TM1", ChangeType.MEMBER_ADD, {"email": "a@b.c"})
        assert result["success"] is False
        assert "teams api down" in result["error"]
