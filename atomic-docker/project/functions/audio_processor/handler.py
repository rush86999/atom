import os
import sys
import uuid
import tempfile
import shutil
import json # Added for sending JSON over WebSocket
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_sock import Sock # Added for WebSocket support
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    PrerecordedOptions,
    FileSource,
    SpeakOptions,
    LiveTranscriptionEvents, # Added for live transcription
    LiveOptions, # Added for live transcription
)

# Add the parent directory (functions) to sys.path to allow sibling imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from note_utils import process_audio_for_note
except ImportError:
    # Fallback for environments where the above path adjustment might not be enough
    # or if running this script directly for testing (though imports might still fail without more context)
    print("Error: Could not import process_audio_for_note. Ensure note_utils.py is accessible.")
    # Define a dummy function if import fails, so Flask can still start for basic testing
    def process_audio_for_note(*args, **kwargs):
        return "Error: process_audio_for_note function not loaded."

app = Flask(__name__)
sock = Sock(app) # Initialize Flask-Sock

# Define and create audio output directory
AUDIO_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'generated_audio')
if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR)
    app.logger.info(f"Created audio output directory: {AUDIO_OUTPUT_DIR}")

# Initialize Deepgram Client
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    app.logger.error("DEEPGRAM_API_KEY not found in environment variables. STT endpoint will not work.")

try:
    config = DeepgramClientOptions(verbose=0) # Set verbose to 1 or higher for more logs
    deepgram = DeepgramClient(DEEPGRAM_API_KEY, config)
except Exception as e:
    app.logger.error(f"Failed to initialize Deepgram client: {e}")
    deepgram = None # Ensure deepgram is defined even if initialization fails

@app.route('/', methods=['POST']) # Default endpoint for the service
def handle_action():
    try:
        req_data = request.get_json()

        # Hasura sends action arguments inside input.arg1 (default behavior)
        # Or directly in input if request_transform is configured differently.
        # Based on the YAML, we expect input.arg1
        action_args = req_data.get("input", {}).get("arg1")

        if not action_args:
            return jsonify({
                "status": "error",
                "error": "Invalid request structure: 'input.arg1' is missing."
            }), 400

        audio_file_path = action_args.get("audio_file_path")
        if not audio_file_path:
            return jsonify({
                "status": "error",
                "error": "Missing required argument: audio_file_path"
            }), 400

        # Optional arguments
        note_id = action_args.get("note_id")
        title = action_args.get("title")
        content = action_args.get("content")
        source = action_args.get("source")
        linked_task_id = action_args.get("linked_task_id")
        linked_event_id = action_args.get("linked_event_id")

        # Call the core logic function
        # Ensure all arguments are passed correctly, using defaults from process_audio_for_note if not provided
        result_note_id_or_error = process_audio_for_note(
            audio_file_path=audio_file_path,
            note_id=note_id,
            title=title if title is not None else "New Audio Note", # Pass defaults if None
            content=content if content is not None else "",
            source=source if source is not None else "Audio Upload",
            linked_task_id=linked_task_id,
            linked_event_id=linked_event_id
        )

        if "Error:" in result_note_id_or_error or "failed:" in result_note_id_or_error.lower() or result_note_id_or_error is None:
            return jsonify({
                "status": "error",
                "error": str(result_note_id_or_error)
            })
        else:
            return jsonify({
                "note_id": result_note_id_or_error,
                "status": "success"
            })

    except Exception as e:
        app.logger.error(f"Error processing action: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": f"An unexpected error occurred: {str(e)}"
        }), 500

if __name__ == '__main__':
    # This is for local development/testing.
    # In a serverless environment, a WSGI server like Gunicorn would run the app.
    # The port should be configurable via environment variable for production.
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host='0.0.0.0', port=port)


@sock.route('/stt_stream')
def stt_stream(ws): # ws is the WebSocket connection object
    app.logger.info("WebSocket connection established for /stt_stream")
    if not deepgram or not DEEPGRAM_API_KEY:
        app.logger.error("Deepgram client not initialized or API key missing. Cannot perform STT.")
        ws.send(json.dumps({"error": "Deepgram client not initialized or API key missing."}))
        ws.close()
        return

    try:
        # Configure Deepgram live transcription
        # Note: The SDK version in requirements.txt (3.x) uses `create_connection`
        # Older versions (like 0.x mentioned in some comments) might use `start`
        dg_connection = deepgram.listen.live.v("1")

        def on_open(self, open, **kwargs):
            app.logger.info(f"Deepgram connection opened: {open}")

        def on_message(self, result, **kwargs):
            if result.is_final and len(result.channel.alternatives) > 0:
                transcript = result.channel.alternatives[0].transcript
                if transcript:
                    app.logger.info(f"Sending transcript (final): {transcript}")
                    ws.send(json.dumps({"transcript": transcript, "is_final": True}))
            elif not result.is_final and len(result.channel.alternatives) > 0:
                transcript = result.channel.alternatives[0].transcript
                if transcript:
                    app.logger.info(f"Sending transcript (interim): {transcript}")
                    ws.send(json.dumps({"transcript": transcript, "is_final": False}))


        def on_metadata(self, metadata, **kwargs):
            app.logger.info(f"Deepgram metadata received: {metadata}")

        def on_speech_started(self, speech_started, **kwargs):
            app.logger.info(f"Deepgram speech started: {speech_started}")

        def on_utterance_end(self, utterance_end, **kwargs):
            app.logger.info(f"Deepgram utterance ended: {utterance_end}")

        def on_close(self, close, **kwargs):
            app.logger.info(f"Deepgram connection closed: {close}")

        def on_error(self, error, **kwargs):
            app.logger.error(f"Deepgram error: {error}")
            ws.send(json.dumps({"error": f"Deepgram error: {str(error)}"}))
            # Optionally close ws here or let client handle reconnection

        def on_unhandled(self, unhandled, **kwargs):
            app.logger.warning(f"Deepgram unhandled event: {unhandled}")

        dg_connection.on(LiveTranscriptionEvents.Open, on_open)
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
        dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
        dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Unhandled, on_unhandled)

        # Configure live transcription options
        # Example options: model, language, encoding, sample_rate, channels
        # Adjust these based on the audio stream characteristics
        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="linear16", # Common encoding for raw audio from browsers
            sample_rate=16000,   # Common sample rate
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True
        )

        if not dg_connection.start(options):
            app.logger.error("Failed to start Deepgram connection.")
            ws.send(json.dumps({"error": "Failed to start Deepgram connection."}))
            ws.close()
            return

        app.logger.info("Deepgram connection started with options.")

        while True:
            try:
                message = ws.receive() # Blocking call, waits for message
                if message is None:
                    app.logger.info("WebSocket connection closed by client (received None).")
                    break

                # Assuming audio data is sent as binary
                if isinstance(message, (bytes, bytearray)):
                    dg_connection.send(message)
                elif isinstance(message, str):
                    # Could be a control message from client, e.g., to close connection
                    app.logger.info(f"Received text message from client: {message}")
                    if message.lower() == 'close': # Example control message
                        break
                else:
                    app.logger.warning(f"Received unexpected message type: {type(message)}")

            except ConnectionResetError:
                app.logger.error("WebSocket connection reset by client.")
                break
            except Exception as e:
                app.logger.error(f"Error receiving from WebSocket or sending to Deepgram: {e}", exc_info=True)
                # Decide if to break or continue based on error
                break

    except Exception as e:
        app.logger.error(f"Error in STT stream handler: {e}", exc_info=True)
        try:
            ws.send(json.dumps({"error": f"Server error: {str(e)}"}))
        except Exception as ws_send_e:
            app.logger.error(f"Failed to send error to WebSocket client: {ws_send_e}")
    finally:
        if 'dg_connection' in locals() and dg_connection:
            app.logger.info("Closing Deepgram connection.")
            dg_connection.finish() # Ensure Deepgram connection is closed
        if not ws.closed:
            app.logger.info("Closing WebSocket connection from server side.")
            ws.close()
        app.logger.info("WebSocket connection for /stt_stream finished.")


@app.route('/stt', methods=['POST'])
def handle_stt():
    if not deepgram or not DEEPGRAM_API_KEY:
        return jsonify({
            "status": "error",
            "error": "Deepgram client not initialized or API key missing. Cannot perform STT."
        }), 500

    temp_dir = None
    temp_audio_path = None

    try:
        if 'audio_file' not in request.files:
            return jsonify({"status": "error", "error": "No audio file part in the request"}), 400

        file = request.files['audio_file']
        if file.filename == '':
            return jsonify({"status": "error", "error": "No selected audio file"}), 400

        if file:
            filename = secure_filename(file.filename)
            temp_dir = tempfile.mkdtemp()
            temp_audio_path = os.path.join(temp_dir, filename)
            file.save(temp_audio_path)
            app.logger.info(f"Audio file saved temporarily to {temp_audio_path}")

            with open(temp_audio_path, 'rb') as audio_file_to_transcribe:
                payload: FileSource = {'buffer': audio_file_to_transcribe}
                options = PrerecordedOptions(model="nova-2", smart_format=True)

                app.logger.info(f"Sending audio file to Deepgram: {temp_audio_path}")
                response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=300)

                transcription = response.results.channels[0].alternatives[0].transcript
                app.logger.info(f"Transcription successful for: {temp_audio_path}")

                return jsonify({
                    "transcription": transcription,
                    "status": "success"
                })
        else:
            # This case should ideally be caught by earlier checks, but as a fallback:
            return jsonify({"status": "error", "error": "File processing failed."}), 400

    except Exception as e:
        app.logger.error(f"Error during STT processing: {e}", exc_info=True)
        # Check if the error is from Deepgram SDK and try to get more details
        if hasattr(e, 'body') and e.body: # some Deepgram errors might have a body
             error_details = str(e.body)
        else:
             error_details = str(e)
        return jsonify({
            "status": "error",
            "error": f"An unexpected error occurred during STT: {error_details}"
        }), 500
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
                app.logger.info(f"Successfully removed temporary audio file: {temp_audio_path}")
            except Exception as e_remove:
                app.logger.error(f"Error removing temporary audio file {temp_audio_path}: {e_remove}")
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                app.logger.info(f"Successfully removed temporary directory: {temp_dir}")
            except Exception as e_rmdir:
                app.logger.error(f"Error removing temporary directory {temp_dir}: {e_rmdir}")


@app.route('/tts', methods=['POST'])
async def handle_tts():
    if not deepgram or not DEEPGRAM_API_KEY:
        return jsonify({
            "status": "error",
            "error": "Deepgram client not initialized or API key missing. Cannot perform TTS."
        }), 500

    try:
        req_data = request.get_json()
        if not req_data:
            return jsonify({"status": "error", "error": "No JSON body provided."}), 400

        text_to_speak = req_data.get("text")
        if not text_to_speak:
            return jsonify({
                "status": "error",
                "error": "Missing required argument: text"
            }), 400

        source = {"text": text_to_speak}
        # Example voice, adjust as needed. Refer to Deepgram docs for available models.
        options = SpeakOptions(model="aura-asteria-en", encoding="mp3")

        filename = f"tts_{uuid.uuid4()}.mp3"
        filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)

        app.logger.info(f"Requesting TTS from Deepgram for text: \"{text_to_speak[:50]}...\"")
        # The Deepgram SDK's speak.rest.v("1").synthesize is an async method.
        # Ensure Flask is run with an ASGI server (e.g. Uvicorn, Hypercorn) for `async def` routes.
        response = await deepgram.speak.rest.v("1").synthesize(source, options, timeout=300)

        if response and response.stream:
            with open(filepath, 'wb') as audio_file:
                async for chunk in response.stream:
                    if chunk:
                        audio_file.write(chunk)
            app.logger.info(f"TTS audio successfully saved to: {filepath}")
            # Construct URL relative to the Flask app's root for serving the file
            # The client will need to prepend the base API URL if this Flask app is served under a prefix like /api/audio_processor
            audio_url = f"/generated_audio/{filename}"
            return jsonify({
                "audio_url": audio_url,
                "status": "success"
            })
        else:
            app.logger.error("Deepgram TTS request did not return a valid stream.")
            return jsonify({
                "status": "error",
                "error": "Failed to get audio stream from Deepgram."
            }), 500

    except Exception as e:
        app.logger.error(f"Error during TTS processing: {e}", exc_info=True)
        # Check if the error is from Deepgram SDK and try to get more details
        if hasattr(e, 'body') and e.body: # some Deepgram errors might have a body
             error_details = str(e.body)
        else:
             error_details = str(e)
        return jsonify({
            "status": "error",
            "error": f"An unexpected error occurred during TTS: {error_details}"
        }), 500


@app.route('/generated_audio/<path:filename>')
def serve_generated_audio(filename):
    """Serves generated audio files."""
    app.logger.info(f"Attempting to serve file: {filename} from {AUDIO_OUTPUT_DIR}")
    try:
        return send_from_directory(AUDIO_OUTPUT_DIR, filename, as_attachment=False)
    except FileNotFoundError:
        app.logger.error(f"File not found: {filename} in {AUDIO_OUTPUT_DIR}")
        return jsonify({"status": "error", "error": "File not found"}), 404
