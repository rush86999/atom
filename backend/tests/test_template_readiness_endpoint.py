"""Readiness endpoint: dependency→connection mapping over real token rows.

Covers ``GET /api/workflow-templates/{id}/readiness`` (the surface the
marketplace page calls). The SQLAlchemy chain is faked at the boundary —
the unit under test is the endpoint's assembly logic, not the ORM.
"""

from types import SimpleNamespace

import pytest

from api import workflow_template_routes as wtr


class _FakeQuery:
    def __init__(self, providers):
        self._providers = providers

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return [(p,) for p in self._providers]


class _FakeDB:
    def __init__(self, providers):
        self._providers = providers

    def query(self, *_cols):
        return _FakeQuery(self._providers)


@pytest.fixture()
def template_manager_monkeypatch(monkeypatch):
    def _install(dependencies):
        manager = SimpleNamespace(
            get_template=lambda tid: (
                SimpleNamespace(template_id=tid, dependencies=dependencies)
                if tid == "template_personal_invoice_chase"
                else None
            )
        )
        monkeypatch.setattr(wtr, "get_template_manager", lambda: manager)

    return _install


async def test_readiness_missing_and_ready_paths(template_manager_monkeypatch):
    template_manager_monkeypatch(["gmail", "slack"])
    user = SimpleNamespace(id="u1", tenant_id=None)

    missing = await wtr.get_template_readiness(
        "template_personal_invoice_chase",
        current_user=user,
        db=_FakeDB(providers=[]),
    )
    assert missing["ready"] is False
    assert missing["missing"] == ["gmail", "slack"]
    assert "/integrations?connect=gmail" in missing["connect_urls"]

    ready = await wtr.get_template_readiness(
        "template_personal_invoice_chase",
        current_user=user,
        db=_FakeDB(providers=["google"]),  # gmail alias
    )
    assert ready["ready"] is False
    assert ready["connected"] == ["gmail"]
    assert ready["missing"] == ["slack"]


async def test_readiness_no_dependencies_is_ready(template_manager_monkeypatch):
    template_manager_monkeypatch([])
    result = await wtr.get_template_readiness(
        "template_personal_invoice_chase",
        current_user=SimpleNamespace(id="u1", tenant_id="t1"),
        db=_FakeDB(providers=[]),
    )
    assert result["ready"] is True


async def test_readiness_404_for_unknown_template(template_manager_monkeypatch):
    from fastapi import HTTPException

    template_manager_monkeypatch(["gmail"])
    with pytest.raises(HTTPException) as exc:
        await wtr.get_template_readiness(
            "template_does_not_exist",
            current_user=SimpleNamespace(id="u1", tenant_id=None),
            db=_FakeDB(providers=[]),
        )
    assert exc.value.status_code == 404
