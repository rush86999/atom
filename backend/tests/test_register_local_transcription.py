"""Tests for the operator-only on-host transcription provisioning CLI.

The URL/rate validation tests need no backend imports. The ORM tests create an
isolated in-memory SQLite database and are skipped when this trimmed worker does
not provide the application's model imports.
"""
from __future__ import annotations

import sys
import types
from contextlib import contextmanager

import pytest

from scripts import register_local_transcription as cli


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("http://127.0.0.1:9000/v1", "http://127.0.0.1:9000/v1"),
        ("http://127.0.0.1:9000/v1/", "http://127.0.0.1:9000/v1"),
        ("HTTP://127.0.0.1:9000/v1", "http://127.0.0.1:9000/v1"),
        ("http://[::1]:9000/v1", "http://[::1]:9000/v1"),
    ],
)
def test_parse_loopback_base_url_accepts_strict_profile(raw, expected):
    assert cli.parse_loopback_base_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "https://127.0.0.1:9000/v1",
        "http://localhost:9000/v1",
        "http://transcription.internal:9000/v1",
        "http://127.0.0.1/v1",
        "http://127.0.0.1:/v1",
        "http://127.0.0.1:0/v1",
        "http://127.0.0.1:70000/v1",
        "http://127.0.0.1:9000/v1/audio/transcriptions",
        "http://127.0.0.1:9000/v2",
        "http://127.0.0.1:9000/v1?x=1",
        "http://127.0.0.1:9000/v1#fragment",
        "http://user@127.0.0.1:9000/v1",
        "http://user:secret@127.0.0.1:9000/v1",
        "http://10.0.0.1:9000/v1",
        "http://192.168.1.10:9000/v1",
        "http://0.0.0.0:9000/v1",
        "http://169.254.169.254:9000/v1",
    ],
)
def test_parse_loopback_base_url_rejects_non_profile_values(raw):
    with pytest.raises(ValueError):
        cli.parse_loopback_base_url(raw)


@pytest.mark.parametrize("raw", ["0", "0.0", "0.0001", "12.5"])
def test_parse_audio_rate_accepts_finite_nonnegative(raw):
    value = cli.parse_audio_rate(raw)
    assert isinstance(value, float)
    assert value >= 0.0


@pytest.mark.parametrize(
    "raw", ["", "nan", "NaN", "inf", "-inf", "-0.01", "not-a-number", None]
)
def test_parse_audio_rate_rejects_invalid(raw):
    with pytest.raises(ValueError):
        cli.parse_audio_rate(raw)


@pytest.fixture()
def isolated_orm():
    """In-memory SQLite with only the tables this CLI touches."""
    models = pytest.importorskip("core.models")
    if not hasattr(models.LocalModelCapabilities, "supports_chat"):
        pytest.skip("LocalModelCapabilities.supports_chat is required")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(
        engine,
        tables=[
            models.Tenant.__table__,
            models.Workspace.__table__,
            models.LocalModelProvider.__table__,
            models.LocalModelCapabilities.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session, models
    finally:
        engine.dispose()


@pytest.fixture()
def seeded_orm(isolated_orm):
    Session, models = isolated_orm
    with Session() as db:
        db.add(
            models.Tenant(
                id="tenant-1",
                name="Tenant One",
                subdomain="tenant-one",
                edition="personal",
            )
        )
        db.add(
            models.Workspace(
                id="ws-1",
                name="Workspace One",
                tenant_id="tenant-1",
            )
        )
        db.add(
            models.Workspace(
                id="ws-empty-tenant",
                name="Workspace Without Tenant",
                tenant_id="",
            )
        )
        db.commit()
    return Session, models


def _provision(db, **overrides):
    values = {
        "workspace_id": "ws-1",
        "name": "On-host Whisper",
        "base_url": "http://127.0.0.1:9000/v1",
        "model_id": "whisper-1",
        "audio_input_cost_per_second_usd": 0.0,
    }
    values.update(overrides)
    return cli.provision_local_transcription(db, **values)


def test_provision_writes_provider_and_transcription_capability(seeded_orm):
    Session, models = seeded_orm
    with Session() as db:
        result = _provision(db)
        db.commit()

    with Session() as db:
        provider = db.query(models.LocalModelProvider).one()
        capability = db.query(models.LocalModelCapabilities).one()

        assert provider.id == result["provider_id"]
        assert provider.workspace_id == "ws-1"
        assert provider.tenant_id == "tenant-1"
        assert provider.name == "On-host Whisper"
        assert provider.provider_type == "custom"
        assert provider.base_url == "http://127.0.0.1:9000/v1"
        assert provider.api_key is None
        assert bool(provider.is_active) is True

        assert capability.id == result["capability_id"]
        assert capability.provider_id == provider.id
        assert capability.workspace_id == "ws-1"
        assert capability.model_id == "whisper-1"
        assert bool(capability.supports_transcription) is True
        assert capability.audio_input_cost_per_second_usd == 0.0
        assert bool(capability.supports_tools) is False
        assert bool(capability.supports_vision) is False
        assert bool(capability.supports_reasoning) is False
        assert bool(capability.supports_chat) is False


def test_repeat_identical_configuration_is_a_noop(seeded_orm):
    Session, models = seeded_orm
    with Session() as db:
        first = _provision(db)
        db.commit()
    with Session() as db:
        second = _provision(db)
        db.commit()

    assert second["provider_id"] == first["provider_id"]
    assert second["capability_id"] == first["capability_id"]
    assert second["created_provider"] is False
    assert second["created_capability"] is False

    with Session() as db:
        assert db.query(models.LocalModelProvider).count() == 1
        assert db.query(models.LocalModelCapabilities).count() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "Different Name"},
        {"base_url": "http://127.0.0.1:9001/v1"},
        {"model_id": "another-model"},
        {"audio_input_cost_per_second_usd": 0.5},
    ],
)
def test_changed_configuration_is_refused_without_changes(
    seeded_orm, overrides
):
    Session, models = seeded_orm
    with Session() as db:
        _provision(db)
        db.commit()

    with Session() as db:
        with pytest.raises(cli.ProvisionError):
            _provision(db, **overrides)

    with Session() as db:
        assert db.query(models.LocalModelProvider).count() == 1
        assert db.query(models.LocalModelCapabilities).count() == 1
        capability = db.query(models.LocalModelCapabilities).one()
        assert capability.model_id == "whisper-1"
        assert capability.audio_input_cost_per_second_usd == 0.0


def test_missing_workspace_is_refused(seeded_orm):
    Session, models = seeded_orm
    with Session() as db:
        with pytest.raises(cli.ProvisionError):
            _provision(db, workspace_id="missing-workspace")
    with Session() as db:
        assert db.query(models.LocalModelProvider).count() == 0


def test_workspace_without_tenant_is_refused(seeded_orm):
    Session, models = seeded_orm
    with Session() as db:
        with pytest.raises(cli.ProvisionError):
            _provision(db, workspace_id="ws-empty-tenant")
    with Session() as db:
        assert db.query(models.LocalModelProvider).count() == 0


def test_existing_provider_name_with_different_identity_is_refused(seeded_orm):
    Session, models = seeded_orm
    with Session() as db:
        db.add(
            models.LocalModelProvider(
                id="ui-created-provider",
                workspace_id="ws-1",
                tenant_id="tenant-1",
                name="On-host Whisper",
                provider_type="custom",
                base_url="http://127.0.0.1:9999/v1",
            )
        )
        db.commit()

    with Session() as db:
        with pytest.raises(cli.ProvisionError):
            _provision(db)

    with Session() as db:
        assert db.query(models.LocalModelProvider).count() == 1
        assert db.query(models.LocalModelCapabilities).count() == 0


def test_old_schema_without_supports_chat_fails_closed(monkeypatch):
    models = pytest.importorskip("core.models")

    class OldCapabilities:
        pass

    monkeypatch.setattr(models, "LocalModelCapabilities", OldCapabilities)

    with pytest.raises(cli.ProvisionError, match="supports_chat"):
        cli.provision_local_transcription(
            object(),
            workspace_id="ws-1",
            name="On-host Whisper",
            base_url="http://127.0.0.1:9000/v1",
            model_id="whisper-1",
            audio_input_cost_per_second_usd=0.0,
        )


def _cli_args() -> list[str]:
    return [
        "--workspace-id", "ws-1",
        "--name", "On-host Whisper",
        "--base-url", "http://127.0.0.1:9000/v1",
        "--model", "whisper-1",
        "--audio-input-cost-per-second-usd", "0",
    ]


@pytest.mark.parametrize("value", [None, "", "   "])
def test_main_requires_explicit_nonempty_database_url(monkeypatch, capsys, value):
    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)

    assert cli.main(_cli_args()) == 1

    captured = capsys.readouterr()
    assert "DATABASE_URL is required" in captured.err


def test_main_reports_only_error_class_for_unexpected_failure(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    class BoomError(Exception):
        pass

    @contextmanager
    def failing_session():
        raise BoomError("database password=secret at /private/db.sqlite")
        yield  # pragma: no cover

    fake_core = types.ModuleType("core")
    fake_core.__path__ = []
    fake_database = types.ModuleType("core.database")
    fake_database.get_db_session = failing_session
    monkeypatch.setitem(sys.modules, "core", fake_core)
    monkeypatch.setitem(sys.modules, "core.database", fake_database)

    assert cli.main(_cli_args()) == 1

    captured = capsys.readouterr()
    assert "BoomError" in captured.err
    assert "secret" not in captured.err
    assert "password" not in captured.err
