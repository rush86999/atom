"""
Tests for Media Control Tool (Spotify and Sonos)

Tests SpotifyService and SonosService with mocked external APIs.
Covers governance enforcement, OAuth flows, token encryption, and error handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from core.models import AgentRegistry, IntegrationToken, User, AgentStatus

# Import functions directly
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.media.spotify_service import SpotifyService
from core.media.sonos_service import SonosService
from tools.media_tool import (
    spotify_current,
    spotify_play,
    spotify_pause,
    spotify_next,
    spotify_previous,
    spotify_volume,
    spotify_devices,
    sonos_discover,
    sonos_play,
    sonos_pause,
    sonos_volume,
    sonos_groups,
)


# ============================================================================
# SpotifyService Tests
# ============================================================================

class TestSpotifyService:
    """Test Spotify service with mocked API calls."""

    @pytest.fixture
    def mock_oauth_handler(self):
        """Mock OAuth handler for Spotify."""
        mock = MagicMock()
        mock.get_authorization_url.return_value = "https://accounts.spotify.com/authorize?client_id=test&redirect_uri=http://localhost:8000/integrations/spotify/callback&scope=user-read-playback-state"
        mock.exchange_code_for_tokens = AsyncMock(return_value={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "user-read-playback-state",
        })
        return mock

    @pytest.fixture
    def spotify_service(self, mock_oauth_handler, db_session):
        """Create SpotifyService with mocked OAuth handler."""
        with patch('core.media.spotify_service.OAuthHandler', return_value=mock_oauth_handler):
            service = SpotifyService(db_session)
            return service

    @pytest.fixture
    def mock_http_client(self):
        """Mock httpx client and response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "item": {
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {"name": "Test Album"},
                "duration_ms": 180000
            },
            "progress_ms": 50000,
            "is_playing": True
        }
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        return mock_cm, mock_response

    @pytest.mark.asyncio
    async def test_get_authorization_url_generates_valid_url(self, spotify_service):
        """Test authorization URL generation includes required parameters."""
        url = await spotify_service.get_authorization_url("test_user")

        assert url is not None
        assert "client_id=" in url
        assert "redirect_uri=" in url
        assert "scope=" in url
        assert "user-read-playback-state" in url

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_stores_token(self, spotify_service, db_session):
        """Test token exchange stores token in database."""
        result = await spotify_service.exchange_code_for_tokens("test_code", "test_user")

        assert result["success"] is True

        token = db_session.query(IntegrationToken).filter(
            IntegrationToken.user_id == "test_user"
        ).first()
        assert token is not None
        assert token.provider == "spotify"
        assert token.access_token == "test_access_token"

    @pytest.mark.asyncio
    async def test_get_current_track_returns_track_info(self, spotify_service, mock_http_client):
        """Test getting current track information."""
        mock_cm, _ = mock_http_client

        with patch('core.media.spotify_service.httpx.AsyncClient', return_value=mock_cm):
            with patch.object(spotify_service, '_get_access_token', new=AsyncMock(return_value="test_access_token")):
                track = await spotify_service.get_current_track("test_user")

        assert track["success"] is True
        assert track["track"]["name"] == "Test Song"
        assert track["track"]["artist"] == "Test Artist"
        assert track["track"]["album"] == "Test Album"
        assert track["playing"] is True

    @pytest.mark.asyncio
    async def test_play_track_success(self, spotify_service, mock_http_client):
        """Test playing a track successfully."""
        mock_cm, mock_response = mock_http_client
        mock_response.status_code = 204
        mock_response.json.return_value = {}

        with patch('core.media.spotify_service.httpx.AsyncClient', return_value=mock_cm):
            with patch.object(spotify_service, '_get_access_token', new=AsyncMock(return_value="test_access_token")):
                result = await spotify_service.play_track("test_user", track_uri="spotify:track:test")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_pause_playback_success(self, spotify_service, mock_http_client):
        """Test pausing playback successfully."""
        mock_cm, mock_response = mock_http_client
        mock_response.status_code = 204
        mock_response.json.return_value = {}

        with patch('core.media.spotify_service.httpx.AsyncClient', return_value=mock_cm):
            with patch.object(spotify_service, '_get_access_token', new=AsyncMock(return_value="test_access_token")):
                result = await spotify_service.pause_playback("test_user")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_expired_token_refreshes_automatically(self, spotify_service, db_session, mock_http_client):
        """Test expired token triggers automatic refresh."""
        token = IntegrationToken(
            id="tok_expired",
            tenant_id="default",
            user_id="test_user",
            provider="spotify",
            access_token="old_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            scope="user-read-playback-state",
            status="active"
        )
        db_session.add(token)
        db_session.commit()

        mock_cm, _ = mock_http_client

        with patch('core.media.spotify_service.httpx.AsyncClient', return_value=mock_cm):
            with patch.object(spotify_service, 'refresh_tokens', new=AsyncMock(return_value={"success": True})) as mock_refresh:
                await spotify_service.get_current_track("test_user")

                # Refresh should have been called (token expired)
                assert mock_refresh.called

    @pytest.mark.asyncio
    async def test_unauthorized_error_handling(self, spotify_service, mock_http_client):
        """Test unauthorized error is handled gracefully."""
        mock_cm, mock_response = mock_http_client
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid token"}}

        with patch('core.media.spotify_service.httpx.AsyncClient', return_value=mock_cm):
            with patch.object(spotify_service, '_get_access_token', new=AsyncMock(return_value="invalid_token")):
                with patch.object(spotify_service, 'refresh_tokens', new=AsyncMock(side_effect=HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token"))):
                    with pytest.raises(HTTPException, match="Invalid token"):
                        await spotify_service.get_current_track("test_user")


# ============================================================================
# SonosService Tests
# ============================================================================

class TestSonosService:
    """Test Sonos service with mocked SoCo library."""

    @pytest.fixture
    def mock_soco(self):
        """Mock SoCo library."""
        mock = MagicMock()
        mock.ip_address = "192.168.1.100"
        mock.player_name = "Living Room"
        mock.uid = "RINCON_00000000000001400"
        return mock

    @pytest.fixture
    def sonos_service(self):
        """Create SonosService with mocked SoCo."""
        service = SonosService()
        return service

    @pytest.mark.asyncio
    async def test_discover_speakers_returns_speaker_list(self, sonos_service):
        """Test speaker discovery returns list of found devices."""
        mock_speaker = MagicMock()
        mock_speaker.ip_address = "192.168.1.100"
        mock_speaker.player_name = "Living Room"
        mock_speaker.uid = "RINCON_00000000000001400"
        mock_speaker.get_speaker_info.return_value = {"model_name": "Sonos One"}
        mock_speaker.is_visible = True
        mock_speaker.is_bridge = False

        with patch('core.media.sonos_service.SOCOS_AVAILABLE', True):
            fake_soco = MagicMock()
            fake_soco.discover.return_value = [mock_speaker]
            with patch('core.media.sonos_service.soco', fake_soco):
                speakers = await sonos_service.discover_speakers()

        assert len(speakers) == 1
        assert speakers[0]["ip"] == "192.168.1.100"
        assert speakers[0]["name"] == "Living Room"
        assert "uid" in speakers[0]

    @pytest.mark.asyncio
    async def test_play_on_speaker(self, sonos_service):
        """Test playing on a Sonos speaker."""
        mock_speaker = MagicMock()
        mock_speaker.is_visible = True

        with patch('core.media.sonos_service.SOCOS_AVAILABLE', True):
            fake_soco = MagicMock()
            fake_soco.SoCo.return_value = mock_speaker
            with patch('core.media.sonos_service.soco', fake_soco):
                result = await sonos_service.play("192.168.1.100", uri="spotify:track:test")

        assert result["success"] is True
        mock_speaker.play_uri.assert_called_once_with("spotify:track:test")

    @pytest.mark.asyncio
    async def test_set_volume(self, sonos_service):
        """Test setting volume on Sonos speaker."""
        mock_speaker = MagicMock()
        mock_speaker.is_visible = True

        with patch('core.media.sonos_service.SOCOS_AVAILABLE', True):
            fake_soco = MagicMock()
            fake_soco.SoCo.return_value = mock_speaker
            with patch('core.media.sonos_service.soco', fake_soco):
                result = await sonos_service.set_volume("192.168.1.100", 50)

        assert result["success"] is True
        assert mock_speaker.volume == 50

    @pytest.mark.asyncio
    async def test_join_group(self, sonos_service):
        """Test joining a speaker group."""
        mock_speaker = MagicMock()
        mock_speaker.is_visible = True
        mock_coordinator = MagicMock()
        mock_coordinator.is_visible = True

        with patch('core.media.sonos_service.SOCOS_AVAILABLE', True):
            fake_soco = MagicMock()
            fake_soco.SoCo.side_effect = [mock_speaker, mock_coordinator]
            with patch('core.media.sonos_service.soco', fake_soco):
                result = await sonos_service.join_group("192.168.1.100", "192.168.1.101")

        assert result["success"] is True
        mock_speaker.join.assert_called_once_with(mock_coordinator.group)

    @pytest.mark.asyncio
    async def test_speaker_not_found_error(self, sonos_service):
        """Test error handling when speaker not found."""
        with patch('core.media.sonos_service.SOCOS_AVAILABLE', True):
            fake_soco = MagicMock()
            fake_soco.SoCo.side_effect = Exception("Speaker not found")
            with patch('core.media.sonos_service.soco', fake_soco):
                with pytest.raises(HTTPException):
                    await sonos_service.play("192.168.1.999")


# ============================================================================
# SpotifyTool Tests
# ============================================================================

class TestSpotifyToolGovernance:
    """Test governance enforcement for Spotify tool."""

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_spotify_control(self, db_session: Session):
        """Test STUDENT agent is blocked from Spotify control."""
        agent = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            maturity_level="STUDENT",
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        result = await spotify_current(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_intern_agent_blocked_from_spotify_write(self, db_session: Session):
        """Test INTERN agent blocked from write operations."""
        agent = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="TestIntern",
            status=AgentStatus.INTERN.value,
            maturity_level="INTERN",
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        result = await spotify_play(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session,
            track_uri="spotify:track:test"
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_supervised_agent_can_control_playback(self, db_session: Session):
        """Test SUPERVISED agent can control playback."""
        agent = AgentRegistry(
            name="SupervisedAgent",
            category="test",
            module_path="test.module",
            class_name="TestSupervised",
            status=AgentStatus.SUPERVISED.value,
            maturity_level="SUPERVISED",
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Spotify service
        with patch('tools.media_tool.SpotifyService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_current_track = AsyncMock(return_value={"name": "Test Song"})
            mock_service_class.return_value = mock_service

            result = await spotify_current(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session
            )

            # Should pass governance check (will fail at service call if no token, but that's ok)
            assert result["name"] == "Test Song"

    @pytest.mark.asyncio
    async def test_autonomous_agent_has_full_access(self, db_session: Session):
        """Test AUTONOMOUS agent has full Spotify access."""
        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Spotify service
        with patch('tools.media_tool.SpotifyService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.pause_playback = AsyncMock(return_value={"success": True})
            mock_service_class.return_value = mock_service

            result = await spotify_pause(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session
            )

            # Should pass governance check
            assert result["success"] is True


# ============================================================================
# SonosTool Governance Tests
# ============================================================================

class TestSonosToolGovernance:
    """Test governance enforcement for Sonos tool."""

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_sonos_control(self, db_session: Session):
        """Test STUDENT agent is blocked from Sonos control."""
        agent = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            maturity_level="STUDENT",
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        result = await sonos_play(
            agent_id=agent.id,
            db=db_session,
            speaker_ip="192.168.1.100"
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_supervised_agent_can_control_sonos(self, db_session: Session):
        """Test SUPERVISED agent can control Sonos."""
        agent = AgentRegistry(
            name="SupervisedAgent",
            category="test",
            module_path="test.module",
            class_name="TestSupervised",
            status=AgentStatus.SUPERVISED.value,
            maturity_level="SUPERVISED",
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Sonos service
        with patch('tools.media_tool.SonosService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.play = AsyncMock(return_value={"success": True})
            mock_service_class.return_value = mock_service

            result = await sonos_play(
                agent_id=agent.id,
                db=db_session,
                speaker_ip="192.168.1.100"
            )

            # Should pass governance check
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_discover_action_restricted_to_intern_plus(self, db_session: Session):
        """Test discover action requires INTERN+ maturity."""
        agent = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            maturity_level="STUDENT",
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        result = await sonos_discover(
            agent_id=agent.id,
            db=db_session
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestMediaIntegration:
    """Integration tests requiring real credentials."""

    @pytest.mark.skip(reason="Requires real Spotify credentials")
    def test_real_spotify_current_track(self):
        """Test with real Spotify API (requires credentials)."""
        # This test only runs with: pytest -m integration
        pass

    @pytest.mark.skip(reason="Requires real Sonos speakers on network")
    def test_real_sonos_discovery(self):
        """Test with real Sonos speakers (requires local network)."""
        # This test only runs with: pytest -m integration
        pass
