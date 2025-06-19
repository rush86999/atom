import pytest
import json
from unittest.mock import patch, MagicMock
import sys
import os

# Add relevant paths to sys.path to allow importing handler and its dependencies
# This assumes 'functions' is the root for these modules in the context of how the handler sees them.
# Path to 'functions' directory
FUNCTIONS_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if FUNCTIONS_DIR_PATH not in sys.path:
    sys.path.append(FUNCTIONS_DIR_PATH)
# Path to 'attend_live_meeting' directory itself (for 'from . import x' if used, or direct import)
HANDLER_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if HANDLER_DIR_PATH not in sys.path:
    sys.path.append(HANDLER_DIR_PATH)


# Mock environment variables that note_utils might depend on at import time
# This needs to happen BEFORE the handler (and thus note_utils) is imported.
os.environ['NOTION_API_TOKEN'] = 'dummy_test_notion_token'
os.environ['NOTION_NOTES_DATABASE_ID'] = 'dummy_test_notion_db_id'
os.environ['DEEPGRAM_API_KEY'] = 'dummy_test_deepgram_key'
os.environ['OPENAI_API_KEY'] = 'dummy_test_openai_key'
os.environ['OPENAI_API_ENDPOINT'] = 'https://api.openai.com/v1/chat/completions'
os.environ['GPT_MODEL_NAME'] = 'gpt-3.5-turbo'

# Import the Flask app from the handler AFTER setting env vars and paths
# We need to mock ZoomAgent and process_live_audio_for_notion *before* they are imported by the handler.
# This is tricky. A common way is to patch them where they are looked up (in the handler's module).

# Mock the dependencies BEFORE importing the app that uses them
mock_zoom_agent_instance = MagicMock()
mock_zoom_agent_class = MagicMock(return_value=mock_zoom_agent_instance)

mock_process_live_audio = MagicMock()

# The modules_to_patch dictionary tells @patch where to find the names to mock.
# It assumes that 'handler' will try to import 'ZoomAgent' from 'agents.zoom_agent'
# and 'process_live_audio_for_notion' from 'note_utils'.
modules_to_patch = {
    'agents.zoom_agent.ZoomAgent': mock_zoom_agent_class, # Patch the class
    'note_utils.process_live_audio_for_notion': mock_process_live_audio,
    # If note_utils itself needs to be reloaded due to its own global clients and env vars:
    # This is complex to manage here. The setenv above is the primary mechanism.
    # We assume the handler.py's importlib.reload(note_utils_module) handles it.
}

# Apply patches globally for the test file or within fixtures/tests.
# For simplicity here, we'll patch them where they are used in the handler module.
# This requires knowing the import paths *as seen by handler.py*.
# handler.py uses: from agents.zoom_agent import ZoomAgent
#                   from note_utils import process_live_audio_for_notion

# We will patch these within each test function or a fixture for cleaner state.

# Now import the app
from attend_live_meeting.handler import app as flask_app


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def reset_mocks():
    # Reset mocks before each test to ensure independence
    mock_zoom_agent_class.reset_mock()
    mock_zoom_agent_instance.reset_mock()
    mock_process_live_audio.reset_mock()

    # Default behaviors for success cases (can be overridden in specific tests)
    mock_zoom_agent_instance.join_meeting.return_value = True
    mock_zoom_agent_instance.leave_meeting.return_value = True # Assuming it returns something or just runs
    mock_process_live_audio.return_value = "mock_notion_page_id_123"


# Define common payload structure
def get_valid_payload(overrides=None):
    payload = {
        "action_input": {
            "platform": "zoom",
            "meeting_identifier": "test_meeting_123",
            "notion_note_title": "Test Live Notes",
            "notion_source": "pytest",
            "linked_event_id": "event_xyz"
        },
        "session_variables": {
            "x-hasura-user-id": "test-user-id-123"
        }
    }
    if overrides:
        payload["action_input"].update(overrides)
    return payload

# Using patch decorator on each test function that needs these mocks
@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_successful_zoom_call(client):
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    response_data = response.get_json()
    print("Response Data:", response_data) # For debugging in case of failure

    assert response.status_code == 200
    assert response_data["status"] == "Processing complete. Notion page created/updated."
    assert response_data["note_id"] == "mock_notion_page_id_123"

    mock_zoom_agent_class.assert_called_once_with(user_id="test-user-id-123")
    mock_zoom_agent_instance.join_meeting.assert_called_once_with("test_meeting_123")
    mock_process_live_audio.assert_called_once_with(
        platform_module=mock_zoom_agent_instance,
        meeting_id="test_meeting_123",
        notion_note_title="Test Live Notes",
        notion_source="pytest",
        linked_event_id="event_xyz"
    )
    mock_zoom_agent_instance.leave_meeting.assert_called_once()


@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_zoom_join_failure(client):
    mock_zoom_agent_instance.join_meeting.return_value = False
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    assert response.status_code == 500 # As per handler logic
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "Failed to join Zoom meeting" in response_data["error_message"]
    mock_process_live_audio.assert_not_called() # Should not be called if join fails
    mock_zoom_agent_instance.leave_meeting.assert_not_called() # Should not be called if join fails

@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_unsupported_platform(client):
    payload = get_valid_payload(overrides={"platform": "teams"})
    response = client.post('/', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "Platform 'teams' is not supported" in response_data["error_message"]

@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_missing_parameters(client):
    # Example: missing meeting_identifier
    invalid_payload = get_valid_payload()
    del invalid_payload["action_input"]["meeting_identifier"]
    response = client.post('/', data=json.dumps(invalid_payload), content_type='application/json')

    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "Missing required parameters" in response_data["error_message"]
    assert "meeting_identifier" in response_data["error_message"]

    # Example: missing user_id (session variable)
    invalid_payload_user = get_valid_payload()
    del invalid_payload_user["session_variables"]["x-hasura-user-id"]
    response_user = client.post('/', data=json.dumps(invalid_payload_user), content_type='application/json')
    assert response_user.status_code == 400
    response_data_user = response_user.get_json()
    assert "user_id (from session)" in response_data_user["error_message"]


@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_process_live_audio_fails(client):
    mock_process_live_audio.return_value = "Error: Specific failure in live processing" # Error string
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    response_data = response.get_json()
    assert response.status_code == 500 # As per handler logic for this error type
    assert response_data["status"] == "Error"
    assert "Error: Specific failure in live processing" in response_data["error_message"]
    mock_zoom_agent_instance.leave_meeting.assert_called_once() # leave_meeting should still be called


@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_internal_exception_in_process_live_audio(client):
    mock_process_live_audio.side_effect = Exception("Unexpected core logic boom!")
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "An internal error occurred: Unexpected core logic boom!" in response_data["error_message"]
    # leave_meeting might not be called if the exception happens before it in process_live_audio
    # but the handler's own try/except should catch it.
    # The current handler calls leave_meeting *after* process_live_audio_for_notion finishes or errors.
    # So, if process_live_audio_for_notion itself raises an unhandled exception that bubbles up to the handler's main try-catch,
    # then leave_meeting would NOT have been called by process_live_audio_for_notion's own finally block (if it had one),
    # NOR by the handler's main flow *after* the call to process_live_audio_for_notion.
    # The handler currently calls agent.leave_meeting() *after* the block where process_live_audio_for_notion is called.
    # This means if process_live_audio_for_notion raises an exception caught by the handler's main try-catch,
    # agent.leave_meeting() in the main flow of the handler will be skipped.
    # This is a potential bug in the handler if agent.leave_meeting() must always be called.
    # For now, testing current behavior:
    mock_zoom_agent_instance.leave_meeting.assert_not_called() # Based on current handler structure

@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio)
def test_internal_exception_before_process_live_audio(client):
    # e.g. ZoomAgent instantiation fails
    mock_zoom_agent_class.side_effect = Exception("ZoomAgent init failed")
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "An internal error occurred: ZoomAgent init failed" in response_data["error_message"]
    mock_process_live_audio.assert_not_called()
    mock_zoom_agent_instance.join_meeting.assert_not_called()
    mock_zoom_agent_instance.leave_meeting.assert_not_called()

# Test case for import failure of critical components (ZoomAgent is None)
@patch('attend_live_meeting.handler.ZoomAgent', None) # Simulate ZoomAgent = None after import attempt
@patch('attend_live_meeting.handler.process_live_audio_for_notion', new=mock_process_live_audio) # Keep this valid
def test_handler_zoom_agent_import_fails(client):
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')
    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "Agent components not loaded" in response_data["error_message"]

# Test case for import failure of critical components (process_live_audio_for_notion is None)
@patch('attend_live_meeting.handler.ZoomAgent', new=mock_zoom_agent_class)
@patch('attend_live_meeting.handler.process_live_audio_for_notion', None) # Simulate process_live_audio_for_notion = None
def test_handler_process_live_audio_import_fails(client):
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')
    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "Error"
    assert "Agent components not loaded" in response_data["error_message"]

# Note: The handler's `os.environ.setdefault` for dummy keys is for its own execution context.
# `note_utils` when imported by the handler should pick these up IF its global clients
# are initialized upon import and IF the handler reloads `note_utils` as intended.
# The tests above mock out `process_live_audio_for_notion`, so they don't directly test
# the behavior of `note_utils` with these dummy keys from this test file.
# That interaction was tested more directly in the `zoom_agent.py` __main__ block.
