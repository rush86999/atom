"""R83 #7 — compliance control-mapping registry on core.feature_flags.

The registry extends feature_flags.py (the existing 14-function substrate)
with a declarative control → framework-requirement map plus live coverage /
gap reporting, so governance enumerates "which flags satisfy which
controls" instead of hand-maintaining docs/compliance/COMPLIANCE_MAPPING.md.
"""
from __future__ import annotations

import pytest

from core.feature_flags import (
    COMPLIANCE_FRAMEWORKS,
    CONTROL_MAPPINGS,
    get_compliance_coverage,
    get_control_mappings,
)


class TestRegistryShape:
    def test_registry_seeded_and_well_formed(self):
        assert len(CONTROL_MAPPINGS) >= 10
        for cid, entry in CONTROL_MAPPINGS.items():
            assert entry.get("title"), cid
            assert entry.get("implementation"), cid
            assert entry.get("evidence"), cid
            frameworks = entry.get("frameworks") or {}
            assert frameworks, f"{cid} maps to no framework"
            for fw, reqs in frameworks.items():
                assert fw in COMPLIANCE_FRAMEWORKS, f"{cid}: unknown framework {fw}"
                assert isinstance(reqs, list) and reqs, f"{cid}.{fw}: empty reqs"

    def test_nist_ai_rmf_function_ids_valid(self):
        valid = {"GOVERN", "MAP", "MEASURE", "MANAGE"}
        for cid, entry in CONTROL_MAPPINGS.items():
            for fn in entry["frameworks"].get("nist_ai_rmf", []):
                assert fn in valid, f"{cid}: bad RMF function {fn}"

    def test_get_control_mappings_returns_copy(self):
        mappings = get_control_mappings()
        mappings["llm.cascade_routing"]["frameworks"]["soc2"].append("XX9.9")
        assert "XX9.9" not in CONTROL_MAPPINGS["llm.cascade_routing"]["frameworks"]["soc2"]


class TestLiveResolution:
    def test_bool_resolver_follows_env(self, monkeypatch):
        monkeypatch.setenv("ATOM_SELF_CONSISTENCY", "true")
        coverage = get_compliance_coverage()
        assert coverage["controls"]["llm.self_consistency_voting"]["enabled"] is True

    def test_mode_resolver_off_is_disabled(self, monkeypatch):
        monkeypatch.delenv("ATOM_DATAMARKING", raising=False)
        coverage = get_compliance_coverage()
        assert coverage["controls"]["prompt.datamarking"]["enabled"] is False
        assert "prompt.datamarking" in coverage["gaps"]["disabled_controls"]

    def test_mode_resolver_shadow_is_enabled(self, monkeypatch):
        monkeypatch.setenv("ATOM_DATAMARKING", "shadow")
        coverage = get_compliance_coverage()
        assert coverage["controls"]["prompt.datamarking"]["enabled"] is True

    def test_flagless_controls_report_none_not_false(self):
        coverage = get_compliance_coverage()
        # Always-on controls have no resolver — None, never a wrong True/False.
        assert coverage["controls"]["security.token_encryption"]["enabled"] is None


class TestCoverageGaps:
    def test_gap_structure(self):
        coverage = get_compliance_coverage()
        gaps = coverage["gaps"]
        assert set(gaps) == {
            "disabled_controls",
            "unresolvable",
            "nist_ai_rmf_unmapped_functions",
        }
        assert isinstance(gaps["disabled_controls"], list)
        assert isinstance(gaps["unresolvable"], list)

    def test_all_four_rmf_functions_mapped(self):
        coverage = get_compliance_coverage()
        assert coverage["gaps"]["nist_ai_rmf_unmapped_functions"] == []

    def test_debug_route_registered(self):
        from api.debug_routes import router as debug_router

        paths = {getattr(r, "path", "") for r in debug_router.routes}
        assert "/api/debug/compliance-coverage" in paths
