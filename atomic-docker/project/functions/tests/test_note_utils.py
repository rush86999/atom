import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio

# Add project root to sys.path to allow importing note_utils
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Functions to test
from note_utils import (
    summarize_transcript_gpt,
    create_notion_note,
    process_live_audio_for_notion,
    init_notion # For setting up Notion client in tests
)
import requests # For requests.exceptions.HTTPError

# --- Fixtures ---

@pytest.fixture(scope="function")
def mock_env_keys_and_init_notion():
    """Sets environment variables and initializes Notion with a mock client."""
    env_vars = {
        "OPENAI_API_KEY": "test_openai_key",
        "OPENAI_API_ENDPOINT": "https://fakeopenai.com/v1/chat/completions",
        "GPT_MODEL_NAME": "gpt-test",
        "DEEPGRAM_API_KEY": "test_deepgram_key", # Though not directly tested here, good for consistency
        "NOTION_API_TOKEN": "test_notion_token",
        "NOTION_NOTES_DATABASE_ID": "test_db_id"
    }
    with patch.dict(os.environ, env_vars):
        # This patch ensures that when init_notion is called, it uses a MagicMock for the Notion Client
        with patch('note_utils.Client', new_callable=MagicMock) as MockNotionClientGlobal:
            # Configure the instance that will be created by init_notion
            mock_notion_instance = MockNotionClientGlobal.return_value
            init_notion(api_token="test_notion_token", database_id="test_db_id")
            # Yield the instance if tests need to configure its methods like pages.create
            yield mock_notion_instance


@pytest.fixture
def sample_transcript_text():
    return "This is a test transcript. It discusses important project updates and action items. Decision 1 was made. John to follow up by Friday."

# --- Tests for summarize_transcript_gpt ---

def test_summarize_transcript_gpt_success_structured(mock_env_keys_and_init_notion, sample_transcript_text):
    mock_response = MagicMock()
    mock_response.status_code = 200
    expected_summary = "Test summary."
    expected_decisions = ["Decision 1.", "Decision 2."]
    expected_action_items = ["Action item 1.", "Action item 2 for Bob."]

    gpt_output_dict = {
        "summary": expected_summary,
        "decisions": expected_decisions,
        "action_items": expected_action_items
    }
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(gpt_output_dict)}}]
    }

    with patch('requests.post', return_value=mock_response) as mock_post:
        result = summarize_transcript_gpt(sample_transcript_text, openai_api_key_param="test_openai_key")

        mock_post.assert_called_once()
        assert result["status"] == "success"
        data = result["data"]
        assert data["summary"] == expected_summary
        assert data["decisions"] == expected_decisions
        assert data["action_items"] == expected_action_items
        assert data["key_points"] == "- Action item 1.\n- Action item 2 for Bob."

def test_summarize_transcript_gpt_missing_fields(mock_env_keys_and_init_notion, sample_transcript_text):
    mock_response = MagicMock()
    mock_response.status_code = 200
    gpt_output_dict = {"summary": "Only summary provided."}
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(gpt_output_dict)}}]
    }
    with patch('requests.post', return_value=mock_response):
        result = summarize_transcript_gpt(sample_transcript_text, openai_api_key_param="test_openai_key")
        assert result["status"] == "success"
        data = result["data"]
        assert data["summary"] == "Only summary provided."
        assert data["decisions"] == []
        assert data["action_items"] == []
        assert data["key_points"] == ""

def test_summarize_transcript_gpt_invalid_list_fields(mock_env_keys_and_init_notion, sample_transcript_text):
    mock_response = MagicMock()
    mock_response.status_code = 200
    gpt_output_dict = {
        "summary": "Summary present.",
        "decisions": "This should be a list",
        "action_items": {"item": "This should also be a list"}
    }
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(gpt_output_dict)}}]
    }
    with patch('requests.post', return_value=mock_response):
        result = summarize_transcript_gpt(sample_transcript_text, openai_api_key_param="test_openai_key")
        assert result["status"] == "success"
        data = result["data"]
        assert data["summary"] == "Summary present."
        assert data["decisions"] == []
        assert data["action_items"] == []
        assert data["key_points"] == ""

def test_summarize_transcript_gpt_empty_transcript_input(mock_env_keys_and_init_notion):
    result = summarize_transcript_gpt("", openai_api_key_param="test_openai_key")
    assert result["status"] == "success"
    data = result["data"]
    assert data["summary"] == "Transcript was empty."
    assert data["decisions"] == []
    assert data["action_items"] == []
    assert data["key_points"] == ""

def test_summarize_transcript_gpt_api_error(mock_env_keys_and_init_notion, sample_transcript_text):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")

    with patch('requests.post', return_value=mock_response):
        result = summarize_transcript_gpt(sample_transcript_text, openai_api_key_param="test_openai_key")
        assert result["status"] == "error"
        assert "OpenAI API request error" in result["message"]

def test_summarize_transcript_gpt_no_api_key(sample_transcript_text): # No mock_env_keys
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        result = summarize_transcript_gpt(sample_transcript_text) # Use env key
        assert result["status"] == "error"
        assert "OpenAI API key not set or invalid" in result["message"]

# --- Tests for create_notion_note ---

def test_create_notion_note_with_decisions_and_actions(mock_env_keys_and_init_notion):
    # mock_env_keys_and_init_notion has already initialized note_utils.notion with a MagicMock instance
    mock_notion_instance = mock_env_keys_and_init_notion # The fixture yields the mocked notion instance
    mock_pages_create = mock_notion_instance.pages.create
    mock_pages_create.return_value = {"id": "new_page_id", "url": "https://notion.so/new_page_id"}

    decisions_list = ["Decision Alpha", "Decision Beta"]
    action_items_list = ["Action Item 1", "Action Item 2"]

    result = create_notion_note(
        title="Test Note",
        content="Sample content.",
        decisions=decisions_list,
        action_items=action_items_list
    )

    assert result["status"] == "success"
    assert result["data"]["page_id"] == "new_page_id"
    mock_pages_create.assert_called_once()

    args, kwargs = mock_pages_create.call_args
    properties = kwargs["properties"]

    assert "Decisions Logged" in properties
    assert properties["Decisions Logged"]["rich_text"][0]["text"]["content"] == "- Decision Alpha\n- Decision Beta"

    assert "Action Items Logged" in properties
    assert properties["Action Items Logged"]["rich_text"][0]["text"]["content"] == "- Action Item 1\n- Action Item 2"

def test_create_notion_note_empty_decisions_actions(mock_env_keys_and_init_notion):
    mock_notion_instance = mock_env_keys_and_init_notion
    mock_pages_create = mock_notion_instance.pages.create
    mock_pages_create.return_value = {"id": "new_page_id2"}

    result = create_notion_note(
        title="Test Note Empty",
        content="Sample content.",
        decisions=[],
        action_items=None
    )
    assert result["status"] == "success"
    mock_pages_create.assert_called_once()
    args, kwargs = mock_pages_create.call_args
    properties = kwargs["properties"]

    assert "Decisions Logged" not in properties
    assert "Action Items Logged" not in properties

# --- Tests for process_live_audio_for_notion ---

class MockAsyncIterator: # Helper for mocking async iterators
    def __init__(self, items):
        self._items = items
        self._iter = iter(self._items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

@pytest.mark.asyncio
async def test_process_live_audio_for_notion_data_flow(mock_env_keys_and_init_notion):
    # mock_env_keys_and_init_notion sets up env vars and initializes Notion client (mocked)

    mock_platform_module = MagicMock()
    mock_platform_module.start_audio_capture = MagicMock(return_value=MockAsyncIterator([b"chunk1", b"chunk2"]))
    mock_platform_module.stop_audio_capture = MagicMock()

    with patch('note_utils.transcribe_audio_deepgram_stream', new_callable=AsyncMock) as mock_transcribe, \
         patch('note_utils.summarize_transcript_gpt') as mock_summarize, \
         patch('note_utils.create_notion_note') as mock_create_note_func: # Mock the function, not the client method here

        mock_transcribe.return_value = {"status": "success", "data": {"full_transcript": "Live transcript."}}

        expected_summary_text = "Live summary text."
        expected_decisions_list = ["Live Decision 1", "Live Decision 2"]
        expected_action_items_list = ["Live Action 1", "Live Action 2"]
        expected_key_points_string = "- Live Action 1\n- Live Action 2"

        mock_summarize.return_value = {
            "status": "success",
            "data": {
                "summary": expected_summary_text,
                "decisions": expected_decisions_list,
                "action_items": expected_action_items_list,
                "key_points": expected_key_points_string
            }
        }
        # This mock is for the create_notion_note FUNCTION, not the client method directly
        mock_create_note_func.return_value = {"status": "success", "data": {"page_id": "live_page_123", "url": "http://notion.live"}}

        result = await process_live_audio_for_notion(
            platform_module=mock_platform_module,
            meeting_id="live_meeting_xyz",
            notion_note_title="Live Meeting Note Title",
            deepgram_api_key="dg_key_param", # Passed as param
            openai_api_key="oai_key_param"    # Passed as param
            # notion_db_id, notion_source, etc., will use defaults or values from mock_env_keys if relevant
        )

        assert result["status"] == "success"
        assert result["data"]["notion_page_id"] == "live_page_123"

        mock_platform_module.start_audio_capture.assert_called_once_with("live_meeting_xyz")
        mock_transcribe.assert_called_once() # Basic check, arg checking can be complex for streams
        mock_summarize.assert_called_once_with("Live transcript.", openai_api_key_param="oai_key_param")

        mock_create_note_func.assert_called_once()
        call_args = mock_create_note_func.call_args
        assert call_args.kwargs["title"] == "Live Meeting Note Title"
        assert call_args.kwargs["summary"] == expected_summary_text
        assert call_args.kwargs["decisions"] == expected_decisions_list # Key assertion
        assert call_args.kwargs["action_items"] == expected_action_items_list # Key assertion
        assert call_args.kwargs["key_points"] == expected_key_points_string
        assert call_args.kwargs["transcription"] == "Live transcript."

# Fallback for requests.exceptions.HTTPError if requests is not installed
# This was in the original file, keeping for consistency, though test environment should have dependencies.
if not hasattr(requests, 'exceptions') or not hasattr(requests.exceptions, 'HTTPError'):
    class RequestsHTTPError(Exception): pass
    if 'requests' not in sys.modules:
        mock_requests_module = MagicMock()
        sys.modules['requests'] = mock_requests_module
    if not hasattr(sys.modules['requests'], 'exceptions'):
        sys.modules['requests'].exceptions = MagicMock()
    sys.modules['requests'].exceptions.HTTPError = RequestsHTTPError
