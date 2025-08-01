import asyncio
import os
import subprocess
import sys
import logging
import platform
from typing import Optional, AsyncIterator, Dict, Any, List

# Initialize logger for this module
logger = logging.getLogger(__name__)
if not logger.handlers: # Avoid duplicate handlers if module is reloaded
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Attempt to import sounddevice, but make it optional
try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice library not found. Real audio capture will not be available for MSTeamsAgent.")
    class DummySoundDevice:
        def __init__(self): pass
        def RawInputStream(self, *args, **kwargs): raise NotImplementedError("sounddevice not available")
        def query_devices(self, *args, **kwargs) -> list: return []
        def get_hostapi_info(self, *args, **kwargs) -> Dict[str, Any]: return {}
        class PortAudioError(Exception): pass
        class CallbackFlags(int): pass
    sd = DummySoundDevice()

# Import the new Linux audio utility
try:
    from ._linux_audio_utils import _get_linux_app_monitor_source
except ImportError:
    if sys.platform.startswith('linux'):
        logger.warning("Could not import _linux_audio_utils. Linux app audio auto-detection will be skipped for MSTeamsAgent.")
    _get_linux_app_monitor_source = None

# --- Custom Exceptions ---
class SoundDeviceError(Exception):
    """Base class for sound device related errors in this agent."""
    pass

class SoundDeviceNotAvailableError(SoundDeviceError):
    """Raised when the sounddevice library is not available or fails to initialize."""
    pass

class AudioDeviceSelectionError(SoundDeviceError):
    """Raised when a suitable audio input device cannot be selected."""
    pass
# --- End Custom Exceptions ---

class MSTeamsAgent:
    """
    MSTeamsAgent aims to interact with Microsoft Teams meetings. Its primary functionalities include:
    1. Launching/Joining MS Teams meetings using system-level URL handlers.
    2. Capturing audio from a specified or default system audio input device.
       On Linux, it can attempt to auto-detect the correct monitor source for Teams audio if pactl is available.

    IMPORTANT AUDIO CAPTURE NOTE:
    (Same detailed explanation as ZoomAgent/GoogleMeetAgent about system audio routing and `MS_TEAMS_AGENT_AUDIO_DEVICE_NAME_OR_ID`)
    - Linux Auto-Detection: If no device is specified, the agent will try to find the audio output
      monitor source associated with MS Teams (desktop app: 'teams', 'ms-teams'; or common browsers) using `pactl`.
    """
    def __init__(self, user_id: str, target_device_specifier_override: Optional[str] = None):
        self.user_id: str = user_id
        self.current_meeting_url: Optional[str] = None
        self.audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.is_capturing: bool = False
        self.audio_stream: Optional[sd.RawInputStream] = None
        self.selected_audio_device_info: Optional[Dict[str, Any]] = None

        self.sample_rate: int = 16000
        self.channels: int = 1
        self.dtype: str = 'int16'
        self.blocksize: int = int(self.sample_rate * 0.04) # 40ms

        self.target_device_specifier: Optional[str] = target_device_specifier_override or os.environ.get('MS_TEAMS_AGENT_AUDIO_DEVICE_NAME_OR_ID')
        self.target_linux_process_names: List[str] = ['teams', 'ms-teams', 'chrome', 'firefox', 'msedge', 'chromium', 'opera', 'brave']

        logger.info(f"MSTeamsAgent initialized for user_id: {self.user_id}. Sounddevice: {SOUNDDEVICE_AVAILABLE}. Device spec: '{self.target_device_specifier}' (Override: '{target_device_specifier_override}')")

    def join_meeting(self, meeting_url: str) -> bool:
        if not meeting_url or not meeting_url.startswith("https://teams.microsoft.com/l/meetup-join/"):
            logger.error(f"MSTeamsAgent: Invalid MS Teams URL: {meeting_url}")
            return False
        self.current_meeting_url = meeting_url
        logger.info(f"MSTeamsAgent ({self.user_id}): Joining MS Teams meeting: {self.current_meeting_url}")
        try:
            system = platform.system()
            if system == "Windows": os.startfile(self.current_meeting_url)
            elif system == "Darwin": subprocess.Popen(['open', self.current_meeting_url])
            else: subprocess.Popen(['xdg-open', self.current_meeting_url])
            logger.info(f"Launched MS Teams client/browser for meeting: {self.current_meeting_url}.")
            return True
        except Exception as e:
            logger.error(f"Failed to launch MS Teams for {self.current_meeting_url}: {e}", exc_info=True)
            self.current_meeting_url = None; return False

    def _sd_callback(self, indata: np.ndarray, frames: int, time_info: Any, status_flags: sd.CallbackFlags):
        if status_flags: logger.warning(f"Sounddevice callback status flags: {status_flags}")
        if self.is_capturing:
            try: self.audio_queue.put_nowait(bytes(indata))
            except asyncio.QueueFull: logger.warning("MSTeamsAgent: Audio queue full, frame dropped.")
            except Exception as e: logger.error(f"MSTeamsAgent: Error in _sd_callback: {e}", exc_info=True)

    async def start_audio_capture(self, meeting_url_to_confirm: str) -> AsyncIterator[bytes]:
        if not SOUNDDEVICE_AVAILABLE:
            err_msg = "MSTeamsAgent: sounddevice library is not available or failed to initialize. Cannot start audio capture."
            logger.critical(err_msg)
            raise SoundDeviceNotAvailableError(err_msg)

        if self.current_meeting_url != meeting_url_to_confirm:
            msg = f"MSTeamsAgent: Meeting URL mismatch. Current: '{self.current_meeting_url}', requested: '{meeting_url_to_confirm}'.";
            logger.error(msg); raise ValueError(msg)

        if self.is_capturing or self.audio_stream:
            msg = f"Audio capture already active for {self.current_meeting_url}.";
            logger.error(msg); raise RuntimeError(msg)

        self.selected_audio_device_info = None; device_id_for_stream = None; device_name_for_log = "Unknown"
        try:
            all_devices = sd.query_devices()
            if not all_devices:
                err_msg = "MSTeamsAgent: No audio devices found by sounddevice."
                logger.error(err_msg)
                raise AudioDeviceSelectionError(err_msg)
            host_api_names = [api.get('name', 'UnknownAPI') for api in sd.query_hostapis()]

            if self.target_device_specifier:
                logger.info(f"MSTeamsAgent: Attempting to use specified audio device: '{self.target_device_specifier}'")
                try:
                    dev_idx = int(self.target_device_specifier)
                    if 0 <= dev_idx < len(all_devices):
                        candidate_device = all_devices[dev_idx]
                        if candidate_device.get('max_input_channels', 0) > 0:
                            self.selected_audio_device_info = candidate_device
                        else:
                            logger.warning(f"MSTeamsAgent: Device at index {dev_idx} ('{candidate_device.get('name')}') is not an input device. Max input channels: {candidate_device.get('max_input_channels', 0)}.")
                    else:
                        logger.warning(f"MSTeamsAgent: Specified device index {dev_idx} is out of range (0-{len(all_devices)-1}).")
                except ValueError:
                    for dev in all_devices:
                        if self.target_device_specifier.lower() in dev.get('name', '').lower() and dev.get('max_input_channels', 0) > 0:
                            self.selected_audio_device_info = dev
                            logger.info(f"MSTeamsAgent: Matched specified name to input device: '{dev.get('name')}'")
                            break

                if not self.selected_audio_device_info:
                    err_msg = f"MSTeamsAgent: Specified audio device '{self.target_device_specifier}' not found as a valid input device."
                    detailed_device_list = "\n".join([f"  - Index {i}: {d.get('name')} (Inputs: {d.get('max_input_channels',0)})" for i,d in enumerate(all_devices)])
                    logger.error(f"{err_msg}\nAvailable devices:\n{detailed_device_list}")
                    raise AudioDeviceSelectionError(err_msg)

            elif sys.platform.startswith('linux') and _get_linux_app_monitor_source:
                logger.info(f"MSTeamsAgent (Linux): Attempting auto-detect for MS Teams (app/browser): {self.target_linux_process_names}")
                monitor_name = _get_linux_app_monitor_source(self.target_linux_process_names, logger)
                if monitor_name:
                    found_device_info = next((d for d in all_devices if monitor_name == d['name'] and d.get('max_input_channels',0)>0), None)
                    if found_device_info:
                        self.selected_audio_device_info = found_device_info
                        logger.info(f"MSTeamsAgent (Linux): Auto-detected and validated monitor source: '{self.selected_audio_device_info['name']}'")
                    else:
                        logger.warning(f"MSTeamsAgent (Linux): Auto-detected monitor source '{monitor_name}' not found or not a valid input device via sounddevice. Falling back to default device.")
                else:
                    logger.info("MSTeamsAgent (Linux): Could not auto-detect MS Teams audio monitor source. Falling back to default device.")

            if not self.selected_audio_device_info: # Fallback to default
                logger.warning("*************************************************************************************")
                logger.warning("MSTeamsAgent: WARNING: Using system default input device. This typically captures MICROPHONE audio.")
                logger.warning("For capturing MS Teams AUDIO OUTPUT, ensure system audio (what you hear) is routed")
                logger.warning("to this default input (e.g., via 'Stereo Mix' on Windows, or Loopback software).")
                logger.warning("*************************************************************************************")
                try:
                    default_input_device = sd.query_devices(kind='input')
                except ValueError as e:
                     logger.warning(f"MSTeamsAgent: Could not query default input device directly ({e}). Checking all default devices.")
                     default_input_idx = sd.default.device[0]
                     if default_input_idx != -1 and default_input_idx < len(all_devices) and all_devices[default_input_idx].get('max_input_channels', 0) > 0:
                         default_input_device = all_devices[default_input_idx]
                     else: default_input_device = None

                if not default_input_device or default_input_device.get('max_input_channels', 0) == 0:
                    err_msg = "MSTeamsAgent: No suitable default audio input device found or default device is not an input device."
                    detailed_device_list = "\n".join([f"  - Index {i}: {d.get('name')} (Inputs: {d.get('max_input_channels',0)})" for i,d in enumerate(all_devices)])
                    logger.error(f"{err_msg}\nDefault device query result: {default_input_device}\nAvailable devices:\n{detailed_device_list}")
                    raise AudioDeviceSelectionError(err_msg)
                self.selected_audio_device_info = default_input_device
                logger.info(f"MSTeamsAgent: Successfully selected default input device: '{self.selected_audio_device_info.get('name')}'")


            if not self.selected_audio_device_info:
                err_msg = "MSTeamsAgent: Audio device selection process failed unexpectedly."
                logger.error(err_msg)
                raise AudioDeviceSelectionError(err_msg)

            device_id_for_stream = self.selected_audio_device_info['index']
            device_name_for_log = self.selected_audio_device_info.get('name', f"Index {device_id_for_stream}")
            host_api_idx = self.selected_audio_device_info.get('hostapi',-1); host_api_name = host_api_names[host_api_idx] if 0<=host_api_idx<len(host_api_names) else "N/A"
            logger.info(f"MSTeamsAgent: Final selected audio device for capture: '{device_name_for_log}' (Sounddevice Index: {device_id_for_stream}, HostAPI: {host_api_name}, Inputs: {self.selected_audio_device_info.get('max_input_channels')})")
        except AudioDeviceSelectionError: raise
        except SoundDeviceNotAvailableError: raise
        except Exception as e:
            err_msg = f"MSTeamsAgent: An unexpected error occurred during audio device selection: {e}"
            logger.error(err_msg, exc_info=True)
            raise AudioDeviceSelectionError(err_msg)

        self.is_capturing = True
        while not self.audio_queue.empty(): self.audio_queue.get_nowait(); self.audio_queue.task_done()
        logger.info(f"MSTeamsAgent ({self.user_id}): Starting audio stream for {self.current_meeting_url} on '{device_name_for_log}'...")
        try:
            self.audio_stream = sd.RawInputStream(
                samplerate=self.sample_rate, device=device_id_for_stream, channels=self.channels,
                dtype=self.dtype, callback=self._sd_callback, blocksize=self.blocksize )
            self.audio_stream.start()
            logger.info(f"Audio stream active: '{device_name_for_log}', Rate: {self.audio_stream.samplerate}Hz")
            while self.is_capturing or not self.audio_queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                    if chunk is None: self.audio_queue.task_done(); break
                    yield chunk; self.audio_queue.task_done()
                except asyncio.TimeoutError:
                    if not self.is_capturing and self.audio_queue.empty(): break
                    continue
        except sd.PortAudioError as e:
            msg = f"PortAudioError on '{device_name_for_log}': {e}"; logger.error(msg, exc_info=True); self.is_capturing=False; self.audio_stream=None; raise RuntimeError(msg)
        except Exception as e:
            msg = f"Stream error for {self.current_meeting_url} on '{device_name_for_log}': {e}"; logger.error(msg, exc_info=True); self.is_capturing=False; self.audio_stream=None; raise RuntimeError(msg)
        finally:
            logger.info(f"Cleaning up audio stream for {self.current_meeting_url} (Device: '{device_name_for_log}').")
            if self.audio_stream:
                if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
                logger.info("Sounddevice stream stopped/closed.")
            self.audio_stream = None; self.is_capturing = False
            if self.audio_queue.empty(): self.audio_queue.put_nowait(None)

    async def stop_audio_capture(self) -> None:
        if not self.is_capturing and not self.audio_stream: logger.info(f"MSTeamsAgent ({self.user_id}): Capture not active."); return
        logger.info(f"MSTeamsAgent ({self.user_id}): Stopping capture for {self.current_meeting_url}...")
        self.is_capturing = False
        if self.audio_stream:
            if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
            self.audio_stream = None; logger.info("Sounddevice stream stopped/closed via stop_audio_capture.")
        try: self.audio_queue.put_nowait(None)
        except asyncio.QueueFull: logger.warning("Audio queue full on stop sentinel.")
        logger.info(f"MSTeamsAgent ({self.user_id}): Capture stop signal sent.")

    async def leave_meeting(self) -> None:
        logger.info(f"MSTeamsAgent ({self.user_id}): Leaving {self.current_meeting_url}...")
        if self.is_capturing or self.audio_stream:
            logger.info(f"Audio capture active, stopping for {self.current_meeting_url}.")
            await self.stop_audio_capture()
        logger.info(f"MSTeamsAgent ({self.user_id}): Left {self.current_meeting_url}. MS Teams app/tab may remain open.")
        self.current_meeting_url = None; self.selected_audio_device_info = None

    def get_current_meeting_id(self) -> Optional[str]: return self.current_meeting_url

[end of atomic-docker/project/functions/agents/ms_teams_agent.py]
