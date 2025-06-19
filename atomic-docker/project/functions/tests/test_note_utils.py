import os
import pytest
from unittest.mock import patch, MagicMock
import json

# Add project root to sys.path to allow importing note_utils
# This might need adjustment based on how tests are run in the actual environment
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Functions to test (assuming they are in note_utils.py directly in functions folder)
from note_utils import summarize_transcript_gpt, process_audio_for_note #, transcribe_audio_deepgram


# --- Tests for summarize_transcript_gpt ---

@pytest.fixture
def mock_env_openai_key():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test_api_key", "OPENAI_API_ENDPOINT": "https://fakeapi.com/v1/chat/completions", "GPT_MODEL_NAME": "gpt-test"}):
        yield

@pytest.fixture
def sample_transcript():
    return "This is a test transcript. It discusses important project updates and action items."

def test_summarize_transcript_gpt_success(mock_env_openai_key, sample_transcript):
    mock_response = MagicMock()
    mock_response.status_code = 200
    # The content from the API is a JSON string, which itself contains a JSON object for summary and key_points
    expected_summary = "Test summary of the transcript."
    expected_key_points_list = ["Point 1", "Point 2"]
    api_content_json_str = json.dumps({
        "summary": expected_summary,
        "key_points": expected_key_points_list
    })
    mock_response.json.return_value = {
        "choices": [{
            "message": {"content": api_content_json_str}
        }]
    }

    with patch('requests.post', return_value=mock_response) as mock_post:
        summary, key_points_str = summarize_transcript_gpt(sample_transcript)

        mock_post.assert_called_once()
        # print(mock_post.call_args.kwargs['json']) # For debugging the payload
        assert summary == expected_summary
        assert key_points_str == "- Point 1\n- Point 2"

def test_summarize_transcript_gpt_api_error(mock_env_openai_key, sample_transcript):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")

    with patch('requests.post', return_value=mock_response) as mock_post:
        summary, key_points = summarize_transcript_gpt(sample_transcript)
        assert summary is None
        assert key_points is None

def test_summarize_transcript_gpt_invalid_json_content(mock_env_openai_key, sample_transcript):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "This is not valid JSON"}}]
    }
    with patch('requests.post', return_value=mock_response) as mock_post:
        summary, key_points = summarize_transcript_gpt(sample_transcript)
        assert summary is None
        assert key_points is None

def test_summarize_transcript_gpt_unexpected_structure(mock_env_openai_key, sample_transcript):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"unexpected_key": "unexpected_value"} # Missing 'choices'
    with patch('requests.post', return_value=mock_response) as mock_post:
        summary, key_points = summarize_transcript_gpt(sample_transcript)
        assert summary is None
        assert key_points is None

def test_summarize_transcript_gpt_malformed_parsed_content(mock_env_openai_key, sample_transcript):
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Correct outer JSON, but inner content JSON is malformed for expectations
    api_content_json_str = json.dumps({
        "summary_wrong_key": "Some summary",
        "key_points_list": ["Point A"]
    })
    mock_response.json.return_value = {
        "choices": [{"message": {"content": api_content_json_str}}]
    }
    with patch('requests.post', return_value=mock_response) as mock_post:
        summary, key_points = summarize_transcript_gpt(sample_transcript)
        assert summary is None
        assert key_points is None


def test_summarize_transcript_gpt_no_api_key(sample_transcript):
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}): # Simulate no API key
        summary, key_points = summarize_transcript_gpt(sample_transcript)
        assert summary is None
        assert key_points is None

def test_summarize_transcript_gpt_empty_transcript(mock_env_openai_key):
    summary, key_points = summarize_transcript_gpt("")
    assert summary is None
    assert key_points is None
    summary, key_points = summarize_transcript_gpt("   ")
    assert summary is None
    assert key_points is None


# --- Placeholder for process_audio_for_note tests ---
# These will be more complex due to multiple mocks

@patch('note_utils.transcribe_audio_deepgram')
@patch('note_utils.summarize_transcript_gpt')
@patch('note_utils.create_notion_note')
@patch('note_utils.update_notion_note')
def test_process_audio_for_note_create_new_success(
    mock_update_notion_note, mock_create_notion_note,
    mock_summarize_transcript_gpt, mock_transcribe_audio_deepgram
):
    mock_transcribe_audio_deepgram.return_value = "Test transcription."
    mock_summarize_transcript_gpt.return_value = ("Test summary.", "Test key points.")
    mock_create_notion_note.return_value = "new_note_123"

    audio_path = "dummy/audio.mp3"
    title = "New Audio Note"
    content = "Initial content for note."
    source = "Test case"

    result = process_audio_for_note(
        audio_file_path=audio_path,
        title=title,
        content=content,
        source=source
    )

    mock_transcribe_audio_deepgram.assert_called_once_with(audio_path)
    mock_summarize_transcript_gpt.assert_called_once_with("Test transcription.")
    mock_create_notion_note.assert_called_once_with(
        title=title,
        content=content,
        source=source,
        transcription="Test transcription.",
        summary="Test summary.",
        key_points="Test key points.",
        linked_task_id=None, # Ensuring defaults are passed
        linked_event_id=None,
        audio_file_link=None # Assuming not passed if not provided
    )
    mock_update_notion_note.assert_not_called()
    assert result == "new_note_123"

@patch('note_utils.transcribe_audio_deepgram')
@patch('note_utils.summarize_transcript_gpt')
@patch('note_utils.create_notion_note')
@patch('note_utils.update_notion_note')
def test_process_audio_for_note_update_existing_success(
    mock_update_notion_note, mock_create_notion_note,
    mock_summarize_transcript_gpt, mock_transcribe_audio_deepgram
):
    existing_note_id = "existing_note_456"
    mock_transcribe_audio_deepgram.return_value = "Updated transcription."
    mock_summarize_transcript_gpt.return_value = ("Updated summary.", "Updated key points.")
    mock_update_notion_note.return_value = True # Assuming update_notion_note returns boolean for success

    audio_path = "dummy/audio_update.mp3"

    result = process_audio_for_note(
        audio_file_path=audio_path,
        note_id=existing_note_id
        # title, content, source etc., are optional for update in process_audio_for_note
    )

    mock_transcribe_audio_deepgram.assert_called_once_with(audio_path)
    mock_summarize_transcript_gpt.assert_called_once_with("Updated transcription.")
    mock_update_notion_note.assert_called_once_with(
        page_id=existing_note_id,
        summary="Updated summary.",
        key_points="Updated key points.",
        transcription="Updated transcription."
        # title=None, content=None, linked_task_id=None, linked_event_id=None are default in update_notion_note
    )
    mock_create_notion_note.assert_not_called()
    assert result == existing_note_id


@patch('note_utils.transcribe_audio_deepgram')
def test_process_audio_for_note_transcription_fails(mock_transcribe_audio_deepgram):
    mock_transcribe_audio_deepgram.return_value = "Error: Transcription failed"

    result = process_audio_for_note(audio_file_path="dummy/audio.mp3")

    assert result == "Transcription failed: Error: Transcription failed"
    mock_transcribe_audio_deepgram.assert_called_once_with("dummy/audio.mp3")

@patch('note_utils.transcribe_audio_deepgram')
@patch('note_utils.summarize_transcript_gpt')
@patch('note_utils.create_notion_note')
def test_process_audio_for_note_summarization_fails(
    mock_create_notion_note, mock_summarize_transcript_gpt, mock_transcribe_audio_deepgram
):
    mock_transcribe_audio_deepgram.return_value = "Good transcription."
    mock_summarize_transcript_gpt.return_value = (None, None) # Summarization returns None
    mock_create_notion_note.return_value = "new_note_789"

    audio_path = "dummy/audio_no_summary.mp3"
    title = "Note without summary"

    result = process_audio_for_note(audio_file_path=audio_path, title=title)

    mock_create_notion_note.assert_called_once_with(
        title=title,
        content="", # Default
        source="Audio Upload", # Default
        transcription="Good transcription.",
        summary=None, # Passed as None
        key_points=None, # Passed as None
        linked_task_id=None,
        linked_event_id=None,
        audio_file_link=None
    )
    assert result == "new_note_789"


# It's good practice to import requests inside the test function or fixture
# where it's needed, especially if the module itself doesn't import it at the top level.
# However, for mocking 'requests.post', it's fine if it's globally available for the mock target.
# For this structure, I'll assume 'requests' would be imported in note_utils.py if needed.
# For test_summarize_transcript_gpt_api_error, we need requests.exceptions.HTTPError
try:
    import requests.exceptions
except ImportError:
    # Create a dummy exception if requests is not installed in the test environment
    # This allows tests to be defined but they might not run correctly if requests is truly missing
    # when note_utils.summarize_transcript_gpt actually tries to use it.
    class RequestsHTTPError(Exception): pass
    if 'requests' not in sys.modules: # Avoid overriding if requests was imported by other means
        # Mocking the module itself if it's not available
        mock_requests_module = MagicMock()
        mock_requests_module.exceptions.HTTPError = RequestsHTTPError
        sys.modules['requests'] = mock_requests_module
        sys.modules['requests.exceptions'] = mock_requests_module.exceptions

# Minimal test for transcribe_audio_deepgram (can be expanded)
@patch('note_utils.DeepgramClient')
@patch('os.path.exists')
def test_transcribe_audio_deepgram_basic(mock_os_exists, MockDeepgramClient):
    # Setup DeepgramClient mock
    mock_deepgram_instance = MockDeepgramClient.return_value
    mock_transcribe_method = mock_deepgram_instance.listen.prerecorded.v("1").transcribe_file
    mock_transcribe_method.return_value = MagicMock(
        results=MagicMock(
            channels=[
                MagicMock(alternatives=[MagicMock(transcript="Deepgram test transcript")])
            ]
        )
    )
    mock_os_exists.return_value = True # File exists

    # Simulate DEEPGRAM_API_KEY being set
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "fake_dg_key"}):
        # Re-initialize deepgram_client within note_utils if it's initialized at module level based on env var
        # For simplicity, assuming note_utils.deepgram_client is accessible or re-initialized.
        # If note_utils.py initializes deepgram_client at import time, this test needs careful setup
        # or the function should take the client as an argument, or re-initialize it.
        # For this test, we'll assume the function can get a working client if API key is set.
        # This part is tricky without seeing the exact DeepgramClient initialization in note_utils.py
        # Let's assume note_utils.transcribe_audio_deepgram internally gets/checks the client.

        # If note_utils.py initializes deepgram_client globally like:
        # deepgram_client = DeepgramClient(DEEPGRAM_API_KEY) if DEEPGRAM_API_KEY else None
        # We need to reload note_utils or patch note_utils.deepgram_client itself.
        # Patching note_utils.deepgram_client to be our mock_deepgram_instance
        with patch('note_utils.deepgram_client', mock_deepgram_instance):
             from note_utils import transcribe_audio_deepgram # Re-import or ensure it uses the patched client
             transcript = transcribe_audio_deepgram("dummy/audio.wav")
             assert transcript == "Deepgram test transcript"
             mock_os_exists.assert_called_once_with("dummy/audio.wav")
             # Check if transcribe_file was called (payload might be complex to assert fully)
             mock_transcribe_method.assert_called_once()

def test_transcribe_audio_deepgram_no_api_key():
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": ""}):
        # Similar to above, this depends on how deepgram_client is handled.
        # Assuming the function checks the key or client internally.
        with patch('note_utils.deepgram_client', None): # Ensure client is None
            from note_utils import transcribe_audio_deepgram
            result = transcribe_audio_deepgram("dummy/audio.wav")
            assert "Error: Deepgram client not initialized" in result or "DEEPGRAM_API_KEY not configured" in result

@patch('os.path.exists')
def test_transcribe_audio_deepgram_file_not_found(mock_os_exists):
    mock_os_exists.return_value = False
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "fake_dg_key"}):
        with patch('note_utils.deepgram_client', MagicMock()): # Provide a dummy client
            from note_utils import transcribe_audio_deepgram
            result = transcribe_audio_deepgram("non_existent_file.wav")
            assert "Error: Audio file not found" in result
            mock_os_exists.assert_called_once_with("non_existent_file.wav")

# (Need to import requests for the HTTPError in summarize_transcript_gpt_api_error)
import requests
# This should ideally be at the top, but placed here to ensure the dummy exception logic
# for requests.exceptions.HTTPError is processed if 'requests' isn't installed.
# If 'requests' is a hard dependency for the project, it should be in requirements.txt
# and this try-except for HTTPError might be simplified.

# Ensure the dummy exception is used if requests wasn't really imported
if not hasattr(requests, 'exceptions') or not hasattr(requests.exceptions, 'HTTPError'):
    # This means requests was probably mocked, so we use the dummy from earlier
    class RequestsHTTPError(Exception): pass
    requests.exceptions = MagicMock()
    requests.exceptions.HTTPError = RequestsHTTPError
