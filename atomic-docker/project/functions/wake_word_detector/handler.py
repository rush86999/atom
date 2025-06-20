import os
import struct
import logging
import pyaudio
import pvporcupine
import requests # For HTTP calls to atom-agent
import websockets # For WebSocket connection to audio_processor
import asyncio # For managing WebSocket communication
import threading # For running audio processing in a separate thread
import json
import time
from enum import Enum
import audioop # For basic silence detection (RMS)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# --- Configuration ---
try:
    PICOVOICE_ACCESS_KEY = os.environ["PV_ACCESS_KEY"]
except KeyError:
    logging.error("PV_ACCESS_KEY environment variable not set. Wake word detection will not work.")
    PICOVOICE_ACCESS_KEY = None

AUDIO_PROCESSOR_URL = os.environ.get("AUDIO_PROCESSOR_URL", "ws://localhost:8081")
AUDIO_PROCESSOR_STT_STREAM_PATH = "/stt_stream"
AUDIO_PROCESSOR_WS_URL = f"{AUDIO_PROCESSOR_URL.replace('http://', 'ws://').replace('https://', 'wss://')}{AUDIO_PROCESSOR_STT_STREAM_PATH}"

ATOM_AGENT_URL = os.environ.get("ATOM_AGENT_URL", "http://localhost:8082")
ATOM_AGENT_ACTIVATE_ENDPOINT = f"{ATOM_AGENT_URL}/atom-agent/activate"
ATOM_AGENT_CONVERSATION_ENDPOINT = f"{ATOM_AGENT_URL}/atom-agent/conversation"
ATOM_AGENT_INTERRUPT_ENDPOINT = f"{ATOM_AGENT_URL}/atom-agent/interrupt" # New endpoint

# Wake word (using a built-in keyword for now, e.g., "porcupine")
WAKE_WORD_KEYWORD_STRING = "porcupine" # Or "atom_linux.ppn" if you have the file

COMMAND_AUDIO_TIMEOUT_SECONDS = 10 # Max duration to listen for command after wake word
SILENCE_THRESHOLD_RMS = 300  # RMS value to consider as silence (adjust based on microphone)
SILENCE_DETECTION_DURATION_SECONDS = 3 # How long silence must persist to timeout command listening early
INTERRUPT_THRESHOLD_SECONDS = 3 # Time window after command sent to consider next wake word as interrupt

class DetectorState(Enum):
    IDLE = 1                  # Initial state, not listening for wake word (e.g., before run or after stop)
    WAITING_FOR_WAKE_WORD = 2 # Actively listening for the wake word via Porcupine
    LISTENING_FOR_COMMAND = 3 # Wake word detected, now listening for user's command (audio sent to STT)
    SENDING_TO_AGENT = 4      # Command transcribed, sending it to Atom Agent
    PROCESSING_ERROR = 5      # An error occurred, returning to IDLE or WAITING_FOR_WAKE_WORD

class WakeWordDetector:
    def __init__(self, access_key, keyword_identifier):
        self._access_key = access_key
        self._keyword_paths = None
        self._keywords = None
        self._porcupine = None
        self._audio_stream_porcupine = None # Dedicated stream for Porcupine
        self._audio_stream_command = None   # Dedicated stream for command audio (can be same device config)
        self._pa = None
        self._running = False
        self._state = DetectorState.IDLE
        self._http_session = requests.Session()
        self._command_thread = None
        self._input_device_index = None
        self.last_command_sent_time = 0 # Timestamp of when the last command was sent to agent

        if not self._access_key:
            logging.error("Cannot initialize WakeWordDetector: Picovoice AccessKey is missing.")
            return

        try:
            if keyword_identifier.endswith('.ppn') and os.path.exists(keyword_identifier):
                self._keyword_paths = [keyword_identifier]
                logging.info(f"Using custom keyword file: {keyword_identifier}")
            elif keyword_identifier in pvporcupine.KEYWORDS:
                self._keywords = [keyword_identifier]
                logging.info(f"Using built-in keyword: {keyword_identifier}")
            else:
                logging.error(f"Keyword '{keyword_identifier}' is not a valid .ppn file or built-in keyword.")
                if pvporcupine.KEYWORDS:
                    self._keywords = [pvporcupine.KEYWORDS[0]]
                    logging.warning(f"Available built-in: {pvporcupine.KEYWORDS}. Falling back to: {self._keywords[0]}")
                else:
                    logging.error("No built-in keywords available. Porcupine init will fail.")
                    return

            self._porcupine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=self._keyword_paths,
                keywords=self._keywords
            )
            logging.info(f"Porcupine engine initialized for keyword(s): {self._keyword_paths or self._keywords}")
            self._state = DetectorState.WAITING_FOR_WAKE_WORD # Ready to listen after init
        except pvporcupine.PorcupineError as e:
            logging.error(f"Failed to initialize Porcupine: {e}")
            self._porcupine = None
            self._state = DetectorState.PROCESSING_ERROR
        except Exception as e:
            logging.error(f"An unexpected error occurred during Porcupine initialization: {e}")
            self._porcupine = None
            self._state = DetectorState.PROCESSING_ERROR


    def _open_audio_stream_for_porcupine(self):
        if not self._pa or not self._porcupine: return False
        try:
            self._audio_stream_porcupine = self._pa.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
                input_device_index=self._input_device_index
            )
            logging.info("Audio stream for Porcupine opened.")
            return True
        except Exception as e:
            logging.error(f"Failed to open Porcupine audio stream: {e}")
            return False

    def _close_audio_stream_porcupine(self):
        if self._audio_stream_porcupine:
            self._audio_stream_porcupine.stop_stream()
            self._audio_stream_porcupine.close()
            self._audio_stream_porcupine = None
            logging.info("Audio stream for Porcupine closed.")

    def list_audio_devices(self):
        if not self._pa: self._pa = pyaudio.PyAudio()
        logging.info("Available audio input devices:")
        for i in range(self._pa.get_device_count()):
            dev_info = self._pa.get_device_info_by_index(i)
            if dev_info.get('maxInputChannels') > 0:
                logging.info(f"  Device {i}: {dev_info.get('name')} (Input Channels: {dev_info.get('maxInputChannels')})")

    def _set_input_device(self, input_device_index=None):
        self._pa = pyaudio.PyAudio()
        if input_device_index is None:
            try:
                self._input_device_index = self._pa.get_default_input_device_info()['index']
                logging.info(f"Using default input device (Index: {self._input_device_index}).")
            except IOError as e:
                logging.error(f"Could not get default input device: {e}. List devices and specify one.")
                self.list_audio_devices()
                return False
        else:
            try:
                device_info = self._pa.get_device_info_by_index(input_device_index)
                if device_info.get('maxInputChannels', 0) == 0:
                    logging.error(f"Device at index {input_device_index} is not an input device.")
                    return False
                self._input_device_index = input_device_index
                logging.info(f"Using selected input device: {device_info.get('name')} (Index: {self._input_device_index})")
            except Exception as e:
                logging.error(f"Invalid input device index {input_device_index}: {e}")
                return False
        return True

    async def _handle_command_audio_and_transcription(self):
        logging.info("Starting command audio handling and transcription...")
        self._state = DetectorState.LISTENING_FOR_COMMAND

        # 1. Activate Atom Agent
        if not self._activate_atom_agent():
            self._state = DetectorState.WAITING_FOR_WAKE_WORD
            return

        # 2. Open WebSocket to audio_processor
        final_transcript = ""
        try:
            async with websockets.connect(AUDIO_PROCESSOR_WS_URL) as websocket:
                logging.info(f"WebSocket connected to {AUDIO_PROCESSOR_WS_URL}")

                # Open a new audio stream for sending command audio
                # This uses the same _pa instance and device index chosen earlier
                self._audio_stream_command = self._pa.open(
                    rate=16000, # Standard for STT, adjust if audio_processor expects different
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=1024, # Smaller buffer for lower latency
                    input_device_index=self._input_device_index
                )
                logging.info("Command audio stream opened.")

                last_speech_time = time.time()
                start_listening_time = time.time()

                async def sender(ws):
                    nonlocal last_speech_time # Allow modification
                    while self._state == DetectorState.LISTENING_FOR_COMMAND:
                        try:
                            audio_data = self._audio_stream_command.read(1024, exception_on_overflow=False)
                            await ws.send(audio_data)

                            # Basic silence detection
                            rms = audioop.rms(audio_data, 2) # 2 bytes per sample for paInt16
                            if rms > SILENCE_THRESHOLD_RMS:
                                last_speech_time = time.time()
                            # logging.debug(f"RMS: {rms}") # Uncomment for debugging silence detection
                            await asyncio.sleep(0.01) # Small sleep to yield control
                        except Exception as e:
                            logging.error(f"Error during audio send: {e}")
                            break
                    logging.info("Audio sending loop finished.")

                async def receiver(ws):
                    nonlocal final_transcript # Allow modification
                    nonlocal last_speech_time
                    while self._state == DetectorState.LISTENING_FOR_COMMAND:
                        try:
                            message_str = await asyncio.wait_for(ws.recv(), timeout=0.1) # Short timeout to check state
                            message_json = json.loads(message_str)
                            transcript = message_json.get("transcript", "")
                            is_final = message_json.get("is_final", False)

                            if transcript:
                                logging.info(f"STT: {'FINAL: ' if is_final else 'INTERIM: '}{transcript}")
                                last_speech_time = time.time() # Reset silence timer on any transcript
                                if is_final and transcript.strip(): # Only consider non-empty final transcripts
                                    final_transcript += transcript.strip() + " "
                                    # If we get a firm final, we can break and send to agent
                                    # Or, we could wait for a pause (silence) after a final transcript
                                    logging.info(f"Final transcript segment received: '{transcript.strip()}'")
                                    # For now, let's assume one solid final transcript is enough, or silence timeout will handle it.
                                    # If we want to break immediately on first final:
                                    # self._state = DetectorState.SENDING_TO_AGENT
                                    # break

                        except asyncio.TimeoutError:
                            continue # No message, check overall timeouts below
                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("WebSocket connection closed by server.")
                            break
                        except Exception as e:
                            logging.error(f"Error receiving/processing STT result: {e}")
                            break
                    logging.info("STT result receiving loop finished.")

                # Run sender and receiver concurrently
                send_task = asyncio.create_task(sender(websocket))
                recv_task = asyncio.create_task(receiver(websocket))

                # Timeout and silence detection logic
                while self._state == DetectorState.LISTENING_FOR_COMMAND:
                    current_time = time.time()
                    if (current_time - start_listening_time) > COMMAND_AUDIO_TIMEOUT_SECONDS:
                        logging.info("Command listening timed out (overall duration).")
                        break
                    if (current_time - last_speech_time) > SILENCE_DETECTION_DURATION_SECONDS:
                        logging.info("Silence detected for configured duration. Ending command listening.")
                        break
                    await asyncio.sleep(0.1) # Check timeouts periodically

                # Ensure tasks are cancelled and awaited to prevent errors on exit
                if not send_task.done(): send_task.cancel()
                if not recv_task.done(): recv_task.cancel()
                try: await send_task
                except asyncio.CancelledError: pass
                try: await recv_task
                except asyncio.CancelledError: pass

        except websockets.exceptions.ConnectionClosedError as e:
            logging.error(f"WebSocket connection failed or closed unexpectedly: {e}")
        except ConnectionRefusedError:
            logging.error(f"WebSocket connection refused by server at {AUDIO_PROCESSOR_WS_URL}. Is audio_processor running?")
        except Exception as e:
            logging.error(f"Error during WebSocket communication: {e}", exc_info=True)
        finally:
            if self._audio_stream_command:
                self._audio_stream_command.stop_stream()
                self._audio_stream_command.close()
                self._audio_stream_command = None
                logging.info("Command audio stream closed.")

            if final_transcript.strip():
                self._state = DetectorState.SENDING_TO_AGENT
                self._send_transcript_to_atom_agent(final_transcript.strip())
            else:
                logging.info("No valid final transcript obtained.")
                self._deactivate_atom_agent("no_command_after_activation") # Inform agent if activation led to nothing

            self._state = DetectorState.WAITING_FOR_WAKE_WORD

    def _activate_atom_agent(self):
        logging.info(f"Activating Atom Agent at {ATOM_AGENT_ACTIVATE_ENDPOINT}...")
        try:
            response = self._http_session.post(ATOM_AGENT_ACTIVATE_ENDPOINT, timeout=5)
            response.raise_for_status()
            logging.info(f"Atom Agent activated successfully: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to activate Atom Agent: {e}")
            return False

    def _deactivate_atom_agent(self, reason="unknown"):
        deactivate_url = f"{ATOM_AGENT_URL}/atom-agent/deactivate"
        logging.info(f"Attempting to inform Atom Agent of deactivation at {deactivate_url} due to: {reason}")
        try:
            response = self._http_session.post(deactivate_url, json={"reason": reason}, timeout=5)
            if response.ok:
                logging.info(f"Atom Agent informed of deactivation: {response.json()}")
            else:
                logging.warning(f"Atom Agent deactivation call failed or not supported: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to call Atom Agent deactivation endpoint: {e}")

    def _send_interrupt_to_atom_agent(self):
        logging.info(f"Sending interrupt to Atom Agent at {ATOM_AGENT_INTERRUPT_ENDPOINT}...")
        try:
            response = self._http_session.post(ATOM_AGENT_INTERRUPT_ENDPOINT, timeout=3)
            response.raise_for_status()
            logging.info(f"Atom Agent interrupt acknowledged: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send interrupt to Atom Agent: {e}")
            return False

    def _send_transcript_to_atom_agent(self, transcript_text):
        logging.info(f"Sending transcript to Atom Agent: '{transcript_text}' at {ATOM_AGENT_CONVERSATION_ENDPOINT}")
        try:
            payload = {"text": transcript_text}
            response = self._http_session.post(ATOM_AGENT_CONVERSATION_ENDPOINT, json=payload, timeout=15)
            response.raise_for_status()
            logging.info(f"Atom Agent responded: {response.json()}")
            self.last_command_sent_time = time.time() # Record time after successful send
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send transcript to Atom Agent: {e}")
            # self.last_command_sent_time should not be updated on failure
        finally:
            self._state = DetectorState.WAITING_FOR_WAKE_WORD


    def _run_porcupine_loop(self):
        if not self._open_audio_stream_for_porcupine():
            self._state = DetectorState.PROCESSING_ERROR
            return

        logging.info("Listening for wake word...")
        while self._running and self._state == DetectorState.WAITING_FOR_WAKE_WORD:
            try:
                pcm = self._audio_stream_porcupine.read(self._porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self._porcupine.frame_length, pcm)
                result = self._porcupine.process(pcm)
                if result >= 0:  # Wake word detected
                    logging.info(f"Wake word detected (keyword_index {result})!")
                    self._close_audio_stream_porcupine() # Close Porcupine stream

                    current_time = time.time()
                    is_interruption = (current_time - self.last_command_sent_time) < INTERRUPT_THRESHOLD_SECONDS

                    if is_interruption:
                        logging.info("Wake word detected soon after last command. Treating as INTERRUPT.")
                        self._send_interrupt_to_atom_agent()
                        # After interrupt, agent should be ready for new command.
                        # The standard flow will call activate again, which is fine.

                    logging.info("Transitioning to handle command audio.")
                    self._command_thread = threading.Thread(target=lambda: asyncio.run(self._handle_command_audio_and_transcription()))
                    self._command_thread.daemon = True
                    self._command_thread.start()
                    break # Exit this loop; start() will re-evaluate state and wait for thread

            except KeyboardInterrupt:
                logging.info("Keyboard interrupt in Porcupine loop.")
                self._running = False
                break
            except Exception as e:
                logging.error(f"Error during wake word detection: {e}", exc_info=True)
                self._state = DetectorState.PROCESSING_ERROR # Set error state
                self._running = False # Stop running on error
                break

        self._close_audio_stream_porcupine() # Ensure stream is closed if loop exited for other reasons

    def start(self, input_device_index=None):
        if not self._porcupine:
            logging.error("Porcupine not initialized. Cannot start.")
            self._state = DetectorState.PROCESSING_ERROR
            return

        if not self._set_input_device(input_device_index):
            self._state = DetectorState.PROCESSING_ERROR
            return

        self._running = True
        self._state = DetectorState.WAITING_FOR_WAKE_WORD # Initial state for starting
        logging.info("Wake word detector started. Press Ctrl+C to stop.")

        try:
            while self._running:
                if self._state == DetectorState.WAITING_FOR_WAKE_WORD:
                    self._run_porcupine_loop()
                elif self._state == DetectorState.LISTENING_FOR_COMMAND or self._state == DetectorState.SENDING_TO_AGENT:
                    # These states are managed by the _command_thread.
                    # The main loop can sleep or yield here, waiting for state change.
                    if self._command_thread and self._command_thread.is_alive():
                        self._command_thread.join(timeout=0.1) # Wait briefly for thread
                    else: # Thread finished or not started properly
                        if self._state != DetectorState.WAITING_FOR_WAKE_WORD and self._state != DetectorState.PROCESSING_ERROR :
                            logging.debug(f"Command thread finished or inactive, current state: {self._state}. Ensuring return to WAITING_FOR_WAKE_WORD.")
                            self._state = DetectorState.WAITING_FOR_WAKE_WORD # Ensure we go back to listening
                elif self._state == DetectorState.PROCESSING_ERROR:
                    logging.error("Detector in PROCESSING_ERROR state. Stopping.")
                    self._running = False
                else:
                    time.sleep(0.1) # Small sleep for other states or transitions

        except KeyboardInterrupt:
            logging.info("Stopping wake word detection (KeyboardInterrupt in start loop).")
        finally:
            self._running = False
            if self._command_thread and self._command_thread.is_alive():
                logging.info("Waiting for command thread to finish...")
                # Signal the thread to stop if it's still in LISTENING_FOR_COMMAND
                if self._state == DetectorState.LISTENING_FOR_COMMAND:
                     self._state = DetectorState.IDLE # Or some other terminal state for the thread
                self._command_thread.join(timeout=2.0)
            self.stop_resources()


    def stop_resources(self):
        logging.info("Stopping wake word detector resources...")
        self._running = False # Ensure loops exit

        self._close_audio_stream_porcupine()
        if self._audio_stream_command: # Ensure command stream is also closed
            self._audio_stream_command.stop_stream()
            self._audio_stream_command.close()
            self._audio_stream_command = None
            logging.info("Command audio stream closed during stop.")

        if self._pa:
            self._pa.terminate()
            self._pa = None
            logging.info("PyAudio instance terminated.")

        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None
            logging.info("Porcupine engine resources released.")

        self._state = DetectorState.IDLE
        logging.info("Wake word detector resources stopped.")


def main():
    logging.info("Starting wake word detector integration test...")

    if not PICOVOICE_ACCESS_KEY:
        logging.error("Picovoice AccessKey (PV_ACCESS_KEY) is not set. Aborting.")
        return

    keyword_to_use = WAKE_WORD_KEYWORD_STRING
    # Example for custom PPN:
    # atom_ppn_path = "atom_keyword.ppn"
    # if os.path.exists(atom_ppn_path):
    #    keyword_to_use = atom_ppn_path

    detector = WakeWordDetector(access_key=PICOVOICE_ACCESS_KEY, keyword=keyword_to_use)

    if detector._state == DetectorState.PROCESSING_ERROR or not detector._porcupine :
        logging.error("Failed to initialize WakeWordDetector. Exiting.")
        return

    detector.list_audio_devices()
    # Try running with default device. User can specify index if needed.
    # e.g., detector.start(input_device_index=0)

    # Note: Actual audio device access and network calls might be restricted in some sandboxes.
    # This script is designed to show the flow and structure.
    # Ensure PV_ACCESS_KEY, AUDIO_PROCESSOR_URL, ATOM_AGENT_URL are set in your environment.

    try:
        detector.start() # This will block until Ctrl+C or error
    except Exception as e:
        logging.error(f"An unexpected error occurred during detector.start(): {e}", exc_info=True)
    finally:
        logging.info("Main: Cleaning up detector resources.")
        detector.stop_resources() # Ensure cleanup on exit
        logging.info("Wake word detector test finished.")

if __name__ == '__main__':
    # System dependencies like portaudio for PyAudio might be needed.
    # `sudo apt-get install portaudio19-dev python3-pyaudio`

    # Check environment variables
    logging.info(f"Config: PV_ACCESS_KEY: {'Set' if PICOVOICE_ACCESS_KEY else 'Not Set'}")
    logging.info(f"Config: AUDIO_PROCESSOR_WS_URL: {AUDIO_PROCESSOR_WS_URL}")
    logging.info(f"Config: ATOM_AGENT_ACTIVATE_ENDPOINT: {ATOM_AGENT_ACTIVATE_ENDPOINT}")
    logging.info(f"Config: ATOM_AGENT_CONVERSATION_ENDPOINT: {ATOM_AGENT_CONVERSATION_ENDPOINT}")
    logging.info(f"Config: ATOM_AGENT_INTERRUPT_ENDPOINT: {ATOM_AGENT_INTERRUPT_ENDPOINT}")

    main()
