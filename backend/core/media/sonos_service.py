"""
Sonos Speaker Control Service

Provides local network discovery and control of Sonos speakers.
Uses SoCo (Sonos Controller) library for UPnP/SSDP communication.

Features:
- Speaker discovery via SSDP/mDNS
- Playback control (play, pause, next, previous)
- Volume control
- Group management (join, leave)
- Current track info retrieval

Network Requirements:
- SSDP/mDNS must work (may require network_mode: host in Docker)
- Speakers must be on same network as Atom server

Governance: SUPERVISED+ maturity level required
"""

import logging
from typing import Dict, List, Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Try to import SoCo library
try:
    import soco
    SOCOS_AVAILABLE = True
    logger.info("SoCo library available - Sonos control enabled")
except ImportError:
    SOCOS_AVAILABLE = False
    logger.warning("SoCo library not installed - Sonos functions will fail")


class SonosService:
    """
    Sonos speaker discovery and control service.

    Provides local network control of Sonos speakers via UPnP/SSDP.
    No authentication required (local network only).
    """

    def __init__(self):
        """Initialize Sonos service."""
        if not SOCOS_AVAILABLE:
            logger.warning("SoCo library not available. Install with: pip install SoCo")

    async def discover_speakers(self) -> List[Dict]:
        """
        Discover Sonos speakers on local network via SSDP.

        Returns:
            List of discovered speakers with {ip, name, model, uid}

        Raises:
            HTTPException: If discovery fails or SoCo not available
        """
        if not SOCOS_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoCo library not installed. Install with: pip install SoCo>=0.31.0"
            )

        try:
            # Discover all Sonos speakers on network
            speakers = soco.discover()

            if not speakers:
                logger.info("No Sonos speakers discovered on network")
                return []

            discovered = []
            for speaker in speakers:
                speaker_info = speaker.get_speaker_info()

                discovered.append({
                    "ip": speaker.ip_address,
                    "name": speaker.player_name,
                    "model": speaker_info.get("model_name", "Unknown"),
                    "uid": speaker.uid,
                    "is_visible": speaker.is_visible,
                    "is_bridge": speaker.is_bridge,
                })

            logger.info(f"Discovered {len(discovered)} Sonos speakers on network")
            return discovered

        except Exception as e:
            logger.error(f"Sonos discovery failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to discover Sonos speakers: {str(e)}"
            )

    async def _get_speaker(self, speaker_ip: str):
        """
        Get SoCo device instance for speaker IP.

        Args:
            speaker_ip: IP address of Sonos speaker

        Returns:
            SoCo device instance

        Raises:
            HTTPException: If speaker not found or connection fails
        """
        if not SOCOS_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoCo library not installed"
            )

        try:
            device = soco.SoCo(speaker_ip)

            # Verify speaker is available
            if not device.is_visible:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Speaker at {speaker_ip} is not visible"
                )

            return device

        except Exception as e:
            logger.error(f"Failed to connect to Sonos speaker at {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Speaker not found at {speaker_ip}: {str(e)}"
            )

    async def play(
        self,
        speaker_ip: str,
        uri: Optional[str] = None
    ) -> Dict:
        """
        Play audio URI or resume playback.

        Args:
            speaker_ip: IP address of Sonos speaker
            uri: Audio URI to play (optional, resumes if None)

        Returns:
            Dict with play confirmation

        Raises:
            HTTPException: If play fails
        """
        try:
            device = await self._get_speaker(speaker_ip)

            if uri:
                # Play specific URI
                result = device.play_uri(uri)
            else:
                # Resume playback
                result = device.play()

            logger.info(f"Started playback on Sonos speaker {speaker_ip}")
            return {"success": True, "message": "Playback started", "speaker_ip": speaker_ip}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to play on Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to play: {str(e)}"
            )

    async def pause(self, speaker_ip: str) -> Dict:
        """
        Pause playback on speaker.

        Args:
            speaker_ip: IP address of Sonos speaker

        Returns:
            Dict with pause confirmation
        """
        try:
            device = await self._get_speaker(speaker_ip)
            device.pause()

            logger.info(f"Paused Sonos speaker {speaker_ip}")
            return {"success": True, "message": "Playback paused", "speaker_ip": speaker_ip}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to pause Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to pause: {str(e)}"
            )

    async def next_track(self, speaker_ip: str) -> Dict:
        """
        Skip to next track.

        Args:
            speaker_ip: IP address of Sonos speaker

        Returns:
            Dict with skip confirmation
        """
        try:
            device = await self._get_speaker(speaker_ip)
            device.next()

            logger.info(f"Skipped to next track on Sonos speaker {speaker_ip}")
            return {"success": True, "message": "Skipped to next track", "speaker_ip": speaker_ip}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to skip next on Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to skip track: {str(e)}"
            )

    async def previous_track(self, speaker_ip: str) -> Dict:
        """
        Skip to previous track.

        Args:
            speaker_ip: IP address of Sonos speaker

        Returns:
            Dict with skip confirmation
        """
        try:
            device = await self._get_speaker(speaker_ip)
            device.previous()

            logger.info(f"Skipped to previous track on Sonos speaker {speaker_ip}")
            return {"success": True, "message": "Skipped to previous track", "speaker_ip": speaker_ip}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to skip previous on Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to skip to previous: {str(e)}"
            )

    async def set_volume(self, speaker_ip: str, volume: int) -> Dict:
        """
        Set speaker volume.

        Args:
            speaker_ip: IP address of Sonos speaker
            volume: Volume level (0-100)

        Returns:
            Dict with volume confirmation

        Raises:
            HTTPException: If volume invalid or set fails
        """
        if not 0 <= volume <= 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Volume must be between 0 and 100"
            )

        try:
            device = await self._get_speaker(speaker_ip)
            device.volume = volume

            logger.info(f"Set Sonos speaker {speaker_ip} volume to {volume}")
            return {
                "success": True,
                "message": f"Volume set to {volume}",
                "speaker_ip": speaker_ip,
                "volume": volume
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to set volume on Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to set volume: {str(e)}"
            )

    async def get_current_track_info(self, speaker_ip: str) -> Dict:
        """
        Get currently playing track info.

        Args:
            speaker_ip: IP address of Sonos speaker

        Returns:
            Dict with track information
        """
        try:
            device = await self._get_speaker(speaker_ip)
            track_info = device.get_current_track_info()

            return {
                "success": True,
                "speaker_ip": speaker_ip,
                "track": {
                    "title": track_info.get("title"),
                    "artist": track_info.get("artist"),
                    "album": track_info.get("album"),
                    "uri": track_info.get("uri"),
                    "duration": track_info.get("duration"),
                    "position": track_info.get("position"),
                },
                "is_playing": track_info.get("metadata", {}).get("streamContent") != "NOT_IMPLEMENTED"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get track info from Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get track info: {str(e)}"
            )

    async def get_groups(self) -> List[Dict]:
        """
        Get all Sonos groups on network.

        Returns:
            List of Sonos groups with speakers
        """
        if not SOCOS_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoCo library not installed"
            )

        try:
            speakers = soco.discover()

            if not speakers:
                return []

            # Get unique groups
            groups_dict = {}
            for speaker in speakers:
                group = speaker.group

                if group and group.uid not in groups_dict:
                    groups_dict[group.uid] = {
                        "uid": group.uid,
                        "name": group.group_name or f"Group {group.uid}",
                        "coordinator_ip": group.coordinator.ip_address if group.coordinator else None,
                        "speaker_ips": [s.ip_address for s in group.members],
                        "speaker_count": len(group.members),
                    }

            groups = list(groups_dict.values())
            logger.info(f"Discovered {len(groups)} Sonos groups")
            return groups

        except Exception as e:
            logger.error(f"Failed to get Sonos groups: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to get groups: {str(e)}"
            )

    async def join_group(
        self,
        speaker_ip: str,
        group_leader_ip: str
    ) -> Dict:
        """
        Join speaker to existing group.

        Args:
            speaker_ip: IP address of speaker to join
            group_leader_ip: IP address of group coordinator

        Returns:
            Dict with join confirmation
        """
        try:
            speaker_device = await self._get_speaker(speaker_ip)
            leader_device = await self._get_speaker(group_leader_ip)

            # Join speaker to leader's group
            speaker_device.join(leader_device.group)

            logger.info(f"Joined Sonos speaker {speaker_ip} to group led by {group_leader_ip}")
            return {
                "success": True,
                "message": f"Joined {speaker_ip} to group",
                "speaker_ip": speaker_ip,
                "group_leader_ip": group_leader_ip
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to join Sonos speaker {speaker_ip} to group: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to join group: {str(e)}"
            )

    async def leave_group(self, speaker_ip: str) -> Dict:
        """
        Remove speaker from group.

        Args:
            speaker_ip: IP address of speaker to leave group

        Returns:
            Dict with leave confirmation
        """
        try:
            device = await self._get_speaker(speaker_ip)
            device.leave()

            logger.info(f"Sonos speaker {speaker_ip} left group")
            return {
                "success": True,
                "message": "Left group",
                "speaker_ip": speaker_ip
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to leave group for Sonos speaker {speaker_ip}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to leave group: {str(e)}"
            )
