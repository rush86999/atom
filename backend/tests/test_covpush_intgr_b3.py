"""Coverage push (>=95%) for integrations wave B - batch 3.

voice/video/zoom/chat_interface/slack_workflow_engine/discord/google_chat/
pdf_ocr/pdf_memory. All external I/O mocked.
"""
import asyncio
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _voice_request(task_type, **kw):
    from integrations.atom_voice_ai_service import (
        VoiceFormat, VoiceLanguage, VoiceModelType, VoiceRequest, VoiceTaskType,
    )
    return VoiceRequest(
        request_id="r1", task_type=task_type, model_type=VoiceModelType.WHISPER,
        language=VoiceLanguage.ENGLISH, audio_path=None, audio_data=b"\x00\x01",
        format=VoiceFormat.WAV, sample_rate=16000, duration=1.0, platform="test",
        user_id="u1", metadata=kw.pop("metadata", {}),
        **kw,
    )


# ============================================================================
# atom_voice_ai_service
# ============================================================================


class TestVoiceAIService:
    def _svc(self, **kw):
        from integrations.atom_voice_ai_service import AtomVoiceAIService
        cfg = {"enable_enterprise_features": True, "security_level": "standard"}
        cfg.update(kw)
        return AtomVoiceAIService(config=cfg)

    async def test_initialize_and_status(self):
        svc = self._svc()
        with patch.object(svc, "_load_voice_models", AsyncMock()), \
             patch.object(svc, "_initialize_command_patterns", AsyncMock()), \
             patch.object(svc, "_setup_language_models", AsyncMock()), \
             patch.object(svc, "_setup_enterprise_features", AsyncMock()), \
             patch.object(svc, "_setup_security_and_compliance", AsyncMock()), \
             patch.object(svc, "_load_voice_profiles", AsyncMock()):
            assert await svc.initialize() is True
            assert svc.is_initialized
        status = await svc.get_service_status()
        assert status["service"] == "voice_ai"
        assert status["status"] == "active"
        svc2 = self._svc()
        with patch.object(svc2, "_load_voice_models", AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc2.initialize() is False

    async def test_transcribe_audio(self):
        svc = self._svc()
        model = MagicMock()
        model.transcribe.return_value = {"text": "hello world", "avg_logprob": -0.5, "segments": [{"s": 1}]}
        svc.whisper_model = model
        resp = await svc._transcribe_audio(_voice_request(svc.__class__.__module__ and __import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION), b"\x00" * 10)
        assert resp.success is True
        assert resp.text == "hello world"
        model.transcribe.side_effect = RuntimeError("x")
        resp = await svc._transcribe_audio(_voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION), b"\x00")
        assert resp.success is False
        assert resp.metadata["error"]

    async def test_translate_speech(self):
        from integrations.atom_voice_ai_service import VoiceTaskType
        svc = self._svc()
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(
            success=True, text="hello", confidence=0.9, language=MagicMock()))
        tr = MagicMock()
        tr.return_value = MagicMock(return_value=[{"translation_text": "hola"}])
        with patch("integrations.atom_voice_ai_service.pipeline", tr):
            svc.translation_model = MagicMock()
            resp = await svc._translate_speech(_voice_request(VoiceTaskType.TRANSLATION, metadata={"target_language": "es"}), b"x")
        assert resp.success is True
        assert resp.translation["translated_text"] == "hola"
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(success=False))
        resp = await svc._translate_speech(_voice_request(VoiceTaskType.TRANSLATION), b"x")
        assert resp.success is False
        svc._transcribe_audio = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._translate_speech(_voice_request(VoiceTaskType.TRANSLATION), b"x")
        assert resp.success is False

    async def test_recognize_command(self):
        from integrations.atom_voice_ai_service import VoiceTaskType
        svc = self._svc()
        await svc._initialize_command_patterns()
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(
            success=True, text="please start meeting now", confidence=0.9))
        resp = await svc._recognize_command(_voice_request(VoiceTaskType.COMMAND_RECOGNITION), b"x")
        assert resp.success is True
        assert resp.metadata["matched_command"]["type"] == "start_meeting"
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(
            success=True, text="no command here", confidence=0.5))
        resp = await svc._recognize_command(_voice_request(VoiceTaskType.COMMAND_RECOGNITION), b"x")
        assert resp.success is False
        svc._transcribe_audio = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._recognize_command(_voice_request(VoiceTaskType.COMMAND_RECOGNITION), b"x")
        assert resp.success is False

    async def test_sentiment_analysis(self):
        from integrations.atom_voice_ai_service import VoiceTaskType
        svc = self._svc()
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(
            success=True, text="great", confidence=0.9))
        svc.sentiment_model = MagicMock(return_value=[{"label": "POSITIVE", "score": 0.9}])
        resp = await svc._analyze_sentiment(_voice_request(VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp.success is True
        assert resp.sentiment.value == "positive"
        svc.sentiment_model = MagicMock(return_value=[{"label": "NEGATIVE", "score": 0.9}])
        resp = await svc._analyze_sentiment(_voice_request(VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp.sentiment.value == "negative"
        svc.sentiment_model = MagicMock(return_value=[{"label": "MIXED", "score": 0.5}])
        resp = await svc._analyze_sentiment(_voice_request(VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp.sentiment.value == "neutral"
        svc._transcribe_audio = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._analyze_sentiment(_voice_request(VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp.success is False

    async def test_detect_emotion(self):
        from integrations.atom_voice_ai_service import VoiceTaskType
        svc = self._svc()
        import numpy as np
        librosa = MagicMock()
        librosa.load.return_value = (np.zeros(10), 16000)
        librosa.feature.mfcc.return_value = np.zeros((13, 10))
        librosa.feature.spectral_centroid.return_value = np.array([[3000.0]])
        librosa.feature.zero_crossing_rate.return_value = np.array([[0.5]])
        with patch("integrations.atom_voice_ai_service.librosa", librosa):
            resp = await svc._detect_emotion(_voice_request(VoiceTaskType.EMOTION_DETECTION), b"\x00" * 10)
        assert resp.success is True
        assert resp.emotion.value == "excited"
        librosa.feature.spectral_centroid.return_value = np.array([[500.0]])
        librosa.feature.zero_crossing_rate.return_value = np.array([[0.01]])
        with patch("integrations.atom_voice_ai_service.librosa", librosa):
            resp = await svc._detect_emotion(_voice_request(VoiceTaskType.EMOTION_DETECTION), b"\x00" * 10)
        assert resp.emotion.value == "calm"
        librosa.feature.spectral_centroid.return_value = np.array([[500.0]])
        librosa.feature.zero_crossing_rate.return_value = np.array([[0.3]])
        with patch("integrations.atom_voice_ai_service.librosa", librosa):
            resp = await svc._detect_emotion(_voice_request(VoiceTaskType.EMOTION_DETECTION), b"\x00" * 10)
        assert resp.emotion.value == "angry"
        librosa.feature.spectral_centroid.return_value = np.array([[1500.0]])
        librosa.feature.zero_crossing_rate.return_value = np.array([[0.08]])
        with patch("integrations.atom_voice_ai_service.librosa", librosa):
            resp = await svc._detect_emotion(_voice_request(VoiceTaskType.EMOTION_DETECTION), b"\x00" * 10)
        assert resp.emotion.value == "neutral"
        with patch("integrations.atom_voice_ai_service.librosa", librosa), \
             patch("integrations.atom_voice_ai_service.np", None):
            pass
        with patch("builtins.open", side_effect=RuntimeError("x")):
            pass
        with patch("integrations.atom_voice_ai_service.librosa", librosa):
            librosa.load.side_effect = RuntimeError("x")
            resp = await svc._detect_emotion(_voice_request(VoiceTaskType.EMOTION_DETECTION), b"\x00")
        assert resp.success is False
        librosa.load.side_effect = None

    async def test_preprocess_audio(self):
        svc = self._svc()
        req = _voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION)
        assert await svc._preprocess_audio(req) == b"\x00\x01"
        from integrations.atom_voice_ai_service import VoiceFormat, VoiceLanguage, VoiceModelType, VoiceRequest, VoiceTaskType
        req2 = VoiceRequest(request_id="r", task_type=VoiceTaskType.TRANSCRIPTION,
                            model_type=VoiceModelType.WHISPER, language=VoiceLanguage.ENGLISH,
                            audio_path=None, audio_data=b"\x00" * 10, format=VoiceFormat.MP3,
                            sample_rate=16000, duration=1.0, platform="t", user_id="u", metadata={})
        seg = MagicMock()
        seg.from_file.return_value = seg
        seg.set_frame_rate.return_value = seg
        seg.set_channels.return_value = seg
        seg.export.return_value.read.return_value = b"wav"
        with patch("integrations.atom_voice_ai_service.AudioSegment", seg):
            assert await svc._preprocess_audio(req2) == b"wav"
        with patch("integrations.atom_voice_ai_service.AudioSegment", seg), \
             patch.object(seg, "from_file", side_effect=RuntimeError("x")):
            assert await svc._preprocess_audio(req2) == b"\x00" * 10

    async def test_process_voice_request_all_tasks(self):
        from integrations.atom_voice_ai_service import VoiceTaskType
        svc = self._svc()
        svc._preprocess_audio = AsyncMock(return_value=b"x")
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        handlers = {
            VoiceTaskType.TRANSCRIPTION: "_transcribe_audio",
            VoiceTaskType.TRANSLATION: "_translate_speech",
            VoiceTaskType.COMMAND_RECOGNITION: "_recognize_command",
            VoiceTaskType.SENTIMENT_ANALYSIS: "_analyze_sentiment",
            VoiceTaskType.EMOTION_DETECTION: "_detect_emotion",
        }
        for task, handler in handlers.items():
            setattr(svc, handler, AsyncMock(return_value=MagicMock(success=True)))
            resp = await svc.process_voice_request(_voice_request(task))
            assert resp.success is True
        resp = await svc.process_voice_request(_voice_request(VoiceTaskType.VOICE_SYNTHESIS))
        assert resp.success is False
        assert "Unsupported" in resp.metadata["error"]
        # security failure path
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "denied"})
        resp = await svc.process_voice_request(_voice_request(VoiceTaskType.TRANSCRIPTION))
        assert resp.success is False
        assert resp.metadata["error"] == "denied"
        # exception path
        svc._preprocess_audio = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc.process_voice_request(_voice_request(VoiceTaskType.TRANSCRIPTION))
        assert resp.success is False

    async def test_security_logging(self):
        svc = self._svc()
        check = await svc._perform_security_check(_voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION))
        assert check["passed"] is True
        svc.enterprise_security = MagicMock()
        check = await svc._perform_security_check(_voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION))
        assert check["passed"] is True
        svc.enterprise_security.audit_event = AsyncMock()
        await svc._log_voice_request(_voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION), MagicMock(success=True, processing_time=1.0, confidence=0.5))
        svc.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError("x"))
        await svc._log_voice_request(_voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION), MagicMock(success=True))

    async def test_enterprise_setup_methods(self):
        svc = self._svc()
        await svc._setup_enterprise_features()
        assert svc.voice_data_retention["auto_delete"] is True
        await svc._setup_security_and_compliance()
        assert svc.voice_security_policies["data_encryption"]["enabled"] is True
        await svc._load_voice_profiles()
        await svc._setup_language_models()
        await svc._initialize_command_patterns()
        assert "start_meeting" in svc.command_patterns
        assert svc._extract_command_parameters("send to bob", "send")["target_language"] == "bob"
        assert svc._extract_command_parameters("plain", "zzz") == {}
        await svc._load_voice_models()

    async def test_close(self):
        svc = self._svc()
        await svc.close()
        assert svc.whisper_model is None
        with patch("integrations.atom_voice_ai_service.rate_limiter.is_rate_limited",
                   new=AsyncMock(return_value=(True, 0))):
            await svc.close()

    async def test_module_instance(self):
        from integrations.atom_voice_ai_service import atom_voice_ai_service
        assert atom_voice_ai_service is not None
        status = await atom_voice_ai_service.get_service_status()
        assert status["service"] == "voice_ai"


class TestVoiceAIGaps:
    def _svc(self):
        from integrations.atom_voice_ai_service import AtomVoiceAIService
        return AtomVoiceAIService(config={"enable_enterprise_features": True})

    async def test_platform_integrations_from_globals(self):
        import integrations.atom_voice_ai_service as mod
        names = ["atom_slack_integration", "atom_teams_integration",
                 "atom_google_chat_integration", "atom_discord_integration",
                 "atom_telegram_integration", "atom_whatsapp_integration",
                 "atom_zoom_integration"]
        saved = {n: getattr(mod, n, None) for n in names}
        for n in names:
            setattr(mod, n, MagicMock())
        try:
            svc = mod.AtomVoiceAIService(config={})
            assert len(svc.platform_integrations) == 7
        finally:
            for n in names:
                if saved[n] is None:
                    delattr(mod, n)
                else:
                    setattr(mod, n, saved[n])

    async def test_circuit_breaker_paths(self):
        import integrations.atom_voice_ai_service as mod
        svc = self._svc()
        with patch.object(mod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            resp = await svc.process_voice_request(_voice_request(mod.VoiceTaskType.TRANSCRIPTION))
            assert resp.success is False
            await svc._load_voice_models()
            await svc.close()

    async def test_rate_limited_paths(self):
        import integrations.atom_voice_ai_service as mod
        svc = self._svc()
        with patch.object(mod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            resp = await svc.process_voice_request(_voice_request(mod.VoiceTaskType.TRANSCRIPTION))
            assert resp.success is False
            await svc._load_voice_models()
            await svc.close()

    async def test_extract_command_parameters_error(self):
        from integrations.atom_voice_ai_service import AtomVoiceAIService
        svc = AtomVoiceAIService(config={})
        assert svc._extract_command_parameters(12345, "x") == {}

    async def test_setup_method_error_branches(self):
        from integrations.atom_voice_ai_service import AtomVoiceAIService
        svc = AtomVoiceAIService(config={})
        orig = dict(svc.command_patterns)
        svc.command_patterns = None
        await svc._initialize_command_patterns()
        assert "start_meeting" in svc.command_patterns
        svc.command_patterns = orig
        # security check error
        class BoomBool:
            def __bool__(self):
                raise RuntimeError("x")
        svc.enterprise_security = BoomBool()
        check = await svc._perform_security_check(_voice_request(__import__("integrations.atom_voice_ai_service", fromlist=["VoiceTaskType"]).VoiceTaskType.TRANSCRIPTION))
        assert check["passed"] is False

    async def test_status_error_branch(self):
        from integrations.atom_voice_ai_service import AtomVoiceAIService
        svc = AtomVoiceAIService(config={})

        class Boom:
            def __getitem__(self, k):
                raise RuntimeError("boom")
        with patch.object(svc, "voice_config", Boom()):
            status = await svc.get_service_status()
            assert "error" in status

    async def test_close_error_branch(self):
        import integrations.atom_voice_ai_service as mod
        svc = self._svc()
        with patch.object(mod.rate_limiter, "is_rate_limited", side_effect=RuntimeError("x")):
            await svc.close()

    async def test_translation_response_branch(self):
        import integrations.atom_voice_ai_service as mod
        svc = self._svc()
        svc._transcribe_audio = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._translate_speech(_voice_request(mod.VoiceTaskType.TRANSLATION), b"x")
        assert resp.success is False

    async def test_recognize_command_metrics_branch(self):
        import integrations.atom_voice_ai_service as mod
        svc = self._svc()
        await svc._initialize_command_patterns()
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(success=True, text="start meeting", confidence=0.9))
        resp = await svc._recognize_command(_voice_request(mod.VoiceTaskType.COMMAND_RECOGNITION), b"x")
        assert resp.success is True
        assert svc.analytics_metrics["successful_commands"] == 1

    async def test_sentiment_label_variants(self):
        import integrations.atom_voice_ai_service as mod
        svc = self._svc()
        svc._transcribe_audio = AsyncMock(return_value=MagicMock(success=True, text="ok", confidence=0.5))
        svc.sentiment_model = MagicMock(return_value=[{"label": "BIG_POSITIVE_X", "score": 0.9}])
        resp = await svc._analyze_sentiment(_voice_request(mod.VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp.sentiment.value == "positive"
        svc.sentiment_model = MagicMock(return_value=[{"label": "VERY_NEGATIVE", "score": 0.9}])
        resp = await svc._analyze_sentiment(_voice_request(mod.VoiceTaskType.SENTIMENT_ANALYSIS), b"x")
        assert resp.sentiment.value == "negative"


class TestVoiceAIReload:
    def test_reload_with_services(self):
        """Reload with stub top-level modules to cover the import try-block."""
        import importlib
        import sys
        from unittest.mock import MagicMock
        mod = importlib.import_module("integrations.atom_voice_ai_service")
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
            with patch.dict(sys.modules, stubs):
                importlib.reload(mod)
                assert mod.atom_voice_ai_service.enterprise_security is not None
        finally:
            importlib.reload(mod)

    async def test_load_voice_models_with_stubbed_deps(self):
        import sys
        from unittest.mock import MagicMock
        import integrations.atom_voice_ai_service as mod
        whisper = MagicMock()
        whisper.load_model.return_value = MagicMock()
        fake_tokenizer = MagicMock()
        fake_tokenizer.from_pretrained.return_value = MagicMock()
        fake_model = MagicMock()
        fake_model.from_pretrained.return_value = MagicMock()
        fake_pipeline = MagicMock(return_value=MagicMock())
        svc = mod.AtomVoiceAIService(config={})
        transformers_mod = MagicMock()
        transformers_mod.pipeline.return_value = MagicMock()
        with patch.dict(sys.modules, {"whisper": whisper, "transformers": transformers_mod}), \
             patch.object(mod, "AutoTokenizer", fake_tokenizer), \
             patch.object(mod, "AutoModelForSeq2SeqLM", fake_model), \
             patch.object(mod, "pipeline", fake_pipeline):
            await svc._load_voice_models()
        assert svc.whisper_model is not None
        assert svc.sentiment_model is not None
        fake_pipeline.side_effect = RuntimeError("x")
        svc2 = mod.AtomVoiceAIService(config={})
        with patch.dict(sys.modules, {"whisper": whisper, "transformers": transformers_mod}), \
             patch.object(mod, "AutoTokenizer", fake_tokenizer), \
             patch.object(mod, "AutoModelForSeq2SeqLM", fake_model), \
             patch.object(mod, "pipeline", fake_pipeline):
            await svc2._load_voice_models()
