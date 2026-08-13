# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/model_factory (70 stmts, never wave-tested).

- create_pydantic_model: JSON Schema → Pydantic model for every TYPE_MAP
  member (string/integer/number/boolean/array/object/null), unknown types
  fall back to str, array-of-null collapses to str, nullable union types
  ("string","null") → Optional[str], required vs optional defaults, field
  descriptions, empty properties, schema-level validation errors.
- invalidate_cache no-op contract, ModelFactory(cache=...) constructor.
- get_model_factory singleton bootstrap (imports core.cache).

No LLM / no network / pydantic only.
"""
from typing import Optional

import pytest
from pydantic import BaseModel, ValidationError

from core.model_factory import ModelFactory, get_model_factory


def _schema(properties, required=None):
    schema = {"type": "object", "properties": properties}
    if required is not None:
        schema["required"] = required
    return schema


class TestCreateModel:
    def test_all_primitive_types(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Product",
            _schema({
                "sku": {"type": "string"},
                "qty": {"type": "integer"},
                "price": {"type": "number"},
                "active": {"type": "boolean"},
                "tags": {"type": "array"},
                "meta": {"type": "object"},
                "note": {"type": "null"},
            }),
        )
        assert issubclass(model, BaseModel)
        assert model.__name__ == "Product"
        assert model.model_fields["sku"].annotation is str
        assert model.model_fields["qty"].annotation is int
        assert model.model_fields["price"].annotation is float
        assert model.model_fields["active"].annotation is bool
        assert model.model_fields["tags"].annotation is list
        assert model.model_fields["meta"].annotation is dict
        assert model.model_fields["note"].annotation is type(None)

    def test_unknown_type_falls_back_to_str(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Thing",
            _schema({"when": {"type": "date"}}),
        )
        assert model.model_fields["when"].annotation is str

    def test_required_field_no_default(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Req",
            _schema({"name": {"type": "string"}}, required=["name"]),
        )
        assert model.model_fields["name"].is_required() is True

    def test_optional_field_defaults_none(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Opt",
            _schema({"name": {"type": "string"}}),
        )
        assert model.model_fields["name"].is_required() is False
        assert model.model_fields["name"].default is None

    def test_required_field_validation_fails_when_missing(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Req",
            _schema({"name": {"type": "string"}}, required=["name"]),
        )
        with pytest.raises(ValidationError):
            model()

    def test_required_field_validates_ok(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Req",
            _schema({"name": {"type": "string"}}, required=["name"]),
        )
        assert model(name="widget").name == "widget"

    def test_type_mismatch_fails_validation(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Typed",
            _schema({"qty": {"type": "integer"}}, required=["qty"]),
        )
        with pytest.raises(ValidationError):
            model(qty="not-an-int")

    def test_field_description_set(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Doc",
            _schema({"name": {"type": "string", "description": "The name field"}}),
        )
        assert model.model_fields["name"].description == "The name field"

    def test_nullable_union_type(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Nullable",
            _schema({"email": {"type": ["string", "null"]}}),
        )
        assert model.model_fields["email"].annotation == Optional[str]
        assert model(email=None).email is None
        assert model(email="a@b.c").email == "a@b.c"

    def test_union_type_without_null(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Union",
            _schema({"val": {"type": ["string", "integer"]}}),
        )
        assert model.model_fields["val"].annotation is str

    def test_array_of_only_null_collapses_to_optional_str(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Weird",
            _schema({"val": {"type": ["null", "null"]}}),
        )
        assert model.model_fields["val"].annotation == Optional[str]

    def test_empty_properties(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "Empty",
            _schema({}),
        )
        assert model.model_fields == {}

    def test_missing_type_defaults_to_str(self):
        model = ModelFactory().create_pydantic_model(
            "t1", "NoType",
            _schema({"x": {"description": "no type given"}}),
        )
        assert model.model_fields["x"].annotation is str

    def test_invalidate_cache_returns_zero(self):
        assert ModelFactory().invalidate_cache("t1", "Product") == 0

    def test_constructor_accepts_cache(self):
        assert ModelFactory(cache="fake-cache").cache == "fake-cache"


class TestGetModelFactory:
    def test_singleton_bootstrap(self, monkeypatch):
        import core.model_factory as mf
        from core.cache import cache

        monkeypatch.setattr(mf, "_model_factory", None)
        factory = get_model_factory()
        assert isinstance(factory, ModelFactory)
        assert factory.cache is cache
        assert get_model_factory() is factory
