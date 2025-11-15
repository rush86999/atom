"""
Voice Integration E2E Tests for Atom Platform
Tests voice-to-action capabilities, ElevenLabs integration, and wake word detection
"""

import json
import time
from typing import Any, Dict, List, Optional

import requests

from config.test_config import TestConfig


def run_tests(config: TestConfig) -> Dict[str, Any]:
    """
    Run voice integration E2E tests

    Args:
        config: Test configuration

    Returns:
        Test results with outputs for LLM verification
    """
    results = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "test_details": {},
        "test_outputs": {},
        "start_time": time.time(),
    }

    # Test 1: Voice endpoints availability
    results.update(_test_voice_endpoints(config))

    # Test 2: Text-to-speech capabilities
    results.update(_test_text_to_speech(config))

    # Test 3: Speech-to-text capabilities
    results.update(_test_speech_to_text(config))

    # Test 4: Voice command processing
    results.update(_test_voice_commands(config))

    # Test 5: Wake word detection
    results.update(_test_wake_word_detection(config))

    # Test 6: Voice workflow automation
    results.update(_test_voice_workflows(config))

    results["end_time"] = time.time()
    results["duration_seconds"] = results["end_time"] - results["start_time"]

    return results


def _test_voice_endpoints(config: TestConfig) -> Dict[str, Any]:
    """Test voice integration endpoints availability"""
    test_name = "voice_endpoints"
    test_details = {
        "test_name": test_name,
        "description": "Test voice integration endpoints and connectivity",
        "status": "failed",
        "details": {},
    }

    try:
        # Test voice endpoints availability
        voice_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice", timeout=10
        )
        test_details["details"]["voice_endpoints"] = {
            "status_code": voice_endpoints_response.status_code,
            "available": voice_endpoints_response.status_code == 200,
        }

        # Test ElevenLabs connection
        elevenlabs_connection_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/elevenlabs/connection", timeout=10
        )
        test_details["details"]["elevenlabs_connection"] = {
            "status_code": elevenlabs_connection_response.status_code,
            "connected": elevenlabs_connection_response.status_code == 200,
            "account_info": elevenlabs_connection_response.json()
            if elevenlabs_connection_response.status_code == 200
            else None,
        }

        # Test wake word service
        wake_word_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/wake-word", timeout=10
        )
        test_details["details"]["wake_word_service"] = {
            "status_code": wake_word_response.status_code,
            "available": wake_word_response.status_code == 200,
        }

        # Test voice models availability
        models_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/models", timeout=10
        )
        test_details["details"]["voice_models"] = {
            "status_code": models_response.status_code,
            "models_count": len(models_response.json().get("models", []))
            if models_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["voice_endpoints"]["available"]
            and test_details["details"]["elevenlabs_connection"]["connected"]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_text_to_speech(config: TestConfig) -> Dict[str, Any]:
    """Test text-to-speech capabilities"""
    test_name = "text_to_speech"
    test_details = {
        "test_name": test_name,
        "description": "Test text-to-speech conversion and audio generation",
        "status": "failed",
        "details": {},
    }

    try:
        # Test TTS with simple message
        test_message = {
            "text": "Hello, this is a test message from Atom E2E voice tests.",
            "voice_model": "default",
            "test_mode": True
        }

        tts_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/voice/tts",
            json=test_message,
            timeout=30
        )

        test_details["details"]["tts_conversion"] = {
            "status_code": tts_response.status_code,
            "audio_generated": tts_response.status_code == 200,
            "audio_format": tts_response.headers.get("Content-Type")
            if tts_response.status_code == 200
            else None,
            "audio_size": len(tts_response.content)
            if tts_response.status_code == 200
            else 0,
        }

        # Test TTS with different voice models
        if test_details["details"]["tts_conversion"]["audio_generated"]:
            voice_models = ["rachel", "matthew", "emma"]
            model_results = {}

            for model in voice_models:
                try:
                    model_test = {
                        "text": f"Testing voice model {model}",
                        "voice_model": model,
                        "test_mode": True
                    }

                    model_response = requests.post(
                        f"{config.BACKEND_URL}/api/v1/voice/tts",
                        json=model_test,
                        timeout=20
                    )

                    model_results[model] = {
                        "status_code": model_response.status_code,
                        "successful": model_response.status_code == 200,
                    }
                except Exception as e:
                    model_results[model] = {"error": str(e)}

            test_details["details"]["voice_models_test"] = model_results

        # Test TTS with SSML (if supported)
        ssml_test = {
            "text": "<speak>This is a <break time='500ms'/> test with SSML.</speak>",
            "voice_model": "default",
            "use_ssml": True,
            "test_mode": True
        }

        ssml_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/voice/tts",
            json=ssml_test,
            timeout=30
        )

        test_details["details"]["ssml_support"] = {
            "status_code": ssml_response.status_code,
            "ssml_supported": ssml_response.status_code == 200,
        }

        # Determine test status
        if test_details["details"]["tts_conversion"]["audio_generated"]:
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_speech_to_text(config: TestConfig) -> Dict[str, Any]:
    """Test speech-to-text capabilities"""
    test_name = "speech_to_text"
    test_details = {
        "test_name": test_name,
        "description": "Test speech-to-text conversion and transcription",
        "status": "failed",
        "details": {},
    }

    try:
        # Test STT endpoint availability
        stt_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/stt", timeout=10
        )
        test_details["details"]["stt_endpoints"] = {
            "status_code": stt_endpoints_response.status_code,
            "available": stt_endpoints_response.status_code == 200,
        }

        # Note: Actual audio file upload testing would require test audio files
        # For now, test the endpoint structure and error handling

        # Test STT with empty payload (should return proper error)
        empty_payload_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/voice/stt",
            json={},
            timeout=10
        )

        test_details["details"]["stt_error_handling"] = {
            "status_code": empty_payload_response.status_code,
            "proper_error": empty_payload_response.status_code != 200,
        }

        # Test supported audio formats
        formats_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/stt/formats", timeout=10
        )
        test_details["details"]["supported_formats"] = {
            "status_code": formats_response.status_code,
            "formats": formats_response.json().get("formats", [])
            if formats_response.status_code == 200
            else [],
        }

        # Test transcription configuration
        config_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/stt/config", timeout=10
        )
        test_details["details"]["stt_config"] = {
            "status_code": config_response.status_code,
            "config": config_response.json()
            if config_response.status_code == 200
            else None,
        }

        # Determine test status - focus on endpoint availability and structure
        if (
            test_details["details"]["stt_endpoints"]["available"]
            and test_details["details"]["stt_error_handling"]["proper_error"]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_voice_commands(config: TestConfig) -> Dict[str, Any]:
    """Test voice command processing and execution"""
    test_name = "voice_commands"
    test_details = {
        "test_name": test_name,
        "description": "Test voice command processing and action execution",
        "status": "failed",
        "details": {},
    }

    try:
        # Test voice command endpoints
        command_endpoints_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/commands", timeout=10
        )
        test_details["details"]["command_endpoints"] = {
            "status_code": command_endpoints_response.status_code,
            "available": command_endpoints_response.status_code == 200,
        }

        # Test voice command processing with text input
        test_commands = [
            "What time is it?",
            "Show me my tasks",
            "Send a message to the team",
            "Schedule a meeting for tomorrow",
            "Search for project documents"
        ]

        command_results = {}
        for i, command in enumerate(test_commands):
            try:
                command_payload = {
                    "command": command,
                    "input_type": "text",  # Simulating transcribed voice
                    "user_id": "test_user",
                    "test_mode": True
                }

                command_response = requests.post(
                    f"{config.BACKEND_URL}/api/v1/voice/commands/process",
                    json=command_payload,
                    timeout=15
                )

                command_results[f"command_{i + 1}"] = {
                    "command": command,
                    "status_code": command_response.status_code,
                    "processed": command_response.status_code == 200,
                    "response_type": type(command_response.json()).__name__
                    if command_response.status_code == 200
                    else None,
                    "action_triggered": command_response.json().get("action_triggered", False)
                    if command_response.status_code == 200
                    else False,
                }
            except Exception as e:
                command_results[f"command_{i + 1}"] = {
                    "command": command,
                    "error": str(e),
                }

        test_details["details"]["voice_command_processing"] = command_results

        # Calculate success rate
        successful_commands = sum(
            1
            for cmd in command_results.values()
            if cmd.get("processed", False)
        )
        test_details["details"]["command_success_rate"] = successful_commands / len(test_commands)

        # Test command history
        history_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/commands/history", timeout=10
        )
        test_details["details"]["command_history"] = {
            "status_code": history_response.status_code,
            "history_available": history_response.status_code == 200,
            "commands_count": len(history_response.json().get("commands", []))
            if history_response.status_code == 200
            else 0,
        }

        # Determine test status
        if (
            test_details["details"]["command_endpoints"]["available"]
            and successful_commands >= 3  # At least 60% success rate
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_wake_word_detection(config: TestConfig) -> Dict[str, Any]:
    """Test wake word detection capabilities"""
    test_name = "wake_word_detection"
    test_details = {
        "test_name": test_name,
        "description": "Test wake word detection and activation",
        "status": "failed",
        "details": {},
    }

    try:
        # Test wake word configuration
        wake_word_config_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/wake-word/config", timeout=10
        )
        test_details["details"]["wake_word_config"] = {
            "status_code": wake_word_config_response.status_code,
            "config_available": wake_word_config_response.status_code == 200,
            "wake_words": wake_word_config_response.json().get("wake_words", [])
            if wake_word_config_response.status_code == 200
            else [],
        }

        # Test wake word activation
        activation_test = {
            "wake_word": "atom",
            "test_mode": True
        }

        activation_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/voice/wake-word/activate",
            json=activation_test,
            timeout=10
        )

        test_details["details"]["wake_word_activation"] = {
            "status_code": activation_response.status_code,
            "activation_supported": activation_response.status_code == 200,
            "listening_active": activation_response.json().get("listening", False)
            if activation_response.status_code == 200
            else False,
        }

        # Test wake word sensitivity
        sensitivity_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/wake-word/sensitivity", timeout=10
        )
        test_details["details"]["wake_word_sensitivity"] = {
            "status_code": sensitivity_response.status_code,
            "sensitivity_configurable": sensitivity_response.status_code == 200,
        }

        # Test wake word statistics
        stats_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/wake-word/stats", timeout=10
        )
        test_details["details"]["wake_word_stats"] = {
            "status_code": stats_response.status_code,
            "stats_available": stats_response.status_code == 200,
        }

        # Determine test status
        if (
            test_details["details"]["wake_word_config"]["config_available"]
            and test_details["details"]["wake_word_activation"]["activation_supported"]
        ):
            test_details["status"] = "passed"

    except Exception as e:
        test_details["details"]["error"] = str(e)

    return {
        "tests_run": 1,
        "tests_passed": 1 if test_details["status"] == "passed" else 0,
        "tests_failed": 0 if test_details["status"] == "passed" else 1,
        "test_details": {test_name: test_details},
        "test_outputs": {test_name: test_details["details"]},
    }


def _test_voice_workflows(config: TestConfig) -> Dict[str, Any]:
    """Test voice-triggered workflow automation"""
    test_name = "voice_workflows"
    test_details = {
        "test_name": test_name,
        "description": "Test voice-triggered workflow creation and execution",
        "status": "failed",
        "details": {},
    }

    try:
        # Test voice workflow endpoints
        voice_workflow_response = requests.get(
            f"{config.BACKEND_URL}/api/v1/voice/workflows", timeout=10
        )
        test_details["details"]["voice_workflow_endpoints"] = {
            "status_code": voice_workflow_response.status_code,
            "available": voice_workflow_response.status_code == 200,
        }

        # Test voice-triggered workflow creation
        voice_workflow_payload = {
            "name": f"Voice Test Workflow - {time.time()}",
            "trigger_phrase": "automate my meeting follow-ups",
            "description": "Create a workflow that sends follow-up emails after meetings",
            "actions": [
                {
                    "service": "gmail",
                    "action": "send_email",
                    "parameters": {
                        "template": "meeting_follow_up",
                        "recipients": ["team@example.com"]
                    }
                }
            ],
            "test_mode": True
        }

        workflow_creation_response = requests.post(
            f"{config.BACKEND_URL}/api/v1/voice/workflows",
            json=voice_workflow_payload,
