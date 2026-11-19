"""Focused regression tests for the signed-in local transcription route.

The route must only dispatch audio through the existing LLMService scoped
audio path, never through a raw URL/client, and only for the caller's exact
(workspace, tenant) provider + per-model transcription declaration. These
tests use an in-memory SQLite database, a fake LLMService, and synthetic WAV
bytes — no network, provider, download, or install is touched.
"""

from __future__ import annotations

import io
import uuid
import wave
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Iterator, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import local_model_routes
from core.database import get_db
from core.models import LocalModelCapabilities, LocalModelProvider
from core.security_dependencies import get_current_user


MODEL_ID = "whisper-local:small"
WORKSPACE_ID = "ws-transcription"
TENANT_ID = "tenant-transcription"


def _wav_bytes(seconds: float = 0.25, framerate: int = 8000) -> bytes:
    """Synthetic mono PCM WAV with a measurable, non-zero duration."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(framerate)
        writer.writeframes(b"\x00\x00" * int(framerate * seconds))
    return buffer.getvalue()


class FakeLLMService:
    """Records the exact dispatch contract without contacting anything."""

    calls: list[dict[str, Any]] = []
    init_kwargs: Optional[dict[str, Any]] = None
    result: Any = {"text": "hello from the local model"}
    error: Optional[BaseException] = None

    def __init__(self, **kwargs: Any) -> None:
        type(self).init_kwargs = kwargs

    async def transcribe_audio(self, **kwargs: Any) -> Any:
        type(self).calls.append(kwargs)
        if type(self).error is not None:
            raise type(self).error
        return type(self).result

    @classmethod
    def reset(cls) -> None:
        cls.calls = []
        cls.init_kwargs = None
        cls.result = {"text": "hello from the local model"}
        cls.error = None


@dataclass
class TranscriptionHarness:
    client: TestClient
    app: FastAPI
    provider_id: str
    session_factory: Callable[[], Any]


@pytest.fixture()
def transcription_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[TranscriptionHarness]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LocalModelProvider.__table__.create(engine)
    LocalModelCapabilities.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    provider_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            LocalModelProvider(
                id=provider_id,
                workspace_id=WORKSPACE_ID,
                tenant_id=TENANT_ID,
                name="Synthetic local Whisper",
                provider_type="custom",
                base_url="http://127.0.0.1:9/v1",
                is_active=True,
            )
        )
        db.add(
            LocalModelCapabilities(
                id=str(uuid.uuid4()),
                provider_id=provider_id,
                workspace_id=WORKSPACE_ID,
                model_id=MODEL_ID,
                supports_tools=False,
                supports_vision=False,
                supports_reasoning=False,
                supports_transcription=True,
                audio_input_cost_per_second_usd=0.0,
                quality_score=0.5,
                speed_score=0.5,
                context_window=4096,
            )
        )
        db.commit()
    finally:
        db.close()

    app = FastAPI()
    app.include_router(local_model_routes.router)

    def override_db() -> Iterator[Any]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    actor = SimpleNamespace(
        id="user-transcription",
        workspace_id=WORKSPACE_ID,
        tenant_id=TENANT_ID,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor

    FakeLLMService.reset()
    monkeypatch.setattr(local_model_routes, "LLMService", FakeLLMService)

    with TestClient(app) as client:
        yield TranscriptionHarness(
            client=client,
            app=app,
            provider_id=provider_id,
            session_factory=SessionLocal,
        )

    engine.dispose()


def _post(
    harness: TranscriptionHarness,
    *,
    model: str = MODEL_ID,
    data: Optional[bytes] = None,
    filename: str = "note.wav",
    content_type: str = "audio/wav",
):
    return harness.client.post(
        f"/api/local-models/{harness.provider_id}/transcriptions",
        data={"model": model},
        files={"file": (filename, _wav_bytes() if data is None else data, content_type)},
    )


class TestTranscriptionRouteRegistration:
    def test_transcriptions_path_is_registered(self):
        paths = {route.path for route in local_model_routes.router.routes}
        assert "/api/local-models/{provider_id}/transcriptions" in paths


class TestTranscriptionScopeAndDeclaration:
    def test_missing_workspace_or_tenant_scope_is_refused(self, transcription_harness):
        harness = transcription_harness
        harness.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            workspace_id=None,
            tenant_id=TENANT_ID,
        )

        response = _post(harness)

        assert response.status_code == 403
        assert "workspace" in response.json()["detail"].lower()
        assert FakeLLMService.calls == []

    def test_foreign_provider_scope_is_not_found(self, transcription_harness):
        harness = transcription_harness
        harness.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            workspace_id="another-workspace",
            tenant_id=TENANT_ID,
        )

        response = _post(harness)

        assert response.status_code == 404
        assert response.json()["detail"] == "Provider not found or inactive."
        assert FakeLLMService.calls == []

    def test_inactive_provider_is_refused(self, transcription_harness):
        harness = transcription_harness
        with harness.session_factory() as db:
            provider = db.query(LocalModelProvider).filter_by(
                id=harness.provider_id
            ).one()
            provider.is_active = False
            db.commit()

        response = _post(harness)

        assert response.status_code == 404
        assert FakeLLMService.calls == []

    def test_undeclared_model_is_refused(self, transcription_harness):
        response = _post(transcription_harness, model="undeclared-model")

        assert response.status_code == 400
        assert "not enabled for transcription" in response.json()["detail"]
        assert FakeLLMService.calls == []

    def test_disabled_transcription_declaration_is_refused(
        self, transcription_harness
    ):
        harness = transcription_harness
        with harness.session_factory() as db:
            capability = db.query(LocalModelCapabilities).one()
            capability.supports_transcription = False
            db.commit()

        response = _post(harness)

        assert response.status_code == 400
        assert FakeLLMService.calls == []

    def test_unset_audio_rate_is_refused(self, transcription_harness):
        harness = transcription_harness
        with harness.session_factory() as db:
            capability = db.query(LocalModelCapabilities).one()
            capability.audio_input_cost_per_second_usd = None
            db.commit()

        response = _post(harness)

        assert response.status_code == 400
        assert FakeLLMService.calls == []


class TestTranscriptionMediaValidation:
    def test_empty_upload_is_refused(self, transcription_harness):
        response = _post(transcription_harness, data=b"")

        assert response.status_code == 400
        assert "Record or choose an audio file" in response.json()["detail"]
        assert FakeLLMService.calls == []

    def test_excessive_upload_is_refused(
        self, transcription_harness, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            local_model_routes, "MAX_TRANSCRIPTION_UPLOAD_BYTES", 64
        )

        response = _post(transcription_harness, data=_wav_bytes())

        assert response.status_code == 413
        assert "too large" in response.json()["detail"]
        assert FakeLLMService.calls == []

    def test_unmeasurable_media_is_refused(
        self, transcription_harness, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            local_model_routes,
            "media_duration_seconds",
            lambda *args, **kwargs: None,
        )

        response = _post(
            transcription_harness,
            data=b"definitely-not-audio" * 32,
            content_type="audio/wav",
        )

        assert response.status_code == 400
        assert "could not be read" in response.json()["detail"]
        assert FakeLLMService.calls == []

    def test_zero_duration_media_is_refused(
        self, transcription_harness, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            local_model_routes,
            "media_duration_seconds",
            lambda *args, **kwargs: 0.0,
        )

        response = _post(transcription_harness)

        assert response.status_code == 400
        assert FakeLLMService.calls == []


class TestTranscriptionDispatch:
    def test_success_uses_exact_scoped_llm_service_kwargs(self, transcription_harness):
        harness = transcription_harness
        wav = _wav_bytes()

        response = _post(harness, data=wav)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["transcript"] == "hello from the local model"
        assert body["text"] == "hello from the local model"
        assert body["model"] == MODEL_ID
        assert body["provider_id"] == harness.provider_id
        assert body["duration_seconds"] == pytest.approx(0.25, abs=0.02)

        assert FakeLLMService.init_kwargs is not None
        assert set(FakeLLMService.init_kwargs) == {
            "db",
            "workspace_id",
            "tenant_id",
        }
        assert FakeLLMService.init_kwargs["workspace_id"] == WORKSPACE_ID
        assert FakeLLMService.init_kwargs["tenant_id"] == TENANT_ID
        assert len(FakeLLMService.calls) == 1
        call = FakeLLMService.calls[0]
        assert call["model"] == MODEL_ID
        assert call["workspace_id"] == WORKSPACE_ID
        assert call["tenant_id"] == TENANT_ID
        assert call["local_provider_id"] == harness.provider_id
        assert set(call) == {
            "file",
            "model",
            "workspace_id",
            "tenant_id",
            "local_provider_id",
        }
        filename, payload, content_type = call["file"]
        assert filename == "note.wav"
        assert payload == wav
        assert content_type == "audio/wav"

    def test_service_failure_does_not_leak_internal_detail(self, transcription_harness):
        FakeLLMService.error = RuntimeError("provider secret sk-live-123")

        response = _post(transcription_harness)

        assert response.status_code == 502
        assert response.json()["detail"] == "Transcription failed. Please try again."
        assert "secret" not in response.text
        assert "sk-live" not in response.text

    def test_service_missing_text_is_a_generic_failure(self, transcription_harness):
        FakeLLMService.result = {"provider": "local"}

        response = _post(transcription_harness)

        assert response.status_code == 502
        assert response.json()["detail"] == "Transcription failed. Please try again."

    def test_transcript_is_returned_but_not_persisted(self, transcription_harness):
        """The route returns text only; no row is created or updated."""
        harness = transcription_harness
        with harness.session_factory() as db:
            before = db.query(LocalModelCapabilities).count()

        response = _post(harness)

        assert response.status_code == 200
        with harness.session_factory() as db:
            assert db.query(LocalModelCapabilities).count() == before
