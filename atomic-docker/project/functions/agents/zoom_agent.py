import asyncio
import subprocess
import platform
import os
import re
import sys
import logging # Added logging
from typing import Optional, AsyncIterator, Dict, Any, List

# Attempt to import sounddevice, but make it optional
try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    # Use logging for warnings consistently
    logging.warning("sounddevice library not found. Real audio capture will not be available for ZoomAgent.")
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
except ImportError: # Handle if run standalone or path issues
    if sys.platform.startswith('linux'):
        logging.warning("Could not import _linux_audio_utils. Linux app audio auto-detection will be skipped.")
    _get_linux_app_monitor_source = None


logger = logging.getLogger(__name__) # Initialize logger for this module

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

class ZoomAgent:
    """
    ZoomAgent aims to interact with Zoom meetings. Its primary functionalities include:
    1. Launching/Joining Zoom meetings using system-level URL handlers.
    2. Capturing audio from a specified or default system audio input device.
       On Linux, it can attempt to auto-detect the correct monitor source for Zoom if pactl is available.

    IMPORTANT AUDIO CAPTURE NOTE:
    By default, this agent will capture audio from the system's default microphone.
    To capture the actual meeting audio (i.e., what you hear from other participants),
    you MUST configure your system's audio routing. This typically involves:
    - Windows: Enabling "Stereo Mix" as an input device and setting it as default, or using a virtual audio cable.
    - macOS/Linux: Using software like BlackHole, LoopBeAudio, VB-Cable, or PulseAudio loopback module
      to route application output (Zoom's audio) to a virtual input device, then configuring this
      agent to use that virtual input device via the `ZOOM_AGENT_AUDIO_DEVICE_NAME_OR_ID` environment variable.
    - Linux Auto-Detection: If no device is specified via environment variable, the agent will attempt
      to find Zoom's audio output monitor source using `pactl`. This is experimental and requires `pactl`.
    Without proper audio routing or successful auto-detection, this agent will only capture microphone input.
    """
    def __init__(self, user_id: str, target_device_specifier_override: Optional[str] = None):
        self.user_id: str = user_id
        self.current_meeting_id: Optional[str] = None
        self.audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.is_capturing: bool = False
        self.audio_stream: Optional[sd.RawInputStream] = None
        self.selected_audio_device_info: Optional[Dict[str, Any]] = None

        self.sample_rate: int = 16000
        self.channels: int = 1
        self.dtype: str = 'int16'

        self.target_device_specifier: Optional[str] = target_device_specifier_override or os.environ.get('ZOOM_AGENT_AUDIO_DEVICE_NAME_OR_ID')
        # For Linux auto-detection: list of process names associated with Zoom
        self.target_linux_process_names: List[str] = ['zoom', 'Zoom Meetings']

        logger.info(f"ZoomAgent initialized for user_id: {self.user_id}. Sounddevice available: {SOUNDDEVICE_AVAILABLE}. Target device spec: '{self.target_device_specifier}' (Override was: '{target_device_specifier_override}')")

    def _parse_meeting_id(self, meeting_url_or_id: str) -> Optional[str]:
        if "zoom.us/j/" in meeting_url_or_id:
            match = re.search(r'zoom.us/j/(\d+)', meeting_url_or_id)
            return match.group(1) if match else None
        elif meeting_url_or_id.replace(" ", "").isdigit() and len(meeting_url_or_id.replace(" ", "")) > 8:
            return meeting_url_or_id.replace(" ", "")
        logger.warning(f"ZoomAgent: Could not parse meeting ID from: {meeting_url_or_id}")
        return None

    def join_meeting(self, meeting_url_or_id: str, meeting_password: Optional[str] = None) -> bool:
        parsed_meeting_id = self._parse_meeting_id(meeting_url_or_id)
        if not parsed_meeting_id:
            logger.error(f"ZoomAgent: Invalid meeting ID or URL format provided: {meeting_url_or_id}")
            return False
        logger.info(f"ZoomAgent ({self.user_id}): Attempting to join Zoom meeting: {parsed_meeting_id}")
        zoom_url = f"zoommtg://zoom.us/join?confno={parsed_meeting_id}"
        if meeting_password: zoom_url += f"&pwd={meeting_password}"
        try:
            system = platform.system()
            if system == "Windows": os.startfile(zoom_url)
            elif system == "Darwin": subprocess.Popen(['open', zoom_url])
            else: subprocess.Popen(['xdg-open', zoom_url])
            self.current_meeting_id = parsed_meeting_id
            logger.info(f"ZoomAgent ({self.user_id}): Launched Zoom client for meeting: {self.current_meeting_id}. Manual interaction may be required.")
            return True
        except Exception as e:
            logger.error(f"ZoomAgent ({self.user_id}): Failed to launch Zoom client for meeting {parsed_meeting_id}. Error: {e}", exc_info=True)
            self.current_meeting_id = None; return False

    def _sd_callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags):
        if status: logger.warning(f"Sounddevice callback status: {status}")
        if self.is_capturing:
            try: self.audio_queue.put_nowait(bytes(indata))
            except asyncio.QueueFull: logger.warning("ZoomAgent: Audio queue full, dropping frame.")
            except Exception as e: logger.error(f"ZoomAgent: Error in _sd_callback: {e}", exc_info=True)


    async def start_audio_capture(self, meeting_id_to_confirm: str) -> AsyncIterator[bytes]:
        if not SOUNDDEVICE_AVAILABLE:
            err_msg = "ZoomAgent: sounddevice library is not available or failed to initialize. Cannot start audio capture."
            logger.critical(err_msg) # Changed to critical
            raise SoundDeviceNotAvailableError(err_msg)

        if self.current_meeting_id != meeting_id_to_confirm:
            msg = f"ZoomAgent: Meeting ID mismatch. Current: '{self.current_meeting_id}', requested: '{meeting_id_to_confirm}'."
            logger.error(msg); raise ValueError(msg)

        if self.is_capturing or self.audio_stream:
            msg = f"ZoomAgent: Audio capture already active for meeting {self.current_meeting_id}."
            logger.error(msg); raise RuntimeError(msg)

        self.selected_audio_device_info = None # Reset
        device_id_for_stream = None
        device_name_for_log = "Unknown"

        try:
            all_devices = sd.query_devices()
            if not all_devices:
                err_msg = "ZoomAgent: No audio devices found by sounddevice."
                logger.error(err_msg)
                raise AudioDeviceSelectionError(err_msg)
            host_api_names = [api.get('name', 'UnknownAPI') for api in sd.query_hostapis()]

            if self.target_device_specifier:
                logger.info(f"ZoomAgent: Attempting to use specified audio device: '{self.target_device_specifier}'")
                try:
                    # Try interpreting as an index first
                    dev_idx = int(self.target_device_specifier)
                    if 0 <= dev_idx < len(all_devices):
                        candidate_device = all_devices[dev_idx]
                        if candidate_device.get('max_input_channels', 0) > 0:
                            self.selected_audio_device_info = candidate_device
                        else:
                            logger.warning(f"ZoomAgent: Device at index {dev_idx} ('{candidate_device.get('name')}') is not an input device. Max input channels: {candidate_device.get('max_input_channels', 0)}.")
                    else:
                        logger.warning(f"ZoomAgent: Specified device index {dev_idx} is out of range (0-{len(all_devices)-1}).")
                except ValueError:
                    # Interpret as a name (substring match)
                    for dev in all_devices:
                        if self.target_device_specifier.lower() in dev.get('name', '').lower() and dev.get('max_input_channels', 0) > 0:
                            self.selected_audio_device_info = dev
                            logger.info(f"ZoomAgent: Matched specified name to input device: '{dev.get('name')}'")
                            break

                if not self.selected_audio_device_info:
                    err_msg = f"ZoomAgent: Specified audio device '{self.target_device_specifier}' not found as a valid input device."
                    detailed_device_list = "\n".join([f"  - Index {i}: {d.get('name')} (Inputs: {d.get('max_input_channels',0)})" for i,d in enumerate(all_devices)])
                    logger.error(f"{err_msg}\nAvailable devices:\n{detailed_device_list}")
                    raise AudioDeviceSelectionError(err_msg)

            elif sys.platform.startswith('linux') and _get_linux_app_monitor_source is not None:
                logger.info("ZoomAgent (Linux): Attempting to auto-detect Zoom audio monitor source via pactl...")
                monitor_name_from_pactl = _get_linux_app_monitor_source(self.target_linux_process_names, logger)
                if monitor_name_from_pactl:
                    found_device_info = next((d for d in all_devices if monitor_name_from_pactl == d['name'] and d['max_input_channels'] > 0), None)
                    if found_device_info:
                        self.selected_audio_device_info = found_device_info
                        logger.info(f"ZoomAgent (Linux): Auto-detected and validated monitor source: '{self.selected_audio_device_info['name']}'")
                    else:
                        logger.warning(f"ZoomAgent (Linux): Auto-detected monitor source '{monitor_name_from_pactl}' not found or not a valid input device via sounddevice. Falling back to default device.")
                else:
                    logger.info("ZoomAgent (Linux): Could not auto-detect Zoom audio monitor source. Falling back to default device.")

            if not self.selected_audio_device_info: # Fallback to default if no specifier or auto-detection failed/skipped
                logger.warning("*************************************************************************************")
                logger.warning("ZoomAgent: WARNING: Using system default input device. This will typically capture MICROPHONE audio.")
                logger.warning("For capturing Zoom meeting AUDIO OUTPUT, ensure system audio (what you hear) is routed")
                logger.warning("to this default input (e.g., via 'Stereo Mix' on Windows, or Loopback software like")
                logger.warning("BlackHole/VB-Cable on macOS/Linux). Refer to agent documentation for details.")
                logger.warning("*************************************************************************************")

                try:
                    default_input_device = sd.query_devices(kind='input')
                except ValueError as e: # Handle cases where kind='input' might not be supported by dummy sd or older versions
                     logger.warning(f"ZoomAgent: Could not query default input device directly ({e}). Checking all default devices.")
                     default_input_idx = sd.default.device[0] # Index for default input
                     if default_input_idx != -1 and default_input_idx < len(all_devices) and all_devices[default_input_idx].get('max_input_channels', 0) > 0:
                         default_input_device = all_devices[default_input_idx]
                     else: default_input_device = None

                if not default_input_device or default_input_device.get('max_input_channels', 0) == 0:
                    err_msg = "ZoomAgent: No suitable default audio input device found or default device is not an input device."
                    detailed_device_list = "\n".join([f"  - Index {i}: {d.get('name')} (Inputs: {d.get('max_input_channels',0)})" for i,d in enumerate(all_devices)])
                    logger.error(f"{err_msg}\nDefault device query result: {default_input_device}\nAvailable devices:\n{detailed_device_list}")
                    raise AudioDeviceSelectionError(err_msg)
                self.selected_audio_device_info = default_input_device
                logger.info(f"ZoomAgent: Successfully selected default input device: '{self.selected_audio_device_info.get('name')}'")


            # Final check, though previous logic should ensure this
            if not self.selected_audio_device_info:
                # This case should ideally be unreachable if logic above is correct
                err_msg = "ZoomAgent: Audio device selection process failed unexpectedly."
                logger.error(err_msg)
                raise AudioDeviceSelectionError(err_msg)

            device_id_for_stream = self.selected_audio_device_info['index'] # sd.query_devices() adds 'index'
            device_name_for_log = self.selected_audio_device_info.get('name', f"Index {device_id_for_stream}")
            host_api_idx = self.selected_audio_device_info.get('hostapi', -1)
            host_api_name = host_api_names[host_api_idx] if 0 <= host_api_idx < len(host_api_names) else "UnknownAPI"
            logger.info(f"ZoomAgent: Final selected audio device for capture: '{device_name_for_log}' (Sounddevice Index: {device_id_for_stream}, HostAPI: {host_api_name}, MaxInputChannels: {self.selected_audio_device_info.get('max_input_channels')})")

        except AudioDeviceSelectionError: # Re-raise specific errors
            raise
        except SoundDeviceNotAvailableError: # Re-raise specific errors
             raise
        except Exception as e: # Catch other unexpected errors during selection
            err_msg = f"ZoomAgent: An unexpected error occurred during audio device selection: {e}"
            logger.error(err_msg, exc_info=True)
            raise AudioDeviceSelectionError(err_msg) # Wrap in our specific error type

        self.is_capturing = True
        while not self.audio_queue.empty(): self.audio_queue.get_nowait(); self.audio_queue.task_done()

        logger.info(f"ZoomAgent ({self.user_id}): Starting audio capture stream for meeting {self.current_meeting_id} on device '{device_name_for_log}'...")
        try:
            self.audio_stream = sd.RawInputStream(
                samplerate=self.sample_rate, channels=self.channels, dtype=self.dtype,
                device=device_id_for_stream, callback=self._sd_callback,
                blocksize=int(self.sample_rate * 0.1) # 100ms chunks
            )
            self.audio_stream.start()
            logger.info(f"Audio stream active. Device: '{device_name_for_log}', Samplerate: {self.audio_stream.samplerate} Hz")

            while self.is_capturing or not self.audio_queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.2)
                    if chunk is None: self.audio_queue.task_done(); break
                    yield chunk
                    self.audio_queue.task_done()
                except asyncio.TimeoutError:
                    if not self.is_capturing and self.audio_queue.empty(): break
                    continue

        except sd.PortAudioError as e:
            msg = f"ZoomAgent: PortAudioError on device '{device_name_for_log}': {e}"
            logger.error(msg, exc_info=True); self.is_capturing = False; self.audio_stream = None; raise RuntimeError(msg)
        except Exception as e:
            msg = f"ZoomAgent: Stream error for {self.current_meeting_id} on '{device_name_for_log}': {e}"
            logger.error(msg, exc_info=True); self.is_capturing = False; self.audio_stream = None; raise RuntimeError(msg)
        finally:
            logger.info(f"ZoomAgent: Cleaning up audio stream for {self.current_meeting_id} (Device: '{device_name_for_log}').")
            if self.audio_stream:
                if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
                logger.info("Sounddevice stream stopped/closed.")
            self.audio_stream = None; self.is_capturing = False
            if self.audio_queue.empty(): self.audio_queue.put_nowait(None)

    async def stop_audio_capture(self) -> None:
        if not self.is_capturing and not self.audio_stream:
            logger.info(f"ZoomAgent ({self.user_id}): Audio capture not active.")
            return
        logger.info(f"ZoomAgent ({self.user_id}): Stopping audio capture for {self.current_meeting_id}...")
        self.is_capturing = False
        if self.audio_stream:
            if self.audio_stream.active: self.audio_stream.stop(); self.audio_stream.close()
            self.audio_stream = None
            logger.info("Sounddevice stream explicitly stopped/closed via stop_audio_capture.")
        try: self.audio_queue.put_nowait(None)
        except asyncio.QueueFull: logger.warning("ZoomAgent: Audio queue full sending stop sentinel.")
        logger.info(f"ZoomAgent ({self.user_id}): Audio capture stopped signal sent.")

    async def leave_meeting(self) -> None:
        logger.info(f"ZoomAgent ({self.user_id}): Leaving meeting {self.current_meeting_id}...")
        if self.is_capturing or self.audio_stream:
            logger.info(f"ZoomAgent ({self.user_id}): Audio capture active, stopping it first.")
            await self.stop_audio_capture()
        logger.info(f"ZoomAgent ({self.user_id}): Left meeting {self.current_meeting_id}. (Zoom application may still be open).")
        self.current_meeting_id = None
        self.selected_audio_device_info = None

    def get_current_meeting_id(self) -> Optional[str]: # Added for consistency with other agents
        return self.current_meeting_id

[end of atomic-docker/project/functions/agents/zoom_agent.py]
