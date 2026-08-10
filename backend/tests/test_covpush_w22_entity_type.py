"""Coverage wave 22 — core/entity_type_service uncovered branches (TDD).

Covers missed lines after the CRUD/bughunt suites:
- merge_entity_types (missing source/target, workspace filter, commit error)
- resolve_or_create_draft (existing unchanged, evolving, new draft)
- compare_schema_versions + _generate_json_patch (all op types, missing versions)
- rollback_to_version (missing, system, bad version, success)
- detect_breaking_changes (removals critical/info, type changes, required adds)
- _normalize_type (list/ref/enum/unknown)
- generate_migration_suggestions (removal high/low, replace type change)
- _generate_type_conversion_script (known/fallback converters)
- _is_valid_slug, close/context manager, get_entity_type_service factory
- update_entity_type validation failure, delete hard/soft + errors
"""
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from core.entity_type_service import EntityTypeService, get_entity_type_service
from core.models import EntityTypeDefinition


@pytest.fixture
def service():
    validator = Mock()
    validator.validate_schema = Mock(return_value=(True, ""))
    factory = Mock()
    factory.invalidate_cache = Mock(return_value=0)
    factory.invalidate_model_cache = Mock()
    db = Mock(spec=Session)
    db.add = Mock()
    db.flush = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.delete = Mock()
    db.rollback = Mock()
    svc = EntityTypeService(db=db, schema_validator=validator, model_factory=factory)
    return svc


def _etype(**kw):
    defaults = dict(
        id="et-1", tenant_id="t1", slug="customer", display_name="Customer",
        json_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        is_system=False, is_active=True, version=1, metadata_json={},
        available_skills=None, description=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _chain(db, first_result=None, all_result=None, update_result=None):
    q = Mock()
    q.filter = Mock(return_value=q)
    q.order_by = Mock(return_value=q)
    q.limit = Mock(return_value=q)
    q.offset = Mock(return_value=q)
    q.first = Mock(return_value=first_result)
    if all_result is not None:
        q.all = Mock(return_value=all_result)
    if update_result is not None:
        q.update = Mock(return_value=update_result)
    db.query = Mock(return_value=q)
    return q


class TestMerge:
    def test_merge_source_missing(self, service):
        _chain(service.db, first_result=None)
        with pytest.raises(ValueError):
            service.merge_entity_types("t1", "src", "customer")

    def test_merge_target_missing(self, service):
        _chain(service.db, first_result=None)
        with patch.object(service, "get_entity_type", side_effect=[_etype(id="src"), None]):
            with pytest.raises(ValueError):
                service.merge_entity_types("t1", "src", "customer")

    def test_merge_success(self, service):
        source = _etype(id="src", slug="discovered", metadata_json={"discovery_reasoning": "found"})
        target = _etype(id="et-1", slug="customer", metadata_json={"merges": []})
        with patch.object(service, "get_entity_type", side_effect=[source, target]):
            q = _chain(service.db, update_result=3)
            result = service.merge_entity_types("t1", "src", "customer")
        assert result is True
        assert q.filter.called
        assert target.metadata_json["merges"][0]["nodes_count"] == 3
        assert source.is_active is False

    def test_merge_commit_error(self, service):
        source = _etype(id="src", slug="discovered")
        target = _etype(id="et-1", slug="customer")
        with patch.object(service, "get_entity_type", side_effect=[source, target]):
            _chain(service.db, update_result=0)
            service.db.commit.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                service.merge_entity_types("t1", "src", "customer")
        assert service.db.rollback.called


class TestResolveOrCreateDraft:
    def test_draft_existing_unchanged(self, service):
        existing = _etype(version=2)
        _chain(service.db, first_result=existing)
        result = service.resolve_or_create_draft("t1", "customer", "Customer", existing.json_schema)
        assert result is existing

    def test_draft_existing_evolving(self, service):
        existing = _etype(version=2)
        _chain(service.db, first_result=existing)
        updated = _etype(version=3)
        with patch.object(service, "update_entity_type", return_value=updated) as upd:
            result = service.resolve_or_create_draft("t1", "customer", "Customer", {"type": "object", "x": 1})
        upd.assert_called_once()
        assert result is updated

    def test_draft_new(self, service):
        _chain(service.db, first_result=None)
        created = _etype()
        with patch.object(service, "create_entity_type", return_value=created) as cr:
            result = service.resolve_or_create_draft("t1", "customer", "Customer", {"type": "object"})
        cr.assert_called_once()
        assert result is created


class TestVersionCompare:
    def test_compare_missing_version(self, service):
        _chain(service.db, first_result=None)
        with pytest.raises(ValueError):
            service.compare_schema_versions("t1", "et-1", 1, 2)

    def test_compare_returns_patch(self, service):
        from_snap = SimpleNamespace(json_schema={
            "properties": {"a": {"type": "string"}, "b": {"type": "number"}},
            "required": ["a"],
        })
        to_snap = SimpleNamespace(json_schema={
            "properties": {"a": {"type": "integer"}, "c": {"type": "boolean"}},
            "required": ["a", "c"],
        })
        q = Mock()
        q.filter = Mock(return_value=q)
        q.first = Mock(side_effect=[from_snap, to_snap])
        service.db.query = Mock(return_value=q)
        from_schema, to_schema, ops = service.compare_schema_versions("t1", "et-1", 1, 2)
        assert len(ops) == 4  # add c, remove b, replace a, required/- add c

    def test_json_patch_required_add_remove(self, service):
        from_s = {"properties": {"a": {"type": "string"}, "b": {"type": "number"}}, "required": ["a", "b"]}
        to_s = {"properties": {"a": {"type": "string"}, "b": {"type": "number"}}, "required": ["a"]}
        ops = service._generate_json_patch(from_s, to_s)
        assert any(o["op"] == "remove" and o["path"] == "/required/b" for o in ops)

    def test_json_patch_no_changes(self, service):
        s = {"properties": {"a": {"type": "string"}}, "required": ["a"]}
        assert service._generate_json_patch(s, s) == []


class TestRollback:
    def test_rollback_missing_entity(self, service):
        _chain(service.db, first_result=None)
        with patch.object(service, "get_entity_type", return_value=None):
            with pytest.raises(ValueError):
                service.rollback_to_version("t1", "et-1", 1)

    def test_rollback_system_type(self, service):
        with patch.object(service, "get_entity_type", return_value=_etype(is_system=True)):
            with pytest.raises(ValueError):
                service.rollback_to_version("t1", "et-1", 1)

    def test_rollback_target_missing(self, service):
        with patch.object(service, "get_entity_type", return_value=_etype(version=3)):
            q = Mock()
            q.filter = Mock(return_value=q)
            q.first = Mock(return_value=None)
            q.all = Mock(return_value=[])
            service.db.query = Mock(return_value=q)
            with pytest.raises(ValueError):
                service.rollback_to_version("t1", "et-1", 1)

    def test_rollback_target_not_in_past(self, service):
        with patch.object(service, "get_entity_type", return_value=_etype(version=3)):
            q = Mock()
            q.filter = Mock(return_value=q)
            q.first = Mock(return_value=_etype(version=3))
            service.db.query = Mock(return_value=q)
            with pytest.raises(ValueError):
                service.rollback_to_version("t1", "et-1", 3)

    def test_rollback_success(self, service):
        entity = _etype(version=3)
        target = _etype(version=1, json_schema={"type": "object"}, display_name="Old", description="d", available_skills=["s"])
        with patch.object(service, "get_entity_type", return_value=entity):
            q = Mock()
            q.filter = Mock(return_value=q)
            q.first = Mock(side_effect=[target, target])
            q.all = Mock(return_value=[target])
            service.db.query = Mock(return_value=q)
            with patch.object(service, "_create_version_snapshot", return_value=Mock()) as snap:
                result = service.rollback_to_version("t1", "et-1", 1, changed_by="u1")
        snap.assert_called_once()
        assert result.version == 4
        assert result.json_schema == {"type": "object"}
        assert service.db.commit.called

    def test_rollback_commit_error(self, service):
        entity = _etype(version=3)
        target = _etype(version=1, json_schema={"type": "object"})
        with patch.object(service, "get_entity_type", return_value=entity):
            q = Mock()
            q.filter = Mock(return_value=q)
            q.first = Mock(side_effect=[target, target])
            q.all = Mock(return_value=[target])
            service.db.query = Mock(return_value=q)
            service.db.commit.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                service.rollback_to_version("t1", "et-1", 1)
        assert service.db.rollback.called


class TestBreakingChanges:
    def test_breaking_changes_all_severities(self, service):
        with patch.object(service, "get_entity_type", return_value=_etype(json_schema={
            "properties": {
                "keep": {"type": "string"},
                "gone": {"type": "string"},
                "typed": {"type": "string"},
            },
            "required": ["gone"],
        })):
            result = service.detect_breaking_changes("t1", "et-1", {
                "properties": {
                    "keep": {"type": "string"},
                    "typed": {"type": "number"},
                },
                "required": ["keep", "newreq"],
            })
        assert result["has_breaking_changes"] is True
        kinds = [c["type"] for c in result["changes"]]
        assert "property_removed" in kinds
        assert "property_type_changed" in kinds
        assert "required_added" in kinds
        assert result["summary"]["critical"] >= 1

    def test_breaking_changes_missing_entity(self, service):
        with patch.object(service, "get_entity_type", return_value=None):
            with pytest.raises(ValueError):
                service.detect_breaking_changes("t1", "et-1", {})

    def test_breaking_changes_no_changes(self, service):
        schema = {"properties": {"a": {"type": "string"}}, "required": []}
        with patch.object(service, "get_entity_type", return_value=_etype(json_schema=schema)):
            result = service.detect_breaking_changes("t1", "et-1", schema)
        assert result["has_breaking_changes"] is False

    def test_normalize_type_variants(self, service):
        assert service._normalize_type({"type": ["string", "null"]}) == "string | null"
        assert service._normalize_type({"type": "integer"}) == "integer"
        assert service._normalize_type({"$ref": "#/defs/x"}) == "#/defs/x"
        assert service._normalize_type({"enum": ["a", "b"]}) == "enum: [a, b]"
        assert service._normalize_type({}) == "unknown"


class TestMigrationSuggestions:
    def test_suggestions_removal_and_replace(self, service):
        with patch.object(service, "get_entity_type", return_value=_etype(json_schema={
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "string"},
            },
            "required": ["name"],
        })):
            result = service.generate_migration_suggestions("t1", "et-1", {
                "properties": {"age": {"type": "number"}},
            })
        assert result["entity_type_slug"] == "customer"
        priorities = {s["type"]: s["priority"] for s in result["suggestions"]}
        assert priorities["field_removal"] == "high"  # name was required
        assert priorities["type_change"] == "medium"
        assert result["summary"]["high"] == 1

    def test_suggestions_missing_entity(self, service):
        with patch.object(service, "get_entity_type", return_value=None):
            with pytest.raises(ValueError):
                service.generate_migration_suggestions("t1", "et-1", {})

    def test_conversion_script_known(self, service):
        js = service._generate_type_conversion_script("age", "string", "number")
        assert "Number(value) || 0" in js["javascript"]
        assert "CAST(age AS NUMBER)" in js["sql"]

    def test_conversion_script_fallback(self, service):
        js = service._generate_type_conversion_script("x", "object", "array")
        assert "String(value)" in js["javascript"]


class TestMisc:
    def test_update_validation_failure(self, service):
        entity = _etype()
        with patch.object(service, "get_entity_type", return_value=entity):
            service.validator.validate_schema = Mock(return_value=(False, "bad schema"))
            with pytest.raises(ValueError):
                service.update_entity_type("t1", "et-1", json_schema={"type": "oops"})

    def test_delete_hard(self, service):
        entity = _etype()
        with patch.object(service, "get_entity_type", return_value=entity):
            result = service.delete_entity_type("t1", "et-1", hard_delete=True)
        assert result is True
        assert service.db.delete.called
        assert service.db.commit.called

    def test_delete_hard_error(self, service):
        entity = _etype()
        with patch.object(service, "get_entity_type", return_value=entity):
            service.db.commit.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                service.delete_entity_type("t1", "et-1", hard_delete=True)
        assert service.db.rollback.called

    def test_delete_not_found(self, service):
        with patch.object(service, "get_entity_type", return_value=None):
            assert service.delete_entity_type("t1", "et-1") is False

    def test_slug_validator(self, service):
        assert service._is_valid_slug("abc_123-XYZ") is True
        assert service._is_valid_slug("bad slug!") is False
        assert service._is_valid_slug("x" * 101) is False

    def test_context_manager(self, service):
        with service as svc:
            assert svc is service

    def test_factory_with_db(self):
        with patch("core.entity_type_service.EntityTypeService") as cls:
            get_entity_type_service(db=Mock())
            cls.assert_called_once()

    def test_factory_singleton(self):
        import core.entity_type_service as ets
        ets._services.clear()
        svc1 = get_entity_type_service()
        svc2 = get_entity_type_service()
        assert svc1 is svc2
