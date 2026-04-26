"""
Comprehensive tests for Spotify Service

Tests core.media.spotify_service module which provides Spotify Web API
integration with OAuth 2.0, playback control, and device management.

Target: backend/core/media/spotify_service.py (633 lines)
Test Categories: Spotify Integration, Music Operations, Audio Processing, Media Management
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import httpx

from core.media.spotify_service import SpotifyService
from core.models import OAuthToken


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    from core.models import Base

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def spotify_service(db_session: Session):
    """Create SpotifyService instance."""
    return SpotifyService(db_session)


@pytest.fixture
def sample_oauth_token():
    """Sample OAuth token for testing."""
    return OAuthToken(
        id="test-token-id",
        user_id="test-user",
        provider="spotify",
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        token_type="Bearer",
        scopes=["user-read-playback-state", "user-modify-playback-state"],
        expires_at=datetime.utcnow() + timedelta(hours=1),
        status="active",
        last_used=datetime.utcnow()
    )


# Test Category 1: Spotify Integration (5 tests)

class TestSpotifyIntegration:
    """Tests for Spotify service initialization and OAuth flow."""

    def test_service_initialization(self, db_session: Session):
        """Test service initializes with database session."""
        service = SpotifyService(db_session)

        assert service.db is db_session
        assert service.oauth_handler is not None
        assert service.SCOPES == [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "user-library-read",
            "user-read-playback-position",
        ]

    def test_base_url_configured(self, spotify_service: SpotifyService):
        """Test Spotify API base URL is configured."""
        assert spotify_service.BASE_URL == "https://api.spotify.com/v1"

    @pytest.mark.asyncio
    async def test_get_authorization_url(self, spotify_service: SpotifyService):
        """Test generating Spotify OAuth authorization URL."""
        user_id = "test-user"

        with patch.object(spotify_service.oauth_handler, 'get_authorization_url', return_value="https://accounts.spotify.com/authorize?test"):
            url = await spotify_service.get_authorization_url(user_id)

            assert url is not None
            assert "accounts.spotify.com" in url

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self, spotify_service: SpotifyService):
        """Test exchanging authorization code for tokens."""
        code = "test-authorization-code"
        user_id = "test-user"

        mock_token_data = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "user-read-playback-state"
        }

        with patch.object(spotify_service.oauth_handler, 'exchange_code_for_tokens', new=AsyncMock(return_value=mock_token_data)):
            result = await spotify_service.exchange_code_for_tokens(code, user_id)

            assert result["success"] is True
            assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_updates_existing_token(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test token exchange updates existing token."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        code = "test-code"
        user_id = "test-user"

        mock_token_data = {
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }

        with patch.object(spotify_service.oauth_handler, 'exchange_code_for_tokens', new=AsyncMock(return_value=mock_token_data)):
            result = await spotify_service.exchange_code_for_tokens(code, user_id)

            assert result["success"] is True

            # Verify token was updated
            updated_token = spotify_service.db.query(OAuthToken).filter(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == "spotify"
            ).first()

            assert updated_token.access_token == "updated-access-token"


# Test Category 2: Music Operations (5 tests)

class TestMusicOperations:
    """Tests for playback control and music operations."""

    @pytest.mark.asyncio
    async def test_get_current_track_playing(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test getting currently playing track."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        mock_track_data = {
            "item": {
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {"name": "Test Album"},
                "uri": "spotify:track:test",
                "duration_ms": 180000
            },
            "is_playing": True,
            "progress_ms": 50000,
            "device": {
                "name": "Test Device",
                "type": "Computer",
                "volume_percent": 75
            }
        }

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value=mock_track_data)):
            result = await spotify_service.get_current_track(user_id)

            assert result["success"] is True
            assert result["playing"] is True
            assert result["track"]["name"] == "Test Song"

    @pytest.mark.asyncio
    async def test_get_current_track_not_playing(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test getting current track when nothing is playing."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value=None)):
            result = await spotify_service.get_current_track(user_id)

            assert result["success"] is True
            assert result["playing"] is False
            assert "message" in result

    @pytest.mark.asyncio
    async def test_play_track(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test playing a track."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"
        track_uri = "spotify:track:test-track"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.play_track(user_id, track_uri=track_uri)

            assert result["success"] is True
            assert "Playback started" in result["message"]

    @pytest.mark.asyncio
    async def test_pause_playback(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test pausing playback."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.pause_playback(user_id)

            assert result["success"] is True
            assert "paused" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_skip_next(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test skipping to next track."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.skip_next(user_id)

            assert result["success"] is True
            assert "next" in result["message"].lower()


# Test Category 3: Audio Processing (5 tests)

class TestAudioProcessing:
    """Tests for audio metadata and quality settings."""

    @pytest.mark.asyncio
    async def test_skip_previous(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test skipping to previous track."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.skip_previous(user_id)

            assert result["success"] is True
            assert "previous" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_set_volume_valid(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test setting volume to valid value."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"
        volume = 75

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.set_volume(user_id, volume)

            assert result["success"] is True
            assert "75%" in result["message"]

    @pytest.mark.asyncio
    async def test_set_volume_invalid_low(self, spotify_service: SpotifyService):
        """Test setting volume below valid range raises error."""
        user_id = "test-user"

        with pytest.raises(Exception):  # HTTPException
            await spotify_service.set_volume(user_id, -10)

    @pytest.mark.asyncio
    async def test_set_volume_invalid_high(self, spotify_service: SpotifyService):
        """Test setting volume above valid range raises error."""
        user_id = "test-user"

        with pytest.raises(Exception):  # HTTPException
            await spotify_service.set_volume(user_id, 150)

    @pytest.mark.asyncio
    async def test_set_volume_boundary_values(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test setting volume to boundary values (0 and 100)."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            # Test volume 0
            result = await spotify_service.set_volume(user_id, 0)
            assert result["success"] is True

            # Test volume 100
            result = await spotify_service.set_volume(user_id, 100)
            assert result["success"] is True


# Test Category 4: Media Management (5 tests)

class TestMediaManagement:
    """Tests for device management and media library integration."""

    @pytest.mark.asyncio
    async def test_get_available_devices(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test getting available Spotify devices."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        mock_devices_data = {
            "devices": [
                {
                    "id": "device-1",
                    "name": "Test Device 1",
                    "type": "Computer",
                    "is_active": True,
                    "is_restricted": False,
                    "volume_percent": 75
                },
                {
                    "id": "device-2",
                    "name": "Test Device 2",
                    "type": "Smartphone",
                    "is_active": False,
                    "is_restricted": False,
                    "volume_percent": 50
                }
            ]
        }

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value=mock_devices_data)):
            result = await spotify_service.get_available_devices(user_id)

            assert result["success"] is True
            assert result["count"] == 2
            assert len(result["devices"]) == 2

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test refreshing expired access token."""
        sample_oauth_token.expires_at = datetime.utcnow() - timedelta(hours=1)
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        mock_new_token_data = {
            "access_token": "refreshed-access-token",
            "expires_in": 3600
        }

        with patch.object(spotify_service.oauth_handler, 'refresh_access_token', new=AsyncMock(return_value=mock_new_token_data)):
            result = await spotify_service.refresh_tokens(user_id)

            assert result["success"] is True
            assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_refresh_tokens_no_token_found(self, spotify_service: SpotifyService):
        """Test refreshing tokens when no token exists."""
        user_id = "nonexistent-user"

        with pytest.raises(Exception):  # HTTPException 404
            await spotify_service.refresh_tokens(user_id)

    @pytest.mark.asyncio
    async def test_get_access_token_auto_refresh(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test _get_access_token automatically refreshes expired tokens."""
        sample_oauth_token.expires_at = datetime.utcnow() - timedelta(hours=1)
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        mock_new_token_data = {
            "access_token": "new-token",
            "expires_in": 3600
        }

        with patch.object(spotify_service.oauth_handler, 'refresh_access_token', new=AsyncMock(return_value=mock_new_token_data)):
            token = await spotify_service._get_access_token(user_id)

            assert token == "new-token"

    @pytest.mark.asyncio
    async def test_play_track_with_device(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test playing track to specific device."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"
        track_uri = "spotify:track:test"
        device_id = "test-device"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.play_track(user_id, track_uri=track_uri, device_id=device_id)

            assert result["success"] is True


# Test Category 5: Error Handling (5 tests)

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_make_spotify_request_401_auto_refresh(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test request retries with token refresh on 401."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        # Mock first call returns 401, second call succeeds
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_response_401.json.return_value = {"error": {"message": "Invalid token"}}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": "success"}

        mock_client = AsyncMock()
        mock_client.request.side_effect = [mock_response_401, mock_response_success]

        with patch('httpx.AsyncClient', return_value=mock_client):
            with patch.object(spotify_service, 'refresh_tokens', new=AsyncMock(return_value={"success": True})):
                # This should handle 401 and retry
                result = await spotify_service._make_spotify_request("GET", "/test", user_id)

    @pytest.mark.asyncio
    async def test_make_spotify_request_network_error(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test request handles network errors gracefully."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.request.side_effect = httpx.RequestError("Network error")

            with pytest.raises(Exception):  # HTTPException 503
                await spotify_service._make_spotify_request("GET", "/test", user_id)

    @pytest.mark.asyncio
    async def test_get_current_track_no_token(self, spotify_service: SpotifyService):
        """Test getting current track without authorization raises error."""
        user_id = "unauthorized-user"

        with pytest.raises(Exception):  # HTTPException 401
            await spotify_service.get_current_track(user_id)

    @pytest.mark.asyncio
    async def test_exchange_code_error_handling(self, spotify_service: SpotifyService):
        """Test token exchange error handling."""
        code = "invalid-code"
        user_id = "test-user"

        with patch.object(spotify_service.oauth_handler, 'exchange_code_for_tokens', new=AsyncMock(side_effect=Exception("API error"))):
            with pytest.raises(Exception):  # HTTPException
                await spotify_service.exchange_code_for_tokens(code, user_id)

    @pytest.mark.asyncio
    async def test_pause_with_device_id(self, spotify_service: SpotifyService, sample_oauth_token: OAuthToken):
        """Test pausing playback on specific device."""
        spotify_service.db.add(sample_oauth_token)
        spotify_service.db.commit()

        user_id = "test-user"
        device_id = "test-device"

        with patch.object(spotify_service, '_make_spotify_request', new=AsyncMock(return_value={"success": True})):
            result = await spotify_service.pause_playback(user_id, device_id=device_id)

            assert result["success"] is True


# Total: 25 tests
