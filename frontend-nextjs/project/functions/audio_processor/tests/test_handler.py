import pytest
import json
from unittest.mock import patch, MagicMock, mock_open as unittest_mock_open, AsyncMock
import uuid # For mocking uuid.uuid4
import io # For io.BytesIO
import tempfile # For patching tempfile.mkdtemp
import shutil # For patching shutil.rmtree

# Add project root to sys.path to allow importing handler and note_utils
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) # Points to functions/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # Points to functions/audio_processor/

# Import the Flask app from the handler
# The import path depends on how Flask app is defined and project structure.
# Assuming 'app' is the Flask instance in 'handler.py'
from audio_processor.handler import app as flask_app
from audio_processor.handler import AUDIO_OUTPUT_DIR # Import for constructing expected paths

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

# ---- Tests for /stt endpoint ----

# Mock Deepgram response structure for STT
class MockDeepgramSTTResponse:
    def __init__(self, transcript):
        self.results = MagicMock()
        self.results.channels = [MagicMock()]
        self.results.channels[0].alternatives = [MagicMock()]
        self.results.channels[0].alternatives[0].transcript = transcript

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
@patch('audio_processor.handler.shutil.rmtree')
@patch('audio_processor.handler.os.remove')
@patch('audio_processor.handler.tempfile.mkdtemp')
@patch('audio_processor.handler.secure_filename', side_effect=lambda x: x) # Mock to return filename as is
@patch('audio_processor.handler.deepgram.listen.prerecorded.v("1").transcribe_file')
@patch('audio_processor.handler.open', new_callable=unittest_mock_open, read_data=b'fake_audio_data_content')
def test_stt_success(mock_open_file, mock_transcribe_file, mock_secure_filename, mock_mkdtemp, mock_os_remove, mock_shutil_rmtree, client):
    """Test successful STT transcription with file upload."""
    mock_transcribe_file.return_value = MockDeepgramSTTResponse("hello world from uploaded file")
    fake_temp_dir = "/tmp/fake_temp_dir_123"
    mock_mkdtemp.return_value = fake_temp_dir

    audio_filename = 'test_audio.wav'
    file_data = io.BytesIO(b'fake_audio_data_content')
    data = {'audio_file': (file_data, audio_filename)}

    # Mocking the file.save() part implicitly:
    # The actual file.save() will try to write to os.path.join(mock_mkdtemp.return_value, mock_secure_filename.return_value)
    # This path is then used by the 'open' call we are mocking with mock_open_file.
    # So, we need to ensure the path used by 'open' matches what file.save() would use.

    expected_temp_filepath = os.path.join(fake_temp_dir, audio_filename)

    response = client.post('/stt', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data["status"] == "success"
    assert response_data["transcription"] == "hello world from uploaded file"

    mock_secure_filename.assert_called_once_with(audio_filename)
    mock_mkdtemp.assert_called_once()
    # `file.save(temp_audio_path)` would be called. We don't mock `file.save` directly here,
    # but the subsequent `open(temp_audio_path, 'rb')` is covered by `mock_open_file`.
    # So `mock_open_file` should be called with `expected_temp_filepath`.
    mock_open_file.assert_called_once_with(expected_temp_filepath, 'rb')
    mock_transcribe_file.assert_called_once()

    mock_os_remove.assert_called_once_with(expected_temp_filepath)
    mock_shutil_rmtree.assert_called_once_with(fake_temp_dir)

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
def test_stt_no_audio_file_part(client):
    """Test STT endpoint when 'audio_file' part is missing from the request."""
    response = client.post('/stt', data={}, content_type='multipart/form-data')

    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "No audio file part in the request" in response_data["error"]

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
def test_stt_no_selected_file(client):
    """Test STT endpoint when an audio_file part is present but no file is selected (empty filename)."""
    data = {'audio_file': (io.BytesIO(b''), '')} # Empty filename
    response = client.post('/stt', data=data, content_type='multipart/form-data')

    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "No selected audio file" in response_data["error"]

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
@patch('audio_processor.handler.shutil.rmtree')
@patch('audio_processor.handler.os.remove')
@patch('audio_processor.handler.tempfile.mkdtemp')
@patch('audio_processor.handler.secure_filename', side_effect=lambda x: x)
@patch('audio_processor.handler.deepgram.listen.prerecorded.v("1").transcribe_file', side_effect=Exception("Deepgram API Error"))
@patch('audio_processor.handler.open', new_callable=unittest_mock_open, read_data=b'fake_audio_data_content')
def test_stt_deepgram_api_error(mock_open_file, mock_transcribe_file, mock_secure_filename, mock_mkdtemp, mock_os_remove, mock_shutil_rmtree, client):
    """Test STT endpoint when Deepgram API call fails, with file upload."""
    fake_temp_dir = "/tmp/fake_temp_dir_api_error"
    mock_mkdtemp.return_value = fake_temp_dir
    audio_filename = 'test_audio_api_error.wav'
    expected_temp_filepath = os.path.join(fake_temp_dir, audio_filename)

    file_data = io.BytesIO(b'fake_audio_data_for_api_error')
    data = {'audio_file': (file_data, audio_filename)}

    response = client.post('/stt', data=data, content_type='multipart/form-data')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "An unexpected error occurred during STT: Deepgram API Error" in response_data["error"]

    mock_os_remove.assert_called_once_with(expected_temp_filepath)
    mock_shutil_rmtree.assert_called_once_with(fake_temp_dir)

@patch.dict(os.environ, {}, clear=True)
@patch('audio_processor.handler.DEEPGRAM_API_KEY', None)
@patch('audio_processor.handler.deepgram', None)
# We also need to mock the file operations as they might be called before API key check,
# or in the finally block.
@patch('audio_processor.handler.shutil.rmtree')
@patch('audio_processor.handler.os.remove')
@patch('audio_processor.handler.tempfile.mkdtemp')
@patch('audio_processor.handler.secure_filename', side_effect=lambda x: x)
def test_stt_missing_api_key(mock_secure_filename, mock_mkdtemp, mock_os_remove, mock_shutil_rmtree, client):
    """Test STT endpoint when DEEPGRAM_API_KEY is missing, with file upload."""
    # Note: The current implementation checks API key *before* file operations.
    # So, mkdtemp, secure_filename, os.remove, shutil.rmtree might not be called
    # if the API key check fails early.
    # However, the finally block will attempt cleanup of temp_dir and temp_audio_path if they were created.
    # For this test, they are not expected to be created.

    audio_filename = 'test_audio_no_api_key.wav'
    file_data = io.BytesIO(b'fake_audio_data_no_api_key')
    data = {'audio_file': (file_data, audio_filename)}

    response = client.post('/stt', data=data, content_type='multipart/form-data')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Deepgram client not initialized or API key missing" in response_data["error"]

    # Assert that file operations and temp directory creation were NOT called due to early exit
    mock_mkdtemp.assert_not_called()
    mock_secure_filename.assert_not_called() # This is called only if file processing starts
    mock_os_remove.assert_not_called()
    mock_shutil_rmtree.assert_not_called()


# test_stt_success_direct_json_input - REMOVE (no longer applicable)
# test_stt_success_hasura_input_structure - REMOVE (no longer applicable)
# test_stt_non_json_request - REMOVE (no longer applicable, expecting multipart)


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
@patch('audio_processor.handler.shutil.rmtree')
@patch('audio_processor.handler.os.remove')
@patch('audio_processor.handler.tempfile.mkdtemp')
@patch('audio_processor.handler.secure_filename', side_effect=lambda x: x)
@patch('audio_processor.handler.deepgram.listen.prerecorded.v("1").transcribe_file')
@patch('audio_processor.handler.open', new_callable=unittest_mock_open, read_data=b'fake_audio_data_content')
def test_stt_deepgram_malformed_response(mock_open_file, mock_transcribe_file, mock_secure_filename, mock_mkdtemp, mock_os_remove, mock_shutil_rmtree, client):
    """Test STT with a malformed response from Deepgram, with file upload."""
    mock_transcribe_file.return_value = MagicMock(results=None) # Malformed: Missing .channels
    fake_temp_dir = "/tmp/fake_temp_dir_malformed"
    mock_mkdtemp.return_value = fake_temp_dir
    audio_filename = 'test_audio_malformed.wav'
    expected_temp_filepath = os.path.join(fake_temp_dir, audio_filename)

    file_data = io.BytesIO(b'fake_audio_data_malformed')
    data = {'audio_file': (file_data, audio_filename)}

    response = client.post('/stt', data=data, content_type='multipart/form-data')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "error"
    # The exact error message might vary depending on how the attribute access fails
    assert "An unexpected error occurred during STT" in response_data["error"]
    # This specific message might change based on actual error, but 'AttributeError' or similar is expected.
    assert "object has no attribute 'channels'" in response_data["error"]

    mock_os_remove.assert_called_once_with(expected_temp_filepath)
    mock_shutil_rmtree.assert_called_once_with(fake_temp_dir)

# ---- Tests for /tts endpoint ----
# These tests remain unchanged as /tts endpoint was not modified in this subtask.

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
@patch('audio_processor.handler.uuid.uuid4')
@patch('audio_processor.handler.open', new_callable=unittest_mock_open)
@patch('audio_processor.handler.deepgram.speak.rest.v("1").synthesize', new_callable=AsyncMock)
@patch('audio_processor.handler.os.path.exists', return_value=True) # Mocks os.path.exists for AUDIO_OUTPUT_DIR if checked in route
def test_tts_success(mock_path_exists, mock_synthesize, mock_file_open, mock_uuid4, client):
    """Test successful TTS audio generation."""
    mock_uuid_value = "test-tts-uuid"
    mock_uuid4.return_value = mock_uuid_value

    mock_audio_data = [b'chunk1_audio_data', b'chunk2_audio_data']

    async def mock_stream_generator():
        for chunk in mock_audio_data:
            yield chunk

    mock_deepgram_response = AsyncMock()
    mock_deepgram_response.stream = mock_stream_generator()
    mock_synthesize.return_value = mock_deepgram_response

    payload = {"text": "Hello, this is a test speech."}
    response = client.post('/tts', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data["status"] == "success"

    expected_filename = f"tts_{mock_uuid_value}.mp3"
    # expected_filepath = os.path.join(AUDIO_OUTPUT_DIR, expected_filename) # Path on server
    expected_audio_url = f"/generated_audio/{expected_filename}" # URL client receives
    assert response_data["audio_url"] == expected_audio_url

    mock_synthesize.assert_called_once()
    # Example: Check arguments if SpeakOptions is complex, for now, just check it was called
    args, kwargs = mock_synthesize.call_args
    assert args[0] == {"text": "Hello, this is a test speech."} # source
    # assert args[1] matches SpeakOptions if needed

    mock_file_open.assert_called_once_with(expected_filepath, 'wb')
    mock_file_handle = mock_file_open.return_value
    mock_file_handle.write.assert_any_call(b'chunk1_audio_data')
    mock_file_handle.write.assert_any_call(b'chunk2_audio_data')
    assert mock_file_handle.write.call_count == len(mock_audio_data)

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
def test_tts_missing_text(client):
    """Test TTS endpoint when 'text' input is missing."""
    response = client.post('/tts', data=json.dumps({}), content_type='application/json')

    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Missing required argument: text" in response_data["error"]

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
@patch('audio_processor.handler.deepgram.speak.rest.v("1").synthesize', new_callable=AsyncMock, side_effect=Exception("Deepgram TTS API Error"))
@patch('audio_processor.handler.uuid.uuid4') # Mock uuid to prevent file creation attempts on error
@patch('audio_processor.handler.open', new_callable=unittest_mock_open) # Mock open as well
def test_tts_deepgram_api_error(mock_open, mock_uuid, mock_synthesize, client):
    """Test TTS endpoint when Deepgram API call fails."""
    mock_uuid.return_value = "error-uuid"
    payload = {"text": "This will cause an API error."}
    response = client.post('/tts', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "An unexpected error occurred during TTS: Deepgram TTS API Error" in response_data["error"]
    mock_open.assert_not_called() # File should not be opened if API fails first

@patch.dict(os.environ, {}, clear=True)
@patch('audio_processor.handler.DEEPGRAM_API_KEY', None) # Ensure the global in handler is None
@patch('audio_processor.handler.deepgram', None) # Ensure the client in handler is None
def test_tts_missing_api_key(client):
    """Test TTS endpoint when DEEPGRAM_API_KEY is missing."""
    # Patches ensure that the checks `if not deepgram or not DEEPGRAM_API_KEY:` in handle_tts fail
    payload = {"text": "Text input with no API key."}
    response = client.post('/tts', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Deepgram client not initialized or API key missing" in response_data["error"]

@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_deepgram_key"})
@patch('audio_processor.handler.uuid.uuid4')
@patch('audio_processor.handler.open', new_callable=unittest_mock_open)
@patch('audio_processor.handler.deepgram.speak.rest.v("1").synthesize', new_callable=AsyncMock)
def test_tts_deepgram_no_stream_response(mock_synthesize, mock_file_open, mock_uuid4, client):
    """Test TTS when Deepgram returns a response without a stream."""
    mock_uuid_value = "no-stream-uuid"
    mock_uuid4.return_value = mock_uuid_value

    # Simulate Deepgram response that is not None, but response.stream is None or missing
    mock_deepgram_response = AsyncMock()
    mock_deepgram_response.stream = None # Key part: stream is None
    mock_synthesize.return_value = mock_deepgram_response

    payload = {"text": "Text that results in no stream."}
    response = client.post('/tts', data=json.dumps(payload), content_type='application/json')

    assert response.status_code == 500
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "Failed to get audio stream from Deepgram" in response_data["error"]
    mock_file_open.assert_not_called() # File should not be opened if stream is bad

@patch('audio_processor.handler.send_from_directory')
def test_serve_generated_audio_success(mock_send_from_directory, client):
    """Test successful serving of a generated audio file."""
    mock_send_from_directory.return_value = "fake file content as Flask Response" # Or a mock Flask Response object

    test_filename = "tts_some_uuid.mp3"
    response = client.get(f'/generated_audio/{test_filename}')

    assert response.status_code == 200
    # If testing actual file content: assert response.data == b"fake file content as Flask Response"
    # For now, just checking if send_from_directory was called correctly.
    mock_send_from_directory.assert_called_once_with(
        AUDIO_OUTPUT_DIR,
        test_filename,
        as_attachment=False
    )

@patch('audio_processor.handler.send_from_directory', side_effect=FileNotFoundError("Mocked File Not Found"))
def test_serve_generated_audio_not_found(mock_send_from_directory, client):
    """Test serving a non-existent audio file."""
    # This tests the try-except block in serve_generated_audio
    response = client.get('/generated_audio/nonexistentfile.mp3')

    assert response.status_code == 404
    response_data = response.get_json()
    assert response_data["status"] == "error"
    assert "File not found" in response_data["error"]
    mock_send_from_directory.assert_called_once_with(
        AUDIO_OUTPUT_DIR,
        'nonexistentfile.mp3',
        as_attachment=False
    )

# ---- Tests for /stt_stream WebSocket endpoint ----

# Helper to manage mock Deepgram LiveTranscriptionConnection and its event handlers
class MockLiveTranscriptionConnection:
    def __init__(self):
        self.handlers = {}
        self.send_buffer = []
        self.is_started = False
        self.is_finished = False
        self.start_options = None

    def on(self, event_name, callback):
        # Store the callback for the event name
        # For simplicity, LiveTranscriptionEvents.Open etc. are strings here
        if event_name not in self.handlers:
            self.handlers[event_name] = []
        self.handlers[event_name].append(callback)
        # print(f"MockLive: Registered handler for event '{event_name}'")

    def start(self, options, **kwargs):
        self.is_started = True
        self.start_options = options
        # print(f"MockLive: Connection started with options: {options}")
        # Simulate 'Open' event upon start
        if 'Open' in self.handlers:
            for handler in self.handlers['Open']:
                # The handler expects (self, open, **kwargs) - self is dg_connection, open is the event data
                handler(self, {"event": "Open", "message": "Mock Deepgram connection opened"})
        return True # Indicate success

    def send(self, data):
        self.send_buffer.append(data)
        # print(f"MockLive: Received data: {len(data)} bytes")

    def finish(self, **kwargs):
        self.is_finished = True
        # print("MockLive: Connection finished.")
        # Simulate 'Close' event upon finish
        if 'Close' in self.handlers:
             for handler in self.handlers['Close']:
                handler(self, {"event": "Close", "message": "Mock Deepgram connection closed by finish()"})


    # Methods to simulate Deepgram emitting events to our application
    def simulate_transcript_event(self, transcript_text, is_final):
        if 'Transcript' in self.handlers:
            # Construct payload similar to what Deepgram SDK provides
            # Based on handler.py: result.channel.alternatives[0].transcript and result.is_final
            payload = MagicMock() # Use MagicMock to allow attribute access
            payload.is_final = is_final
            payload.channel.alternatives = [MagicMock()]
            payload.channel.alternatives[0].transcript = transcript_text

            for handler in self.handlers['Transcript']:
                handler(self, payload) # Pass self as first arg (dg_connection)
        else:
            print("MockLive Warning: No handler registered for Transcript event")


    def simulate_error_event(self, error_message):
        if 'Error' in self.handlers:
            payload = MagicMock()
            payload.message = error_message # Or whatever structure the error object has
            for handler in self.handlers['Error']:
                handler(self, payload) # Pass self as first arg
        else:
            print("MockLive Warning: No handler registered for Error event")

    def simulate_close_event(self): # Server initiated close
        if 'Close' in self.handlers:
            for handler in self.handlers['Close']:
                handler(self, {"event": "Close", "message": "Mock Deepgram connection closed by server"})
        else:
            print("MockLive Warning: No handler registered for Close event")


@pytest.fixture
def mock_deepgram_live_connection(mocker): # Changed from mocker to patch style for consistency
    mock_connection = MockLiveTranscriptionConnection()

    # Path to DeepgramClient in the handler.py module
    # This assumes 'from deepgram import DeepgramClient' in handler.py
    # and 'deepgram = DeepgramClient(...)'
    # If 'deepgram' instance is directly used, patch its methods.
    # The current handler.py creates a 'deepgram' global instance.
    # So we patch the 'listen.live.v("1")' method of that instance.

    # Patching the global 'deepgram' instance's live transcription capability
    # This requires 'audio_processor.handler.deepgram' to be the actual DeepgramClient instance
    # If 'deepgram' is not initialized (e.g. no API key), this patch won't work as expected for those tests.
    # For tests where 'deepgram' is expected to be valid, this is okay.

    # Path where 'deepgram' instance is located and its method is called
    patcher = patch('audio_processor.handler.deepgram.listen.live.v')
    mock_live_v1 = patcher.start()
    mock_live_v1.return_value = mock_connection

    yield mock_connection # Provide the connection mock to the test

    patcher.stop()


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key_for_stt_stream"}, clear=True)
def test_stt_stream_successful_connection(client, mock_deepgram_live_connection):
    with client.websocket_connect('/stt_stream') as ws:
        # Connection itself is the test, check if Deepgram was started
        pass # Context manager handles connect/close

    assert mock_deepgram_live_connection.is_started, "Deepgram connection should have been started"
    # Check if options were passed (example option check)
    assert mock_deepgram_live_connection.start_options.model == "nova-2"
    assert mock_deepgram_live_connection.is_finished, "Deepgram connection should be finished when WebSocket closes"


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key_for_stt_stream"}, clear=True)
def test_stt_stream_audio_forwarding(client, mock_deepgram_live_connection):
    with client.websocket_connect('/stt_stream') as ws:
        test_audio_data = b'\x01\x02\x03\x04'
        ws.send(test_audio_data)
        # Add a small delay or check for send_buffer, as send is async from client perspective
        # For unit test, if send is blocking or if we can poll, it's fine.
        # Here, we assume the handler processes it quickly.
        # To be very sure, you might need a loop with timeout to check send_buffer.
        # For now, let's assume it's processed.
        # ws.receive(timeout=0.1) # Try to ensure send is processed if there was a confirmation msg

    assert mock_deepgram_live_connection.is_started
    assert len(mock_deepgram_live_connection.send_buffer) > 0, "Audio data should have been sent to Deepgram"
    assert mock_deepgram_live_connection.send_buffer[0] == test_audio_data
    assert mock_deepgram_live_connection.is_finished


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key_for_stt_stream"}, clear=True)
def test_stt_stream_transcript_forwarding(client, mock_deepgram_live_connection):
    with client.websocket_connect('/stt_stream') as ws:
        assert mock_deepgram_live_connection.is_started # Should be started by on_open

        # Simulate Deepgram sending an interim transcript
        mock_deepgram_live_connection.simulate_transcript_event("hello", False)
        received_interim = ws.receive(timeout=1)
        assert json.loads(received_interim) == {"transcript": "hello", "is_final": False}

        # Simulate Deepgram sending a final transcript
        mock_deepgram_live_connection.simulate_transcript_event("world", True)
        received_final = ws.receive(timeout=1)
        assert json.loads(received_final) == {"transcript": "world", "is_final": True}

    assert mock_deepgram_live_connection.is_finished


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key_for_stt_stream"}, clear=True)
def test_stt_stream_deepgram_error(client, mock_deepgram_live_connection):
    with client.websocket_connect('/stt_stream') as ws:
        assert mock_deepgram_live_connection.is_started

        mock_deepgram_live_connection.simulate_error_event("Test Deepgram Error")

        # The handler should send an error message over WebSocket
        received_error = ws.receive(timeout=1)
        error_data = json.loads(received_error)
        assert "error" in error_data
        assert "Test Deepgram Error" in error_data["error"]

        # Connection might be kept open by handler, or closed.
        # The current handler.py doesn't explicitly close WebSocket on Deepgram error,
        # but Deepgram itself might close, which would trigger on_close.
        # For this test, we only check the error message is sent.

    # Depending on chosen strategy, is_finished might be true or false.
    # If Deepgram error causes its own Close event, then it would be finished.
    # Let's assume for now the test ensures the error is passed to client.


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key_for_stt_stream"}, clear=True)
def test_stt_stream_client_disconnect(client, mock_deepgram_live_connection):
    # This test relies on the WebSocket context manager exiting to simulate client disconnect
    with client.websocket_connect('/stt_stream') as ws:
        assert mock_deepgram_live_connection.is_started
        # ws client disconnects when 'with' block exits

    # Check that Deepgram connection was finished
    assert mock_deepgram_live_connection.is_finished, "Deepgram connection should be finished after client disconnects"


@patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key_for_stt_stream"}, clear=True)
def test_stt_stream_deepgram_closes_connection(client, mock_deepgram_live_connection):
    with client.websocket_connect('/stt_stream') as ws:
        assert mock_deepgram_live_connection.is_started

        # Simulate Deepgram closing the connection
        mock_deepgram_live_connection.simulate_close_event()

        # Check if WebSocket receives a close frame or if receive() times out / raises error
        try:
            # Depending on flask-sock, a closed connection might raise an error on receive
            # or return a specific close message/None.
            # For now, we'll assume the client's receive will detect the closure.
            # A more direct way is to check ws.closed if the test client supports it.
            ws.receive(timeout=1) # Should ideally indicate closure
        except Exception as e: # Catching broad exception as behavior might vary
            print(f"WebSocket behavior on remote close: {e}")
            pass # Expected if connection is hard closed

    assert mock_deepgram_live_connection.is_finished, "Deepgram connection finish method should have been called"


@patch.dict(os.environ, {}, clear=True) # No DEEPGRAM_API_KEY
@patch('audio_processor.handler.DEEPGRAM_API_KEY', None) # Ensure handler sees it as None
@patch('audio_processor.handler.deepgram', None) # Simulate deepgram client not being initialized
def test_stt_stream_deepgram_not_initialized(client, mock_deepgram_live_connection):
    # mock_deepgram_live_connection fixture might not be strictly needed if 'deepgram' is None,
    # but patching it ensures it doesn't interfere.
    # The @patch for deepgram.listen.live.v might not even be hit if 'deepgram' is None.

    with client.websocket_connect('/stt_stream') as ws:
        response = ws.receive(timeout=1)
        data = json.loads(response)
        assert "error" in data
        assert "Deepgram client not initialized" in data["error"]

    # In this case, deepgram connection should not have been started
    assert not mock_deepgram_live_connection.is_started
    assert not mock_deepgram_live_connection.is_finished

# Note: LiveTranscriptionEvents.Open, etc. are part of deepgram-sdk.
# For tests, it's fine to use string representations like 'Open', 'Transcript'
# if the mock `on` method stores handlers by string names.
# If using the actual Enum members, ensure they are imported or accessible in test.
# from deepgram import LiveTranscriptionEvents # If needed for mock_connection.on
