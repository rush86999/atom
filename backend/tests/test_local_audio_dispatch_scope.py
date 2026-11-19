"""Scoped dispatch controls for registered LOCAL audio routes.

The local-model settings half adds two persistable capability columns:
``supports_transcription`` (bool, default false) and
``audio_input_cost_per_second_usd`` (nullable finite nonnegative rate; an
explicit zero is valid). These controls register synthetic routes directly on
the handler (no DB, network or live provider) and pin the dispatch contract:

* local dispatch is reachable ONLY through the explicit durable
  ``local_provider_id`` supplied to the public transcription entry points;
* that route must match the exact model, durable provider id, nonempty
  workspace, registration-derived scoped provider key and audio declaration,
  and must have its scoped client before any audio leaves the process;
* routes are indexed by the full (durable provider id, exact model) pair, so
  two registrations serving the same model name stay independently selectable
  even when their truncated display client keys collide;
* missing/mismatched material fails closed with no cloud fallback, even when
  the shared pricing catalog is cold;
* the admitted bound and settlement use the route's exact declared per-second
  rate — never global pricing data;
* omitting ``local_provider_id`` keeps the historical OpenAI behavior.
"""
from __future__ import annotations

import asyncio
import inspect
import io
import wave
from types import SimpleNamespace

import pytest

import core.llm.byok_handler as bh

MODEL = "local-whisper"
PROVIDER_ID = "provider-row-id"
PROVIDER_KEY = f"local_{PROVIDER_ID[:8]}"
RATE = 0.125


class _AudioClient:
    """Doubled audio transport; records every physical call."""

    def __init__(self, response, calls):
        self._response = response
        self._calls = calls
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self._calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _ExplodingCloudClient:
    """An available OpenAI client that must never be dialled by local scope."""

    def __init__(self):
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):  # pragma: no cover - assertion path
        raise AssertionError("cloud transcription request was dispatched")


def _wav_bytes(seconds: float, framerate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(framerate)
        writer.writeframes(b"\x00\x00" * int(seconds * framerate))
    return buffer.getvalue()


def _handler(*, routes=None, clients=None, async_clients=None,
             workspace_id="ws-a", policy=None):
    """A minimal real BYOKHandler without DB/credential initialization."""
    handler = object.__new__(bh.BYOKHandler)
    handler.workspace_id = workspace_id
    handler.tenant_id = "tenant-a"
    handler._local_routes = dict(routes or {})
    handler.clients = dict(clients or {})
    handler.async_clients = dict(async_clients or {})
    handler.provider_policy = policy
    return handler


def _route(*, workspace_id="ws-a", supports_transcription=True,
           rate=RATE, provider_id=PROVIDER_ID, provider_key=None,
           supports_chat=True):
    return {
        "provider_key": (provider_key
                         if provider_key is not None
                         else f"local_{provider_id[:8]}"),
        "workspace_id": workspace_id,
        "provider_id": provider_id,
        "provider_type": "openai-compatible",
        "supports_tools": True,
        "supports_vision": False,
        "supports_reasoning": False,
        "supports_chat": supports_chat,
        "supports_transcription": supports_transcription,
        "audio_input_cost_per_second_usd": rate,
        "quality_score": 0.8,
        "context_window": 8192,
    }


def _without(route, key):
    """A route record missing one declaration key (not merely invalid)."""
    copy = dict(route)
    copy.pop(key)
    return copy


@pytest.fixture(autouse=True)
def _dispatch_defaults(monkeypatch):
    # Routing reads the documented local-only guard; dispatch controls here
    # are about provider/route selection, so pin the guard off by default.
    monkeypatch.setattr(
        bh, "_local_only_blocks_provider", lambda *a, **k: False)
    monkeypatch.delenv("ATOM_LLM_RESERVATION_MARGIN", raising=False)


@pytest.fixture()
def ledger(monkeypatch):
    """Capture the real admission/settlement calls without a database."""
    spend = pytest.importorskip("core.spend_aggregation_service")
    attempts = []
    settlements = []
    monkeypatch.setattr(
        spend, "begin_llm_usage",
        lambda **kwargs: attempts.append(kwargs), raising=False)
    monkeypatch.setattr(
        spend, "record_llm_usage",
        lambda **kwargs: settlements.append(kwargs), raising=False)
    return attempts, settlements


def _forbid_global_pricing(monkeypatch):
    """A registered local route's rate must never consult global pricing."""
    def _fail():
        raise AssertionError("global pricing consulted for a local route")

    monkeypatch.setattr(bh, "get_pricing_fetcher", _fail)


def test_zero_local_rate_pins_zero_bound_and_settles_zero(
        monkeypatch, ledger):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    local = _AudioClient(SimpleNamespace(text="local zero"), calls)
    handler = _handler(
        routes={MODEL: _route(rate=0.0)},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: local})

    result = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(2.0)), model=MODEL,
        local_provider_id=PROVIDER_ID))

    assert result == {
        "text": "local zero", "model": MODEL, "provider": PROVIDER_KEY}
    assert len(calls) == 1
    assert attempts[0]["provider_id"] == PROVIDER_KEY
    assert attempts[0]["workspace_id"] == "ws-a"
    # Explicit zero remains an authoritative free bound + settlement.
    assert attempts[0]["reserved_cost_usd"] == 0.0
    assert settlements[0]["provider_id"] == PROVIDER_KEY
    assert settlements[0]["cost_usd"] == 0.0


def test_priced_local_rate_pins_bound_and_settles_at_same_rate(
        monkeypatch, ledger):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    # The provider reports a longer billed duration than the upload: the
    # SAME declared rate prices both the admitted bound and settlement.
    local = _AudioClient(
        SimpleNamespace(text="local priced", duration=3.0), calls)
    handler = _handler(
        routes={MODEL: _route(rate=RATE)},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: local})

    asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(4.0)), model=MODEL,
        response_format="verbose_json", local_provider_id=PROVIDER_ID))

    assert len(calls) == 1
    assert calls[0]["model"] == MODEL
    # 4s upload -> 0.5 USD actual, reservations keep the documented 1.25x
    # margin; settlement uses the provider's 3s at the exact same rate.
    assert attempts[0]["reserved_cost_usd"] == pytest.approx(0.625)
    assert settlements[0]["cost_usd"] == pytest.approx(3.0 * RATE)


def test_priced_local_route_works_with_cold_shared_catalog(
        monkeypatch, ledger):
    """A cold/empty shared catalog is not authority to re-price or re-route."""
    attempts, settlements = ledger
    calls = []

    class _ColdFetcher:
        pricing_cache = {}

        @staticmethod
        def get_model_price(model):
            return None

    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: _ColdFetcher())
    local = _AudioClient(SimpleNamespace(text="local cold"), calls)
    handler = _handler(
        routes={MODEL: _route(rate=RATE)},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: local})

    result = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(2.0)), model=MODEL,
        local_provider_id=PROVIDER_ID))

    assert result == {
        "text": "local cold", "model": MODEL, "provider": PROVIDER_KEY}
    assert len(calls) == 1
    assert attempts[0]["provider_id"] == PROVIDER_KEY
    assert attempts[0]["reserved_cost_usd"] == pytest.approx(2.0 * RATE * 1.25)
    assert settlements[0]["cost_usd"] == pytest.approx(2.0 * RATE)


def test_cross_workspace_route_refuses_before_transport(monkeypatch, ledger):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    handler = _handler(
        routes={MODEL: _route(workspace_id="ws-b")},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: _AudioClient(
            SimpleNamespace(text="must not run"), calls)})

    with pytest.raises(ValueError, match="another workspace"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert calls == []
    assert attempts == [] and settlements == []


def test_missing_route_refuses_with_cold_catalog_without_cloud(
        monkeypatch, ledger):
    """Explicit local intent never degrades to a cloud upload.

    The shared catalog has no entry at all (a cold cache); that absence is not
    authority to re-route the audio. Zero cloud calls and zero ledger rows.
    """
    attempts, settlements = ledger
    calls = []
    cloud = _AudioClient(SimpleNamespace(text="must not run"), calls)

    class _ColdFetcher:
        pricing_cache = {}

        @staticmethod
        def get_model_price(model):
            return None

    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: _ColdFetcher())
    handler = _handler(
        clients={"openai": cloud}, async_clients={"openai": cloud})

    with pytest.raises(ValueError, match="No local model route"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert calls == []
    assert attempts == [] and settlements == []


@pytest.mark.parametrize(
    "handler_workspace, route, match",
    [
        (None, _route(workspace_id="ws-a"),
         "resolved nonempty workspace"),
        ("", _route(workspace_id="ws-a"),
         "resolved nonempty workspace"),
        ("ws-a", _route(workspace_id=None),
         "has no owning workspace"),
        ("ws-a", _route(workspace_id=""),
         "has no owning workspace"),
    ],
)
def test_missing_workspace_refuses_before_transport(
        monkeypatch, ledger, handler_workspace, route, match):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    handler = _handler(
        routes={MODEL: route}, workspace_id=handler_workspace,
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: _AudioClient(
            SimpleNamespace(text="must not run"), calls)})

    with pytest.raises(ValueError, match=match):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert calls == []
    assert attempts == [] and settlements == []


@pytest.mark.parametrize(
    "requested_id, route, match",
    [
        ("other-provider-id", _route(), "does not match the requested"),
        ("http://127.0.0.1:9/v1", _route(), "does not match the requested"),
        (PROVIDER_ID, _route(provider_key="local_wrong"),
         "invalid scoped provider key"),
        ("   ", _route(), "nonempty durable local_provider_id"),
    ],
)
def test_wrong_provider_identity_refuses_before_transport(
        monkeypatch, ledger, requested_id, route, match):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    handler = _handler(
        routes={MODEL: route},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: _AudioClient(
            SimpleNamespace(text="must not run"), calls)})

    with pytest.raises(ValueError, match=match):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=requested_id))

    assert calls == []
    assert attempts == [] and settlements == []


@pytest.mark.parametrize(
    "route, match",
    [
        (_route(supports_transcription=False),
         "does not declare transcription support"),
        (_without(_route(), "supports_transcription"),
         "does not declare transcription support"),
        (_route(rate=None), "no valid per-second audio rate"),
        (_without(_route(), "audio_input_cost_per_second_usd"),
         "no valid per-second audio rate"),
        (_route(rate=-0.01), "no valid per-second audio rate"),
        (_route(rate=float("nan")), "no valid per-second audio rate"),
        (_route(rate=float("inf")), "no valid per-second audio rate"),
        (_route(rate="not-a-rate"), "no valid per-second audio rate"),
    ],
)
def test_invalid_local_declaration_fails_closed(
        monkeypatch, ledger, route, match):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    handler = _handler(
        routes={MODEL: route},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: _AudioClient(
            SimpleNamespace(text="must not run"), calls)})

    with pytest.raises(ValueError, match=match):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert calls == []
    assert attempts == [] and settlements == []


def test_missing_local_client_fails_closed_without_cloud_fallback(
        monkeypatch, ledger):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    handler = _handler(
        routes={MODEL: _route()},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={})

    with pytest.raises(ValueError, match="client .* is not configured"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert attempts == [] and settlements == []


def test_local_route_provider_policy_denial_fails_closed(
        monkeypatch, ledger):
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    policy = SimpleNamespace(allows=lambda provider, model: False)
    handler = _handler(
        routes={MODEL: _route()},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={PROVIDER_KEY: _AudioClient(
            SimpleNamespace(text="must not run"), calls)},
        policy=policy)

    with pytest.raises(ValueError, match="Provider policy excludes"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert calls == []
    assert attempts == [] and settlements == []


def test_unregistered_model_keeps_openai_transcription_behavior(
        monkeypatch, ledger):
    attempts, settlements = ledger
    calls = []
    cloud = _AudioClient(SimpleNamespace(text="openai default"), calls)

    class _Fetcher:
        pricing_cache = {}

        @staticmethod
        def get_model_price(model):
            return None

        @staticmethod
        def estimate_audio_cost(model, seconds):
            return float(seconds) * 0.001 if model == "whisper-1" else None

    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: _Fetcher())
    handler = _handler(
        clients={"openai": cloud},
        async_clients={"openai": cloud},
        policy=SimpleNamespace(
            allows=lambda provider, model: provider == "openai"))

    result = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(2.0))))

    assert result == {
        "text": "openai default",
        "model": "whisper-1",
        "provider": "openai",
    }
    assert len(calls) == 1
    assert attempts[0]["provider_id"] == "openai"
    assert attempts[0]["reserved_cost_usd"] == pytest.approx(0.0025)
    assert settlements[0]["provider_id"] == "openai"
    assert settlements[0]["cost_usd"] == pytest.approx(0.002)


def test_local_only_control_still_blocks_openai_fallback(monkeypatch, ledger):
    attempts, settlements = ledger
    monkeypatch.setattr(
        bh, "_local_only_blocks_provider",
        lambda provider, routes=None: provider == "openai")
    monkeypatch.setattr(
        bh, "get_pricing_fetcher",
        lambda: SimpleNamespace(get_model_price=lambda model: None))
    handler = _handler(
        clients={"openai": _ExplodingCloudClient()},
        async_clients={"openai": _ExplodingCloudClient()})

    with pytest.raises(ValueError, match="Local-only mode blocks openai"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model="whisper-1"))

    assert attempts == [] and settlements == []


def test_llm_service_transcription_forwards_explicit_provider_id():
    """The public service surface carries the durable id, not a URL."""
    from core.llm_service import LLMService

    service = object.__new__(LLMService)
    captured = {}

    class _Handler:
        async def generate_transcription(self, **kwargs):
            captured.update(kwargs)
            return {"text": "ok", "model": kwargs["model"],
                    "provider": PROVIDER_KEY}

    service._get_handler = lambda **kwargs: _Handler()

    asyncio.run(service.transcribe_audio(
        file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
        local_provider_id=PROVIDER_ID))
    assert captured["local_provider_id"] == PROVIDER_ID
    assert captured["model"] == MODEL

    # Historical callers keep the exact old delegation shape.
    captured.clear()
    asyncio.run(service.transcribe_audio(
        file=io.BytesIO(_wav_bytes(1.0)), model="whisper-1"))
    assert "local_provider_id" not in captured


class _FieldRef:
    """SQLAlchemy-column stand-in so the loader's filters actually build."""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)

    def __hash__(self):
        return hash(self.name)


class _ProviderModel:
    workspace_id = _FieldRef("workspace_id")
    is_active = _FieldRef("is_active")


class _CapabilityModel:
    provider_id = _FieldRef("provider_id")


def test_local_route_loader_copies_audio_declarations(monkeypatch):
    """The scoped route record carries both new capability columns.

    The model doubles expose the attributes the loader filters on (the old
    bare ``type`` doubles raised inside the loader and silently produced no
    route). Filter expressions are asserted explicitly, not just swallowed.
    """
    import core.database as db_module
    import core.models as models

    provider = SimpleNamespace(
        id="abcdef1234567890",
        name="Scoped local",
        provider_type="openai-compatible",
        api_key=None,
        base_url="http://127.0.0.1:9/v1",
        workspace_id="ws-a",
        is_active=True,
    )
    capability = SimpleNamespace(
        provider_id=provider.id,
        model_id=MODEL,
        supports_tools=True,
        supports_vision=False,
        supports_reasoning=False,
        supports_transcription=True,
        audio_input_cost_per_second_usd=0.0,
        supports_chat=True,
        quality_score=0.75,
        context_window=8192,
    )

    class _Query:
        def __init__(self, entity, rows):
            self.entity = entity
            self._rows = rows
            self.criteria = []

        def filter(self, *args, **kwargs):
            assert not kwargs
            self.criteria.extend(args)
            return self

        def all(self):
            return list(self._rows)

    class _Session:
        def __init__(self):
            self.queries = []

        def query(self, entity):
            if entity is _ProviderModel:
                rows = [provider]
            elif entity is _CapabilityModel:
                rows = [capability]
            else:  # pragma: no cover - loader only queries these two
                raise AssertionError(f"unexpected entity {entity!r}")
            query = _Query(entity, rows)
            self.queries.append(query)
            return query

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    session = _Session()
    monkeypatch.setattr(models, "LocalModelProvider", _ProviderModel)
    monkeypatch.setattr(models, "LocalModelCapabilities", _CapabilityModel)
    monkeypatch.setattr(
        db_module, "get_db_session", lambda: session)

    class _Fetcher:
        pricing_cache = {}

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fetcher = _Fetcher()
    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: fetcher)
    monkeypatch.setattr(bh, "OpenAI", _Client)
    monkeypatch.setattr(bh, "AsyncOpenAI", _Client)

    handler = _handler()
    handler._load_local_providers()

    # The loader filtered by the CURRENT workspace and the provider row, so
    # the doubles now faithfully exercise the loader instead of raising.
    assert len(session.queries) == 2
    provider_query, capability_query = session.queries
    assert ("eq", "workspace_id", "ws-a") in provider_query.criteria
    assert ("eq", "is_active", True) in provider_query.criteria
    assert ("eq", "provider_id", provider.id) in capability_query.criteria

    route = handler._local_routes[MODEL]
    assert route["workspace_id"] == "ws-a"
    assert route["provider_id"] == provider.id
    assert route["provider_key"] == f"local_{provider.id[:8]}"
    assert route["supports_transcription"] is True
    assert route["audio_input_cost_per_second_usd"] == 0.0
    assert route["supports_chat"] is True
    # Global pricing metadata is never the local audio rate authority.
    assert "audio_input_cost_per_second_usd" not in fetcher.pricing_cache[
        MODEL]
    assert "supports_transcription" not in fetcher.pricing_cache[MODEL]


def test_same_name_routes_on_two_registrations_dispatch_independently(
        monkeypatch, ledger):
    """Two registrations serving one model name are two selectable routes.

    The display client key is truncated (``local_<id[:8]>``), so these two
    durable ids deliberately collide on it. Each selection must reach ITS
    registration's client and settle at ITS declared rate; neither may borrow
    the client the shared map happens to hold.
    """
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls_a, calls_b = [], []
    client_a = _AudioClient(SimpleNamespace(text="route a", duration=2.0),
                            calls_a)
    client_b = _AudioClient(SimpleNamespace(text="route b", duration=2.0),
                            calls_b)
    provider_a = "abcdef12-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    provider_b = "abcdef12-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    shared_key = f"local_{provider_a[:8]}"
    assert shared_key == f"local_{provider_b[:8]}"

    route_a = _route(provider_id=provider_a, rate=0.1)
    route_a.update({"client": client_a, "async_client": client_a,
                    "tenant_id": "tenant-a"})
    route_b = _route(provider_id=provider_b, rate=0.5)
    route_b.update({"client": client_b, "async_client": client_b,
                    "tenant_id": "tenant-a"})

    handler = _handler(
        # Chat's historical model-keyed map holds only the last registration.
        routes={MODEL: route_b},
        # The shared map is occupied by B only; A must not borrow it.
        clients={shared_key: client_b, "openai": _ExplodingCloudClient()},
        async_clients={shared_key: client_b},
    )
    handler._local_audio_routes = {
        (provider_a, MODEL): route_a,
        (provider_b, MODEL): route_b,
    }
    handler._local_audio_routes_loaded = True

    result_a = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(4.0)), model=MODEL,
        local_provider_id=provider_a))
    assert result_a == {
        "text": "route a", "model": MODEL, "provider": shared_key}
    assert len(calls_a) == 1 and calls_b == []
    assert attempts[-1]["provider_id"] == shared_key
    assert attempts[-1]["reserved_cost_usd"] == pytest.approx(
        4.0 * 0.1 * 1.25)
    assert settlements[-1]["cost_usd"] == pytest.approx(2.0 * 0.1)

    result_b = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(4.0)), model=MODEL,
        local_provider_id=provider_b))
    assert result_b == {
        "text": "route b", "model": MODEL, "provider": shared_key}
    assert len(calls_a) == 1 and len(calls_b) == 1
    assert attempts[-1]["provider_id"] == shared_key
    assert attempts[-1]["reserved_cost_usd"] == pytest.approx(
        4.0 * 0.5 * 1.25)
    assert settlements[-1]["cost_usd"] == pytest.approx(2.0 * 0.5)


def test_pair_index_refuses_unregistered_provider_without_borrowing(
        monkeypatch, ledger):
    """An authoritative pair index never falls back to another provider.

    The model name exists in the chat map for provider B; selecting provider A
    is an unregistered pair and fails closed before transport.
    """
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    client_b = _AudioClient(SimpleNamespace(text="must not run"), calls)
    provider_a = "provider-a"
    provider_b = "provider-b"
    route_b = _route(provider_id=provider_b)
    route_b.update({"async_client": client_b, "client": client_b})

    handler = _handler(
        routes={MODEL: route_b},
        clients={"openai": _ExplodingCloudClient()},
        async_clients={f"local_{provider_b[:8]}": client_b},
    )
    handler._local_audio_routes = {(provider_b, MODEL): route_b}
    handler._local_audio_routes_loaded = True

    with pytest.raises(ValueError, match="No local model route"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=provider_a))

    assert calls == []
    assert attempts == [] and settlements == []


def test_mismatched_tenant_refuses_before_transport(monkeypatch, ledger):
    """A registration owned by another tenant is not dispatch authority."""
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    route = _route()
    route.update({
        "async_client": _AudioClient(SimpleNamespace(text="must not run"),
                                     calls),
        "client": None,
        "tenant_id": "tenant-b",
    })
    handler = _handler(routes={MODEL: route},
                       clients={"openai": _ExplodingCloudClient()})
    handler._local_audio_routes = {(PROVIDER_ID, MODEL): route}
    handler._local_audio_routes_loaded = True

    with pytest.raises(ValueError, match="another tenant"):
        asyncio.run(handler.generate_transcription(
            file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
            local_provider_id=PROVIDER_ID))

    assert calls == []
    assert attempts == [] and settlements == []


def test_loader_indexes_same_name_routes_by_pair_with_own_clients(monkeypatch):
    """The loader keeps both registrations addressable by full identity.

    Both provider rows serve the same model name and share a truncated display
    key. The pair index must retain one entry per registration, each carrying
    that registration's own client and declared rate, while the chat map keeps
    its historical last-wins entry.
    """
    import core.database as db_module
    import core.models as models

    provider_a = SimpleNamespace(
        id="abcdef12-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        name="Scoped local A", provider_type="openai-compatible",
        api_key=None, base_url="http://127.0.0.1:9101/v1",
        workspace_id="ws-a", tenant_id="tenant-a", is_active=True)
    provider_b = SimpleNamespace(
        id="abcdef12-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        name="Scoped local B", provider_type="openai-compatible",
        api_key=None, base_url="http://127.0.0.1:9102/v1",
        workspace_id="ws-a", tenant_id="tenant-a", is_active=True)
    capability_a = SimpleNamespace(
        provider_id=provider_a.id, model_id=MODEL,
        supports_tools=True, supports_vision=False, supports_reasoning=False,
        supports_chat=True,
        supports_transcription=True, audio_input_cost_per_second_usd=0.01,
        quality_score=0.6, context_window=8192)
    capability_b = SimpleNamespace(
        provider_id=provider_b.id, model_id=MODEL,
        supports_tools=True, supports_vision=False, supports_reasoning=False,
        supports_chat=True,
        supports_transcription=True, audio_input_cost_per_second_usd=0.5,
        quality_score=0.9, context_window=8192)
    capabilities = {
        provider_a.id: capability_a,
        provider_b.id: capability_b,
    }

    class _Query:
        def __init__(self, entity, criteria):
            self.entity = entity
            self.criteria = list(criteria)

        def filter(self, *args, **kwargs):
            assert not kwargs
            self.criteria.extend(args)
            return self

        def all(self):
            if self.entity is _ProviderModel:
                return [provider_a, provider_b]
            assert self.entity is _CapabilityModel
            for criterion in self.criteria:
                if criterion[:2] == ("eq", "provider_id"):
                    cap = capabilities.get(criterion[2])
                    return [cap] if cap is not None else []
            return []  # pragma: no cover - loader always filters by provider

    class _Session:
        def query(self, entity):
            return _Query(entity, [])

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(models, "LocalModelProvider", _ProviderModel)
    monkeypatch.setattr(models, "LocalModelCapabilities", _CapabilityModel)
    monkeypatch.setattr(db_module, "get_db_session", lambda: _Session())

    class _Fetcher:
        pricing_cache = {}

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: _Fetcher())
    monkeypatch.setattr(bh, "OpenAI", _Client)
    monkeypatch.setattr(bh, "AsyncOpenAI", _Client)

    handler = _handler()
    handler._local_audio_routes = {}
    handler._local_audio_routes_loaded = False
    handler._load_local_providers()

    key = f"local_{provider_a.id[:8]}"
    assert key == f"local_{provider_b.id[:8]}"
    audio_a = handler._local_audio_routes[(provider_a.id, MODEL)]
    audio_b = handler._local_audio_routes[(provider_b.id, MODEL)]
    assert len(handler._local_audio_routes) == 2
    assert handler._local_audio_routes_loaded is True
    assert audio_a["client"] is not audio_b["client"]
    assert audio_a["client"].kwargs["base_url"] == provider_a.base_url
    assert audio_b["client"].kwargs["base_url"] == provider_b.base_url
    assert audio_a["audio_input_cost_per_second_usd"] == 0.01
    assert audio_b["audio_input_cost_per_second_usd"] == 0.5
    assert audio_a["tenant_id"] == "tenant-a"
    assert audio_a["provider_workspace_id"] == "ws-a"
    # Chat keeps its historical model-keyed last-wins behavior.
    assert handler._local_routes[MODEL]["provider_id"] == provider_b.id
    assert handler.clients[key] is audio_b["client"]


def test_loader_keeps_audio_only_model_out_of_chat_paths(monkeypatch):
    """An audio-only row is transcription-only: no chat route, no chat price.

    The same registration still gets its full-pair audio route (with its own
    client and rate), so the model remains usable for transcription while
    being absent from every chat discovery source.
    """
    import core.database as db_module
    import core.models as models

    provider = SimpleNamespace(
        id="feedface-1111-2222-3333-444455556666",
        name="Whisper box", provider_type="openai-compatible",
        api_key=None, base_url="http://127.0.0.1:9200/v1",
        workspace_id="ws-a", tenant_id="tenant-a", is_active=True)
    capability = SimpleNamespace(
        provider_id=provider.id, model_id=MODEL,
        supports_tools=False, supports_vision=False, supports_reasoning=False,
        supports_chat=False, supports_transcription=True,
        audio_input_cost_per_second_usd=0.0,
        quality_score=0.5, context_window=8192)

    class _Query:
        def __init__(self, entity):
            self.entity = entity

        def filter(self, *args, **kwargs):
            assert not kwargs
            return self

        def all(self):
            if self.entity is _ProviderModel:
                return [provider]
            assert self.entity is _CapabilityModel
            return [capability]

    class _Session:
        def query(self, entity):
            return _Query(entity)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(models, "LocalModelProvider", _ProviderModel)
    monkeypatch.setattr(models, "LocalModelCapabilities", _CapabilityModel)
    monkeypatch.setattr(db_module, "get_db_session", lambda: _Session())

    class _Fetcher:
        pricing_cache = {}

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fetcher = _Fetcher()
    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: fetcher)
    monkeypatch.setattr(bh, "OpenAI", _Client)
    monkeypatch.setattr(bh, "AsyncOpenAI", _Client)

    handler = _handler()
    handler._load_local_providers()

    # Chat discovery sources are all closed for the audio-only model.
    assert MODEL not in handler._local_routes
    assert MODEL not in fetcher.pricing_cache
    assert handler._local_served_models(f"local_{provider.id[:8]}") == []
    assert handler._reconcile_ranked_routes(
        [(f"local_{provider.id[:8]}", MODEL)]) == []
    assert handler._dispatch_catalog_admits(
        f"local_{provider.id[:8]}", MODEL, "openai") is False

    # Transcription remains available through the exact pair route.
    audio_route = handler._local_audio_routes[(provider.id, MODEL)]
    assert audio_route["supports_chat"] is False
    assert audio_route["supports_transcription"] is True
    assert audio_route["audio_input_cost_per_second_usd"] == 0.0
    assert audio_route["client"].kwargs["base_url"] == provider.base_url


def test_local_only_recognizes_exact_audio_only_route(monkeypatch, ledger):
    """Local-only evidence includes the admitted audio-only pair, exactly.

    An audio-only provider deliberately has no chat route, so the guard must
    be given the exact full-pair audio record instead of inferring locality
    from a model name or an unrelated chat entry.
    """
    attempts, settlements = ledger
    _forbid_global_pricing(monkeypatch)
    calls = []
    route = _route(supports_chat=False)
    local = _AudioClient(SimpleNamespace(text="audio only"), calls)
    route.update({"client": local, "async_client": local,
                  "tenant_id": "tenant-a"})

    handler = _handler(routes={}, clients={"openai": _ExplodingCloudClient()})
    handler._local_audio_routes = {(PROVIDER_ID, MODEL): route}
    handler._local_audio_routes_loaded = True

    seen = {}

    def _guard(provider, evidence=None):
        seen["provider"] = provider
        seen["evidence"] = evidence
        return False

    monkeypatch.setattr(bh, "_local_only_blocks_provider", _guard)

    result = asyncio.run(handler.generate_transcription(
        file=io.BytesIO(_wav_bytes(1.0)), model=MODEL,
        local_provider_id=PROVIDER_ID))

    assert result["text"] == "audio only"
    assert seen["provider"] == PROVIDER_KEY
    evidence = seen["evidence"]
    assert evidence[(PROVIDER_ID, MODEL)] is route
    assert evidence[(PROVIDER_ID, MODEL)]["provider_id"] == PROVIDER_ID
    assert len(calls) == 1
    assert attempts and settlements


def test_audio_only_route_is_never_admitted_for_chat():
    """Explicit chat selection cannot override an audio-only declaration."""
    route = _route(supports_chat=False)
    handler = _handler(
        routes={MODEL: route},
        policy=SimpleNamespace(allows=lambda provider, model: True))
    handler._local_audio_routes = {(PROVIDER_ID, MODEL): route}
    handler._local_audio_routes_loaded = True

    assert handler._dispatch_catalog_admits(
        PROVIDER_KEY, MODEL, PROVIDER_KEY) is False
    assert handler._reconcile_ranked_routes([(PROVIDER_KEY, MODEL)]) == []


def _install_loader_doubles(monkeypatch, providers, caps_by_provider):
    """A realistic LocalModelProvider/Capabilities read for the loader.

    The capability query is answered per ``provider_id`` criterion, exactly
    like the real loader's per-provider filter, so multi-registration cases
    cannot accidentally see another provider's rows.
    """
    import core.database as db_module
    import core.models as models

    class _Query:
        def __init__(self, entity, rows):
            self.entity = entity
            self._rows = rows
            self.criteria = []

        def filter(self, *args, **kwargs):
            assert not kwargs
            self.criteria.extend(args)
            return self

        def all(self):
            for criterion in self.criteria:
                if criterion[:2] == ("eq", "provider_id"):
                    return list(caps_by_provider.get(criterion[2], []))
            return list(self._rows)

    class _Session:
        def query(self, entity):
            if entity is _ProviderModel:
                return _Query(entity, providers)
            assert entity is _CapabilityModel
            return _Query(entity, [])

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _Fetcher:
        pricing_cache = {}

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(models, "LocalModelProvider", _ProviderModel)
    monkeypatch.setattr(models, "LocalModelCapabilities", _CapabilityModel)
    monkeypatch.setattr(db_module, "get_db_session", lambda: _Session())
    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: _Fetcher())
    monkeypatch.setattr(bh, "OpenAI", _Client)
    monkeypatch.setattr(bh, "AsyncOpenAI", _Client)


def test_loader_built_audio_only_pair_rejects_normal_chat_override(monkeypatch):
    """The pair index blocks the CHAT alias, not just the durable UUID.

    An audio-only row is omitted from the Chat map, so the pair index is the
    ONLY evidence the chat gate has. The caller names the normal scoped alias
    (``local_<id[:8]>``) with an explicit override; that override must still
    be rejected.
    """
    provider = SimpleNamespace(
        id="feedface-1111-2222-3333-444455556666",
        name="Audio only", provider_type="openai-compatible",
        api_key=None, base_url="http://127.0.0.1:9200/v1",
        workspace_id="ws-a", tenant_id="tenant-a", is_active=True)
    capability = SimpleNamespace(
        provider_id=provider.id, model_id=MODEL,
        supports_tools=False, supports_vision=False, supports_reasoning=False,
        supports_chat=False, supports_transcription=True,
        audio_input_cost_per_second_usd=0.0,
        quality_score=0.5, context_window=8192)
    _install_loader_doubles(
        monkeypatch, [provider], {provider.id: [capability]})

    handler = _handler(
        policy=SimpleNamespace(allows=lambda provider, model: True))
    handler._load_local_providers()

    alias = f"local_{provider.id[:8]}"
    # The row was omitted from every Chat source; only the pair remains.
    assert MODEL not in handler._local_routes
    assert (provider.id, MODEL) in handler._local_audio_routes
    # The ordinary Chat alias resolves to that audio-only pair.
    assert handler._local_route_is_audio_only(alias, MODEL) is True
    assert handler._dispatch_catalog_admits(
        alias, MODEL, alias, explicit_route=True) is False
    assert handler._reconcile_ranked_routes([(alias, MODEL)]) == []


def test_colliding_chat_alias_fails_closed_while_pair_audio_survives(
        monkeypatch):
    """A display-key collision closes chat for that alias, never audio.

    Two registrations serve the same model under the same truncated key: one
    declares chat, the other is audio-only. The shared Chat alias must fail
    closed, while transcription still resolves each durable pair's own route.
    """
    provider_a = SimpleNamespace(
        id="abcdef12-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        name="Chat local", provider_type="openai-compatible",
        api_key=None, base_url="http://127.0.0.1:9101/v1",
        workspace_id="ws-a", tenant_id="tenant-a", is_active=True)
    provider_b = SimpleNamespace(
        id="abcdef12-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        name="Audio local", provider_type="openai-compatible",
        api_key=None, base_url="http://127.0.0.1:9102/v1",
        workspace_id="ws-a", tenant_id="tenant-a", is_active=True)
    chat_cap = SimpleNamespace(
        provider_id=provider_a.id, model_id=MODEL,
        supports_tools=True, supports_vision=False, supports_reasoning=False,
        supports_chat=True, supports_transcription=False,
        audio_input_cost_per_second_usd=None,
        quality_score=0.8, context_window=8192)
    audio_cap = SimpleNamespace(
        provider_id=provider_b.id, model_id=MODEL,
        supports_tools=False, supports_vision=False, supports_reasoning=False,
        supports_chat=False, supports_transcription=True,
        audio_input_cost_per_second_usd=0.5,
        quality_score=0.6, context_window=8192)
    _install_loader_doubles(
        monkeypatch, [provider_a, provider_b],
        {provider_a.id: [chat_cap], provider_b.id: [audio_cap]})

    handler = _handler(
        policy=SimpleNamespace(allows=lambda provider, model: True))
    handler._load_local_providers()

    alias = f"local_{provider_a.id[:8]}"
    assert alias == f"local_{provider_b.id[:8]}"
    # Chat keeps the chat-capable registration ...
    assert handler._local_routes[MODEL]["provider_id"] == provider_a.id
    # ... but the colliding alias is closed for chat under this model.
    assert handler._local_route_is_audio_only(alias, MODEL) is True
    assert handler._dispatch_catalog_admits(
        alias, MODEL, alias, explicit_route=True) is False
    # Pair-keyed audio dispatch still selects the audio registration itself.
    dispatched, client, rate = handler._local_transcription_dispatch(
        model=MODEL, local_provider_id=provider_b.id)
    assert dispatched == alias
    assert client is handler._local_audio_routes[
        (provider_b.id, MODEL)]["async_client"]
    assert rate == 0.5


def test_missing_supports_chat_key_keeps_legacy_chat_eligibility():
    """Routes/rows predating the field remain chat-capable (default true)."""
    legacy = _route()
    legacy.pop("supports_chat")
    handler = _handler(
        routes={MODEL: legacy},
        policy=SimpleNamespace(allows=lambda provider, model: True))
    handler._local_audio_routes = {(PROVIDER_ID, MODEL): legacy}
    handler._local_audio_routes_loaded = True

    assert handler._local_route_is_audio_only(PROVIDER_KEY, MODEL) is False
    assert handler._local_served_models(PROVIDER_KEY) == [MODEL]


def test_transcription_entry_points_expose_local_provider_id():
    """Both public entry points accept the explicit durable provider id."""
    byok_signature = inspect.signature(
        bh.BYOKHandler.generate_transcription)
    assert "local_provider_id" in byok_signature.parameters

    from core.llm_service import LLMService

    service_signature = inspect.signature(LLMService.transcribe_audio)
    assert "local_provider_id" in service_signature.parameters
