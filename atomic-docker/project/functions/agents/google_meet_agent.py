import asyncio
import os
import subprocess
import sys
import logging
import platform
from typing import Optional, AsyncIterator, Dict, Any

# Initialize logger for this module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Attempt to import sounddevice, but make it optional
try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice library not found. Real audio capture will not be available for GoogleMeetAgent.")
    # Dummy sd object for type hinting and basic class structure
    class DummySoundDevice:
        def __init__(self): pass
        def RawInputStream(self, *args, **kwargs): raise NotImplementedError("sounddevice not available")
        def query_devices(self, *args, **kwargs) -> list: return []
        def get_hostapi_info(self, *args, **kwargs) -> Dict[str, Any]: return {}
        class PortAudioError(Exception): pass
        class CallbackFlags(int): pass
    sd = DummySoundDevice()

class GoogleMeetAgent:
    """
    GoogleMeetAgent aims to interact with Google Meet meetings. Its primary functionalities include:
    1. Launching/Joining Google Meet meetings using system-level URL handlers.
    2. Capturing audio from a specified or default system audio input device.

    IMPORTANT AUDIO CAPTURE NOTE:
    By default, this agent will capture audio from the system's default microphone.
    To capture the actual meeting audio (i.e., what you hear from other participants),
    you MUST configure your system's audio routing. This typically involves:
    - Windows: Enabling "Stereo Mix" as an input device and setting it as default, or using a virtual audio cable.
    - macOS/Linux: Using software like BlackHole, LoopBeAudio, VB-Cable, or PulseAudio loopback module
      to route application output (Google Meet's audio from the browser) to a virtual input device,
      then configuring this agent to use that virtual input device via the
      `GOOGLE_MEET_AGENT_AUDIO_DEVICE_NAME_OR_ID` environment variable.
    Without proper audio routing, this agent will only capture microphone input.
    """
    def __init__(self, user_id: str):
        self.user_id: str = user_id
        self.current_meeting_url: Optional[str] = None

        self.audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.is_capturing: bool = False
        self.audio_stream: Optional[sd.RawInputStream] = None
        self.selected_audio_device_info: Optional[Dict[str, Any]] = None # Store info of the selected device

        self.sample_rate: int = 16000 # Hz
        self.channels: int = 1 # Mono
        self.dtype: str = 'int16' # Data type for audio samples

        self.target_device_specifier: Optional[str] = os.environ.get('GOOGLE_MEET_AGENT_AUDIO_DEVICE_NAME_OR_ID')
        logger.info(f"GoogleMeetAgent initialized for user_id: {self.user_id}. Sounddevice available: {SOUNDDEVICE_AVAILABLE}. Target device spec: '{self.target_device_specifier}'")

    def join_meeting(self, meeting_url: str) -> bool:
        """
        Attempts to join a Google Meet meeting by launching the browser with the URL.
        """
        if not meeting_url or not meeting_url.startswith("https://meet.google.com/"):
            logger.error(f"GoogleMeetAgent: Invalid Google Meet URL format: {meeting_url}")
            return False

        self.current_meeting_url = meeting_url
        logger.info(f"GoogleMeetAgent ({self.user_id}): Attempting to join Google Meet: {self.current_meeting_url}")

        try:
            system = platform.system()
            if system == "Windows": os.startfile(self.current_meeting_url)
            elif system == "Darwin": subprocess.Popen(['open', self.current_meeting_url])
            else: subprocess.Popen(['xdg-open', self.current_meeting_url])

            logger.info(f"GoogleMeetAgent ({self.user_id}): Launched browser for Google Meet: {self.current_meeting_url}. User may need to interact with browser.")
            return True
        except Exception as e:
            logger.error(f"GoogleMeetAgent ({self.user_id}): Failed to launch browser for Google Meet {self.current_meeting_url}. Error: {e}")
            self.current_meeting_url = None
            return False

    def _sd_callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags):
        """Sounddevice callback. Puts audio data into the asyncio queue."""
        if status: logger.warning(f"Sounddevice callback status: {status}")
        if self.is_capturing:
            try: self.audio_queue.put_nowait(bytes(indata))
            except asyncio.QueueFull: logger.warning("GoogleMeetAgent: Audio queue full, dropping audio frame.")
            except Exception as e: logger.error(f"GoogleMeetAgent: Error in _sd_callback queueing audio: {e}")


    async def start_audio_capture(self, meeting_url_to_confirm: str) -> AsyncIterator[bytes]:
        """
        Starts capturing audio from the configured/default input device.

        Audio Device Selection uses `GOOGLE_MEET_AGENT_AUDIO_DEVICE_NAME_OR_ID` env var.
        See class docstring for crucial notes on system audio routing for capturing meeting output.

        Raises:
            ValueError: If meeting URL mismatch, or specified/default audio device is not found/unsuitable.
            RuntimeError: If audio stream fails to open or capture is already active.
        """
        if not SOUNDDEVICE_AVAILABLE:
            logger.error("GoogleMeetAgent: Sounddevice not available. Cannot start real audio capture.")
            if False: yield b'' # Ensure async generator type hint even if it does nothing.
            return

        if self.current_meeting_url != meeting_url_to_confirm:
            msg = f"GoogleMeetAgent: Meeting URL mismatch. Current: '{self.current_meeting_url}', requested for capture: '{meeting_url_to_confirm}'."
            logger.error(msg); raise ValueError(msg)

        if self.is_capturing or self.audio_stream:
            msg = f"GoogleMeetAgent: Audio capture is already active for meeting {self.current_meeting_url}."
            logger.error(msg); raise RuntimeError(msg)

        # --- Device Selection Logic ---
        chosen_device_info = None
        device_id_for_stream = None
        device_name_for_log = "Unknown"
        try:
            devices = sd.query_devices()
            host_api_names = [api['name'] for api in sd.query_hostapis()]

            if self.target_device_specifier:
                logger.info(f"Attempting to use specified audio device: '{self.target_device_specifier}'")
                try:
                    dev_idx = int(self.target_device_specifier)
                    if 0 <= dev_idx < len(devices): chosen_device_info = devices[dev_idx]
                except ValueError:
                    for dev in devices:
                        if self.target_device_specifier.lower() in dev.get('name', '').lower() and dev.get('max_input_channels', 0) > 0:
                            chosen_device_info = dev; break
                if not chosen_device_info or chosen_device_info.get('max_input_channels', 0) == 0:
                    msg = f"Specified audio device '{self.target_device_specifier}' not found or not an input device."
                    logger.error(f"{msg} Available devices: {devices}"); raise ValueError(msg)
            else:
                logger.warning("*************************************************************************************")
                logger.warning("WARNING: GOOGLE_MEET_AGENT_AUDIO_DEVICE_NAME_OR_ID not set. Using system default input.")
                logger.warning("This will capture microphone. For Google Meet audio output, configure system audio routing.")
                logger.warning("See agent documentation (Stereo Mix, BlackHole, VB-Cable).")
                logger.warning("*************************************************************************************")
                default_input_idx = sd.default.device[0]
                if default_input_idx == -1 or default_input_idx >= len(devices) or devices[default_input_idx].get('max_input_channels', 0) == 0:
                    msg = "No suitable default audio input device found."
                    logger.error(f"{msg} Default input index: {default_input_idx}. Available: {devices}"); raise ValueError(msg)
                chosen_device_info = devices[default_input_idx]

            if not chosen_device_info: raise ValueError("Could not determine a suitable audio input device.")

            self.selected_audio_device_info = chosen_device_info
            device_id_for_stream = chosen_device_info['index']
            device_name_for_log = chosen_device_info.get('name', f"Index {device_id_for_stream}")
            host_api_idx = chosen_device_info.get('hostapi', -1)
            host_api_name = host_api_names[host_api_idx] if 0 <= host_api_idx < len(host_api_names) else "UnknownAPI"
            logger.info(f"Selected audio device: '{device_name_for_log}' (Index: {device_id_for_stream}, HostAPI: {host_api_name}, MaxInputChannels: {chosen_device_info.get('max_input_channels')})")
        except Exception as e:
            msg = f"GoogleMeetAgent: Error selecting audio device: {e}"; logger.error(msg, exc_info=True); raise ValueError(msg)
        # --- End Device Selection ---

        self.is_capturing = True
        while not self.audio_queue.empty(): self.audio_queue.get_nowait(); self.audio_queue.task_done()

        logger.info(f"GoogleMeetAgent ({self.user_id}): Starting audio capture stream for meet {self.current_meeting_url} on device '{device_name_for_log}'...")
        try:
            # Fixed stream parameters
            samplerate = 16000; channels = 1; dtype = 'int16'
            blocksize = int(samplerate * 0.04) # 40ms chunks (640 frames at 16kHz) - Deepgram prefers 20-40ms.

            self.audio_stream = sd.RawInputStream(
                samplerate=samplerate, channels=channels, dtype=dtype,
                device=device_id_for_stream, callback=self._sd_callback, blocksize=blocksize
            )
            self.audio_stream.start()
            logger.info(f"Audio stream active. Device: '{device_name_for_log}', Samplerate: {self.audio_stream.samplerate} Hz, Channels: {self.audio_stream.channels}")

            while self.is_capturing or not self.audio_queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                    if chunk is None: self.audio_queue.task_done(); break
                    yield chunk
                    self.audio_queue.task_done()
                except asyncio.TimeoutError:
                    if not self.is_capturing and self.audio_queue.empty(): break
                    continue

        except sd.PortAudioError as e:
            msg = f"PortAudioError opening audio stream on device '{device_name_for_log}': {e}"
            logger.error(msg, exc_info=True); self.is_capturing = False; self.audio_stream = None; raise RuntimeError(msg)
        except Exception as e:
            msg = f"Error during audio stream for {self.current_meeting_url} on '{device_name_for_log}': {e}"
            logger.error(msg, exc_info=True); self.is_capturing = False; self.audio_stream = None; raise RuntimeError(msg)
        finally:
            logger.info(f"Cleaning up audio stream for {self.current_meeting_url} (Device: '{device_name_for_log}').")
            if self.audio_stream:
                if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
                logger.info("Sounddevice stream stopped and closed.")
            self.audio_stream = None; self.is_capturing = False
            if self.audio_queue.empty(): self.audio_queue.put_nowait(None)


    async def stop_audio_capture(self) -> None:
        """Stops the active audio capture stream."""
        if not self.is_capturing and not self.audio_stream:
            logger.info(f"GoogleMeetAgent ({self.user_id}): Audio capture not active.")
            return
        logger.info(f"GoogleMeetAgent ({self.user_id}): Stopping audio capture for {self.current_meeting_url}...")
        self.is_capturing = False
        if self.audio_stream:
            if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
            self.audio_stream = None
            logger.info("Sounddevice stream explicitly stopped/closed via stop_audio_capture.")
        try: self.audio_queue.put_nowait(None)
        except asyncio.QueueFull: logger.warning("Audio queue full sending stop sentinel.")
        logger.info(f"GoogleMeetAgent ({self.user_id}): Audio capture stopped signal sent.")

    async def leave_meeting(self) -> None:
        """Stops audio capture and logs leaving the current Google Meet."""
        logger.info(f"GoogleMeetAgent ({self.user_id}): Leaving meeting {self.current_meeting_url}...")
        if self.is_capturing or self.audio_stream:
            logger.info(f"Audio capture active, stopping it first for {self.current_meeting_url}.")
            await self.stop_audio_capture()

        # Note: Unlike Zoom, Google Meet runs in a browser tab. Closing it programmatically
        # is highly complex and browser/OS-dependent (e.g., requires browser extensions or UI automation).
        # For this agent, "leaving" means stopping interaction and resetting state.
        logger.info(f"GoogleMeetAgent ({self.user_id}): Left meeting {self.current_meeting_url}. Browser tab may still be open.")
        self.current_meeting_url = None
        self.selected_audio_device_info = None # Reset selected device info

    def get_current_meeting_id(self) -> Optional[str]:
        """Returns the current meeting URL (which serves as its ID for Google Meet)."""
        return self.current_meeting_url

[end of atomic-docker/project/functions/agents/google_meet_agent.py]
