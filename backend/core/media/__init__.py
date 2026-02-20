"""
Media control services for Spotify and Sonos integration.

Provides:
- SpotifyService: Spotify Web API with OAuth 2.0
- SonosService: Sonos speaker discovery and control
"""

from core.media.spotify_service import SpotifyService

__all__ = ["SpotifyService"]

try:
    from core.media.sonos_service import SonosService
    __all__.append("SonosService")
except ImportError:
    pass  # Sonos service import error (e.g., models.py issue)
