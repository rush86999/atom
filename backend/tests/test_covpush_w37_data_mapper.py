"""Coverage wave 37 — core/integration_data_mapper.py (TDD, pure).

Drives the data-mapping system end-to-end: every transformation type
(direct copy / value mapping / format conversions / calculations /
concatenation / conditional / custom functions), condition operators,
all field-type conversions, failure tracking (required re-raise vs
default fallback), schema registration + default schemas, mapping
creation validation, bulk/single transform, type matching for all
FieldTypes, data validation (required/type/unknown-type/bulk), mapping
import/export and the singleton — zero I/O, zero spend.
"""
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.integration_data_mapper import (
    DataTransformer,
    FieldMapping,
    FieldType,
    IntegrationDataMapper,
    IntegrationSchema,
    TransformationType,
    get_data_mapper,
)


def fm(**kw):
    defaults = dict(
        source_field="src", target_field="tgt",
        source_type=FieldType.STRING, target_type=FieldType.STRING,
        transformation=TransformationType.DIRECT_COPY,
        transformation_config=None, required=True, default_value=None)
    defaults.update(kw)
    return FieldMapping(**defaults)


def make_mapper():
    return IntegrationDataMapper()


class TestTransformField:
    def test_none_with_default(self):
        t = DataTransformer()
        assert t.transform_field(
            None, fm(default_value="DFLT"), {}) == "DFLT"

    def test_none_required_raises(self):
        t = DataTransformer()
        with pytest.raises(ValueError, match="Required field src is missing"):
            t.transform_field(None, fm(), {})

    def test_none_optional_returns_none(self):
        t = DataTransformer()
        assert t.transform_field(None, fm(required=False), {}) is None

    def test_unknown_transformation_passthrough(self):
        t = DataTransformer()
        assert t.transform_field("x", fm(), {}) == "x"

    def test_type_conversion_applied(self):
        t = DataTransformer()
        assert t.transform_field(
            "42", fm(target_type=FieldType.INTEGER), {}) == 42

    def test_failure_required_reraises(self):
        t = DataTransformer()
        with pytest.raises(ValueError):
            t.transform_field("x", fm(target_type=FieldType.EMAIL), {})
        assert len(t.failed_transforms) == 1

    def test_failure_optional_returns_default(self):
        t = DataTransformer()
        result = t.transform_field(
            "x", fm(required=False, default_value="FALLBACK",
                    target_type=FieldType.EMAIL), {})
        assert result == "FALLBACK"
        assert t.failed_transforms[0]["field"] == "src"


class TestTransformations:
    def test_direct_copy(self):
        t = DataTransformer()
        assert t._direct_copy("v", fm(), {}) == "v"

    def test_value_mapping(self):
        t = DataTransformer()
        m = fm(transformation_config={"value_map": {"a": "A", "b": "B"}})
        assert t._value_mapping("a", m, {}) == "A"
        assert t._value_mapping("unknown", m, {}) == "unknown"
        assert t._value_mapping(1, m, {}) == 1

    def test_format_date_to_iso(self):
        t = DataTransformer()
        m = fm(transformation_config={"format_type": "date_to_iso"})
        assert t._format_conversion("2026-01-01T00:00:00Z", m, {}) == "2026-01-01T00:00:00+00:00"
        assert t._format_conversion(
            datetime(2026, 1, 1), m, {}) == "2026-01-01T00:00:00"

    def test_format_date_format(self):
        t = DataTransformer()
        m = fm(transformation_config={"format_type": "date_format",
                                      "format": "%d/%m/%Y"})
        assert t._format_conversion("2026-01-01T00:00:00Z", m, {}) == "01/01/2026"
        assert t._format_conversion(datetime(2026, 2, 3), m, {}) == "03/02/2026"

    @pytest.mark.parametrize("fmt,value,expected", [
        ("lowercase", "Hello", "hello"),
        ("uppercase", "Hello", "HELLO"),
        ("title_case", "hello world", "Hello World"),
        ("remove_spaces", "a b c", "abc"),
    ])
    def test_format_string_cases(self, fmt, value, expected):
        t = DataTransformer()
        m = fm(transformation_config={"format_type": fmt})
        assert t._format_conversion(value, m, {}) == expected

    def test_format_unknown(self):
        t = DataTransformer()
        assert t._format_conversion("v", fm(transformation_config={}), {}) == "v"

    def test_calculation_types(self):
        t = DataTransformer()
        m = fm(transformation_config={"calculation_type": "sum_fields",
                                      "fields": ["a", "b"]})
        assert t._calculation(0, m, {"a": 1, "b": 2}) == 3
        m2 = fm(transformation_config={"calculation_type": "multiply",
                                       "multiplier": 3})
        assert t._calculation(5, m2, {}) == 15.0
        m3 = fm(transformation_config={"calculation_type": "percentage",
                                       "percentage": 50})
        assert t._calculation(100, m3, {}) == 50.0
        m4 = fm(transformation_config={"calculation_type": "round",
                                       "decimals": 1})
        assert t._calculation(3.14159, m4, {}) == 3.1
        assert t._calculation(5, fm(transformation_config={}), {}) == 5

    def test_concatenation(self):
        t = DataTransformer()
        m = fm(transformation_config={"fields": ["self", "b"],
                                      "separator": "-"})
        assert t._concatenation("a", m, {"b": "c"}) == "a-c"
        m2 = fm(transformation_config={"fields": ["self", "missing"]})
        assert t._concatenation("a", m2, {}) == "a"

    def test_conditional(self):
        t = DataTransformer()
        m = fm(transformation_config={
            "conditions": [
                {"type": "equals", "field": "status", "operator": "equals",
                 "expected": "active", "result": "OK"},
            ],
            "default": "UNKNOWN"})
        assert t._conditional("x", m, {"status": "active"}) == "OK"
        assert t._conditional("x", m, {"status": "other"}) == "UNKNOWN"
        m2 = fm(transformation_config={
            "conditions": [
                {"type": "self", "field": "self", "operator": "equals",
                 "expected": "v", "result": "SELF"},
            ]})
        assert t._conditional("v", m2, {}) == "SELF"

    def test_custom_functions(self):
        t = DataTransformer()
        m = fm(transformation_config={"function_name": "generate_id"})
        result = t._custom_function("hello", m, {})
        assert len(result) == 12
        m2 = fm(transformation_config={"function_name": "slugify"})
        assert t._custom_function("Hello World_2", m2, {}) == "hello-world-2"
        m3 = fm(transformation_config={"function_name": "extract_domain"})
        assert t._custom_function("https://example.com/path", m3, {}) == "example.com"
        assert t._custom_function("example.com/x", m3, {}) == "example.com"
        m4 = fm(transformation_config={"function_name": "phone_format"})
        assert t._custom_function("5551234567", m4, {}) == "(555) 123-4567"
        assert t._custom_function("123", m4, {}) == "123"
        assert t._custom_function("x", fm(transformation_config={}), {}) == "x"


class TestConditionOperators:
    def test_all_operators(self):
        t = DataTransformer()
        assert t._evaluate_condition("a", "equals", "a") is True
        assert t._evaluate_condition("a", "not_equals", "b") is True
        assert t._evaluate_condition("abc", "contains", "b") is True
        assert t._evaluate_condition("abc", "not_contains", "z") is True
        assert t._evaluate_condition(5, "greater_than", 3) is True
        assert t._evaluate_condition(5, "less_than", 8) is True
        assert t._evaluate_condition("", "is_empty", None) is True
        assert t._evaluate_condition("x", "is_not_empty", None) is True
        assert t._evaluate_condition("a", "bogus", "a") is False


class TestConvertType:
    def test_none(self):
        t = DataTransformer()
        assert t._convert_type(None, FieldType.STRING) is None

    def test_string(self):
        t = DataTransformer()
        assert t._convert_type(42, FieldType.STRING) == "42"

    def test_integer_float(self):
        t = DataTransformer()
        assert t._convert_type("3.7", FieldType.INTEGER) == 3
        assert t._convert_type("2.5", FieldType.FLOAT) == 2.5

    def test_boolean(self):
        t = DataTransformer()
        assert t._convert_type("true", FieldType.BOOLEAN) is True
        assert t._convert_type("no", FieldType.BOOLEAN) is False
        assert t._convert_type(1, FieldType.BOOLEAN) is True

    def test_date_datetime(self):
        t = DataTransformer()
        assert t._convert_type("2026-01-01T00:00:00Z", FieldType.DATE) == "2026-01-01"
        assert t._convert_type(datetime(2026, 1, 1), FieldType.DATE) == "2026-01-01"
        assert t._convert_type("2026-01-01T00:00:00Z", FieldType.DATETIME) == "2026-01-01T00:00:00+00:00"
        assert t._convert_type(datetime(2026, 1, 1), FieldType.DATETIME) == "2026-01-01T00:00:00"
        assert t._convert_type(5, FieldType.DATE) == 5

    def test_email(self):
        t = DataTransformer()
        assert t._convert_type("A@B.COM", FieldType.EMAIL) == "a@b.com"
        with pytest.raises(ValueError, match="Invalid email"):
            t._convert_type("not-an-email", FieldType.EMAIL)

    def test_url(self):
        t = DataTransformer()
        assert t._convert_type("https://x.com", FieldType.URL) == "https://x.com"
        assert t._convert_type("x.com", FieldType.URL) == "https://x.com"

    def test_json(self):
        t = DataTransformer()
        assert t._convert_type('{"a": 1}', FieldType.JSON) == {"a": 1}
        assert t._convert_type({"a": 1}, FieldType.JSON) == {"a": 1}
        assert t._convert_type(5, FieldType.JSON) == 5

    def test_array(self):
        t = DataTransformer()
        assert t._convert_type("a,b,c", FieldType.ARRAY) == ["a", "b", "c"]
        assert t._convert_type([1, 2], FieldType.ARRAY) == [1, 2]
        assert t._convert_type(5, FieldType.ARRAY) == [5]

    def test_object(self):
        t = DataTransformer()
        assert t._convert_type({"k": 1}, FieldType.OBJECT) == {"k": 1}
        assert t._convert_type('{"k": 1}', FieldType.OBJECT) == {"k": 1}
        assert t._convert_type(5, FieldType.OBJECT) == {"value": 5}

    def test_conversion_error_reraises(self):
        t = DataTransformer()
        with pytest.raises(Exception):
            t._convert_type("abc", FieldType.INTEGER)


class TestMapper:
    def test_default_schemas(self):
        m = make_mapper()
        assert "asana_task" in m.schemas
        assert "jira_issue" in m.schemas
        assert "salesforce_lead" in m.schemas

    def test_register_schema(self):
        m = make_mapper()
        schema = IntegrationSchema(
            integration_id="custom", integration_name="Custom",
            version="1.0", fields={"f": {"type": "string", "required": False}},
            supported_operations=["create"])
        m.register_schema(schema)
        assert m.schemas["custom"] is schema

    def test_create_mapping_validation(self):
        m = make_mapper()
        with pytest.raises(ValueError, match="Source schema"):
            m.create_mapping("m1", "missing", "jira_issue", [])
        with pytest.raises(ValueError, match="Target schema"):
            m.create_mapping("m1", "asana_task", "missing", [])
        with pytest.raises(ValueError, match="Target field"):
            m.create_mapping("m1", "asana_task", "jira_issue",
                             [fm(source_field="name", target_field="bogus")])

    def test_create_mapping_warns_on_source(self):
        m = make_mapper()
        m.create_mapping("m1", "asana_task", "jira_issue",
                         [fm(source_field="not_in_schema", target_field="summary")])
        assert "m1" in m.mappings

    def test_create_mapping_constant_allowed(self):
        m = make_mapper()
        m.create_mapping("m2", "asana_task", "jira_issue",
                         [fm(source_field="constant", target_field="summary",
                             transformation_config={"constant_value": "X"})])
        assert "m2" in m.mappings

    def test_transform_data(self):
        m = make_mapper()
        m.mappings["m1"] = [fm(source_field="name", target_field="summary")]
        result = m.transform_data({"name": "Task"}, "m1")
        assert result == {"summary": "Task"}
        bulk = m.transform_data([{"name": "A"}, {"name": "B"}], "m1")
        assert bulk == [{"summary": "A"}, {"summary": "B"}]
        with pytest.raises(ValueError, match="Mapping m9 not found"):
            m.transform_data({}, "m9")

    def test_transform_single_constant_and_defaults(self):
        m = make_mapper()
        m.mappings["m1"] = [
            fm(source_field="constant", target_field="c",
               transformation_config={"constant_value": "CONST"}),
            fm(source_field="missing", target_field="d", required=False,
               default_value="DF"),
            fm(source_field="req", target_field="r", required=True,
               default_value=None),
        ]
        result = m._transform_single(
            {}, [mm for mm in m.mappings["m1"] if mm.target_field != "r"])
        assert result["c"] == "CONST"
        assert result["d"] == "DF"
        # required missing field re-raises out of _transform_single
        with pytest.raises(ValueError, match="Required field req is missing"):
            m._transform_single({}, m.mappings["m1"])

    def test_transform_single_required_failure_reraises(self):
        m = make_mapper()
        m.mappings["m1"] = [
            fm(source_field="bad", target_field="e", target_type=FieldType.EMAIL)]
        with pytest.raises(ValueError):
            m._transform_single({"bad": "nope"}, m.mappings["m1"])

    def test_value_matches_type(self):
        assert IntegrationDataMapper._value_matches_type("x", "string") is True
        assert IntegrationDataMapper._value_matches_type(5, "string") is False
        assert IntegrationDataMapper._value_matches_type(5, "integer") is True
        assert IntegrationDataMapper._value_matches_type(True, "integer") is True
        assert IntegrationDataMapper._value_matches_type("-42", "integer") is True
        assert IntegrationDataMapper._value_matches_type("a", "integer") is False
        assert IntegrationDataMapper._value_matches_type(1.5, "float") is True
        assert IntegrationDataMapper._value_matches_type(True, "float") is False
        assert IntegrationDataMapper._value_matches_type("1.5", "float") is True
        assert IntegrationDataMapper._value_matches_type("x", "float") is False
        assert IntegrationDataMapper._value_matches_type(True, "boolean") is True
        assert IntegrationDataMapper._value_matches_type("yes", "boolean") is True
        assert IntegrationDataMapper._value_matches_type(1, "boolean") is False
        assert IntegrationDataMapper._value_matches_type(
            "2026-01-01T00:00:00Z", "date") is True
        assert IntegrationDataMapper._value_matches_type("nope", "date") is False
        assert IntegrationDataMapper._value_matches_type(5, "date") is False
        assert IntegrationDataMapper._value_matches_type("a@b.co", "email") is True
        assert IntegrationDataMapper._value_matches_type("nope", "email") is False
        assert IntegrationDataMapper._value_matches_type(5, "email") is False
        assert IntegrationDataMapper._value_matches_type("https://x", "url") is True
        assert IntegrationDataMapper._value_matches_type("x", "url") is False
        assert IntegrationDataMapper._value_matches_type({"a": 1}, "json") is True
        assert IntegrationDataMapper._value_matches_type('{"a": 1}', "json") is True
        assert IntegrationDataMapper._value_matches_type("{bad", "json") is False
        assert IntegrationDataMapper._value_matches_type([1], "array") is True
        assert IntegrationDataMapper._value_matches_type("x", "array") is False
        assert IntegrationDataMapper._value_matches_type({"k": 1}, "object") is True
        assert IntegrationDataMapper._value_matches_type(5, "object") is False
        assert IntegrationDataMapper._value_matches_type(5, "mystery_type") is True

    def test_validate_data(self):
        m = make_mapper()
        with pytest.raises(ValueError, match="Schema ghost not found"):
            m.validate_data({}, "ghost")

        schema = IntegrationSchema(
            integration_id="test", integration_name="T", version="1.0",
            fields={
                "req": {"type": "string", "required": True},
                "num": {"type": "integer", "required": False},
                "weird": {"type": "bogus_type", "required": False},
            },
            supported_operations=["create"])
        m.register_schema(schema)

        result = m.validate_data({"req": "x", "num": 5}, "test")
        assert result["valid"] is True
        assert result["validated_count"] == 1

        result2 = m.validate_data({"num": "not-int"}, "test")
        assert result2["valid"] is False
        assert any("Required field 'req'" in e for e in result2["errors"])
        assert any("invalid type" in e for e in result2["errors"])

        result3 = m.validate_data({"req": "", "weird": 1}, "test")
        assert result3["valid"] is False
        assert any("Unknown field type" in w for w in result3["warnings"])

        result4 = m.validate_data([{"req": "a"}, {"req": 5}], "test")
        assert result4["valid"] is False
        assert result4["validated_count"] == 2
        assert any("Item 2" in e for e in result4["errors"])

    def test_schema_and_mapping_lists(self):
        m = make_mapper()
        assert len(m.list_schemas()) == 3
        assert m.get_schema_info("jira_issue") is not None
        assert m.get_schema_info("ghost") is None
        assert m.list_mappings() == []

    def test_export_import_mapping(self):
        m = make_mapper()
        with pytest.raises(ValueError, match="Mapping m9 not found"):
            m.export_mapping("m9")
        m.mappings["m1"] = [fm(source_field="a", target_field="b")]
        exported = m.export_mapping("m1")
        assert exported["mapping_id"] == "m1"
        assert len(exported["field_mappings"]) == 1

        m2 = make_mapper()
        m2.import_mapping(exported)
        assert "m1" in m2.mappings

    def test_singleton(self):
        from core.integration_data_mapper import _data_mapper
        _data_mapper = None
        s1 = get_data_mapper()
        s2 = get_data_mapper()
        assert s1 is s2
        _data_mapper = None
