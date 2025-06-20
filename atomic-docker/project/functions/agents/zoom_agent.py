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
            logger.error("ZoomAgent: Sounddevice not available. Cannot start real audio capture.")
            if False: yield b'' ; return

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
            if not all_devices: raise ValueError("No audio devices found by sounddevice.")
            host_api_names = [api.get('name', 'UnknownAPI') for api in sd.query_hostapis()]

            if self.target_device_specifier:
                logger.info(f"Attempting to use specified audio device: '{self.target_device_specifier}'")
                try:
                    dev_idx = int(self.target_device_specifier)
                    if 0 <= dev_idx < len(all_devices): self.selected_audio_device_info = all_devices[dev_idx]
                except ValueError:
                    for dev in all_devices:
                        if self.target_device_specifier.lower() in dev.get('name', '').lower() and dev.get('max_input_channels', 0) > 0:
                            self.selected_audio_device_info = dev; break
                if not self.selected_audio_device_info or self.selected_audio_device_info.get('max_input_channels', 0) == 0:
                    msg = f"Specified audio device '{self.target_device_specifier}' not found or not an input device."
                    logger.error(f"{msg} Available: {all_devices}"); raise ValueError(msg)

            elif sys.platform.startswith('linux') and _get_linux_app_monitor_source is not None:
                logger.info("Linux platform: Attempting to auto-detect Zoom audio monitor source via pactl...")
                monitor_name_from_pactl = _get_linux_app_monitor_source(self.target_linux_process_names, logger)
                if monitor_name_from_pactl:
                    found_device_info = next((d for d in all_devices if monitor_name_from_pactl == d['name'] and d['max_input_channels'] > 0), None)
                    if found_device_info:
                        self.selected_audio_device_info = found_device_info
                        logger.info(f"Auto-detected and validated Linux monitor source: '{self.selected_audio_device_info['name']}'")
                    else:
                        logger.warning(f"Auto-detected monitor source '{monitor_name_from_pactl}' not found/valid via sounddevice. Falling back.")
                else:
                    logger.info("Could not auto-detect Zoom audio monitor source. Falling back.")

            if not self.selected_audio_device_info: # Fallback to default if no specifier or auto-detection failed
                logger.warning("*************************************************************************************")
                logger.warning("WARNING: Using system default input device. This will typically capture microphone audio.")
                logger.warning("For Zoom meeting audio output, ensure system audio is routed to this default input")
                logger.warning("(e.g., via Stereo Mix, Loopback software like BlackHole/VB-Cable). See agent docs.")
                logger.warning("*************************************************************************************")
                default_input_idx = sd.default.device[0]
                if default_input_idx == -1 or default_input_idx >= len(all_devices) or all_devices[default_input_idx].get('max_input_channels', 0) == 0:
                    msg = "No suitable default audio input device found."
                    logger.error(f"{msg} Default idx: {default_input_idx}. Available: {all_devices}"); raise ValueError(msg)
                self.selected_audio_device_info = all_devices[default_input_idx]

            if not self.selected_audio_device_info: raise ValueError("Audio device selection failed.") # Should be caught by earlier checks

            device_id_for_stream = self.selected_audio_device_info['index']
            device_name_for_log = self.selected_audio_device_info.get('name', f"Index {device_id_for_stream}")
            host_api_idx = self.selected_audio_device_info.get('hostapi', -1)
            host_api_name = host_api_names[host_api_idx] if 0 <= host_api_idx < len(host_api_names) else "UnknownAPI"
            logger.info(f"ZoomAgent: Final selected audio device: '{device_name_for_log}' (Index: {device_id_for_stream}, HostAPI: {host_api_name}, MaxInputChannels: {self.selected_audio_device_info.get('max_input_channels')})")

        except Exception as e:
            msg = f"ZoomAgent: Fatal error during audio device selection: {e}"; logger.error(msg, exc_info=True); raise ValueError(msg)

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
