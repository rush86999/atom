import flask
import os
import sys
import json # For Kafka message serialization
import uuid # For generating taskId
import traceback
from kafka.errors import KafkaError # Specific Kafka errors
# Assuming kafka-python is the library. If another, imports would change.
try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None # Allow file to load if kafka-python is not installed yet
    print("WARNING: kafka-python library not found. Kafka functionality will be disabled.", file=sys.stderr)


# Add parent 'functions' directory to sys.path for sibling imports
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
FUNCTIONS_DIR_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT))
if FUNCTIONS_DIR_PATH not in sys.path:
    sys.path.append(FUNCTIONS_DIR_PATH)

# Import constants
try:
    from _utils import constants as app_constants
except ImportError:
    # Fallback if _utils.constants is not found (e.g. local test without full structure)
    class MockAppConstants:
        KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
        KAFKA_LIVE_MEETING_TOPIC = "atom_live_meeting_tasks"
    app_constants = MockAppConstants()
    print("Warning: Could not import shared constants. Using fallback values for Kafka.", file=sys.stderr)


# Kafka Producer - Initialize lazily or per request for Flask simplicity
# For high-throughput, a shared global instance with proper connection management is better.
kafka_producer: KafkaProducer | None = None

def get_kafka_producer() -> KafkaProducer:
    global kafka_producer
    if kafka_producer is None and KafkaProducer is not None: # Check if library was imported
        try:
            kafka_producer = KafkaProducer(
                bootstrap_servers=app_constants.KAFKA_BOOTSTRAP_SERVERS.split(','), # Allow comma-separated list
                client_id="attend-live-meeting-producer",
                retries=3, # Retry sending a few times
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            print("KafkaProducer initialized successfully.", file=sys.stderr)
        except KafkaError as e: # More specific Kafka connection errors
            print(f"Failed to initialize KafkaProducer: {e}", file=sys.stderr)
            kafka_producer = None # Ensure it's None if init fails
            raise # Re-raise to signal failure to the route
        except Exception as e: # Other unexpected errors during init
            print(f"Unexpected error initializing KafkaProducer: {e}", file=sys.stderr)
            kafka_producer = None
            raise
    if kafka_producer is None and KafkaProducer is None:
        raise RuntimeError("KafkaProducer library (kafka-python) not available.")
    if kafka_producer is None: # If initialization failed previously
        raise RuntimeError("KafkaProducer failed to initialize. Check Kafka server and configuration.")
    return kafka_producer


app = flask.Flask(__name__)

def make_error_response(code: str, message: str, details: any = None, http_status: int = 500):
    return flask.jsonify({
        "ok": False,
        "error": {"code": code, "message": message, "details": details}
    }), http_status

@app.route('/', methods=['POST'])
async def attend_live_meeting_route(): # Remains async for consistency, though core is sync now
    if KafkaProducer is None: # Check if kafka-python is even installed
        return make_error_response("SERVICE_UNAVAILABLE", "Kafka client library not available on server.", http_status=503)

    payload = {}
    try:
        payload = flask.request.get_json()
        if not payload:
            return make_error_response("INVALID_PAYLOAD", "Request must be JSON.", http_status=400)

        action_input = payload.get('action_input', {})
        session_variables = payload.get('session_variables', {})
        handler_input = payload.get('handler_input', {})

        platform = action_input.get('platform', '').lower()
        meeting_identifier = action_input.get('meeting_identifier')
        notion_note_title = action_input.get('notion_note_title')

        notion_source = action_input.get('notion_source', 'Live Meeting Transcription')
        linked_event_id = action_input.get('linked_event_id')
        notion_db_id = action_input.get('notion_db_id')

        user_id = session_variables.get('x-hasura-user-id')

        notion_api_token = handler_input.get('notion_api_token')
        deepgram_api_key = handler_input.get('deepgram_api_key')
        openai_api_key = handler_input.get('openai_api_key')

        # --- Zoom SDK Credentials from handler_input ---
        # These are expected to be passed by the client calling this Flask endpoint
        # if a Zoom meeting using the NewZoomSdkAgent is intended.
        zoom_sdk_key = handler_input.get('zoom_sdk_key')
        zoom_sdk_secret = handler_input.get('zoom_sdk_secret')
        # --- End Zoom SDK Credentials ---

        # Extract audio settings, specifically the device specifier
        audio_settings = handler_input.get('audio_settings', {})
        audio_device_specifier = audio_settings.get('audio_device_specifier')


        required_params_map = {
            "platform": platform, "meeting_identifier": meeting_identifier,
            "notion_note_title": notion_note_title, "user_id": user_id,
            "notion_api_token": notion_api_token, "deepgram_api_key": deepgram_api_key,
            "openai_api_key": openai_api_key,
        }
        missing_params = [k for k, v in required_params_map.items() if not v]
        if missing_params:
            return make_error_response("VALIDATION_ERROR", f"Missing required parameters: {', '.join(missing_params)}", http_status=400)

        # --- Construct Kafka Message ---
        task_id = str(uuid.uuid4())
        kafka_message_payload = {
            "taskId": task_id,
            "userId": user_id,
            "platform": platform,
            "meetingIdentifier": meeting_identifier,
            "notionNoteTitle": notion_note_title,
            "notionSource": notion_source,
            "linkedEventId": linked_event_id,
            "notionDbId": notion_db_id,
            "apiKeys": {
                "notion": notion_api_token,
                "deepgram": deepgram_api_key,
                "openai": openai_api_key,
                # Add Zoom SDK keys if they were provided in the handler_input
                "zoom_sdk_key": zoom_sdk_key,
                "zoom_sdk_secret": zoom_sdk_secret,
            },
            "audioSettings": {
                "audioDeviceSpecifier": audio_device_specifier
            }
        }

        # --- Publish to Kafka ---
        # Log if Zoom SDK keys are being included
        if zoom_sdk_key and zoom_sdk_secret:
            print(f"Task {task_id}: Including Zoom SDK Key (found in handler_input) in Kafka message.", file=sys.stderr)
        elif platform == "zoom": # Log warning if platform is zoom but keys are missing from input
            # This warning is for the handler; the worker will make the final decision
            # if keys are strictly required based on USE_NEW_ZOOM_SDK_AGENT.
            print(f"Task {task_id}: Zoom platform specified, but Zoom SDK Key or Secret not found in handler_input. New SDK agent might fail if configured.", file=sys.stderr)

        # --- Publish to Kafka ---
        # Log if Zoom SDK keys are being included
        if zoom_sdk_key and zoom_sdk_secret:
            print(f"Task {task_id}: Including Zoom SDK Key (found in handler_input) in Kafka message.", file=sys.stderr)
        elif platform == "zoom": # Log warning if platform is zoom but keys are missing from input
            # This warning is for the handler; the worker will make the final decision
            # if keys are strictly required based on USE_NEW_ZOOM_SDK_AGENT.
            print(f"Task {task_id}: Zoom platform specified, but Zoom SDK Key or Secret not found in handler_input. New SDK agent might fail if configured.", file=sys.stderr)

        try:
            # --- Publish to Kafka ---
            producer = get_kafka_producer() # Get or initialize producer
            future = producer.send(
                app_constants.KAFKA_LIVE_MEETING_TOPIC,
                key=task_id, # Key is already encoded by serializer
                value=kafka_message_payload # Value is JSON serialized by serializer
            )
            # Wait for the send to complete with a timeout
            record_metadata = future.get(timeout=10)
            print(f"Successfully published task {task_id} to Kafka topic '{record_metadata.topic}' partition {record_metadata.partition} offset {record_metadata.offset}", file=sys.stderr)

            return flask.jsonify({
                "ok": True,
                "data": {"message": "Meeting processing request accepted.", "taskId": task_id}
            }), 202 # HTTP 202 Accepted
        except KafkaError as e: # Specific Kafka errors (e.g., KafkaTimeoutError if broker down)
            error_message = f"Failed to publish task to Kafka: {e}"
            print(error_message, file=sys.stderr)
            return make_error_response("KAFKA_PUBLISH_FAILED", error_message, {"kafka_error": str(e)}, http_status=500)
        except Exception as e: # Other exceptions during send (e.g., serializer error if payload not dict)
            error_message = f"An unexpected error occurred during Kafka publish: {e}"
            print(error_message, file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return make_error_response("KAFKA_PUBLISH_UNEXPECTED_ERROR", error_message, {"exception_type": type(e).__name__}, http_status=500)
    except Exception as e: # Catch-all for validation, JSON parsing, or other unexpected errors
        print(f"Critical error in attend_live_meeting_route before Kafka publish: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return make_error_response("INTERNAL_SERVER_ERROR", f"An internal error occurred: {str(e)}", http_status=500)

if __name__ == '__main__':
    print(f"Starting local Flask server for attend_live_meeting (Kafka publisher) handler on port {os.environ.get('FLASK_PORT', 5000)}...", file=sys.stderr)
    # Note: KafkaProducer should ideally be closed on app shutdown.
    # For Flask dev server, this is tricky. For prod WSGI, use app context or atexit.
    try:
        app.run(port=int(os.environ.get("FLASK_PORT", 5000)), debug=True)
    finally:
        if kafka_producer:
            print("Closing Kafka producer...", file=sys.stderr)
            kafka_producer.flush()
            kafka_producer.close()
            print("Kafka producer closed.", file=sys.stderr)
