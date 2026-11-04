"""Capability-aware BYOK selection: quality before cost, Flash first-class.

These are controlled-candidate tests for the pure workload selector and the
existing LLMService/pinned-call forwarding. No provider call, credential,
download or spend occurs.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("TESTING", "1")

from core.llm.capability_profiles import (
    escalation_candidate,
    get_profile,
    parse_evidence_rows,
    pin_decision,
    record_capability_decision,
    reset_capability_evidence_cache,
    reset_capability_journal_memory,
    resolve_capability_profile,
    select_profile_candidates,
)


def _candidate(provider, model, quality, cost, *, context=32768,
               structured=True, tools=True):
    return {
        "provider": provider, "model": model, "quality": quality,
        "cost": cost, "context_window": context,
        "supports_structured": structured, "supports_tools": tools,
    }


def _evidence(successes, samples, *, retries=0, unsafe=0, kind="",
              profile=None, version=None, workspace=None):
    profile = profile or get_profile("employee_adaptive_planning")
    return {
        f"{profile.name}": {
            "samples": samples,
            "successes": successes,
            "quality_successes": successes,
            "semantic_failures": 1 if kind in (
                "semantic_failure", "invented_fact",
                "invalid_plan_reference", "wrong_field_mapping") else 0,
            "unsafe_failures": unsafe,
            "retries": retries,
            "latency_ms": 1000,
            "last_failure_kind": kind,
            "profile": profile.name,
            "profile_version": version or profile.version,
            "workspace_id": workspace or "ws-a",
            "tenant_id": "t-a",
        }
    }


def _route_evidence(provider, model, **kwargs):
    profile = get_profile("employee_adaptive_planning")
    return {f"{provider}/{model}": _evidence(profile=profile, **kwargs)[profile.name]}


def test_flash_like_cheap_candidate_beats_equivalent_expensive_candidate():
    profile = get_profile("employee_adaptive_planning")
    selection = select_profile_candidates(
        profile,
        [
            _candidate("frontier", "expensive", 90, 12.0),
            _candidate("fast", "flash", 90, 1.0),
        ])
    assert selection["outcome"] == "selected"
    assert (selection["ranked"][0]["provider"],
            selection["ranked"][0]["model"]) == ("fast", "flash")


def test_complex_profile_keeps_qualified_flash_eligible():
    profile = get_profile("employee_adaptive_planning")
    selection = select_profile_candidates(
        profile,
        [
            _candidate("frontier", "expensive", 99, 20.0),
            _candidate("fast", "flash", 88, 2.0),
        ])
    assert [c["model"] for c in selection["ranked"]] == ["flash", "expensive"]
    assert selection["ranked"][0]["evidence_state"] == "prior"


def test_measured_failure_excludes_flash_and_escalates_once():
    profile = get_profile("employee_adaptive_planning")
    evidence = {
        **_route_evidence(
            "fast", "flash", successes=1, samples=6, retries=3,
            kind="semantic_failure"),
        **_route_evidence(
            "second", "flash-2", successes=10, samples=10),
    }
    selection = select_profile_candidates(
        profile,
        [
            _candidate("fast", "flash", 92, 1.0),
            _candidate("second", "flash-2", 86, 2.0),
        ],
        evidence=evidence)
    assert selection["outcome"] == "selected"
    assert [c["model"] for c in selection["ranked"]] == ["flash-2"]
    assert any(
        item["route"] == "fast/flash"
        and "measured_failure_rate" in item["reasons"]
        for item in selection["excluded"])
    escalated = escalation_candidate(
        profile, selection["ranked"], ("fast", "flash"))
    assert escalated is None, "failed pair must not be re-selected"
    # A failure on the eligible second route has no further eligible
    # escalation in this bounded set.
    assert escalation_candidate(
        profile, selection["ranked"], ("second", "flash-2")) is None


def test_expensive_model_with_measured_failure_is_excluded_too():
    profile = get_profile("employee_adaptive_planning")
    evidence = _route_evidence(
        "frontier", "expensive", successes=0, samples=5,
        kind="invented_fact")
    selection = select_profile_candidates(
        profile,
        [_candidate("frontier", "expensive", 99, 50.0)],
        evidence=evidence)
    assert selection["outcome"] == "no_suitable"
    assert selection["excluded"][0]["reasons"] == [
        "measured_failure_rate"]


def test_no_eligible_candidate_is_explicit_not_relaxed():
    profile = get_profile("employee_adaptive_planning")
    selection = select_profile_candidates(
        profile,
        [_candidate("cheap", "weak", 60, 0.01)])
    assert selection["outcome"] == "no_suitable"
    assert selection["ranked"] == []
    assert selection["excluded"][0]["reasons"] == ["below_quality_prior"]


def test_context_window_mismatch_is_ineligible():
    profile = get_profile("employee_adaptive_planning")
    selection = select_profile_candidates(
        profile,
        [_candidate("fast", "small-window", 95, 0.1, context=4096)])
    assert selection["outcome"] == "no_suitable"
    assert "context_too_small" in selection["excluded"][0]["reasons"]


def test_evidence_scope_and_version_do_not_poison_other_workspace():
    profile = get_profile("employee_adaptive_planning")
    rows = [{
        "tenant_id": "t-a",
        "model_id": "fast/flash",
        "success": False,
        "quality_satisfied": False,
        "prompt_features": {
            "capability_profile": profile.name,
            "profile_version": profile.version,
            "workspace_id": "ws-other",
            "failure_kind": "invented_fact",
        },
    }, {
        "tenant_id": "t-a",
        "model_id": "fast/flash",
        "success": True,
        "quality_satisfied": True,
        "prompt_features": {
            "capability_profile": profile.name,
            "profile_version": "old-version",
            "workspace_id": "ws-a",
            "failure_kind": "invented_fact",
        },
    }]
    evidence = parse_evidence_rows(
        rows, profile, workspace_id="ws-a", tenant_id="t-a")
    assert evidence == {}


def test_measured_success_does_not_exclude_efficient_route():
    profile = get_profile("extraction")
    evidence = _route_evidence(
        "fast", "flash", successes=20, samples=20)
    selection = select_profile_candidates(
        profile,
        [
            _candidate("fast", "flash", 85, 0.2),
            _candidate("slow", "expensive", 90, 5.0),
        ],
        evidence=evidence)
    assert selection["outcome"] == "selected"
    assert selection["ranked"][0]["model"] == "flash"
    assert selection["ranked"][0]["evidence_state"] == "measured"


def test_alignment_failure_does_not_ban_extraction_profile():
    alignment = get_profile("alignment_judging")
    extraction = get_profile("extraction")
    rows = [{
        "tenant_id": "t-a",
        "model_id": "fast/flash",
        "success": False,
        "quality_satisfied": False,
        "prompt_features": {
            "capability_profile": alignment.name,
            "profile_version": alignment.version,
            "workspace_id": "ws-a",
            "route_provider": "fast",
            "failure_kind": "invented_fact",
        },
    }]
    assert parse_evidence_rows(
        rows, alignment, workspace_id="ws-a") != {}
    assert parse_evidence_rows(
        rows, extraction, workspace_id="ws-a") == {}


def test_strict_pin_is_exact_or_failed_no_escape():
    profile = get_profile("employee_adaptive_planning")
    good = pin_decision(
        profile, "fast", "flash", quality=90, context_window=32768)
    assert good["eligible"] is True
    assert good["route"] == ("fast", "flash")
    bad = pin_decision(
        profile, "local", "llama3.1:8b", quality=70,
        context_window=8192)
    assert bad["eligible"] is False
    assert bad["route"] == ("local", "llama3.1:8b")
    assert "below_quality_prior" in bad["reasons"]


def test_profile_resolution_uses_server_label_not_model_name():
    assert resolve_capability_profile(
        None, "planning", "employee adaptation").name == (
            "employee_adaptive_planning")
    assert resolve_capability_profile(
        None, "planning", "employee work proposal").name == (
            "employee_evidence_selection")
    # Ordinary planning stays the legacy best-effort profile, not an
    # expensive frontier default.
    assert resolve_capability_profile(None, "planning", "canvas edit") is None
    with pytest.raises(ValueError):
        resolve_capability_profile("not-a-profile", "planning")


def test_decision_journal_persists_across_memory_reset(tmp_path, monkeypatch):
    path = tmp_path / "capability-journal.json"
    monkeypatch.setenv("ATOM_CAPABILITY_ROUTING_JOURNAL", str(path))
    reset_capability_journal_memory()
    entry = record_capability_decision({
        "event": "selection",
        "profile": {"name": "employee_adaptive_planning", "version": "v1"},
        "outcome": "selected",
        "selected": [{"provider": "fast", "model": "flash"}],
    })
    assert path.is_file()
    reset_capability_journal_memory()
    from core.llm.capability_profiles import capability_decisions

    loaded = capability_decisions(5)
    assert loaded and loaded[-1]["digest"] == entry["digest"]


# ---------------------------------------------------------------------------
# Existing service/pin forwarding
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_llm_service_forwards_capability_profile_to_handler():
    from unittest.mock import AsyncMock, MagicMock

    from core.llm_service import LLMService

    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(return_value="OK")
    svc = LLMService.__new__(LLMService)
    svc._get_handler = MagicMock(return_value=handler)
    svc.continuous_learning = None
    out = await svc.generate_structured_response(
        prompt="p", response_model=object,
        task_type="planning",
        capability_profile="employee_adaptive_planning",
        capability_preference="economy",
    )
    assert out == "OK"
    kwargs = handler.generate_structured_response.await_args.kwargs
    assert kwargs["capability_profile"] == "employee_adaptive_planning"
    assert kwargs["capability_preference"] == "economy"
    assert kwargs["task_type"] == "planning"


@pytest.mark.asyncio
async def test_pinned_call_adds_profile_from_server_label():
    from unittest.mock import AsyncMock, MagicMock

    from core.llm.pinned_planning import pinned_structured_call

    service = MagicMock()
    service.generate_structured_response = AsyncMock(return_value="OK")
    await pinned_structured_call(
        service, prompt="p", response_model=object,
        system_instruction="json", log_label="employee adaptation",
        task_type="planning", disable_reasoning=False)
    kwargs = service.generate_structured_response.await_args.kwargs
    assert kwargs["capability_profile"] == "employee_adaptive_planning"


def test_production_bpc_ranks_economical_flash_over_expensive_equal(monkeypatch):
    """Controlled BPC pool: equal task evidence, Flash is cheaper and wins."""
    from unittest.mock import MagicMock, patch

    from core.llm.byok_handler import QueryComplexity
    from tests.test_bpc_frontier_reserved_gate import _handler_cm

    fetcher = MagicMock()
    fetcher.pricing_cache = {
        "flash": {
            "litellm_provider": "fast", "input_cost_per_token": 1e-7,
            "output_cost_per_token": 1e-7, "max_input_tokens": 32768,
            "supports_tools": True, "supports_structured": True,
        },
        "expensive": {
            "litellm_provider": "frontier", "input_cost_per_token": 2e-6,
            "output_cost_per_token": 2e-6, "max_input_tokens": 32768,
            "supports_tools": True, "supports_structured": True,
        },
    }
    qualities = {"flash": 90, "expensive": 90}
    with _handler_cm() as handler:
        handler.provider_policy = None
        handler.clients = {"fast": MagicMock(), "frontier": MagicMock()}
        handler.env_key_providers = {"fast", "frontier"}
        handler.excluded_models = set()
        handler.cache_router.calculate_effective_cost = MagicMock(
            side_effect=lambda model, provider, estimated_tokens,
            turn_index=0, **kw: fetcher.pricing_cache[model][
                "input_cost_per_token"] * estimated_tokens)
        with patch(
                "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                return_value=fetcher), patch(
                "core.llm.byok_handler.get_quality_score",
                side_effect=lambda model: qualities.get(model, 0)):
            ranked = list(handler.get_ranked_providers(
                QueryComplexity.MODERATE, None, True, "free", False,
                requires_tools=True, requires_structured=True,
                estimated_tokens=3000,
                capability_profile="employee_adaptive_planning"))
    assert ranked, "controlled pool must produce a route"
    assert ranked[0] == ("fast", "flash"), ranked


def test_production_bpc_no_suitable_returns_empty_and_journals(
        monkeypatch, tmp_path):
    from unittest.mock import MagicMock, patch

    from core.llm.byok_handler import QueryComplexity
    from tests.test_bpc_frontier_reserved_gate import _handler_cm

    journal = tmp_path / "capability.json"
    monkeypatch.setenv("ATOM_CAPABILITY_ROUTING_JOURNAL", str(journal))
    fetcher = MagicMock()
    fetcher.pricing_cache = {
        "weak": {
            "litellm_provider": "fast", "input_cost_per_token": 1e-7,
            "output_cost_per_token": 1e-7, "max_input_tokens": 32768,
            "supports_tools": True, "supports_structured": True,
        },
    }
    with _handler_cm() as handler:
        handler.provider_policy = None
        handler.clients = {"fast": MagicMock()}
        handler.env_key_providers = {"fast"}
        handler.excluded_models = set()
        handler.cache_router.calculate_effective_cost = MagicMock(
            return_value=1e-4)
        with patch(
                "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                return_value=fetcher), patch(
                "core.llm.byok_handler.get_quality_score",
                return_value=81):
            ranked = list(handler.get_ranked_providers(
                QueryComplexity.MODERATE, None, True, "free", False,
                requires_tools=True, requires_structured=True,
                estimated_tokens=3000,
                capability_profile="employee_adaptive_planning"))
    assert ranked == []
    assert journal.is_file()
    entries = json.loads(journal.read_text())
    assert any(
        item.get("event") == "selection"
        and item.get("outcome") == "no_suitable"
        for item in entries)


def test_bounded_escalation_selects_a_better_eligible_candidate_once():
    profile = get_profile("employee_adaptive_planning")
    ranked = [
        {"provider": "fast", "model": "flash", "quality": 85},
        {"provider": "better", "model": "flash-2", "quality": 92},
        {"provider": "other", "model": "flash-3", "quality": 90},
    ]
    escalated = escalation_candidate(
        profile, ranked, ("fast", "flash"))
    assert escalated["model"] == "flash-2"
    # No candidate below the failed route is actually better; the bounded
    # escalation stops instead of cycling to a weaker pair.
    assert escalation_candidate(
        profile, ranked, ("better", "flash-2")) is None
    assert escalation_candidate(
        profile, ranked, ("missing", "route")) is None


def test_no_escalation_when_profile_does_not_allow_it():
    profile = get_profile("extraction")
    ranked = [
        {"provider": "fast", "model": "flash", "quality": 85},
        {"provider": "better", "model": "flash-2", "quality": 99},
    ]
    assert escalation_candidate(
        profile, ranked, ("fast", "flash")) is None


def test_profile_floor_keeps_capable_flash_eligible_on_complex_call():
    """A capable Flash route must not be excluded by a generic complexity
    floor when the declared workload profile says the task is in scope."""
    from unittest.mock import MagicMock, patch

    from core.llm.byok_handler import QueryComplexity
    from tests.test_bpc_frontier_reserved_gate import _handler_cm

    fetcher = MagicMock()
    fetcher.pricing_cache = {
        "flash": {
            "litellm_provider": "fast", "input_cost_per_token": 1e-7,
            "output_cost_per_token": 1e-7, "max_input_tokens": 32768,
            "supports_tools": True, "supports_structured": True,
        },
    }
    with _handler_cm() as handler:
        handler.provider_policy = None
        handler.clients = {"fast": MagicMock()}
        handler.env_key_providers = {"fast"}
        handler.excluded_models = set()
        handler.cache_router.calculate_effective_cost = MagicMock(
            return_value=1e-4)
        with patch(
                "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                return_value=fetcher), patch(
                "core.llm.byok_handler.get_quality_score",
                return_value=85):
            ranked = list(handler.get_ranked_providers(
                QueryComplexity.COMPLEX, None, True, "free", False,
                requires_tools=True, requires_structured=True,
                estimated_tokens=3000,
                capability_profile="employee_adaptive_planning"))
    assert ranked == [("fast", "flash")], ranked


def test_explicit_quality_preference_can_choose_stronger_eligible_route():
    profile = get_profile("document_drafting")
    selection = select_profile_candidates(
        profile,
        [
            _candidate("fast", "flash", 85, 0.2),
            _candidate("slow", "deluxe", 95, 4.0),
        ],
        preference="quality")
    assert selection["outcome"] == "selected"
    assert selection["ranked"][0]["model"] == "deluxe"
    economy = select_profile_candidates(
        profile,
        [
            _candidate("fast", "flash", 85, 0.2),
            _candidate("slow", "deluxe", 95, 4.0),
        ],
        preference="economy")
    assert economy["ranked"][0]["model"] == "flash"


# ---------------------------------------------------------------------------
# Verifier boundary repairs
# ---------------------------------------------------------------------------
def _scoped_rows(profile, *, quality=True, workspace="ws-a", failure="",
                 created_at=None):
    return [{
        "tenant_id": "t-a", "model_id": "flash", "success": True,
        "quality_satisfied": quality,
        "created_at": created_at or (
            datetime.now(timezone.utc) - timedelta(seconds=10)),
        "prompt_features": {
            "capability_profile": profile.name,
            "profile_version": profile.version,
            "workspace_id": workspace,
            "route_provider": "fast",
            "failure_kind": failure,
        },
    } for _ in range(6)]


def _flash_candidate():
    return _candidate("fast", "flash", 90, 1.0)


def test_semantic_transport_success_is_not_satisfactory():
    profile = get_profile("employee_adaptive_planning")
    evidence = parse_evidence_rows(
        _scoped_rows(profile, quality=False), profile,
        workspace_id="ws-a", tenant_id="t-a")
    result = select_profile_candidates(
        profile, [_flash_candidate()], evidence=evidence)
    assert result["outcome"] == "no_suitable", result


def test_missing_workspace_evidence_is_not_assigned_to_reader():
    profile = get_profile("employee_adaptive_planning")
    assert parse_evidence_rows(
        _scoped_rows(profile, workspace=""), profile,
        workspace_id="ws-a", tenant_id="t-a") == {}


def test_provider_missing_evidence_is_not_transferred_across_providers():
    profile = get_profile("employee_adaptive_planning")
    rows = _scoped_rows(profile)
    for row in rows:
        row["prompt_features"].pop("route_provider")
    assert parse_evidence_rows(
        rows, profile, workspace_id="ws-a", tenant_id="t-a") == {}


def test_single_unsafe_outcome_quarantines_until_reviewed_recovery(
        tmp_path, monkeypatch):
    from core.llm.capability_profiles import (
        apply_capability_recoveries, capability_decisions,
        recover_capability_quarantine, reset_capability_journal_memory,
    )

    journal = tmp_path / "decisions.json"
    monkeypatch.setenv("ATOM_CAPABILITY_JOURNAL", str(journal))
    monkeypatch.setenv("ATOM_CAPABILITY_ROUTING_JOURNAL", str(journal))
    reset_capability_journal_memory()
    profile = get_profile("employee_adaptive_planning")
    rows = _scoped_rows(profile, quality=False, failure="unsafe_action")[:1]
    evidence = parse_evidence_rows(
        rows, profile, workspace_id="ws-a", tenant_id="t-a")
    blocked = select_profile_candidates(
        profile, [_flash_candidate()], evidence=evidence)
    assert blocked["outcome"] == "no_suitable"
    assert blocked["excluded"][0]["reasons"] == ["measured_unsafe_action"]

    # A different workload is not quarantined by this safety evidence.
    extraction = get_profile("extraction")
    other = select_profile_candidates(
        extraction, [_flash_candidate()], evidence={})
    assert other["outcome"] == "selected"

    incident_id = evidence["fast/flash"]["incidents"][0]["incident_id"]
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="safety-reviewer",
        reason="reviewed fixture recovery", incident_ids=[incident_id],
        workspace_id="ws-a", tenant_id="t-a")
    recovered = apply_capability_recoveries(
        profile, parse_evidence_rows(
            rows, profile, workspace_id="ws-a", tenant_id="t-a"),
        workspace_id="ws-a", tenant_id="t-a")
    allowed = select_profile_candidates(
        profile, [_flash_candidate()], evidence=recovered)
    assert allowed["outcome"] == "selected", allowed
    assert capability_decisions(
        10, workspace_id="ws-a", tenant_id="t-a")

    # Recovery survives the in-memory reset (read from the world-owned file).
    reset_capability_journal_memory()
    again = apply_capability_recoveries(
        profile, parse_evidence_rows(
            rows, profile, workspace_id="ws-a", tenant_id="t-a"),
        workspace_id="ws-a", tenant_id="t-a")
    assert select_profile_candidates(
        profile, [_flash_candidate()], evidence=again)["outcome"] == (
            "selected")


@pytest.mark.asyncio
async def test_strict_profile_pin_does_not_escape_through_wrapper():
    from pydantic import BaseModel

    from core.llm.byok_handler import NoSuitableConfiguredModelError
    from core.llm.pinned_planning import pinned_structured_call

    profile = get_profile("employee_adaptive_planning")

    class Reply(BaseModel):
        decision: str

    calls = []

    class LLM:
        async def generate_structured_response(self, **kwargs):
            calls.append(kwargs.get("provider_model"))
            if kwargs.get("provider_model"):
                raise NoSuitableConfiguredModelError(
                    profile, {"selection_reason": "controlled rejected pin"})
            return Reply(decision="returned_by_other_model")

    result = await pinned_structured_call(
        LLM(), prompt="Choose next work", response_model=Reply,
        system_instruction="Controlled contract",
        log_label="employee adaptation",
        call_kwargs={"provider_model": ("local", "failed")},
        capability_profile=profile.name)
    assert calls == [("local", "failed")], calls
    assert result is None


def test_decision_history_requires_exact_workspace_and_tenant(
        tmp_path, monkeypatch):
    from core.llm.capability_profiles import (
        capability_decisions, record_capability_decision,
        reset_capability_journal_memory,
    )

    monkeypatch.setenv(
        "ATOM_CAPABILITY_ROUTING_JOURNAL", str(tmp_path / "j.json"))
    reset_capability_journal_memory()
    record_capability_decision({
        "event": "selection", "workspace_id": "ws-a", "tenant_id": "t-a",
        "route": ["fast", "flash"]})
    record_capability_decision({
        "event": "selection", "workspace_id": "ws-b", "tenant_id": "t-b",
        "route": ["private", "model"]})
    scoped = capability_decisions(
        10, workspace_id="ws-a", tenant_id="t-a")
    assert len(scoped) == 1
    assert scoped[0]["workspace_id"] == "ws-a"


def test_journal_path_is_world_owned_when_configured(tmp_path, monkeypatch):
    from core.llm.capability_profiles import (
        _journal_path, record_capability_decision,
        reset_capability_journal_memory,
    )

    monkeypatch.delenv("ATOM_CAPABILITY_ROUTING_JOURNAL", raising=False)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "world-data"))
    expected = tmp_path / "world-data" / "llm_capability_routing.json"
    assert _journal_path() == expected
    monkeypatch.delenv("TESTING", raising=False)
    reset_capability_journal_memory()
    record_capability_decision({"event": "selection"})
    assert expected.is_file()


@pytest.mark.asyncio
async def test_provider_policy_route_hides_other_scope_decisions(monkeypatch):
    from types import SimpleNamespace

    from api.byok_routes import get_provider_policy
    import core.llm.capability_profiles as profiles
    import core.llm.provider_policy as provider_policy

    monkeypatch.setattr(
        provider_policy, "resolve_provider_policy",
        lambda: SimpleNamespace(public_dict=lambda: {}))
    monkeypatch.setattr(
        profiles, "capability_decisions",
        lambda limit: [{
            "workspace_id": "ws-b", "tenant_id": "t-b",
            "route": ["private-provider", "private-model"]}])
    response = await get_provider_policy(
        current_user=SimpleNamespace(
            id="viewer-a", workspace_id="ws-a", tenant_id="t-a",
            role="viewer"),
        byok_manager=SimpleNamespace(providers={}))
    assert response.data["capability_routing"]["recent_decisions"] == []


def test_feedback_carries_profile_metadata_for_persistence():
    from types import SimpleNamespace

    from core.learning_llm_router import LearningBasedRouter

    quality = SimpleNamespace(
        success=True, quality_satisfied=True, quality_score=1.0)
    feedback = LearningBasedRouter.build_feedback(
        routing_result_id="r1", tenant_id="t-a", model_id="flash",
        task_type="planning", quality=quality, provider_id="fast",
        capability_profile="employee_adaptive_planning",
        capability_profile_version="2026-11-04.1", workspace_id="ws-a")
    assert feedback.capability_profile == "employee_adaptive_planning"
    assert feedback.capability_profile_version == "2026-11-04.1"
    assert feedback.workspace_id == "ws-a"


def test_semantic_failure_overrides_transport_and_quality_flags():
    profile = get_profile("employee_adaptive_planning")
    rows = _scoped_rows(
        profile, quality=True, failure="semantic_failure")
    evidence = parse_evidence_rows(
        rows, profile, workspace_id="ws-a", tenant_id="t-a")
    result = select_profile_candidates(
        profile, [_flash_candidate()], evidence=evidence)
    assert result["outcome"] == "no_suitable", result


def test_old_recovery_does_not_release_a_new_unsafe_incident(
        tmp_path, monkeypatch):
    from core.llm.capability_profiles import (
        apply_capability_recoveries, recover_capability_quarantine,
        reset_capability_journal_memory,
    )

    journal = tmp_path / "epoch.json"
    monkeypatch.setenv("ATOM_CAPABILITY_ROUTING_JOURNAL", str(journal))
    reset_capability_journal_memory()
    profile = get_profile("employee_adaptive_planning")
    # A review from an earlier epoch, bound to an incident that is not the
    # new one.
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="reviewed an earlier incident", incident_ids=["old-incident"],
        workspace_id="ws-a", tenant_id="t-a")
    rows = _scoped_rows(
        profile, quality=False, failure="unsafe_action",
        created_at=datetime.now(timezone.utc))[:1]
    evidence = parse_evidence_rows(
        rows, profile, workspace_id="ws-a", tenant_id="t-a")
    incident_id = evidence["fast/flash"]["incidents"][0]["incident_id"]
    recovered = apply_capability_recoveries(
        profile, evidence, workspace_id="ws-a", tenant_id="t-a")
    assert select_profile_candidates(
        profile, [_flash_candidate()], evidence=recovered)["outcome"] == (
            "no_suitable")

    # A review of the new incident releases it; duplicate review stays
    # idempotent.
    recover_capability_quarantine(
        profile, "fast", "flash", reviewed_by="reviewer",
        reason="reviewed the new incident", incident_ids=[incident_id],
        workspace_id="ws-a", tenant_id="t-a")
    recovered = apply_capability_recoveries(
        profile, evidence, workspace_id="ws-a", tenant_id="t-a")
    assert select_profile_candidates(
        profile, [_flash_candidate()], evidence=recovered)["outcome"] == (
            "selected")
    again = apply_capability_recoveries(
        profile, recovered, workspace_id="ws-a", tenant_id="t-a")
    assert select_profile_candidates(
        profile, [_flash_candidate()], evidence=again)["outcome"] == (
            "selected")
    assert again["fast/flash"]["samples"] == 0


@pytest.mark.asyncio
async def test_employee_proposal_and_pin_attribution_are_business_safe():
    from pydantic import BaseModel

    from core.employee_proposal import (
        build_employee_context, propose_employee_work,
    )
    from core.llm.byok_handler import NoSuitableConfiguredModelError
    from core.llm.model_provenance import get_route_attribution
    from core.llm.pinned_planning import pinned_structured_call

    context = build_employee_context(
        objective="Read evidence",
        sources=[{
            "kind": "document", "representation": "document_text",
            "resource_id": "doc-1", "file_name": "note.txt",
        }])
    deterministic = await propose_employee_work(context, llm_service=None)
    assert deterministic["routing"]["mode"] == "deterministic"
    assert "provider" not in deterministic["routing"]

    class Reply(BaseModel):
        decision: str

    class GoodLLM:
        async def generate_structured_response(self, **_kwargs):
            return Reply(decision="read")

    await pinned_structured_call(
        GoodLLM(), prompt="p", response_model=Reply,
        system_instruction="json", log_label="employee work proposal",
        call_kwargs={"provider_model": ("fast", "flash")},
        capability_profile="employee_evidence_selection")
    attribution = get_route_attribution()
    assert attribution["mode"] == "pinned"
    assert attribution["requested_route"] == {
        "provider": "fast", "model": "flash"}
    assert attribution["profile"]["name"] == "employee_evidence_selection"
    assert attribution["served_route"] is None

    class BadLLM:
        async def generate_structured_response(self, **_kwargs):
            raise NoSuitableConfiguredModelError(
                get_profile("employee_evidence_selection"),
                {"selection_reason": "controlled no suitable route"})

    result = await pinned_structured_call(
        BadLLM(), prompt="p", response_model=Reply,
        system_instruction="json", log_label="employee work proposal",
        call_kwargs={"provider_model": ("local", "weak")},
        capability_profile="employee_evidence_selection")
    assert result is None
    failure = get_route_attribution()
    assert failure["mode"] == "pinned"
    assert failure["error"]["code"] == "no_suitable_configured_model"
    assert failure["requested_route"] == {
        "provider": "local", "model": "weak"}
    assert "controlled no suitable route" in failure["error"]["detail"]


def test_route_attribution_is_call_local_and_clears_stale_served_state():
    from core.llm.model_provenance import (
        clear_route_attribution, get_route_attribution, set_requested_route,
        set_resolved_model, set_served_route,
    )

    clear_route_attribution()
    set_requested_route("local", "candidate-a")
    set_resolved_model("candidate-a-echo")
    attribution = get_route_attribution()
    assert attribution["requested_route"] == {
        "provider": "local", "model": "candidate-a"}
    assert attribution["served_route"] is None
    assert attribution["resolved_model"] == "candidate-a-echo"

    from core.llm.model_provenance import set_routing_error

    set_routing_error("provider_failure", "earlier candidate excluded")
    set_served_route("local", "candidate-b")
    attribution = get_route_attribution()
    assert attribution["served_route"] == {
        "provider": "local", "model": "candidate-b"}
    assert attribution["error"] is None

    # A fresh boundary cannot inherit the previous call's served route or
    # provider-echoed checkpoint.
    clear_route_attribution()
    attribution = get_route_attribution()
    assert attribution["requested_route"] is None
    assert attribution["served_route"] is None
    assert attribution["resolved_model"] is None


@pytest.mark.asyncio
async def test_strict_pin_no_result_is_explicit_and_not_served():
    from pydantic import BaseModel

    from core.llm.model_provenance import (
        clear_route_attribution, get_route_attribution,
    )
    from core.llm.pinned_planning import pinned_structured_call

    class EmptyLLM:
        async def generate_structured_response(self, **_kwargs):
            return None

    class Reply(BaseModel):
        decision: str

    clear_route_attribution()
    result = await pinned_structured_call(
        EmptyLLM(), prompt="p", response_model=Reply,
        system_instruction="json", log_label="employee work proposal",
        call_kwargs={"provider_model": ("fast", "flash")},
        capability_profile="employee_evidence_selection")
    assert result is None
    attribution = get_route_attribution()
    assert attribution["mode"] == "pinned"
    assert attribution["requested_route"] == {
        "provider": "fast", "model": "flash"}
    assert attribution["served_route"] is None
    assert attribution["error"]["code"] == "provider_failure"
    assert "qualification pin" in attribution["error"]["detail"]


@pytest.mark.asyncio
async def test_successful_unpinned_fallback_clears_prior_pin_failure():
    from pydantic import BaseModel

    from core.llm.byok_handler import NoSuitableConfiguredModelError
    from core.llm.model_provenance import (
        clear_route_attribution, get_route_attribution, set_served_route,
    )
    from core.llm.pinned_planning import pinned_structured_call

    class FallbackLLM:
        def __init__(self):
            self.calls = 0

        async def generate_structured_response(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise NoSuitableConfiguredModelError(
                    get_profile("employee_evidence_selection"),
                    {"selection_reason": "pinned candidate unavailable"})
            set_served_route("fallback", "capable-flash")
            return Reply(decision="read")

    class Reply(BaseModel):
        decision: str

    clear_route_attribution()
    result = await pinned_structured_call(
        FallbackLLM(), prompt="p", response_model=Reply,
        system_instruction="json", log_label="employee work proposal",
        call_kwargs={"provider_model": ("pin", "unavailable")})
    assert result is not None
    attribution = get_route_attribution()
    assert attribution["mode"] == "unpinned_fallback"
    assert attribution["requested_route"] == {
        "provider": "pin", "model": "unavailable"}
    assert attribution["served_route"] == {
        "provider": "fallback", "model": "capable-flash"}
    assert attribution["error"] is None
