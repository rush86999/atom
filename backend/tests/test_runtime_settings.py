"""Runtime Settings layer — env vars as UI admin settings.

Covers the resolution core (``core/runtime_settings.py``):

* Precedence: explicit env var WINS > DB row > catalog default
  (kill-switch semantics preserved — an operator can always force
  behavior via env even after a UI edit).
* Type coercion per the catalog spec; bad values fall back, never raise.
* TTL cache over DB rows with explicit invalidation on writes.
* Secrets are never exposed through the catalog serializer.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.runtime_settings import (
    ResolvedSetting,
    get_setting,
    invalidate_settings_cache,
    resolve_setting,
)
from core.settings_catalog import (
    SETTING_CATALOG,
    SettingSpec,
    find_spec,
    serialize_catalog,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    invalidate_settings_cache()
    yield
    invalidate_settings_cache()


@pytest.fixture
def db():
    """In-memory SQLite with runtime_settings table created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base
    from core.models import RuntimeSetting  # noqa: F401

    Base.metadata.create_all(bind=engine, tables=[RuntimeSetting.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# helpers -------------------------------------------------------------------

def _seed_db_row(db, key: str, value):
    from core.models import RuntimeSetting

    row = db.get(RuntimeSetting, key)
    if row is None:
        db.add(RuntimeSetting(key=key, value_json=value))
    else:
        row.value_json = value
    db.commit()


# ============================================================================
# Catalog integrity
# ============================================================================


class TestCatalog:
    def test_catalog_covers_claude_md_flag_families(self):
        keys = {s.key for s in SETTING_CATALOG}
        for expected in (
            "ATOM_SELF_CONSISTENCY",
            "ATOM_SANDBOX_ENABLED",
            "ATOM_RADIO_ENABLED",
            "ATOM_STAGE_ROUTING_ENABLED",
            "ATOM_TRUST_CALIBRATION_ENABLED",
            "ATOM_ORG_TELEMETRY_ENABLED",
            "ATOM_GATEWAY_ENABLED",
            "MAX_UPLOAD_BYTES",
            "LANCEDB_CLOUD_ENABLED",
        ):
            assert expected in keys, f"missing catalog entry: {expected}"

    def test_every_spec_has_category_and_description(self):
        for spec in SETTING_CATALOG:
            assert spec.category, spec.key
            assert spec.description, spec.key
            assert spec.type in {"bool", "int", "float", "str", "json"}, spec.key

    def test_no_duplicate_keys(self):
        keys = [s.key for s in SETTING_CATALOG]
        assert len(keys) == len(set(keys))

    def test_find_spec_roundtrip(self):
        spec = find_spec("ATOM_SELF_CONSISTENCY_SAMPLES")
        assert spec is not None and spec.type == "int" and spec.default == 3
        assert find_spec("NOT_A_REAL_VAR") is None

    def test_secrets_never_serialize_values(self):
        specs = [
            SettingSpec(
                key="TEST_SECRET_KEY",
                type="str",
                default="hunter2",
                category="t",
                description="d",
                secret=True,
            )
        ]
        out = serialize_catalog(specs, resolved={})
        entry = next(e for e in out if e["key"] == "TEST_SECRET_KEY")
        assert entry["secret"] is True
        assert entry["editable"] is False
        # Neither env value nor default may leak for secrets.
        assert "hunter2" not in json.dumps(out)


# ============================================================================
# Resolution precedence
# ============================================================================


class TestPrecedence:
    def test_default_when_unset_everywhere(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("ATOM_SC_TEST_FLAG", None)
            res = resolve_setting("ATOM_SC_TEST_FLAG", db=None)
            assert res.value is False and res.source == "default"

    def test_env_wins_over_db(self, db):
        _seed_db_row(db, "ATOM_SC_TEST_INT", 99)
        with patch.dict("os.environ", {"ATOM_SC_TEST_INT": "7"}):
            res = resolve_setting("ATOM_SC_TEST_INT", db=db)
            assert res.value == 7 and res.source == "env"

    def test_db_used_when_env_unset(self, db):
        _seed_db_row(db, "ATOM_SC_TEST_INT", 42)
        import os

        os.environ.pop("ATOM_SC_TEST_INT", None)
        res = resolve_setting("ATOM_SC_TEST_INT", db=db)
        assert res.value == 42 and res.source == "db"

    def test_unknown_key_returns_none_value_without_raising(self, db):
        res = resolve_setting("TOTALLY_UNKNOWN_SETTING_XYZ", db=db)
        assert res.value is None and res.source == "unknown"

    def test_bad_db_json_falls_back_to_default(self, db):
        from core.models import RuntimeSetting

        # A dict cannot coerce to int — must fall through to default.
        db.add(RuntimeSetting(key="ATOM_SC_TEST_INT", value_json={"oops": True}))
        db.commit()
        import os

        os.environ.pop("ATOM_SC_TEST_INT", None)
        res = resolve_setting("ATOM_SC_TEST_INT", db=db)
        assert res.value == 3 and res.source == "default"

    def test_db_bool_string_coerces_like_env(self, db):
        # Strings coerce under the same rules whether they arrive from
        # env or from a DB row ("not-a-bool" → False, never raises).
        from core.models import RuntimeSetting

        db.add(RuntimeSetting(key="ATOM_SC_TEST_BOOL", value_json="not-a-bool"))
        db.commit()
        import os

        os.environ.pop("ATOM_SC_TEST_BOOL", None)
        res = resolve_setting("ATOM_SC_TEST_BOOL", db=db)
        assert res.value is False and res.source == "db"


class TestCoercion:
    def test_bool_coercion_from_env_string(self):
        for raw, want in (("true", True), ("1", True), ("yes", True), ("0", False), ("false", False)):
            with patch.dict("os.environ", {"ATOM_SC_TEST_BOOL": raw}):
                assert resolve_setting("ATOM_SC_TEST_BOOL", db=None).value is want

    def test_int_coercion_and_garbage_fallback(self):
        with patch.dict("os.environ", {"ATOM_SC_TEST_INT": "12"}):
            assert resolve_setting("ATOM_SC_TEST_INT").value == 12
        with patch.dict("os.environ", {"ATOM_SC_TEST_INT": "garbage"}):
            res = resolve_setting("ATOM_SC_TEST_INT")
            assert res.value == 3 and res.source == "default"

    def test_float_coercion(self):
        with patch.dict("os.environ", {"ATOM_SC_TEST_FLOAT": "0.42"}):
            assert resolve_setting("ATOM_SC_TEST_FLOAT").value == pytest.approx(0.42)

    def test_get_setting_convenience_returns_bare_value(self):
        with patch.dict("os.environ", {"ATOM_SC_TEST_INT": "5"}):
            assert get_setting("ATOM_SC_TEST_INT") == 5


# ============================================================================
# Cache behavior
# ============================================================================


class TestCache:
    def test_second_resolve_hits_cache_not_db(self, db):
        _seed_db_row(db, "ATOM_SC_TEST_STR", "first")
        import os

        os.environ.pop("ATOM_SC_TEST_STR", None)
        assert resolve_setting("ATOM_SC_TEST_STR", db=db).value == "first"
        # Mutate DB directly WITHOUT invalidation — cached value must persist.
        _seed_db_row(db, "ATOM_SC_TEST_STR", "second")
        assert resolve_setting("ATOM_SC_TEST_STR", db=db).value == "first"
        invalidate_settings_cache()
        assert resolve_setting("ATOM_SC_TEST_STR", db=db).value == "second"

    def test_ttl_expiry_re_reads_db(self, db):
        _seed_db_row(db, "ATOM_SC_TEST_STR", "old")
        import os

        os.environ.pop("ATOM_SC_TEST_STR", None)
        assert resolve_setting("ATOM_SC_TEST_STR", db=db).value == "old"
        _seed_db_row(db, "ATOM_SC_TEST_STR", "new")
        with patch("core.runtime_settings._CACHE_TTL_SECONDS", 0.0):
            assert resolve_setting("ATOM_SC_TEST_STR", db=db).value == "new"

    def test_resolved_dataclass_shape(self):
        r = ResolvedSetting(value=True, source="env")
        assert (r.value, r.source) == (True, "env")


# ============================================================================
# Imports sanity (stdlib-only surface)
# ============================================================================


def test_module_exports():
    import core.runtime_settings as rs

    for name in (
        "get_setting",
        "resolve_setting",
        "get_bool_setting",
        "get_int_setting",
        "get_float_setting",
        "invalidate_settings_cache",
    ):
        assert hasattr(rs, name), name


import os  # noqa: E402  (kept at bottom so patches above read cleanly)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
