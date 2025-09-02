import os
import logging
import threading
import time
import numpy as np
import pyaudio
import requests
import websockets
import asyncio
import json
from enum import Enum
import audioop

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# --- Configuration ---
AUDIO_PROCESSOR_URL = os.environ.get("AUDIO_PROCESSOR_URL", "ws://localhost:8081")
AUDIO_PROCESSOR_STT_STREAM_PATH = "/stt_stream"
AUDIO_PROCESSOR_WS_URL = f"{AUDIO_PROCESSOR_URL.replace('http://', 'ws://').replace('https://', 'wss://')}{AUDIO_PROCESSOR_STT_STREAM_PATH}"

ATOM_AGENT_URL = os.environ.get("ATOM_AGENT_URL", "http://localhost:8082")
ATOM_AGENT_ACTIVATE_ENDPOINT = f"{ATOM_AGENT_URL}/atom-agent/activate"
ATOM_AGENT_CONVERSATION_ENDPOINT = f"{ATOM_AGENT_URL}/atom-agent/conversation"
ATOM_AGENT_INTERRUPT_ENDPOINT = f"{ATOM_AGENT_URL}/atom-agent/interrupt"

# Wake word model path
WAKE_WORD_MODEL_PATH = os.environ.get("WAKE_WORD_MODEL_PATH", "/app/data/atom_wake_word.onnx")
WAKE_WORD_THRESHOLD = 0.5  # Confidence threshold for wake word detection

COMMAND_AUDIO_TIMEOUT_SECONDS = 10
SILENCE_THRESHOLD_RMS = 300
SILENCE_DETECTION_DURATION_SECONDS = 3
INTERRUPT_THRESHOLD_SECONDS = 3

class DetectorState(Enum):
    IDLE = 1
    WAITING_FOR_WAKE_WORD = 2
    LISTENING_FOR_COMMAND = 3
    SENDING_TO_AGENT = 4
    PROCESSING_ERROR = 5

class WakeWordDetector:
    def __init__(self):
        self._state = DetectorState.IDLE
        self._audio_stream = None
        self._wake_word_model = None
        self._audio_buffer = []
        self._stop_event = threading.Event()
        self._processing_thread = None

        # Audio configuration
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16

        # Initialize openWakeWord
        self._initialize_openwakeword()

    def _initialize_openwakeword(self):
        """Initialize the openWakeWord model"""
        try:
            from openwakeword.model import Model

            # Load the custom wake word model
            self._wake_word_model = Model(
                wakeword_models=[WAKE_WORD_MODEL_PATH],
                inference_framework="onnx"
            )
            logging.info(f"Loaded openWakeWord model from {WAKE_WORD_MODEL_PATH}")
            self._state = DetectorState.WAITING_FOR_WAKE_WORD

        except ImportError:
            logging.error("openwakeword package not installed. Please install with: pip install openwakeword")
            self._state = DetectorState.PROCESSING_ERROR
        except Exception as e:
            logging.error(f"Failed to initialize openWakeWord: {e}")
            self._state = DetectorState.PROCESSING_ERROR

    def _open_audio_stream(self):
        """Open audio stream for recording"""
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            return stream, audio
        except Exception as e:
            logging.error(f"Failed to open audio stream: {e}")
            return None, None

    def _close_audio_stream(self, stream, audio):
        """Close audio stream"""
        if stream:
            stream.stop_stream()
            stream.close()
        if audio:
            audio.terminate()

    def list_audio_devices(self):
        """List available audio devices"""
        try:
            audio = pyaudio.PyAudio()
            info = audio.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')

            logging.info("Available audio devices:")
            for i in range(num_devices):
                device_info = audio.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels') > 0:
                    logging.info(f"Device {i}: {device_info.get('name')}")

            audio.terminate()
        except Exception as e:
            logging.error(f"Error listing audio devices: {e}")

    def _set_input_device(self, device_index=None):
        """Set audio input device"""
        # Implementation would set the specific audio device
        # For now, we'll use default device
        pass

    async def _handle_command_audio_and_transcription(self):
        """Handle command audio and send to STT service"""
        try:
            async with websockets.connect(AUDIO_PROCESSOR_WS_URL) as websocket:
                # Send audio data to STT service
                for audio_chunk in self._audio_buffer:
                    await websocket.send(audio_chunk)

                # Receive transcription
                transcription = await websocket.recv()
                return json.loads(transcription)

        except Exception as e:
            logging.error(f"Error in audio processing: {e}")
            return None

    def _activate_atom_agent(self):
        """Activate the Atom agent"""
        try:
            response = requests.post(ATOM_AGENT_ACTIVATE_ENDPOINT, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error activating Atom agent: {e}")
            return False

    def _deactivate_atom_agent(self):
        """Deactivate the Atom agent"""
        # Implementation would send deactivation signal
        pass

    def _send_interrupt_to_atom_agent(self):
        """Send interrupt signal to Atom agent"""
        try:
            response = requests.post(ATOM_AGENT_INTERRUPT_ENDPOINT, timeout=2)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error sending interrupt to Atom agent: {e}")
            return False

    def _send_transcript_to_atom_agent(self, transcript):
        """Send transcript to Atom agent"""
        try:
            payload = {"text": transcript, "user_id": "default_user"}
            response = requests.post(
                ATOM_AGENT_CONVERSATION_ENDPOINT,
                json=payload,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error sending transcript to Atom agent: {e}")
            return False

    def _run_wakeword_loop(self):
        """Main loop for wake word detection using openWakeWord"""
        stream, audio = self._open_audio_stream()
        if not stream:
            self._state = DetectorState.PROCESSING_ERROR
            return

        try:
            self._state = DetectorState.WAITING_FOR_WAKE_WORD
            logging.info("Listening for wake word 'Atom'...")

            while not self._stop_event.is_set():
                # Read audio data
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)

                # Get predictions from openWakeWord
                prediction = self._wake_word_model.predict(audio_data)

                # Check if wake word was detected
                if prediction and len(prediction) > 0:
                    # Get the first (and only) prediction value
                    prediction_value = list(prediction.values())[0]
                    if prediction_value > WAKE_WORD_THRESHOLD:
                        logging.info(f"Wake word 'Atom' detected! Confidence: {prediction_value:.3f}")

                        if self._activate_atom_agent():
                            self._state = DetectorState.LISTENING_FOR_COMMAND
                            self._audio_buffer = [data]  # Start with current chunk

                            # Listen for command
                            start_time = time.time()
                            silence_start_time = None

                            while (time.time() - start_time < COMMAND_AUDIO_TIMEOUT_SECONDS and
                                   not self._stop_event.is_set()):

                                command_data = stream.read(self.chunk_size, exception_on_overflow=False)
                                self._audio_buffer.append(command_data)

                                # Check for silence
                                rms = audioop.rms(command_data, 2)
                                if rms < SILENCE_THRESHOLD_RMS:
                                    if silence_start_time is None:
                                        silence_start_time = time.time()
                                    elif time.time() - silence_start_time > SILENCE_DETECTION_DURATION_SECONDS:
                                        break
                                else:
                                    silence_start_time = None

                            # Process the command
                            if self._audio_buffer:
                                self._state = DetectorState.SENDING_TO_AGENT
                                asyncio.run(self._process_command_audio())

                            self._state = DetectorState.WAITING_FOR_WAKE_WORD
                else:
                    # No prediction or empty prediction
                    time.sleep(0.01)  # Small delay to prevent CPU overload
                    continue

                time.sleep(0.01)  # Small delay to prevent CPU overload

        except Exception as e:
            logging.error(f"Error in wake word detection loop: {e}")
            self._state = DetectorState.PROCESSING_ERROR
        finally:
            self._close_audio_stream(stream, audio)

    async def _process_command_audio(self):
        """Process the recorded command audio"""
        try:
            # Send audio to STT service
            transcription_result = await self._handle_command_audio_and_transcription()

            if transcription_result and 'text' in transcription_result:
                transcript = transcription_result['text']
                logging.info(f"Transcribed command: {transcript}")

                # Send to Atom agent
                if self._send_transcript_to_atom_agent(transcript):
                    logging.info("Command sent to Atom agent successfully")
                else:
                    logging.error("Failed to send command to Atom agent")
            else:
                logging.error("Failed to transcribe audio command")

        except Exception as e:
            logging.error(f"Error processing command audio: {e}")

    def start(self, input_device_index=None):
        """Start the wake word detector"""
        if self._state == DetectorState.PROCESSING_ERROR:
            logging.error("Cannot start detector in error state")
            return False

        if self._processing_thread and self._processing_thread.is_alive():
            logging.warning("Detector is already running")
            return True

        self._stop_event.clear()
        self._set_input_device(input_device_index)

        self._processing_thread = threading.Thread(target=self._run_wakeword_loop)
        self._processing_thread.daemon = True
        self._processing_thread.start()

        logging.info("Wake word detector started")
        return True

    def stop(self):
        """Stop the wake word detector"""
        self._stop_event.set()
        if self._processing_thread:
            self._processing_thread.join(timeout=2.0)

        self._deactivate_atom_agent()
        logging.info("Wake word detector stopped")

    def stop_resources(self):
        """Clean up resources"""
        self.stop()
        if self._wake_word_model:
            self._wake_word_model = None
            logging.info("Wake word model resources released")

def main():
    """Main function for testing"""
    logging.info("Starting openWakeWord-based wake word detector...")

    detector = WakeWordDetector()

    if detector._state == DetectorState.PROCESSING_ERROR:
        logging.error("Failed to initialize wake word detector")
        return

    detector.list_audio_devices()

    try:
        detector.start()
        logging.info("Wake word detector running. Press Ctrl+C to stop.")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Stopping wake word detector...")
    finally:
        detector.stop_resources()
        logging.info("Wake word detector stopped")

if __name__ == '__main__':
    main()
