"""Regression tests for DELETE /api/ai/providers/{provider_id}/keys/{key_name}.

The wizard/Settings store keys under TENANT-scoped manager ids
(``tenant_{tenant}_{provider}_{key}_{env}``) AND sync them into the
``tenant_settings`` table. The old delete implementation only removed the
exact global-format id and never touched the DB, so UI-saved keys were
undeletable (404, then the provider still showed "configured" from the DB
row). These tests pin the cross-store semantics.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException

from api.byok_routes import delete_api_key


def _manager(keys: dict):
    saved = {"saved": False}

    def _save():
        saved["saved"] = True

    return SimpleNamespace(api_keys=keys, _save_configuration=_save), saved


def _db(with_setting: bool = True):
    db = MagicMock()
    if with_setting:
        setting = SimpleNamespace(setting_key="OPENAI_API_KEY")
        db.query.return_value.filter.return_value.first.return_value = setting
    else:
        db.query.return_value.filter.return_value.first.return_value = None
    return db


def _delete(provider_id="openai", key_name="default", manager=None, db=None,
            tenant_id="default", environment="production"):
    return asyncio.run(delete_api_key(
        provider_id=provider_id,
        key_name=key_name,
        environment=environment,
        current_user=SimpleNamespace(id="u1"),
        tenant=SimpleNamespace(id=tenant_id),
        byok_manager=manager,
        db=db,
    ))


def test_deletes_tenant_scoped_row_and_db_sync():
    """The wizard's exact footprint: tenant-scoped manager row + DB setting."""
    keys = {"tenant_default_openai_openai (onboarding)_production": object()}
    manager, saved = _manager(keys)
    db = _db(with_setting=True)

    result = _delete(key_name="openai (onboarding)", manager=manager, db=db)

    assert keys == {}, "tenant-scoped manager row must be removed"
    assert saved["saved"] is True
    db.delete.assert_called_once()
    db.commit.assert_called_once()
    assert "tenant_settings:OPENAI_API_KEY" in result.data["removed"]


def test_deletes_global_row_and_tenant_rows_together():
    keys = {
        "openai_default_production": object(),
        "tenant_default_openai_default_production": object(),
        "tenant_other_openai_default_production": object(),  # different tenant: kept
        "openrouter_default_production": object(),  # other provider: kept
    }
    manager, _saved = _manager(keys)
    db = _db(with_setting=False)

    result = _delete(manager=manager, db=db)

    assert "openai_default_production" in result.data["removed"]
    assert "tenant_default_openai_default_production" in result.data["removed"]
    assert "tenant_other_openai_default_production" not in result.data["removed"]
    assert "openrouter_default_production" in keys
    assert "tenant_other_openai_default_production" in keys


def test_named_key_delete_does_not_touch_other_named_keys():
    keys = {
        "tenant_default_openrouter_t-1_production": object(),
        "tenant_default_openrouter_default_production": object(),
    }
    manager, _saved = _manager(keys)
    db = _db(with_setting=False)

    _delete(provider_id="openrouter", key_name="t-1", manager=manager, db=db)

    assert "tenant_default_openrouter_default_production" in keys
    assert "tenant_default_openrouter_t-1_production" not in keys


def test_404_when_nothing_matches():
    manager, _saved = _manager({})
    db = _db(with_setting=False)

    try:
        _delete(manager=manager, db=db)
        raise AssertionError("expected HTTPException 404")
    except HTTPException as e:
        assert e.status_code == 404


def test_db_failure_still_removes_file_rows():
    """DB is a sync target — its failure must not block the file deletion."""
    keys = {"tenant_default_openai_default_production": object()}
    manager, saved = _manager(keys)
    db = _db(with_setting=True)
    db.delete.side_effect = RuntimeError("db down")

    result = _delete(manager=manager, db=db)

    assert keys == {}
    assert saved["saved"] is True
    assert result.data["removed"] == ["tenant_default_openai_default_production"]
