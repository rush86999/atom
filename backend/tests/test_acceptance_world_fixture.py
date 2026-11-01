"""The shared acceptance world enforces FKs and exposes effects/faults."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from tests.acceptance.fixtures import world  # noqa: F401 — fixture re-export


def test_foreign_keys_are_enforced(world):
    from core.models import HITLAction

    world.session.add(HITLAction(
        id="hitl-fk", tenant_id="missing-tenant", agent_id=world.agent_id,
        action_type="send", platform="email", params={}, status="pending",
    ))
    with pytest.raises(IntegrityError):
        world.session.commit()
    world.session.rollback()


def test_effect_ledger_counts_attempts(world):
    assert world.ledger.count() == 0
    world.ledger.record("send", to="owner@example.invalid")
    world.ledger.record("send", to="owner@example.invalid")
    world.ledger.record("render", artifact="docx")
    assert world.ledger.count("send") == 2
    assert world.ledger.count() == 3


def test_fault_injection_is_explicit(world):
    world.faults.check("dispatch")  # not armed: no-op
    world.faults.arm("dispatch")
    with pytest.raises(RuntimeError, match="injected: dispatch"):
        world.faults.check("dispatch")
    world.faults.disarm("dispatch")
    world.faults.check("dispatch")
