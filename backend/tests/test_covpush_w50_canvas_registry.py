"""Coverage wave 50 — core/canvas_type_registry (66% → 100%).

- get_type (found/missing), get_all_types copy
- validate_canvas_type / validate_component / validate_layout (missing type,
  valid/invalid component/layout)
- check_governance_permission (unknown type, allowed/denied action)
- get_min_maturity / get_components_for_type / get_layouts_for_type
  (found/missing)
- get_canvas_info (found/missing), get_all_canvas_info
- singleton registry has all 7 types
"""
from unittest.mock import MagicMock

import pytest

from core.canvas_type_registry import CanvasType, CanvasTypeRegistry, canvas_type_registry


@pytest.fixture
def registry():
    return CanvasTypeRegistry()


class TestTypeLookup:
    def test_get_type(self, registry):
        meta = registry.get_type("docs")
        assert meta is not None
        assert meta.canvas_type == "docs"
        assert registry.get_type("bogus") is None

    def test_get_all_types_copy(self, registry):
        types = registry.get_all_types()
        assert len(types) >= 7
        types["bogus"] = "x"  # mutation must not leak
        assert registry.get_type("bogus") is None


class TestValidation:
    def test_validate_canvas_type(self, registry):
        assert registry.validate_canvas_type("docs") is True
        assert registry.validate_canvas_type("bogus") is False

    def test_validate_component(self, registry):
        assert registry.validate_component("docs", "rich_editor") is True
        assert registry.validate_component("docs", "not_a_component") is False
        assert registry.validate_component("bogus", "rich_editor") is False

    def test_validate_layout(self, registry):
        assert registry.validate_layout("docs", "document") is True
        assert registry.validate_layout("docs", "not_a_layout") is False
        assert registry.validate_layout("bogus", "document") is False


class TestGovernance:
    def test_check_permission_unknown_type(self, registry):
        assert registry.check_governance_permission("bogus", "autonomous") is False

    def test_check_permission_allowed(self, registry):
        # docs: AUTONOMOUS has create
        assert registry.check_governance_permission("docs", "autonomous", "create") is True

    def test_check_permission_denied(self, registry):
        # docs: STUDENT has no delete
        assert registry.check_governance_permission("docs", "student", "delete") is False


class TestMetadataAccess:
    def test_get_min_maturity(self, registry):
        assert registry.get_min_maturity("docs") is not None
        assert registry.get_min_maturity("bogus") is None

    def test_get_components(self, registry):
        assert "rich_editor" in registry.get_components_for_type("docs")
        assert registry.get_components_for_type("bogus") == []

    def test_get_layouts(self, registry):
        assert "document" in registry.get_layouts_for_type("docs")
        assert registry.get_layouts_for_type("bogus") == []


class TestInfo:
    def test_get_canvas_info(self, registry):
        info = registry.get_canvas_info("docs")
        assert info["type"] == "docs"
        assert info["min_maturity"]
        assert "rich_editor" in info["components"]
        assert registry.get_canvas_info("bogus") is None

    def test_get_all_canvas_info(self, registry):
        infos = registry.get_all_canvas_info()
        assert len(infos) >= 7
        assert all(i["type"] for i in infos)


class TestSingleton:
    def test_singleton_has_all_types(self):
        for t in ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]:
            assert canvas_type_registry.get_type(t) is not None
