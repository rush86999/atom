import json
import os
import sys
import logging
import asyncio
import uuid # Though taskId comes from message, good to have if worker needs to generate IDs
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json # Already imported, but good to note for HTTP server context

# Sounddevice import - will be conditional
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception as e:
    # Using a broad exception class as various issues can occur (missing library, portaudio issues)
    # In a production system, more specific exception handling might be desired.
    sd = None
    SOUNDDEVICE_AVAILABLE = False
    # Logging this at the point of use or server startup might be more relevant
    # print(f"Warning: sounddevice library not available or failed to initialize: {e}", file=sys.stderr)


# Adjust sys.path to allow imports from parent 'functions' directory
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.append(FUNCTIONS_DIR)
AGENTS_DIR = os.path.join(FUNCTIONS_DIR, 'agents') # If agents are in functions/agents
if AGENTS_DIR not in sys.path:
     sys.path.append(AGENTS_DIR)

# LanceDB service import
try:
    from _utils.lancedb_service import create_meeting_transcripts_table_if_not_exists
except ImportError as e:
    print(f"Warning: Failed to import lancedb_service: {e}", file=sys.stderr)
    create_meeting_transcripts_table_if_not_exists = None # Placeholder

# Kafka Consumer (using kafka-python)
try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KafkaConsumer = None
    KafkaError = Exception # Placeholder
    KAFKA_AVAILABLE = False
    print("WARNING: kafka-python library not found. Kafka worker cannot start.", file=sys.stderr)

# Agent Imports
OldZoomAgent, GoogleMeetAgent, MSTeamsAgent = None, None, None # Renamed OldZoomAgent
NewZoomSdkAgent = None
# Agent specific exceptions
SoundDeviceNotAvailableError, AudioDeviceSelectionError = None, None # For non-SDK agents
ZoomSdkAuthError, ZoomSdkAgentError, ZoomSdkMeetingError = None, None, None # For NewZoomSdkAgent

try:
    from agents.zoom_agent import ZoomAgent as ImportedOldZoomAgent, SoundDeviceNotAvailableError as OldZoomSdnae, AudioDeviceSelectionError as OldZoomAse
    OldZoomAgent = ImportedOldZoomAgent
    if not SoundDeviceNotAvailableError: SoundDeviceNotAvailableError = OldZoomSdnae
    if not AudioDeviceSelectionError: AudioDeviceSelectionError = OldZoomAse
except ImportError as e:
    print(f"Warning: Old ZoomAgent (zoom_agent.py) failed to import: {e}", file=sys.stderr)

try:
    from agents.NewZoomSdkAgent import NewZoomSdkAgent as ImportedNewZoomSdkAgent, ZoomSdkAuthError as NewZoomAuthErr, ZoomSdkAgentError as NewZoomAgentErr, ZoomSdkMeetingError as NewZoomMeetingErr
    NewZoomSdkAgent = ImportedNewZoomSdkAgent
    ZoomSdkAuthError = NewZoomAuthErr
    ZoomSdkAgentError = NewZoomAgentErr
    ZoomSdkMeetingError = NewZoomMeetingErr
except ImportError as e:
    print(f"Warning: NewZoomSdkAgent failed to import: {e}", file=sys.stderr)

try:
    from agents.google_meet_agent import GoogleMeetAgent as ImportedGoogleMeetAgent, SoundDeviceNotAvailableError as GMeetSdnae, AudioDeviceSelectionError as GMeetAse
    GoogleMeetAgent = ImportedGoogleMeetAgent
    if not SoundDeviceNotAvailableError: SoundDeviceNotAvailableError = GMeetSdnae # Still needed for these agents
    if not AudioDeviceSelectionError: AudioDeviceSelectionError = GMeetAse
except ImportError as e:
    print(f"Warning: GoogleMeetAgent or its specific exceptions failed to import in worker: {e}", file=sys.stderr)
try:
    from agents.ms_teams_agent import MSTeamsAgent as ImportedMSTeamsAgent, SoundDeviceNotAvailableError as TeamsSdnae, AudioDeviceSelectionError as TeamsAse
    MSTeamsAgent = ImportedMSTeamsAgent
    if not SoundDeviceNotAvailableError: SoundDeviceNotAvailableError = TeamsSdnae
    if not AudioDeviceSelectionError: AudioDeviceSelectionError = TeamsAse
except ImportError as e:
    print(f"Warning: MSTeamsAgent or its specific exceptions failed to import in worker: {e}", file=sys.stderr)


# psycopg2 for PostgreSQL connection
try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    sql = None # Placeholder
    RealDictCursor = None # Placeholder
    PSYCOPG2_AVAILABLE = False
    print("WARNING: psycopg2 library not found. Database status reporting will be disabled.", file=sys.stderr)

# note_utils import
note_utils_module = None
try:
    import note_utils as nu_module
    note_utils_module = nu_module
    if not hasattr(note_utils_module, 'process_live_audio_for_notion') or \
       not hasattr(note_utils_module, 'init_notion'):
        print("Error: Required functions (process_live_audio_for_notion, init_notion) not found in note_utils.", file=sys.stderr)
        note_utils_module = None
except ImportError as e:
    print(f"Critical Import Error for note_utils in live_meeting_worker: {e}", file=sys.stderr)

# Constants
try:
    from _utils import constants as app_constants
except ImportError:
    class MockAppConstants: # Fallback if constants can't be imported (e.g. path issue in test)
        KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        KAFKA_LIVE_MEETING_TOPIC = os.environ.get("KAFKA_LIVE_MEETING_TOPIC", "atom_live_meeting_tasks")
    app_constants = MockAppConstants()
    print("Warning: Could not import shared constants for Kafka worker. Using fallback values.", file=sys.stderr)


# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- PostgreSQL Status Reporting Functions ---
DB_CONN_PARAMS = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
    "user": os.environ.get("POSTGRES_USER", "user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "password"),
    "dbname": os.environ.get("POSTGRES_DB", "atomic_dev")
}

def get_db_connection():
    if not PSYCOPG2_AVAILABLE:
        return None
    try:
        conn = psycopg2.connect(**DB_CONN_PARAMS)
        return conn
    except psycopg2.Error as e:
        logger.error(f"DB Status: Failed to connect to PostgreSQL: {e}", exc_info=True)
        return None

def init_task_status(task_id: str, user_id: str, platform: str, meeting_identifier: str, initial_status: str):
    if not PSYCOPG2_AVAILABLE:
        logger.warning(f"DB Status (Task {task_id}): psycopg2 not available. Skipping init_task_status.")
        return

    conn = get_db_connection()
    if not conn:
        logger.error(f"DB Status (Task {task_id}): No DB connection. Skipping init_task_status.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meeting_attendance_status
                    (task_id, user_id, platform, meeting_identifier, status_timestamp, current_status_message)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (task_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    platform = EXCLUDED.platform,
                    meeting_identifier = EXCLUDED.meeting_identifier,
                    status_timestamp = NOW(),
                    current_status_message = EXCLUDED.current_status_message,
                    final_notion_page_url = NULL,
                    error_details = NULL;
                """,
                (task_id, user_id, platform, meeting_identifier, initial_status)
            )
        conn.commit()
        logger.info(f"DB Status (Task {task_id}): Initialized/Reset status to '{initial_status}'.")
    except psycopg2.Error as e:
        logger.error(f"DB Status (Task {task_id}): Error initializing task status: {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

def update_task_status(task_id: str, status_message: str, error_details: Optional[str] = None, final_notion_page_url: Optional[str] = None):
    if not PSYCOPG2_AVAILABLE:
        logger.warning(f"DB Status (Task {task_id}): psycopg2 not available. Skipping update_task_status to '{status_message}'.")
        return

    conn = get_db_connection()
    if not conn:
        logger.error(f"DB Status (Task {task_id}): No DB connection. Skipping update_task_status to '{status_message}'.")
        return

    try:
        with conn.cursor() as cur:
            query = sql.SQL("""
                UPDATE meeting_attendance_status SET
                    status_timestamp = NOW(),
                    current_status_message = %s,
                    error_details = %s,
                    final_notion_page_url = %s
                WHERE task_id = %s;
            """)
            cur.execute(query, (status_message, error_details, final_notion_page_url, task_id))

            if cur.rowcount == 0: # If no row was updated, maybe it was never inserted
                logger.warning(f"DB Status (Task {task_id}): Update affected 0 rows for status '{status_message}'. Task might not have been initialized in DB.")
                # Attempt to insert it with the current status, though some initial info might be missing.
                # This is a fallback, ideally init_task_status is always called first.
                # For simplicity, we're not calling init_task_status here to avoid complex parameter passing.
                # The primary responsibility for init is at the start of process_live_meeting_message.
            else:
                 logger.info(f"DB Status (Task {task_id}): Updated status to '{status_message}'.")
        conn.commit()
    except psycopg2.Error as e:
        logger.error(f"DB Status (Task {task_id}): Error updating task status to '{status_message}': {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

# --- End PostgreSQL Status Reporting Functions ---


# --- HTTP Server for Audio Device Listing ---
class AudioDeviceListHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/list_audio_devices':
            if not SOUNDDEVICE_AVAILABLE:
                self.send_response(503) # Service Unavailable
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "sounddevice library not available or failed to initialize.",
                    "note": "Audio device listing is unavailable."
                }).encode('utf-8'))
                logger.warning("HTTP Request to /list_audio_devices: sounddevice not available.")
                return

            try:
                devices = sd.query_devices()
                input_devices = []
                for i, device in enumerate(devices):
                    # Standard check for an input device
                    if device.get('max_input_channels', 0) > 0:
                        input_devices.append({
                            "index": i, # Original index from query_devices()
                            "name": device.get('name', 'Unknown Device'),
                            "hostapi_name": sd.query_hostapis(device.get('hostapi', -1))['name'] if device.get('hostapi', -1) != -1 else 'N/A',
                            "max_input_channels": device.get('max_input_channels')
                        })

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(input_devices).encode('utf-8'))
                logger.info(f"HTTP Request to /list_audio_devices: Found {len(input_devices)} input devices.")

            except Exception as e:
                self.send_response(500) # Internal Server Error
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Failed to query audio devices.",
                    "details": str(e)
                }).encode('utf-8'))
                logger.error(f"HTTP Request to /list_audio_devices: Error querying devices: {e}", exc_info=True)
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

def start_http_server(host='0.0.0.0', port=8081): # Port can be configured as needed
    """Starts the HTTP server in a separate thread."""
    if not SOUNDDEVICE_AVAILABLE:
        logger.warning("sounddevice not available. Audio device listing HTTP endpoint will indicate this.")
        # Server still runs to provide the 503 error, which is informative.

    try:
        httpd = HTTPServer((host, port), AudioDeviceListHandler)
        logger.info(f"Starting HTTP server for audio device listing on {host}:{port}...")
        # To run indefinitely in a thread:
        # httpd.serve_forever()
        # For controlled shutdown, it's better to run httpd.serve_forever() in a thread
        # that can be joined or signaled.
        thread = threading.Thread(target=httpd.serve_forever, daemon=True) # daemon=True allows main program to exit
        thread.start()
        logger.info("HTTP server thread started.")
        return httpd, thread
    except Exception as e:
        logger.error(f"Could not start HTTP server: {e}", exc_info=True)
        return None, None

# --- End HTTP Server ---


async def process_live_meeting_message(message_payload: dict):
    """
    Processes a single live meeting task message from Kafka.
    """
    task_id = message_payload.get('taskId', str(uuid.uuid4()))
    user_id = message_payload.get('userId') # Extract early for status reporting
    platform = message_payload.get('platform', '').lower() # Extract early
    meeting_identifier = message_payload.get('meetingIdentifier') # Extract early

    logger.info(f"Task {task_id}: Received live meeting processing request for User {user_id}, Platform {platform}, Meeting {meeting_identifier}.")

    # Initialize task status in DB
    init_task_status(task_id, user_id, platform, meeting_identifier, "Task Received")

    # --- Extract data from payload ---
    platform = message_payload.get('platform', '').lower()
    meeting_identifier = message_payload.get('meetingIdentifier')
    notion_note_title = message_payload.get('notionNoteTitle')

    notion_source = message_payload.get('notionSource', 'Live Meeting Transcription via Kafka Worker')
    linked_event_id = message_payload.get('linkedEventId')
    notion_db_id = message_payload.get('notionDbId') # Optional DB ID for the note

    api_keys = message_payload.get('apiKeys', {})
    notion_api_token = api_keys.get('notion')
    deepgram_api_key = api_keys.get('deepgram')
    openai_api_key = api_keys.get('openai')

    audio_settings = message_payload.get('audioSettings', {})
    audio_device_specifier = audio_settings.get('audioDeviceSpecifier')

    # --- Validate essential parameters ---
    # (Extracted earlier: user_id, platform, meeting_identifier)
    notion_note_title = message_payload.get('notionNoteTitle')
    notion_source = message_payload.get('notionSource', 'Live Meeting Transcription via Kafka Worker')
    linked_event_id = message_payload.get('linkedEventId')
    notion_db_id = message_payload.get('notionDbId') # Optional DB ID for the note
    api_keys = message_payload.get('apiKeys', {})
    notion_api_token = api_keys.get('notion')
    deepgram_api_key = api_keys.get('deepgram')
    openai_api_key = api_keys.get('openai')
    audio_settings = message_payload.get('audioSettings', {})
    audio_device_specifier = audio_settings.get('audioDeviceSpecifier')

    required_for_processing = {
        "userId": user_id, "platform": platform, "meetingIdentifier": meeting_identifier,
        "notionNoteTitle": notion_note_title, "notionApiKey": notion_api_token,
        "deepgramApiKey": deepgram_api_key, "openaiApiKey": openai_api_key
    }
    missing_processing_params = [k for k,v in required_for_processing.items() if not v]
    if missing_processing_params:
        err_msg = f"Missing critical parameters for processing: {', '.join(missing_processing_params)}. Payload: {message_payload}"
        logger.error(f"Task {task_id}: {err_msg}")
        update_task_status(task_id, "Failed: Missing Parameters", error_details=err_msg)
        return

    if not note_utils_module:
        err_msg = "note_utils module not available. Skipping processing."
        logger.error(f"Task {task_id}: {err_msg}")
        update_task_status(task_id, "Failed: Internal Error", error_details=err_msg)
        return

    update_task_status(task_id, "Initializing Notion")
    init_notion_resp = note_utils_module.init_notion(notion_api_token, database_id=notion_db_id)
    if init_notion_resp["status"] != "success":
        err_msg = f"Failed to initialize Notion client. Error: {init_notion_resp.get('message')}. Details: {init_notion_resp.get('details')}"
        logger.error(f"Task {task_id}: {err_msg}")
        update_task_status(task_id, "Failed: Notion Initialization", error_details=err_msg)
        return

    # --- Agent Instantiation & Configuration ---
    agent = None
    platform_interface = None
    agent_type_name = "UnknownAgent"
    use_new_zoom_sdk_agent = os.environ.get("USE_NEW_ZOOM_SDK_AGENT", "false").lower() == "true"


    try:
        update_task_status(task_id, "Initializing Agent")
        if platform == "zoom":
            if use_new_zoom_sdk_agent:
                if not NewZoomSdkAgent:
                    logger.error(f"Task {task_id}: NewZoomSdkAgent is configured for use but not imported.")
                    update_task_status(task_id, "Failed: Configuration Error", error_details="NewZoomSdkAgent not available.")
                    return

                zoom_sdk_key = api_keys.get('zoom_sdk_key')
                zoom_sdk_secret = api_keys.get('zoom_sdk_secret')

                if not zoom_sdk_key or not zoom_sdk_secret:
                    err_msg = "Zoom SDK Key or Secret not provided in task payload for NewZoomSdkAgent."
                    logger.error(f"Task {task_id}: {err_msg}")
                    update_task_status(task_id, "Failed: Zoom SDK credentials missing", error_details=err_msg)
                    return
                try:
                    agent = NewZoomSdkAgent(
                        user_id=user_id,
                        zoom_sdk_key=zoom_sdk_key,
                        zoom_sdk_secret=zoom_sdk_secret,
                        logger_instance=logger # Pass main worker logger
                    )
                    agent_type_name = "NewZoomSdkAgent"
                    if audio_device_specifier:
                        logger.info(f"Task {task_id}: audio_device_specifier ('{audio_device_specifier}') provided for Zoom SDK task. Note: This is ignored as audio is managed by the SDK helper's environment.")
                except ZoomSdkAuthError as e: # Specific error from NewZoomSdkAgent init
                    logger.error(f"Task {task_id}: NewZoomSdkAgent authentication error during init: {e}", exc_info=True)
                    update_task_status(task_id, "Failed: Zoom SDK Auth Error", error_details=str(e))
                    return
                except ValueError as ve: # Catch missing SDK key/secret from NewZoomSdkAgent init
                    logger.error(f"Task {task_id}: NewZoomSdkAgent initialization error: {ve}", exc_info=True)
                    update_task_status(task_id, "Failed: Zoom SDK Config Error", error_details=str(ve))
                    return
                except Exception as e: # Catch other init errors for NewZoomSdkAgent
                    logger.error(f"Task {task_id}: Error instantiating NewZoomSdkAgent: {e}", exc_info=True)
                    update_task_status(task_id, "Failed: Agent Instantiation Error", error_details=str(e))
                    return
            else: # Use old ZoomAgent
                if not OldZoomAgent:
                    logger.error(f"Task {task_id}: Old ZoomAgent (zoom_agent.py) is configured for use but not imported.")
                    update_task_status(task_id, "Failed: Configuration Error", error_details="Old ZoomAgent not available.")
                    return
                agent = OldZoomAgent(user_id=user_id, target_device_specifier_override=audio_device_specifier)
                agent_type_name = "OldZoomAgent"

        elif platform in ["googlemeet", "google_meet"]:
            if not GoogleMeetAgent:
                logger.error(f"Task {task_id}: GoogleMeetAgent not imported.")
                update_task_status(task_id, "Failed: Configuration Error", error_details="GoogleMeetAgent not available.")
                return
            agent = GoogleMeetAgent(user_id=user_id, target_device_specifier_override=audio_device_specifier)
            agent_type_name = "GoogleMeetAgent"
        elif platform in ["msteams", "microsoft_teams", "teams"]:
            if not MSTeamsAgent:
                logger.error(f"Task {task_id}: MSTeamsAgent not imported.")
                update_task_status(task_id, "Failed: Configuration Error", error_details="MSTeamsAgent not available.")
                return
            agent = MSTeamsAgent(user_id=user_id, target_device_specifier_override=audio_device_specifier)
            agent_type_name = "MSTeamsAgent"
        else:
            err_msg = f"Platform '{platform}' is not supported. Supported: zoom, googlemeet, msteams."
            logger.error(f"Task {task_id}: {err_msg}")
            update_task_status(task_id, "Failed: Unsupported Platform", error_details=err_msg)
            return
        platform_interface = agent
        logger.info(f"Task {task_id}: Instantiated {agent_type_name} for user {user_id} on platform {platform}.")

        # --- Meeting Lifecycle ---
        update_task_status(task_id, "Joining Meeting")
        logger.info(f"Task {task_id}: Attempting to join meeting {meeting_identifier}...")
        join_success = platform_interface.join_meeting(meeting_identifier)

        if not join_success:
            err_msg = f"Agent failed to launch/join meeting: {meeting_identifier} on platform {platform}."
            logger.error(f"Task {task_id}: {err_msg}")
            update_task_status(task_id, "Failed: Could Not Join Meeting", error_details=err_msg)
            return

        update_task_status(task_id, "Capturing Audio & Transcribing")
        logger.info(f"Task {task_id}: Successfully joined {meeting_identifier}. Starting live processing.")

        process_live_audio_func = getattr(note_utils_module, 'process_live_audio_for_notion')
        current_meeting_id = platform_interface.get_current_meeting_id() or meeting_identifier

        processing_result = await process_live_audio_func(
            platform_module=platform_interface, # type: ignore
            meeting_id=current_meeting_id,
            notion_note_title=notion_note_title,
            deepgram_api_key=deepgram_api_key,
            openai_api_key=openai_api_key,
            notion_db_id=notion_db_id,
            notion_source=notion_source,
            linked_event_id=linked_event_id
        )

        update_task_status(task_id, "Processing & Saving Note")

        if processing_result and processing_result.get("status") == "success":
            final_url = processing_result.get("data", {}).get("notion_page_url", None)
            logger.info(f"Task {task_id}: Successfully processed and created Notion note: {processing_result.get('data')}")
            update_task_status(task_id, "Completed", final_notion_page_url=final_url)

            notion_page_id = processing_result["data"].get("notion_page_id")
            full_transcript_text = processing_result["data"].get("full_transcript")

            # --- Embed and Store Transcript in LanceDB ---
            # This part is secondary to the main Notion processing result for status
            if notion_page_id and full_transcript_text: # Ensure these exist before trying to embed
                lancedb_uri_call = os.environ.get("LANCEDB_URI")
                if lancedb_uri_call:
                    logger.info(f"Task {task_id}: Attempting to embed transcript for Notion page {notion_page_id}")
                    try:
                        meeting_date_iso_param = None # As before
                        embed_and_store_func = getattr(note_utils_module, 'embed_and_store_transcript_in_lancedb', None)
                        if embed_and_store_func:
                            embed_result = embed_and_store_func(
                                notion_page_id=notion_page_id, transcript_text=full_transcript_text,
                                meeting_title=notion_note_title, meeting_date_iso=meeting_date_iso_param,
                                user_id=user_id, openai_api_key_param=openai_api_key,
                                lancedb_uri_param=lancedb_uri_call
                            )
                            if embed_result.get("status") == "success":
                                logger.info(f"Task {task_id}: Successfully embedded transcript for Notion page {notion_page_id}")
                            else:
                                logger.error(f"Task {task_id}: Failed to embed transcript for {notion_page_id}. Error: {embed_result.get('message')}")
                        else:
                            logger.error(f"Task {task_id}: 'embed_and_store_transcript_in_lancedb' not found in note_utils.")
                    except Exception as e:
                        logger.error(f"Task {task_id}: Exception during transcript embedding for {notion_page_id}: {e}", exc_info=True)
                else: # lancedb_uri_call is not set
                    logger.info(f"Task {task_id}: Skipping LanceDB embedding for {notion_page_id} as LANCEDB_URI is not set.")
            elif processing_result.get("status") == "success": # Ensure this log only if main processing was success but embedding info missing
                 logger.warning(f"Task {task_id}: Skipping LanceDB embedding for {notion_page_id if notion_page_id else 'Unknown Page'} due to missing notion_page_id or full_transcript, though main processing was successful.")

        else: # processing_result is None or status is not "success"
            error_message = "Processing failed"
            error_code = "PROCESSING_FAILED"
            error_details_text = "Unknown processing error."

            if processing_result: # If processing_result dict exists
                error_message = processing_result.get("message", error_message)
                error_code = processing_result.get("code", error_code)
                error_details_text = f"Code: {error_code}, Msg: {error_message}, Details: {processing_result.get('details')}"
            else: # processing_result itself is None
                error_details_text = "Processing function returned None."

            full_err_msg = f"Live audio processing failed for {current_meeting_id}. {error_details_text}"
            logger.error(f"Task {task_id}: {full_err_msg}")
            update_task_status(task_id, f"Failed: {error_message}", error_details=error_details_text)

    # Specific exceptions for NewZoomSdkAgent
    except (ZoomSdkAuthError, ZoomSdkAgentError, ZoomSdkMeetingError) as zoom_sdk_ex:
        err_msg = f"Zoom SDK Agent error ({agent_type_name}): {str(zoom_sdk_ex)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        # Determine a more specific status message if possible
        status_msg_prefix = "Failed: Zoom SDK Error"
        if isinstance(zoom_sdk_ex, ZoomSdkAuthError):
            status_msg_prefix = "Failed: Zoom SDK Auth Error"
        elif isinstance(zoom_sdk_ex, ZoomSdkMeetingError):
            status_msg_prefix = "Failed: Zoom SDK Meeting Error"
        update_task_status(task_id, status_msg_prefix, error_details=err_msg)

    # Specific exceptions for other agents (sounddevice based)
    except (SoundDeviceNotAvailableError, AudioDeviceSelectionError) as audio_err:
        err_msg = f"Audio device error for {agent_type_name}: {str(audio_err)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_task_status(task_id, "Failed: Audio Device Error", error_details=err_msg)

    # General runtime errors (could be from any agent or processing step)
    except RuntimeError as rt_err:
        err_msg = f"Runtime error during processing with {agent_type_name}: {str(rt_err)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_task_status(task_id, "Failed: Runtime Error", error_details=err_msg)

    # Catch-all for any other unexpected exceptions
    except Exception as e:
        err_msg = f"Unexpected error during processing with {agent_type_name if agent else 'N/A'}: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_task_status(task_id, "Failed: Unexpected Error", error_details=err_msg)

    finally:
        if agent and hasattr(agent, 'is_active') and agent.is_active(): # For NewZoomSdkAgent
             logger.info(f"Task {task_id}: Ensuring agent {agent_type_name} (SDK type) leaves meeting if active...")
             await agent.leave_meeting()
        elif agent and hasattr(agent, 'current_meeting_id') and agent.current_meeting_id: # For older agents
            meeting_id_for_leave = agent.get_current_meeting_id()
            logger.info(f"Task {task_id}: Ensuring agent {agent_type_name} leaves meeting {meeting_id_for_leave}.")
            try:
                # All agents should have an async leave_meeting now or be callable this way
                if hasattr(agent, 'leave_meeting') and asyncio.iscoroutinefunction(agent.leave_meeting):
                    await agent.leave_meeting()
                elif hasattr(agent, 'leave_meeting'): # If not async, log warning but call
                     logger.warning(f"Task {task_id}: Agent {agent_type_name} has a synchronous leave_meeting method. Calling it.")
                     agent.leave_meeting() # type: ignore
            except Exception as leave_err:
                logger.error(f"Task {task_id}: Error during {agent_type_name}.leave_meeting(): {leave_err}", exc_info=True)
        elif agent and platform == "zoom" and use_new_zoom_sdk_agent: # If NewZoomSdkAgent was attempted but failed before join
             logger.info(f"Task {task_id}: Ensuring NewZoomSdkAgent cleanup is called if it was instantiated but might not be 'active'.")
             await agent.leave_meeting() # leave_meeting on NewZoomSdkAgent handles null process

        logger.info(f"Task {task_id}: Processing finished.")


async def consume_live_meeting_tasks():
    """
    Consumes tasks from the Kafka topic for live meeting processing.
    """
    if not KAFKA_AVAILABLE:
        logger.error("Kafka client library (kafka-python) not available. Worker cannot start.")
        return

    # Check if at least one agent type is available
    agent_available = OldZoomAgent or NewZoomSdkAgent or GoogleMeetAgent or MSTeamsAgent
    if not agent_available:
        logger.error("No meeting agent implementations (OldZoomAgent, NewZoomSdkAgent, GoogleMeetAgent, MSTeamsAgent) are available. Worker cannot effectively process tasks.")
        return

    if not note_utils_module:
        logger.error("note_utils module is not available. Worker cannot process tasks.")
        return

    # --- Initialize LanceDB Table for Meeting Transcripts ---
    lancedb_uri_env = os.environ.get("LANCEDB_URI")
    if not lancedb_uri_env:
        logger.warning("LANCEDB_URI environment variable not set. LanceDB operations for meeting transcripts will be skipped.")
    elif not create_meeting_transcripts_table_if_not_exists:
        logger.warning("create_meeting_transcripts_table_if_not_exists function not available. LanceDB table initialization skipped.")
    else:
        try:
            # This function is synchronous
            create_meeting_transcripts_table_if_not_exists(db_path=lancedb_uri_env)
            logger.info(f"Ensured LanceDB table 'meeting_transcripts' exists at {lancedb_uri_env}")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB table 'meeting_transcripts': {e}", exc_info=True)
            # Worker will continue, but embedding will likely fail if table is needed.

    consumer = None
    try:
        consumer = KafkaConsumer(
            app_constants.KAFKA_LIVE_MEETING_TOPIC,
            bootstrap_servers=app_constants.KAFKA_BOOTSTRAP_SERVERS.split(','),
            group_id="live-meeting-worker-group-v1", # Consumer group ID
            auto_offset_reset='earliest', # Start reading at the earliest message if no offset stored
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            # key_deserializer=lambda x: x.decode('utf-8') if x else None, # If key is used
            # enable_auto_commit=True, # Default, commits offsets automatically in background
            # auto_commit_interval_ms=5000 # Default
            # For more control, set enable_auto_commit=False and commit manually:
            # consumer.commit()
        )
        logger.info(f"KafkaConsumer initialized for topic '{app_constants.KAFKA_LIVE_MEETING_TOPIC}' on servers '{app_constants.KAFKA_BOOTSTRAP_SERVERS}'. Waiting for messages...")

        async for message in consumer:
            task_id = message.value.get('taskId', 'UnknownTask')
            logger.info(f"Task {task_id}: Received message from Kafka: Topic '{message.topic}', Partition {message.partition}, Offset {message.offset}")
            try:
                await process_live_meeting_message(message.value)
                # If manual commit: consumer.commit() # or commit specific offsets
            except Exception as e:
                logger.error(f"Task {task_id}: Unhandled exception during process_live_meeting_message: {e}", exc_info=True)
                # Decide on error strategy: retry, dead-letter queue, or skip.
                # For now, it logs and continues to next message.

    except KafkaError as e:
        logger.error(f"Kafka Consumer error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in Kafka consumer loop: {e}", exc_info=True)
    finally:
        if consumer:
            logger.info("Closing Kafka consumer.")
            consumer.close()

if __name__ == '__main__':
    logger.info("Starting Live Meeting Worker...")

    # Start the HTTP server for audio device listing
    http_server, http_thread = start_http_server()
    if http_server:
        logger.info(f"HTTP server for audio devices is running in thread: {http_thread.name}")
    else:
        logger.error("HTTP server for audio devices failed to start. Proceeding without it.")

    # Ensure Python 3.7+ for asyncio.run
    if sys.version_info >= (3, 7):
        try:
            asyncio.run(consume_live_meeting_tasks())
        except KeyboardInterrupt:
            logger.info("Worker shutdown requested via KeyboardInterrupt.")
            if http_server:
                logger.info("Attempting to shut down HTTP server...")
                http_server.shutdown() # Signal the server to stop
                http_thread.join(timeout=5) # Wait for the thread to finish
                if http_thread.is_alive():
                    logger.warning("HTTP server thread did not terminate cleanly.")
                else:
                    logger.info("HTTP server shut down.")
        except Exception as e: # Catch errors from consume_live_meeting_tasks if it raises before loop
            logger.error(f"Critical error preventing worker from running: {e}", exc_info=True)
            if http_server: # Also try to shutdown HTTP server on other critical errors
                logger.info("Attempting to shut down HTTP server due to critical error...")
                http_server.shutdown()
                http_thread.join(timeout=5)
    else:
        logger.error("Python 3.7 or higher is required to run this worker.")

[end of atomic-docker/project/functions/live_meeting_worker/worker.py]
