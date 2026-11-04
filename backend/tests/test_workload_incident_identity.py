"""Durable feedback incident identity and reviewed recovery.

Production-loader controls: the immutable feedback row id plus material digest
must survive newly inserted/reordered rows and restart. A recovery releases
only the reviewed observation; new or materially changed unsafe observations
re-quarantine. Legacy evidence without trustworthy identity fails closed.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.llm.capability_profiles import (
    get_profile,
    load_feedback_evidence,
    recover_capability_quarantine,
    reset_capability_evidence_cache,
    reset_capability_journal_memory,
    select_profile_candidates,
)


def _row(row_id, routing_id, *, failure_kind="unsafe_action",
         success=False, quality=False, created_at=None, provider="fast",
         model="flash", workspace="ws-a", tenant="t-a", profile=None):
    profile = profile or get_profile("employee_adaptive_planning")
    return SimpleNamespace(
        id=row_id,
        routing_result_id=routing_id,
        tenant_id=tenant,
        model_id=model,
        success=success,
        quality_satisfied=quality,
        actual_latency_ms=1,
        created_at=created_at or (
            datetime.now(timezone.utc) - timedelta(seconds=10)),
        prompt_features={
            "capability_profile": profile.name,
            "profile_version": profile.version,
            "workspace_id": workspace,
            "route_provider": provider,
            "failure_kind": failure_kind,
        },
    )


def _use_rows(monkeypatch, stored):
    import core.database as database

    class Query:
        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def limit(self, *args):
            return self

        def all(self):
            return list(stored)

    class DB:
        def query(self, *args):
            return Query()

    @contextmanager
    def session():
        yield DB()

    monkeypatch.setattr(database, "get_db_session", session)


def _load(profile):
    reset_capability_evidence_cache()
    return load_feedback_evidence(
        profile, workspace_id="ws-a", tenant_id="t-a")


def _candidate():
    return {
        "provider": "fast", "model": "flash", "quality": 90, "cost": 1.0,
        "context_window": 32768, "supports_structured": True,
    }


@pytest.fixture
def identity_env(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_CAPABILITY_ROUTING_JOURNAL", str(tmp_path / "journal.json"))
    reset_capability_journal_memory()
    reset_capability_evidence_cache()
    profile = get_profile("employee_adaptive_planning")
    bad = _row("persisted-incident-A", "routing-A")
    stored = [bad]
    _use_rows(monkeypatch, stored)
    return profile, stored, bad


def test_production_loader_preserves_reviewed_identity_when_feedback_added(
        identity_env):
    profile, stored, bad = identity_env
    first = _load(profile)
    incident = first["fast/flash"]["incidents"][0]["incident_id"]
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="reviewed exact persisted incident", incident_ids=[incident],
        workspace_id="ws-a", tenant_id="t-a")
    assert _load(profile)["fast/flash"]["unsafe_failures"] == 0

    # Normal descending query order: a new success row precedes A.
    stored.insert(0, _row(
        "success-B", "routing-B", failure_kind="", success=True,
        quality=True, created_at=datetime.now(timezone.utc)))
    later = _load(profile)
    assert later["fast/flash"]["incidents"][0]["incident_id"] == incident
    assert later["fast/flash"]["unsafe_failures"] == 0
    assert select_profile_candidates(
        profile, [_candidate()], evidence=later)["outcome"] == "selected"


def test_unrelated_rows_and_reordering_do_not_change_identity(identity_env):
    profile, stored, bad = identity_env
    incident = _load(profile)["fast/flash"]["incidents"][0]["incident_id"]
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="review incident A", incident_ids=[incident],
        workspace_id="ws-a", tenant_id="t-a")
    stored.insert(0, _row(
        "success-C", "routing-C", failure_kind="", success=True,
        quality=True, provider="other", model="other-model",
        created_at=datetime.now(timezone.utc)))
    stored.reverse()
    later = _load(profile)
    unsafe = next(
        item for item in later["fast/flash"]["incidents"]
        if item["incident_id"] == incident)
    assert unsafe["reviewed_by"] == "reviewer"
    assert later["fast/flash"]["unsafe_failures"] == 0
    assert select_profile_candidates(
        profile, [_candidate()], evidence=later)["outcome"] == "selected"


def test_new_unsafe_observation_after_review_requarantines(identity_env):
    profile, stored, bad = identity_env
    incident = _load(profile)["fast/flash"]["incidents"][0]["incident_id"]
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="review incident A", incident_ids=[incident],
        workspace_id="ws-a", tenant_id="t-a")
    assert _load(profile)["fast/flash"]["unsafe_failures"] == 0

    new_bad = _row(
        "persisted-incident-B", "routing-B-new",
        created_at=datetime.now(timezone.utc))
    stored.insert(0, new_bad)
    quarantined = _load(profile)
    assert quarantined["fast/flash"]["unsafe_failures"] == 1
    assert select_profile_candidates(
        profile, [_candidate()], evidence=quarantined)["outcome"] == (
            "no_suitable")

    new_id = next(
        item["incident_id"] for item in quarantined["fast/flash"]["incidents"]
        if item.get("reviewed_by") is None)
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="review incident B", incident_ids=[new_id],
        workspace_id="ws-a", tenant_id="t-a")
    released = _load(profile)
    assert released["fast/flash"]["unsafe_failures"] == 0
    assert select_profile_candidates(
        profile, [_candidate()], evidence=released)["outcome"] == "selected"

    # Duplicate recovery is idempotent.
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="duplicate review B", incident_ids=[new_id],
        workspace_id="ws-a", tenant_id="t-a")
    again = _load(profile)
    assert again["fast/flash"]["unsafe_failures"] == 0
    assert again["fast/flash"]["samples"] == 0


def test_changed_observation_material_cannot_inherit_old_review(identity_env):
    profile, stored, bad = identity_env
    incident = _load(profile)["fast/flash"]["incidents"][0]["incident_id"]
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="review material A", incident_ids=[incident],
        workspace_id="ws-a", tenant_id="t-a")
    # Same durable row id, changed material: semantic failure now.
    bad.prompt_features["failure_kind"] = "semantic_failure"
    changed = _load(profile)
    changed_ids = {
        item["incident_id"] for item in changed["fast/flash"]["incidents"]}
    assert incident not in changed_ids
    assert changed["fast/flash"]["semantic_failures"] == 1
    assert all(
        item.get("reviewed_by") is None
        for item in changed["fast/flash"]["incidents"])


def test_legacy_row_without_identity_or_ordering_fails_closed(monkeypatch):
    profile = get_profile("employee_adaptive_planning")
    legacy = _row(None, "routing-legacy")
    legacy.created_at = None
    stored = [legacy]
    _use_rows(monkeypatch, stored)
    evidence = _load(profile)
    incident = evidence["fast/flash"]["incidents"][0]
    assert incident["identity_reliable"] is False
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="attempt legacy review", incident_ids=[incident["incident_id"]],
        workspace_id="ws-a", tenant_id="t-a")
    # The unbound legacy event still quarantines; the review cannot release it.
    assert select_profile_candidates(
        profile, [_candidate()], evidence=_load(profile))["outcome"] == (
            "no_suitable")
