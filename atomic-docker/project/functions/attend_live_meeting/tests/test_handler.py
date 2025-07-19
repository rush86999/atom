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

@pytest.fixture
def mock_kafka_producer():
    with patch('attend_live_meeting.handler.KafkaProducer') as mock_producer_class:
        mock_producer_instance = MagicMock()
        mock_producer_class.return_value = mock_producer_instance
        yield mock_producer_instance

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
        },
        "handler_input": {
            "notion_api_token": "test_notion_token",
            "deepgram_api_key": "test_deepgram_key",
            "openai_api_key": "test_openai_key",
            "zoom_sdk_key": "test_zoom_sdk_key",
            "zoom_sdk_secret": "test_zoom_sdk_secret"
        }
    }
    if overrides:
        if 'action_input' in overrides:
            payload['action_input'].update(overrides['action_input'])
        if 'session_variables' in overrides:
            payload['session_variables'].update(overrides['session_variables'])
        if 'handler_input' in overrides:
            payload['handler_input'].update(overrides['handler_input'])
    return payload

# Using patch decorator on each test function that needs these mocks
def test_successful_zoom_call(client, mock_kafka_producer):
    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    response_data = response.get_json()
    print("Response Data:", response_data) # For debugging in case of failure

    assert response.status_code == 202
    assert response_data["ok"] == True
    assert "taskId" in response_data["data"]

    mock_kafka_producer.send.assert_called_once()
    # Optionally, assert the content of the sent message
    sent_value = mock_kafka_producer.send.call_args[1]['value']
    assert sent_value['platform'] == 'zoom'
    assert sent_value['meetingIdentifier'] == 'test_meeting_123'

def test_missing_parameters(client, mock_kafka_producer):
    # Example: missing meeting_identifier
    invalid_payload = get_valid_payload()
    del invalid_payload["action_input"]["meeting_identifier"]
    response = client.post('/', data=json.dumps(invalid_payload), content_type='application/json')

    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["ok"] == False
    assert "Missing required parameters" in response_data["error"]["message"]
    assert "meeting_identifier" in response_data["error"]["message"]

    # Example: missing user_id (session variable)
    invalid_payload_user = get_valid_payload()
    del invalid_payload_user["session_variables"]["x-hasura-user-id"]
    response_user = client.post('/', data=json.dumps(invalid_payload_user), content_type='application/json')
    assert response_user.status_code == 400
    response_data_user = response_user.get_json()
    assert "Missing required parameters" in response_data_user["error"]["message"]
    assert "user_id" in response_data_user["error"]["message"]

@patch('attend_live_meeting.handler.get_kafka_producer')
def test_kafka_publish_failure(mock_get_kafka_producer, client):
    mock_producer_instance = MagicMock()
    mock_producer_instance.send.side_effect = Exception("Kafka connection failed")
    mock_get_kafka_producer.return_value = mock_producer_instance

    response = client.post('/', data=json.dumps(get_valid_payload()), content_type='application/json')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["ok"] == False
    assert "An unexpected error occurred during Kafka publish" in response_data["error"]["message"]
    assert "Kafka connection failed" in response_data["error"]["message"]

# Note: The handler's `os.environ.setdefault` for dummy keys is for its own execution context.
# `note_utils` when imported by the handler should pick these up IF its global clients
# are initialized upon import and IF the handler reloads `note_utils` as intended.
# The tests above mock out `process_live_audio_for_notion`, so they don't directly test
# the behavior of `note_utils` with these dummy keys from this test file.
# That interaction was tested more directly in the `zoom_agent.py` __main__ block.
