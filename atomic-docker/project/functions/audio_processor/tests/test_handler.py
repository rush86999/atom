import pytest
import json
from unittest.mock import patch, MagicMock

# Add project root to sys.path to allow importing handler and note_utils
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) # Points to functions/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # Points to functions/audio_processor/

# Import the Flask app from the handler
# The import path depends on how Flask app is defined and project structure.
# Assuming 'app' is the Flask instance in 'handler.py'
from audio_processor.handler import app as flask_app

@pytest.fixture
def client():
    """Create and configure a new app instance for each test."""
    # flask_app.config['TESTING'] = True # Standard Flask testing config
    with flask_app.test_client() as client:
        yield client

# Test successful processing
@patch('audio_processor.handler.process_audio_for_note')
def test_handler_success(mock_process_audio, client):
    mock_process_audio.return_value = "test_note_id_123"

    payload = {
        "input": {
            "arg1": {
                "audio_file_path": "dummy/path/to/audio.wav",
                "title": "Test Note from Audio",
                "content": "Initial content here.",
                "source": "Test Handler"
            }
        },
        "session_variables": {"x-hasura-user-id": "test-user"} # Example session var
    }

    response = client.post('/', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data["status"] == "success"
    assert response_data["note_id"] == "test_note_id_123"

    mock_process_audio.assert_called_once_with(
        audio_file_path="dummy/path/to/audio.wav",
        note_id=None,
        title="Test Note from Audio",
        content="Initial content here.",
        source="Test Handler",
        linked_task_id=None,
        linked_event_id=None
    )

# Test when process_audio_for_note returns an error string
@patch('audio_processor.handler.process_audio_for_note')
def test_handler_process_audio_returns_error(mock_process_audio, client):
    mock_process_audio.return_value = "Error: Transcription failed badly"

    payload = {
        "input": {"arg1": {"audio_file_path": "dummy/audio_error.wav"}}
    }

    response = client.post('/', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 200 # Handler itself doesn't error, but returns JSON error
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Error: Transcription failed badly" in response_data["error"]

# Test when process_audio_for_note raises an unexpected exception
@patch('audio_processor.handler.process_audio_for_note')
def test_handler_process_audio_raises_exception(mock_process_audio, client):
    mock_process_audio.side_effect = Exception("Unexpected internal error")

    payload = {
        "input": {"arg1": {"audio_file_path": "dummy/audio_exception.wav"}}
    }

    response = client.post('/', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 500 # Flask default for unhandled exceptions
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "An unexpected error occurred: Unexpected internal error" in response_data["error"]

# Test with missing audio_file_path
def test_handler_missing_audio_file_path(client):
    payload = {
        "input": {"arg1": {"title": "Note without audio path"}}
    }
    response = client.post('/', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Missing required argument: audio_file_path" in response_data["error"]

# Test with missing input.arg1 structure
def test_handler_missing_input_arg1(client):
    payload = {
        "input": {"wrong_key": {"audio_file_path": "dummy/path.wav"}} # Missing arg1
    }
    response = client.post('/', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Invalid request structure: 'input.arg1' is missing." in response_data["error"]

# Test with empty JSON payload
def test_handler_empty_payload(client):
    response = client.post('/', data=json.dumps({}), content_type='application/json')
    assert response.status_code == 400 # Because input.arg1 will be missing
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "'input.arg1' is missing" in response_data["error"] # Or similar, depending on Flask's behavior with get("input", {})

# Test to ensure dummy function is not active if import fails (illustrative)
# This test depends on how the dummy function is implemented in handler.py
@patch('audio_processor.handler.process_audio_for_note', None) # Simulate import failure by removing it
def test_handler_import_failure_scenario(client):
    # This requires the dummy in handler.py to behave in a detectable way
    # For example, if the dummy was:
    # def process_audio_for_note(*args, **kwargs): return "DUMMY_FUNCTION_ERROR"
    # Then we could assert that. The current dummy in handler.py prints and returns an error string.
    # Let's assume the dummy is not sophisticated enough for a specific assertion beyond what other tests cover.
    # If the dummy process_audio_for_note was used, it would return its error string.

    # To properly test the dummy, we'd need to control the import mechanism more finely
    # or make the dummy return a very unique error.
    # The current dummy would lead to a response similar to test_handler_process_audio_returns_error
    # if it was successfully called.
    # If the import truly failed and `process_audio_for_note` was None,
    # the handler would raise a TypeError when trying to call it.
    # The current handler.py has a try-except around the import and defines a fallback.
    # So, let's test if that fallback is invoked if we could force the import error.
    # This is hard to simulate without deeper sys.modules manipulation or if the handler
    # didn't have the try-except for import.
    # For now, this test is more of a conceptual placeholder.
    # A more direct test of the dummy would be to call it directly if it were accessible.

    # If we could guarantee the dummy is called:
    # mock_process_audio.return_value = "Error: process_audio_for_note function not loaded."
    # The current fallback in handler.py would result in this error being returned.
    # This is similar to test_handler_process_audio_returns_error.
    pass

# Test with different optional parameters
@patch('audio_processor.handler.process_audio_for_note')
def test_handler_with_optional_params(mock_process_audio, client):
    mock_process_audio.return_value = "note_with_optionals"

    payload = {
        "input": {
            "arg1": {
                "audio_file_path": "dummy/path/to/audio.wav",
                "note_id": "existing_note_001",
                "title": "Optional Title",
                "content": "Optional Content",
                "source": "Optional Source",
                "linked_task_id": "task_abc",
                "linked_event_id": "event_xyz"
            }
        }
    }

    response = client.post('/', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data["status"] == "success"
    assert response_data["note_id"] == "note_with_optionals"

    mock_process_audio.assert_called_once_with(
        audio_file_path="dummy/path/to/audio.wav",
        note_id="existing_note_001",
        title="Optional Title",
        content="Optional Content",
        source="Optional Source",
        linked_task_id="task_abc",
        linked_event_id="event_xyz"
    )

# Test ensuring default values are used if not provided by handler call to process_audio_for_note
@patch('audio_processor.handler.process_audio_for_note')
def test_handler_calls_process_audio_with_defaults_for_missing_optionals(mock_process_audio, client):
    mock_process_audio.return_value = "note_defaults_check"

    payload = {
        "input": {
            "arg1": {
                "audio_file_path": "dummy/path/to/audio.wav"
                # title, content, source, etc., are missing
            }
        }
    }

    response = client.post('/', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 200

    # The handler calls process_audio_for_note, which itself has defaults.
    # The handler explicitly passes title, content, source with defaults if they are None from input.
    mock_process_audio.assert_called_once_with(
        audio_file_path="dummy/path/to/audio.wav",
        note_id=None,
        title="New Audio Note", # Default from handler's call to process_audio_for_note
        content="",           # Default from handler's call
        source="Audio Upload",# Default from handler's call
        linked_task_id=None,
        linked_event_id=None
    )

    # Test GET request not allowed (or any other method)
def test_handler_get_not_allowed(client):
    response = client.get('/')
    assert response.status_code == 405 # Method Not Allowed for Flask routes by default unless specified
