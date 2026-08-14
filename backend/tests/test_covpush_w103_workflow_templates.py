# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/orchestration/workflow_templates.py to 100%.

Complements tests/test_enhanced_orchestration.py (template happy-path
instantiation) with: TemplateParameter.validate across all types and
constraints (string pattern, int/float min/max, boolean, array, enum,
None-required), validate_parameters (missing required, type failure,
jsonschema success + ValidationError), instantiate (ValueError on invalid,
${param} substitution, unresolved placeholder passthrough, step field
copying), TemplateLibrary (register/get/list/search by name/description/
tag, category index miss, statistics, standard-template seed set), and the
get_template_library factory. Zero LLM/network.
"""
import pytest
from jsonschema import ValidationError

from core.orchestration.workflow_templates import (
    ParameterType,
    TemplateCategory,
    TemplateLibrary,
    TemplateParameter,
    WorkflowStepTemplate,
    WorkflowTemplate,
    get_template_library,
)


# ============================================================================
# TemplateParameter.validate
# ============================================================================

class TestTemplateParameterValidate:
    def test_none_required_rejected(self):
        p = TemplateParameter(name="x", required=True)
        assert p.validate(None) is False

    def test_none_optional_accepted(self):
        p = TemplateParameter(name="x", required=False)
        assert p.validate(None) is True

    def test_string_ok(self):
        assert TemplateParameter(name="x", type=ParameterType.STRING).validate("hi") is True

    def test_string_wrong_type(self):
        assert TemplateParameter(name="x", type=ParameterType.STRING).validate(5) is False

    def test_string_pattern_match(self):
        p = TemplateParameter(name="x", type=ParameterType.STRING, pattern=r"^[a-z]+$")
        assert p.validate("abc") is True
        assert p.validate("AbC1") is False

    def test_integer_type_check(self):
        p = TemplateParameter(name="x", type=ParameterType.INTEGER)
        assert p.validate(3) is True
        assert p.validate("3") is False
        assert p.validate(3.5) is False

    def test_integer_min_max(self):
        p = TemplateParameter(name="x", type=ParameterType.INTEGER, min_value=1, max_value=5)
        assert p.validate(0) is False
        assert p.validate(6) is False
        assert p.validate(3) is True

    def test_integer_min_only(self):
        p = TemplateParameter(name="x", type=ParameterType.INTEGER, min_value=2)
        assert p.validate(1) is False
        assert p.validate(2) is True

    def test_integer_max_only(self):
        p = TemplateParameter(name="x", type=ParameterType.INTEGER, max_value=2)
        assert p.validate(3) is False
        assert p.validate(2) is True

    def test_float_accepts_int(self):
        p = TemplateParameter(name="x", type=ParameterType.FLOAT)
        assert p.validate(3) is True
        assert p.validate(3.5) is True
        assert p.validate("3") is False

    def test_float_min_max(self):
        p = TemplateParameter(name="x", type=ParameterType.FLOAT, min_value=0.5, max_value=1.5)
        assert p.validate(0.4) is False
        assert p.validate(2.0) is False
        assert p.validate(1.0) is True

    def test_boolean_strict(self):
        p = TemplateParameter(name="x", type=ParameterType.BOOLEAN)
        assert p.validate(True) is True
        assert p.validate(False) is True
        assert p.validate(1) is False  # int is not bool

    def test_array_requires_list(self):
        p = TemplateParameter(name="x", type=ParameterType.ARRAY)
        assert p.validate(["a"]) is True
        assert p.validate("a") is False
        assert p.validate({}) is False

    def test_enum_allowed_values(self):
        p = TemplateParameter(name="x", type=ParameterType.ENUM, allowed_values=["full", "incremental"])
        assert p.validate("full") is True
        assert p.validate("delta") is False

    def test_enum_without_allowed_values_passes_any(self):
        p = TemplateParameter(name="x", type=ParameterType.ENUM)
        assert p.validate("anything") is True


# ============================================================================
# WorkflowTemplate.validate_parameters / instantiate
# ============================================================================

def _template(**overrides):
    defaults = dict(
        template_id="t1",
        name="T1",
        parameters=[
            TemplateParameter(name="req", type=ParameterType.STRING, required=True),
            TemplateParameter(name="opt", type=ParameterType.INTEGER, required=False, default=1, min_value=1, max_value=3),
        ],
        steps=[
            WorkflowStepTemplate(
                step_id="s1",
                name="Step 1",
                step_type="agent",
                agent_type="analyst",
                capability="summarize",
                parameters={"prompt": "summarize ${req}", "keep": 1},
                depends_on=["s0"],
                next_steps=["s2"],
                condition="ok",
                parallel_group="g1",
                timeout_seconds=42,
            )
        ],
        start_step="s1",
    )
    defaults.update(overrides)
    return WorkflowTemplate(**defaults)


class TestValidateParameters:
    def test_valid_params(self):
        valid, errors = _template().validate_parameters({"req": "hello", "opt": 2})
        assert valid is True
        assert errors == []

    def test_missing_required(self):
        valid, errors = _template().validate_parameters({"opt": 2})
        assert valid is False
        assert any("Required parameter 'req' is missing" in e for e in errors)

    def test_type_failure(self):
        valid, errors = _template().validate_parameters({"req": "hi", "opt": "not-an-int"})
        assert valid is False
        assert any("'opt' validation failed" in e for e in errors)

    def test_schema_validation_success(self):
        t = _template(
            input_schema={
                "type": "object",
                "properties": {"req": {"type": "string"}},
                "required": ["req"],
            }
        )
        valid, errors = t.validate_parameters({"req": "hello"})
        assert valid is True

    def test_schema_validation_failure(self):
        t = _template(
            input_schema={
                "type": "object",
                "properties": {"req": {"type": "string"}},
                "required": ["req", "extra"],
            }
        )
        valid, errors = t.validate_parameters({"req": "hello"})
        assert valid is False
        assert any("Schema validation failed" in e for e in errors)


class TestInstantiate:
    def test_success_builds_workflow(self):
        wf = _template().instantiate({"req": "hello"})
        assert wf["workflow_id"].startswith("wf_")
        assert wf["name"] == "T1"
        assert wf["template_id"] == "t1"
        assert wf["template_version"] == "1.0.0"
        assert wf["start_step"] == "s1"
        assert wf["parameters"] == {"req": "hello"}
        assert len(wf["steps"]) == 1

    def test_invalid_params_raise_valueerror(self):
        with pytest.raises(ValueError, match="Invalid parameters"):
            _template().instantiate({})

    def test_parameter_substitution_in_steps(self):
        wf = _template().instantiate({"req": "quarterly"})
        step = wf["steps"][0]
        assert step["parameters"]["prompt"] == "summarize quarterly"
        assert step["parameters"]["keep"] == 1  # non-template value untouched
        assert step["depends_on"] == ["s0"]
        assert step["next_steps"] == ["s2"]
        assert step["condition"] == "ok"
        assert step["parallel_group"] == "g1"
        assert step["timeout_seconds"] == 42
        assert step["agent_type"] == "analyst"
        assert step["capability"] == "summarize"

    def test_unresolved_placeholder_passthrough(self):
        # ${missing} not in params → placeholder text left in place
        t = _template(
            steps=[
                WorkflowStepTemplate(
                    step_id="s1",
                    name="Step 1",
                    parameters={"prompt": "summarize ${missing} and ${req}"},
                )
            ]
        )
        wf = t.instantiate({"req": "hi"})
        assert wf["steps"][0]["parameters"]["prompt"] == "summarize ${missing} and hi"

    def test_whole_value_placeholder_keeps_type(self):
        t = _template(
            steps=[
                WorkflowStepTemplate(
                    step_id="s1",
                    name="Step 1",
                    parameters={"limit": "${count}"},
                )
            ]
        )
        wf = t.instantiate({"req": "x", "count": 7})
        # whole-value placeholder substitutes the raw (uncoerced) value
        assert wf["steps"][0]["parameters"]["limit"] == 7

    def test_empty_steps(self):
        t = _template(steps=[])
        wf = t.instantiate({"req": "hi"})
        assert wf["steps"] == []

    def test_original_template_parameters_not_mutated(self):
        t = _template()
        t.instantiate({"req": "hello"})
        # step parameter dict copied — original untouched
        assert t.steps[0].parameters["prompt"] == "summarize ${req}"


# ============================================================================
# TemplateLibrary
# ============================================================================

class TestTemplateLibrary:
    def test_standard_templates_seeded(self):
        lib = TemplateLibrary()
        ids = {t.template_id for t in lib.list_templates()}
        assert {"data_sync_automation", "report_generation", "approval_workflow", "monitoring_alert"} <= ids
        assert len(ids) >= 4

    def test_register_and_get(self):
        lib = TemplateLibrary()
        t = _template()
        lib.register_template(t)
        assert lib.get_template("t1") is t
        assert lib.get_template("missing") is None

    def test_get_templates_by_category(self):
        lib = TemplateLibrary()
        report = [t for t in lib.list_templates() if t.category == TemplateCategory.REPORTING]
        assert len(report) == 1
        assert lib.get_templates_by_category(TemplateCategory.REPORTING) == report

    def test_get_templates_by_category_empty(self):
        lib = TemplateLibrary()
        assert lib.get_templates_by_category(TemplateCategory.DATA_PIPELINE) == []

    def test_search_by_name(self):
        lib = TemplateLibrary()
        results = lib.search_templates("Report Generation")
        assert any(t.template_id == "report_generation" for t in results)

    def test_search_by_description_case_insensitive(self):
        lib = TemplateLibrary()
        results = lib.search_templates("ALERT")
        assert any(t.template_id == "monitoring_alert" for t in results)

    def test_search_by_tag(self):
        lib = TemplateLibrary()
        results = lib.search_templates("approval")
        assert any(t.template_id == "approval_workflow" for t in results)

    def test_search_no_match(self):
        lib = TemplateLibrary()
        assert lib.search_templates("zzz_nothing_matches") == []

    def test_statistics(self):
        lib = TemplateLibrary()
        stats = lib.get_statistics()
        assert stats["total_templates"] >= 4
        assert stats["category_distribution"]["automation"] >= 1
        assert stats["category_distribution"]["approval"] == 1
        assert "data_sync_automation" in stats["parameter_counts"]

    def test_registered_template_in_category_index(self):
        lib = TemplateLibrary()
        t = _template()
        lib.register_template(t)
        assert t in lib.get_templates_by_category(TemplateCategory.AUTOMATION)


class TestFactory:
    def test_factory_returns_singleton(self):
        import core.orchestration.workflow_templates as wt_mod
        wt_mod._template_library_instance = None
        try:
            lib1 = get_template_library()
            lib2 = get_template_library()
            assert lib1 is lib2
        finally:
            wt_mod._template_library_instance = None


class TestEnums:
    def test_category_values(self):
        assert TemplateCategory.AUTOMATION.value == "automation"
        assert TemplateCategory.MONITORING.value == "monitoring"

    def test_parameter_type_values(self):
        assert ParameterType.DATETIME.value == "datetime"
        assert ParameterType.DATE.value == "date"
        assert ParameterType.OBJECT.value == "object"
