"""Goal 9 admission/settlement for TIME-billed Whisper transcription.

Failure-first: ``BYOKHandler.generate_transcription`` checked provider policy
but dispatched the paid OpenAI audio call with no durable reservation and no
settlement. Audio is billed by media duration (Whisper: USD 0.006/minute), so
a token estimate or a byte-length guess is the wrong quantity.

These controls double the audio transport and use the real scratch SQLite
ledger/policy. No provider, model, network or live DB is used.
"""
from __future__ import annotations

import asyncio
import io
import shutil
import subprocess
import wave
from types import SimpleNamespace

import pytest

from tests.test_goal9_physical_attempts import (
    _attempt_rows,
    _make_handler,
    _pricing,
    _seed,
    host,
)

pytest_plugins = ("tests.test_goal9_physical_attempts",)

WHISPER_PER_SECOND = 0.006 / 60.0
CLIP_SECONDS = 3.25
SUPPORTED_AUDIO_FORMATS = ("wav", "flac", "mp3", "m4a", "ogg", "webm")


class _AudioClient:
    """Doubled OpenAI audio transport; records each physical call."""

    def __init__(self, script, calls):
        self._script = list(script)
        self._calls = calls
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self._calls.append(kwargs)
        action = self._script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


def _wav_bytes(seconds: float, framerate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(framerate)
        writer.writeframes(b"\x00\x00" * int(seconds * framerate))
    return buffer.getvalue()


def _mp3_bytes(frames: int = 100, bitrate_kbps: int = 128) -> bytes:
    """A valid CBR MPEG-1 Layer III header sequence (no audio payload)."""
    header = bytes((0xFF, 0xFB, 0x90, 0x00))  # MPEG1 L3, 128k, 44.1kHz
    frame_length = 144 * bitrate_kbps * 1000 // 44100
    frame = header + b"\x00" * (frame_length - len(header))
    return frame * frames


def _handler(monkeypatch, tmp_path, script, calls):
    return _make_handler(
        monkeypatch, tmp_path, {"openai": ["whisper-1"]},
        async_={"openai": _AudioClient(script, calls)})


def _audio_pricing(monkeypatch, per_second=WHISPER_PER_SECOND):
    """Configure TIME pricing on the audio-aware path only.

    The fetcher deliberately exposes ``estimate_audio_cost`` (and no token
    ``estimate_cost``): audio quantity must come from seconds, never a token
    count.
    """
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(
            estimate_audio_cost=lambda model, seconds: (
                float(seconds) * per_second
                if model == "whisper-1" else None)))


@pytest.fixture(scope="module")
def encoded_clip(tmp_path_factory):
    """A realistic encoded clip in every supported container.

    Header-only hand-built blobs cannot catch container-offset regressions:
    the reported failure measured 0.424s (M4A), 0.157s (Ogg) and 0.026s
    (WebM) for a real 3.25s clip. Generate real encoder output with the
    locally installed ffmpeg (never a network fetch); skip where ffmpeg is
    genuinely unavailable.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not installed; realistic fixtures unavailable")
    output = tmp_path_factory.mktemp("whisper-encoded-clips")
    source = output / "source.wav"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i",
         f"sine=frequency=440:duration={CLIP_SECONDS}",
         "-ar", "8000", "-ac", "1", str(source)],
        check=True, capture_output=True)
    recipes = {
        "wav": ["-c:a", "pcm_s16le", "-f", "wav"],
        "flac": ["-c:a", "flac", "-f", "flac"],
        "mp3": ["-c:a", "libmp3lame", "-b:a", "32k", "-f", "mp3"],
        "m4a": ["-c:a", "aac", "-b:a", "32k", "-f", "ipod"],
        "ogg": ["-c:a", "libopus", "-b:a", "24k", "-f", "ogg"],
        "webm": ["-c:a", "libopus", "-b:a", "24k", "-f", "webm"],
    }
    clips = {}
    for extension, arguments in recipes.items():
        path = output / f"clip.{extension}"
        subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(source), *arguments, str(path)],
            check=True, capture_output=True)
        clips[extension] = path.read_bytes()
    return clips


def test_whisper_allowed_dispatch_admits_and_settles_duration(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _audio_pricing(monkeypatch)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="hello world")], calls)

    result = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(2.0)), model="whisper-1"))

    # Response contract is unchanged: exactly these three keys.
    assert result == {
        "text": "hello world",
        "model": "whisper-1",
        "provider": "openai",
    }
    assert len(calls) == 1
    assert calls[0]["model"] == "whisper-1"
    # Probing must not consume the request body: the one physical dispatch
    # still receives the full audio stream.
    transport = calls[0]["file"]
    transport.seek(0)
    assert transport.read() == _wav_bytes(2.0)
    rows = _attempt_rows(host)
    assert len(rows) == 1
    row = rows[0]
    assert row.attempt_id and row.request_id
    assert row.provider_id == "openai"
    assert row.model_name == "whisper-1"
    assert row.workspace_id == "ws-goal9-physical"
    assert row.tenant_id == "tenant-goal9-physical"
    assert row.billed is True
    assert row.cost_usd == pytest.approx(2.0 * WHISPER_PER_SECOND)
    assert row.pricing_status == "priced"
    assert row.reservation_status == "settled"
    # Audio quantity is TIME, not a fabricated token count.
    assert row.prompt_tokens == 0 and row.completion_tokens == 0


def test_whisper_denied_before_transport_at_hard_stop(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.9999, limit=1.0)
    _audio_pricing(monkeypatch)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="must not be sent")], calls)

    with pytest.raises(Exception):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(2.0)), model="whisper-1"))

    assert calls == []
    assert _attempt_rows(host) == []


def test_whisper_missing_billing_policy_refuses_before_transport(
        host, monkeypatch, tmp_path):
    """An unresolvable tenant scope is not a licence to dispatch unenforced.

    The draft used to fall back to ``enforce_budget=False`` whenever the
    handler's tenant row was absent, turning a misconfigured/missing policy
    into an unenforced paid call. Admission stays strict: zero provider calls.
    """
    _seed(host, spend=0.0)
    _audio_pricing(monkeypatch)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="must not be sent")], calls)
    handler.tenant_id = "tenant-with-no-billing-policy"

    with pytest.raises(Exception):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(2.0)), model="whisper-1"))

    assert calls == []
    assert _attempt_rows(host) == []


def test_whisper_unknown_price_refuses_before_transport(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda *args, **kwargs: None)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="must not be sent")], calls)

    with pytest.raises(Exception):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)),
            model="controlled-unpriced-whisper"))

    assert calls == []
    assert _attempt_rows(host) == []


def test_whisper_present_but_unusable_price_is_not_masked_by_static(
        host, monkeypatch, tmp_path):
    """A present audio row without a time rate is unknown, not whisper-1."""
    _seed(host, spend=0.0)
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(
            get_model_price=lambda model: {
                "input_cost_per_token": 0.000001,
                "mode": "audio_transcription",
            }))
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="must not be sent")], calls)

    with pytest.raises(Exception):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model="whisper-1"))

    assert calls == []
    assert _attempt_rows(host) == []


def test_whisper_unknown_duration_refuses_under_hard_stop(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _audio_pricing(monkeypatch)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="must not be sent")], calls)

    with pytest.raises(Exception):
        asyncio.run(handler.generate_transcription(
            file=object(), model="whisper-1"))

    assert calls == []
    assert _attempt_rows(host) == []


def test_whisper_compressed_mp3_uses_media_duration(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _audio_pricing(monkeypatch)
    calls = []
    audio = _mp3_bytes(frames=100, bitrate_kbps=128)
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="compressed")], calls)

    asyncio.run(handler.generate_transcription(
        file=io.BytesIO(audio), model="whisper-1"))

    expected_seconds = 100 * 1152 / 44100
    row = _attempt_rows(host)[0]
    assert len(calls) == 1
    assert row.cost_usd == pytest.approx(
        expected_seconds * WHISPER_PER_SECOND)
    assert row.reservation_status == "settled"


def test_whisper_provider_duration_wins_for_settlement(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _audio_pricing(monkeypatch)
    handler = _handler(
        monkeypatch, tmp_path,
        [SimpleNamespace(text="verbose", duration=3.0)], [])

    asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(1.0)), model="whisper-1",
        response_format="verbose_json"))

    row = _attempt_rows(host)[0]
    assert row.cost_usd == pytest.approx(3.0 * WHISPER_PER_SECOND)
    assert row.reservation_status == "settled"


def test_whisper_metadata_and_hint_cannot_shrink_billed_duration(
        host, monkeypatch, tmp_path):
    """Upload metadata / a caller hint must never under-reserve the attempt.

    The bytes are evidence; a ``duration_seconds`` attribute on the upload
    object (or a stale caller hint) claiming 1ms cannot turn a 2s clip into a
    near-free call.
    """
    _seed(host, spend=0.0)
    _audio_pricing(monkeypatch)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, [SimpleNamespace(text="measured")], calls)

    upload = io.BytesIO(_wav_bytes(2.0))
    upload.name = "note.wav"
    upload.duration_seconds = 0.001
    upload.duration = 0.001
    asyncio.run(handler.generate_transcription(
        file=upload, model="whisper-1", duration_seconds=0.001))

    assert len(calls) == 1
    row = _attempt_rows(host)[0]
    assert row.cost_usd == pytest.approx(2.0 * WHISPER_PER_SECOND)
    assert row.reservation_status == "settled"


def test_whisper_never_prices_audio_through_token_estimator(
        host, monkeypatch, tmp_path):
    """Audio is billed per second; the per-token estimator is not a fallback."""
    _seed(host, spend=0.0)
    token_calls = []

    def _estimate_cost(model, input_tokens, output_tokens):
        token_calls.append((model, input_tokens, output_tokens))
        raise AssertionError("token estimator used for audio")

    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=_estimate_cost))
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, [SimpleNamespace(text="ok")], calls)

    asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(2.0)), model="whisper-1"))

    assert token_calls == []
    assert len(calls) == 1
    # Falls back to the documented static rate for the exact model identity.
    assert _attempt_rows(host)[0].cost_usd == pytest.approx(
        2.0 * WHISPER_PER_SECOND)


def test_whisper_media_duration_reads_headers_not_byte_length():
    from core.media_duration import media_duration_seconds

    assert media_duration_seconds(_wav_bytes(2.5)) == pytest.approx(2.5)
    assert media_duration_seconds(_mp3_bytes(frames=100)) == pytest.approx(
        100 * 1152 / 44100)
    # A compressed file with different bitrate must not reuse a byte-length
    # formula: 50 frames at half the bitrate is the same time, half the bytes.
    assert media_duration_seconds(_mp3_bytes(frames=50)) == pytest.approx(
        50 * 1152 / 44100)
    # A declared duration on an arbitrary object is metadata, not evidence.
    class _ClaimsShort:
        duration_seconds = 0.001
        duration = 0.001

    assert media_duration_seconds(b"not audio", file=_ClaimsShort()) is None


@pytest.mark.parametrize("container", SUPPORTED_AUDIO_FORMATS)
def test_whisper_realistic_encoded_fixture_duration(encoded_clip, container):
    """Real encoder output must report the billed time, never a fragment.

    Regression: a 3.25s clip measured 0.424s (M4A), 0.157s (Ogg) and 0.026s
    (WebM), which would under-reserve almost the whole call.
    """
    from core.media_duration import media_duration_seconds

    payload = encoded_clip[container]
    seconds = media_duration_seconds(payload, f"clip.{container}")
    assert seconds is not None
    # Frame granularity may round a hair up; it must never round down.
    assert seconds >= CLIP_SECONDS - 0.05, (container, seconds)
    assert seconds <= CLIP_SECONDS + 0.25, (container, seconds)


def test_whisper_pricing_catalog_preserves_audio_rate():
    from core.cost_config import get_llm_audio_cost
    from core.dynamic_pricing_fetcher import DynamicPricingFetcher

    fetcher = DynamicPricingFetcher.__new__(DynamicPricingFetcher)
    fetcher.pricing_cache = {
        "whisper-scratch": {
            "input_cost_per_second": 0.0001,
            "mode": "audio_transcription",
        }
    }
    assert fetcher.estimate_audio_cost("whisper-scratch", 60) == pytest.approx(
        0.006)
    # The repo's static fallback encodes the documented $0.006/minute.
    assert get_llm_audio_cost("whisper-1", 60) == pytest.approx(0.006)


def test_whisper_static_fallback_binds_exact_model_identity():
    from core.cost_config import get_llm_audio_cost

    assert get_llm_audio_cost("whisper-1", 60) == pytest.approx(0.006)
    assert get_llm_audio_cost("  WHISPER-1  ", 60) == pytest.approx(0.006)
    assert get_llm_audio_cost("openai/whisper-1", 60) == pytest.approx(0.006)
    # Substring matches are different model identities with no published
    # audio price: they must stay unknown, not inherit whisper-1's rate.
    for unrelated in (
            "whisper-1-preview", "not-whisper-1", "whisper-1-eu",
            "custom-whisper-1-clone", "", None):
        assert get_llm_audio_cost(unrelated, 60) is None


def test_whisper_local_probe_cannot_fetch_remote_resources(monkeypatch):
    """ffprobe is a LOCAL last resort; upload contents cannot steer it online."""
    import core.media_duration as media_duration

    captured = {}

    def _run(args, **kwargs):
        captured["args"] = list(args)
        return SimpleNamespace(returncode=0, stdout="1.5\n", stderr="")

    monkeypatch.setattr(
        media_duration.shutil, "which", lambda name: "/usr/local/bin/ffprobe")
    monkeypatch.setattr(media_duration.subprocess, "run", _run)

    # An unknown container in an .m3u8 upload: ffprobe may sniff a playlist,
    # so it must be limited to the local file protocol (no http/https/tcp).
    payload = b"\x00" * 4096
    assert media_duration.media_duration_seconds(
        payload, "upload.m3u8") == pytest.approx(1.5)
    args = captured["args"]
    assert "-protocol_whitelist" in args
    assert args[args.index("-protocol_whitelist") + 1] == "file"
    # The probe receives a local temp path, never the caller's (remote-ish)
    # name.
    assert args[-1] != "upload.m3u8"


def test_whisper_openai_clients_disable_sdk_retries():
    import inspect

    import core.llm.byok_handler as bh

    source = inspect.getsource(bh.BYOKHandler._initialize_clients)
    assert "max_retries=_SDK_MAX_RETRIES" in source
    assert bh._SDK_MAX_RETRIES == 0
