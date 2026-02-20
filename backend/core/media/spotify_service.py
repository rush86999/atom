"""
Spotify Web API Integration with OAuth 2.0

Provides Spotify playback control, device management, and OAuth authentication
for AI agents. Uses encrypted token storage via OAuthToken model.

Features:
- OAuth 2.0 flow with PKCE support
- Encrypted token storage (access_token, refresh_token)
- Automatic token refresh on expiration
- Playback control (play, pause, skip, volume)
- Device discovery and transfer
- Currently playing track retrieval

Governance: SUPERVISED+ maturity level required
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

import httpx
from fastapi import HTTPException, status

from core.models import OAuthToken
from core.oauth_handler import OAuthConfig, OAuthHandler

logger = logging.getLogger(__name__)


class SpotifyService:
    """
    Spotify Web API integration with OAuth 2.0 authentication.

    Handles Spotify OAuth flow, token management, and playback control.
    Tokens are encrypted at rest using the OAuthToken model.
    """

    # Spotify OAuth scopes for playback control
    SCOPES = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "user-library-read",
        "user-read-playback-position",
    ]

    # Spotify API endpoints
    BASE_URL = "https://api.spotify.com/v1"

    def __init__(self, db: Session):
        """
        Initialize Spotify service with database session.

        Args:
            db: SQLAlchemy database session for token storage
        """
        self.db = db

        # Configure OAuth handler for Spotify
        self.oauth_config = OAuthConfig(
            client_id_env="SPOTIFY_CLIENT_ID",
            client_secret_env="SPOTIFY_CLIENT_SECRET",
            redirect_uri_env="SPOTIFY_REDIRECT_URI",
            auth_url="https://accounts.spotify.com/authorize",
            token_url="https://accounts.spotify.com/api/token",
            scopes=self.SCOPES,
        )
        self.oauth_handler = OAuthHandler(self.oauth_config)

    async def get_authorization_url(self, user_id: str) -> str:
        """
        Generate Spotify OAuth authorization URL.

        Args:
            user_id: User ID requesting authorization

        Returns:
            Authorization URL for Spotify OAuth flow

        Raises:
            HTTPException: If OAuth not configured
        """
        # Generate state parameter for CSRF protection
        import secrets
        state = secrets.token_urlsafe(16)

        auth_url = self.oauth_handler.get_authorization_url(state=state)

        logger.info(f"Generated Spotify auth URL for user {user_id}")
        return auth_url

    async def exchange_code_for_tokens(self, code: str, user_id: str) -> Dict:
        """
        Exchange OAuth authorization code for access tokens.

        Args:
            code: Authorization code from Spotify callback
            user_id: User ID completing OAuth flow

        Returns:
            Dict with success status and token info

        Raises:
            HTTPException: If token exchange fails
        """
        try:
            # Exchange code for tokens
            token_data = await self.oauth_handler.exchange_code_for_tokens(code)

            # Calculate token expiration (Spotify tokens expire in 1 hour)
            expires_in = token_data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            # Check if OAuth token already exists for this user
            existing_token = (
                self.db.query(OAuthToken)
                .filter(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == "spotify"
                )
                .first()
            )

            if existing_token:
                # Update existing token
                existing_token.access_token = token_data["access_token"]
                existing_token.refresh_token = token_data.get("refresh_token", existing_token.refresh_token)
                existing_token.expires_at = expires_at
                existing_token.scopes = token_data.get("scope", "").split()
                existing_token.status = "active"
                existing_token.last_used = datetime.utcnow()
                logger.info(f"Updated Spotify OAuth token for user {user_id}")
            else:
                # Create new token record
                new_token = OAuthToken(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    provider="spotify",
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token"),
                    token_type=token_data.get("token_type", "Bearer"),
                    scopes=token_data.get("scope", "").split(),
                    expires_at=expires_at,
                    status="active",
                    last_used=datetime.utcnow(),
                )
                self.db.add(new_token)
                logger.info(f"Created Spotify OAuth token for user {user_id}")

            self.db.commit()

            return {
                "success": True,
                "message": "Spotify authorization successful",
                "expires_at": expires_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Spotify token exchange failed for user {user_id}: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange authorization code: {str(e)}"
            )

    async def refresh_tokens(self, user_id: str) -> Dict:
        """
        Refresh expired Spotify access token using refresh token.

        Args:
            user_id: User ID requesting token refresh

        Returns:
            Dict with new token data

        Raises:
            HTTPException: If refresh fails
        """
        try:
            # Get existing token
            oauth_token = (
                self.db.query(OAuthToken)
                .filter(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == "spotify",
                    OAuthToken.status == "active"
                )
                .first()
            )

            if not oauth_token:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active Spotify token found. Please authorize first."
                )

            if not oauth_token.refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No refresh token available. Please re-authorize."
                )

            # Refresh token using OAuth handler
            token_data = await self.oauth_handler.refresh_access_token(
                oauth_token.refresh_token
            )

            # Update token
            expires_in = token_data.get("expires_in", 3600)
            oauth_token.access_token = token_data["access_token"]
            oauth_token.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            oauth_token.last_used = datetime.utcnow()

            self.db.commit()

            logger.info(f"Refreshed Spotify token for user {user_id}")
            return {"success": True, "expires_at": oauth_token.expires_at.isoformat()}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Spotify token refresh failed for user {user_id}: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to refresh token: {str(e)}"
            )

    async def _get_access_token(self, user_id: str) -> str:
        """
        Get valid access token for user, refreshing if necessary.

        Args:
            user_id: User ID requesting access token

        Returns:
            Valid access token

        Raises:
            HTTPException: If token not found or refresh fails
        """
        oauth_token = (
            self.db.query(OAuthToken)
            .filter(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == "spotify",
                OAuthToken.status == "active"
            )
            .first()
        )

        if not oauth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not connected to Spotify. Please authorize first."
            )

        # Check if token needs refresh
        if oauth_token.is_expired():
            await self.refresh_tokens(user_id)
            # Reload token after refresh
            self.db.refresh(oauth_token)

        oauth_token.last_used = datetime.utcnow()
        self.db.commit()

        return oauth_token.access_token

    async def _make_spotify_request(
        self,
        method: str,
        endpoint: str,
        user_id: str,
        **kwargs
    ) -> Dict:
        """
        Make authenticated request to Spotify API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            user_id: User ID for authentication
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response data

        Raises:
            HTTPException: If request fails
        """
        access_token = await self._get_access_token(user_id)

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {access_token}"

        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                )

                if response.status_code == 401:
                    # Token expired, try refresh once
                    await self.refresh_tokens(user_id)
                    access_token = await self._get_access_token(user_id)
                    headers["Authorization"] = f"Bearer {access_token}"

                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        **kwargs
                    )

                if response.status_code == 204:
                    return {"success": True}
                elif response.status_code >= 400:
                    error_detail = response.json().get("error", {}).get("message", "Unknown error")
                    logger.error(f"Spotify API error: {response.status_code} - {error_detail}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )

                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Spotify API request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Spotify service unavailable"
            )

    async def get_current_track(self, user_id: str) -> Dict:
        """
        Get currently playing track for user.

        Args:
            user_id: User ID requesting track info

        Returns:
            Dict with track information (artist, name, album, is_playing)
        """
        try:
            data = await self._make_spotify_request("GET", "/me/player/currently-playing", user_id)

            if not data or data.get("item") is None:
                return {
                    "success": True,
                    "playing": False,
                    "message": "No track currently playing"
                }

            track = data["item"]
            return {
                "success": True,
                "playing": data.get("is_playing", False),
                "track": {
                    "name": track.get("name"),
                    "artist": ", ".join([a["name"] for a in track.get("artists", [])]),
                    "album": track.get("album", {}).get("name"),
                    "uri": track.get("uri"),
                    "duration_ms": track.get("duration_ms"),
                    "progress_ms": data.get("progress_ms"),
                },
                "device": {
                    "name": data.get("device", {}).get("name"),
                    "type": data.get("device", {}).get("type"),
                    "volume_percent": data.get("device", {}).get("volume_percent"),
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get current track for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve current track: {str(e)}"
            )

    async def play_track(
        self,
        user_id: str,
        track_uri: Optional[str] = None,
        device_id: Optional[str] = None,
        context_uri: Optional[str] = None
    ) -> Dict:
        """
        Play track or resume playback.

        Args:
            user_id: User ID requesting playback
            track_uri: Spotify track URI (optional, resumes if None)
            device_id: Target device ID (optional)
            context_uri: Album/playlist URI (optional)

        Returns:
            Dict with playback status
        """
        try:
            body = {}
            if track_uri:
                body["uris"] = [track_uri]
            elif context_uri:
                body["context_uri"] = context_uri

            params = {}
            if device_id:
                params["device_id"] = device_id

            endpoint = "/me/player/play"
            await self._make_spotify_request(
                "PUT",
                endpoint,
                user_id,
                params=params,
                json=body
            )

            logger.info(f"Started playback for user {user_id} (track={track_uri}, device={device_id})")
            return {"success": True, "message": "Playback started"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to play track for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to play track: {str(e)}"
            )

    async def pause_playback(self, user_id: str, device_id: Optional[str] = None) -> Dict:
        """
        Pause playback.

        Args:
            user_id: User ID requesting pause
            device_id: Target device ID (optional)

        Returns:
            Dict with pause confirmation
        """
        try:
            params = {}
            if device_id:
                params["device_id"] = device_id

            await self._make_spotify_request(
                "PUT",
                "/me/player/pause",
                user_id,
                params=params
            )

            logger.info(f"Paused playback for user {user_id}")
            return {"success": True, "message": "Playback paused"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to pause playback for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to pause playback: {str(e)}"
            )

    async def skip_next(self, user_id: str, device_id: Optional[str] = None) -> Dict:
        """
        Skip to next track.

        Args:
            user_id: User ID requesting skip
            device_id: Target device ID (optional)

        Returns:
            Dict with skip confirmation
        """
        try:
            params = {}
            if device_id:
                params["device_id"] = device_id

            await self._make_spotify_request(
                "POST",
                "/me/player/next",
                user_id,
                params=params
            )

            logger.info(f"Skipped to next track for user {user_id}")
            return {"success": True, "message": "Skipped to next track"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to skip next for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to skip track: {str(e)}"
            )

    async def skip_previous(self, user_id: str, device_id: Optional[str] = None) -> Dict:
        """
        Skip to previous track.

        Args:
            user_id: User ID requesting previous
            device_id: Target device ID (optional)

        Returns:
            Dict with skip confirmation
        """
        try:
            params = {}
            if device_id:
                params["device_id"] = device_id

            await self._make_spotify_request(
                "POST",
                "/me/player/previous",
                user_id,
                params=params
            )

            logger.info(f"Skipped to previous track for user {user_id}")
            return {"success": True, "message": "Skipped to previous track"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to skip previous for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to skip to previous track: {str(e)}"
            )

    async def set_volume(
        self,
        user_id: str,
        volume_percent: int,
        device_id: Optional[str] = None
    ) -> Dict:
        """
        Set playback volume.

        Args:
            user_id: User ID setting volume
            volume_percent: Volume level (0-100)
            device_id: Target device ID (optional)

        Returns:
            Dict with volume confirmation
        """
        if not 0 <= volume_percent <= 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Volume must be between 0 and 100"
            )

        try:
            params = {}
            if device_id:
                params["device_id"] = device_id

            # Spotify expects volume percent as JSON body
            await self._make_spotify_request(
                "PUT",
                f"/me/player/volume?volume_percent={volume_percent}",
                user_id,
                params=params
            )

            logger.info(f"Set volume to {volume_percent}% for user {user_id}")
            return {"success": True, "message": f"Volume set to {volume_percent}%"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to set volume for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to set volume: {str(e)}"
            )

    async def get_available_devices(self, user_id: str) -> Dict:
        """
        Get available Spotify devices for user.

        Args:
            user_id: User ID requesting devices

        Returns:
            Dict with list of available devices
        """
        try:
            data = await self._make_spotify_request("GET", "/me/player/devices", user_id)

            devices = [
                {
                    "id": d.get("id"),
                    "name": d.get("name"),
                    "type": d.get("type"),
                    "is_active": d.get("is_active"),
                    "is_restricted": d.get("is_restricted"),
                    "volume_percent": d.get("volume_percent"),
                }
                for d in data.get("devices", [])
            ]

            return {
                "success": True,
                "devices": devices,
                "count": len(devices)
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get devices for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve devices: {str(e)}"
            )
