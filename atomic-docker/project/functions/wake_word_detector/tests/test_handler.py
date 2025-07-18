import pytest
from unittest.mock import MagicMock, patch, mock_open, call, AsyncMock
import os
import sys
import time
import asyncio
import audioop
import websockets
import requests
import threading
import json

COMMAND_AUDIO_TIMEOUT_SECONDS = 10
SILENCE_DETECTION_DURATION_SECONDS = 3

# Ensure the handler module can be imported
# This might need adjustment based on how pytest is run and project structure
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) # up to functions/
from wake_word_detector.handler import WakeWordDetector, DetectorState, WAKE_WORD_KEYWORD_STRING

# Default URLs for testing, can be overridden by environment variables if needed by handler
DEFAULT_AUDIO_PROCESSOR_WS_URL = "ws://localhost:8081/stt_stream"
DEFAULT_ATOM_AGENT_URL = "http://localhost:8082"
DEFAULT_ATOM_AGENT_ACTIVATE_ENDPOINT = f"{DEFAULT_ATOM_AGENT_URL}/atom-agent/activate"
DEFAULT_ATOM_AGENT_CONVERSATION_ENDPOINT = f"{DEFAULT_ATOM_AGENT_URL}/atom-agent/conversation"
DEFAULT_ATOM_AGENT_INTERRUPT_ENDPOINT = f"{DEFAULT_ATOM_AGENT_URL}/atom-agent/interrupt"
DEFAULT_ATOM_AGENT_DEACTIVATE_ENDPOINT = f"{DEFAULT_ATOM_AGENT_URL}/atom-agent/deactivate"


# --- Pytest Fixtures ---

@pytest.fixture
def mock_pyaudio_instance(mocker):
    mock_stream = MagicMock()
    mock_stream.read.return_value = b'\x00' * 1024 # Dummy audio data
    mock_stream.stop_stream = MagicMock()
    mock_stream.close = MagicMock()

    mock_pyaudio = MagicMock()
    mock_pyaudio.open.return_value = mock_stream
    mock_pyaudio.get_default_input_device_info.return_value = {'index': 0, 'maxInputChannels': 1}
    mock_pyaudio.get_device_info_by_index.return_value = {'index': 0, 'name': 'Test Mic', 'maxInputChannels': 1}
    mock_pyaudio.terminate = MagicMock()
    mocker.patch('pyaudio.PyAudio', return_value=mock_pyaudio)
    return mock_pyaudio, mock_stream

@pytest.fixture
def mock_porcupine_instance(mocker):
    mock_porcupine = MagicMock()
    mock_porcupine.process.return_value = -1 # Default: no wake word
    mock_porcupine.frame_length = 512
    mock_porcupine.sample_rate = 16000
    mock_porcupine.delete = MagicMock()
    mocker.patch('pvporcupine.create', return_value=mock_porcupine)
    return mock_porcupine

@pytest.fixture
def mock_websockets_connect(mocker):
    mock_ws_connection = MagicMock(spec=websockets.WebSocketClientProtocol)
    mock_ws_connection.send = AsyncMock()
    mock_ws_connection.recv = AsyncMock(return_value=json.dumps({"transcript": "test", "is_final": True}))
    mock_ws_connection.close = AsyncMock()

    # Simulate context manager usage for async with websockets.connect(...)
    async_context_manager_mock = AsyncMock()
    async_context_manager_mock.__aenter__.return_value = mock_ws_connection
    async_context_manager_mock.__aexit__.return_value = None

    mocker.patch('websockets.connect', return_value=async_context_manager_mock)
    return mock_ws_connection, async_context_manager_mock


@pytest.fixture
def mock_requests_post(mocker):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"status": "success"}
    mock_post = mocker.patch('requests.Session.post', return_value=mock_response)
    return mock_post

@pytest.fixture
def mock_time(mocker):
    # Mock time.time and time.sleep
    # time.time needs to be controllable to simulate timeouts
    mock_time_time = mocker.patch('time.time', return_value=time.time()) # Start with current time
    mock_time_sleep = mocker.patch('time.sleep', return_value=None) # Prevent actual sleeping
    return mock_time_time, mock_time_sleep

@pytest.fixture
def mock_audioop_rms(mocker):
    # Default: simulate non-silent audio to not trigger silence detection unless specified
    return mocker.patch('audioop.rms', return_value=500)

@pytest.fixture
def mock_asyncio_run(mocker):
    # This allows us to inspect what async function was called by `asyncio.run`
    # and potentially control its execution flow or return value for testing.
    # For now, just make it run the passed coroutine.
    # Using actual asyncio.run for tests that need the async code to execute.
    # If a test needs to *prevent* execution, it can patch asyncio.run specifically for that test.
    return mocker.patch('asyncio.run', side_effect=lambda coro: asyncio.get_event_loop().run_until_complete(coro))


@pytest.fixture
def mock_thread_factory(mocker): # Renamed to avoid conflict if a test needs a specific instance
    # This fixture provides a way to get a mock Thread instance when Thread() is called.
    # It also captures the target for potential direct invocation in tests.
    # Using a list to store created mock thread instances if multiple threads are created.
    created_threads_mocks = []

    def thread_side_effect(target, daemon):
        mock_thread_instance = MagicMock(spec=threading.Thread)
        mock_thread_instance.daemon = daemon
        mock_thread_instance._target = target # Store target for inspection/execution

        # Mock methods
        mock_thread_instance.start = MagicMock(side_effect=lambda: setattr(mock_thread_instance, '_started', True))
        mock_thread_instance.join = MagicMock()
        mock_thread_instance.is_alive = MagicMock(return_value=False) # Default, can be changed by test

        created_threads_mocks.append(mock_thread_instance)
        return mock_thread_instance

    # Patch threading.Thread to use our side_effect
    patched_thread = mocker.patch('threading.Thread', side_effect=thread_side_effect)

    # Yield both the patch object (to check calls to Thread(...))
    # and the list of created mock instances (to control/inspect them)
    yield patched_thread, created_threads_mocks


@pytest.fixture
def detector(mock_pyaudio_instance, mock_porcupine_instance, mock_websockets_connect, mock_requests_post, mock_time, mock_audioop_rms, mock_asyncio_run, mock_thread_factory): # Use factory here
    # Environment variables for the detector
    with patch.dict(os.environ, {
        "PV_ACCESS_KEY": "test_pv_access_key",
        "AUDIO_PROCESSOR_URL": DEFAULT_AUDIO_PROCESSOR_WS_URL.replace("/stt_stream","").replace("ws://","http://"),
        "ATOM_AGENT_URL": DEFAULT_ATOM_AGENT_URL
    }, clear=True):
        detector_instance = WakeWordDetector(
            access_key="test_pv_access_key",
            keyword_identifier=WAKE_WORD_KEYWORD_STRING
        )
        # Ensure the global session's post is the mock, if detector creates its own session instance.
        # If WakeWordDetector uses requests.post directly, then patch 'requests.post'
        # The current code uses self._http_session = requests.Session(), so patching Session.post is correct.
        detector_instance._http_session.post = mock_requests_post
    return detector_instance

# --- Test Cases ---

def test_detector_initialization_success(detector, mock_porcupine_instance):
    assert detector._access_key == "test_pv_access_key"
    # pvporcupine.create is patched globally by the fixture mock_porcupine_instance
    # So, detector._porcupine should be this global mock if init was successful
    # However, the fixture directly patches 'pvporcupine.create' to return mock_porcupine.
    # The WakeWordDetector class calls pvporcupine.create() and assigns its return to self._porcupine.
    # So, self._porcupine should be the mock_porcupine that the fixture's patch returned.
    assert detector._porcupine is mock_porcupine_instance
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    # Check that pvporcupine.create was called correctly by the WakeWordDetector constructor
    mock_porcupine_instance.create.assert_called_once_with(
        access_key="test_pv_access_key",
        keyword_paths=None,
        keywords=[WAKE_WORD_KEYWORD_STRING]
    )

@patch.dict(os.environ, {}, clear=True)
def test_detector_initialization_no_picovoice_key(mocker):
    mocker.patch('pvporcupine.create')
    mocker.patch('pyaudio.PyAudio')

    with patch('logging.error') as mock_log_error:
        # Test with PICOVOICE_ACCESS_KEY effectively None by not setting it in environ
        # and ensuring the handler's global PICOVOICE_ACCESS_KEY is None for this test.
        with patch('wake_word_detector.handler.PICOVOICE_ACCESS_KEY', None):
             detector_instance = WakeWordDetector(access_key=None, keyword_identifier="dummy")
        assert detector_instance._porcupine is None
        mock_log_error.assert_any_call("PV_ACCESS_KEY environment variable not set. Wake word detection will not work.")
        mock_log_error.assert_any_call("Cannot initialize WakeWordDetector: Picovoice AccessKey is missing.")


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
def test_detector_initialization_porcupine_error(mocker):
    # This import is needed for PorcupineError to be recognized by isinstance checks if any, or for type
    import pvporcupine as pv_porcupine_module # Import the actual module for the Error type
    mocker.patch('pvporcupine.create', side_effect=pv_porcupine_module.PorcupineError("Test Porcupine init error"))
    mocker.patch('pyaudio.PyAudio')

    with patch('logging.error') as mock_log_error:
        detector_instance = WakeWordDetector(access_key="test_key", keyword_identifier="dummy")
        assert detector_instance._porcupine is None
        assert detector_instance._state == DetectorState.PROCESSING_ERROR
        mock_log_error.assert_any_call("Failed to initialize Porcupine: Test Porcupine init error")


def test_start_selects_default_audio_device(detector, mock_pyaudio_instance):
    pyaudio_mock, _ = mock_pyaudio_instance

    with patch.object(detector, '_run_porcupine_loop', MagicMock()) as mock_run_loop:
        detector.start(input_device_index=None)
        detector._running = False
        if detector._command_thread and detector._command_thread.is_alive():
            detector._command_thread.join(timeout=0.1)

    pyaudio_mock.get_default_input_device_info.assert_called_once()
    assert detector._input_device_index == 0


def test_start_uses_specified_audio_device(detector, mock_pyaudio_instance):
    pyaudio_mock, _ = mock_pyaudio_instance

    with patch.object(detector, '_run_porcupine_loop', MagicMock()) as mock_run_loop:
        detector.start(input_device_index=1)
        detector._running = False
        if detector._command_thread and detector._command_thread.is_alive():
            detector._command_thread.join(timeout=0.1)

    pyaudio_mock.get_device_info_by_index.assert_called_with(1)
    assert detector._input_device_index == 1


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
def test_start_fails_if_no_audio_device(mocker):
    pyaudio_mock = MagicMock()
    pyaudio_mock.get_default_input_device_info.side_effect = IOError("No default device")
    pyaudio_mock.get_device_info_by_index.side_effect = Exception("Invalid device index")
    mocker.patch('pyaudio.PyAudio', return_value=pyaudio_mock)
    # Patch pvporcupine.create, because it's called in WakeWordDetector's __init__
    mocker.patch('pvporcupine.create')

    with patch('logging.error') as mock_log_error:
        # Initialize WakeWordDetector *after* pvporcupine.create is globally patched
        detector_instance = WakeWordDetector(access_key="test_key", keyword_identifier="dummy")
        detector_instance.start()
        assert detector_instance._state == DetectorState.PROCESSING_ERROR
        mock_log_error.assert_any_call("Could not get default input device: No default device. List devices and specify one.")


def test_wake_word_triggers_command_handling(detector, mock_porcupine_instance, mock_thread_factory, mock_pyaudio_instance):
    # Setup: Detector is running and waiting for wake word
    detector._state = DetectorState.WAITING_FOR_WAKE_WORD
    detector._running = True
    detector._input_device_index = 0 # Assume device is set

    # Simulate Porcupine detecting the wake word
    mock_porcupine_instance.process.return_value = 0

    # PyAudio's open needs to be ready for the Porcupine stream
    pyaudio_mock, porcupine_stream_mock = mock_pyaudio_instance
    detector._pa = pyaudio_mock # Ensure detector has the PyAudio instance

    # Patch asyncio.run to check the coroutine without fully executing complex async logic here
    # if we want to avoid testing the full _handle_command_audio_and_transcription here.
    # For now, the default mock_asyncio_run from fixture will try to run it.
    # We need _handle_command_audio_and_transcription to be an attribute for patching.
    # It's an instance method, so it's fine.
    mock_hcat_coro = AsyncMock() # Mock the coroutine itself
    detector._handle_command_audio_and_transcription = mock_hcat_coro

    # This is to ensure the _run_porcupine_loop runs once and then stops
    # so the test doesn't hang or run forever.
    def run_loop_once_then_stop(*args, **kwargs):
        detector._run_porcupine_loop() # Call the original method
        detector._running = False      # Set flag to stop outer start() loop

    with patch.object(detector, '_run_porcupine_loop', side_effect=run_loop_once_then_stop) as mock_run_loop_method:
        detector.start() # This will call the (mocked) _run_porcupine_loop

    mock_run_loop_method.assert_called_once() # Ensure our loop control worked

    # Check that a thread was created for _handle_command_audio_and_transcription
    patched_thread_constructor, created_threads = mock_thread_factory
    patched_thread_constructor.assert_called_once()
    assert len(created_threads) == 1
    mock_thread_instance = created_threads[0]

    # Check that the thread was started
    mock_thread_instance.start.assert_called_once()

    # The target of the thread is lambda: asyncio.run(self._handle_command_audio_and_transcription())
    # We mocked _handle_command_audio_and_transcription to be an AsyncMock (mock_hcat_coro)
    # So, when the lambda is called by the thread (or by us simulating it),
    # asyncio.run(mock_hcat_coro()) should be invoked.
    # Our mock_asyncio_run fixture calls asyncio.get_event_loop().run_until_complete(coro).
    # This means mock_hcat_coro() would be awaited.

    # To verify the *target* of the thread was set correctly:
    # The target is a lambda. Inside that lambda, `asyncio.run` is called with `detector._handle_command_audio_and_transcription()`.
    # Since `detector._handle_command_audio_and_transcription` is now `mock_hcat_coro`,
    # the thread's target, when called, would effectively do `asyncio.run(mock_hcat_coro())`.

    # To simulate the thread's execution for checking if the async mock was called:
    # This requires the mock_asyncio_run to be in place.
    if hasattr(mock_thread_instance, '_target') and mock_thread_instance._target:
        mock_thread_instance._target() # Execute the lambda: asyncio.run(detector._handle_command_audio_and_transcription())
        mock_hcat_coro.assert_awaited_once() # Check if the async method itself was awaited
    else:
        pytest.fail("Thread target was not captured or executed for assertion.")

    # State should change from WAITING_FOR_WAKE_WORD because a thread is now "handling" it.
    # The _run_porcupine_loop breaks and the outer loop in start() would then wait for the thread.
    # The state inside _handle_command_audio_and_transcription changes to LISTENING_FOR_COMMAND.
    # This test primarily checks the transition *to* command handling.

def test_stop_resources_calls_cleanup_methods(detector, mock_pyaudio_instance, mock_porcupine_instance):
    pyaudio_mock, stream_mock = mock_pyaudio_instance

    detector._audio_stream_porcupine = stream_mock
    detector._audio_stream_command = stream_mock
    detector._pa = pyaudio_mock
    detector._porcupine = mock_porcupine_instance

    detector.stop_resources()

    mock_porcupine_instance.delete.assert_called_once()
    # stream_mock is used for both, so it's stop/close would be called twice if both were active
    # However, stop_resources checks `if self._audio_stream_porcupine:` etc.
    # So, each distinct stream mock would be closed once.
    assert stream_mock.stop_stream.call_count >= 1
    assert stream_mock.close.call_count >= 1
    pyaudio_mock.terminate.assert_called_once()
    assert detector._state == DetectorState.IDLE


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True) # Mock helper
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent', return_value=None) # Mock helper
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent', return_value=None) # Mock helper
def test_hcat_flow_successful_transcript(
    mock_deactivate_agent, mock_send_transcript, mock_activate_agent,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    # This test focuses on the _handle_command_audio_and_transcription method's logic
    pyaudio_mock, main_stream_mock = mock_pyaudio_instance

    # Ensure _pa is set for _handle_command_audio_and_transcription to open command stream
    detector._pa = pyaudio_mock
    # Configure the main PyAudio mock's open to return a specific stream for command audio
    command_audio_stream_mock = MagicMock()
    command_audio_stream_mock.read.return_value = b'\x01' * 1024 # Non-silent audio
    command_audio_stream_mock.stop_stream = MagicMock()
    command_audio_stream_mock.close = MagicMock()
    # Important: detector._pa.open is called inside _handle_command_audio_and_transcription
    pyaudio_mock.open.return_value = command_audio_stream_mock

    ws_conn_mock, ws_context_mock = mock_websockets_connect
    ws_conn_mock.recv.side_effect = [
        json.dumps({"transcript": "final transcript", "is_final": True}),
        # Keep raising timeout after the first message to make the loop exit condition cleaner for test
        asyncio.TimeoutError,
        asyncio.TimeoutError,
    ]
    mock_audioop_rms.return_value = 500 # Non-silent

    # Mock time.time to control timeouts
    # Initial time, then advance it slightly for send/recv, then enough for silence if needed.
    # For this success test, we don't need to advance time excessively.
    start_time = time.time()
    mock_time[0].side_effect = [
        start_time, start_time + 0.1, start_time + 0.2, start_time + 0.3,
        start_time + 0.4, start_time + 0.5, start_time + 0.6 # Enough for a few loops
    ]


    # Directly call the async method using asyncio.run (which is what the thread would do)
    asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    ws_context_mock.__aenter__.assert_called_once() # WebSocket connected

    # Check audio was sent (at least once)
    command_audio_stream_mock.read.assert_called()
    ws_conn_mock.send.assert_called()

    # Check transcript sent to agent
    mock_send_transcript.assert_called_once_with("final transcript")

    assert detector.last_command_sent_time > 0 # Should be updated
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD # Should return to this state

    ws_context_mock.__aexit__.assert_called_once()
    command_audio_stream_mock.close.assert_called_once()
    mock_deactivate_agent.assert_not_called() # Should not be called on success


# More tests needed for timeouts, interruptions, and various error conditions within HCAT
# The structure for test_hcat_flow_successful_transcript provides a good template.
# For timeouts, mock_time[0] (time.time) needs to be advanced significantly.
# For silence, mock_audioop_rms needs to return low values.
# For interruption, test the _run_porcupine_loop's logic for calling _send_interrupt_to_atom_agent.

# Example for interruption (testing the logic in _run_porcupine_loop)
def test_interruption_detection_sends_signal(detector, mock_porcupine_instance, mock_requests_post, mock_time, mock_thread_factory):
    detector._state = DetectorState.WAITING_FOR_WAKE_WORD
    detector._running = True
    detector._input_device_index = 0 # Assume device is set
    detector._pa = MagicMock() # Mock PyAudio instance on detector
    detector._pa.open.return_value = MagicMock() # Mock stream for porcupine

    # Simulate that a command was just sent
    current_real_time = time.time()
    detector.last_command_sent_time = current_real_time - 1 # 1 second ago

    # Configure time.time mock to return current_real_time when checked in the loop
    mock_time[0].return_value = current_real_time

    mock_porcupine_instance.process.return_value = 0 # Wake word detected

    # Mock _handle_command_audio_and_transcription to prevent its full execution
    # as we are testing the interruption logic *before* it's called for the new command.
    mock_hcat = MagicMock()
    detector._handle_command_audio_and_transcription = mock_hcat

    # This is to ensure the _run_porcupine_loop runs once and then the main start() loop stops
    def run_loop_once_then_stop(*args, **kwargs):
        detector._run_porcupine_loop()
        detector._running = False

    with patch.object(detector, '_run_porcupine_loop', side_effect=run_loop_once_then_stop):
        detector.start()

    # Check that interrupt endpoint was called
    mock_requests_post.assert_any_call(DEFAULT_ATOM_AGENT_INTERRUPT_ENDPOINT, timeout=3)

    # Check that command handling was still initiated for the new command (after interrupt)
    patched_thread_constructor, created_threads = mock_thread_factory
    assert len(created_threads) == 1 # Thread for HCAT should have been created
    created_threads[0].start.assert_called_once()


# Test for command timeout in HCAT
@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True)
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent') # Should not be called
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_command_timeout(
    mock_deactivate_agent, mock_send_transcript, mock_activate_agent,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    pyaudio_mock, _ = mock_pyaudio_instance
    detector._pa = pyaudio_mock
    command_audio_stream_mock = MagicMock()
    command_audio_stream_mock.read.return_value = b'\x01' * 1024
    pyaudio_mock.open.return_value = command_audio_stream_mock

    ws_conn_mock, ws_context_mock = mock_websockets_connect
    # Simulate STT never sending a final transcript, or just keep timing out
    ws_conn_mock.recv.side_effect = asyncio.TimeoutError
    mock_audioop_rms.return_value = 500 # Non-silent, so only overall timeout matters

    # Control time to exceed COMMAND_AUDIO_TIMEOUT_SECONDS
    start_time = time.time()
    # Simulate time advancing beyond the command timeout
    time_sequence = [start_time + i * 0.1 for i in range(int(COMMAND_AUDIO_TIMEOUT_SECONDS * 10) + 20)]
    mock_time[0].side_effect = time_sequence

    asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    mock_send_transcript.assert_not_called()
    mock_deactivate_agent.assert_called_once_with("no_command_after_activation")
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    ws_context_mock.__aexit__.assert_called_once()

@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True)
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent') # Should not be called
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_silence_timeout(
    mock_deactivate_agent, mock_send_transcript, mock_activate_agent,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    pyaudio_mock, _ = mock_pyaudio_instance
    detector._pa = pyaudio_mock
    command_audio_stream_mock = MagicMock()
    # Simulate audio data being read, even if it's silence for RMS check
    command_audio_stream_mock.read.return_value = b'\x00' * 1024
    pyaudio_mock.open.return_value = command_audio_stream_mock

    ws_conn_mock, ws_context_mock = mock_websockets_connect
    # STT might send interim results, but no final ones, or just keep timing out on recv
    ws_conn_mock.recv.side_effect = asyncio.TimeoutError

    # Simulate silence
    mock_audioop_rms.return_value = 50 # Below SILENCE_THRESHOLD_RMS

    # Control time: advance just enough for silence detection to kick in
    # The loop checks SILENCE_DETECTION_DURATION_SECONDS after last_speech_time.
    # last_speech_time is initialized to start_listening_time.
    start_time = time.time()
    # Ensure last_speech_time (initially start_listening_time) becomes older than SILENCE_DETECTION_DURATION_SECONDS
    time_sequence = [start_time] # Initial time for start_listening_time
    # Add times for the loop iterations, advancing by small amounts
    for i in range(1, int(SILENCE_DETECTION_DURATION_SECONDS * 10) + 20): # Iterate enough for timeout
        time_sequence.append(start_time + i * 0.1)
    mock_time[0].side_effect = time_sequence

    asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    mock_send_transcript.assert_not_called() # No final transcript due to silence
    mock_deactivate_agent.assert_called_once_with("no_command_after_activation") # Or a specific silence reason
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    ws_context_mock.__aexit__.assert_called_once() # Ensure WebSocket resources are cleaned up


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', side_effect=requests.exceptions.RequestException("Activation Error"))
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent')
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_activation_fails(
    mock_deactivate_agent, mock_send_transcript, mock_activate_agent_raising_error,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    # No need to mock pyaudio, websockets etc. deeply if activation fails early
    with patch('logging.error') as mock_log_error:
        asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent_raising_error.assert_called_once()
    mock_send_transcript.assert_not_called()
    mock_deactivate_agent.assert_not_called() # Activation failed, so no command to time out on.
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD # Should revert to waiting
    mock_log_error.assert_any_call("Failed to activate Atom Agent: Activation Error")


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True)
# Patch websockets.connect at the module level where it's imported in the handler
@patch('wake_word_detector.handler.websockets.connect', side_effect=websockets.WebSocketException("WS Connect Error"))
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent')
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_websocket_connection_fails(
    mock_deactivate_agent, mock_send_transcript, mock_ws_connect_raising_error, mock_activate_agent,
    detector, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    # _pa needs to be set for the 'finally' block in _hcat if command stream was attempted
    detector._pa = mock_pyaudio_instance[0]

    with patch('logging.error') as mock_log_error:
        asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    mock_ws_connect_raising_error.assert_called_once_with(DEFAULT_AUDIO_PROCESSOR_WS_URL)
    mock_send_transcript.assert_not_called()
    # Deactivate might be called if activation succeeded but WS failed before any transcript
    mock_deactivate_agent.assert_called_once_with("no_command_after_activation")
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    mock_log_error.assert_any_call("WebSocket connection failed or closed unexpectedly: WS Connect Error")


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True)
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent', side_effect=requests.exceptions.RequestException("Send Transcript Error"))
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_send_transcript_fails(
    mock_deactivate_agent, mock_send_transcript_raising_error, mock_activate_agent,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    pyaudio_mock, _ = mock_pyaudio_instance
    detector._pa = pyaudio_mock
    command_audio_stream_mock = MagicMock()
    command_audio_stream_mock.read.return_value = b'\x01' * 1024
    pyaudio_mock.open.return_value = command_audio_stream_mock

    ws_conn_mock, ws_context_mock = mock_websockets_connect
    ws_conn_mock.recv.side_effect = [
        json.dumps({"transcript": "error will happen after this", "is_final": True}),
        asyncio.TimeoutError
    ]
    mock_audioop_rms.return_value = 500 # Non-silent

    start_time = time.time()
    mock_time[0].side_effect = [start_time + i * 0.1 for i in range(10)]

    with patch('logging.error') as mock_log_error:
        asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    mock_send_transcript_raising_error.assert_called_once_with("error will happen after this")
    # Deactivation is not called here because the error is in sending the transcript,
    # not in a timeout of user command.
    mock_deactivate_agent.assert_not_called()
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    mock_log_error.assert_any_call("Failed to send transcript to Atom Agent: Send Transcript Error")


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True)
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent')
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_websocket_send_error(
    mock_deactivate_agent, mock_send_transcript, mock_activate_agent,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    pyaudio_mock, _ = mock_pyaudio_instance
    detector._pa = pyaudio_mock
    command_audio_stream_mock = MagicMock()
    command_audio_stream_mock.read.return_value = b'\x01' * 1024 # Audio data to send
    pyaudio_mock.open.return_value = command_audio_stream_mock

    ws_conn_mock, ws_context_mock = mock_websockets_connect
    ws_conn_mock.send.side_effect = websockets.exceptions.ConnectionClosedError(None, None) # Simulate send error
    # No need to mock recv if send fails early in the sender task.

    mock_audioop_rms.return_value = 500 # Non-silent initially

    start_time = time.time()
    mock_time[0].side_effect = [start_time + i * 0.1 for i in range(10)] # Allow some time progression

    with patch('logging.error') as mock_log_error:
        asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    ws_context_mock.__aenter__.assert_called_once() # WS connection was attempted

    # Send was attempted, then error should break sender loop
    command_audio_stream_mock.read.assert_called() # Should have tried to read audio
    ws_conn_mock.send.assert_called()       # Should have attempted to send

    mock_send_transcript.assert_not_called() # Should not get to sending transcript
    # Deactivation should be called as the command processing failed before completion
    mock_deactivate_agent.assert_called_once_with("no_command_after_activation")
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    mock_log_error.assert_any_call("Error during audio send: None") # Error message from ConnectionClosedError
    ws_context_mock.__aexit__.assert_called_once() # Ensure WS context is exited


@patch.dict(os.environ, {"PV_ACCESS_KEY": "test_key"}, clear=True)
@patch('wake_word_detector.handler.WakeWordDetector._activate_atom_agent', return_value=True)
@patch('wake_word_detector.handler.WakeWordDetector._send_transcript_to_atom_agent')
@patch('wake_word_detector.handler.WakeWordDetector._deactivate_atom_agent')
def test_hcat_websocket_recv_error(
    mock_deactivate_agent, mock_send_transcript, mock_activate_agent,
    detector, mock_websockets_connect, mock_pyaudio_instance, mock_time, mock_audioop_rms, mocker
):
    pyaudio_mock, _ = mock_pyaudio_instance
    detector._pa = pyaudio_mock
    command_audio_stream_mock = MagicMock()
    command_audio_stream_mock.read.return_value = b'\x01' * 1024
    pyaudio_mock.open.return_value = command_audio_stream_mock

    ws_conn_mock, ws_context_mock = mock_websockets_connect
    ws_conn_mock.recv.side_effect = Exception("Recv Error") # Simulate a generic recv error

    mock_audioop_rms.return_value = 500
    start_time = time.time()
    mock_time[0].side_effect = [start_time + i * 0.1 for i in range(10)]

    with patch('logging.error') as mock_log_error:
        asyncio.run(detector._handle_command_audio_and_transcription())

    mock_activate_agent.assert_called_once()
    ws_context_mock.__aenter__.assert_called_once()
    ws_conn_mock.recv.assert_called() # Recv was attempted

    mock_send_transcript.assert_not_called()
    mock_deactivate_agent.assert_called_once_with("no_command_after_activation")
    assert detector._state == DetectorState.WAITING_FOR_WAKE_WORD
    mock_log_error.assert_any_call("Error receiving/processing STT result: Recv Error")
    ws_context_mock.__aexit__.assert_called_once()
