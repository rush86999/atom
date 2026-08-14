# -*- coding: utf-8 -*-
"""Coverage wave 85 — voice AI service, chat interface, PDF memory integration.

Standalone, zero network, no LLM spend, no real DB. All external boundaries
(audio/ML libs, Slack, memory/search services, LanceDB, BYOK) are mocked.
"""
import json
import os
import sqlite3
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import integrations.atom_voice_ai_service as voice_mod
from integrations.atom_voice_ai_service import (
    AtomVoiceAIService,
    VoiceEmotion,
    VoiceFormat,
    VoiceLanguage,
    VoiceRequest,
    VoiceSentiment,
    VoiceTaskType,
)

import integrations.atom_chat_interface as chat_mod
from integrations.atom_chat_interface import AtomChatInterface, ChatMessage

import integrations.pdf_processing.pdf_memory_integration as pdf_mod
from integrations.pdf_processing.pdf_memory_integration import PDFMemoryIntegration


# ============================================================================
# Helpers — voice
# ============================================================================

@pytest.fixture()
def vbrk(monkeypatch):
    """Make circuit breaker / rate limiter always allow."""
    cb = MagicMock()
    cb.is_enabled = AsyncMock(return_value=True)
    rl = MagicMock()
    rl.is_rate_limited = AsyncMock(return_value=(False, 10))
    monkeypatch.setattr(voice_mod, "circuit_breaker", cb)
    monkeypatch.setattr(voice_mod, "rate_limiter", rl)
    return cb, rl


def make_voice_service(**config_over):
    config = {
        "whisper_model": "base",
        "enable_enterprise_features": False,
        "database": None,
        "cache": None,
    }
    config.update(config_over)
    return AtomVoiceAIService(config=config)  # note: first positional is tenant_id


def make_request(task=VoiceTaskType.TRANSCRIPTION, lang=VoiceLanguage.ENGLISH,
                 fmt=VoiceFormat.WAV, audio=b"RIFFwav-bytes", metadata=None):
    return VoiceRequest(
        request_id="req-1",
        task_type=task,
        model_type=voice_mod.VoiceModelType.WHISPER,
        language=lang,
        audio_path=None,
        audio_data=audio,
        format=fmt,
        sample_rate=16000,
        duration=1.0,
        platform="slack",
        user_id="u1",
        metadata=metadata or {},
    )


def whisper_mock(text="hello world", logprob=-0.4):
    m = MagicMock()
    m.transcribe = MagicMock(return_value={"text": text, "avg_logprob": logprob, "segments": [1, 2]})
    return m


# ============================================================================
# Voice AI: init / lifecycle
# ============================================================================

async def test_voice_init_defaults():
    svc = make_voice_service()
    assert svc.db is None and svc.cache is None
    assert svc.voice_config["whisper_model"] == "base"
    assert svc.speech_recognizer is None  # SR unavailable in env
    assert svc.platform_integrations == {}  # optional imports absent
    assert svc.analytics_metrics["total_voice_requests"] == 0
    assert svc.command_patterns == {}
    assert isinstance(svc.analytics_metrics["language_distribution"], dict)


async def test_voice_initialize_success(vbrk):
    svc = make_voice_service()
    assert await svc.initialize() is True
    assert svc.is_initialized
    assert len(svc.command_patterns) == 8
    assert "start_meeting" in svc.command_patterns


async def test_voice_initialize_failure(vbrk, monkeypatch):
    svc = make_voice_service()
    async def boom():
        raise RuntimeError("boom")
    monkeypatch.setattr(svc, "_setup_language_models", boom)
    assert await svc.initialize() is False
    assert not svc.is_initialized


async def test_voice_initialize_enterprise_features(vbrk):
    svc = make_voice_service(enable_enterprise_features=True)
    assert await svc.initialize() is True
    assert svc.voice_data_retention["auto_delete"] is True
    assert "gdpr" in svc.voice_compliance_standards
    assert svc.voice_security_policies["data_encryption"]["enabled"] is True


async def test_voice_close_success_and_guard_rails(vbrk, monkeypatch):
    svc = make_voice_service()
    svc.whisper_model = object()
    await svc.close()
    assert svc.whisper_model is None

    # guard rails raise inside close's own try -> swallowed and logged
    cb, rl = vbrk
    cb.is_enabled = AsyncMock(return_value=False)
    await svc.close()  # no raise
    cb.is_enabled = AsyncMock(return_value=True)
    rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    await svc.close()  # no raise


async def test_voice_get_service_status():
    svc = make_voice_service()
    status = await svc.get_service_status()
    assert status["service"] == "voice_ai"
    assert status["status"] == "inactive"
    assert status["models_loaded"]["whisper"] is False
    assert "uptime" in status
    svc._start_time = 0.0
    status2 = await svc.get_service_status()
    assert status2["uptime"] > 0


# ============================================================================
# Voice AI: process_voice_request guard rails
# ============================================================================

async def test_voice_process_circuit_breaker_open(vbrk, monkeypatch):
    cb, rl = vbrk
    cb.is_enabled = AsyncMock(return_value=False)
    svc = make_voice_service()
    # HTTPException raised inside the outer try -> converted to error response
    resp = await svc.process_voice_request(make_request())
    assert resp.success is False
    assert resp.metadata["error"] == "Voice request processing failed"


async def test_voice_process_rate_limited(vbrk):
    cb, rl = vbrk
    rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    svc = make_voice_service()
    resp = await svc.process_voice_request(make_request())
    assert resp.success is False
    assert resp.metadata["error"] == "Voice request processing failed"


async def test_voice_process_unsupported_task(vbrk):
    svc = make_voice_service()
    resp = await svc.process_voice_request(make_request(task=VoiceTaskType.VOICE_SYNTHESIS))
    assert resp.success is False
    assert resp.metadata["error"] == "Unsupported task type"


async def test_voice_process_security_check_fail(vbrk, monkeypatch):
    svc = make_voice_service(enable_enterprise_features=True)
    async def fail(request):
        return {"passed": False, "reason": "policy violation"}
    monkeypatch.setattr(svc, "_perform_security_check", fail)
    resp = await svc.process_voice_request(make_request())
    assert resp.success is False
    assert resp.metadata["error"] == "policy violation"


async def test_voice_process_unexpected_exception_returns_error(vbrk, monkeypatch):
    svc = make_voice_service()
    async def boom(request):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(svc, "_preprocess_audio", boom)
    resp = await svc.process_voice_request(make_request())
    assert resp.success is False
    assert resp.metadata["error"] == "Voice request processing failed"


# ============================================================================
# Voice AI: STT / tasks
# ============================================================================

async def test_voice_transcribe_success(vbrk):
    svc = make_voice_service()
    svc.whisper_model = whisper_mock("transcribed text")
    resp = await svc._transcribe_audio(make_request(), b"audio")
    assert resp.success is True
    assert resp.text == "transcribed text"
    assert resp.confidence == -0.4
    assert resp.metadata["model"] == "whisper"
    assert svc.analytics_metrics["successful_transcriptions"] == 1
    assert svc.analytics_metrics["average_confidence"] == -0.4


async def test_voice_transcribe_non_english_language_arg(vbrk):
    svc = make_voice_service()
    m = whisper_mock()
    svc.whisper_model = m
    await svc._transcribe_audio(make_request(lang=VoiceLanguage.SPANISH), b"audio")
    assert m.transcribe.call_args.kwargs["language"] == "es"


async def test_voice_transcribe_failure(vbrk):
    svc = make_voice_service()  # whisper_model None -> AttributeError -> error
    resp = await svc._transcribe_audio(make_request(), b"audio")
    assert resp.success is False
    assert resp.metadata["error"] == "Audio transcription failed"


async def test_voice_translate_success(vbrk, monkeypatch):
    svc = make_voice_service()
    svc.whisper_model = whisper_mock("hola mundo")
    translator = MagicMock(return_value=[{"translation_text": "hello world"}])
    monkeypatch.setattr(voice_mod, "pipeline", lambda *a, **k: translator)
    resp = await svc.process_voice_request(
        make_request(task=VoiceTaskType.TRANSLATION, lang=VoiceLanguage.SPANISH,
                     metadata={"target_language": "en"})
    )
    assert resp.success is True
    assert resp.translation == {"source_language": "es", "target_language": "en",
                                "translated_text": "hello world"}
    assert translator.call_args.kwargs["src_lang"] == "es"
    assert svc.analytics_metrics["successful_translations"] == 1


async def test_voice_translate_transcription_fails(vbrk):
    svc = make_voice_service()  # no whisper -> transcribe fails
    resp = await svc._translate_speech(make_request(task=VoiceTaskType.TRANSLATION), b"a")
    assert resp.success is False


async def test_voice_translate_pipeline_fails(vbrk, monkeypatch):
    svc = make_voice_service()
    svc.whisper_model = whisper_mock()
    def boom(*a, **k):
        raise RuntimeError("no pipeline")
    monkeypatch.setattr(voice_mod, "pipeline", boom)
    resp = await svc._translate_speech(make_request(task=VoiceTaskType.TRANSLATION), b"a")
    assert resp.success is False
    assert resp.metadata["error"] == "Speech translation failed"


async def test_voice_recognize_command_match_and_miss(vbrk):
    svc = make_voice_service()
    await svc._initialize_command_patterns()
    svc.whisper_model = whisper_mock("please start meeting now")
    resp = await svc._recognize_command(make_request(task=VoiceTaskType.COMMAND_RECOGNITION), b"a")
    assert resp.success is True
    assert resp.metadata["matched_command"]["type"] == "start_meeting"
    assert svc.analytics_metrics["successful_commands"] == 1

    svc.whisper_model = whisper_mock("completely unrelated words")
    resp2 = await svc._recognize_command(make_request(task=VoiceTaskType.COMMAND_RECOGNITION), b"a")
    assert resp2.success is False
    assert resp2.metadata["matched_command"] is None


async def test_voice_recognize_command_failure(vbrk):
    svc = make_voice_service()
    # transcription itself fails -> early transcription error response
    resp = await svc._recognize_command(make_request(), b"a")
    assert resp.success is False
    assert resp.metadata["error"] == "Audio transcription failed"

    # transcription succeeds but command matching blows up
    svc.whisper_model = whisper_mock("hello")
    svc.command_patterns = {"broken": {}}  # missing 'patterns' key -> KeyError
    resp2 = await svc._recognize_command(make_request(), b"a")
    assert resp2.success is False
    assert resp2.metadata["error"] == "Command recognition failed"


def test_voice_extract_command_parameters():
    svc = make_voice_service()
    params = svc._extract_command_parameters("translate to spanish", "translate")
    assert params == {"target_language": "spanish"}
    assert svc._extract_command_parameters("translate", "translate") == {}


async def test_voice_sentiment_all_labels(vbrk):
    for label, expected in [("POSITIVE", VoiceSentiment.POSITIVE),
                            ("NEGATIVE", VoiceSentiment.NEGATIVE),
                            ("NEUTRAL", VoiceSentiment.NEUTRAL)]:
        svc = make_voice_service()
        svc.whisper_model = whisper_mock("some text")
        svc.sentiment_model = MagicMock(return_value=[{"label": label, "score": 0.9}])
        resp = await svc._analyze_sentiment(make_request(task=VoiceTaskType.SENTIMENT_ANALYSIS), b"a")
        assert resp.sentiment is expected
        assert resp.confidence == 0.9
        assert svc.analytics_metrics["sentiment_distribution"][expected.value] == 1


async def test_voice_sentiment_failure(vbrk):
    svc = make_voice_service()  # whisper missing -> transcription fails early return
    resp = await svc._analyze_sentiment(make_request(), b"a")
    assert resp.success is False
    svc2 = make_voice_service()
    svc2.whisper_model = whisper_mock()
    svc2.sentiment_model = None
    resp2 = await svc2._analyze_sentiment(make_request(), b"a")
    assert resp2.success is False
    assert resp2.metadata["error"] == "Sentiment analysis failed"


async def test_voice_detect_emotion_heuristics(vbrk, monkeypatch):
    import numpy as np
    for centroid, zcr, expected in [(2500.0, 0.2, VoiceEmotion.EXCITED),
                                    (800.0, 0.01, VoiceEmotion.CALM),
                                    (1500.0, 0.2, VoiceEmotion.ANGRY),
                                    (1500.0, 0.08, VoiceEmotion.NEUTRAL)]:
        svc = make_voice_service()
        lib = MagicMock()
        lib.load = MagicMock(return_value=(np.zeros(100), 16000))
        lib.feature.mfcc = MagicMock(return_value=np.zeros((13, 10)))
        lib.feature.spectral_centroid = MagicMock(return_value=np.array([centroid]))
        lib.feature.zero_crossing_rate = MagicMock(return_value=np.array([zcr]))
        monkeypatch.setattr(voice_mod, "librosa", lib)
        resp = await svc._detect_emotion(make_request(task=VoiceTaskType.EMOTION_DETECTION), b"a")
        assert resp.success is True
        assert resp.emotion is expected
        assert resp.confidence == 0.7


async def test_voice_detect_emotion_failure(vbrk, monkeypatch):
    svc = make_voice_service()
    lib = MagicMock()
    lib.load = MagicMock(side_effect=RuntimeError("corrupt"))
    monkeypatch.setattr(voice_mod, "librosa", lib)
    resp = await svc._detect_emotion(make_request(), b"a")
    assert resp.success is False
    assert resp.metadata["error"] == "Emotion detection failed"


async def test_voice_preprocess_wav_passthrough(vbrk):
    svc = make_voice_service()
    out = await svc._preprocess_audio(make_request(fmt=VoiceFormat.WAV, audio=b"raw"))
    assert out == b"raw"


async def test_voice_preprocess_conversion_and_fallback(vbrk, monkeypatch):
    svc = make_voice_service()
    seg = MagicMock()
    seg.set_frame_rate.return_value.set_channels.return_value.export.return_value.read.return_value = b"converted"
    monkeypatch.setattr(voice_mod, "AudioSegment", MagicMock(from_file=MagicMock(return_value=seg)))
    out = await svc._preprocess_audio(make_request(fmt=VoiceFormat.MP3, audio=b"raw"))
    assert out == b"converted"
    assert svc.performance_metrics["audio_preprocessing_time"] >= 0

    # conversion blows up -> falls back to raw audio_data
    monkeypatch.setattr(voice_mod, "AudioSegment", MagicMock(from_file=MagicMock(side_effect=ValueError("bad"))))
    out2 = await svc._preprocess_audio(make_request(fmt=VoiceFormat.OGG, audio=b"raw2"))
    assert out2 == b"raw2"


async def test_voice_request_logging_enterprise(vbrk):
    security = MagicMock()
    security.audit_event = AsyncMock()
    svc = make_voice_service(enable_enterprise_features=True, security_service=security)
    svc.whisper_model = whisper_mock("hello")
    resp = await svc.process_voice_request(make_request())
    assert resp.success is True
    security.audit_event.assert_awaited_once()
    event = security.audit_event.await_args.args[0]
    assert event["event_type"] == "voice_ai_request"
    assert event["result"] == "success"


async def test_voice_perform_security_check_branches():
    svc = make_voice_service()  # no enterprise security -> passes
    assert (await svc._perform_security_check(make_request()))["passed"] is True
    svc.enterprise_security = MagicMock()
    assert (await svc._perform_security_check(make_request()))["passed"] is True


async def test_voice_load_models_failure_swallowed(vbrk):
    svc = make_voice_service()
    await svc._load_voice_models()  # whisper not installed -> exception logged
    assert svc.whisper_model is None


async def test_voice_load_models_guard_rails(monkeypatch):
    cb = MagicMock(); cb.is_enabled = AsyncMock(return_value=False)
    rl = MagicMock(); rl.is_rate_limited = AsyncMock(return_value=(False, 1))
    monkeypatch.setattr(voice_mod, "circuit_breaker", cb)
    monkeypatch.setattr(voice_mod, "rate_limiter", rl)
    svc = make_voice_service()
    await svc._load_voice_models()  # breaker open -> swallowed, no models
    assert svc.whisper_model is None
    cb.is_enabled = AsyncMock(return_value=True)
    rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    await svc._load_voice_models()  # rate limited -> swallowed
    assert svc.whisper_model is None


# ============================================================================
# Chat interface fixtures
# ============================================================================

class _WS:
    def __init__(self, id, name, domain):
        self.id, self.name, self.domain = id, name, domain


@pytest.fixture()
def chat():
    iface = AtomChatInterface({"slack": {}})
    iface.memory_service = AsyncMock()
    iface.search_service = AsyncMock()
    iface.slack_service = AsyncMock()
    return iface


def _ctx(conv="c1"):
    return {"conversation_id": conv, "channel": "default"}


# ============================================================================
# Chat: message routing
# ============================================================================

async def test_chat_process_regular_message_default(chat):
    out = await chat.process_message("just saying hi", "u1", "Alice", context=_ctx())
    assert isinstance(out, str) and out


async def test_chat_process_command_and_unknown(chat):
    out = await chat.process_message("/bogus-command", "u1", "A", context=_ctx())
    assert "Unknown command" in out
    out2 = await chat.process_message("/help", "u1", "A", context=_ctx())
    assert "/slack-connect" in out2


async def test_chat_process_invalid_syntax(chat):
    out = await chat.process_message("/remember", "u1", "A", context=_ctx())
    assert "Invalid command syntax" in out


async def test_chat_process_message_error_returns_apology(chat, monkeypatch):
    def boom(cid, uid):
        raise RuntimeError("no ctx")
    monkeypatch.setattr(chat, "_get_context", boom)
    out = await chat.process_message("hi", "u1", "A")
    assert out.startswith("Sorry, I encountered an error")


async def test_chat_command_handler_exception(chat, monkeypatch):
    async def boom(msg, *a):
        raise RuntimeError("x")
    chat.commands["help"].handler = boom
    out = await chat.process_message("/help", "u1", "A", context=_ctx())
    assert out == "Error executing command. Please try again."


async def test_chat_requires_slack_not_connected(chat):
    out = await chat.process_message("/slack-channels", "u1", "A", context=_ctx())
    assert "requires Slack" in out


async def test_chat_permission_denied(chat):
    chat.commands["custom"] = chat_mod.SlackCommand(
        trigger="custom", pattern=r"/custom(?:\s+(.+))?", handler=AsyncMock(return_value="x"),
        description="d", permission_level="admin")
    out = await chat.process_message("/custom", "u1", "A", context=_ctx())
    assert "permission" in out


# ============================================================================
# Chat: slack handlers
# ============================================================================

async def test_chat_slack_connect_no_service(chat):
    chat.slack_service = None
    assert (await chat._handle_slack_connect(chat_msg())) == "Slack service is not available."


_UNSET = object()


def chat_msg(text="/help", ctx=_UNSET, user="u1"):
    if ctx is _UNSET:
        ctx = _ctx()
    return ChatMessage(id="m1", user_id=user, user_name="A", message=text,
                       timestamp=datetime.now(timezone.utc), channel="default",
                       context=ctx, source="user")


async def test_chat_slack_connect_specific_workspace(chat):
    chat.slack_service.test_connection = AsyncMock(return_value={"connected": True, "team": "Atom"})
    out = await chat._handle_slack_connect(chat_msg(), "ws1")
    assert "Successfully connected" in out and "Atom" in out
    assert chat.slack_connected

    chat.slack_service.test_connection = AsyncMock(return_value={"connected": False, "error": "bad token"})
    out2 = await chat._handle_slack_connect(chat_msg(), "ws1")
    assert "Failed to connect" in out2 and "bad token" in out2


async def test_chat_slack_connect_list_workspaces(chat):
    chat.slack_service.list_workspaces = AsyncMock(
        return_value=[_WS("w1", "Atom", "atomhq"), _WS("w2", "Side", "side")])
    out = await chat._handle_slack_connect(chat_msg())
    assert "atomhq.slack.com" in out and "w2" in out

    chat.slack_service.list_workspaces = AsyncMock(return_value=[])
    out2 = await chat._handle_slack_connect(chat_msg())
    assert "No workspaces" in out2


async def test_chat_slack_connect_error(chat):
    chat.slack_service.test_connection = AsyncMock(side_effect=RuntimeError("net"))
    assert (await chat._handle_slack_connect(chat_msg(), "w")) == "Error connecting to Slack."


async def test_chat_slack_channels_not_connected(chat):
    assert "connect" in await chat._handle_slack_channels(chat_msg())


async def test_chat_slack_channels_list_and_switch(chat):
    chat.slack_connected = True
    channels = [{"name": "general", "id": "C1", "num_members": 5},
                {"name": "dev", "id": "C2", "num_members": 3}]
    chat.slack_service.list_channels = AsyncMock(return_value=channels)
    out = await chat._handle_slack_channels(chat_msg())
    assert "#general (5 members)" in out

    out2 = await chat._handle_slack_channels(chat_msg("/slack-channels dev"), "dev")
    assert "Switched to Slack channel: #dev" in out2
    ctx = chat._get_context("c1", "u1")
    assert ctx.slack_channel_id == "C2"

    out3 = await chat._handle_slack_channels(chat_msg(), "nope")
    assert "not found" in out3


async def test_chat_slack_channels_error(chat):
    chat.slack_connected = True
    chat.slack_service.list_channels = AsyncMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_slack_channels(chat_msg())) == "Error listing channels."


async def test_chat_slack_send_variants(chat):
    m = chat_msg("/slack-send hello there")
    assert "connect" in await chat._handle_slack_send(m)  # not connected

    chat.slack_connected = True
    # channel via context
    chat._get_context("c1", "u1").slack_channel_id = "C1"
    chat.slack_service.post_message = AsyncMock(return_value={"ok": True})
    out = await chat._handle_slack_send(chat_msg(), None, "hello")
    assert "Message sent" in out

    # channel by name
    chat.slack_service.list_channels = AsyncMock(
        return_value=[{"name": "general", "id": "C1", "num_members": 1}])
    out2 = await chat._handle_slack_send(chat_msg(), "general", "hi")
    assert "Message sent to Slack channel #general" in out2

    # unknown channel name -> not found
    out3 = await chat._handle_slack_send(chat_msg(), "ghost", "hi")
    assert "Channel not found" in out3

    # no channel id in context
    chat._get_context("c1", "u1").slack_channel_id = None
    out4 = await chat._handle_slack_send(chat_msg(), None, "hi")
    assert "Channel not found" in out4

    # post failure
    chat._get_context("c1", "u1").slack_channel_id = "C1"
    chat.slack_service.post_message = AsyncMock(return_value={"ok": False, "error": "nope"})
    out5 = await chat._handle_slack_send(chat_msg(), None, "hi")
    assert "Failed to send" in out5


async def test_chat_slack_send_error(chat):
    chat.slack_connected = True
    chat._get_context("c1", "u1").slack_channel_id = "C1"
    chat.slack_service.post_message = AsyncMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_slack_send(chat_msg(), None, "hi")) == "Error sending message."


async def test_chat_slack_search(chat):
    assert "connect" in await chat._handle_slack_search(chat_msg(), "q")
    chat.slack_connected = True
    chat.slack_service.search_messages = AsyncMock(return_value={
        "ok": True,
        "messages": [{"user_name": "A", "channel_name": "gen", "text": "hello world", "ts": "1"}],
    })
    out = await chat._handle_slack_search(chat_msg(), "hello")
    assert "Found 1 results" in out and "hello world" in out

    chat.slack_service.search_messages = AsyncMock(return_value={"ok": True, "messages": []})
    assert "No messages found" in await chat._handle_slack_search(chat_msg(), "zzz")

    chat.slack_service.search_messages = AsyncMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_slack_search(chat_msg(), "q")) == "Error searching Slack."


async def test_chat_slack_workflows(chat, monkeypatch):
    wf = types.SimpleNamespace(id="wf1", name="deploy", description="Deploy things", active=True)
    automation = MagicMock()
    automation.list_workflows = MagicMock(return_value=[wf])
    automation.execute_workflow = AsyncMock(
        return_value=types.SimpleNamespace(id="exec9"))
    monkeypatch.setattr(chat_mod, "slack_workflow_automation", automation)

    out = await chat._handle_slack_workflows(chat_msg(), "list")
    assert "deploy - Deploy things" in out and "Active" in out

    out2 = await chat._handle_slack_workflows(chat_msg(), "run", "deploy")
    assert "Execution ID: exec9" in out2

    assert "specify a workflow" in await chat._handle_slack_workflows(chat_msg(), "run")
    assert "not found" in await chat._handle_slack_workflows(chat_msg(), "run", "ghost")
    assert "Available workflow actions" in await chat._handle_slack_workflows(chat_msg(), "bogus")

    automation.list_workflows = MagicMock(return_value=[])
    assert (await chat._handle_slack_workflows(chat_msg(), "list")) == "No workflows configured."
    automation.list_workflows = MagicMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_slack_workflows(chat_msg(), "list")) == "Error with workflows."


async def test_chat_workflows_no_automation(chat, monkeypatch):
    monkeypatch.setattr(chat_mod, "slack_workflow_automation", None)
    assert (await chat._handle_slack_workflows(chat_msg(), "list")) == "No workflows configured."
    assert (await chat._handle_slack_workflows(chat_msg(), "run", "x")) == "Workflow 'x' not found."


# ============================================================================
# Chat: memory / search / help / context
# ============================================================================

async def test_chat_remember_and_recall(chat):
    chat.memory_service = None
    assert (await chat._handle_remember(chat_msg(), "fact")) == "Memory service is not available."
    assert (await chat._handle_recall(chat_msg())) == "Memory service is not available."

    mem = AsyncMock()
    chat.memory_service = mem
    out = await chat._handle_remember(chat_msg("/remember x"), "the fact")
    assert out == "I'll remember: the fact"
    mem.store.assert_awaited_once()

    mem.search = AsyncMock(return_value=[{"content": "c1", "timestamp": "t1"},
                                         {"content": "c2", "timestamp": "t2"}])
    assert "Found memories" in await chat._handle_recall(chat_msg(), "fact")
    mem.search = AsyncMock(return_value=[])
    assert "No memories found for: fact" in await chat._handle_recall(chat_msg(), "fact")

    mem.get_recent = AsyncMock(return_value=[{"content": "recent", "timestamp": "t"}])
    assert "Recent memories" in await chat._handle_recall(chat_msg())
    mem.get_recent = AsyncMock(return_value=[])
    assert (await chat._handle_recall(chat_msg())) == "No memories found."

    mem.store = AsyncMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_remember(chat_msg(), "z")) == "Error storing information."
    mem.search = AsyncMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_recall(chat_msg(), "q")) == "Error recalling information."


async def test_chat_search(chat):
    chat.search_service = None
    assert (await chat._handle_search(chat_msg(), "q")) == "Search service is not available."
    ss = AsyncMock()
    chat.search_service = ss
    ss.search = AsyncMock(return_value=[{"title": "Doc", "source": "gdrive",
                                         "snippet": "snip", "text": "full", "timestamp": "t"}])
    out = await chat._handle_search(chat_msg(), "doc")
    assert "Found 1 results" in out and "Doc" in out
    ss.search = AsyncMock(return_value=[])
    assert "No results found" in await chat._handle_search(chat_msg(), "zz")
    ss.search = AsyncMock(side_effect=RuntimeError("x"))
    assert (await chat._handle_search(chat_msg(), "q")) == "Error searching."


async def test_chat_help(chat):
    full = await chat._handle_help(chat_msg())
    assert "/remember" in full
    specific = await chat._handle_help(chat_msg(), "search")
    assert "Command: /search" in specific
    unknown = await chat._handle_help(chat_msg(), "bogus")
    assert "Unknown command: bogus" in unknown


async def test_chat_context_actions(chat):
    no_ctx = chat_msg(ctx={})
    assert "No conversation context" in await chat._handle_context(no_ctx)

    show = await chat._handle_context(chat_msg("/context show"), "show")
    assert "Conversation ID: c1" in show
    clear = await chat._handle_context(chat_msg("/context clear"), "clear")
    assert clear == "Context cleared."
    set_topic = await chat._handle_context(chat_msg("/context set"), "set", "pricing")
    assert "pricing" in set_topic
    other = await chat._handle_context(chat_msg("/context"), "bogus")
    assert "Available context actions" in other


async def test_chat_context_show_populated(chat):
    ctx = chat._get_context("c9", "u1")
    ctx.slack_workspace_id = "W1"; ctx.slack_channel_id = "C1"
    ctx.current_topic = "t"; ctx.intents = ["send_message"]; ctx.entities = {"a": 1}
    ctx.messages.append(chat_msg())
    out = await chat._handle_context(chat_msg(ctx={"conversation_id": "c9"}), "show")
    assert "W1" in out and "send_message" in out and '"a": 1' in out


# ============================================================================
# Chat: intents, AI response, callbacks, sync
# ============================================================================

async def test_chat_extract_intents_entities(chat):
    intents, entities = await chat._extract_intents_entities("please send to #general and find it, remember this")
    assert intents == ["send_message", "search", "remember"]
    assert entities == {"channel": "general"}
    i2, e2 = await chat._extract_intents_entities("plain")
    assert i2 == [] and e2 == {}


async def test_chat_generate_ai_response_branches(chat):
    m = chat_msg("anything")
    m.context = {"conversation_id": "c1", "slack_channel_id": "C1"}
    assert "`/slack-" in await chat._generate_ai_response(m, [], {})

    m2 = chat_msg("anything", ctx=_ctx())
    assert "search across" in await chat._generate_ai_response(m2, ["search"], {})
    assert "send messages" in await chat._generate_ai_response(m2, ["send_message"], {})

    ctx = chat._get_context("c1", "u1")
    for _ in range(7):
        ctx.messages.append(chat_msg())
    assert "tracking our conversation" in await chat._generate_ai_response(m2, [], {})
    ctx.messages = []
    assert "here to help" in await chat._generate_ai_response(m2, [], {})


async def test_chat_regular_message_error_branch(chat, monkeypatch):
    async def boom(msg):
        raise RuntimeError("nlp down")
    monkeypatch.setattr(chat, "_extract_intents_entities", boom)
    out = await chat._process_regular_message(chat_msg("hi", ctx=_ctx()))
    assert "trouble generating a response" in out


async def test_chat_callbacks(chat):
    calls = []
    def sync_cb(msg):
        calls.append(("sync", msg.id))
    async def async_cb(msg):
        calls.append(("async", msg.id))
    bad = MagicMock(side_effect=RuntimeError("cb fail"))
    chat.add_message_callback(sync_cb)
    chat.add_message_callback(async_cb)
    chat.add_message_callback(bad)
    await chat._notify_callbacks(chat_msg())
    assert ("sync", "m1") in calls and ("async", "m1") in calls
    chat.remove_message_callback(sync_cb)
    chat.remove_message_callback(object())  # no-op
    assert sync_cb not in chat.message_callbacks


async def test_chat_save_context_error_swallowed(chat):
    chat.memory_service.store = AsyncMock(side_effect=RuntimeError("db"))
    ctx = chat._get_context("c1", "u1")
    await chat._save_context(ctx)  # must not raise


async def test_chat_conversation_history(chat):
    assert chat.get_conversation_history("nope") == []
    chat._get_context("c1", "u1").messages.append(chat_msg())
    assert len(chat.get_conversation_history("c1")) == 1


def test_chat_permissions_and_workspace(chat):
    assert chat._get_user_permissions("u1") == ["user"]
    assert chat._check_permissions(["user"], "user") is True
    assert chat._check_permissions(["user"], "admin") is False
    assert chat._check_permissions(["admin"], "user") is True
    assert chat._get_context_channel_workspace({}) is None
    ctx = chat._get_context("c1", "u1")
    ctx.slack_workspace_id = "W9"
    assert chat._get_context_channel_workspace({"conversation_id": "c1"}) == "W9"


async def test_chat_index_slack_content(chat):
    chat.slack_connected = False
    await chat.index_slack_content()  # early return

    chat.slack_connected = True
    chat.search_service = None
    await chat.index_slack_content()  # still early

    ss = AsyncMock()
    chat.search_service = ss
    chat.slack_workspaces = [{"id": "w1"}]
    chat.slack_service.list_channels = AsyncMock(return_value=[{"id": "C1"}])
    chat.slack_service.get_channel_history = AsyncMock(
        return_value=[{"ts": "1", "text": "hi", "user": "u"}])
    await chat.index_slack_content()
    ss.index.assert_awaited_once()
    assert ss.index.await_args.args[0]["source"] == "slack"

    chat.slack_service.list_channels = AsyncMock(side_effect=RuntimeError("x"))
    await chat.index_slack_content()  # error swallowed

    chat.slack_service = None
    await chat.sync_with_slack()  # no service -> no-op

    chat.slack_service = AsyncMock()
    chat.slack_service.list_workspaces = AsyncMock(return_value=[_WS("w1", "A", "a")])
    chat.slack_workspaces = []
    await chat.sync_with_slack()
    assert chat.slack_connected is True

    chat.slack_service.list_workspaces = AsyncMock(side_effect=RuntimeError("x"))
    await chat.sync_with_slack()  # error swallowed


# ============================================================================
# PDF memory integration
# ============================================================================

def make_lance():
    lance = MagicMock()
    lance.list_tables = MagicMock(return_value=["pdf_documents"])
    table = MagicMock()
    table.search = MagicMock(return_value=MagicMock(
        where=MagicMock(return_value=MagicMock(to_list=MagicMock(return_value=[])))))
    lance.get_table = MagicMock(return_value=table)
    lance.embed_text = MagicMock(return_value=[0.1] * 768)
    return lance


def make_pdf_service(tmp_path, monkeypatch, use_byok=False):
    """Build a PDFMemoryIntegration whose SQLite fallback lives in tmp_path.

    _init_simple_db derives its path from __file__ and overwrites any preset
    _simple_db_path, so we redirect sqlite3.connect for the repo DB instead.
    """
    repo_db = os.path.join(os.path.dirname(pdf_mod.__file__), "..", "data", "pdf_simple.db")
    repo_db = os.path.abspath(repo_db)
    tmp_db = str(tmp_path / "pdf.db")
    real_connect = sqlite3.connect

    def connect_redirect(path, *a, **k):
        if isinstance(path, str) and os.path.abspath(path) == repo_db:
            path = tmp_db
        return real_connect(path, *a, **k)

    monkeypatch.setattr(pdf_mod.sqlite3, "connect", connect_redirect)
    monkeypatch.setattr(pdf_mod, "BYOK_AVAILABLE", use_byok)
    return PDFMemoryIntegration(lancedb_handler=None, use_byok=use_byok)


@pytest.fixture()
def pdf(tmp_path, monkeypatch):
    return make_pdf_service(tmp_path, monkeypatch)


def proc_result(text="quarterly revenue report content", ocr=False, ratio=0.9):
    return {
        "extracted_content": {"text": text, "text_ratio": ratio},
        "processing_summary": {"total_pages": 3, "total_characters": len(text),
                               "best_method": "basic_pdf", "used_ocr": ocr},
        "file_metadata": {"filename": "report.pdf", "size_bytes": 1234},
    }


# ---- ingestion / storage ----

async def test_pdf_store_and_get_roundtrip(pdf):
    res = await pdf.store_processed_pdf("u1", proc_result(), source_uri="file:///x",
                                        tags=["finance"])
    assert res["success"] is True
    assert res["storage_methods"] == ["simple_format"]
    assert res["document_info"]["pages"] == 3
    doc = await pdf.get_document("u1", res["doc_id"])
    assert doc["filename"] == "report.pdf"
    assert doc["tags"] == []  # tags column not written by simple store
    assert await pdf.get_document("u1", "missing") is None


async def test_pdf_store_with_lancedb(pdf):
    lance = make_lance()
    pdf.lancedb_handler = lance
    res = await pdf.store_processed_pdf("u1", proc_result("word " * 50))
    assert res["success"] is True
    assert "lancedb" in res["storage_methods"]
    assert lance.get_table.return_value.add.called
    chunk = lance.get_table.return_value.add.call_args.args[0][0]
    assert chunk["embedding"] == [0.1] * 768


async def test_pdf_store_empty_text_lancedb_warning(pdf):
    lance = make_lance()
    pdf.lancedb_handler = lance
    res = await pdf.store_processed_pdf("u1", proc_result(""))
    assert res["success"] is True
    lance.get_table.return_value.add.assert_not_called()


async def test_pdf_store_lancedb_failure_returns_error(pdf):
    lance = make_lance()
    lance.embed_text = MagicMock(side_effect=RuntimeError("embed down"))
    pdf.lancedb_handler = lance
    res = await pdf.store_processed_pdf("u1", proc_result("some text"))
    assert res["success"] is False
    assert "embed down" in res["error"]


async def test_pdf_store_simple_unavailable(pdf):
    pdf._simple_db_path = None
    res = await pdf.store_processed_pdf("u1", proc_result())
    assert res["success"] is True  # lancedb absent + simple skipped -> still ok
    pdf.lancedb_handler = make_lance()
    res2 = await pdf.store_processed_pdf("u1", proc_result("text here"))
    assert res2["success"] is True


async def test_pdf_store_failure_branch(pdf, monkeypatch):
    monkeypatch.setattr(pdf, "_determine_pdf_type", MagicMock(side_effect=RuntimeError("x")))
    res = await pdf.store_processed_pdf("u1", proc_result())
    assert res["success"] is False and res["doc_id"] is None


async def test_pdf_determine_pdf_type(pdf):
    assert pdf._determine_pdf_type(proc_result(ocr=True)) == "scanned"
    assert pdf._determine_pdf_type(proc_result(ratio=0.9)) == "searchable"
    assert pdf._determine_pdf_type(proc_result(ratio=0.5)) == "mixed"
    assert pdf._determine_pdf_type(proc_result(ratio=0.1)) == "scanned"


def test_pdf_serialize_metadata(pdf):
    assert json.loads(pdf._serialize_metadata({"a": 1})) == {"a": 1}
    assert pdf._serialize_metadata({"bad": {1, 2}}) == "{}"  # set not serializable


def test_pdf_sliding_window_chunks(pdf):
    assert pdf._create_sliding_window_chunks("") == []
    text = "x" * 2500
    chunks = pdf._create_sliding_window_chunks(text, window_size=1000, overlap=200)
    assert chunks[0] == "x" * 1000
    assert chunks[-1].endswith("x")
    assert sum(1 for _ in chunks) >= 3


# ---- search ----

async def test_pdf_search_lancedb_dedup(pdf):
    lance = make_lance()
    lance.search = MagicMock(return_value=[
        {"doc_id": "d1", "filename": "a.pdf", "_distance": 0.4, "extracted_text": "hello query world", "page_count": 1, "total_chars": 10, "pdf_type": "searchable"},
        {"doc_id": "d1", "filename": "a.pdf", "_distance": 0.2, "extracted_text": "query again", "page_count": 1, "total_chars": 10, "pdf_type": "searchable"},
        {"doc_id": "d2", "filename": "b.pdf", "_distance": 0.9, "extracted_text": "other", "page_count": 2, "total_chars": 20, "pdf_type": "mixed"},
    ])
    pdf.lancedb_handler = lance
    results = await pdf.search_pdfs("u1", "query")
    assert [r["doc_id"] for r in results] == ["d1", "d2"]
    assert results[0]["similarity_score"] == 0.2  # best chunk wins
    expr = lance.search.call_args.kwargs["filter_expr"]
    assert "user_id = 'u1'" in expr


async def test_pdf_search_lancedb_filters_and_error(pdf):
    lance = make_lance()
    lance.search = MagicMock(return_value=[])
    pdf.lancedb_handler = lance
    await pdf.search_pdfs("u1", "q", filters={"pdf_type": "searchable", "tags": ["a", "b'b"]})
    expr = lance.search.call_args.kwargs["filter_expr"]
    assert "pdf_type = 'searchable'" in expr
    assert "IN tags" in expr and "'b''b'" in expr

    lance.search = MagicMock(side_effect=RuntimeError("boom"))
    assert await pdf.search_pdfs("u1", "q") == []  # lancedb fails -> simple fallback


async def test_pdf_search_simple_fts(pdf):
    await pdf.store_processed_pdf("u1", proc_result("uniquealpha document body"))
    results = await pdf.search_pdfs("u1", "uniquealpha")
    assert len(results) == 1
    assert results[0]["doc_id"]
    assert results[0]["filename"] == "report.pdf"
    assert "uniquealpha" in results[0]["excerpt"]


async def test_pdf_search_simple_filters_and_error(pdf):
    await pdf.store_processed_pdf("u1", proc_result("filterable text content"))
    results = await pdf.search_pdfs("u1", "filterable",
                                    filters={"pdf_type": "searchable", "processing_method": "basic_pdf"})
    assert len(results) == 1
    assert await pdf.search_pdfs("u1", "filterable", filters={"pdf_type": "scanned"}) == []

    pdf._simple_db_path = None
    assert await pdf._simple_search("u1", "q", 5, None) == []


async def test_pdf_search_no_storage(pdf):
    pdf._simple_db_path = None
    assert await pdf.search_pdfs("u1", "anything") == []


def test_pdf_get_text_excerpt(pdf):
    long_text = "filler " * 40 + "needle" + " tail " * 40
    ex = pdf._get_text_excerpt(long_text, "needle")
    assert "needle" in ex and ex.startswith("...")
    assert pdf._get_text_excerpt("", "q") == ""
    assert pdf._get_text_excerpt("short", "") == "short"
    assert pdf._get_text_excerpt("word " * 100, "shortword") .endswith("...")  # fallback branch
    pdf._get_text_excerpt("abc", "tiny")  # words <=3 chars skipped


# ---- get / delete / list ----

async def test_pdf_get_document_lancedb_first(pdf):
    lance = make_lance()
    row = {"doc_id": "d1", "filename": "x.pdf", "metadata": '{"k": "v"}'}
    lance.get_table.return_value.search.return_value.where.return_value.to_list = MagicMock(return_value=[row])
    pdf.lancedb_handler = lance
    doc = await pdf.get_document("u1", "d1")
    assert doc["filename"] == "x.pdf"
    assert doc["metadata"] == {"k": "v"}
    assert doc["tags"] == []

    # lancedb raises -> falls through to simple -> None
    lance.get_table = MagicMock(side_effect=RuntimeError("x"))
    assert await pdf.get_document("u1", "ghost") is None


async def test_pdf_get_simple_document_error(pdf):
    pdf._simple_db_path = None
    assert await pdf._get_simple_document("u1", "d") is None
    pdf._simple_db_path = "/nonexistent/dir/x.db"
    assert await pdf._get_simple_document("u1", "d") is None


async def test_pdf_delete_document(pdf):
    res = await pdf.store_processed_pdf("u1", proc_result("to be deleted"))
    doc_id = res["doc_id"]
    out = await pdf.delete_document("u1", doc_id)
    assert out["success"] is True
    assert "simple_storage" in out["deleted_from"]
    assert await pdf.get_document("u1", doc_id) is None

    lance = make_lance()
    pdf.lancedb_handler = lance
    out2 = await pdf.delete_document("u1", "other")
    assert "lancedb" in out2["deleted_from"]

    lance.get_table = MagicMock(side_effect=RuntimeError("x"))
    out3 = await pdf.delete_document("u1", "other")
    assert "lancedb" not in out3["deleted_from"]

    pdf._simple_db_path = None
    assert (await pdf._delete_simple_document("u1", "d"))["success"] is False
    pdf._simple_db_path = "/nonexistent/x.db"
    assert (await pdf._delete_simple_document("u1", "d"))["success"] is False


async def test_pdf_list_documents_sqlite_and_tags(pdf):
    for i in range(3):
        await pdf.store_processed_pdf("u1", proc_result(f"doc number {i} content"))
    await pdf.store_processed_pdf("u2", proc_result("other user"))
    listing = await pdf.list_documents("u1")
    assert listing["success"] is True and listing["total"] == 3
    limited = await pdf.list_documents("u1", limit=2, offset=1)
    assert len(limited["documents"]) == 2
    typed = await pdf.list_documents("u1", pdf_type="searchable")
    assert typed["total"] == 3
    dated = await pdf.list_documents("u1", date_from="2000-01-01", date_to="2099-01-01")
    assert dated["total"] == 3

    # tag filter (client-side) — docs have empty tags -> all filtered out
    tagged = await pdf.list_documents("u1", tags=["nope"])
    assert tagged["documents"] == [] and tagged["total"] == 0


async def test_pdf_list_documents_lancedb(pdf):
    lance = make_lance()
    rows = [{"doc_id": f"d{i}", "user_id": "u1", "filename": f"f{i}.pdf"} for i in range(3)]
    lance.get_table.return_value.search.return_value.where.return_value.to_list = MagicMock(return_value=rows)
    pdf.lancedb_handler = lance
    listing = await pdf.list_documents("u1", pdf_type="searchable",
                                       date_from="2020-01-01", date_to="2030-01-01", tags=None)
    assert listing["total"] == 3
    assert listing["documents"][0]["doc_id"] == "d0"
    where = lance.get_table.return_value.search.return_value.where.call_args.args[0]
    assert "pdf_type = 'searchable'" in where and "created_at >= '2020-01-01'" in where


async def test_pdf_list_documents_error(pdf, monkeypatch):
    monkeypatch.setattr(pdf_mod.sqlite3, "connect", MagicMock(side_effect=RuntimeError("db")))
    listing = await pdf.list_documents("u1")
    assert listing["success"] is False and listing["documents"] == []


# ---- tags ----

async def test_pdf_update_tags_validation(pdf):
    assert (await pdf.update_document_tags("u1", "d", "notalist"))["success"] is False
    assert (await pdf.update_document_tags("u1", "d", ["x" * 60]))["success"] is False


async def test_pdf_update_tags_sqlite(pdf):
    res = await pdf.store_processed_pdf("u1", proc_result("text"))
    doc_id = res["doc_id"]
    out = await pdf.update_document_tags("u1", doc_id, [" alpha ", "", "beta"])
    assert out["success"] is True and out["tags"] == ["alpha", "beta"]
    missing = await pdf.update_document_tags("u1", "ghost", ["t"])
    assert missing["success"] is False


async def test_pdf_update_tags_lancedb(pdf):
    lance = make_lance()
    pdf.lancedb_handler = lance
    lance.get_table.return_value.search.return_value.where.return_value.to_list = MagicMock(
        return_value=[{"doc_id": "d1"}])
    out = await pdf.update_document_tags("u1", "d1", ["t1"])
    assert out["success"] is True
    lance.get_table.return_value.search.return_value.where.return_value.to_list = MagicMock(return_value=[])
    out2 = await pdf.update_document_tags("u1", "ghost", ["t"])
    assert out2["success"] is False


async def test_pdf_tags_get_and_delete(pdf):
    res = await pdf.store_processed_pdf("u1", proc_result("text"))
    doc_id = res["doc_id"]
    await pdf.update_document_tags("u1", doc_id, ["one", "two"])
    got = await pdf.get_document_tags(doc_id, "u1")
    assert got["success"] is True and sorted(got["tags"]) == ["one", "two"]

    deleted = await pdf.delete_document_tags(doc_id, "u1", ["one"])
    assert deleted["success"] is True and deleted["remaining_tags"] == ["two"]

    assert (await pdf.get_document_tags("ghost", "u1"))["success"] is False
    assert (await pdf.delete_document_tags("ghost", "u1", ["x"]))["success"] is False


async def test_pdf_tags_no_sqlite(pdf):
    pdf._simple_db_path = None
    assert (await pdf.get_document_tags("d", "u1"))["success"] is False
    assert (await pdf.delete_document_tags("d", "u1", ["x"]))["success"] is False
    assert (await pdf.search_by_tags("u1", ["x"]))["success"] is False


async def test_pdf_search_by_tags(pdf):
    res1 = await pdf.store_processed_pdf("u1", proc_result("text one"))
    res2 = await pdf.store_processed_pdf("u1", proc_result("text two"))
    await pdf.update_document_tags("u1", res1["doc_id"], ["red", "blue"])
    await pdf.update_document_tags("u1", res2["doc_id"], ["blue"])

    any_match = await pdf.search_by_tags("u1", ["red", "blue"])
    assert any_match["count"] == 2
    all_match = await pdf.search_by_tags("u1", ["red", "blue"], match_all=True)
    assert all_match["count"] == 1
    assert all_match["documents"][0]["matched_tags"] == ["red", "blue"]


async def test_pdf_search_by_tags_bad_json_skipped(pdf):
    res = await pdf.store_processed_pdf("u1", proc_result("text"))
    conn = sqlite3.connect(pdf._simple_db_path)
    conn.execute("UPDATE pdf_documents SET tags = ? WHERE doc_id = ?", ("not-json", res["doc_id"]))
    conn.commit(); conn.close()
    out = await pdf.search_by_tags("u1", ["x"])
    assert out["success"] is True and out["count"] == 0


# ---- stats / BYOK ----

async def test_pdf_user_stats(pdf):
    lance = make_lance()
    lance.get_table.return_value.search.return_value.where.return_value.to_list = MagicMock(
        return_value=[{"page_count": 2, "total_chars": 100, "file_size": 50, "pdf_type": "searchable"},
                      {"page_count": 3, "total_chars": 200, "file_size": 60, "pdf_type": "mixed"}])
    pdf.lancedb_handler = lance
    stats = await pdf.get_user_document_stats("u1")
    assert stats["total_documents"] == 2
    assert stats["total_pages"] == 5
    assert stats["pdf_types"] == {"searchable": 1, "mixed": 1}

    lance.get_table = MagicMock(side_effect=RuntimeError("x"))
    stats2 = await pdf.get_user_document_stats("u1")
    assert stats2["total_documents"] == 0 and "error" in stats2


def test_pdf_byok_status_and_mapping(pdf):
    assert pdf.get_byok_status() == {"byok_integrated": False,
                                     "byok_manager_available": False,
                                     "tracking_enabled": False}
    assert pdf._map_processing_method_to_provider("", False) is None
    assert pdf._map_processing_method_to_provider("openai_vision", False) == "openai"
    assert pdf._map_processing_method_to_provider("tesseract", False) == "openai"
    assert pdf._map_processing_method_to_provider("easyocr", False) == "openai"
    assert pdf._map_processing_method_to_provider("basic_pdf", False) == "openai"
    assert pdf._map_processing_method_to_provider("unknown_method", True) == "openai"
    assert pdf._map_processing_method_to_provider("unknown_method", False) is None


async def test_pdf_store_tracks_byok_usage(tmp_path, monkeypatch):
    manager = MagicMock()
    monkeypatch.setattr(pdf_mod, "get_byok_manager", MagicMock(return_value=manager))
    svc = make_pdf_service(tmp_path, monkeypatch, use_byok=True)
    manager.get_optimal_provider = MagicMock(return_value="openai")

    res = await svc.store_processed_pdf("u1", proc_result("some text body"))
    assert res["success"] is True
    assert manager.track_usage.call_args.kwargs["provider_id"] == "openai"
    assert manager.track_usage.call_args.kwargs["tokens_used"] >= 100


async def test_pdf_byok_init_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_mod, "get_byok_manager", MagicMock(side_effect=RuntimeError("no byok")))
    svc = make_pdf_service(tmp_path, monkeypatch, use_byok=True)
    assert svc.use_byok is False
    assert svc.get_byok_status()["byok_integrated"] is False


async def test_pdf_search_byok_usage_and_failures(tmp_path, monkeypatch):
    manager = MagicMock()
    monkeypatch.setattr(pdf_mod, "get_byok_manager", MagicMock(return_value=manager))
    svc = make_pdf_service(tmp_path, monkeypatch, use_byok=True)
    manager.get_optimal_provider = MagicMock(return_value="openai")
    await svc.search_pdfs("u1", "find things")
    manager.track_usage.assert_called_once()

    manager.track_usage = MagicMock(side_effect=RuntimeError("track fail"))
    assert await svc.search_pdfs("u1", "find things") == []  # warning path, still returns

    def bad_provider(kind):
        raise RuntimeError("no provider")
    manager.track_usage = MagicMock()
    manager.get_optimal_provider = bad_provider
    assert await svc.search_pdfs("u1", "find things") == []
