"""Round 82 — model provenance for self-evolving harnesses.

Rec #1 (adjudicated): capture the provider-echoed (resolved) model ID alongside
the router-selected (requested) one, detect silent checkpoint bumps under stable
aliases, and expire model-scoped harness patches when drift fires.

Rec #2: model_scope tagging in HarnessEvolutionService.propose_mutation plus
read-time applicability filtering (normalize -> scope match -> drift expiry).

All tests mock-heavy: zero network, zero LLM spend.
"""

import json
import threading

import pytest

from core.llm.model_provenance import (
    DriftEvent,
    ModelDriftDetector,
    clear_resolved_model,
    get_resolved_model,
    normalize_model_family,
    set_resolved_model,
)


# ── contextvar carrier ────────────────────────────────────────────────


def test_resolved_model_contextvar_default_none():
    clear_resolved_model()
    assert get_resolved_model() is None


def test_resolved_model_set_get_clear():
    clear_resolved_model()
    set_resolved_model("gpt-5.4-2026-03")
    assert get_resolved_model() == "gpt-5.4-2026-03"
    clear_resolved_model()
    assert get_resolved_model() is None


# ── family normalization (policy: collapse dates/snapshots, keep variants) ──


@pytest.mark.parametrize(
    "raw,family",
    [
        ("gpt-5.4-2026-03", "gpt-5.4"),
        ("GPT-5.4", "gpt-5.4"),
        ("deepseek-v4-flash-free", "deepseek-v4-flash"),
        ("deepseek-v4-pro", "deepseek-v4-pro"),  # variant tier kept separate
        ("gemini-3.1-flash-lite-preview", "gemini-3.1-flash-lite"),
        ("claude-opus-4-20260219", "claude-opus-4"),
        ("qwen3.6-plus:latest", "qwen3.6-plus"),
        ("gpt-5.4@2026-01-17", "gpt-5.4"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalize_model_family(raw, family):
    assert normalize_model_family(raw) == family


# ── drift detector ────────────────────────────────────────────────────


def _detector(tmp_path):
    return ModelDriftDetector(state_path=tmp_path / "drift_state.json")


def test_drift_baseline_then_change_fires_event(tmp_path):
    det = _detector(tmp_path)
    assert det.observe("openai", "gpt-5.4", "gpt-5.4-2026-01") is None  # baseline
    ev = det.observe("openai", "gpt-5.4", "gpt-5.4-2026-09")  # silent bump
    assert isinstance(ev, DriftEvent)
    assert ev.requested_model == "gpt-5.4"
    assert ev.previous_resolved == "gpt-5.4-2026-01"
    assert ev.new_resolved == "gpt-5.4-2026-09"


def test_drift_none_is_unknown_not_change(tmp_path):
    """Missing echo must NOT clear or clobber the baseline (null-safe)."""
    det = _detector(tmp_path)
    det.observe("openai", "gpt-5.4", "gpt-5.4-2026-01")
    assert det.observe("openai", "gpt-5.4", None) is None
    # baseline survives the unknown gap
    ev = det.observe("openai", "gpt-5.4", "gpt-5.4-2026-09")
    assert ev is not None and ev.previous_resolved == "gpt-5.4-2026-01"


def test_drift_same_value_no_event(tmp_path):
    det = _detector(tmp_path)
    det.observe("openai", "m", "m-snap-1")
    assert det.observe("openai", "m", "m-snap-1") is None


def test_drift_heals_when_provider_rolls_back(tmp_path):
    det = _detector(tmp_path)
    det.observe("openai", "m", "snap-a")
    assert det.is_drifted("openai", "m") is False  # steady baseline
    det.observe("openai", "m", "snap-b")
    assert det.is_drifted("openai", "m") is True  # bump fires
    det.observe("openai", "m", "snap-b")
    assert det.is_drifted("openai", "m") is False  # echo stabilized → healed


def test_drift_state_persists_across_instances(tmp_path):
    p = tmp_path / "drift_state.json"
    det1 = ModelDriftDetector(state_path=p)
    det1.observe("openai", "gpt-5.4", "snap-1")
    det2 = ModelDriftDetector(state_path=p)
    ev = det2.observe("openai", "gpt-5.4", "snap-2")
    assert ev is not None  # baseline loaded from disk


def test_drift_state_file_shape(tmp_path):
    p = tmp_path / "drift_state.json"
    det = ModelDriftDetector(state_path=p)
    det.observe("openai", "gpt-5.4", "snap-1")
    data = json.loads(p.read_text())
    assert "baselines" in data and "openai:gpt-5.4" in data["baselines"]


def test_drift_detector_never_raises_on_bad_state_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    det = ModelDriftDetector(state_path=p)
    assert det.observe("p", "m", "r") is None  # treated as fresh baseline


def test_drift_detection_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_MODEL_DRIFT_DETECTION_ENABLED", "false")
    det = _detector(tmp_path)
    det.observe("openai", "m", "snap-a")
    assert det.observe("openai", "m", "snap-b") is None
    assert det.is_drifted("openai", "m") is False


def test_drift_detector_thread_safety_smoke(tmp_path):
    det = _detector(tmp_path)
    errs = []

    def worker(i):
        try:
            for n in range(50):
                det.observe("prov", f"m{i}", f"snap-{n}")
        except Exception as e:  # pragma: no cover
            errs.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errs == []


# ── integration: _record_outcome_feedback picks up the echo ───────────


def _make_handler():
    from core.llm.byok_handler import BYOKHandler

    return BYOKHandler.__new__(BYOKHandler)


@pytest.mark.asyncio
async def test_record_outcome_feedback_reads_contextvarEcho(monkeypatch, tmp_path):
    """When callers don't pass resolved_model, the contextvar echo is used."""
    import core.llm.byok_handler as bh

    observed = {}

    class FakeDet:
        def observe(self, provider, requested, resolved):
            observed["args"] = (provider, requested, resolved)
            return None

    h = _make_handler()
    monkeypatch.setattr(bh, "_get_drift_detector", lambda: FakeDet())
    clear_resolved_model()
    set_resolved_model("echoed-snapshot-id")
    await h._record_outcome_feedback(
        model="requested-model",
        provider_id="openai",
        task_type=None,
        content="ok",
        finish_reason="stop",
        success=True,
        cost=0.0,
        latency_ms=1.0,
    )
    clear_resolved_model()
    assert observed["args"] == ("openai", "requested-model", "echoed-snapshot-id")


@pytest.mark.asyncio
async def test_record_outcome_feedback_explicit_param_wins(monkeypatch):
    import core.llm.byok_handler as bh

    observed = {}

    class FakeDet:
        def observe(self, provider, requested, resolved):
            observed["resolved"] = resolved

    h = _make_handler()
    monkeypatch.setattr(bh, "_get_drift_detector", lambda: FakeDet())
    clear_resolved_model()
    set_resolved_model("stale-echo")
    await h._record_outcome_feedback(
        model="req",
        provider_id="openai",
        task_type=None,
        content=None,
        finish_reason=None,
        success=True,
        cost=None,
        latency_ms=0.0,
        resolved_model="explicit-echo",
    )
    clear_resolved_model()
    assert observed["resolved"] == "explicit-echo"


@pytest.mark.asyncio
async def test_record_outcome_feedback_survives_detector_crash(monkeypatch):
    import core.llm.byok_handler as bh

    def boom():
        raise RuntimeError("detector down")

    h = _make_handler()
    monkeypatch.setattr(bh, "_get_drift_detector", boom)
    clear_resolved_model()
    await h._record_outcome_feedback(  # must not raise
        model="m", provider_id="p", task_type=None, content=None,
        finish_reason=None, success=True, cost=None, latency_ms=0.0,
    )


# ── rec #2: scoping in propose_mutation + read-time filter ────────────


@pytest.mark.asyncio
async def test_propose_mutation_prompt_patch_is_family_scoped():
    from core.harness_evolution_service import HarnessEvolutionService

    svc = HarnessEvolutionService.__new__(HarnessEvolutionService)
    patch = await svc.propose_mutation({"tool": "unknown", "step_type": "thought"})
    assert patch["target_component"] == "system_prompt"
    assert patch["model_scope"] == "model_family"
    assert "model_family" in patch


@pytest.mark.asyncio
async def test_propose_mutation_deterministic_patches_stay_portable():
    from core.harness_evolution_service import HarnessEvolutionService

    svc = HarnessEvolutionService.__new__(HarnessEvolutionService)
    tripwire = await svc.propose_mutation({"tool": "shell", "step_type": "action"})
    assert tripwire["target_component"] == "ast_tripwire"
    assert tripwire["model_scope"] == "all"
    compaction = await svc.propose_mutation({"tool": "search", "step_type": "observation"})
    assert compaction["target_component"] == "context_compaction"
    assert compaction["model_scope"] == "all"


def test_applicable_patches_scope_filtering():
    from core.harness_evolution_service import applicable_patches

    patches = [
        {"patch_id": "p1", "target_component": "ast_tripwire", "model_scope": "all"},
        {"patch_id": "p2", "target_component": "system_prompt",
         "model_scope": "model_family", "model_family": "gpt-5.4"},
        {"patch_id": "p4", "target_component": "system_prompt",
         "model_scope": "model_family", "model_family": "deepseek-v4-flash"},
        {"patch_id": "p5", "target_component": "system_prompt",
         "model_scope": "model_family", "model_family": None},  # unknown origin
    ]
    ids_gpt = {p["patch_id"] for p in applicable_patches(patches, "GPT-5.4-2026-03")}
    assert ids_gpt == {"p1", "p2"}  # unknown-origin p5 fail-safe excluded
    ids_ds = {p["patch_id"] for p in applicable_patches(patches, "deepseek-v4-flash")}
    assert ids_ds == {"p1", "p4"}
    # Variant tiers are separate families: pro must NOT receive flash's patch
    ids_pro = {p["patch_id"] for p in applicable_patches(patches, "deepseek-v4-pro")}
    assert ids_pro == {"p1"}


def test_applicable_patches_drift_expiry(tmp_path, monkeypatch):
    """Amendment: drift on the serving alias immediately suppresses its
    family-scoped patches — not just next mining cycle."""
    from core.harness_evolution_service import applicable_patches

    det = ModelDriftDetector(state_path=tmp_path / "d.json")
    monkeypatch.setenv("ATOM_MODEL_DRIFT_DETECTION_ENABLED", "true")

    patches = [
        {"patch_id": "portable", "target_component": "ast_tripwire", "model_scope": "all"},
        {"patch_id": "scoped", "target_component": "system_prompt",
         "model_scope": "model_family", "model_family": "gpt-5.4"},
    ]
    det.observe("openai", "gpt-5.4-2026-03", "snap-old")
    before = {p["patch_id"] for p in applicable_patches(
        patches, "gpt-5.4-2026-03", provider_id="openai", drift_detector=det)}
    assert before == {"portable", "scoped"}

    det.observe("openai", "gpt-5.4-2026-03", "snap-new")  # silent bump!
    after = {p["patch_id"] for p in applicable_patches(
        patches, "gpt-5.4-2026-03", provider_id="openai", drift_detector=det)}
    assert after == {"portable"}  # scoped patch expired immediately


# ── rec #1d: reasoning-step provenance columns ────────────────────────


def test_agent_reasoning_step_has_provenance_columns():
    from core.models import AgentReasoningStep

    cols = {c.name for c in AgentReasoningStep.__table__.columns}
    assert "requested_model" in cols
    assert "resolved_model" in cols


def test_reasoning_step_roundtrip_with_provenance():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.models import AgentReasoningStep, Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        row = AgentReasoningStep(
            execution_id="exec-1",
            step_number=1,
            step_type="thought",
            requested_model="gpt-5.4-2026-03",
            resolved_model="gpt-5.4-2026-03-snap",
        )
        db.add(row)
        db.commit()
        got = db.query(AgentReasoningStep).filter_by(execution_id="exec-1").one()
        assert got.resolved_model == "gpt-5.4-2026-03-snap"
