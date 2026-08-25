"""Wiring contract: central config resolvers read through runtime_settings.

Each case seeds a ``runtime_settings`` DB row (the UI-admin path) and
asserts the subsystem's config accessor observes it. Env is left unset
so resolution order env > db > default lands on the DB leg. This is the
regression net for "env vars as UI admin settings": if a module's
resolver stops consulting the layer, its case goes red.
"""
from __future__ import annotations

from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _clean_cache():
    import core.runtime_settings as rs

    rs.invalidate_settings_cache()
    yield
    rs.invalidate_settings_cache()


@pytest.fixture(autouse=True)
def _strip_catalog_env(monkeypatch):
    """Remove every cataloged var from the process env so resolution lands
    on the DB leg (the dev environment exports several of these)."""
    import os

    from core.settings_catalog import SETTING_CATALOG

    for spec in SETTING_CATALOG:
        monkeypatch.delenv(spec.key, raising=False)
    yield


@pytest.fixture
def seed(monkeypatch) -> Iterator[object]:
    """Yield a callable that stores a setting row and routes the resolver's
    lazy ``get_db_session`` import at the test session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import core.database as database
    from core.database import Base
    from core.models import RuntimeSetting

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[RuntimeSetting.__table__])
    session = sessionmaker(bind=engine)()

    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(database, "get_db_session", lambda: _Ctx())

    def _seed(key: str, value) -> None:
        row = RuntimeSetting(key=key, value_json=value)
        session.add(row)
        session.commit()
        import core.runtime_settings as rs

        rs.invalidate_settings_cache()

    yield _seed
    session.close()


# ============================================================================
# Batch 1 — helper-seam modules (env read at call time)
# ============================================================================


def test_sandbox_egress_via_db(seed) -> None:
    from core.sandbox_config import is_sandbox_egress_enabled

    assert is_sandbox_egress_enabled() is False  # default off
    seed("ATOM_SANDBOX_EGRESS_ENABLED", True)
    assert is_sandbox_egress_enabled() is True


def test_sandbox_max_tool_calls_via_db(seed) -> None:
    from core.sandbox_config import get_sandbox_max_tool_calls

    seed("ATOM_SANDBOX_MAX_TOOL_CALLS", 55)
    assert get_sandbox_max_tool_calls() == 55


def test_radio_inbox_cap_via_db(seed) -> None:
    from core.agent_radio.radio_config import inbox_cap

    seed("ATOM_RADIO_INBOX_CAP", 3)
    assert inbox_cap() == 3


def test_radio_master_switch_via_db(seed) -> None:
    from core.agent_radio.radio_config import radio_enabled

    seed("ATOM_RADIO_ENABLED", False)
    assert radio_enabled() is False


def test_fleet_force_enforce_via_db(seed) -> None:
    from core.fleet_routing_config import fleet_routing_force_enforce

    seed("ATOM_FLEET_ROUTING_FORCE_ENFORCE", True)
    assert fleet_routing_force_enforce() is True


def test_knowledge_vfs_via_db(seed) -> None:
    from core.knowledge_vfs_config import knowledge_vfs_enabled

    seed("ATOM_KNOWLEDGE_VFS_ENABLED", False)
    assert knowledge_vfs_enabled() is False


def test_trust_calibration_gateway_knob_via_db(seed) -> None:
    from core.trust_calibration.gateway import _env_float

    seed("ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS", 7)
    assert _env_float("ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS", 30.0) == pytest.approx(7.0)


def test_trust_calibration_automation_mode_via_db(seed) -> None:
    from core.trust_calibration.automation import _env_str

    seed("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "notify")
    assert _env_str("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "off") == "notify"


def test_reviewer_loop_via_db(seed) -> None:
    from core.orchestration.reviewer_loop import reviewer_loop_enabled

    seed("ATOM_REVIEWER_LOOP_ENABLED", True)
    assert reviewer_loop_enabled() is True


def test_contribution_credit_via_db(seed) -> None:
    from core.contribution_credit import contribution_credit_enabled

    seed("ATOM_CONTRIBUTION_CREDIT_ENABLED", True)
    assert contribution_credit_enabled() is True


# ============================================================================
# Batch 2/3 — formerly import-time-constant modules now resolve at call time
# ============================================================================


def test_stage_router_enabled_via_db(seed) -> None:
    from core.llm.stage_router import stage_router_enabled

    seed("ATOM_STAGE_ROUTING_ENABLED", False)
    assert stage_router_enabled() is False


def test_gateway_enabled_and_default_tokens_via_db(seed) -> None:
    from core.llm.gateway.gateway_service import default_max_tokens, gateway_enabled

    seed("ATOM_GATEWAY_ENABLED", False)
    seed("ATOM_GATEWAY_DEFAULT_MAX_TOKENS", 7777)
    assert gateway_enabled() is False
    assert default_max_tokens() == 7777


def test_gateway_log_bodies_via_db(seed) -> None:
    from core.llm.gateway.request_logger import log_bodies

    seed("ATOM_GATEWAY_LOG_BODIES", True)
    assert log_bodies() is True


def test_turn_fact_extraction_via_db(seed) -> None:
    from core.turn_fact_extractor import extraction_enabled, max_per_turn

    seed("TURN_FACT_EXTRACTION_ENABLED", False)
    seed("TURN_FACT_MAX_PER_TURN", 9)
    assert extraction_enabled() is False
    assert max_per_turn() == 9


def test_doc_freshness_filter_via_db(seed) -> None:
    from core.doc_freshness_service import freshness_filter_enabled

    seed("ATOM_FRESHNESS_FILTER_ENABLED", False)
    assert freshness_filter_enabled() is False


def test_memory_consolidator_llm_review_via_db(seed) -> None:
    from core.memory_consolidator import llm_review_enabled

    seed("ATOM_MEMORY_CONSOLIDATION_LLM", True)
    assert llm_review_enabled() is True
