"""Coverage push + bug-fix tests for integrations.atom_voice_ai_service.

Covers remaining uncovered branches (early-return on failed transcription,
temp-file cleanup on error paths, audit action names, str(e) leak removal).
All external I/O mocked.
"""
import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_voice_ai_service as vmod


@pytest.fixture(autouse=True)
def _allow_governance_gates():
    with patch.object(vmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=True)), \
         patch.object(vmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(False, 99))):
        yield


def _request(task_type, **kw):
    return vmod.VoiceRequest(
        request_id="r1", task_type=task_type, model_type=vmod.VoiceModelType.WHISPER,
        language=vmod.VoiceLanguage.ENGLISH, audio_path=None, audio_data=b"\x00\x01",
        format=vmod.VoiceFormat.WAV, sample_rate=16000, duration=1.0, platform="test",
        user_id="u1", metadata=kw.pop("metadata", {}), **kw,
    )


def _svc(**cfg):
    base = {"enable_enterprise_features": True, "security_level": "standard"}
    base.update(cfg)
    return vmod.AtomVoiceAIService(config=base)


class TestVoiceCoverageGaps:
    async def test_recognize_command_returns_failed_transcription(self):
        svc = _svc()
        failed = MagicMock(success=False)
        svc._transcribe_audio = AsyncMock(return_value=failed)
        resp = await svc._recognize_command(_request(vmod.VoiceTaskType.COMMAND_RECOGNITION), b"x")
        assert resp is failed

    async def test_analyze_sentiment_returns_failed_transcription(self):
        svc = _svc()
        failed = MagicMock(success=False)
        svc._transcribe_audio = AsyncMock(return_value=failed)
        resp = await svc._analyze_sentiment(_request(vmod.VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp is failed


class TestVoiceTempFileCleanup:
    async def test_transcribe_audio_unlinks_temp_file_on_error(self):
        svc = _svc()
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("decode failed")
        svc.whisper_model = model
        with patch("integrations.atom_voice_ai_service.os.unlink") as unlink:
            resp = await svc._transcribe_audio(_request(vmod.VoiceTaskType.TRANSCRIPTION), b"\x00" * 16)
        assert resp.success is False
        assert unlink.called

    async def test_transcribe_audio_unlinks_temp_file_on_success(self):
        svc = _svc()
        model = MagicMock()
        model.transcribe.return_value = {"text": "ok", "avg_logprob": -0.1, "segments": []}
        svc.whisper_model = model
        with patch("integrations.atom_voice_ai_service.os.unlink") as unlink:
            resp = await svc._transcribe_audio(_request(vmod.VoiceTaskType.TRANSCRIPTION), b"\x00" * 16)
        assert resp.success is True
        assert unlink.called

    async def test_detect_emotion_unlinks_temp_file_on_error(self):
        svc = _svc()
        librosa = MagicMock()
        librosa.load.side_effect = RuntimeError("no audio")
        with patch("integrations.atom_voice_ai_service.librosa", librosa), \
             patch("integrations.atom_voice_ai_service.os.unlink") as unlink:
            resp = await svc._detect_emotion(_request(vmod.VoiceTaskType.EMOTION_DETECTION), b"\x00" * 16)
        assert resp.success is False
        assert unlink.called

    async def test_transcribe_audio_unlink_oserror_is_swallowed(self):
        svc = _svc()
        model = MagicMock()
        model.transcribe.return_value = {"text": "ok", "avg_logprob": -0.1, "segments": []}
        svc.whisper_model = model
        with patch("integrations.atom_voice_ai_service.os.unlink", side_effect=OSError("gone")):
            resp = await svc._transcribe_audio(_request(vmod.VoiceTaskType.TRANSCRIPTION), b"\x00" * 16)
        assert resp.success is True

    async def test_detect_emotion_unlink_oserror_is_swallowed(self):
        svc = _svc()
        librosa = MagicMock()
        librosa.load.return_value = ([0.0, 0.0], 16000)
        librosa.feature.mfcc.return_value = [[0.0]]
        librosa.feature.spectral_centroid.return_value = [[500.0]]
        librosa.feature.zero_crossing_rate.return_value = [[0.01]]
        with patch("integrations.atom_voice_ai_service.librosa", librosa), \
             patch("integrations.atom_voice_ai_service.os.unlink", side_effect=OSError("gone")):
            resp = await svc._detect_emotion(_request(vmod.VoiceTaskType.EMOTION_DETECTION), b"\x00" * 16)
        assert resp.success is True


class TestVoiceAuditActionNames:
    async def test_process_voice_request_audit_action(self):
        svc = _svc()
        svc._preprocess_audio = AsyncMock(return_value=b"x")
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(success=True))
        with patch("integrations.atom_voice_ai_service.log_integration_attempt") as attempt:
            await svc.process_voice_request(_request(vmod.VoiceTaskType.TRANSCRIPTION))
        assert attempt.call_args.args[1] == "process_voice_request"

    async def test_load_voice_models_audit_action(self):
        svc = _svc()
        with patch("integrations.atom_voice_ai_service.log_integration_attempt") as attempt:
            await svc._load_voice_models()
        assert attempt.call_args.args[1] == "_load_voice_models"

    async def test_close_audit_action(self):
        svc = _svc()
        with patch("integrations.atom_voice_ai_service.log_integration_attempt") as attempt:
            await svc.close()
        assert attempt.call_args.args[1] == "close"


class TestVoiceNoStrELeaks:
    async def test_process_voice_request_generic_error(self):
        svc = _svc()
        svc._preprocess_audio = AsyncMock(side_effect=RuntimeError("secret-internal-detail"))
        resp = await svc.process_voice_request(_request(vmod.VoiceTaskType.TRANSCRIPTION))
        assert resp.success is False
        assert "secret-internal-detail" not in resp.metadata.get("error", "")

    async def test_transcribe_audio_generic_error(self):
        svc = _svc()
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("secret-internal-detail")
        svc.whisper_model = model
        resp = await svc._transcribe_audio(_request(vmod.VoiceTaskType.TRANSCRIPTION), b"x")
        assert resp.success is False
        assert "secret-internal-detail" not in resp.metadata.get("error", "")

    async def test_perform_security_check_generic_error(self):
        svc = _svc()

        class Boom:
            def __bool__(self):
                raise RuntimeError("secret-internal-detail")

        svc.enterprise_security = Boom()
        check = await svc._perform_security_check(_request(vmod.VoiceTaskType.TRANSCRIPTION))
        assert check["passed"] is False
        assert "secret-internal-detail" not in check.get("reason", "")


class TestVoiceModuleReload:
    def test_reload_with_stubbed_services(self):
        sys_mods = importlib.import_module("sys")
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
            "atom_discord_integration": ["atom_discord_integration"],
            "atom_enterprise_security_service": ["atom_enterprise_security_service", "ComplianceStandard", "SecurityLevel"],
            "atom_google_chat_integration": ["atom_google_chat_integration"],
            "atom_slack_integration": ["atom_slack_integration"],
            "atom_teams_integration": ["atom_teams_integration"],
            "atom_telegram_integration": ["atom_telegram_integration"],
            "atom_whatsapp_integration": ["atom_whatsapp_integration"],
            "atom_workflow_automation_service": ["atom_workflow_automation_service", "AutomationPriority", "AutomationStatus"],
            "atom_zoom_integration": ["atom_zoom_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        try:
            with patch.dict(sys_mods.modules, stubs):
                importlib.reload(vmod)
                assert vmod.atom_voice_ai_service.enterprise_security is not None
        finally:
            importlib.reload(vmod)
