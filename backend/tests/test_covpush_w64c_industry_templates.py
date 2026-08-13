"""Coverage push wave 64c — core/industry_workflow_templates.py (TDD).

Target: >=95% statement coverage STANDALONE (this file alone).

Covers: catalog initialization (all 7 industry template factories), dataclass
defaults (auto created_at + explicit), template lookup/filtering/search
(keyword matches on name/description/use_cases, no-match and combined
filters), ROI math (weekly/monthly/annual, custom hourly rate, missing
template, unparseable time savings, zero-hours "Never" payback), and the
thread-safe module-level singleton (first-call creation, cache hit,
reset-and-recreate, concurrent access).

No bugs found in the module; all uncovered lines were plain untested
branches.
"""
import threading
from datetime import datetime

import pytest

import core.industry_workflow_templates as iwt
from core.industry_workflow_templates import (
    Industry,
    IndustryWorkflowEngine,
    IndustryWorkflowTemplate,
    get_industry_workflow_engine,
)


def make_template(**overrides):
    """Build a minimal IndustryWorkflowTemplate for injection."""
    defaults = dict(
        id="custom_template",
        name="Custom Template",
        description="A custom template for tests",
        industry=Industry.TECHNOLOGY,
        sub_category="Custom",
        complexity="Beginner",
        estimated_time_savings="5 hours/week",
        required_integrations=["slack"],
        optional_integrations=[],
        workflow_data={"nodes": [], "edges": []},
        setup_instructions=["Step one"],
        benefits=["Saves time"],
        use_cases=["General use"],
    )
    defaults.update(overrides)
    return IndustryWorkflowTemplate(**defaults)


class TestIndustryEnum:
    """Industry enum contract."""

    def test_all_industries_and_values(self):
        expected = {
            "HEALTHCARE": "healthcare",
            "FINANCE": "finance",
            "EDUCATION": "education",
            "RETAIL": "retail",
            "MANUFACTURING": "manufacturing",
            "REAL_ESTATE": "real_estate",
            "LEGAL": "legal",
            "NON_PROFIT": "non_profit",
            "TECHNOLOGY": "technology",
            "CONSULTING": "consulting",
            "HOSPITALITY": "hospitality",
            "LOGISTICS": "logistics",
        }
        for name, value in expected.items():
            member = getattr(Industry, name)
            assert member.value == value
            assert isinstance(member, Industry)

    def test_enum_stringification(self):
        assert str(Industry.HEALTHCARE) == "Industry.HEALTHCARE"


class TestIndustryWorkflowTemplateDataclass:
    """Dataclass defaults and custom values."""

    def test_created_at_auto_generated(self):
        template = make_template()
        assert template.created_at is not None
        assert isinstance(template.created_at, str)
        # ISO-ish timestamp, must parse as datetime
        datetime.fromisoformat(template.created_at)

    def test_created_at_explicit_value_preserved(self):
        fixed = "2026-01-01T00:00:00"
        template = make_template(created_at=fixed)
        assert template.created_at == fixed

    def test_compliance_notes_none_by_default(self):
        template = make_template()
        assert template.compliance_notes is None

    def test_full_field_roundtrip(self):
        template = make_template(
            id="t1",
            name="N",
            description="D",
            industry=Industry.LEGAL,
            sub_category="SC",
            complexity="Advanced",
            estimated_time_savings="10 hours/week",
            required_integrations=["a"],
            optional_integrations=["b"],
            workflow_data={"nodes": [{"id": "1"}], "edges": []},
            setup_instructions=["s"],
            benefits=["b1"],
            use_cases=["u1"],
            compliance_notes=["n1"],
        )
        assert template.id == "t1"
        assert template.name == "N"
        assert template.industry == Industry.LEGAL
        assert template.complexity == "Advanced"
        assert template.required_integrations == ["a"]
        assert template.workflow_data["nodes"][0]["id"] == "1"
        assert template.compliance_notes == ["n1"]


class TestEngineCatalog:
    """Catalog initialization covers every template factory body."""

    def test_engine_init_populates_all_templates(self):
        engine = IndustryWorkflowEngine()
        expected_ids = {
            "healthcare_patient_onboarding",
            "finance_expense_approval",
            "education_student_enrollment",
            "retail_inventory_management",
            "real_estate_client_onboarding",
            "legal_case_management",
            "tech_content_file_management",
        }
        assert set(engine.templates.keys()) == expected_ids
        assert all(isinstance(t, IndustryWorkflowTemplate) for t in engine.templates.values())

    def test_each_template_has_industry_workflow_data(self):
        engine = IndustryWorkflowEngine()
        for template_id, template in engine.templates.items():
            assert template.id == template_id
            assert template.industry in Industry
            assert "nodes" in template.workflow_data
            assert "edges" in template.workflow_data
            assert template.workflow_data["nodes"]
            assert template.complexity in ("Beginner", "Intermediate", "Advanced")
            assert template.estimated_time_savings
            assert template.required_integrations
            assert template.setup_instructions
            assert template.benefits
            assert template.use_cases

    def test_healthcare_template_compliance_notes(self):
        engine = IndustryWorkflowEngine()
        template = engine.get_template_by_id("healthcare_patient_onboarding")
        assert template.compliance_notes
        assert any("HIPAA" in note for note in template.compliance_notes)

    def test_legal_template_compliance_notes(self):
        engine = IndustryWorkflowEngine()
        template = engine.get_template_by_id("legal_case_management")
        assert template.compliance_notes
        assert any("privilege" in note.lower() for note in template.compliance_notes)

    def test_finance_template_edges_with_conditions(self):
        engine = IndustryWorkflowEngine()
        template = engine.get_template_by_id("finance_expense_approval")
        conditions = [e.get("condition") for e in template.workflow_data["edges"]]
        assert "yes" in conditions
        assert "no" in conditions


class TestTemplateLookup:
    """Lookup + industry filtering."""

    def test_get_template_by_id_found(self):
        engine = IndustryWorkflowEngine()
        template = engine.get_template_by_id("retail_inventory_management")
        assert template is not None
        assert template.industry == Industry.RETAIL

    def test_get_template_by_id_missing(self):
        engine = IndustryWorkflowEngine()
        assert engine.get_template_by_id("does_not_exist") is None

    def test_get_templates_by_industry(self):
        engine = IndustryWorkflowEngine()
        tech = engine.get_templates_by_industry(Industry.TECHNOLOGY)
        assert len(tech) == 1
        assert tech[0].id == "tech_content_file_management"
        empty = engine.get_templates_by_industry(Industry.HOSPITALITY)
        assert empty == []

    def test_get_all_industries(self):
        engine = IndustryWorkflowEngine()
        industries = engine.get_all_industries()
        assert set(industries) == {
            Industry.HEALTHCARE,
            Industry.FINANCE,
            Industry.EDUCATION,
            Industry.RETAIL,
            Industry.REAL_ESTATE,
            Industry.LEGAL,
            Industry.TECHNOLOGY,
        }
        assert len(industries) == 7


class TestSearchTemplates:
    """Search filter combinations, incl. keyword edge cases."""

    def test_no_filters_returns_all(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates()
        assert len(results) == len(engine.templates)

    def test_industry_filter(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(industry=Industry.FINANCE)
        assert len(results) == 1
        assert results[0].industry == Industry.FINANCE

    def test_industry_filter_no_match(self):
        engine = IndustryWorkflowEngine()
        assert engine.search_templates(industry=Industry.NON_PROFIT) == []

    def test_complexity_filter(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(complexity="Advanced")
        assert results
        assert all(t.complexity == "Advanced" for t in results)

    def test_complexity_filter_no_match(self):
        engine = IndustryWorkflowEngine()
        assert engine.search_templates(complexity="Expert") == []

    def test_keyword_matches_name(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(keywords=["patient"])
        assert any(t.id == "healthcare_patient_onboarding" for t in results)

    def test_keyword_matches_description(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(keywords=["insurance verification"])
        assert any(t.id == "healthcare_patient_onboarding" for t in results)

    def test_keyword_matches_use_cases_only(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(keywords=["law firms"])
        assert any(t.id == "legal_case_management" for t in results)
        assert any(t.id == "tech_content_file_management" for t in results) is False

    def test_keyword_case_insensitive(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(keywords=["PATIENT"])
        assert results

    def test_keyword_no_match(self):
        engine = IndustryWorkflowEngine()
        assert engine.search_templates(keywords=["quantum flux"]) == []

    def test_combined_filters(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(
            industry=Industry.TECHNOLOGY,
            complexity="Intermediate",
            keywords=["file"],
        )
        assert [t.id for t in results] == ["tech_content_file_management"]

    def test_combined_filters_conflict_empty(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(
            industry=Industry.HEALTHCARE,
            complexity="Advanced",
        )
        assert results == []

    def test_multiple_keywords_any_match(self):
        engine = IndustryWorkflowEngine()
        results = engine.search_templates(keywords=["warehouse", "training"])
        ids = {t.id for t in results}
        assert "retail_inventory_management" in ids
        assert "education_student_enrollment" in ids


class TestCalculateROI:
    """ROI math, error branches and payback edge cases."""

    def test_roi_math_default_rate(self):
        engine = IndustryWorkflowEngine()
        roi = engine.calculate_roi("healthcare_patient_onboarding")
        assert roi["time_savings"]["hours_per_week"] == 8
        assert roi["time_savings"]["weekly_savings"] == 8 * 50.0
        assert roi["time_savings"]["monthly_savings"] == 8 * 50.0 * 4.33
        assert roi["time_savings"]["annual_savings"] == 8 * 50.0 * 4.33 * 12
        assert roi["implementation"]["estimated_setup_hours"] == 8
        assert roi["implementation"]["setup_cost"] == 400.0
        assert roi["implementation"]["payback_period_weeks"] == 1.0

    def test_roi_math_custom_rate(self):
        engine = IndustryWorkflowEngine()
        roi = engine.calculate_roi("finance_expense_approval", hourly_rate=100.0)
        assert roi["time_savings"]["weekly_savings"] == 10 * 100.0
        assert roi["implementation"]["setup_cost"] == 800.0

    def test_roi_template_not_found(self):
        engine = IndustryWorkflowEngine()
        assert engine.calculate_roi("missing") == {"error": "Template not found"}

    def test_roi_unparseable_time_savings(self):
        engine = IndustryWorkflowEngine()
        engine.templates["custom"] = make_template(
            estimated_time_savings="varies by season")
        assert engine.calculate_roi("custom") == {
            "error": "Could not calculate time savings"}

    def test_roi_zero_hours_never_payback(self):
        engine = IndustryWorkflowEngine()
        engine.templates["custom"] = make_template(
            estimated_time_savings="0 hours/week")
        roi = engine.calculate_roi("custom")
        assert roi["time_savings"]["hours_per_week"] == 0
        assert roi["implementation"]["payback_period_weeks"] == "Never"

    def test_roi_hours_without_slash(self):
        engine = IndustryWorkflowEngine()
        engine.templates["custom"] = make_template(
            estimated_time_savings="3 hours week")
        roi = engine.calculate_roi("custom")
        assert roi["time_savings"]["hours_per_week"] == 3


class TestEngineSingleton:
    """Module-level get_industry_workflow_engine singleton semantics."""

    def teardown_method(self):
        iwt._industry_workflow_engine = None

    def test_first_call_creates_and_returns_engine(self):
        engine = get_industry_workflow_engine()
        assert isinstance(engine, IndustryWorkflowEngine)
        assert len(engine.templates) == 7

    def test_second_call_returns_same_instance(self):
        first = get_industry_workflow_engine()
        second = get_industry_workflow_engine()
        assert first is second

    def test_reset_global_recreates_instance(self):
        first = get_industry_workflow_engine()
        iwt._industry_workflow_engine = None
        second = get_industry_workflow_engine()
        assert second is not first
        assert isinstance(second, IndustryWorkflowEngine)

    def test_concurrent_calls_single_instance(self):
        iwt._industry_workflow_engine = None
        results = []
        errors = []

        def _call():
            try:
                results.append(get_industry_workflow_engine())
            except Exception as exc:  # pragma: no cover - failure surface
                errors.append(exc)

        threads = [threading.Thread(target=_call) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(results) == 8
        assert len({id(r) for r in results}) == 1

    def test_engine_object_is_independent(self):
        engine = get_industry_workflow_engine()
        engine.templates["extra"] = make_template(id="extra")
        assert "extra" in get_industry_workflow_engine().templates
        iwt._industry_workflow_engine = None
        assert "extra" not in get_industry_workflow_engine().templates
