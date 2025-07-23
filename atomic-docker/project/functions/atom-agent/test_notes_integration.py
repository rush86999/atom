import os
import time
import tempfile
from typing import Dict, Any, Optional

# Imports assume PYTHONPATH="/app" is set in Docker environment,
# and the 'project' directory is directly under /app.
from .. import note_utils
from . import command_handlers

# --- Test State ---
# A simple dictionary to hold state between tests, like created page IDs.
test_state: Dict[str, Any] = {
    "text_page_id": None,
    "audio_page_id": None,
    "dummy_audio_file_path": None,
    "timestamp_suffix": int(time.time()),
    "initial_title": "",
    "updated_title": "",
}


def _print_test_header(name: str):
    """Prints a standardized header for each test case."""
    print(f"\n--- {name} ---")


def _print_manual_verification(message: str):
    """Prints a standardized message for manual verification steps."""
    print(f"MANUAL VERIFICATION: {message}\n")


def _check_notion_config(response: Dict[str, Any]) -> bool:
    """Checks if a response indicates a Notion configuration issue."""
    message = response.get("message", "")
    if "Notion client not initialized" in message or "NOTION_NOTES_DATABASE_ID not configured" in message:
        print("INFO: Notion not fully configured (API token or DB ID missing). Skipping live check.")
        return True
    return False


def _create_dummy_wav_file():
    """Creates a dummy WAV file for audio tests and stores its path in the test state."""
    _print_test_header("Setup: Create Dummy Audio File")
    try:
        # A minimal but valid WAV header for a silent audio file.
        header = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x1f\x00\x00\x00\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00'
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            tmpfile.write(header)
            test_state["dummy_audio_file_path"] = tmpfile.name
        print(f"Created dummy WAV file for testing at: {test_state['dummy_audio_file_path']}")
    except Exception as e:
        print(f"Could not create dummy WAV file: {e}. Audio tests might fail early.")


def _test_create_text_note():
    """Test 1: Create a simple text note."""
    _print_test_header("Test 1: Create Text Note")
    test_state["initial_title"] = f"Test Note {test_state['timestamp_suffix']}"
    params = {
        'title': test_state["initial_title"],
        'content': "This is a test note created by the agent.",
        'source': 'simulated-text-test'
    }
    response = command_handlers.handle_create_text_note(params)
    print(f"Response: {response}")
    if response.get("status") == "success" and response.get("page_id"):
        test_state["text_page_id"] = response["page_id"]
        print(f"SUCCESS: Text note creation handled. Page ID: {test_state['text_page_id']}")
        _print_manual_verification(f"Check Notion for note '{test_state['initial_title']}'.")
    elif not _check_notion_config(response):
        print(f"FAILURE: Text note creation. Reason: {response.get('message')}\n")


def _test_get_note():
    """Test 2: Retrieve the note that was just created."""
    _print_test_header("Test 2: Get Note")
    if not test_state["text_page_id"]:
        print("SKIPPED (no page_id from creation)\n")
        return

    response = command_handlers.handle_get_note({'page_id': test_state["text_page_id"]})
    print(f"Response: {response}")
    if response.get("status") == "success" and response.get("note"):
        retrieved_title = response['note'].get('title')
        print(f"SUCCESS: Note retrieval handled. Retrieved title: '{retrieved_title}'")
        if retrieved_title != test_state["initial_title"]:
            print(f"WARNING: Retrieved title '{retrieved_title}' does not match original '{test_state['initial_title']}'")
        _print_manual_verification("Ensure retrieved details match the created note.")
    else:
        print(f"FAILURE: Note retrieval. Reason: {response.get('message')}\n")


def _test_update_note():
    """Test 3: Update the title and content of the created note."""
    _print_test_header("Test 3: Update Note")
    if not test_state["text_page_id"]:
        print("SKIPPED (no page_id from creation)\n")
        return

    test_state["updated_title"] = f"{test_state['initial_title']} (Updated)"
    params = {
        'page_id': test_state["text_page_id"],
        'title': test_state["updated_title"],
        'content': "The content of this note has been updated.",
        'linked_task_id': f"task_{test_state['timestamp_suffix']}"
    }
    response = command_handlers.handle_update_note(params)
    print(f"Response: {response}")
    if response.get("status") == "success":
        print("SUCCESS: Note update handled.")
        _print_manual_verification(f"Note should now have title '{test_state['updated_title']}' and new content.")
    else:
        print(f"FAILURE: Note update. Reason: {response.get('message')}\n")


def _test_search_notes():
    """Test 4: Search for the note using its updated title."""
    _print_test_header("Test 4: Search Notes")
    search_query = test_state.get("updated_title") or test_state.get("initial_title")
    params = {'query': search_query, 'source': 'simulated-text-test'}
    response = command_handlers.handle_search_notes(params)
    print(f"Search Response: {response}")

    if response.get("status") == "success":
        count = response.get("count", 0)
        print(f"SUCCESS: Note search handled. Found {count} note(s).")
        if test_state["text_page_id"] and any(note.get('id') == test_state["text_page_id"] for note in response.get("notes", [])):
            print("Verification: The specific test note was found in search results.")
        elif test_state["text_page_id"]:
            print(f"WARNING: The test note (ID: {test_state['text_page_id']}) was NOT found in search results.")
        _print_manual_verification("Search Notion for the query and verify results match.")
    elif not _check_notion_config(response):
        print(f"FAILURE: Note search. Reason: {response.get('message')}\n")


def _test_transcribe_audio():
    """Test 5: Test the Deepgram transcription utility directly."""
    _print_test_header("Test 5: Transcribe Audio (Deepgram Utility)")
    if not test_state.get("dummy_audio_file_path"):
        print("SKIPPED: Dummy audio file not available.\n")
        return

    result = note_utils.transcribe_audio_deepgram(test_state["dummy_audio_file_path"])
    print(f"Transcription result: '{result}'")
    message = result if isinstance(result, str) else result.get("message", "")

    if "DEEPGRAM_API_KEY not configured" in message:
        print("INFO: Deepgram API key not configured. Skipping live transcription.")
    elif message.startswith("Error:"):
        print(f"INFO: Transcription failed as expected for an empty file or due to API error: {message}")
    else:
        print("SUCCESS: Deepgram audio transcription function called.")
        if not message:
            print("INFO: Transcription is empty, which is expected for a dummy/silent audio file.")


def _test_create_audio_note():
    """Test 6: Create a note by transcribing the dummy audio file."""
    _print_test_header("Test 6: Create Audio Note (Handler)")
    if not test_state.get("dummy_audio_file_path"):
        print("SKIPPED: Dummy audio file not available.\n")
        return

    title = f"Audio Note Deepgram {test_state['timestamp_suffix']}"
    params = {
        'audio_file_path': test_state["dummy_audio_file_path"],
        'title': title,
        'source': 'simulated-audio-test'
    }
    response = command_handlers.handle_create_audio_note(params)
    print(f"Response: {response}")
    message = response.get("message", "")

    if response.get("status") == "success" and response.get("page_id"):
        test_state["audio_page_id"] = response["page_id"]
        print(f"SUCCESS: Audio note creation handled. Page ID: {test_state['audio_page_id']}")
        _print_manual_verification(f"Check Notion for note '{title}' with transcription.")
    elif "DEEPGRAM_API_KEY not configured" in message:
        print("INFO: Deepgram API key not configured. Full audio note creation cannot be verified.")
    elif not _check_notion_config(response):
        print(f"FAILURE: Audio note creation. Reason: {message}\n")


def _test_link_note():
    """Test 7: Add a linked task and event ID to the original text note."""
    _print_test_header("Test 7: Link Note")
    if not test_state["text_page_id"]:
        print("SKIPPED (no page_id from text note creation)\n")
        return

    params = {
        'page_id': test_state["text_page_id"],
        'linked_task_id': f"task_linked_{test_state['timestamp_suffix']}",
        'linked_event_id': f"event_linked_{test_state['timestamp_suffix']}"
    }
    response = command_handlers.handle_link_note(params)
    print(f"Response: {response}")
    if response.get("status") == "success":
        print("SUCCESS: Note link update handled.")
        _print_manual_verification("Check Notion note for updated Linked Task and Event IDs.")
    else:
        print(f"FAILURE: Note link update. Reason: {response.get('message')}\n")


def _test_delete_note(page_id: Optional[str], note_type: str):
    """Test 8 & 9: Delete a note and verify it's archived."""
    _print_test_header(f"Test {8 if note_type == 'Text' else 9}: Delete {note_type} Note")
    if not page_id:
        print(f"SKIPPED (no page_id from {note_type.lower()} note creation)\n")
        return

    response = command_handlers.handle_delete_note({'page_id': page_id})
    print(f"Response: {response}")
    if response.get("status") == "success":
        print(f"SUCCESS: {note_type} note deletion handled.")
        # Verification check
        get_response = command_handlers.handle_get_note({'page_id': page_id})
        if get_response.get("note", {}).get("archived"):
            print("Verification: Get call after delete shows note is archived.")
        else:
            print(f"Verification: Get call after delete returned unexpected state: {get_response}")
        _print_manual_verification(f"Check that the {note_type.lower()} note is deleted (archived).")
    else:
        print(f"FAILURE: {note_type} note deletion. Reason: {response.get('message')}\n")


def _cleanup_dummy_file():
    """Clean up the dummy audio file created during setup."""
    _print_test_header("Cleanup")
    path = test_state.get("dummy_audio_file_path")
    if path and os.path.exists(path):
        try:
            os.remove(path)
            print(f"Cleaned up dummy audio file: {path}")
        except Exception as e:
            print(f"Error cleaning up dummy audio file: {e}")


def simulate_tests():
    """Runs a sequence of simulated integration tests for note-taking features."""
    print("Starting simulated tests for note-taking features...\n")

    # Setup
    _create_dummy_wav_file()

    # Test Execution
    _test_create_text_note()
    _test_get_note()
    _test_update_note()
    _test_search_notes()
    _test_transcribe_audio()
    _test_create_audio_note()
    _test_link_note()
    _test_delete_note(test_state.get("text_page_id"), "Text")
    _test_delete_note(test_state.get("audio_page_id"), "Audio")

    # Cleanup
    _cleanup_dummy_file()

    print("\nSimulated tests completed.")
    print("IMPORTANT: For full verification, ensure API keys and database ID are correctly set as environment variables and manually check your Notion workspace for expected outcomes.")


if __name__ == "__main__":
    print("Running notes integration test script...")
    # This section allows the script to be run directly.
    # It assumes that necessary environment variables (NOTION_API_TOKEN, etc.) are set.
    simulate_tests()
