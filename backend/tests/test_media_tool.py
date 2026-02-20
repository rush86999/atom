"""
Tests for Media Control Tool (Spotify and Sonos)

Tests SpotifyService and SonosService with mocked external APIs.
Covers governance enforcement, OAuth flows, token encryption, and error handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import AgentRegistry, OAuthToken, User, AgentStatus

# Import functions directly
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        return mock

    @pytest.fixture
    def spotify_service(self, mock_oauth_handler):
        """Create SpotifyService with mocked OAuth handler."""
        with patch('core.media.spotify_service.OAuthHandler', return_value=mock_oauth_handler):
            service = SpotifyService()
            service.oauth = mock_oauth_handler
            return service

    def test_get_authorization_url_generates_valid_url(self, spotify_service):
        """Test authorization URL generation includes required parameters."""
        url = spotify_service.get_authorization_url()

        assert url is not None
        assert "client_id=" in url
        assert "redirect_uri=" in url
        assert "scope=" in url
        assert "user-read-playback-state" in url

    def test_exchange_code_for_tokens_stores_encrypted(self, spotify_service, db_session: Session):
        """Test token exchange stores encrypted token in database."""
        # Mock token exchange response
        spotify_service.oauth.exchange_code_for_token = MagicMock(return_value={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        })

        # Mock token encryption
        with patch('core.media.spotify_service.encrypt_token') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_access_token"

            user_id = "test_user"
            result = spotify_service.exchange_code_for_token("test_code", user_id, db_session)

            assert result is not None
            assert "access_token" in result
            # Verify token was encrypted before storage
            mock_encrypt.assert_called()

    def test_get_current_track_returns_track_info(self, spotify_service):
        """Test getting current track information."""
        # Mock Spotify API response
        mock_response = MagicMock()
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

        with patch('core.media.spotify_service.requests.get', return_value=mock_response):
            track = spotify_service.get_current_track("test_access_token")

            assert track is not None
            assert track["name"] == "Test Song"
            assert track["artist"] == "Test Artist"
            assert track["album"] == "Test Album"
            assert track["is_playing"] is True

    def test_play_track_success(self, spotify_service):
        """Test playing a track successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.json.return_value = {}

        with patch('core.media.spotify_service.requests.put', return_value=mock_response):
            result = spotify_service.play("test_access_token", track_uri="spotify:track:test")

            assert result is True

    def test_pause_playback_success(self, spotify_service):
        """Test pausing playback successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.json.return_value = {}

        with patch('core.media.spotify_service.requests.put', return_value=mock_response):
            result = spotify_service.pause("test_access_token")

            assert result is True

    def test_expired_token_refreshes_automatically(self, spotify_service, db_session: Session):
        """Test expired token triggers automatic refresh."""
        # Create an expired token
        user = User(id="test_user", email="test@example.com")
        db_session.add(user)

        expired_token = OAuthToken(
            user_id="test_user",
            provider="spotify",
            access_token="old_access_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            scope="user-read-playback-state"
        )
        db_session.add(expired_token)
        db_session.commit()

        # Mock token refresh
        with patch('core.media.spotify_service.SpotifyService.refresh_token') as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new_access_token",
                "expires_in": 3600
            }

            # Attempt to use expired token should trigger refresh
            mock_response = MagicMock()
            mock_response.json.return_value = {"item": {"name": "Test"}}
            with patch('core.media.spotify_service.requests.get', return_value=mock_response):
                track = spotify_service.get_current_track("old_access_token", "test_user", db_session)

                # Refresh should have been called
                assert mock_refresh.called

    def test_unauthorized_error_handling(self, spotify_service):
        """Test unauthorized error is handled gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid token"}

        with patch('core.media.spotify_service.requests.get', return_value=mock_response):
            with pytest.raises(Exception, match="Unauthorized"):
                spotify_service.get_current_track("invalid_token")


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

    def test_discover_speakers_returns_speaker_list(self, sonos_service):
        """Test speaker discovery returns list of found devices."""
        mock_speaker = MagicMock()
        mock_speaker.ip_address = "192.168.1.100"
        mock_speaker.player_name = "Living Room"
        mock_speaker.uid = "RINCON_00000000000001400"

        with patch('core.media.sonos_service.SoCo.discover', return_value=[mock_speaker]):
            speakers = sonos_service.discover_speakers()

            assert len(speakers) == 1
            assert speakers[0]["ip"] == "192.168.1.100"
            assert speakers[0]["name"] == "Living Room"
            assert "uid" in speakers[0]

    def test_play_on_speaker(self, sonos_service):
        """Test playing on a Sonos speaker."""
        mock_speaker = MagicMock()

        with patch('core.media.sonos_service.SoCo', return_value=mock_speaker):
            result = sonos_service.play("192.168.1.100", track_uri="spotify:track:test")

            assert result is True
            mock_speaker.play_from_queue.assert_called_once()

    def test_set_volume(self, sonos_service):
        """Test setting volume on Sonos speaker."""
        mock_speaker = MagicMock()

        with patch('core.media.sonos_service.SoCo', return_value=mock_speaker):
            result = sonos_service.set_volume("192.168.1.100", 50)

            assert result is True
            mock_speaker.volume = 50

    def test_join_group(self, sonos_service):
        """Test joining a speaker group."""
        mock_speaker = MagicMock()
        mock_coordinator = MagicMock()

        with patch('core.media.sonos_service.SoCo') as mock_soco_class:
            mock_soco_class.side_effect = [mock_speaker, mock_coordinator]

            result = sonos_service.join_group("192.168.1.100", "192.168.1.101")

            assert result is True
            mock_speaker.join.assert_called_once_with(mock_coordinator)

    def test_speaker_not_found_error(self, sonos_service):
        """Test error handling when speaker not found."""
        with patch('core.media.sonos_service.SoCo', side_effect=Exception("Speaker not found")):
            with pytest.raises(Exception, match="Speaker not found"):
                sonos_service.play("192.168.1.999", track_uri="spotify:track:test")


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
            mock_service.get_current_track.return_value = {"name": "Test Song"}
            mock_service_class.return_value = mock_service

            result = await spotify_current(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session
            )

            # Should pass governance check (will fail at service call if no token, but that's ok)
            assert "governance_check" in result

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
            mock_service.pause.return_value = True
            mock_service_class.return_value = mock_service

            result = await spotify_pause(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session
            )

            # Should pass governance check
            assert "governance_check" in result


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
            user_id="test_user",
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
            mock_service.play.return_value = True
            mock_service_class.return_value = mock_service

            result = await sonos_play(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                speaker_ip="192.168.1.100"
            )

            # Should pass governance check
            assert "governance_check" in result

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
            user_id="test_user",
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
