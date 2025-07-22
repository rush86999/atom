import os


import time
import tempfile # For creating a dummy audio file

# Imports assume PYTHONPATH="/app" is set in Docker environment,
# and the 'project' directory is directly under /app.
from .. import note_utils
from . import command_handlers

# --- Configuration for Testing ---
# To run these tests, you would need to:
# 1. Set up a Notion database for notes and get its ID.
# 2. Create a Notion API integration token.
# 3. Get a Deepgram API key.
# 4. Set the following environment variables:
#    NOTION_API_TOKEN=<your_notion_api_token>
#    NOTION_NOTES_DATABASE_ID=<your_notion_database_id>
#    DEEPGRAM_API_KEY=<your_deepgram_api_key>
# 5. For a real audio test, place a sample audio file (e.g., "sample.wav" or "sample.mp3")
#    that Deepgram can process. A very short, clear one is best for testing.

def simulate_tests():
    print("Starting simulated tests for note-taking features (with Deepgram)...\n")

    # Test Data
    timestamp_suffix = int(time.time())
    sample_note_title = f"Test Note {timestamp_suffix}"
    sample_note_content = "This is a test note created by the agent for general testing."
    created_page_id = None
    created_audio_page_id = None
    updated_title = ""

    # --- Helper: Create a dummy WAV file for audio tests ---
    dummy_audio_file_path = None
    try:
        # Create a very short, minimal WAV file.
        header = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x1f\x00\x00\x00\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00'
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            tmpfile.write(header)
            dummy_audio_file_path = tmpfile.name
        print(f"Created dummy WAV file for testing at: {dummy_audio_file_path}")
    except Exception as e:
        print(f"Could not create dummy WAV file: {e}. Audio note creation test might fail early.")


    # --- Test 1: Create Text Note (Handler) ---
    print("\n--- Test 1: Create Text Note ---")
    create_params = {
        'title': sample_note_title,
        'content': sample_note_content,
        'source': 'simulated-text-test'
    }
    response = command_handlers.handle_create_text_note(create_params)
    print(f"Response: {response}")
    if response.get("status") == "success" and response.get("page_id"):
        created_page_id = response["page_id"]
        print(f"SUCCESS: Text note creation handled. Page ID: {created_page_id}")
        print(f"MANUAL VERIFICATION: Check Notion for note '{sample_note_title}'.\n")
    elif "Notion client not initialized" in response.get("message", "") or "NOTION_NOTES_DATABASE_ID not configured" in response.get("message", ""):
        print("INFO: Notion not fully configured (API token or DB ID missing). Skipping live creation check.")
    else:
        print(f"FAILURE: Text note creation. Reason: {response.get('message')}\n")

    # --- Test 2: Get Note (Handler) ---
    if created_page_id:
        print("\n--- Test 2: Get Note ---")
        get_params = {'page_id': created_page_id}
        response = command_handlers.handle_get_note(get_params)
        print(f"Response: {response}")
        if response.get("status") == "success" and response.get("note"):
            retrieved_title = response['note'].get('title')
            print(f"SUCCESS: Note retrieval handled. Retrieved title: '{retrieved_title}'")
            if retrieved_title != sample_note_title:
                 print(f"WARNING: Retrieved title '{retrieved_title}' does not match original '{sample_note_title}'")
            print("MANUAL VERIFICATION: Ensure retrieved details match the created note in Notion.\n")
        else:
            print(f"FAILURE: Note retrieval. Reason: {response.get('message')}\n")
    else:
        print("\n--- Test 2: Get Note --- SKIPPED (no page_id from creation)\n")

    # --- Test 3: Update Note (Handler) ---
    if created_page_id:
        print("\n--- Test 3: Update Note ---")
        updated_title = f"{sample_note_title} (Updated {timestamp_suffix})"
        updated_content = "The content of this note has been updated during testing."
        update_params = {
            'page_id': created_page_id,
            'title': updated_title,
            'content': updated_content,
            'linked_task_id': f"task_{timestamp_suffix}"
        }
        response = command_handlers.handle_update_note(update_params)
        print(f"Response: {response}")
        if response.get("status") == "success":
            print("SUCCESS: Note update handled.")
            print(f"MANUAL VERIFICATION: Check Notion. Note should have title '{updated_title}' and new content/links.\n")
            get_response = command_handlers.handle_get_note({'page_id': created_page_id})
            if get_response.get("status") == "success" and get_response.get("note"):
                if get_response["note"].get("title") == updated_title and \
                   get_response["note"].get("linked_task_id") == f"task_{timestamp_suffix}":
                    print("Verification via get_note: Update confirmed for title and link.")
                else:
                    print(f"Verification via get_note: Update discrepancy. Current details: {get_response.get('note')}")
            else:
                 print(f"Verification via get_note failed: {get_response.get('message')}")
        else:
            print(f"FAILURE: Note update. Reason: {response.get('message')}\n")
    else:
        print("\n--- Test 3: Update Note --- SKIPPED (no page_id from creation)\n")

    # --- Test 4: Search Notes (Handler) ---
    print("\n--- Test 4: Search Notes ---")
    search_query = updated_title if created_page_id else sample_note_title
    search_params = {'query': search_query, 'source': 'simulated-text-test'}

    response_search = command_handlers.handle_search_notes(search_params)
    print(f"Search Response: {response_search}")

    if response_search.get("status") == "success":
        found_notes_count = response_search.get("count", 0)
        print(f"SUCCESS: Note search handled. Found {found_notes_count} note(s) for query '{search_query}'.")
        if created_page_id and any(note.get('id') == created_page_id for note in response_search.get("notes",[])):
            print("The specific test note was found in search results.")
        elif created_page_id:
            print(f"WARNING: The specific test note (ID: {created_page_id}) was NOT found in search results for '{search_query}'.")
        print("MANUAL VERIFICATION: Search Notion for the query and verify results.\n")
    elif "Notion client not initialized" in response_search.get("message", ""):
        print("INFO: Notion not fully configured. Skipping live search check.")
    else:
        print(f"FAILURE: Note search. Reason: {response_search.get('message')}\n")

    # --- Test 5: Transcribe Audio (Direct call to note_utils for Deepgram) ---
    print("\n--- Test 5: Transcribe Audio (Deepgram) ---")
    if dummy_audio_file_path and os.path.exists(dummy_audio_file_path):
        transcription = note_utils.transcribe_audio_deepgram(dummy_audio_file_path)
        print(f"Transcription result: '{transcription}'")

        transcription_text = transcription if isinstance(transcription, str) else ""

        if isinstance(transcription, dict):
            # If the result is a dict, it's likely an error object.
            transcription_text = transcription.get("message", "") or transcription.get("error", "")

        if "Error: DEEPGRAM_API_KEY not configured" in transcription_text:
            print("INFO: Deepgram API key not configured. Transcription itself not tested.")
        elif transcription_text.startswith("Error:"):
            print(f"INFO: Transcription failed (e.g., API error, file issue): {transcription_text}")
        else:
            print("SUCCESS: Deepgram audio transcription function called.")
            if not transcription_text:
                print("INFO: Transcription is empty, which may be expected for a dummy/silent audio file.")
            print("MANUAL VERIFICATION: If a REAL audio file and API key were used, verify transcription text.\n")
    else:
        print("SKIPPED: Dummy audio file not available for transcription test.\n")

    # --- Test 6: Create Audio Note (Handler with Deepgram) ---
    print("\n--- Test 6: Create Audio Note (Deepgram) ---")
    if dummy_audio_file_path and os.path.exists(dummy_audio_file_path):
        audio_note_title = f"Audio Note Deepgram {timestamp_suffix}"
        audio_params = {
            'audio_file_path': dummy_audio_file_path,
            'title': audio_note_title,
            'source': 'simulated-audio-deepgram-test',
            'content': 'Initial content for Deepgram audio note.'
        }
        audio_response = command_handlers.handle_create_audio_note(audio_params)
        print(f"Response: {audio_response}")
        if audio_response.get("status") == "success" and audio_response.get("page_id"):
            created_audio_page_id = audio_response["page_id"]
            print(f"SUCCESS: Audio note creation handled. Page ID: {created_audio_page_id}")
            print(f"Transcription from handler: '{audio_response.get('transcription')}'")
            print(f"MANUAL VERIFICATION: Check Notion for note '{audio_note_title}'. Transcription should be present.\n")
        elif "DEEPGRAM_API_KEY not configured" in audio_response.get("message", ""):
            print("INFO: Deepgram API key not configured. Full audio note creation cannot be verified.")
        elif "Notion client not initialized" in audio_response.get("message", ""):
            print("INFO: Notion not configured. Full audio note creation cannot be verified.")
        else:
            print(f"FAILURE: Audio note creation. Reason: {audio_response.get('message')}\n")
    else:
        print("SKIPPED: Dummy audio file not available for audio note creation test.\n")

    # --- Test 7: Link Note (Handler) ---
    if created_page_id:
        print("\n--- Test 7: Link Note ---")
        new_task_id = f"task_linked_{timestamp_suffix}"
        new_event_id = f"event_linked_{timestamp_suffix}"
        link_params = {
            'page_id': created_page_id,
            'linked_task_id': new_task_id,
            'linked_event_id': new_event_id
        }
        response = command_handlers.handle_link_note(link_params)
        print(f"Response: {response}")
        if response.get("status") == "success":
            print("SUCCESS: Note link update handled.")
            get_response = command_handlers.handle_get_note({'page_id': created_page_id})
            if get_response.get("status") == "success" and get_response.get("note"):
                note_data = get_response["note"]
                if note_data.get("linked_task_id") == new_task_id and note_data.get("linked_event_id") == new_event_id:
                    print(f"Verification via get_note: Links confirmed. Task: {note_data.get('linked_task_id')}, Event: {note_data.get('linked_event_id')}")
                else:
                    print(f"Verification via get_note: Link discrepancy. Current links: Task='{note_data.get('linked_task_id')}', Event='{note_data.get('linked_event_id')}'")
                print("MANUAL VERIFICATION: Check Notion note for updated Linked Task ID and Linked Event ID.\n")
            else:
                print(f"Could not re-fetch note to verify link update: {get_response.get('message')}")
        else:
            print(f"FAILURE: Note link update. Reason: {response.get('message')}\n")
    else:
        print("\n--- Test 7: Link Note --- SKIPPED (no page_id from text note creation)\n")

    # --- Test 8: Delete Note (Handler) ---
    if created_page_id:
        print("\n--- Test 8: Delete Text Note ---")
        delete_params = {'page_id': created_page_id}
        response = command_handlers.handle_delete_note(delete_params)
        print(f"Response: {response}")
        if response.get("status") == "success":
            print("SUCCESS: Text note deletion handled.")
            get_response = command_handlers.handle_get_note({'page_id': created_page_id})
            if get_response.get("status") == "success" and get_response.get("note", {}).get("archived"):
                 print("Verification: Get call after delete shows note is archived.")
            elif get_response.get("status") == "error" and "not found" in get_response.get("message", ""):
                 print("Verification: Get call after delete confirms note not found (or error indicating it's gone).")
            else:
                 print(f"Verification: Get call after delete returned unexpected: {get_response}")
            print("MANUAL VERIFICATION: Check Notion. The text note should be deleted (archived).\n")
        else:
            print(f"FAILURE: Text note deletion. Reason: {response.get('message')}\n")
    else:
        print("\n--- Test 8: Delete Text Note --- SKIPPED (no page_id from creation)\n")

    if created_audio_page_id:
        print("\n--- Test 9: Delete Audio Note ---")
        delete_params = {'page_id': created_audio_page_id}
        response = command_handlers.handle_delete_note(delete_params)
        if response.get("status") == "success":
            print(f"SUCCESS: Audio note (ID: {created_audio_page_id}) deleted successfully.\n")
            print("MANUAL VERIFICATION: Check Notion. The audio note should be deleted (archived).\n")
        else:
            print(f"FAILURE: Failed to delete audio note (ID: {created_audio_page_id}). Reason: {response.get('message')}\n")

    # --- Final Cleanup ---
    if dummy_audio_file_path and os.path.exists(dummy_audio_file_path):
        try:
            os.remove(dummy_audio_file_path)
            print(f"Cleaned up dummy audio file: {dummy_audio_file_path}")
        except Exception as e:
            print(f"Error cleaning up dummy audio file: {e}")

    print("\nSimulated tests completed.")
    print("IMPORTANT: For full verification, ensure API keys and database ID are correctly set as environment variables, "
          "use a real sample audio file for transcription, and manually check your Notion workspace for expected outcomes.")

if __name__ == "__main__":
    print("Running notes integration test script...")
    # This section is for conceptual testing if this file were run directly.
    # Environment variables (NOTION_API_TOKEN, etc.) would need to be set.
    # The note_utils.py and command_handlers.py files have print statements
    # that will indicate if critical env vars are missing.

    # The re-initialization logic for clients has been removed from the test script itself,
    # as it's better handled by ensuring the modules load fresh in each test run if possible,
    # or by the modules themselves being robust to multiple initializations (which they are, mostly).
    # In a Docker context, environment variables are set when the container starts.

    simulate_tests()
