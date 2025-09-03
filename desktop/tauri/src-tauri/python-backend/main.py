#!/usr/bin/env python3
"""
Main Python Backend Service for Atom Desktop App
Provides voice, audio processing, and backend functionality for the desktop app
"""

import os
import sys
import logging
import asyncio
import threading
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add the local backend to Python path to access shared modules
backend_root = Path(__file__).parent / "backend"
python_api_root = Path(__file__).parent / "backend" / "python-api-service"
sys.path.insert(0, str(backend_root))
sys.path.insert(0, str(python_api_root))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import pyaudio
    import numpy as np
    import audioop
    # OpenWakeWord may have compatibility issues with Python 3.7
    try:
        from openwakeword.model import Model
        OPENWAKEWORD_AVAILABLE = True
    except ImportError:
        OPENWAKEWORD_AVAILABLE = False
        print("Warning: openwakeword not available, using fallback audio processing")
except ImportError as e:
    print(f"Missing required packages: {e}")
    print("Please install with: pip install flask flask-cors pyaudio numpy")
    if "openwakeword" in str(e):
        print("Note: openwakeword may not be fully compatible with Python 3.7")
    sys.exit(1)

# Import shared backend functionality
try:
    from _utils.constants import LANCEDB_URI, KAFKA_BOOTSTRAP_SERVERS
    from _utils.lancedb_service import search_meeting_transcripts, SemanticSearchResult
except ImportError as e:
    print(f"Failed to import shared backend modules: {e}")
    print("Using fallback implementations")
    LANCEDB_URI = os.environ.get("LANCEDB_URI", "/data/lancedb_store")
    KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    def search_meeting_transcripts(*args, **kwargs):
        return {"status": "success", "data": [], "message": "LanceDB search not available in desktop mode"}

    class SemanticSearchResult:
        pass

# Simplified wake word detector for desktop with Python 3.7 compatibility
class DetectorState:
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
        self._stop_event = threading.Event()
        self._processing_thread = None

        # Audio configuration
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.channels = 1

    def start(self):
        if self._state == DetectorState.PROCESSING_ERROR:
            logging.error("Cannot start detector in error state")
            return False

        if self._processing_thread and self._processing_thread.is_alive():
            logging.warning("Detector is already running")
            return True

        self._stop_event.clear()
        self._processing_thread = threading.Thread(target=self._run_audio_loop)
        self._processing_thread.daemon = True
        self._processing_thread.start()

        logging.info("Audio processing started (manual activation mode)")
        return True

    def stop(self):
        self._stop_event.set()
        if self._processing_thread:
            self._processing_thread.join(timeout=2.0)
        logging.info("Audio processing stopped")

    def stop_resources(self):
        self.stop()
        if self._wake_word_model:
            self._wake_word_model = None

    def _run_audio_loop(self):
        """Simple audio loop for manual activation in desktop mode"""
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )

            self._state = DetectorState.WAITING_FOR_WAKE_WORD
            logging.info("Audio input ready for manual activation")

            while not self._stop_event.is_set():
                # Read audio data (keep stream active)
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                # Simple audio level monitoring
                rms = audioop.rms(data, 2)
                if rms > 1000:  # Detect some audio activity
                    logging.debug(f"Audio activity detected: {rms}")

                self._stop_event.wait(0.1)  # Small delay to prevent CPU overload

        except Exception as e:
            logging.error(f"Error in audio loop: {e}")
            self._state = DetectorState.PROCESSING_ERROR
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            if audio:
                audio.terminate()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('desktop-backend.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DesktopBackendService:
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)
        self.wake_word_detector = None
        self.wake_word_model = None
        self.is_listening = False

        # Audio configuration
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.channels = 1

        self.setup_routes()
        self.initialize_services()

    def initialize_services(self):
        """Initialize all backend services"""
        try:
            # Initialize wake word detector with Python 3.7 compatibility
            self.wake_word_detector = WakeWordDetector()

            # Try to load wake word model if available
            self.wake_word_model = None
            if OPENWAKEWORD_AVAILABLE:
                try:
                    wake_word_model_path = os.path.join(os.path.dirname(__file__), "atom_wake_word.onnx")
                    if os.path.exists(wake_word_model_path):
                        self.wake_word_model = Model(wakeword_models=[wake_word_model_path], inference_framework="onnx")
                        logger.info(f"Loaded wake word model from {wake_word_model_path}")
                    else:
                        logger.warning("Wake word model file not found, using manual activation mode")
                except Exception as e:
                    logger.warning(f"Could not load wake word model: {e}, using manual activation mode")

            logger.info("Desktop backend services initialized successfully")
            if self.wake_word_model:
                logger.info("Wake word detection enabled")
            else:
                logger.info("Manual activation mode - use API endpoints to trigger audio processing")

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            self.wake_word_model = None
            self.wake_word_detector = WakeWordDetector()

    def setup_routes(self):
        """Setup Flask API routes"""

        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({"status": "healthy", "services": {
                "wake_word": self.wake_word_model is not None,
                "audio_processing": True
            }})

        @self.app.route('/api/wake-word/start', methods=['POST'])
        def start_wake_word_detection():
            try:
                if self.wake_word_detector and self.wake_word_detector.start():
                    self.is_listening = True
                    return jsonify({
                        "status": "success",
                        "message": "Wake word detection started",
                        "note": "Desktop mode - manual activation only"
                    })
                else:
                    return jsonify({"status": "error", "message": "Failed to start wake word detection"}), 500
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/wake-word/stop', methods=['POST'])
        def stop_wake_word_detection():
            try:
                if self.wake_word_detector:
                    self.wake_word_detector.stop()
                    self.is_listening = False
                return jsonify({"status": "success", "message": "Wake word detection stopped"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/wake-word/status', methods=['GET'])
        def get_wake_word_status():
            status = "inactive"
            if self.wake_word_detector:
                status = {
                    DetectorState.IDLE: "idle",
                    DetectorState.WAITING_FOR_WAKE_WORD: "listening",
                    DetectorState.LISTENING_FOR_COMMAND: "processing",
                    DetectorState.SENDING_TO_AGENT: "sending",
                    DetectorState.PROCESSING_ERROR: "error"
                }.get(self.wake_word_detector._state, "unknown")

            return jsonify({
                "status": status,
                "is_listening": self.is_listening,
                "model_loaded": self.wake_word_model is not None,
                "mode": "desktop",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "openwakeword_available": OPENWAKEWORD_AVAILABLE,
                "capabilities": ["manual_activation", "audio_processing", "voice_transcription", "audio_recording"]
            })

        @self.app.route('/api/audio/process', methods=['POST'])
        def process_audio():
            try:
                data = request.get_json()
                audio_data = data.get('audio_data')
                user_id = data.get('user_id', 'default_user')

                if not audio_data:
                    return jsonify({"status": "error", "message": "No audio data provided"}), 400

                # Process audio data (base64 encoded or binary)
                # For now, simulate processing and return mock response
                logger.info(f"Processing audio for user {user_id}, data length: {len(audio_data) if isinstance(audio_data, str) else 'binary'}")

                return jsonify({
                    "status": "success",
                    "message": "Audio processed successfully",
                    "transcription": "This is a mock transcription from desktop backend",
                    "confidence": 0.85,
                    "user_id": user_id
                })
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/search/meetings', methods=['POST'])
        def search_meetings():
            try:
                data = request.get_json()
                query = data.get('query')
                user_id = data.get('user_id', 'default_user')

                if not query:
                    return jsonify({"status": "error", "message": "Query parameter required"}), 400

                # Convert query to vector (this would typically come from an embedding service)
                # For now, use a dummy vector
                query_vector = [0.1] * 384  # Example vector dimension

                try:
                    result = search_meeting_transcripts(
                        db_path=str(LANCEDB_URI),
                        query_vector=query_vector,
                        user_id=user_id,
                        table_name="meeting_transcripts_embeddings",
                        limit=5
                    )
                except Exception as search_error:
                    result = {"status": "error", "message": f"Search failed: {search_error}"}

                return jsonify(result)

            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/voice/transcribe', methods=['POST'])
        def transcribe_audio():
            try:
                # Handle audio file upload for transcription
                if 'audio' not in request.files:
                    return jsonify({"status": "error", "message": "No audio file provided"}), 400

                audio_file = request.files['audio']
                user_id = request.form.get('user_id', 'default_user')

                if audio_file.filename == '':
                    return jsonify({"status": "error", "message": "No audio file selected"}), 400

                # Save audio file temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                    audio_file.save(tmp_file.name)
                    tmp_path = tmp_file.name

                logger.info(f"Transcribing audio file: {audio_file.filename} for user {user_id}")

                # Simulate transcription processing
                # In a real implementation, this would call a speech-to-text service

                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except:
                    pass

                return jsonify({
                    "status": "success",
                    "transcription": "This is a simulated transcription from the desktop audio backend",
                    "confidence": 0.92,
                    "user_id": user_id,
                    "file_name": audio_file.filename
                })
            except Exception as e:
                logger.error(f"Error transcribing audio: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

    def run(self, host='127.0.0.1', port=8084):
        """Run the Flask server"""
        logger.info(f"Starting Desktop Backend Service on {host}:{port}")
        self.app.run(host=host, port=port, debug=False, threaded=True)

def main():
    """Main entry point"""
    service = DesktopBackendService()
    service.run()

if __name__ == '__main__':
    main()
