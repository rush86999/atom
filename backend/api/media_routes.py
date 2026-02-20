"""
Media Control REST API Endpoints

Provides OAuth flow and media control endpoints for Spotify and Sonos.
All endpoints require authentication via get_current_user dependency.

OAuth Flow:
1. GET /integrations/spotify/authorize - Get Spotify OAuth URL
2. GET /integrations/spotify/callback - OAuth callback (token exchange)

Spotify Control:
- GET /media/spotify/current - Get currently playing track
- POST /media/spotify/play - Play track or resume
- POST /media/spotify/pause - Pause playback
- POST /media/spotify/next - Skip to next track
- POST /media/spotify/previous - Skip to previous
- POST /media/spotify/volume - Set volume
- GET /media/spotify/devices - Get available devices

Sonos Control:
- GET /media/sonos/discover - Discover speakers
- POST /media/sonos/play - Play on speaker
- POST /media/sonos/pause - Pause speaker
- POST /media/sonos/volume - Set volume
- GET /media/sonos/groups - Get groups
- POST /media/sonos/join - Join group
- POST /media/sonos/leave - Leave group
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
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

from api.authentication import get_current_user
from core.models import User

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/media", tags=["media", "integrations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AuthorizeResponse(BaseModel):
    """OAuth authorization URL response."""
    authorization_url: str
    provider: str = "spotify"


class CallbackResponse(BaseModel):
    """OAuth callback response."""
    success: bool
    message: str
    expires_at: Optional[str] = None


class TrackInfo(BaseModel):
    """Currently playing track info."""
    name: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    uri: Optional[str]
    duration_ms: Optional[int]
    progress_ms: Optional[int]


class DeviceInfo(BaseModel):
    """Device information."""
    id: Optional[str]
    name: Optional[str]
    type: Optional[str]
    is_active: Optional[bool]
    volume_percent: Optional[int]


class CurrentTrackResponse(BaseModel):
    """Current track response."""
    success: bool
    playing: bool = False
    message: Optional[str] = None
    track: Optional[TrackInfo] = None
    device: Optional[DeviceInfo] = None


class PlayRequest(BaseModel):
    """Play track request."""
    track_uri: Optional[str] = Field(None, description="Spotify track URI (optional)")
    device_id: Optional[str] = Field(None, description="Target device ID (optional)")


class VolumeRequest(BaseModel):
    """Volume request."""
    volume_percent: int = Field(..., ge=0, le=100, description="Volume level (0-100)")
    device_id: Optional[str] = Field(None, description="Target device ID (optional)")


class DeviceIdRequest(BaseModel):
    """Device ID request."""
    device_id: Optional[str] = Field(None, description="Target device ID (optional)")


class SonosPlayRequest(BaseModel):
    """Sonos play request."""
    speaker_ip: str = Field(..., description="Sonos speaker IP address")
    uri: Optional[str] = Field(None, description="Audio URI to play (optional)")


class SonosSpeakerRequest(BaseModel):
    """Sonos speaker request."""
    speaker_ip: str = Field(..., description="Sonos speaker IP address")


class SonosVolumeRequest(BaseModel):
    """Sonos volume request."""
    speaker_ip: str = Field(..., description="Sonos speaker IP address")
    volume: int = Field(..., ge=0, le=100, description="Volume level (0-100)")


class SonosGroupRequest(BaseModel):
    """Sonos group join request."""
    speaker_ip: str = Field(..., description="Speaker IP to join")
    group_leader_ip: str = Field(..., description="Group coordinator IP")


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Error response."""
    success: bool = False
    error: str
    governance_blocked: Optional[bool] = None


# ============================================================================
# OAuth Endpoints
# ============================================================================

@router.get("/integrations/spotify/authorize", response_model=AuthorizeResponse)
async def spotify_authorize(
    redirect_uri: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Spotify OAuth authorization URL.

    Initiates OAuth flow by returning authorization URL for user to visit.
    User will be redirected back to /integrations/spotify/callback after approval.
    """
    try:
        spotify_service = SpotifyService(db)
        auth_url = await spotify_service.get_authorization_url(current_user.id)

        return AuthorizeResponse(
            authorization_url=auth_url,
            provider="spotify"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate Spotify auth URL for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authorization URL"
        )


@router.get("/integrations/spotify/callback", response_model=CallbackResponse)
async def spotify_callback(
    code: str,
    state: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Spotify OAuth callback endpoint.

    Exchanges authorization code for access tokens.
    Tokens are encrypted and stored in database.
    """
    try:
        spotify_service = SpotifyService(db)
        result = await spotify_service.exchange_code_for_tokens(code, current_user.id)

        return CallbackResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Spotify OAuth callback failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete OAuth flow"
        )


# ============================================================================
# Spotify Control Endpoints
# ============================================================================

@router.get("/spotify/current", response_model=CurrentTrackResponse)
async def get_spotify_current(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get currently playing track from Spotify."""
    try:
        result = await spotify_current(db, current_user.id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to get current track")
            )

        return CurrentTrackResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current track for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve current track"
        )


@router.post("/spotify/play", response_model=SuccessResponse)
async def spotify_play_endpoint(
    request: PlayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Play track or resume playback on Spotify."""
    try:
        result = await spotify_play(
            db,
            current_user.id,
            track_uri=request.track_uri,
            device_id=request.device_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to play track")
            )

        return SuccessResponse(
            success=True,
            message=result.get("message", "Playback started")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to play track for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to play track"
        )


@router.post("/spotify/pause", response_model=SuccessResponse)
async def spotify_pause_endpoint(
    request: DeviceIdRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause Spotify playback."""
    try:
        device_id = request.device_id if request else None
        result = await spotify_pause(db, current_user.id, device_id=device_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to pause playback")
            )

        return SuccessResponse(success=True, message="Playback paused")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause Spotify for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause playback"
        )


@router.post("/spotify/next", response_model=SuccessResponse)
async def spotify_next_endpoint(
    request: DeviceIdRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Skip to next track on Spotify."""
    try:
        device_id = request.device_id if request else None
        result = await spotify_next(db, current_user.id, device_id=device_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to skip track")
            )

        return SuccessResponse(success=True, message="Skipped to next track")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to skip next for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip track"
        )


@router.post("/spotify/previous", response_model=SuccessResponse)
async def spotify_previous_endpoint(
    request: DeviceIdRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Skip to previous track on Spotify."""
    try:
        device_id = request.device_id if request else None
        result = await spotify_previous(db, current_user.id, device_id=device_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to skip to previous")
            )

        return SuccessResponse(success=True, message="Skipped to previous track")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to skip previous for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip to previous track"
        )


@router.post("/spotify/volume", response_model=SuccessResponse)
async def spotify_volume_endpoint(
    request: VolumeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set Spotify volume."""
    try:
        result = await spotify_volume(
            db,
            current_user.id,
            request.volume_percent,
            device_id=request.device_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to set volume")
            )

        return SuccessResponse(
            success=True,
            message=f"Volume set to {request.volume_percent}%"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set volume for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set volume"
        )


@router.get("/spotify/devices")
async def get_spotify_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available Spotify devices."""
    try:
        result = await spotify_devices(db, current_user.id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to get devices")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get devices for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve devices"
        )


# ============================================================================
# Sonos Control Endpoints
# ============================================================================

@router.get("/sonos/discover")
async def sonos_discover_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Discover Sonos speakers on local network."""
    try:
        result = await sonos_discover(db)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to discover Sonos speakers: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to discover speakers"
        )


@router.post("/sonos/play", response_model=SuccessResponse)
async def sonos_play_endpoint(
    request: SonosPlayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Play audio or resume playback on Sonos speaker."""
    try:
        result = await sonos_play(db, request.speaker_ip, uri=request.uri)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to play")
            )

        return SuccessResponse(success=True, message="Playback started")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to play on Sonos speaker {request.speaker_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to play"
        )


@router.post("/sonos/pause", response_model=SuccessResponse)
async def sonos_pause_endpoint(
    request: SonosSpeakerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause Sonos speaker."""
    try:
        result = await sonos_pause(db, request.speaker_ip)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to pause")
            )

        return SuccessResponse(success=True, message="Playback paused")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause Sonos speaker {request.speaker_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause"
        )


@router.post("/sonos/volume", response_model=SuccessResponse)
async def sonos_volume_endpoint(
    request: SonosVolumeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set Sonos speaker volume."""
    try:
        result = await sonos_volume(db, request.speaker_ip, request.volume)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.get("error", "Failed to set volume")
            )

        return SuccessResponse(success=True, message=f"Volume set to {request.volume}%")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set volume for Sonos speaker {request.speaker_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set volume"
        )


@router.get("/sonos/groups")
async def sonos_groups_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Sonos speaker groups."""
    try:
        result = await sonos_groups(db)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Sonos groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to get groups"
        )
