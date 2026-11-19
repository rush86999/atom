"""Synthetic tests for the opt-in scoped credential read and create.

These tests intentionally use a scratch ORM/query and in-memory encrypted
values. No database, network, provider, or live credential is involved.
"""

from datetime import datetime, timedelta, timezone
import importlib
import logging
from pathlib import Path
import sys
import types

import pytest
from sqlalchemy.exc import IntegrityError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _ensure_core_imports():
    """Import the service, providing minimal core stubs in this scratch tree."""
    try:
        core = importlib.import_module("core")
    except ModuleNotFoundError:
        core = types.ModuleType("core")
        core.__path__ = [str(BACKEND_DIR / "core")]
        sys.modules["core"] = core

    try:
        importlib.import_module("core.config")
    except ModuleNotFoundError:
        config = types.ModuleType("core.config")
        config.get_config = lambda: types.SimpleNamespace(
            security=types.SimpleNamespace(
                encryption_key="unit-test-encryption-key",
                secret_key="unit-test-secret-key",
            )
        )
        sys.modules["core.config"] = config
        setattr(core, "config", config)

    try:
        importlib.import_module("core.database")
    except ModuleNotFoundError:
        database = types.ModuleType("core.database")

        def get_db_session():
            raise RuntimeError("tests must monkeypatch get_db_session")

        database.get_db_session = get_db_session
        sys.modules["core.database"] = database
        setattr(core, "database", database)

    try:
        importlib.import_module("core.models")
    except ModuleNotFoundError:
        models = types.ModuleType("core.models")

        class UserConnection:
            pass

        models.UserConnection = UserConnection
        sys.modules["core.models"] = models
        setattr(core, "models", models)


_ensure_core_imports()
connection_service_module = importlib.import_module("core.connection_service")


TEST_SECURITY = types.SimpleNamespace(
    encryption_key="unit-test-encryption-key",
    secret_key="unit-test-secret-key",
)
SCOPE = {
    "user_id": "user-1",
    "tenant_id": "tenant-1",
    "workspace_id": "workspace-1",
    "connection_id": "connection-1",
    "integration_id": "integration-1",
}


class ScratchColumn:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)

    __hash__ = object.__hash__


class ScratchUserConnection:
    id = ScratchColumn("id")
    user_id = ScratchColumn("user_id")
    tenant_id = ScratchColumn("tenant_id")
    workspace_id = ScratchColumn("workspace_id")
    integration_id = ScratchColumn("integration_id")
    status = ScratchColumn("status")

    def __init__(self, **values):
        self.__dict__.update(values)


class FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self.filters = []
        self.first_calls = 0

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    @staticmethod
    def _matches(row, criterion):
        operation, field, expected = criterion
        assert operation == "eq"
        return getattr(row, field, object()) == expected

    def first(self):
        self.first_calls += 1
        for row in self._rows:
            if all(self._matches(row, criterion) for criterion in self.filters):
                return row
        return None


class FakeSession:
    def __init__(self, rows):
        self.query_count = 0
        self.commits = 0
        self.rollbacks = 0
        self.added = []
        self.writes = []
        self.query_obj = FakeQuery(rows)

    def query(self, model):
        assert model is ScratchUserConnection
        self.query_count += 1
        return self.query_obj

    def commit(self):
        self.commits += 1
        self.writes.append("commit")

    def add(self, obj):
        self.added.append(obj)
        self.writes.append("add")

    def delete(self, obj):
        self.writes.append("delete")

    def refresh(self, obj):
        self.writes.append("refresh")

    def rollback(self):
        self.rollbacks += 1
        self.writes.append("rollback")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_service():
    service = connection_service_module.ConnectionService.__new__(
        connection_service_module.ConnectionService
    )
    service.security_config = TEST_SECURITY
    service._fernet = None
    return service


def _row(service, **overrides):
    values = {
        "id": SCOPE["connection_id"],
        "user_id": SCOPE["user_id"],
        "tenant_id": SCOPE["tenant_id"],
        "workspace_id": SCOPE["workspace_id"],
        "integration_id": SCOPE["integration_id"],
        "status": "active",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "credentials": service._encrypt({"api_key": "synthetic-secret"}),
        "last_used": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _install(monkeypatch, rows):
    session = FakeSession(rows)
    monkeypatch.setattr(connection_service_module, "get_db_session", lambda: session)
    monkeypatch.setattr(
        connection_service_module, "UserConnection", ScratchUserConnection
    )
    return session


def _call(service, **overrides):
    values = dict(SCOPE)
    values.update(overrides)
    return service.get_scoped_connection_credentials(**values)


def _create_call(service, **overrides):
    values = {
        **SCOPE,
        "name": "Synthetic connection",
        "credentials": {"api_key": "synthetic-secret"},
    }
    values.update(overrides)
    return service.create_scoped_connection(**values)


def test_reads_exact_active_scope_with_all_filters_before_decrypt(monkeypatch):
    service = _make_service()
    row = _row(service)
    last_used = row.last_used
    session = _install(monkeypatch, [row])

    decrypt_calls = []
    real_decrypt = service._decrypt

    def tracking_decrypt(encrypted):
        assert session.query_obj.first_calls == 1
        decrypt_calls.append(encrypted)
        return real_decrypt(encrypted)

    monkeypatch.setattr(service, "_decrypt", tracking_decrypt)

    result = _call(service)

    assert result == {"api_key": "synthetic-secret"}
    assert decrypt_calls == [row.credentials]
    assert session.query_count == 1
    assert session.query_obj.first_calls == 1
    assert len(session.query_obj.filters) == 6
    assert set(session.query_obj.filters) == {
        ("eq", "id", SCOPE["connection_id"]),
        ("eq", "user_id", SCOPE["user_id"]),
        ("eq", "tenant_id", SCOPE["tenant_id"]),
        ("eq", "workspace_id", SCOPE["workspace_id"]),
        ("eq", "integration_id", SCOPE["integration_id"]),
        ("eq", "status", "active"),
    }
    assert session.commits == 0
    assert session.writes == []
    assert row.last_used == last_used
    assert row.status == "active"


@pytest.mark.parametrize("field", list(SCOPE))
@pytest.mark.parametrize("value", [None, "", "   ", 123])
def test_rejects_missing_or_blank_scope_identifiers_before_query(
    monkeypatch, field, value
):
    service = _make_service()
    session = _install(monkeypatch, [_row(service)])
    monkeypatch.setattr(
        service, "_decrypt", lambda encrypted: pytest.fail("must not decrypt")
    )

    assert _call(service, **{field: value}) is None
    assert session.query_count == 0
    assert session.query_obj.first_calls == 0


def test_expired_row_is_refused_using_existing_timezone_helper(monkeypatch):
    service = _make_service()
    expired_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        seconds=1
    )
    row = _row(service, expires_at=expired_naive)
    session = _install(monkeypatch, [row])

    helper_calls = []
    real_helper = service._ensure_aware_datetime

    def tracking_helper(value):
        helper_calls.append(value)
        return real_helper(value)

    monkeypatch.setattr(service, "_ensure_aware_datetime", tracking_helper)
    monkeypatch.setattr(
        service, "_decrypt", lambda encrypted: pytest.fail("must not decrypt")
    )

    assert _call(service) is None
    assert helper_calls == [expired_naive]
    assert session.commits == 0
    assert session.writes == []


def test_future_naive_expiry_is_allowed(monkeypatch):
    service = _make_service()
    future_naive = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    row = _row(service, expires_at=future_naive)
    _install(monkeypatch, [row])

    assert _call(service) == {"api_key": "synthetic-secret"}


@pytest.mark.parametrize(
    "credentials",
    [
        None,
        "",
        "   ",
        '{"api_key": "synthetic-secret"}',
        '  {"api_key": "synthetic-secret"}',
        {"api_key": "synthetic-secret"},
    ],
)
def test_refuses_empty_or_unencrypted_credentials_before_decrypt(
    monkeypatch, credentials
):
    service = _make_service()
    row = _row(service, credentials=credentials)
    session = _install(monkeypatch, [row])
    monkeypatch.setattr(
        service, "_decrypt", lambda encrypted: pytest.fail("must not decrypt")
    )

    assert _call(service) is None
    assert session.commits == 0
    assert session.writes == []


@pytest.mark.parametrize(
    "plaintext",
    [
        {"api_key": "synthetic-secret", "scope": None},
        {"api_key": "synthetic-secret", "refresh_token": ""},
        {"api_key": "synthetic-secret", "scope": "   ", "expires_in": None},
        {"api_key": None},
        {"access_token": ""},
    ],
)
def test_allows_blank_or_null_optional_credential_metadata(monkeypatch, plaintext):
    service = _make_service()
    row = _row(service, credentials=service._encrypt(plaintext))
    _install(monkeypatch, [row])

    assert _call(service) == plaintext


def test_refuses_empty_decrypted_dict(monkeypatch):
    service = _make_service()
    row = _row(service, credentials=service._encrypt({}))
    _install(monkeypatch, [row])

    assert _call(service) is None


def test_refuses_decryption_failure(monkeypatch):
    service = _make_service()
    row = _row(service, credentials="not-a-valid-fernet-token")
    session = _install(monkeypatch, [row])

    assert _call(service) is None
    assert session.commits == 0
    assert session.writes == []


def test_read_is_side_effect_free(monkeypatch):
    service = _make_service()
    row = _row(service)
    last_used = row.last_used
    original_ciphertext = row.credentials
    session = _install(monkeypatch, [row])

    monkeypatch.setattr(
        service,
        "_refresh_token_if_needed",
        lambda *args, **kwargs: pytest.fail("must not refresh"),
    )

    assert _call(service) == {"api_key": "synthetic-secret"}
    assert row.last_used == last_used
    assert row.status == "active"
    assert row.credentials == original_ciphertext
    assert session.commits == 0
    assert session.writes == []


def test_create_inserts_exact_caller_scope_with_encrypted_credentials(monkeypatch):
    service = _make_service()
    session = _install(monkeypatch, [])
    credentials = {"api_key": "synthetic-secret", "expires_in": "600"}
    before = datetime.now(timezone.utc)

    assert _create_call(service, credentials=credentials) is True

    after = datetime.now(timezone.utc)
    assert credentials == {"api_key": "synthetic-secret", "expires_in": "600"}
    assert session.query_count == 1
    assert session.query_obj.first_calls == 1
    assert session.query_obj.filters == [
        ("eq", "id", SCOPE["connection_id"]),
    ]
    assert len(session.added) == 1
    created = session.added[0]
    assert isinstance(created, ScratchUserConnection)
    assert created.id == SCOPE["connection_id"]
    assert created.user_id == SCOPE["user_id"]
    assert created.tenant_id == SCOPE["tenant_id"]
    assert created.workspace_id == SCOPE["workspace_id"]
    assert created.integration_id == SCOPE["integration_id"]
    assert created.connection_name == "Synthetic connection"
    assert created.status == "active"
    assert isinstance(created.credentials, str)
    assert "synthetic-secret" not in created.credentials
    assert service._decrypt(created.credentials) == credentials
    assert created.expires_at.tzinfo is not None
    assert before + timedelta(seconds=599) <= created.expires_at
    assert created.expires_at <= after + timedelta(seconds=601)
    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.writes == ["add", "commit"]


def test_create_allows_nonempty_credentials_with_blank_values(monkeypatch):
    service = _make_service()
    session = _install(monkeypatch, [])

    assert _create_call(service, credentials={"access_token": ""}) is True
    assert session.added[0].credentials != {"access_token": ""}
    assert service._decrypt(session.added[0].credentials) == {"access_token": ""}


@pytest.mark.parametrize("field", [*SCOPE, "name"])
@pytest.mark.parametrize("value", [None, "", "   ", 123, True])
def test_create_rejects_missing_or_blank_identifiers_before_query(
    monkeypatch, field, value
):
    service = _make_service()
    session = _install(monkeypatch, [])
    monkeypatch.setattr(
        service, "_encrypt", lambda data: pytest.fail("must not encrypt")
    )

    assert _create_call(service, **{field: value}) is False
    assert session.query_count == 0
    assert session.query_obj.first_calls == 0
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0
    assert session.writes == []


@pytest.mark.parametrize(
    "credentials",
    [None, {}, [], "", "synthetic-secret", 0, False],
)
def test_create_rejects_non_dict_or_empty_credentials_before_query(
    monkeypatch, credentials
):
    service = _make_service()
    session = _install(monkeypatch, [])
    monkeypatch.setattr(
        service, "_encrypt", lambda data: pytest.fail("must not encrypt")
    )

    assert _create_call(service, credentials=credentials) is False
    assert session.query_count == 0
    assert session.query_obj.first_calls == 0
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0
    assert session.writes == []


def test_create_refuses_existing_id_without_updating_or_encrypting(monkeypatch):
    service = _make_service()
    existing = _row(
        service,
        connection_name="Old name",
        credentials=service._encrypt({"api_key": "old-synthetic-secret"}),
        status="disabled",
    )
    original = types.SimpleNamespace(**vars(existing))
    session = _install(monkeypatch, [existing])
    monkeypatch.setattr(
        service, "_encrypt", lambda data: pytest.fail("must not re-encrypt")
    )

    assert _create_call(service) is False
    assert session.query_count == 1
    assert session.query_obj.first_calls == 1
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0
    assert session.writes == []
    assert vars(existing) == vars(original)


def test_create_does_not_adopt_or_widen_another_connections_credentials(
    monkeypatch,
):
    service = _make_service()
    old = _row(
        service,
        id="old-connection",
        connection_name="Old connection",
        credentials=service._encrypt({"api_key": "old-synthetic-secret"}),
        status="disabled",
    )
    old_credentials = old.credentials
    session = _install(monkeypatch, [old])

    assert _create_call(service) is True

    assert old.id == "old-connection"
    assert old.connection_name == "Old connection"
    assert old.credentials == old_credentials
    assert old.status == "disabled"
    assert len(session.added) == 1
    created = session.added[0]
    assert created.id == SCOPE["connection_id"]
    assert created.id != old.id
    assert service._decrypt(created.credentials) == {
        "api_key": "synthetic-secret"
    }
    assert session.commits == 1
    assert session.rollbacks == 0


def test_create_rolls_back_concurrent_primary_key_collision(monkeypatch):
    service = _make_service()
    session = _install(monkeypatch, [])

    def collide():
        session.writes.append("commit")
        session.commits += 1
        raise IntegrityError(
            "INSERT INTO user_connections",
            {},
            Exception("UNIQUE constraint failed: user_connections.id"),
        )

    monkeypatch.setattr(session, "commit", collide)

    assert _create_call(service) is False
    assert session.query_count == 1
    assert len(session.added) == 1
    assert session.commits == 1
    assert session.rollbacks == 1
    assert session.writes == ["add", "commit", "rollback"]


def test_create_never_logs_credential_material(monkeypatch, caplog):
    service = _make_service()
    secret = "synthetic-credential-material"
    session = _install(monkeypatch, [])

    with caplog.at_level(logging.DEBUG):
        assert _create_call(
            service,
            credentials={"api_key": secret, "expires_in": "not-an-integer"},
        ) is True

    def collide():
        raise IntegrityError(
            "INSERT INTO user_connections",
            {"credentials": secret},
            Exception(f"UNIQUE constraint failed for {secret}"),
        )

    monkeypatch.setattr(session, "commit", collide)
    with caplog.at_level(logging.DEBUG):
        assert _create_call(
            service, connection_id="connection-2", credentials={"api_key": secret}
        ) is False

    assert secret not in caplog.text
