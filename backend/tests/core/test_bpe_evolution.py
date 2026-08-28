"""BPE gap-closure tests: persistence, evolution search, telemetry feed.

Covers restore-on-restart (JSON store + lazy registry restore), the
AlphaEvolve-lite population search (genome clamping, mutation bounds,
elite diversity, flag-gated apply), the harness-evolution weakness feed,
and workspace bound-genome threading.
"""
from __future__ import annotations

import asyncio
import random

import pytest

from core.bpe.workspace import (
    GENE_BOUNDS,
    MAX_SUBGOALS,
    BPEWorkspace,
    get_active_bounds,
    get_workspace,
    reset_registry,
    set_active_bounds,
)


def apply(ws: BPEWorkspace, *args):
    return asyncio.run(ws.apply(*args))


@pytest.fixture(autouse=True)
def _clean():
    reset_registry()
    set_active_bounds(None)
    yield
    reset_registry()
    set_active_bounds(None)


# ---------------------------------------------------------------------------
# Gap B — durable persistence + lazy restore
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPersistence:
    def test_save_and_load_round_trip(self, tmp_path):
        from core.bpe.persistence import BPEWorkspaceStore

        store = BPEWorkspaceStore(data_dir=tmp_path)
        ws = BPEWorkspace("w1", "agentA", "sess1")
        apply(ws, "commit", "durable step")
        ws.experience.add("skills", "persistent procedure")
        assert store.save(ws.to_dict()) is True
        loaded = store.load("w1", "agentA", "sess1")
        assert loaded is not None
        restored = BPEWorkspace.from_dict(loaded)
        assert restored.progress[0].title == "durable step"
        assert restored.experience.recall("persistent procedure")

    def test_load_missing_returns_none(self, tmp_path):
        from core.bpe.persistence import BPEWorkspaceStore

        store = BPEWorkspaceStore(data_dir=tmp_path)
        assert store.load("w", "a", "s") is None

    def test_lru_bound_keeps_recent(self, tmp_path):
        from core.bpe.persistence import BPEWorkspaceStore, MAX_SCOPES_PER_WORKSPACE

        store = BPEWorkspaceStore(data_dir=tmp_path)
        for i in range(MAX_SCOPES_PER_WORKSPACE + 4):
            store.save({"workspace_id": "w", "agent_id": "a",
                        "scope_key": f"s{i}", "progress": [], "pending_notes": []})
        import json

        with open(store._path_for("w")) as f:
            scopes = json.load(f)
        assert len(scopes) <= MAX_SCOPES_PER_WORKSPACE
        assert "a|s3" not in scopes  # oldest evicted
        assert f"a|s{MAX_SCOPES_PER_WORKSPACE + 3}" in scopes

    def test_oversized_snapshot_rejected(self, tmp_path):
        from core.bpe.persistence import BPEWorkspaceStore

        store = BPEWorkspaceStore(data_dir=tmp_path)
        ws = BPEWorkspace("w", "a", "s")
        ws.experience.add("skills", "x" * 70_000)
        assert store.save(ws.to_dict()) is False

    def test_corrupt_file_degrades_to_empty(self, tmp_path):
        from core.bpe.persistence import BPEWorkspaceStore

        store = BPEWorkspaceStore(data_dir=tmp_path)
        store.data_dir.mkdir(parents=True, exist_ok=True)
        store._path_for("w").write_text("{not json")
        assert store.load("w", "a", "s") is None

    def test_registry_lazy_restore(self, tmp_path, monkeypatch):
        """Cold registry + persisted snapshot → get_workspace restores."""
        from core.bpe.persistence import BPEWorkspaceStore

        store = BPEWorkspaceStore(data_dir=tmp_path)
        ws = BPEWorkspace("w", "agentA", "sess9")
        apply(ws, "commit", "restore me")
        store.save(ws.to_dict())

        original_init = BPEWorkspaceStore.__init__

        def patched_init(self, data_dir=None):
            original_init(self, data_dir=tmp_path)

        monkeypatch.setattr(
            "core.bpe.persistence.BPEWorkspaceStore.__init__", patched_init
        )
        reset_registry()  # simulate process restart
        restored_ws = get_workspace("w", "agentA", "sess9")
        assert restored_ws.progress[0].title == "restore me"


# ---------------------------------------------------------------------------
# Gap D — workspace bounds genome threading
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWorkspaceBounds:
    def test_defaults_until_genome_applied(self):
        bounds = get_active_bounds()
        assert bounds["max_subgoals"] == MAX_SUBGOALS

    def test_genome_clamped_to_gene_bounds(self):
        effective = set_active_bounds({"max_subgoals": 999, "recall_top_k": 1,
                                       "max_entries_per_category": 10_000,
                                       "max_render_chars": -5})
        lo, hi = GENE_BOUNDS["max_subgoals"]
        assert effective["max_subgoals"] == hi
        assert effective["recall_top_k"] == GENE_BOUNDS["recall_top_k"][0]
        assert effective["max_entries_per_category"] == GENE_BOUNDS["max_entries_per_category"][1]
        assert effective["max_render_chars"] == GENE_BOUNDS["max_render_chars"][0]

    def test_invalid_genome_entries_ignored(self):
        effective = set_active_bounds({"max_subgoals": "not-a-number"})
        assert effective["max_subgoals"] == MAX_SUBGOALS

    def test_new_workspaces_honor_bounds(self):
        set_active_bounds({"max_subgoals": 5})
        ws = BPEWorkspace()
        for i in range(8):
            apply(ws, "commit", f"g{i}")
        assert len(ws.progress) == 5

    def test_experience_honors_capacity(self):
        set_active_bounds({"max_entries_per_category": 40})
        ws = BPEWorkspace()
        for i in range(45):
            ws.experience.add("skills", f"unique skill entry {i}")
        assert len(ws.experience._categories["skills"]) == 40


# ---------------------------------------------------------------------------
# Gap D — AlphaEvolve-lite population search
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEvolutionSearch:
    def test_clamp_and_validation(self):
        from core.bpe.evolution import clamp_genome

        genome = clamp_genome(dict.fromkeys(GENE_BOUNDS, 10**9))
        assert set(genome) == set(GENE_BOUNDS)  # all clamped into range
        for gene, (lo, hi) in GENE_BOUNDS.items():
            assert lo <= genome[gene] <= hi

    def test_mutate_single_gene_in_bounds(self):
        from core.bpe.evolution import mutate, random_genome

        rng = random.Random(7)
        parent = random_genome(rng)
        for _ in range(50):
            child = mutate(parent, rng)
            diffs = sum(1 for g in GENE_BOUNDS if child[g] != parent[g])
            assert diffs <= 1
            for gene, (lo, hi) in GENE_BOUNDS.items():
                assert lo <= child[gene] <= hi

    def test_random_genome_in_bounds(self):
        from core.bpe.evolution import random_genome

        rng = random.Random(1)
        for _ in range(20):
            genome = random_genome(rng)
            for gene, (lo, hi) in GENE_BOUNDS.items():
                assert lo <= genome[gene] <= hi

    def test_population_keeps_top_n_distinct(self):
        from core.bpe.evolution import POPULATION_SIZE, Population, random_genome

        rng = random.Random(3)
        pop = Population(rng=rng)
        for i in range(30):
            pop.report("fam", random_genome(rng), fitness=float(i))
        fam = pop.snapshot()["fam"]
        assert len(fam) == POPULATION_SIZE
        genomes = {tuple(sorted(i["genome"].items())) for i in fam}
        assert len(genomes) == POPULATION_SIZE  # distinct

    def test_report_rejects_incomplete_genome(self):
        from core.bpe.evolution import Population

        pop = Population()
        assert pop.report("fam", {"max_subgoals": 6}, 1.0) is False

    def test_propose_cold_population_samples_fresh(self):
        from core.bpe.evolution import Population

        pop = Population(rng=random.Random(5))
        genome = pop.propose("cold")
        assert set(genome) == set(GENE_BOUNDS)

    def test_propose_mutates_an_elite(self):
        from core.bpe.evolution import Population, random_genome

        pop = Population(rng=random.Random(11))
        parent = random_genome(pop.rng)
        pop.report("fam", parent, 1.0)
        child = pop.propose("fam")
        diffs = sum(1 for g in GENE_BOUNDS if child[g] != parent[g])
        assert diffs <= 1

    def test_fitness_penalizes_call_rate_drift(self):
        from core.bpe.evolution import fitness_from_signals

        on_target = fitness_from_signals(0.5, 1.0)
        drifted = fitness_from_signals(0.5, 5.0)
        assert on_target > drifted
        assert fitness_from_signals(-1.0, 1.0) < 0

    def test_apply_best_flag_gated(self, monkeypatch):
        from core.bpe import evolution
        from core.bpe.evolution import Population

        monkeypatch.delenv("ATOM_BPE_EVOLUTION_ENABLED", raising=False)
        pop = Population()
        genome = {g: (lo + hi) // 2 if isinstance(lo, int) else (lo + hi) / 2
                  for g, (lo, hi) in GENE_BOUNDS.items()}
        pop.report("fam", genome, 2.0)
        monkeypatch.setattr(evolution, "population", pop)
        assert evolution.apply_best("fam") is None  # flag off → proposal only

        monkeypatch.setenv("ATOM_BPE_EVOLUTION_ENABLED", "true")
        applied = evolution.apply_best("fam")
        assert applied is not None
        assert get_active_bounds() == genome


# ---------------------------------------------------------------------------
# Gap C — telemetry → harness-evolution weakness feed
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTelemetryFeed:
    def test_errored_consults_become_patterns(self, monkeypatch):
        from core.observability import tracing
        from core.bpe.telemetry_feed import collect_bpe_weakness_patterns

        tracing.clear_spans()
        ws = BPEWorkspace()
        apply(ws, "note", "")  # fails → error span
        patterns = collect_bpe_weakness_patterns()
        assert patterns, "expected harness_action pattern"
        pat = patterns[0]
        assert pat["step_type"] == "harness_action"
        assert pat["tool"].startswith("bpe.note")
        assert pat["failure_count"] >= 1

    def test_negative_value_agents_become_patterns(self, monkeypatch):
        from core.observability import tracing
        from core.bpe.telemetry_feed import collect_bpe_weakness_patterns
        from core.bpe.consult_policy import get_consult_policy

        tracing.clear_spans()
        policy = get_consult_policy()
        for _ in range(5):
            policy.record_episode("sad_agent", consult_count=3, success=False,
                                  step_efficiency=2.0)
        patterns = collect_bpe_weakness_patterns()
        consult_pats = [p for p in patterns if p["step_type"] == "consult_value"]
        assert consult_pats, "expected consult_value pattern"
        assert consult_pats[0]["agent_id"] == "sad_agent"
        assert consult_pats[0]["tool"] == "workspace.block"

    def test_harness_evolution_service_appends_bpe_patterns(self):
        """mine_weaknesses appends bpe.* patterns to the DB-mined list."""
        from unittest.mock import MagicMock, patch

        from core.observability import tracing

        tracing.clear_spans()
        apply(BPEWorkspace(), "recall", "")  # failing consult → error span

        from core.harness_evolution_service import HarnessEvolutionService

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        service = HarnessEvolutionService(db)
        import asyncio

        patterns = asyncio.run(service.mine_weaknesses("t1"))
        assert any(
            p.get("step_type") == "harness_action" and "recall" in p.get("tool", "")
            for p in patterns
        )


# ---------------------------------------------------------------------------
# Gap E — property tests: render determinism + bounds
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenderProperties:
    def test_render_deterministic_and_bounded(self):
        hypothesis = pytest.importorskip("hypothesis")
        from hypothesis import given, settings
        from hypothesis import strategies as st

        note = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())
        title = st.text(min_size=1, max_size=120).filter(lambda s: s.strip())

        @settings(max_examples=25, deadline=None)
        @given(st.lists(st.tuples(note, title), min_size=1, max_size=6))
        def run(pairs):
            ws = BPEWorkspace()
            for n, t in pairs:
                ws._pending_notes.append(n)
                asyncio.run(ws.apply("commit", t))
            first = ws.render()
            second = ws.render()
            assert first == second  # deterministic
            from core.bpe.workspace import MAX_RENDER_CHARS

            assert len(first) <= MAX_RENDER_CHARS + 1
            if first:
                assert first.startswith("WORKSPACE STATE")

        run()
