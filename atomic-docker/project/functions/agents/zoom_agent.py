import collections
import threading
import time
import sys
import os

# --- Set Dummy Environment Variables FIRST ---
# This is crucial for note_utils.py which initializes clients based on these at its import time.
os.environ.setdefault('NOTION_API_TOKEN', 'dummy_notion_token_for_test')
os.environ.setdefault('NOTION_NOTES_DATABASE_ID', 'dummy_notion_db_id_for_test')
os.environ.setdefault('DEEPGRAM_API_KEY', 'dummy_deepgram_key_for_test')
os.environ.setdefault('OPENAI_API_KEY', 'dummy_openai_key_for_test')
# Also set defaults for other OpenAI vars if summarize_transcript_gpt uses them from env
os.environ.setdefault('OPENAI_API_ENDPOINT', 'https://api.openai.com/v1/chat/completions') # Default from note_utils
os.environ.setdefault('GPT_MODEL_NAME', 'gpt-3.5-turbo') # Default from note_utils


# --- Path Setup to allow importing note_utils ---
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
FUNCTIONS_DIR_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT))
if FUNCTIONS_DIR_PATH not in sys.path:
    sys.path.append(FUNCTIONS_DIR_PATH)

# --- Import from note_utils AFTER setting env vars and path ---
# We also need to handle the case where note_utils might have been implicitly imported
# IF another module imported before this script ran (unlikely for direct execution, but good practice)
# Forcing a reload can ensure it picks up the new env vars for its global client initializations.
process_live_audio_for_notion = None
create_notion_note = None
summarize_transcript_gpt = None
process_post_meeting_transcript_for_notion = None

try:
    import note_utils
    import importlib
    importlib.reload(note_utils) # Reload to ensure it uses the new env vars

    from note_utils import (
        process_live_audio_for_notion as pl,
        create_notion_note as cn,
        summarize_transcript_gpt as stg,
        process_post_meeting_transcript_for_notion as ppmtfn
    )
    # Assign to globals used in __main__
    process_live_audio_for_notion = pl
    create_notion_note = cn
    summarize_transcript_gpt = stg
    process_post_meeting_transcript_for_notion = ppmtfn

except ImportError as e:
    print(f"Error importing from note_utils after attempting reload: {e}.")
    # Fallback definitions remain None


class ZoomAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.zoom_sdk_client = None
        self.current_meeting_id = None
        self.is_capturing_audio = False
        self.audio_buffer = collections.deque()
        self.audio_capture_thread = None
        print(f"ZoomAgent initialized for user_id: {self.user_id}")

    def _authenticate(self) -> bool:
        print(f"(Mocked) ZoomAgent ({self.user_id}): Authenticating with Zoom SDK...")
        self.zoom_sdk_client = object()
        print(f"(Mocked) ZoomAgent ({self.user_id}): Authentication successful, SDK client initialized.")
        return True

    def join_meeting(self, meeting_id_or_url: str) -> bool:
        print(f"(Mocked) ZoomAgent ({self.user_id}): Attempting to join Zoom meeting: {meeting_id_or_url}")
        if not self.zoom_sdk_client:
            if not self._authenticate():
                print(f"(Mocked) ZoomAgent ({self.user_id}): Authentication failed. Cannot join meeting.")
                return False

        parsed_meeting_id = meeting_id_or_url
        if "zoom.us/j/" in meeting_id_or_url:
            parsed_meeting_id = meeting_id_or_url.split('/j/')[-1].split('?')[0]

        self.current_meeting_id = parsed_meeting_id
        print(f"(Mocked) ZoomAgent ({self.user_id}): Successfully joined Zoom meeting: {self.current_meeting_id}")
        return True

    def _audio_chunk_generator(self):
        self.is_capturing_audio = True
        print(f"(Mocked) ZoomAgent ({self.user_id}): Starting audio chunk generation for meeting {self.current_meeting_id}...")

        try:
            for i in range(30):
                if not self.is_capturing_audio:
                    print(f"(Mocked) ZoomAgent ({self.user_id}): Audio capture flag turned off. Stopping chunk generation.")
                    break
                mock_chunk = b"\x00" * 3200
                self.audio_buffer.append(mock_chunk)
                time.sleep(0.1)
        except Exception as e:
            print(f"(Mocked) ZoomAgent ({self.user_id}): Error during audio chunk generation: {e}")
        finally:
            self.is_capturing_audio = False
            self.audio_buffer.append(None)
            print(f"(Mocked) ZoomAgent ({self.user_id}): Finished audio chunk generation. EOS signal queued.")

    def start_audio_capture(self, meeting_id: str):
        print(f"(Mocked) ZoomAgent ({self.user_id}): Received request to start audio capture for meeting: {meeting_id}")
        if self.current_meeting_id != meeting_id or not self.zoom_sdk_client:
            print(f"(Mocked) ZoomAgent ({self.user_id}): Error - Must join meeting '{meeting_id}' before capturing audio, or meeting ID mismatch. Current: {self.current_meeting_id}")
            return None

        if self.is_capturing_audio or (self.audio_capture_thread and self.audio_capture_thread.is_alive()):
            print(f"(Mocked) ZoomAgent ({self.user_id}): Warning - Audio capture already in progress for meeting {self.current_meeting_id}.")
            return None

        print(f"(Mocked) ZoomAgent ({self.user_id}): Initializing audio buffer and starting capture thread for {meeting_id}.")
        self.audio_buffer.clear()

        self.audio_capture_thread = threading.Thread(target=self._audio_chunk_generator)
        self.audio_capture_thread.daemon = True
        self.audio_capture_thread.start()

        print(f"(Mocked) ZoomAgent ({self.user_id}): Audio capture thread started for meeting: {meeting_id}.")
        return self._iterate_audio_buffer()

    def _iterate_audio_buffer(self):
        print(f"(Mocked) ZoomAgent ({self.user_id}): Iterator created for audio buffer.")
        while True:
            try:
                chunk = self.audio_buffer.popleft()
                if chunk is None:
                    print(f"(Mocked) ZoomAgent ({self.user_id}): End of stream signal (None) received by iterator. Stopping.")
                    yield None
                    break
                yield chunk
            except IndexError:
                if not self.is_capturing_audio and len(self.audio_buffer) == 0:
                    print(f"(Mocked) ZoomAgent ({self.user_id}): Capture stopped and buffer empty. Iterator truly finished.")
                    yield None
                    break
                time.sleep(0.01)

    def stop_audio_capture(self):
        print(f"(Mocked) ZoomAgent ({self.user_id}): Received request to stop audio capture for meeting {self.current_meeting_id}.")
        if not self.is_capturing_audio and not (self.audio_capture_thread and self.audio_capture_thread.is_alive()):
            print(f"(Mocked) ZoomAgent ({self.user_id}): Audio capture is not currently active or thread already stopped.")
            return

        self.is_capturing_audio = False

        if self.audio_capture_thread and self.audio_capture_thread.is_alive():
            print(f"(Mocked) ZoomAgent ({self.user_id}): Waiting for audio capture thread to join (timeout 5s)...")
            self.audio_capture_thread.join(timeout=5)
            if self.audio_capture_thread.is_alive():
                print(f"(Mocked) ZoomAgent ({self.user_id}): Warning - Audio capture thread did not join within timeout.")
        else:
            print(f"(Mocked) ZoomAgent ({self.user_id}): Audio capture thread was not alive or not set.")

        print(f"(Mocked) ZoomAgent ({self.user_id}): Audio capture signaled to stop. SDK resources would be released here.")

    def leave_meeting(self):
        print(f"(Mocked) ZoomAgent ({self.user_id}): Attempting to leave meeting {self.current_meeting_id}.")
        if self.is_capturing_audio or (self.audio_capture_thread and self.audio_capture_thread.is_alive()):
            print(f"(Mocked) ZoomAgent ({self.user_id}): Audio capture seems active, stopping it first.")
            self.stop_audio_capture()

        print(f"(Mocked) ZoomAgent ({self.user_id}): Successfully left meeting {self.current_meeting_id}.")
        self.current_meeting_id = None
        print(f"(Mocked) ZoomAgent ({self.user_id}): Zoom client ready for new meeting or shutdown.")


if __name__ == '__main__':
    print("--- Testing ZoomAgent and note_utils integration ---")

    test_user_id = "test_user_zoom_integration"
    test_meeting_id = "123456789"

    agent = ZoomAgent(user_id=test_user_id)

    print("\n--- Test: process_live_audio_for_notion ---")
    if process_live_audio_for_notion and callable(process_live_audio_for_notion):
        if agent.join_meeting(test_meeting_id):
            print(f"Successfully joined meeting {test_meeting_id}")

            notion_page_id = process_live_audio_for_notion(
                platform_module=agent,
                meeting_id=test_meeting_id,
                notion_note_title=f"Live Notes: Zoom Meeting {test_meeting_id}",
                notion_source="Zoom Live Test Integration"
            )

            if notion_page_id:
                print(f"Notion page from live audio processing: {notion_page_id}")
            else:
                print("Failed to create/update Notion page from live audio processing.")

            agent.leave_meeting()
        else:
            print(f"Failed to join meeting {test_meeting_id}")
    else:
        print("process_live_audio_for_notion function not found or not callable. Check imports and reload logic.")

    print("\n--- Test: process_post_meeting_transcript_for_notion ---")
    if process_post_meeting_transcript_for_notion and callable(process_post_meeting_transcript_for_notion):
        sample_transcript = "This is a sample transcript from a test meeting. Hello world. Key point one. Another key point."
        page_id_transcript = process_post_meeting_transcript_for_notion(
            transcript_text=sample_transcript,
            notion_note_title="Test Post-Meeting Transcript",
            notion_source="Transcript Test Integration"
        )
        if page_id_transcript:
            print(f"Notion page from transcript created: {page_id_transcript}")
        else:
            print("Failed to create Notion page from transcript.")
    else:
        print("process_post_meeting_transcript_for_notion not found. Check imports and reload logic.")

    print("\n--- Test: create_notion_note (direct) ---")
    if create_notion_note and callable(create_notion_note):
        summary, key_points = None, None

        if summarize_transcript_gpt and callable(summarize_transcript_gpt):
             print("Attempting mocked summarization for direct create_notion_note test...")
             # Since OPENAI_API_KEY is a dummy key, summarize_transcript_gpt should return (None, None)
             # or print its own error about the key and then return (None, None).
             summary_mock, kp_mock = summarize_transcript_gpt("Test transcript for Notion direct creation.")
             if summary_mock is not None: summary = summary_mock
             if kp_mock is not None: key_points = kp_mock
             print(f"Mocked summarization result: Summary='{summary}', KeyPoints='{key_points}'")

        page_id_direct = create_notion_note(
            title="Direct Notion Test (Summarization may have failed)",
            content="Content for direct test.",
            source="Direct Test Integration",
            transcription="Minimal transcript for direct test.",
            summary=summary,
            key_points=key_points
        )
        if page_id_direct:
            print(f"Direct Notion page created: {page_id_direct} (Summary/KP presence depends on mock summarization)")
        else:
            print("Failed to create direct Notion page.")
    else:
        print("create_notion_note not found. Check imports and reload logic.")

    print("\n--- ZoomAgent and note_utils integration test finished ---")
